#!/usr/bin/env python3
"""
Generate a 12-frame contact sheet grid visualizing evaluation labels.

Draws bounding boxes, class labels, and summary telemetry onto selected
keyframes and compiles them into a grid saved at local_assets/label_preview.jpg.
"""

import sys
import argparse
from pathlib import Path
from typing import List, Tuple
import cv2
import numpy as np

CLASS_NAMES = ["person", "car", "truck", "bus"]
# BGR colors for OpenCV rendering
CLASS_COLORS = {
    0: (255, 255, 0),    # person: Cyan
    1: (0, 255, 0),      # car: Lime Green
    2: (0, 165, 255),    # truck: Orange
    3: (255, 0, 180),    # bus: Magenta
}


def load_yolo_labels(label_file: Path) -> List[Tuple[int, float, float, float, float]]:
    """Parse YOLO format annotations: class_id, x_center, y_center, width, height."""
    boxes = []
    if not label_file.exists():
        return boxes
    with open(label_file, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) == 5:
                try:
                    cid = int(parts[0])
                    xc, yc, w, h = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
                    boxes.append((cid, xc, yc, w, h))
                except ValueError:
                    continue
    return boxes


def draw_boxes_on_image(
    img: np.ndarray,
    boxes: List[Tuple[int, float, float, float, float]],
    frame_title: str = ""
) -> np.ndarray:
    """Draw bounding boxes with badge tags and telemetry on frame."""
    canvas = img.copy()
    h, w = canvas.shape[:2]

    # Draw header badge for frame name
    if frame_title:
        cv2.rectangle(canvas, (10, 10), (330, 48), (20, 20, 20), -1)
        cv2.rectangle(canvas, (10, 10), (330, 48), (60, 60, 60), 1)
        cv2.putText(
            canvas,
            f"{frame_title} | obj:{len(boxes)}",
            (18, 36),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
            cv2.LINE_AA
        )

    for cid, xc, yc, bw, bh in boxes:
        color = CLASS_COLORS.get(cid, (200, 200, 200))
        cname = CLASS_NAMES[cid] if 0 <= cid < len(CLASS_NAMES) else str(cid)

        # Convert normalized center-based coordinates to pixel bounds
        x1 = int(round((xc - bw / 2.0) * w))
        y1 = int(round((yc - bh / 2.0) * h))
        x2 = int(round((xc + bw / 2.0) * w))
        y2 = int(round((yc + bh / 2.0) * h))

        # Clamp to image boundary
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w - 1, x2), min(h - 1, y2)

        # Draw bounding box rectangle
        cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 2)

        # Badge tag above box
        label_text = f"{cname}"
        (tw, th), baseline = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        tag_y1 = max(0, y1 - th - 6)
        tag_y2 = y1
        tag_x2 = min(w - 1, x1 + tw + 8)

        cv2.rectangle(canvas, (x1, tag_y1), (tag_x2, tag_y2), color, -1)
        cv2.putText(
            canvas,
            label_text,
            (x1 + 4, tag_y2 - 3),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 0, 0),
            1,
            cv2.LINE_AA
        )

    return canvas


def build_contact_sheet(
    image_paths: List[Path],
    label_dir: Path,
    cols: int = 4,
    thumb_w: int = 640,
    thumb_h: int = 360
) -> np.ndarray:
    """Build grid of annotated thumbnails with header banner."""
    annotated_thumbs = []
    for p in image_paths:
        img = cv2.imread(str(p))
        if img is None:
            img = np.zeros((1080, 1920, 3), dtype=np.uint8)

        lbl_file = label_dir / f"{p.stem}.txt"
        boxes = load_yolo_labels(lbl_file)
        annotated = draw_boxes_on_image(img, boxes, frame_title=p.name)

        thumb = cv2.resize(annotated, (thumb_w, thumb_h), interpolation=cv2.INTER_AREA)
        annotated_thumbs.append(thumb)

    n = len(annotated_thumbs)
    rows = (n + cols - 1) // cols

    while len(annotated_thumbs) < rows * cols:
        blank = np.zeros((thumb_h, thumb_w, 3), dtype=np.uint8)
        annotated_thumbs.append(blank)

    grid_rows = []
    for r in range(rows):
        row_thumbs = annotated_thumbs[r * cols : (r + 1) * cols]
        grid_rows.append(np.hstack(row_thumbs))

    grid = np.vstack(grid_rows)

    # Header banner
    banner_height = 60
    grid_w = grid.shape[1]
    banner = np.zeros((banner_height, grid_w, 3), dtype=np.uint8)
    banner[:] = (24, 24, 24)

    title = "AEGIS COMMAND | EVALUATION DATASET LABEL PREVIEW (12 KEYFRAMES)"
    legend = "LEGEND: [CYAN: person]  [LIME: car]  [ORANGE: truck]  [MAGENTA: bus]"
    cv2.putText(banner, title, (20, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(banner, legend, (grid_w - 740, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1, cv2.LINE_AA)

    return np.vstack([banner, grid])


def main():
    parser = argparse.ArgumentParser(description="Generate 12-frame contact sheet preview of evaluation labels.")
    parser.add_argument("--images", default="vision/eval/images", help="Path to evaluation images directory")
    parser.add_argument("--labels", default=None, help="Path to label annotations directory (default: eval/labels or eval/labels_draft)")
    parser.add_argument("--output", default="local_assets/label_preview.jpg", help="Output contact sheet image path")
    parser.add_argument("--num-frames", type=int, default=12, help="Number of sample frames in contact sheet")
    parser.add_argument("--cols", type=int, default=4, help="Grid columns count")
    args = parser.parse_args()

    images_dir = Path(args.images)
    if not images_dir.exists():
        print(f"Error: images directory not found: {images_dir}", file=sys.stderr)
        sys.exit(1)

    all_images = sorted(list(images_dir.glob("*.jpg")))
    if not all_images:
        all_images = sorted(list(images_dir.glob("*.png")))
    if not all_images:
        print(f"Error: no images found in {images_dir}", file=sys.stderr)
        sys.exit(1)

    # Determine labels directory
    if args.labels:
        labels_dir = Path(args.labels)
    else:
        verified_labels = Path("vision/eval/labels")
        if verified_labels.exists() and list(verified_labels.glob("*.txt")):
            labels_dir = verified_labels
        else:
            labels_dir = Path("vision/eval/labels_draft")

    print(f"Generating preview using:")
    print(f"  Images dir: {images_dir} ({len(all_images)} frames available)")
    print(f"  Labels dir: {labels_dir}")
    print(f"  Output:     {args.output}")

    # Deterministically select evenly spaced keyframes
    n_samples = min(args.num_frames, len(all_images))
    indices = np.linspace(0, len(all_images) - 1, n_samples, dtype=int)
    selected_paths = [all_images[i] for i in indices]

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    contact_sheet = build_contact_sheet(
        selected_paths,
        labels_dir,
        cols=args.cols,
        thumb_w=640,
        thumb_h=360
    )

    cv2.imwrite(str(out_path), contact_sheet, [cv2.IMWRITE_JPEG_QUALITY, 90])
    print(f"Successfully generated contact sheet preview: {out_path} ({contact_sheet.shape[1]}x{contact_sheet.shape[0]} px)")


if __name__ == "__main__":
    main()
