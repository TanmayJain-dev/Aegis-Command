#!/usr/bin/env python3
"""
Sample evaluation frames from drone_feed.mp4.
Extracts every 13th frame starting at frame 6 (~155 frames).
Saves images to vision/eval/images/ and writes manifest.json.
"""

import os
import sys
import json
import datetime
from pathlib import Path
import cv2

def sample_frames(video_path="vision/source/drone_feed.mp4", out_dir="vision/eval/images", manifest_path="vision/eval/manifest.json", stride=13, offset=6):
    video_file = Path(video_path)
    if not video_file.exists():
        legacy_file = Path("vision/drone_feed.mp4")
        if legacy_file.exists():
            video_file = legacy_file
        else:
            print(f"Error: video not found at {video_file}", file=sys.stderr)
            sys.exit(1)

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video_file))
    if not cap.isOpened():
        print(f"Error: failed to open video {video_file}", file=sys.stderr)
        sys.exit(1)

    total_video_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 59.94
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    print(f"Video: {video_path} ({width}x{height}, {fps:.2f} fps, {total_video_frames} frames)")
    print(f"Sampling with stride={stride}, offset={offset} into {out_dir}...")

    frames_meta = []
    frame_idx = 0
    sampled_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx >= offset and (frame_idx - offset) % stride == 0:
            filename = f"frame_{frame_idx:06d}.png"
            img_path = out_path / filename
            cv2.imwrite(str(img_path), frame)

            time_s = round(frame_idx / fps, 4)
            frames_meta.append({
                "index": frame_idx,
                "time_s": time_s,
                "filename": filename,
                "width": width,
                "height": height
            })
            sampled_count += 1

        frame_idx += 1

    cap.release()

    manifest = {
        "video": str(video_path),
        "sampled_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "total_video_frames": total_video_frames,
        "sampled_count": sampled_count,
        "stride": stride,
        "offset": offset,
        "frames": frames_meta
    }

    manifest_file = Path(manifest_path)
    manifest_file.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Sampled {sampled_count} frames. Manifest saved to {manifest_file}.")
    return manifest

if __name__ == "__main__":
    sample_frames()
