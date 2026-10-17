import { describe, it, expect, vi } from "vitest";
import { loadFeedsManifest, loadFeedTimeline, DEFAULT_FALLBACK_FEED } from "./feeds";

describe("Feeds Manifest Loader", () => {
  it("loads valid feed entries from manifest", async () => {
    const mockFeeds = [
      {
        id: "uav-alpha",
        label: "UAV Alpha",
        video: "/feeds/uav-alpha/video.mp4",
        detections: "/feeds/uav-alpha/detections.json",
        center_lat: 31.4520,
        center_lng: 74.9250,
        sensor: "EO/IR",
      },
      {
        id: "cctv-04",
        label: "Perimeter CCTV",
        video: "/feeds/cctv-04/video.mp4",
        detections: "/feeds/cctv-04/detections.json",
        center_lat: 31.4580,
        center_lng: 74.9210,
        sensor: "Fixed Optical",
      },
    ];

    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockFeeds,
    });

    const feeds = await loadFeedsManifest("/feeds/index.json", mockFetch as unknown as typeof fetch);
    expect(feeds).toHaveLength(2);
    expect(feeds[0].id).toBe("uav-alpha");
    expect(feeds[1].id).toBe("cctv-04");
  });

  it("falls back to default feed when fetch fails or errors", async () => {
    const failingFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
    });

    const feeds = await loadFeedsManifest("/missing.json", failingFetch as unknown as typeof fetch);
    expect(feeds).toEqual([DEFAULT_FALLBACK_FEED]);

    const errorFetch = vi.fn().mockRejectedValue(new Error("Network Error"));
    const errorFeeds = await loadFeedsManifest("/error.json", errorFetch as unknown as typeof fetch);
    expect(errorFeeds).toEqual([DEFAULT_FALLBACK_FEED]);
  });

  it("loads timeline from inline detections object directly", async () => {
    const inlineData = {
      "0.5": [
        {
          id: "Truck-1",
          class: "truck",
          confidence: 0.95,
          box: [100, 200, 300, 400],
          speed_kmh: 40,
          direction: "NE",
        },
      ],
    };

    const tl = await loadFeedTimeline(inlineData);
    expect(tl).not.toBeNull();
    expect(tl?.sampleAt(0.5)).toHaveLength(1);
    expect(tl?.sampleAt(0.5)[0].class).toBe("truck");
  });
});
