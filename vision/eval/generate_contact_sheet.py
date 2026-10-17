#!/usr/bin/env python3
"""
Aegis Command - Contact Sheet Generator for Secondary Feeds.

Extracts 12 evenly spaced frames across the feed video duration,
overlays bounding boxes and class labels from detections.json,
and arranges them into a 4x3 composite contact sheet grid for human inspection.
"""

import argparse
import json
import math
from pathlib import Path
from typing import Dict, List, Any, Tuple
import cv2
import numpy as np

CLASS_COLORS = {
    "person": (50, 220, 50),     # Bright green
    "car": (240, 160, 20),       # Cyan-amber
    "truck": (30, 140, 255),     # Vivid orange
    "bus": (230, 80, 20),        # Deep cyan-blue
    "motorcycle": (200, 30, 220) # Magenta
}
DEFAULT_COLOR = (200, 200, 200)


def find_closest_detections(detections_data: Dict[str, Any], target_sec: float, max_delta: float = 0.5) -> List[Dict[str, Any]]:
    best_match = []
    min_dist = float("inf")
    for k, v in detections_data.items():
        if k == "meta":
            continue
        try:
            ts = float(k)
            dist = abs(ts - target_sec)
            if dist < min_dist and dist <= max_delta:
                min_dist = dist
                best_match = v
        except ValueError:
            continue
    return best_match


def draw_detections_on_frame(frame: np.ndarray, detections: List[Dict[str, Any]], title: str) -> np.ndarray:
    annotated = frame.copy()
    h, w = annotated.shape[:2]

    # Draw header bar
    cv2.rectangle(annotated, (0, 0), (w, 40), (20, 20, 20), -1)
    cv2.putText(annotated, title, (15, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)

    for det in detections:
        box = det.get("box")
        if not box or len(box) != 4:
            continue
        x1, y1, x2, y2 = [int(round(c)) for c in box]
        x1 = max(0, min(w - 1, x1))
        y1 = max(0, min(h - 1, y1))
        x2 = max(0, min(w - 1, x2))
        y2 = max(0, min(h - 1, y2))

        cls_name = str(det.get("class", "object")).lower()
        conf = float(det.get("confidence", 0.0))
        color = CLASS_COLORS.get(cls_name, DEFAULT_COLOR)

        # Draw box
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

        # Draw label badge
        label = f"{cls_name} {conf:.2f}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        badge_y1 = max(42, y1 - th - 6)
        cv2.rectangle(annotated, (x1, badge_y1), (x1 + tw + 6, badge_y1 + th + 6), color, -1)
        cv2.putText(annotated, label, (x1 + 3, badge_y1 + th + 2), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)

    return annotated


def generate_contact_sheet(
    video_path: Path,
    detections_path: Path,
    out_path: Path,
    num_frames: int = 12,
    cols: int = 4
) -> Path:
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")
    if not detections_path.exists():
        raise FileNotFoundError(f"Detections JSON not found: {detections_path}")

    with open(detections_path, "r", encoding="utf-8") as f:
        detections_data = json.load(f)

    meta = detections_data.get("meta", {})
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_s = total_frames / fps

    rows = math.ceil(num_frames / cols)
    sample_timestamps = [(i + 0.5) * (duration_s / num_frames) for i in range(num_frames)]

    tiles = []
    # Target thumbnail size per cell
    target_w = 480
    target_h = 270

    for idx, ts in enumerate(sample_timestamps):
        frame_idx = min(total_frames - 1, int(round(ts * fps)))
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            # Create blank frame if read fails
            frame = np.zeros((720, 1280, 3), dtype=np.uint8)

        dets = find_closest_detections(detections_data, ts)
        title = f"Frame {frame_idx:04d} | t={ts:.2f}s | {len(dets)} objs"
        annotated = draw_detections_on_frame(frame, dets, title)
        thumb = cv2.resize(annotated, (target_w, target_h), interpolation=cv2.INTER_AREA)
        tiles.append(thumb)

    cap.release()

    # Fill remainder if tiles < cols * rows
    blank = np.zeros((target_h, target_w, 3), dtype=np.uint8)
    while len(tiles) < cols * rows:
        tiles.append(blank)

    # Stitch rows
    row_images = []
    for r in range(rows):
        row_tiles = tiles[r * cols:(r + 1) * cols]
        row_images.append(np.hstack(row_tiles))
    grid = np.vstack(row_images)

    # Add master banner on top
    banner_h = 60
    banner = np.zeros((banner_h, grid.shape[1], 3), dtype=np.uint8)
    feed_title = meta.get("feed", video_path.parent.name)
    model_name = meta.get("model", "unknown")
    header_text = f"AEGIS COMMAND - {feed_title.upper()} ZERO-SHOT CONTACT SHEET ({model_name} @ {meta.get('imgsz', 1280)}px)"
    sub_text = f"Frames: {total_frames} | Duration: {duration_s:.1f}s | Evaluated: {meta.get('evaluated', False)} | 12 Representative Samples"
    cv2.putText(banner, header_text, (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(banner, sub_text, (20, 52), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (180, 180, 180), 1, cv2.LINE_AA)

    final_sheet = np.vstack([banner, grid])

    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), final_sheet, [cv2.IMWRITE_JPEG_QUALITY, 90])
    print(f"✓ Contact sheet saved: {out_path} ({final_sheet.shape[1]}x{final_sheet.shape[0]})")
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Generate 12-frame contact sheets for video feeds.")
    parser.add_argument("--feed", default=None, help="Feed directory name under frontend/public/feeds/")
    parser.add_argument("--video", default=None, help="Path to video file")
    parser.add_argument("--detections", default=None, help="Path to detections.json")
    parser.add_argument("--out", default=None, help="Path to output contact sheet jpg")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent.parent

    if args.feed:
        feed_dir = project_root / "frontend" / "public" / "feeds" / args.feed
        video_p = feed_dir / "video.mp4"
        dets_p = feed_dir / "detections.json"
        out_p = Path(args.out) if args.out else (project_root / "docs" / "results" / "visual" / f"{args.feed}_contact_sheet.jpg")
    else:
        assert args.video and args.detections and args.out, "Must specify --feed or all of --video, --detections, --out"
        video_p = Path(args.video)
        dets_p = Path(args.detections)
        out_p = Path(args.out)

    generate_contact_sheet(video_p, dets_p, out_p)


if __name__ == "__main__":
    main()
