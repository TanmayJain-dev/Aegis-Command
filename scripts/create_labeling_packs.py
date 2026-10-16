#!/usr/bin/env python3
"""
Aegis Command - Secondary Feed Labeling Pack Generator (Task G).

Generates a ready-to-label 30-frame sample per secondary feed:
- cctv-bravo
- bodycam-charlie

Extracts 30 uniformly spaced frames from each feed's video and pairs them
with zero-shot pre-annotations from detections.json in both YOLO format
and X-AnyLabeling JSON format for human verification.
NOTE: Does NOT compute or report accuracy metrics against draft pre-labels.
"""

import os
import sys
import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FEEDS_DIR = REPO_ROOT / "frontend" / "public" / "feeds"
OUTPUT_ROOT = REPO_ROOT / "vision" / "labeling_packs"

CLASS_TO_ID = {
    "person": 0,
    "car": 1,
    "truck": 2,
    "bus": 3,
}

CLASSES_TXT = "person\ncar\ntruck\nbus\n"


def extract_frame_ffmpeg(video_path: Path, timestamp_s: float, out_path: Path) -> bool:
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{timestamp_s:.3f}",
        "-i", str(video_path),
        "-vframes", "1",
        "-q:v", "2",
        str(out_path)
    ]
    res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return res.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0


def create_xanylabeling_json(image_name: str, width: int, height: int, detections: list) -> dict:
    shapes = []
    for d in detections:
        cls_name = d.get("class", "").lower()
        if cls_name not in CLASS_TO_ID:
            continue
        box = d.get("box", [])
        if len(box) != 4:
            continue
        x1, y1, x2, y2 = box
        shapes.append({
            "label": cls_name,
            "score": d.get("confidence", None),
            "points": [
                [float(x1), float(y1)],
                [float(x2), float(y1)],
                [float(x2), float(y2)],
                [float(x1), float(y2)],
            ],
            "group_id": None,
            "description": None,
            "difficult": False,
            "shape_type": "rectangle",
            "flags": {},
            "attributes": {},
            "kie_linking": [],
        })

    return {
        "version": "4.1.0",
        "flags": {},
        "checked": False,
        "shapes": shapes,
        "imagePath": image_name,
        "imageHeight": height,
        "imageWidth": width,
    }


def create_yolo_txt(width: int, height: int, detections: list) -> str:
    lines = []
    for d in detections:
        cls_name = d.get("class", "").lower()
        if cls_name not in CLASS_TO_ID:
            continue
        box = d.get("box", [])
        if len(box) != 4:
            continue
        x1, y1, x2, y2 = box
        cls_id = CLASS_TO_ID[cls_name]
        cx = ((x1 + x2) / 2.0) / width
        cy = ((y1 + y2) / 2.0) / height
        w = (x2 - x1) / width
        h = (y2 - y1) / height
        # Clamp to [0, 1]
        cx = max(0.0, min(1.0, cx))
        cy = max(0.0, min(1.0, cy))
        w = max(0.0, min(1.0, w))
        h = max(0.0, min(1.0, h))
        lines.append(f"{cls_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")
    return "\n".join(lines) + ("\n" if lines else "")


def process_feed(feed_name: str, num_samples: int = 30):
    feed_dir = FEEDS_DIR / feed_name
    video_path = feed_dir / "video.mp4"
    detections_path = feed_dir / "detections.json"

    if not video_path.exists():
        print(f"Error: {video_path} not found")
        return
    if not detections_path.exists():
        print(f"Error: {detections_path} not found")
        return

    with open(detections_path, "r", encoding="utf-8") as f:
        det_data = json.load(f)

    meta = det_data.get("meta", {})
    width = int(meta.get("width", 1280))
    height = int(meta.get("height", 720))
    duration_s = float(meta.get("duration_s", 25.0))

    out_feed_dir = OUTPUT_ROOT / feed_name / "zero_shot_sample"
    images_dir = out_feed_dir / "images"
    labels_dir = out_feed_dir / "labels"
    annotations_dir = out_feed_dir / "annotations"

    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)
    annotations_dir.mkdir(parents=True, exist_ok=True)

    # Write classes.txt
    (out_feed_dir / "classes.txt").write_text(CLASSES_TXT, encoding="utf-8")
    (annotations_dir / "classes.txt").write_text(CLASSES_TXT, encoding="utf-8")

    # Available detection timestamps
    time_keys = []
    for k in det_data.keys():
        if k == "meta":
            continue
        try:
            time_keys.append((float(k), k))
        except ValueError:
            pass
    time_keys.sort()

    # Generate 30 sample timestamps
    # Sample uniformly with small margin at start and end
    margin = duration_s * 0.05
    effective_duration = duration_s - 2 * margin
    step = effective_duration / max(1, num_samples - 1)

    print(f"\nProcessing feed '{feed_name}': {duration_s:.2f}s, {width}x{height}, extracting {num_samples} frames...")

    manifest = {
        "feed": feed_name,
        "sample_count": num_samples,
        "video_duration_s": duration_s,
        "resolution": [width, height],
        "zero_shot_model": meta.get("model", "yolov8m.pt"),
        "zero_shot_weights_sha256": meta.get("weights_sha256", ""),
        "samples": []
    }

    for i in range(num_samples):
        target_t = margin + i * step
        frame_name = f"frame_{i+1:04d}"
        img_filename = f"{frame_name}.jpg"
        img_out = images_dir / img_filename

        # Extract frame
        ok = extract_frame_ffmpeg(video_path, target_t, img_out)
        if not ok:
            print(f"  Warning: failed to extract frame at {target_t:.2f}s")
            continue

        # Find closest detection timestamp
        closest_k = None
        min_diff = float("inf")
        for t_val, k_str in time_keys:
            diff = abs(t_val - target_t)
            if diff < min_diff:
                min_diff = diff
                closest_k = k_str

        detections = det_data.get(closest_k, []) if closest_k else []

        # Write YOLO label
        lbl_content = create_yolo_txt(width, height, detections)
        (labels_dir / f"{frame_name}.txt").write_text(lbl_content, encoding="utf-8")

        # Write X-AnyLabeling JSON
        anno_data = create_xanylabeling_json(img_filename, width, height, detections)
        (annotations_dir / f"{frame_name}.json").write_text(json.dumps(anno_data, indent=2), encoding="utf-8")
        # Also copy image to annotations dir for X-AnyLabeling convenience
        safe_img_anno = annotations_dir / img_filename
        if not safe_img_anno.exists():
            os.symlink(img_out.resolve(), safe_img_anno)

        manifest["samples"].append({
            "index": i + 1,
            "frame": frame_name,
            "timestamp_s": round(target_t, 3),
            "matched_detection_timestamp_s": round(float(closest_k), 3) if closest_k else None,
            "num_pre_annotations": len([d for d in detections if d.get("class", "").lower() in CLASS_TO_ID]),
        })

    with open(out_feed_dir / "sample_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    readme_content = f"""# Aegis Command - Labeling Pack: {feed_name}

## Overview
This labeling pack contains a **30-frame representative sample** extracted from `{feed_name}` (`video.mp4`, duration {duration_s:.2f}s).
Frames are paired with **zero-shot pre-annotations** generated by the baseline detector (`{meta.get('model', 'yolov8m.pt')}`).

> [!WARNING]
> **PRE-ANNOTATION / DRAFT ONLY**:
> These bounding boxes are draft suggestions generated by an uncalibrated zero-shot detector.
> **DO NOT report, benchmark, or claim detection accuracy on this feed** until these frames are human-verified, corrected, and certified following `docs/LABELING.md`.

## Directory Structure
- `images/`: 30 high-resolution extracted frames (`frame_0001.jpg` .. `frame_0030.jpg`).
- `labels/`: Standard YOLO format bounding box text files (`frame_0001.txt` .. `frame_0030.txt`).
- `annotations/`: X-AnyLabeling JSON format files ready to open in X-AnyLabeling (`Ctrl+U` -> open `annotations/`).
- `classes.txt`: Target class taxonomy (`person`, `car`, `truck`, `bus`).
- `sample_manifest.json`: Frame timestamps and pre-annotation counts.

## Annotation Instructions
1. Launch annotation tool: `local_assets/labeling_env/bin/xanylabeling`
2. Open directory: `vision/labeling_packs/{feed_name}/annotations/`
3. Inspect and correct bounding boxes:
   - Fix false positives (delete stray boxes).
   - Add false negatives (draw missing target objects).
   - Adjust loose or misaligned boundaries.
4. When all 30 frames are approved, export finalized labels to `vision/eval/{feed_name}/labels/` with a signed `VERIFIED` marker.
"""
    (out_feed_dir / "README.md").write_text(readme_content, encoding="utf-8")
    print(f"  [OK] Successfully created labeling pack for '{feed_name}' with {len(manifest['samples'])} frames at {out_feed_dir}")


def main():
    print("=== AEGIS COMMAND - GENERATING SECONDARY FEED LABELING PACKS (Task G) ===")
    process_feed("cctv-bravo", num_samples=30)
    process_feed("bodycam-charlie", num_samples=30)
    print("\n[OK] Task G complete.")


if __name__ == "__main__":
    main()
