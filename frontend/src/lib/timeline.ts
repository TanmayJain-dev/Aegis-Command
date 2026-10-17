/**
 * Aegis Command - Detection Timeline Engine.
 * 
 * High-performance timeline loader and sampler supporting:
 * - Schema v2 (track-based keyframes with linear interpolation)
 * - Schema v1 (legacy per-frame detections with 0.05s tolerance window)
 * - Binary search over Float64Array timestamps (zero parseFloat during render loop)
 * - Resolution-decoupled scaling against source metadata (never video.videoWidth)
 */

export const LEGACY_SOURCE_SIZE = { width: 1920, height: 1080 } as const;
export const LEGACY_FPS = 59.94;
export const LEGACY_TOLERANCE_S = 0.05;

export const ALLOWED_PRODUCT_CLASSES = new Set(["person", "car", "truck", "motorcycle", "bus"]);
export const VEHICLE_CLASSES = new Set(["car", "truck", "motorcycle", "bus"]);

export function isVehicleClass(cls: string): boolean {
  return VEHICLE_CLASSES.has((cls || "").toLowerCase());
}

export interface TimelineMeta {
  feed_id: string;
  width: number;
  height: number;
  fps: number;
  duration_s: number;
  stride?: number;
  model?: string;
  weights_sha256?: string;
  imgsz?: number;
  conf?: number;
  date?: string;
  evaluated?: boolean;
  evaluation?: string;
  note?: string;
  cv_metrics?: {
    folds_count?: number;
    person_ap50_mean?: number;
    person_ap50_std?: number;
    vehicle_ap50_mean?: number;
    vehicle_ap50_std?: number;
  };
  feed?: string;
  sahi?: boolean;
  tracker?: string;
  generated_at?: string;
  git_commit?: string;
  generator_commit?: string;
  detections_sha256?: string;
  speed_is_simulated: boolean;
  heading_frame?: string;
}

export interface DrawableDetection {
  id: string;
  class: string;
  confidence: number;
  box: [number, number, number, number]; // [x1, y1, x2, y2] in source resolution coordinates
  speed_kmh: number;
  direction: string;
  interpolated?: boolean;
}

export interface ScaleFactors {
  scaleX: number;
  scaleY: number;
}

export interface Timeline {
  schema: 1 | 2;
  meta: TimelineMeta;
  sampleAt(t: number): DrawableDetection[];
  scaleBox(box: [number, number, number, number], targetWidth: number, targetHeight: number): [number, number, number, number];
  getScale(targetWidth: number, targetHeight: number): ScaleFactors;
  threatKeyframes: Float64Array;
}

// ---------------------------------------------------------------------------
// Numeric Binary Search Utilities
// ---------------------------------------------------------------------------

/**
 * Finds index of closest value in a sorted Float64Array.
 */
export function binarySearchClosest(arr: Float64Array, target: number): number {
  if (arr.length === 0) return -1;
  let left = 0;
  let right = arr.length - 1;
  let closestIdx = 0;
  let minDiff = Math.abs(arr[0] - target);

  while (left <= right) {
    const mid = (left + right) >> 1;
    const diff = Math.abs(arr[mid] - target);

    if (diff < minDiff) {
      minDiff = diff;
      closestIdx = mid;
    }

    if (arr[mid] === target) {
      return mid;
    } else if (arr[mid] < target) {
      left = mid + 1;
    } else {
      right = mid - 1;
    }
  }

  return closestIdx;
}

/**
 * Finds index i such that arr[i] <= target <= arr[i + 1] in a sorted Float64Array.
 * Returns -1 if target is out of bounds [arr[0], arr[arr.length - 1]].
 */
export function binarySearchInterval(arr: Float64Array, target: number): number {
  const len = arr.length;
  if (len < 2 || target < arr[0] || target > arr[len - 1]) {
    return -1;
  }
  if (target === arr[len - 1]) {
    return len - 2;
  }

  let left = 0;
  let right = len - 2;
  let res = 0;

  while (left <= right) {
    const mid = (left + right) >> 1;
    if (arr[mid] <= target) {
      res = mid;
      left = mid + 1;
    } else {
      right = mid - 1;
    }
  }

  return res;
}

// ---------------------------------------------------------------------------
// Schema v2 Implementation
// ---------------------------------------------------------------------------

interface V2ParsedTrack {
  id: string;
  cls: string;
  t: Float64Array;
  box: [number, number, number, number][];
  conf: Float64Array;
  spd_kmh?: Float64Array;
  dir?: string[];
}

export function createV2Timeline(raw: {
  schema: 2;
  meta: Partial<TimelineMeta> & { width: number; height: number };
  tracks: Array<{
    id: string;
    cls: string;
    t: number[];
    box: [number, number, number, number][];
    conf: number[];
    spd_kmh?: number[];
    dir?: string[];
  }>;
}): Timeline {
  const meta: TimelineMeta = {
    feed_id: raw.meta.feed_id ?? "unknown",
    width: raw.meta.width,
    height: raw.meta.height,
    fps: raw.meta.fps ?? LEGACY_FPS,
    duration_s: raw.meta.duration_s ?? 0,
    stride: raw.meta.stride ?? 1,
    model: raw.meta.model,
    imgsz: raw.meta.imgsz,
    tracker: raw.meta.tracker,
    generated_at: raw.meta.generated_at,
    git_commit: raw.meta.git_commit,
    speed_is_simulated: raw.meta.speed_is_simulated ?? true,
    heading_frame: raw.meta.heading_frame ?? "image",
  };

  const tracks: V2ParsedTrack[] = (raw.tracks || [])
    .filter((tr) => ALLOWED_PRODUCT_CLASSES.has((tr.cls || "").toLowerCase()))
    .map((tr) => ({
      id: tr.id,
      cls: tr.cls,
      t: new Float64Array(tr.t),
      box: tr.box,
      conf: new Float64Array(tr.conf),
      spd_kmh: tr.spd_kmh ? new Float64Array(tr.spd_kmh) : undefined,
      dir: tr.dir,
    }));

  // Collect unique keyframe timestamps for threat scrub markers
  const uniqueTimes = new Set<number>();
  for (const tr of tracks) {
    for (let i = 0; i < tr.t.length; i++) {
      uniqueTimes.add(tr.t[i]);
    }
  }
  const threatKeyframes = new Float64Array(
    Array.from(uniqueTimes).sort((a, b) => a - b)
  );

  const getScale = (targetWidth: number, targetHeight: number): ScaleFactors => ({
    scaleX: targetWidth / meta.width,
    scaleY: targetHeight / meta.height,
  });

  const scaleBox = (
    box: [number, number, number, number],
    targetWidth: number,
    targetHeight: number
  ): [number, number, number, number] => {
    const { scaleX, scaleY } = getScale(targetWidth, targetHeight);
    return [
      box[0] * scaleX,
      box[1] * scaleY,
      box[2] * scaleX,
      box[3] * scaleY,
    ];
  };

  const sampleAt = (t: number): DrawableDetection[] => {
    const results: DrawableDetection[] = [];

    for (const track of tracks) {
      const times = track.t;
      const count = times.length;
      if (count === 0) continue;

      // Never extrapolate beyond a track's own keyframes
      if (t < times[0] || t > times[count - 1]) {
        continue;
      }

      if (count === 1) {
        // Single observation: only valid within 1 frame interval
        const frameInterval = 1 / meta.fps;
        if (Math.abs(t - times[0]) <= frameInterval) {
          results.push({
            id: track.id,
            class: track.cls,
            confidence: track.conf[0],
            box: track.box[0],
            speed_kmh: track.spd_kmh ? track.spd_kmh[0] : 0,
            direction: track.dir ? track.dir[0] : "-",
            interpolated: false,
          });
        }
        continue;
      }

      const idx = binarySearchInterval(times, t);
      if (idx === -1) continue;

      const t0 = times[idx];
      const t1 = times[idx + 1];

      if (t === t0) {
        results.push({
          id: track.id,
          class: track.cls,
          confidence: track.conf[idx],
          box: track.box[idx],
          speed_kmh: track.spd_kmh ? track.spd_kmh[idx] : 0,
          direction: track.dir ? track.dir[idx] : "-",
          interpolated: false,
        });
      } else if (t === t1) {
        results.push({
          id: track.id,
          class: track.cls,
          confidence: track.conf[idx + 1],
          box: track.box[idx + 1],
          speed_kmh: track.spd_kmh ? track.spd_kmh[idx + 1] : 0,
          direction: track.dir ? track.dir[idx + 1] : "-",
          interpolated: false,
        });
      } else {
        // Linear interpolation between keyframes
        const alpha = (t - t0) / (t1 - t0);
        const b0 = track.box[idx];
        const b1 = track.box[idx + 1];

        const interpBox: [number, number, number, number] = [
          b0[0] + alpha * (b1[0] - b0[0]),
          b0[1] + alpha * (b1[1] - b0[1]),
          b0[2] + alpha * (b1[2] - b0[2]),
          b0[3] + alpha * (b1[3] - b0[3]),
        ];

        const c0 = track.conf[idx];
        const c1 = track.conf[idx + 1];
        const interpConf = c0 + alpha * (c1 - c0);

        let interpSpd = 0;
        if (track.spd_kmh) {
          const s0 = track.spd_kmh[idx];
          const s1 = track.spd_kmh[idx + 1];
          interpSpd = s0 + alpha * (s1 - s0);
        }

        const dir = track.dir ? (alpha <= 0.5 ? track.dir[idx] : track.dir[idx + 1]) : "-";

        results.push({
          id: track.id,
          class: track.cls,
          confidence: interpConf,
          box: interpBox,
          speed_kmh: interpSpd,
          direction: dir,
          interpolated: true,
        });
      }
    }

    return results;
  };

  return {
    schema: 2,
    meta,
    sampleAt,
    scaleBox,
    getScale,
    threatKeyframes,
  };
}

// ---------------------------------------------------------------------------
// Schema v1 Adapter Implementation
// ---------------------------------------------------------------------------

interface LegacyRawItem {
  id?: string;
  class?: string;
  confidence?: number;
  box: [number, number, number, number];
  speed_kmh?: number;
  direction?: string;
}

export function createV1Timeline(raw: Record<string, LegacyRawItem[]>): Timeline {
  const rawKeys = Object.keys(raw);
  const parsedTimes: number[] = [];

  for (let i = 0; i < rawKeys.length; i++) {
    const num = Number(rawKeys[i]);
    if (!Number.isNaN(num)) {
      parsedTimes.push(num);
    }
  }

  parsedTimes.sort((a, b) => a - b);
  const timesArray = new Float64Array(parsedTimes);
  const frameDetections: DrawableDetection[][] = new Array(parsedTimes.length);

  for (let i = 0; i < parsedTimes.length; i++) {
    const key = String(parsedTimes[i]);
    const items = raw[key] || raw[rawKeys.find((k) => Number(k) === parsedTimes[i]) || ""] || [];
    frameDetections[i] = items
      .filter((item) => ALLOWED_PRODUCT_CLASSES.has((item.class || "").toLowerCase()))
      .map((item) => ({
        id: item.id || "target",
        class: item.class || "unknown",
        confidence: item.confidence ?? 0,
        box: item.box,
        speed_kmh: item.speed_kmh ?? 0,
        direction: item.direction || "-",
        interpolated: false,
      }));
  }

  const duration_s = timesArray.length > 0 ? timesArray[timesArray.length - 1] : 0;

  const rawMeta = (raw as Record<string, unknown>).meta as Partial<TimelineMeta> | undefined;

  const meta: TimelineMeta = {
    feed_id: rawMeta?.feed_id || "legacy",
    width: rawMeta?.width || LEGACY_SOURCE_SIZE.width,
    height: rawMeta?.height || LEGACY_SOURCE_SIZE.height,
    fps: rawMeta?.fps || LEGACY_FPS,
    duration_s: rawMeta?.duration_s || duration_s,
    stride: rawMeta?.stride,
    model: rawMeta?.model,
    weights_sha256: rawMeta?.weights_sha256,
    imgsz: rawMeta?.imgsz,
    conf: rawMeta?.conf,
    date: rawMeta?.date,
    evaluated: rawMeta?.evaluated,
    evaluation: rawMeta?.evaluation,
    note: rawMeta?.note,
    cv_metrics: rawMeta?.cv_metrics,
    feed: rawMeta?.feed,
    sahi: rawMeta?.sahi,
    tracker: rawMeta?.tracker,
    generated_at: rawMeta?.generated_at,
    git_commit: rawMeta?.git_commit,
    generator_commit: rawMeta?.generator_commit,
    detections_sha256: rawMeta?.detections_sha256,
    speed_is_simulated: rawMeta?.speed_is_simulated ?? true,
    heading_frame: rawMeta?.heading_frame || "image",
  };

  const getScale = (targetWidth: number, targetHeight: number): ScaleFactors => ({
    scaleX: targetWidth / meta.width,
    scaleY: targetHeight / meta.height,
  });

  const scaleBox = (
    box: [number, number, number, number],
    targetWidth: number,
    targetHeight: number
  ): [number, number, number, number] => {
    const { scaleX, scaleY } = getScale(targetWidth, targetHeight);
    return [
      box[0] * scaleX,
      box[1] * scaleY,
      box[2] * scaleX,
      box[3] * scaleY,
    ];
  };

  const sampleAt = (t: number): DrawableDetection[] => {
    if (timesArray.length === 0) return [];

    const closestIdx = binarySearchClosest(timesArray, t);
    if (closestIdx === -1) return [];

    const closestTime = timesArray[closestIdx];
    // Enforce 0.05s tolerance window to prevent rendering stale detections
    if (Math.abs(closestTime - t) <= LEGACY_TOLERANCE_S) {
      return frameDetections[closestIdx];
    }

    return [];
  };

  return {
    schema: 1,
    meta,
    sampleAt,
    scaleBox,
    getScale,
    threatKeyframes: timesArray,
  };
}

// ---------------------------------------------------------------------------
// Parser & Loader Entry Points
// ---------------------------------------------------------------------------

export function parseTimeline(data: unknown): Timeline {
  if (!data || typeof data !== "object") {
    return createV1Timeline({});
  }

  const record = data as Record<string, unknown>;
  if (record.schema === 2 && record.meta && Array.isArray(record.tracks)) {
    return createV2Timeline(data as Parameters<typeof createV2Timeline>[0]);
  }

  return createV1Timeline(data as Record<string, LegacyRawItem[]>);
}

export async function loadTimeline(
  url: string,
  fetchFn: typeof fetch = fetch
): Promise<Timeline> {
  const response = await fetchFn(url);
  if (!response.ok) {
    throw new Error(`Failed to load timeline from ${url}: ${response.status} ${response.statusText}`);
  }
  const json = await response.json();
  return parseTimeline(json);
}
