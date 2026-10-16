#!/usr/bin/env python3
"""
Aegis Command - Unified Detection Generation Pipeline.

Generates precomputed detection timelines for surveillance feeds (uav-alpha, cctv-bravo, bodycam-charlie)
using Ultralytics YOLO with ByteTrack tracking and optional SAHI sliced inference.

Produces the standard timeline schema:
{
  "meta": {
    "model": "yolov8s.pt",
    "weights_sha256": "...",
    "imgsz": 1280,
    "conf": 0.35,
    "date": "2026-10-16",
    "evaluated": true,
    "feed": "uav-alpha",
    "sahi": false,
    "tracker": "bytetrack.yaml"
  },
  "0.0": [ { "id": "Person-1", "class": "person", "confidence": 0.85, "box": [x1, y1, x2, y2], "speed_kmh": 4.0, "direction": "S" } ],
  ...
}
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sys
from typing import Dict, List, Optional, Tuple

import cv2

# Standard product classes used in threat assessment and UI overlays
ALLOWED_CLASSES = {"person", "car", "truck", "motorcycle", "bus"}

FEED_PATHS = {
    "uav-alpha": {
        "video": "frontend/public/feeds/uav-alpha/video.mp4",
        "output": "frontend/public/feeds/uav-alpha/detections.json",
        "evaluated": True,
    },
    "cctv-bravo": {
        "video": "frontend/public/feeds/cctv-bravo/video.mp4",
        "output": "frontend/public/feeds/cctv-bravo/detections.json",
        "evaluated": False,
    },
    "bodycam-charlie": {
        "video": "frontend/public/feeds/bodycam-charlie/video.mp4",
        "output": "frontend/public/feeds/bodycam-charlie/detections.json",
        "evaluated": False,
    },
}


def compute_weights_sha256(weights_path: str) -> str:
    """Compute SHA-256 hash of model weights file if it exists."""
    p = Path(weights_path)
    if p.exists() and p.is_file():
        h = hashlib.sha256()
        with open(p, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()
    return "built-in-weights"


def compute_kinematics(
    prev_box: Optional[Tuple[float, float, float, float]],
    curr_box: Tuple[float, float, float, float],
    dt: float,
    cls_name: str,
) -> Tuple[float, str]:
    """Estimate speed in km/h and cardinal direction from bounding box centers."""
    if prev_box is None or dt <= 0:
        default_spd = 4.0 if cls_name == "person" else 20.0
        return (default_spd, "-")

    c1_x = (prev_box[0] + prev_box[2]) / 2.0
    c1_y = (prev_box[1] + prev_box[3]) / 2.0
    c2_x = (curr_box[0] + curr_box[2]) / 2.0
    c2_y = (curr_box[1] + curr_box[3]) / 2.0

    dx = c2_x - c1_x
    dy = c2_y - c1_y
    dist_px = math.hypot(dx, dy)

    # Approximate ground speed in km/h (~20 px/meter scale)
    speed_mps = (dist_px / 20.0) / dt
    speed_kmh = round(speed_mps * 3.6, 1)

    # Cardinal heading
    angle_deg = math.degrees(math.atan2(-dy, dx))  # Inverted Y for image plane
    compass_brackets = ["E", "NE", "N", "NW", "W", "SW", "S", "SE"]
    compass_idx = int((angle_deg + 22.5) % 360 // 45)
    direction = compass_brackets[compass_idx] if dist_px > 3.0 else "-"

    return (speed_kmh, direction)


def generate_feed_detections(
    feed_key: str,
    video_path: str,
    output_path: str,
    weights: str = "yolov8s.pt",
    imgsz: int = 1280,
    sahi: bool = False,
    conf: float = 0.35,
    sample_interval: float = 0.5,
    device: str = "cpu",
    evaluated: Optional[bool] = None,
    limit_frames: Optional[int] = None,
) -> Dict:
    """Run full video tracking and export structured detections JSON."""
    print("=" * 70)
    print(f"AEGIS DETECTION GENERATION: {feed_key}")
    print(f"Video:      {video_path}")
    print(f"Weights:    {weights} (imgsz={imgsz}, conf={conf}, sahi={sahi})")
    print(f"Output:     {output_path}")
    print("=" * 70)

    v_path = Path(video_path)
    if not v_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    # Determine evaluated flag
    if evaluated is None:
        evaluated = FEED_PATHS.get(feed_key, {}).get("evaluated", False)

    # Load model
    print(f"[MODEL] Loading YOLO from {weights} on {device}...")
    from ultralytics import YOLO
    model = YOLO(weights)
    weight_hash = compute_weights_sha256(weights)
    if weight_hash == "built-in-weights" and hasattr(model, "ckpt_path") and model.ckpt_path:
        weight_hash = compute_weights_sha256(model.ckpt_path)

    # Open video capture
    cap = cv2.VideoCapture(str(v_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration_s = total_frames / fps

    print(f"[VIDEO] Dimensions: {width}x{height}, FPS: {fps:.2f}, Frames: {total_frames}, Duration: {duration_s:.2f}s")

    # SAHI detection model if enabled
    sahi_model = None
    if sahi:
        try:
            from sahi import AutoDetectionModel
            from sahi.predict import get_sliced_prediction
            sahi_model = AutoDetectionModel.from_pretrained(
                model_type="yolov8",
                model_path=weights,
                confidence_threshold=conf,
                device=device,
            )
            print("[SAHI] Initialized Sliced Aided Hyper Inference engine.")
        except ImportError:
            print("[WARNING] sahi package not installed; falling back to standard YOLO tracking.")
            sahi = False

    # Timestamp sampling schedule
    sample_timestamps = [
        round(i * sample_interval, 2)
        for i in range(int(duration_s / sample_interval) + 1)
    ]
    if limit_frames:
        sample_timestamps = sample_timestamps[:limit_frames]

    timeline_data: Dict = {}
    prev_track_boxes: Dict[int, Tuple[float, float, float, float]] = {}
    prev_track_time: Dict[int, float] = {}

    for t in sample_timestamps:
        frame_idx = min(int(t * fps), total_frames - 1)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            break

        boxes_list: List[Dict] = []

        if sahi and sahi_model is not None:
            slice_res = get_sliced_prediction(
                frame,
                sahi_model,
                slice_height=640,
                slice_width=640,
                overlap_height_ratio=0.2,
                overlap_width_ratio=0.2,
                verbose=0,
            )
            for idx, pred in enumerate(slice_res.object_prediction_list):
                cls_name = pred.category.name
                box_conf = float(pred.score.value)
                if cls_name in ALLOWED_CLASSES and box_conf >= conf:
                    bbox = pred.bbox
                    x1, y1, x2, y2 = [
                        round(float(bbox.minx), 1),
                        round(float(bbox.miny), 1),
                        round(float(bbox.maxx), 1),
                        round(float(bbox.maxy), 1),
                    ]
                    track_id = idx + 1
                    target_id = f"{cls_name.capitalize()}-{track_id}"
                    boxes_list.append({
                        "id": target_id,
                        "class": cls_name,
                        "confidence": round(box_conf, 2),
                        "box": [x1, y1, x2, y2],
                        "speed_kmh": 4.0 if cls_name == "person" else 15.0,
                        "direction": "-",
                    })
        else:
            results = model.track(
                frame,
                persist=True,
                tracker="bytetrack.yaml",
                verbose=False,
                conf=conf,
                imgsz=imgsz,
                device=device,
            )
            for r in results:
                if r.boxes is None:
                    continue
                for b in r.boxes:
                    cls_id = int(b.cls[0])
                    cls_name = model.names[cls_id]
                    box_conf = float(b.conf[0])

                    if cls_name not in ALLOWED_CLASSES or box_conf < conf:
                        continue

                    x1, y1, x2, y2 = [round(float(v), 1) for v in b.xyxy[0].tolist()]
                    curr_box = (x1, y1, x2, y2)

                    raw_id = int(b.id[0]) if b.id is not None else (len(boxes_list) + 1)
                    target_id = f"{cls_name.capitalize()}-{raw_id}"

                    # Estimate speed and heading
                    prev_b = prev_track_boxes.get(raw_id)
                    prev_t = prev_track_time.get(raw_id, t)
                    dt = t - prev_t

                    speed_kmh, direction = compute_kinematics(prev_b, curr_box, dt, cls_name)
                    prev_track_boxes[raw_id] = curr_box
                    prev_track_time[raw_id] = t

                    boxes_list.append({
                        "id": target_id,
                        "class": cls_name,
                        "confidence": round(box_conf, 2),
                        "box": [x1, y1, x2, y2],
                        "speed_kmh": speed_kmh,
                        "direction": direction,
                    })

        timeline_data[str(t)] = boxes_list
        if len(sample_timestamps) <= 20 or int(t) % 5 == 0:
            print(f"  t={t:.2f}s: {len(boxes_list)} targets detected")

    cap.release()

    # Build metadata block
    meta = {
        "model": Path(weights).name,
        "weights_sha256": weight_hash,
        "imgsz": imgsz,
        "conf": conf,
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "evaluated": evaluated,
        "feed": feed_key,
        "width": width,
        "height": height,
        "fps": round(fps, 2),
        "duration_s": round(duration_s, 2),
        "sahi": sahi,
        "tracker": "bytetrack.yaml",
    }

    output_payload = {
        "meta": meta,
        **timeline_data,
    }

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, indent=2)

    print(f"\n[DONE] Saved {len(timeline_data)} timestamp frames with meta to {output_path}")
    return output_payload


def main():
    parser = argparse.ArgumentParser(description="Aegis Command - Unified Detection Generation Pipeline")
    parser.add_argument(
        "--feed",
        type=str,
        default="uav-alpha",
        choices=["uav-alpha", "cctv-bravo", "bodycam-charlie", "all"],
        help="Feed identifier to process (or 'all' for all three feeds)",
    )
    parser.add_argument("--video", type=str, default=None, help="Custom video path (overrides default)")
    parser.add_argument("--out", type=str, default=None, help="Custom output path (overrides default)")
    parser.add_argument("--weights", type=str, default="yolov8s.pt", help="YOLO model checkpoint or weights file")
    parser.add_argument("--imgsz", type=int, default=1280, help="Inference resolution (default: 1280)")
    parser.add_argument("--sahi", action="store_true", help="Enable SAHI sliced inference")
    parser.add_argument("--conf", type=float, default=0.35, help="Confidence threshold (default: 0.35)")
    parser.add_argument("--sample-interval", type=float, default=0.5, help="Sampling interval in seconds (default: 0.5)")
    default_dev = "cpu"
    try:
        import torch
        if torch.cuda.is_available():
            default_dev = "cuda:0"
    except ImportError:
        pass

    parser.add_argument(
        "--device",
        type=str,
        default=default_dev,
        help="Inference device (cuda:0 or cpu)",
    )
    parser.add_argument("--evaluated", type=str, default="auto", choices=["auto", "true", "false"])
    parser.add_argument("--limit-frames", type=int, default=None, help="Limit number of frames for smoke testing")

    args = parser.parse_args()

    feeds_to_run = ["uav-alpha", "cctv-bravo", "bodycam-charlie"] if args.feed == "all" else [args.feed]

    for f_key in feeds_to_run:
        feed_cfg = FEED_PATHS.get(f_key, {})
        video_path = args.video if args.feed != "all" else feed_cfg.get("video")
        output_path = args.out if args.feed != "all" else feed_cfg.get("output")
        if not video_path:
            video_path = feed_cfg.get("video")
        if not output_path:
            output_path = feed_cfg.get("output")

        if args.evaluated == "auto":
            is_evaluated = feed_cfg.get("evaluated", False)
        else:
            is_evaluated = args.evaluated.lower() == "true"

        generate_feed_detections(
            feed_key=f_key,
            video_path=video_path,
            output_path=output_path,
            weights=args.weights,
            imgsz=args.imgsz,
            sahi=args.sahi,
            conf=args.conf,
            sample_interval=args.sample_interval,
            device=args.device,
            evaluated=is_evaluated,
            limit_frames=args.limit_frames,
        )


if __name__ == "__main__":
    main()
