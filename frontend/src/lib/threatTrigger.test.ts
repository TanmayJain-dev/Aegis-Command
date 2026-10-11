import { describe, it, expect, beforeEach } from "vitest";
import {
  TriggerGate,
  projectGeoCoordinates,
  DEFAULT_GEO_PARAMS,
} from "./threatTrigger";
import { DrawableDetection } from "./timeline";

function createDetection(
  id: string,
  cls: string,
  conf: number,
  box: [number, number, number, number] = [100, 100, 200, 200]
): DrawableDetection {
  return {
    id,
    class: cls,
    confidence: conf,
    box,
    speed_kmh: 25,
    direction: "NW",
  };
}

describe("Threat Trigger Gate (TriggerGate)", () => {
  let gate: TriggerGate;

  beforeEach(() => {
    gate = new TriggerGate();
  });

  it("suppresses flickering tracks (< 0.5s visibility)", () => {
    const det = [createDetection("person-1", "person", 0.9)];

    // Frame 1 at t=0.0s
    expect(gate.evaluate(0.0, det, false)).toBeNull();

    // Frame 2 at t=0.25s (visible for 0.25s < 0.5s)
    expect(gate.evaluate(0.25, det, false)).toBeNull();

    // Track disappears at t=0.50s (no detections)
    expect(gate.evaluate(0.50, [], false)).toBeNull();
  });

  it("fires once for sustained qualifying track (>= 0.5s visibility)", () => {
    const det = [createDetection("truck-1", "truck", 0.85)];

    // t=0.0s
    expect(gate.evaluate(0.0, det, false)).toBeNull();
    // t=0.25s
    expect(gate.evaluate(0.25, det, false)).toBeNull();
    // t=0.50s: now visible for 0.50s, mean conf 0.85 >= 0.5
    const payload = gate.evaluate(0.50, det, false);
    expect(payload).not.toBeNull();
    expect(payload?.track_id).toBe("truck-1");
    expect(payload?.class).toBe("truck");
    expect(payload?.confidence).toBeCloseTo(0.85);

    // Subsequent tick at t=0.75s: track already fired, should NOT fire again immediately
    expect(gate.evaluate(0.75, det, false)).toBeNull();
  });

  it("enforces in-flight request suppression", () => {
    const det = [createDetection("person-2", "person", 0.8)];

    // Prime track history
    gate.evaluate(0.0, det, false);
    gate.evaluate(0.25, det, false);

    // At t=0.50s, track qualifies, but an inference request is in-flight!
    const suppressed = gate.evaluate(0.50, det, true);
    expect(suppressed).toBeNull();

    // At t=0.75s, in-flight request completes (inFlight = false) -> fires!
    const payload = gate.evaluate(0.75, det, false);
    expect(payload).not.toBeNull();
    expect(payload?.track_id).toBe("person-2");
  });

  it("enforces 5s global minimum interval across distinct tracks", () => {
    const det1 = [createDetection("car-1", "car", 0.8)];
    const det2 = [createDetection("truck-2", "truck", 0.9)];

    // Track 1 fires at t=0.50s
    gate.evaluate(0.0, det1, false);
    gate.evaluate(0.25, det1, false);
    const fire1 = gate.evaluate(0.50, det1, false);
    expect(fire1).not.toBeNull();
    expect(fire1?.track_id).toBe("car-1");

    // Track 2 starts at t=1.0s and qualifies at t=1.50s
    gate.evaluate(1.0, det2, false);
    gate.evaluate(1.25, det2, false);
    const fire2Early = gate.evaluate(1.50, det2, false);
    // Suppressed because 1.50 - 0.50 = 1.0s < 5.0s global interval
    expect(fire2Early).toBeNull();

    // At t=5.60s (5.60 - 0.50 = 5.1s >= 5.0s global interval)
    // Sustain Track 2 for >= 0.5s at 4 Hz ticks (5.10, 5.35, 5.60)
    gate.evaluate(5.10, det2, false);
    gate.evaluate(5.35, det2, false);
    const fire2 = gate.evaluate(5.60, det2, false);
    expect(fire2).not.toBeNull();
    expect(fire2?.track_id).toBe("truck-2");
  });

  it("enforces 20s per-track cooldown", () => {
    const det = [createDetection("car-1", "car", 0.85)];

    // car-1 fires at t=0.50s
    gate.evaluate(0.0, det, false);
    gate.evaluate(0.25, det, false);
    expect(gate.evaluate(0.50, det, false)).not.toBeNull();

    // At t=10.0s (9.5s after firing, global interval satisfied, but track cooldown 20s not met)
    expect(gate.evaluate(10.0, det, false)).toBeNull();

    // At t=19.0s (18.5s after firing)
    expect(gate.evaluate(19.0, det, false)).toBeNull();

    // Sustain car-1 for >= 0.5s leading up to t=21.0s (20.5s after firing >= 20.0s cooldown)
    gate.evaluate(20.50, det, false);
    gate.evaluate(20.75, det, false);
    // At t=21.0s -> fires again!
    expect(gate.evaluate(21.0, det, false)).not.toBeNull();
  });

  it("filters unapproved object classes", () => {
    const dog = [createDetection("animal-1", "dog", 0.99)];

    gate.evaluate(0.0, dog, false);
    gate.evaluate(0.25, dog, false);
    gate.evaluate(0.50, dog, false);
    gate.evaluate(1.00, dog, false);

    expect(gate.evaluate(2.00, dog, false)).toBeNull();
  });

  it("filters low-confidence detections (< 0.5 mean)", () => {
    const lowConf = [createDetection("person-low", "person", 0.40)];

    gate.evaluate(0.0, lowConf, false);
    gate.evaluate(0.25, lowConf, false);
    gate.evaluate(0.50, lowConf, false);

    expect(gate.evaluate(0.75, lowConf, false)).toBeNull();
  });

  it("resets continuity when track vanishes for > 0.35s", () => {
    const det = [createDetection("person-gap", "person", 0.85)];

    gate.evaluate(0.0, det, false);
    gate.evaluate(0.25, det, false);

    // Track disappears for 0.50s (gap > 0.35s)
    gate.evaluate(0.50, [], false);
    gate.evaluate(0.75, [], false);

    // Track reappears at t=1.00s: should NOT immediately fire!
    expect(gate.evaluate(1.00, det, false)).toBeNull();

    // Must sustain for >= 0.5s from 1.00s -> fires at 1.50s
    gate.evaluate(1.25, det, false);
    const fire = gate.evaluate(1.50, det, false);
    expect(fire).not.toBeNull();
    expect(fire?.track_id).toBe("person-gap");
  });
});

describe("Deterministic Geo-Projection", () => {
  it("projects bounding box coordinates deterministically", () => {
    const box1: [number, number, number, number] = [960, 540, 960, 540]; // Dead center
    const proj1 = projectGeoCoordinates(box1, DEFAULT_GEO_PARAMS);

    // Center of 1920x1080 is (0.5, 0.5)
    // lat = 31.4520 + (0.5 - 0.5) * latSpan = 31.4520
    // lng = 74.9250 + (0.5 - 0.5) * lngSpan = 74.9250
    expect(proj1.latitude).toBeCloseTo(31.4520, 4);
    expect(proj1.longitude).toBeCloseTo(74.9250, 4);
    expect(proj1.video_x).toBeCloseTo(0.5, 3);
    expect(proj1.video_y).toBeCloseTo(0.5, 3);

    // Repeating projection returns identical result
    const projRepeat = projectGeoCoordinates(box1, DEFAULT_GEO_PARAMS);
    expect(projRepeat).toEqual(proj1);
  });

  it("clamps coordinates within designated tactical bounding box", () => {
    const extremeBox: [number, number, number, number] = [5000, 5000, 6000, 6000];
    const proj = projectGeoCoordinates(extremeBox, DEFAULT_GEO_PARAMS);

    const maxLat = DEFAULT_GEO_PARAMS.centerLat + (DEFAULT_GEO_PARAMS.latSpan ?? 0.035) / 2;
    const minLat = DEFAULT_GEO_PARAMS.centerLat - (DEFAULT_GEO_PARAMS.latSpan ?? 0.035) / 2;
    const maxLng = DEFAULT_GEO_PARAMS.centerLng + (DEFAULT_GEO_PARAMS.lngSpan ?? 0.045) / 2;
    const minLng = DEFAULT_GEO_PARAMS.centerLng - (DEFAULT_GEO_PARAMS.lngSpan ?? 0.045) / 2;

    expect(proj.latitude).toBeGreaterThanOrEqual(minLat - 1e-5);
    expect(proj.latitude).toBeLessThanOrEqual(maxLat + 1e-5);
    expect(proj.longitude).toBeGreaterThanOrEqual(minLng - 1e-5);
    expect(proj.longitude).toBeLessThanOrEqual(maxLng + 1e-5);
  });
});
