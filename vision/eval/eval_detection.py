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
    fold: int = 1,
    manifest_path: str = "vision/data/split_manifest.json",
    native_classes: Optional[bool] = None,
    device: str = "cpu",
    limit: Optional[int] = None,
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
        fold_key = f"fold_{fold}"
        if fold_key in manifest and f"{split}_stems" in manifest[fold_key]:
            target_stems = set(manifest[fold_key][f"{split}_stems"])
        elif f"{split}_stems" in manifest:
            target_stems = set(manifest[f"{split}_stems"])
        else:
            print(f"Error: no stems found for split {split} in {m_path}", file=sys.stderr)
            sys.exit(1)
        images = [img for img in all_images if img.stem in target_stems]
        print(f"Filtered split '{split}' (Fold {fold}): {len(images)} / {len(all_images)} images.")
    else:
        images = all_images
        print(f"Evaluating full set: {len(images)} images.")

    if limit is not None and limit > 0:
        images = images[:limit]
        print(f"Applied image limit: evaluating first {len(images)} images only.")

    print(f"Verified marker found. Evaluating {len(images)} images with {model_path} on {device}...")
    from ultralytics import YOLO
    model = YOLO(model_path)

    # Auto-detect native classes if not explicitly provided
    if native_classes is None:
        model_names = getattr(model, "names", {})
        if len(model_names) <= 4 and model_names.get(0, "").lower() == "person":
            native_classes = True
            print("Auto-detected custom fine-tuned model with native classes (0..3).")
        else:
            native_classes = False
            print("Auto-detected standard COCO model; applying COCO_TO_EVAL class remapping.")

    latencies_ms = []
    raw_predictions = []
    image_ids = [img.stem for img in images]

    # Predict with minimum threshold to capture both 0.25 and 0.35
    eval_conf_min = min(0.20, conf)

    # Warmup
    if images:
        model.predict(source=str(images[0]), imgsz=imgsz, conf=eval_conf_min, device=device, verbose=False)

    print("Running inference and latency profiling...")
    predict_classes = list(CLASS_NAMES.keys()) if native_classes else list(COCO_TO_EVAL.keys())

    for img in images:
        t0 = time.perf_counter()
        results = model.predict(
            source=str(img),
            imgsz=imgsz,
            conf=eval_conf_min,
            classes=predict_classes,
            device=device,
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
                raw_predictions.append({
                    "image_id": img.stem,
                    "class": eval_cls,
                    "conf": conf_val,
                    "box": [x1, y1, x2, y2]
                })

    # Load verified ground truths
    ground_truths = load_yolo_labels(labels_path, image_ids)

    # Latency statistics
    latency_stats = {
        "mean_ms": round(float(np.mean(latencies_ms)), 2) if latencies_ms else 0.0,
        "p50_ms": round(float(np.percentile(latencies_ms, 50)), 2) if latencies_ms else 0.0,
        "p95_ms": round(float(np.percentile(latencies_ms, 95)), 2) if latencies_ms else 0.0
    }

    # Evaluate at multiple confidence thresholds: 0.25 and 0.35
    conf_thresholds = [0.25, 0.35]
    metrics_by_conf = {}

    from metrics import bootstrap_metric_ci

    for c_thresh in conf_thresholds:
        preds_thresh = [p for p in raw_predictions if p["conf"] >= c_thresh]
        class_eval = {}
        for c_id, c_name in CLASS_NAMES.items():
            m = calculate_metrics_for_class(preds_thresh, ground_truths, target_class=c_id)
            fp_per_frame = round(m["fp"] / len(images), 4) if images else 0.0
            class_eval[c_name] = {
                "n_gt": m["n_gt"],
                "n_pred": m["n_pred"],
                "tp": m["tp"],
                "fp": m["fp"],
                "fp_per_frame": fp_per_frame,
                "precision": m["precision"],
                "recall": m["recall"],
                "f1": m["f1"],
                "ap50": m["ap50"],
                "ap50_95": m["ap50_95"],
            }
            if c_name == "car":
                class_eval[c_name]["note"] = "n=58, unreliable"
            elif c_name == "bus":
                class_eval[c_name]["note"] = "n=0, excluded"

        metrics_by_conf[f"conf_{c_thresh}"] = class_eval

    # Compute 95% bootstrap confidence intervals for primary metric: person AP50 and recall (conf=0.25)
    preds_025 = [p for p in raw_predictions if p["conf"] >= 0.25]
    bootstrap_ci = bootstrap_metric_ci(
        preds_025,
        ground_truths,
        image_ids,
        target_class=0, # person
        n_bootstraps=1000,
        seed=42
    )

    # Primary class metrics at requested conf (default 0.25)
    primary_metrics = metrics_by_conf.get(f"conf_{conf}", metrics_by_conf["conf_0.25"])

    # Error analysis at conf 0.25
    error_analysis = perform_error_analysis(preds_025, ground_truths, num_classes=len(CLASS_NAMES))

    results = {
        "evaluated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "model": model_path,
        "split": split,
        "fold": fold,
        "native_classes": native_classes,
        "imgsz": imgsz,
        "device": device,
        "num_images": len(images),
        "latency_ms": latency_stats,
        "bootstrap_ci_95_person": bootstrap_ci,
        "metrics_at_conf_0.25": metrics_by_conf["conf_0.25"],
        "metrics_at_conf_0.35": metrics_by_conf["conf_0.35"],
        "error_analysis": error_analysis
    }

    out_path = Path(out_results)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 75)
    print(f"DETECTION EVALUATION RESULTS (Split: {split}, Model: {model_path}, Imgsz: {imgsz})")
    print("=" * 75)
    print(f"Latency: Mean={latency_stats['mean_ms']}ms, P50={latency_stats['p50_ms']}ms, P95={latency_stats['p95_ms']}ms")
    print(f"Person 95% Bootstrap CI (1,000 resamples):")
    print(f"  AP50:   [{bootstrap_ci['ap50_ci'][0]:.4f}, {bootstrap_ci['ap50_ci'][1]:.4f}] (mean={bootstrap_ci['ap50_mean']:.4f})")
    print(f"  Recall: [{bootstrap_ci['recall_ci'][0]:.4f}, {bootstrap_ci['recall_ci'][1]:.4f}] (mean={bootstrap_ci['recall_mean']:.4f})")
    print("\nPer-Class Breakdown (Confidence = 0.25):")
    print(f"{'Class':<10} {'GT Count':<10} {'P':<8} {'R':<8} {'F1':<8} {'AP50':<8} {'AP50-95':<10} {'FP/frame':<10} {'Notes'}")
    print("-" * 75)
    for c_id, c_name in CLASS_NAMES.items():
        if c_name == "bus":
            continue # Exclude bus (n=0, meaningless)
        cm = metrics_by_conf["conf_0.25"][c_name]
        note = cm.get("note", "")
        print(f"{c_name:<10} {cm['n_gt']:<10} {cm['precision']:<8.4f} {cm['recall']:<8.4f} {cm['f1']:<8.4f} {cm['ap50']:<8.4f} {cm['ap50_95']:<10.4f} {cm['fp_per_frame']:<10.4f} {note}")
    print("=" * 75)
    print(f"\nFull results saved to {out_results}")
    return results


def main():
    parser = argparse.ArgumentParser(description="Evaluate detection models on verified ground truth.")
    parser.add_argument("--model", default="yolov8s.pt", help="Path or name of model weights")
    parser.add_argument("--split", choices=["all", "train", "val"], default="all", help="Dataset split to evaluate")
    parser.add_argument("--fold", type=int, default=1, choices=[1, 2], help="Fold index (1 or 2)")
    parser.add_argument("--images-dir", default="vision/eval/images", help="Path to images directory")
    parser.add_argument("--labels-dir", default="vision/eval/labels", help="Path to labels directory")
    parser.add_argument("--manifest", default="vision/data/split_manifest.json", help="Path to split manifest")
    parser.add_argument("--imgsz", type=int, default=960, help="Inference image resolution")
    parser.add_argument("--conf", type=float, default=0.25, help="Confidence threshold")
    parser.add_argument("--device", default="cpu", help="Compute device (cpu, cuda, or 0)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of images for rapid testing")
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
        fold=args.fold,
        manifest_path=args.manifest,
        native_classes=args.native_classes,
        device=args.device,
        limit=args.limit,
        out_results=args.out
    )


if __name__ == "__main__":
    main()
