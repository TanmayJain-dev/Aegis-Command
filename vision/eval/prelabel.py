#!/usr/bin/env python3
"""
Generate draft labels on evaluation frames using YOLOv8s.
Model: yolov8s.pt
Image Size: 960
Confidence: 0.25
Target classes:
  0: person (COCO 0)
  1: car    (COCO 2)
  2: truck  (COCO 7)
  3: bus    (COCO 5)
Outputs draft labels in YOLO format (class x_center y_center width height normalized)
to vision/eval/labels_draft/.
"""

import sys
from pathlib import Path
from ultralytics import YOLO

COCO_TO_EVAL_CLASS = {
    0: 0,  # person
    2: 1,  # car
    7: 2,  # truck
    5: 3,  # bus
}

def prelabel(
    images_dir="vision/eval/images",
    labels_dir="vision/eval/labels_draft",
    model_name="yolov8s.pt",
    imgsz=960,
    conf=0.25
):
    img_path = Path(images_dir)
    if not img_path.exists():
        print(f"Error: images directory not found: {img_path}", file=sys.stderr)
        sys.exit(1)

    out_path = Path(labels_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    images = sorted(list(img_path.glob("*.png")) + list(img_path.glob("*.jpg")))
    if not images:
        print(f"Error: no images found in {img_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading {model_name}...")
    model = YOLO(model_name)

    print(f"Running inference on {len(images)} images (imgsz={imgsz}, conf={conf})...")
    coco_classes = list(COCO_TO_EVAL_CLASS.keys())

    total_boxes = 0
    class_counts = {0: 0, 1: 0, 2: 0, 3: 0}

    for img_file in images:
        results = model.predict(
            source=str(img_file),
            imgsz=imgsz,
            conf=conf,
            classes=coco_classes,
            verbose=False,
            device="cpu"
        )

        label_file = out_path / f"{img_file.stem}.txt"
        lines = []

        if results and len(results) > 0:
            boxes = results[0].boxes
            for box in boxes:
                coco_cls = int(box.cls[0].item())
                if coco_cls not in COCO_TO_EVAL_CLASS:
                    continue

                eval_cls = COCO_TO_EVAL_CLASS[coco_cls]
                xywhn = box.xywhn[0].tolist()
                x_c, y_c, w, h = xywhn

                lines.append(f"{eval_cls} {x_c:.6f} {y_c:.6f} {w:.6f} {h:.6f}")
                total_boxes += 1
                class_counts[eval_cls] += 1

        with open(label_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + ("\n" if lines else ""))

    print(f"Completed pre-labeling.")
    print(f"Total draft boxes: {total_boxes}")
    print(f"Breakdown: person(0)={class_counts[0]}, car(1)={class_counts[1]}, truck(2)={class_counts[2]}, bus(3)={class_counts[3]}")
    print(f"Draft labels saved to {out_path}.")

if __name__ == "__main__":
    prelabel()
