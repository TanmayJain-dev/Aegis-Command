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

export const MAX_BRIDGE_S = 1.0;
export const UNMATCHED_TOLERANCE_S = 0.15;
export const MIN_IOU_THRESHOLD = 0.05;
export const MAX_CENTER_DIST_FACTOR = 1.5;
export const MAX_CENTER_DIST_RATIO = 0.2; // Reject bridging if center distance > 0.2 * meta.width

export function computeBoxIoU(
  a: [number, number, number, number],
  b: [number, number, number, number]
): number {
  const x1 = Math.max(a[0], b[0]);
  const y1 = Math.max(a[1], b[1]);
  const x2 = Math.min(a[2], b[2]);
  const y2 = Math.min(a[3], b[3]);

  const interW = Math.max(0, x2 - x1);
  const interH = Math.max(0, y2 - y1);
  const interArea = interW * interH;

  const areaA = Math.max(0, a[2] - a[0]) * Math.max(0, a[3] - a[1]);
  const areaB = Math.max(0, b[2] - b[0]) * Math.max(0, b[3] - b[1]);

  const unionArea = areaA + areaB - interArea;
  if (unionArea <= 0) return 0;
  return interArea / unionArea;
}

export function computeBoxCenterDist(
  a: [number, number, number, number],
  b: [number, number, number, number]
): number {
  const cAx = (a[0] + a[2]) * 0.5;
  const cAy = (a[1] + a[3]) * 0.5;
  const cBx = (b[0] + b[2]) * 0.5;
  const cBy = (b[1] + b[3]) * 0.5;
  const dx = cAx - cBx;
  const dy = cAy - cBy;
  return Math.sqrt(dx * dx + dy * dy);
}

interface IntervalBridge {
  matched: Array<{
    a: DrawableDetection;
    b: DrawableDetection;
  }>;
  unmatchedA: DrawableDetection[];
  unmatchedB: DrawableDetection[];
}

export function matchSampleBoxes(
  detsA: DrawableDetection[],
  detsB: DrawableDetection[],
  maxCenterDistCap?: number
): IntervalBridge {
  const lenA = detsA.length;
  const lenB = detsB.length;
  const matchedA = new Uint8Array(lenA);
  const matchedB = new Uint8Array(lenB);
  const matched: Array<{ a: DrawableDetection; b: DrawableDetection }> = [];

  // Pass 1: Greedy match by highest IoU (IoU >= 0.05) among same class, respecting distance cap
  const iouCandidates: Array<{ j: number; k: number; iou: number }> = [];
  for (let j = 0; j < lenA; j++) {
    const clsA = (detsA[j].class || "").toLowerCase();
    for (let k = 0; k < lenB; k++) {
      const clsB = (detsB[k].class || "").toLowerCase();
      if (clsA !== clsB) continue;

      const dist = computeBoxCenterDist(detsA[j].box, detsB[k].box);
      if (maxCenterDistCap !== undefined && dist > maxCenterDistCap) continue;

      const iou = computeBoxIoU(detsA[j].box, detsB[k].box);
      if (iou >= MIN_IOU_THRESHOLD) {
        iouCandidates.push({ j, k, iou });
      }
    }
  }

  iouCandidates.sort((p1, p2) => p2.iou - p1.iou);
  for (let i = 0; i < iouCandidates.length; i++) {
    const { j, k } = iouCandidates[i];
    if (matchedA[j] === 0 && matchedB[k] === 0) {
      matchedA[j] = 1;
      matchedB[k] = 1;
      matched.push({ a: detsA[j], b: detsB[k] });
    }
  }

  // Pass 2: Fallback to nearest center distance <= min(1.5 * max(box w, h), maxCenterDistCap) among remaining unmatched of same class
  const distCandidates: Array<{ j: number; k: number; dist: number }> = [];
  for (let j = 0; j < lenA; j++) {
    if (matchedA[j] === 1) continue;
    const boxA = detsA[j].box;
    const wA = boxA[2] - boxA[0];
    const hA = boxA[3] - boxA[1];
    const clsA = (detsA[j].class || "").toLowerCase();

    for (let k = 0; k < lenB; k++) {
      if (matchedB[k] === 1) continue;
      const clsB = (detsB[k].class || "").toLowerCase();
      if (clsA !== clsB) continue;

      const boxB = detsB[k].box;
      const dist = computeBoxCenterDist(boxA, boxB);
      if (maxCenterDistCap !== undefined && dist > maxCenterDistCap) continue;

      const wB = boxB[2] - boxB[0];
      const hB = boxB[3] - boxB[1];
      const maxDim = Math.max(wA, hA, wB, hB);

      if (dist <= MAX_CENTER_DIST_FACTOR * maxDim) {
        distCandidates.push({ j, k, dist });
      }
    }
  }

  distCandidates.sort((p1, p2) => p1.dist - p2.dist);
  for (let i = 0; i < distCandidates.length; i++) {
    const { j, k } = distCandidates[i];
    if (matchedA[j] === 0 && matchedB[k] === 0) {
      matchedA[j] = 1;
      matchedB[k] = 1;
      matched.push({ a: detsA[j], b: detsB[k] });
    }
  }

  const unmatchedA: DrawableDetection[] = [];
  for (let j = 0; j < lenA; j++) {
    if (matchedA[j] === 0) {
      unmatchedA.push(detsA[j]);
    }
  }

  const unmatchedB: DrawableDetection[] = [];
  for (let k = 0; k < lenB; k++) {
    if (matchedB[k] === 0) {
      unmatchedB.push(detsB[k]);
    }
  }

  return { matched, unmatchedA, unmatchedB };
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

  const maxCenterDistCap = MAX_CENTER_DIST_RATIO * meta.width;

  // Precompute bridges between consecutive samples i and i+1 at load time
  const intervalBridges: IntervalBridge[] = new Array(Math.max(0, parsedTimes.length - 1));
  for (let i = 0; i < parsedTimes.length - 1; i++) {
    const gap = timesArray[i + 1] - timesArray[i];
    if (gap <= MAX_BRIDGE_S && gap > 0) {
      intervalBridges[i] = matchSampleBoxes(frameDetections[i], frameDetections[i + 1], maxCenterDistCap);
    } else {
      intervalBridges[i] = {
        matched: [],
        unmatchedA: frameDetections[i],
        unmatchedB: frameDetections[i + 1],
      };
    }
  }

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
    const len = timesArray.length;
    if (len === 0) return [];

    if (len === 1) {
      if (Math.abs(timesArray[0] - t) <= LEGACY_TOLERANCE_S) {
        return frameDetections[0];
      }
      return [];
    }

    // Boundary checks before first and after last
    if (t < timesArray[0]) {
      if (timesArray[0] - t <= LEGACY_TOLERANCE_S) {
        return frameDetections[0];
      }
      return [];
    }
    if (t > timesArray[len - 1]) {
      if (t - timesArray[len - 1] <= LEGACY_TOLERANCE_S) {
        return frameDetections[len - 1];
      }
      return [];
    }

    const idx = binarySearchInterval(timesArray, t);
    if (idx === -1) return [];

    const t0 = timesArray[idx];
    const t1 = timesArray[idx + 1];

    if (t === t0) {
      return frameDetections[idx];
    }
    if (t === t1) {
      return frameDetections[idx + 1];
    }

    const gap = t1 - t0;
    // Beyond MAX_BRIDGE_S: fall back to old tolerance behaviour (0.05s)
    if (gap > MAX_BRIDGE_S) {
      if (t - t0 <= LEGACY_TOLERANCE_S) {
        return frameDetections[idx];
      }
      if (t1 - t <= LEGACY_TOLERANCE_S) {
        return frameDetections[idx + 1];
      }
      return [];
    }

    const bridge = intervalBridges[idx];
    const alpha = (t - t0) / gap;
    const results: DrawableDetection[] = [];

    // Matched pairs: linearly interpolate
    for (let m = 0; m < bridge.matched.length; m++) {
      const { a, b } = bridge.matched[m];
      const nearer = alpha <= 0.5 ? a : b;
      results.push({
        id: nearer.id,
        class: a.class,
        confidence: nearer.confidence,
        box: [
          a.box[0] + alpha * (b.box[0] - a.box[0]),
          a.box[1] + alpha * (b.box[1] - a.box[1]),
          a.box[2] + alpha * (b.box[2] - a.box[2]),
          a.box[3] + alpha * (b.box[3] - a.box[3]),
        ],
        speed_kmh: nearer.speed_kmh,
        direction: nearer.direction,
        interpolated: true,
      });
    }

    // Unmatched from sample i: visible within +/-0.15s (forward: t - t0 <= 0.15)
    if (t - t0 <= UNMATCHED_TOLERANCE_S) {
      for (let u = 0; u < bridge.unmatchedA.length; u++) {
        results.push(bridge.unmatchedA[u]);
      }
    }

    // Unmatched from sample i+1: visible within +/-0.15s (backward: t1 - t <= 0.15)
    if (t1 - t <= UNMATCHED_TOLERANCE_S) {
      for (let u = 0; u < bridge.unmatchedB.length; u++) {
        results.push(bridge.unmatchedB[u]);
      }
    }

    return results;
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
