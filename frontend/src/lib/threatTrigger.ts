/**
 * Aegis Command - Threat Trigger & Classification Gate.
 * 
 * Pure, deterministic evaluation gate for autonomous threat signaling:
 * - Gated at max 4 Hz
 * - Qualifies when continuously visible >= 0.5s and mean confidence (last 5 obs) >= 0.5
 * - Class filter: person, car, truck, bus
 * - Fires once per qualifying track with 20s per-track cooldown
 * - Enforces 5s global minimum interval
 * - Suppressed when an inference request is in flight
 * - Deterministic geo-projection into tactical boundary
 */

import { DrawableDetection } from "./timeline";

export const ALLOWED_THREAT_CLASSES = new Set(["person", "car", "truck", "motorcycle", "bus"]);
export const VEHICLE_CLASSES = new Set(["car", "truck", "motorcycle", "bus"]);

export function isVehicleClass(cls: string): boolean {
  return VEHICLE_CLASSES.has((cls || "").toLowerCase());
}

export const PER_TRACK_COOLDOWN_S = 20.0;
export const GLOBAL_MIN_INTERVAL_S = 5.0;
export const MIN_VISIBILITY_DURATION_S = 0.5;
export const MAX_OBSERVATION_GAP_S = 0.35;
export const MIN_MEAN_CONFIDENCE = 0.5;
export const MAX_EVAL_FREQ_HZ = 4;
export const MIN_EVAL_INTERVAL_S = 1.0 / MAX_EVAL_FREQ_HZ; // 0.25s

export interface GeoProjectionParams {
  centerLat: number;
  centerLng: number;
  latSpan?: number;
  lngSpan?: number;
  sourceWidth?: number;
  sourceHeight?: number;
}

export const DEFAULT_GEO_PARAMS: GeoProjectionParams = {
  centerLat: 31.4520,
  centerLng: 74.9250,
  latSpan: 0.035,
  lngSpan: 0.045,
  sourceWidth: 1920,
  sourceHeight: 1080,
};

export interface ProjectedCoordinates {
  latitude: number;
  longitude: number;
  video_x: number;
  video_y: number;
}

/**
 * Projects 2D optical bounding box center into bounded geographic coordinates.
 * Deterministic: identical bounding boxes produce identical GPS coordinates.
 */
export function projectGeoCoordinates(
  box: [number, number, number, number],
  params: GeoProjectionParams = DEFAULT_GEO_PARAMS
): ProjectedCoordinates {
  const [x1, y1, x2, y2] = box;
  const width = params.sourceWidth ?? 1920;
  const height = params.sourceHeight ?? 1080;

  const centerX = (x1 + x2) / 2 / width;
  const centerY = (y1 + y2) / 2 / height;

  const latSpan = params.latSpan ?? 0.035;
  const lngSpan = params.lngSpan ?? 0.045;

  const latitude = params.centerLat + (0.5 - centerY) * latSpan;
  const longitude = params.centerLng + (centerX - 0.5) * lngSpan;

  const clampedLat = Math.max(
    params.centerLat - latSpan / 2,
    Math.min(params.centerLat + latSpan / 2, latitude)
  );

  const clampedLng = Math.max(
    params.centerLng - lngSpan / 2,
    Math.min(params.centerLng + lngSpan / 2, longitude)
  );

  return {
    latitude: Number(clampedLat.toFixed(6)),
    longitude: Number(clampedLng.toFixed(6)),
    video_x: Number(centerX.toFixed(4)),
    video_y: Number(centerY.toFixed(4)),
  };
}

export interface ThreatPayload {
  track_id: string;
  class: string;
  confidence: number;
  speed_kmh: number;
  direction: string;
  latitude: number;
  longitude: number;
  video_x: number;
  video_y: number;
  detection_time: number;
  timestamp: string;
  box: [number, number, number, number];
}

interface TrackHistory {
  firstSeenTime: number;
  lastSeenTime: number;
  confidences: number[];
  lastFiredTime?: number;
}

export class TriggerGate {
  private tracks = new Map<string, TrackHistory>();
  private lastEvalTime = -Infinity;
  private lastGlobalFireTime = -Infinity;
  private geoParams: GeoProjectionParams;

  constructor(geoParams: GeoProjectionParams = DEFAULT_GEO_PARAMS) {
    this.geoParams = geoParams;
  }

  /**
   * Resets internal tracking state and cooldown timers (e.g. upon camera feed switch).
   */
  public reset(): void {
    this.tracks.clear();
    this.lastEvalTime = -Infinity;
    this.lastGlobalFireTime = -Infinity;
  }

  public setGeoParams(params: GeoProjectionParams): void {
    this.geoParams = params;
  }

  /**
   * Evaluates detections at the given media timestamp.
   * Returns a ThreatPayload if a qualifying track triggers, or null otherwise.
   * 
   * @param currentTime Current playback/feed time in seconds
   * @param detections Detections active at currentTime
   * @param inFlight Whether a threat inference request is already in flight
   */
  public evaluate(
    currentTime: number,
    detections: DrawableDetection[],
    inFlight: boolean
  ): ThreatPayload | null {
    // Throttle evaluation to at most 4 Hz (0.25s, allowing small float epsilon)
    if (this.lastEvalTime >= 0 && currentTime - this.lastEvalTime < MIN_EVAL_INTERVAL_S - 1e-4) {
      return null;
    }
    this.lastEvalTime = currentTime;

    // Update track histories
    const currentTrackIds = new Set<string>();

    for (let i = 0; i < detections.length; i++) {
      const det = detections[i];
      if (!ALLOWED_THREAT_CLASSES.has(det.class.toLowerCase())) {
        continue;
      }

      const id = det.id;
      currentTrackIds.add(id);

      let history = this.tracks.get(id);
      if (!history) {
        history = {
          firstSeenTime: currentTime,
          lastSeenTime: currentTime,
          confidences: [det.confidence],
        };
        this.tracks.set(id, history);
      } else {
        // If track vanished for longer than gap tolerance, reset continuity window
        if (currentTime - history.lastSeenTime > MAX_OBSERVATION_GAP_S) {
          history.firstSeenTime = currentTime;
          history.confidences = [det.confidence];
        } else {
          history.confidences.push(det.confidence);
          if (history.confidences.length > 5) {
            history.confidences.shift();
          }
        }
        history.lastSeenTime = currentTime;
      }
    }

    // If an inference request is currently in flight, suppress firing
    if (inFlight) {
      return null;
    }

    // Check global cooldown
    if (currentTime - this.lastGlobalFireTime < GLOBAL_MIN_INTERVAL_S) {
      return null;
    }

    // Find candidate track that qualifies
    for (let i = 0; i < detections.length; i++) {
      const det = detections[i];
      if (!ALLOWED_THREAT_CLASSES.has(det.class.toLowerCase())) {
        continue;
      }

      const history = this.tracks.get(det.id);
      if (!history) continue;

      // 1. Must be continuously visible for at least 0.5s
      const visibilityDuration = currentTime - history.firstSeenTime;
      if (visibilityDuration < MIN_VISIBILITY_DURATION_S) {
        continue;
      }

      // 2. Mean confidence of last 5 observations must be >= 0.5
      const sumConf = history.confidences.reduce((a, b) => a + b, 0);
      const meanConf = sumConf / history.confidences.length;
      if (meanConf < MIN_MEAN_CONFIDENCE) {
        continue;
      }

      // 3. Per-track cooldown check (20s)
      if (
        history.lastFiredTime !== undefined &&
        currentTime - history.lastFiredTime < PER_TRACK_COOLDOWN_S
      ) {
        continue;
      }

      // Qualifies! Fire threat payload
      history.lastFiredTime = currentTime;
      this.lastGlobalFireTime = currentTime;

      const coords = projectGeoCoordinates(det.box, this.geoParams);

      return {
        track_id: det.id,
        class: det.class,
        confidence: Number(meanConf.toFixed(4)),
        speed_kmh: det.speed_kmh ?? 0,
        direction: det.direction ?? "unknown",
        latitude: coords.latitude,
        longitude: coords.longitude,
        video_x: coords.video_x,
        video_y: coords.video_y,
        detection_time: Number(currentTime.toFixed(3)),
        timestamp: new Date().toISOString(),
        box: det.box,
      };
    }

    return null;
  }
}
