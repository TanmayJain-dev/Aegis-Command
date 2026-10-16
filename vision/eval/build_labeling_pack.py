#!/usr/bin/env python3
"""
Aegis Command - Secondary Feeds Labeling Pack Builder (Task 7).

Extracts 40 evenly spaced frames each from secondary surveillance feeds (cctv-bravo, bodycam-charlie),
initializes empty YOLO-format labels, writes classes definition, and generates a manifest
marking reviewed=false.

INVARIANT: No model prelabels are used as ground truth. All annotations start clean for human verification.
"""

import argparse
import json
from pathlib import Path
from typing import Dict, List

import cv2

CLASSES = ["person", "car", "truck", "motorcycle", "bus"]

FEEDS = {
    "cctv-bravo": {
        "video": "frontend/public/feeds/cctv-bravo/video.mp4",
        "output_dir": "vision/labeling_packs/cctv-bravo",
    },
    "bodycam-charlie": {
        "video": "frontend/public/feeds/bodycam-charlie/video.mp4",
        "output_dir": "vision/labeling_packs/bodycam-charlie",
    },
}


def build_pack_for_feed(feed_id: str, video_path: str, output_dir: str, num_frames: int = 40) -> Dict:
    v_path = Path(video_path)
    if not v_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    out_root = Path(output_dir)
    images_dir = out_root / "images"
    labels_dir = out_root / "labels"
    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(v_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration_s = total_frames / fps

    print(f"\n[BUILD PACK] Feed: {feed_id}")
    print(f"  Source Video: {video_path}")
    print(f"  Specs:        {width}x{height} @ {fps:.2f} fps ({total_frames} frames, {duration_s:.2f}s)")
    print(f"  Sampling:     {num_frames} evenly spaced frames -> {out_root}")

    # Determine 40 evenly spaced frame indices
    if total_frames <= num_frames:
        indices = list(range(total_frames))
    else:
        indices = [int(round(i * (total_frames - 1) / (num_frames - 1))) for i in range(num_frames)]

    manifest_frames: List[Dict] = []

    for i, frame_idx in enumerate(indices):
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            print(f"  Warning: failed to read frame at index {frame_idx}")
            continue

        timestamp_s = round(frame_idx / fps, 3)
        img_name = f"{feed_id}_frame_{i:02d}_{frame_idx:04d}.jpg"
        lbl_name = f"{feed_id}_frame_{i:02d}_{frame_idx:04d}.txt"

        img_path = images_dir / img_name
        lbl_path = labels_dir / lbl_name

        # Save frame image
        cv2.imwrite(str(img_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])

        # Touch empty label file (NO model prelabels per strict invariant)
        lbl_path.touch(exist_ok=True)

        manifest_frames.append({
            "pack_index": i,
            "video_frame_index": frame_idx,
            "timestamp_seconds": timestamp_s,
            "image_filename": img_name,
            "label_filename": lbl_name,
            "width": width,
            "height": height,
        })

    cap.release()

    # Write classes.txt
    classes_file = out_root / "classes.txt"
    classes_file.write_text("\n".join(CLASSES) + "\n", encoding="utf-8")

    # Write manifest.json
    manifest = {
        "feed": feed_id,
        "source_video": video_path,
        "total_frames_sampled": len(manifest_frames),
        "source_total_frames": total_frames,
        "source_fps": round(fps, 2),
        "source_duration_s": round(duration_s, 2),
        "reviewed": False,
        "annotator": None,
        "verification_date": None,
        "classes": CLASSES,
        "prelabels_used": False,
        "invariant": "Zero model pre-labels. Human ground-truth verification only.",
        "frames": manifest_frames,
    }

    manifest_path = out_root / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"  [COMPLETED] Extracted {len(manifest_frames)} frames and generated manifest at {manifest_path}")
    return manifest


def main():
    parser = argparse.ArgumentParser(description="Build secondary feed labeling packs for human review.")
    parser.add_argument("--feed", choices=["cctv-bravo", "bodycam-charlie", "all"], default="all")
    parser.add_argument("--num-frames", type=int, default=40)
    args = parser.parse_args()

    feeds_to_run = ["cctv-bravo", "bodycam-charlie"] if args.feed == "all" else [args.feed]

    for f_id in feeds_to_run:
        cfg = FEEDS[f_id]
        build_pack_for_feed(f_id, cfg["video"], cfg["output_dir"], num_frames=args.num_frames)


if __name__ == "__main__":
    main()
