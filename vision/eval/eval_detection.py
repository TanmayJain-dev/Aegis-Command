#!/usr/bin/env python3
"""
Aegis Command - Detection Evaluation Pipeline.

STRICT GATE: Refuses to run and exits with code 2 if vision/eval/labels/VERIFIED is missing.
Does NOT compute or report accuracy metrics against draft/pre-labels.

When VERIFIED labels exist:
- Runs inference on eval images
- Measures CPU latency (mean, p50, p95 ms per image)
- Computes per-class and overall Precision, Recall, F1, AP50, mAP50-95
- Performs error analysis (confusion matrix, false-positive breakdown, false-negative area distribution)
- Saves results to vision/eval/eval_results.json
"""

import sys
import os
import json
import time
import argparse
from pathlib import Path
from typing import Optional
import numpy as np

# Import evaluation metrics engine
sys.path.insert(0, str(Path(__file__).resolve().parent))
from metrics import calculate_metrics_for_class, perform_error_analysis
from finalize_labels import compute_labels_sha256

CLASS_NAMES = {
    0: "person",
    1: "car",
    2: "truck",
    3: "bus"
}

COCO_TO_EVAL = {
    0: 0,
    2: 1,
    7: 2,
    5: 3
}

def check_verification_gate(labels_dir: Path) -> Path:
    verified_file = labels_dir / "VERIFIED"
    if not verified_file.exists():
        print(
            "\n" + "=" * 70 + "\n"
            "STRICT GATE REJECTION (Exit Code 2):\n"
            f"Missing required verification marker: {verified_file}\n\n"
            "Evaluation cannot be run against unverified or draft labels.\n"
            "To run evaluation:\n"
            "  1. Annotate/verify frames following docs/LABELING.md\n"
            "  2. Export verified YOLO labels into vision/eval/labels/\n"
            "  3. Create vision/eval/labels/VERIFIED with annotator metadata\n"
            "=" * 70 + "\n",
            file=sys.stderr
        )
        sys.exit(2)

    content = verified_file.read_text(encoding="utf-8")
    expected_sha256 = None
    for line in content.splitlines():
        if line.startswith("SHA256:"):
            expected_sha256 = line.split(":", 1)[1].strip()
            break

    if not expected_sha256:
        print(
            "\n" + "=" * 70 + "\n"
            "STRICT GATE REJECTION (Exit Code 2):\n"
            f"Missing SHA256 checksum in verification marker: {verified_file}\n"
            "The labels directory must be finalized with a valid SHA256 checksum.\n"
            "=" * 70 + "\n",
            file=sys.stderr
        )
        sys.exit(2)

    actual_sha256 = compute_labels_sha256(labels_dir)
    if actual_sha256 != expected_sha256:
        print(
            "\n" + "=" * 70 + "\n"
            "STRICT GATE REJECTION (Exit Code 2):\n"
            f"SHA256 checksum mismatch for label files in {labels_dir}!\n"
            f"  Expected: {expected_sha256}\n"
            f"  Actual:   {actual_sha256}\n"
            "Labels have been modified, corrupted, or tampered with since verification.\n"
            "=" * 70 + "\n",
            file=sys.stderr
        )
        sys.exit(2)

    return verified_file

def load_yolo_labels(labels_dir: Path, image_ids: list) -> list:
    """
    Loads YOLO format labels (cls x_c y_c w h normalized) and converts to [x1, y1, x2, y2].
    """
    gts = []
    for img_id in image_ids:
        txt_file = labels_dir / f"{img_id}.txt"
        if not txt_file.exists():
            continue
        with open(txt_file, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 5:
                    cls_id = int(parts[0])
                    xc, yc, w, h = map(float, parts[1:5])
                    x1 = max(0.0, xc - w / 2)
                    y1 = max(0.0, yc - h / 2)
                    x2 = min(1.0, xc + w / 2)
                    y2 = min(1.0, yc + h / 2)
                    gts.append({
                        "image_id": img_id,
                        "class": cls_id,
                        "box": [x1, y1, x2, y2]
                    })
    return gts

def run_evaluation(
    images_dir: str = "vision/eval/images",
    labels_dir: str = "vision/eval/labels",
    model_path: str = "yolov8s.pt",
    imgsz: int = 960,
    conf: float = 0.25,
    split: str = "all",
    manifest_path: str = "vision/data/split_manifest.json",
    native_classes: Optional[bool] = None,
    out_results: str = "vision/eval/eval_results.json"
):
    labels_path = Path(labels_dir)
    check_verification_gate(labels_path)

    images_path = Path(images_dir)
    if not images_path.exists():
        print(f"Error: images directory not found at {images_path}", file=sys.stderr)
        sys.exit(1)

    all_images = sorted(list(images_path.glob("*.png")) + list(images_path.glob("*.jpg")))
    if not all_images:
        print(f"Error: no images found in {images_path}", file=sys.stderr)
        sys.exit(1)

    # Filter by split if requested
    if split in ("train", "val"):
        m_path = Path(manifest_path)
        if not m_path.exists():
            print(f"Error: manifest {m_path} required for --split {split}", file=sys.stderr)
            sys.exit(1)
        with open(m_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        target_stems = set(manifest[f"{split}_stems"])
        images = [img for img in all_images if img.stem in target_stems]
        print(f"Filtered split '{split}': {len(images)} / {len(all_images)} images.")
    else:
        images = all_images
        print(f"Evaluating full set: {len(images)} images.")

    print(f"Verified marker found. Evaluating {len(images)} images with {model_path}...")
    from ultralytics import YOLO
    model = YOLO(model_path)

    # Auto-detect native classes if not explicitly provided
    if native_classes is None:
        # If model has <= 4 classes and first class is person, it is our custom fine-tuned model
        model_names = getattr(model, "names", {})
        if len(model_names) <= 4 and model_names.get(0, "").lower() == "person":
            native_classes = True
            print("Auto-detected custom fine-tuned model with native classes (0..3).")
        else:
            native_classes = False
            print("Auto-detected standard COCO model; applying COCO_TO_EVAL class remapping.")

    latencies_ms = []
    predictions = []
    image_ids = [img.stem for img in images]

    # Warmup
    if images:
        model.predict(source=str(images[0]), imgsz=imgsz, conf=conf, device="cpu", verbose=False)

    print("Running inference and latency profiling...")
    predict_classes = list(CLASS_NAMES.keys()) if native_classes else list(COCO_TO_EVAL.keys())

    for img in images:
        t0 = time.perf_counter()
        results = model.predict(
            source=str(img),
            imgsz=imgsz,
            conf=conf,
            classes=predict_classes,
            device="cpu",
            verbose=False
        )
        t1 = time.perf_counter()
        latencies_ms.append((t1 - t0) * 1000.0)

        if results and len(results) > 0:
            boxes = results[0].boxes
            for box in boxes:
                c_cls = int(box.cls[0].item())
                if native_classes:
                    if c_cls in CLASS_NAMES:
                        eval_cls = c_cls
                    else:
                        continue
                else:
                    if c_cls in COCO_TO_EVAL:
                        eval_cls = COCO_TO_EVAL[c_cls]
                    else:
                        continue

                conf_val = float(box.conf[0].item())
                xywhn = box.xywhn[0].tolist()
                xc, yc, w, h = xywhn
                x1 = max(0.0, xc - w / 2)
                y1 = max(0.0, yc - h / 2)
                x2 = min(1.0, xc + w / 2)
                y2 = min(1.0, yc + h / 2)
                predictions.append({
                    "image_id": img.stem,
                    "class": eval_cls,
                    "conf": conf_val,
                    "box": [x1, y1, x2, y2]
                })

    # Load verified ground truths
    ground_truths = load_yolo_labels(labels_path, image_ids)

    # Compute latency statistics
    latency_stats = {
        "mean_ms": round(float(np.mean(latencies_ms)), 2),
        "p50_ms": round(float(np.percentile(latencies_ms, 50)), 2),
        "p95_ms": round(float(np.percentile(latencies_ms, 95)), 2)
    }

    # Compute per-class and overall metrics
    class_metrics = {}
    ap50_list = []
    ap50_95_list = []

    for c_id, c_name in CLASS_NAMES.items():
        m = calculate_metrics_for_class(predictions, ground_truths, target_class=c_id)
        class_metrics[c_name] = m
        if m["n_gt"] > 0:
            ap50_list.append(m["ap50"])
            ap50_95_list.append(m["ap50_95"])

    overall_metrics = {
        "mAP50": round(float(np.mean(ap50_list)) if ap50_list else 0.0, 4),
        "mAP50_95": round(float(np.mean(ap50_95_list)) if ap50_95_list else 0.0, 4),
        "total_gt": len(ground_truths),
        "total_pred": len(predictions)
    }

    # Error analysis
    error_analysis = perform_error_analysis(predictions, ground_truths, num_classes=len(CLASS_NAMES))

    results = {
        "evaluated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "model": model_path,
        "split": split,
        "native_classes": native_classes,
        "imgsz": imgsz,
        "conf_threshold": conf,
        "num_images": len(images),
        "latency_cpu": latency_stats,
        "overall": overall_metrics,
        "per_class": class_metrics,
        "error_analysis": error_analysis
    }

    out_path = Path(out_results)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 60)
    print(f"DETECTION EVALUATION RESULTS (Split: {split}, Model: {model_path})")
    print("=" * 60)
    print(f"CPU Latency: Mean={latency_stats['mean_ms']}ms, P50={latency_stats['p50_ms']}ms, P95={latency_stats['p95_ms']}ms")
    print(f"Overall: mAP50={overall_metrics['mAP50']:.4f}, mAP50-95={overall_metrics['mAP50_95']:.4f}")
    for c_name, m in class_metrics.items():
        print(f"  {c_name:8s}: P={m['precision']:.4f}, R={m['recall']:.4f}, F1={m['f1']:.4f}, AP50={m['ap50']:.4f}, AP50-95={m['ap50_95']:.4f} (GT={m['n_gt']})")
    print(f"\nFull results saved to {out_results}")
    return results


def main():
    parser = argparse.ArgumentParser(description="Evaluate detection models on verified ground truth.")
    parser.add_argument("--model", default="yolov8s.pt", help="Path or name of model weights")
    parser.add_argument("--split", choices=["all", "train", "val"], default="all", help="Dataset split to evaluate")
    parser.add_argument("--images-dir", default="vision/eval/images", help="Path to images directory")
    parser.add_argument("--labels-dir", default="vision/eval/labels", help="Path to labels directory")
    parser.add_argument("--manifest", default="vision/data/split_manifest.json", help="Path to split manifest")
    parser.add_argument("--imgsz", type=int, default=960, help="Inference image resolution")
    parser.add_argument("--conf", type=float, default=0.25, help="Confidence threshold")
    parser.add_argument("--native-classes", action="store_true", default=None, help="Force native class indices")
    parser.add_argument("--out", default="vision/eval/eval_results.json", help="Output results JSON path")
    args = parser.parse_args()

    run_evaluation(
        images_dir=args.images_dir,
        labels_dir=args.labels_dir,
        model_path=args.model,
        imgsz=args.imgsz,
        conf=args.conf,
        split=args.split,
        manifest_path=args.manifest,
        native_classes=args.native_classes,
        out_results=args.out
    )


if __name__ == "__main__":
    main()
