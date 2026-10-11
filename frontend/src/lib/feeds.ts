/**
 * Aegis Command - Multi-Feed Ingestion & Manifest Manager.
 * Loads and validates surveillance feed registrations from /feeds/index.json.
 */

import { Timeline, parseTimeline } from "./timeline";

export interface FeedManifestItem {
  id: string;
  label: string;
  video: string;
  detections: string;
  center_lat: number;
  center_lng: number;
  sensor: string;
}

export type FeedItem = FeedManifestItem;

export const DEFAULT_FALLBACK_FEED: FeedManifestItem = {
  id: "uav-alpha",
  label: "UAV Alpha (FLIR 4K)",
  video: "/feeds/uav-alpha/video.mp4",
  detections: "/feeds/uav-alpha/detections.json",
  center_lat: 31.4520,
  center_lng: 74.9250,
  sensor: "EO/IR Optronics",
};

export async function loadFeedsManifest(
  url = "/feeds/index.json",
  fetchFn: typeof fetch = fetch
): Promise<FeedManifestItem[]> {
  try {
    const res = await fetchFn(url);
    if (!res.ok) return [DEFAULT_FALLBACK_FEED];
    const data = await res.json();
    if (Array.isArray(data) && data.length > 0) {
      return data;
    }
    return [DEFAULT_FALLBACK_FEED];
  } catch {
    return [DEFAULT_FALLBACK_FEED];
  }
}

export const loadFeedManifest = loadFeedsManifest;

export async function loadFeedTimeline(
  detectionsUrl: string,
  fetchFn: typeof fetch = fetch
): Promise<Timeline | null> {
  try {
    const res = await fetchFn(detectionsUrl);
    if (!res.ok) return null;
    const data = await res.json();
    return parseTimeline(data);
  } catch {
    return null;
  }
}
