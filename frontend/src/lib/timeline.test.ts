import { describe, it, expect } from "vitest";
import {
  binarySearchClosest,
  binarySearchInterval,
  parseTimeline,
  loadTimeline,
  LEGACY_SOURCE_SIZE,
  LEGACY_FPS,
} from "./timeline";

describe("Timeline Binary Search Utilities", () => {
  const times = new Float64Array([1.0, 2.0, 4.0, 7.0, 10.0]);

  it("handles exact hits in binarySearchClosest", () => {
    expect(binarySearchClosest(times, 1.0)).toBe(0);
    expect(binarySearchClosest(times, 4.0)).toBe(2);
    expect(binarySearchClosest(times, 10.0)).toBe(4);
  });

  it("handles queries before first and after last in binarySearchClosest", () => {
    // Before first
    expect(binarySearchClosest(times, 0.0)).toBe(0);
    expect(binarySearchClosest(times, -5.0)).toBe(0);

    // After last
    expect(binarySearchClosest(times, 15.0)).toBe(4);
    expect(binarySearchClosest(times, 100.0)).toBe(4);
  });

  it("picks the nearest element in binarySearchClosest", () => {
    // 2.3 is closer to 2.0 (diff 0.3) than to 4.0 (diff 1.7)
    expect(binarySearchClosest(times, 2.3)).toBe(1);
    // 3.8 is closer to 4.0 (diff 0.2) than to 2.0 (diff 1.8)
    expect(binarySearchClosest(times, 3.8)).toBe(2);
  });

  it("handles empty array in binarySearchClosest", () => {
    expect(binarySearchClosest(new Float64Array([]), 5.0)).toBe(-1);
  });

  it("finds valid interval in binarySearchInterval", () => {
    expect(binarySearchInterval(times, 1.0)).toBe(0);
    expect(binarySearchInterval(times, 1.5)).toBe(0);
    expect(binarySearchInterval(times, 2.0)).toBe(1);
    expect(binarySearchInterval(times, 3.5)).toBe(1);
    expect(binarySearchInterval(times, 5.0)).toBe(2);
    expect(binarySearchInterval(times, 10.0)).toBe(3); // Last interval index is len - 2
  });

  it("rejects out of bounds in binarySearchInterval", () => {
    expect(binarySearchInterval(times, 0.9)).toBe(-1);
    expect(binarySearchInterval(times, 10.1)).toBe(-1);
  });
});

describe("Schema v2 Track Keyframe Interpolation", () => {
  const sampleV2 = {
    schema: 2 as const,
    meta: {
      feed_id: "uav-alpha",
      width: 1920,
      height: 1080,
      fps: 60,
      duration_s: 10.0,
      speed_is_simulated: true,
    },
    tracks: [
      {
        id: "person-1",
        cls: "person",
        t: [1.0, 2.0, 3.0],
        box: [
          [100, 100, 200, 200] as [number, number, number, number],
          [200, 200, 400, 400] as [number, number, number, number],
          [300, 300, 500, 500] as [number, number, number, number],
        ],
        conf: [0.8, 0.9, 0.85],
        spd_kmh: [10, 20, 15],
        dir: ["N", "NE", "E"],
      },
    ],
  };

  const timeline = parseTimeline(sampleV2);

  it("returns exact keyframe detections without interpolation", () => {
    const dets = timeline.sampleAt(1.0);
    expect(dets).toHaveLength(1);
    expect(dets[0].id).toBe("person-1");
    expect(dets[0].box).toEqual([100, 100, 200, 200]);
    expect(dets[0].confidence).toBeCloseTo(0.8);
    expect(dets[0].speed_kmh).toBeCloseTo(10);
    expect(dets[0].direction).toBe("N");
    expect(dets[0].interpolated).toBe(false);
  });

  it("linearly interpolates boxes and metrics between keyframes", () => {
    // Exactly halfway between t=1.0 and t=2.0 (alpha = 0.5)
    const dets = timeline.sampleAt(1.5);
    expect(dets).toHaveLength(1);
    expect(dets[0].id).toBe("person-1");
    // [100 + 0.5*100, 100 + 0.5*100, 200 + 0.5*200, 200 + 0.5*200] = [150, 150, 300, 300]
    expect(dets[0].box).toEqual([150, 150, 300, 300]);
    expect(dets[0].confidence).toBeCloseTo(0.85);
    expect(dets[0].speed_kmh).toBeCloseTo(15);
    expect(dets[0].direction).toBe("N"); // alpha < 0.5 selects dir[0]
    expect(dets[0].interpolated).toBe(true);

    // Quarterway between t=1.0 and t=2.0 (alpha = 0.25)
    const detsQuarter = timeline.sampleAt(1.25);
    expect(detsQuarter[0].box).toEqual([125, 125, 250, 250]);
    expect(detsQuarter[0].confidence).toBeCloseTo(0.825);
  });

  it("never extrapolates before first keyframe or after last keyframe", () => {
    // Before t=1.0
    expect(timeline.sampleAt(0.5)).toEqual([]);
    expect(timeline.sampleAt(0.99)).toEqual([]);

    // After t=3.0
    expect(timeline.sampleAt(3.01)).toEqual([]);
    expect(timeline.sampleAt(5.0)).toEqual([]);
  });
});

describe("Schema v1 Legacy Adapter & Tolerance Window", () => {
  const legacyData = {
    "1.00": [
      {
        id: "Vehicle-1",
        class: "truck",
        confidence: 0.75,
        box: [500, 400, 700, 600] as [number, number, number, number],
        speed_kmh: 42,
        direction: "NW",
      },
    ],
    "2.00": [
      {
        id: "Vehicle-1",
        class: "truck",
        confidence: 0.80,
        box: [550, 420, 750, 620] as [number, number, number, number],
        speed_kmh: 44,
        direction: "NW",
      },
    ],
  };

  const timeline = parseTimeline(legacyData);

  it("synthesizes standard legacy metadata", () => {
    expect(timeline.schema).toBe(1);
    expect(timeline.meta.width).toBe(LEGACY_SOURCE_SIZE.width);
    expect(timeline.meta.height).toBe(LEGACY_SOURCE_SIZE.height);
    expect(timeline.meta.fps).toBe(LEGACY_FPS);
  });

  it("renders detections within tolerance window (<= 0.05s)", () => {
    // Exact match
    const exact = timeline.sampleAt(1.00);
    expect(exact).toHaveLength(1);
    expect(exact[0].id).toBe("Vehicle-1");

    // Inside tolerance: 1.03 (diff = 0.03 <= 0.05)
    const inside = timeline.sampleAt(1.03);
    expect(inside).toHaveLength(1);
    expect(inside[0].id).toBe("Vehicle-1");
  });

  it("suppresses stale detections outside tolerance window (> 0.05s)", () => {
    // Outside tolerance: 1.06 (diff = 0.06 > 0.05) -> must be empty (prevents stale boxes)
    const outside = timeline.sampleAt(1.06);
    expect(outside).toEqual([]);

    // Halfway at 1.50 -> must be empty
    expect(timeline.sampleAt(1.50)).toEqual([]);
  });
});

describe("Resolution-Decoupled Scaling", () => {
  const v2Data = {
    schema: 2 as const,
    meta: {
      feed_id: "uav-alpha",
      width: 1920,
      height: 1080,
      fps: 60,
      duration_s: 5.0,
      speed_is_simulated: true,
    },
    tracks: [],
  };

  const timeline = parseTimeline(v2Data);

  it("scales boxes from source 1920x1080 to transcoded 720p (1280x720)", () => {
    const sourceBox: [number, number, number, number] = [192, 108, 384, 216];
    const targetW = 1280;
    const targetH = 720;

    const scaled = timeline.scaleBox(sourceBox, targetW, targetH);

    // 192 * (1280 / 1920) = 192 * (2/3) = 128
    // 108 * (720 / 1080) = 108 * (2/3) = 72
    // 384 * (2/3) = 256
    // 216 * (2/3) = 144
    expect(scaled[0]).toBeCloseTo(128);
    expect(scaled[1]).toBeCloseTo(72);
    expect(scaled[2]).toBeCloseTo(256);
    expect(scaled[3]).toBeCloseTo(144);

    const scale = timeline.getScale(targetW, targetH);
    expect(scale.scaleX).toBeCloseTo(2 / 3);
    expect(scale.scaleY).toBeCloseTo(2 / 3);
  });

  it("proves normalized alignment holds invariant between 1080p source and 720p transcode", () => {
    // Arbitrary detection in 1080p source coordinates
    const sourceBox: [number, number, number, number] = [960, 540, 1440, 810];
    const normX1 = sourceBox[0] / 1920;
    const normY1 = sourceBox[1] / 1080;
    const normX2 = sourceBox[2] / 1920;
    const normY2 = sourceBox[3] / 1080;

    // Scale to 720p transcode (1280x720)
    const scaled720 = timeline.scaleBox(sourceBox, 1280, 720);
    expect(scaled720[0] / 1280).toBeCloseTo(normX1);
    expect(scaled720[1] / 720).toBeCloseTo(normY1);
    expect(scaled720[2] / 1280).toBeCloseTo(normX2);
    expect(scaled720[3] / 720).toBeCloseTo(normY2);

    // Scale to arbitrary display container (e.g. responsive viewport 800x450)
    const scaledViewport = timeline.scaleBox(sourceBox, 800, 450);
    expect(scaledViewport[0] / 800).toBeCloseTo(normX1);
    expect(scaledViewport[1] / 450).toBeCloseTo(normY1);
    expect(scaledViewport[2] / 800).toBeCloseTo(normX2);
    expect(scaledViewport[3] / 450).toBeCloseTo(normY2);
  });
});

describe("Empty Timeline Resilience", () => {
  it("handles completely empty v1 data", () => {
    const emptyV1 = parseTimeline({});
    expect(emptyV1.schema).toBe(1);
    expect(emptyV1.sampleAt(0)).toEqual([]);
    expect(emptyV1.sampleAt(10)).toEqual([]);
    expect(emptyV1.threatKeyframes.length).toBe(0);
  });

  it("handles empty v2 tracks", () => {
    const emptyV2 = parseTimeline({
      schema: 2,
      meta: { width: 1920, height: 1080 },
      tracks: [],
    });
    expect(emptyV2.schema).toBe(2);
    expect(emptyV2.sampleAt(0)).toEqual([]);
    expect(emptyV2.threatKeyframes.length).toBe(0);
  });

  it("handles null / invalid payload gracefully", () => {
    const invalid = parseTimeline(null);
    expect(invalid.schema).toBe(1);
    expect(invalid.sampleAt(0)).toEqual([]);
  });
});

describe("Unified Detection Generator Payload Loading", () => {
  const generatedPayload = {
    meta: {
      model: "yolov8m.pt",
      weights_sha256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      imgsz: 1280,
      conf: 0.25,
      date: "2026-10-16",
      evaluated: true,
      feed: "uav-alpha",
      width: 1920,
      height: 1080,
      fps: 59.94,
      duration_s: 33.6,
      sahi: false,
      tracker: "bytetrack.yaml",
    },
    "0.0": [
      {
        id: "Person-1",
        class: "person",
        confidence: 0.88,
        box: [1838.4, 334.1, 1868.3, 388.2] as [number, number, number, number],
        speed_kmh: 4.0,
        direction: "S",
      },
    ],
    "0.5": [
      {
        id: "Person-1",
        class: "person",
        confidence: 0.91,
        box: [1839.0, 335.0, 1869.0, 389.0] as [number, number, number, number],
        speed_kmh: 3.8,
        direction: "S",
      },
      {
        id: "Truck-12",
        class: "truck",
        confidence: 0.74,
        box: [820.0, 625.0, 1280.0, 903.0] as [number, number, number, number],
        speed_kmh: 18.5,
        direction: "SW",
      },
    ],
  };

  it("parses top-level meta and preserves provenance fields", () => {
    const timeline = parseTimeline(generatedPayload);
    expect(timeline.schema).toBe(1);
    expect(timeline.meta.model).toBe("yolov8m.pt");
    expect(timeline.meta.weights_sha256).toBe("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
    expect(timeline.meta.imgsz).toBe(1280);
    expect(timeline.meta.conf).toBe(0.25);
    expect(timeline.meta.date).toBe("2026-10-16");
    expect(timeline.meta.evaluated).toBe(true);
    expect(timeline.meta.width).toBe(1920);
    expect(timeline.meta.height).toBe(1080);
    expect(timeline.meta.fps).toBe(59.94);
    expect(timeline.meta.tracker).toBe("bytetrack.yaml");
  });

  it("samples detections accurately with ByteTrack IDs and kinematics", () => {
    const timeline = parseTimeline(generatedPayload);
    const dets = timeline.sampleAt(0.5);
    expect(dets).toHaveLength(2);
    expect(dets[0].id).toBe("Person-1");
    expect(dets[0].class).toBe("person");
    expect(dets[0].confidence).toBe(0.91);
    expect(dets[1].id).toBe("Truck-12");
    expect(dets[1].class).toBe("truck");
    expect(dets[1].speed_kmh).toBe(18.5);
    expect(dets[1].direction).toBe("SW");
  });

  it("loads timeline via loadTimeline fetcher", async () => {
    const mockFetch = (async () =>
      ({
        ok: true,
        status: 200,
        statusText: "OK",
        json: async () => generatedPayload,
      } as unknown as Response)) as unknown as typeof fetch;

    const timeline = await loadTimeline("/feeds/uav-alpha/detections.json", mockFetch);
    expect(timeline.meta.evaluated).toBe(true);
    expect(timeline.meta.model).toBe("yolov8m.pt");
    expect(timeline.sampleAt(0.0)).toHaveLength(1);
  });
});


