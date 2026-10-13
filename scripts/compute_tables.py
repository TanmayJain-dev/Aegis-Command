#!/usr/bin/env python3
"""
Aegis Command - Compute Benchmark Tables from Raw Prediction Outputs.

Reads docs/results/raw/<run_id>/predictions.json and run_meta.json,
recomputes AP50, AP50-95, P/R at 0.25 and 0.35, FP/frame, and
1,000-resample bootstrap confidence intervals (seed 42) directly from raw predictions.
"""

import sys
import os
import json
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add project root and vision/eval to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "vision" / "eval"))

from metrics import calculate_metrics_for_class, bootstrap_metric_ci
from finalize_labels import compute_labels_sha256
from eval_detection import check_verification_gate, load_yolo_labels, CLASS_NAMES


def compute_metrics_for_run(
    run_dir: Path,
    labels_dir: Path = PROJECT_ROOT / "vision" / "eval" / "labels",
    manifest_path: Path = PROJECT_ROOT / "vision" / "data" / "split_manifest.json",
    n_bootstraps: int = 1000,
    seed: int = 42
) -> Dict[str, Any]:
    """
    Recomputes metrics from raw run directory containing predictions.json and run_meta.json.
    """
    preds_file = run_dir / "predictions.json"
    meta_file = run_dir / "run_meta.json"

    if not preds_file.exists():
        raise FileNotFoundError(f"Missing predictions.json in {run_dir}")
    if not meta_file.exists():
        raise FileNotFoundError(f"Missing run_meta.json in {run_dir}")

    with open(preds_file, "r", encoding="utf-8") as f:
        raw_predictions = json.load(f)
    with open(meta_file, "r", encoding="utf-8") as f:
        run_meta = json.load(f)

    # Check verification gate & label integrity
    check_verification_gate(labels_dir)
    current_sha = compute_labels_sha256(labels_dir)
    meta_sha = run_meta.get("labels_sha256")
    if meta_sha and meta_sha != current_sha:
        raise ValueError(
            f"Labels SHA256 mismatch in {run_dir}!\n"
            f"  Run metadata: {meta_sha}\n"
            f"  Current disk: {current_sha}"
        )

    split = run_meta.get("split", "all")
    fold = run_meta.get("fold", 1)
    num_frames_meta = run_meta.get("num_frames")

    # Determine frame set
    if split in ("train", "val") and manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        fold_key = f"fold_{fold}"
        if fold_key in manifest and f"{split}_stems" in manifest[fold_key]:
            frame_ids = sorted(list(manifest[fold_key][f"{split}_stems"]))
        elif f"{split}_stems" in manifest:
            frame_ids = sorted(list(manifest[f"{split}_stems"]))
        else:
            raise ValueError(f"Split {split} not found in manifest {manifest_path}")
    else:
        # Full set: all label text files in labels_dir
        label_txts = sorted(labels_dir.glob("*.txt"))
        frame_ids = [txt.stem for txt in label_txts]

    if num_frames_meta is not None and num_frames_meta < len(frame_ids):
        # Handle limited/smoke runs if recorded
        pred_stems = sorted(list({p.get("frame_id", p.get("image_id")) for p in raw_predictions if p.get("frame_id") or p.get("image_id")}))
        if len(pred_stems) <= num_frames_meta:
            frame_ids = frame_ids[:num_frames_meta]

    # Load ground truths
    ground_truths = load_yolo_labels(labels_dir, frame_ids)

    # Standardize predictions format
    formatted_preds = []
    for p in raw_predictions:
        img_id = p.get("frame_id") or p.get("image_id")
        cls_id = p.get("class_id") if "class_id" in p else p.get("class")
        conf_val = float(p.get("conf", 0.0))
        box_coords = p.get("box")
        if box_coords is None and "bbox_xywh_norm" in p:
            xc, yc, w, h = p["bbox_xywh_norm"]
            box_coords = [xc - w / 2, yc - h / 2, xc + w / 2, yc + h / 2]
        formatted_preds.append({
            "image_id": img_id,
            "frame_id": img_id,
            "class": cls_id,
            "class_id": cls_id,
            "conf": conf_val,
            "box": box_coords
        })

    # Evaluate at conf 0.25 and 0.35
    preds_025 = [p for p in formatted_preds if p["conf"] >= 0.25]
    preds_035 = [p for p in formatted_preds if p["conf"] >= 0.35]

    class_metrics = {}
    for c_id, c_name in CLASS_NAMES.items():
        m_025 = calculate_metrics_for_class(preds_025, ground_truths, target_class=c_id)
        m_035 = calculate_metrics_for_class(preds_035, ground_truths, target_class=c_id)
        fp_per_frame = round(m_025["fp"] / len(frame_ids), 4) if frame_ids else 0.0

        class_metrics[c_name] = {
            "n_gt": m_025["n_gt"],
            "n_pred_025": m_025["n_pred"],
            "tp_025": m_025["tp"],
            "fp_025": m_025["fp"],
            "fp_per_frame_025": fp_per_frame,
            "precision_025": m_025["precision"],
            "recall_025": m_025["recall"],
            "f1_025": m_025["f1"],
            "ap50": m_025["ap50"],
            "ap50_95": m_025["ap50_95"],
            "precision_035": m_035["precision"],
            "recall_035": m_035["recall"],
            "f1_035": m_035["f1"]
        }

    # Bootstrap 95% CI on Person (class 0) at conf 0.25
    ci = bootstrap_metric_ci(
        preds_025,
        ground_truths,
        frame_ids,
        target_class=0,
        n_bootstraps=n_bootstraps,
        seed=seed
    )

    return {
        "run_id": run_dir.name,
        "model": run_meta.get("weights"),
        "imgsz": run_meta.get("imgsz"),
        "device": run_meta.get("device", "cpu"),
        "split": split,
        "fold": fold,
        "num_frames": len(frame_ids),
        "wall_seconds": run_meta.get("wall_seconds"),
        "latency_mean_ms": run_meta.get("latency_mean_ms", 0.0),
        "latency_p50_ms": run_meta.get("latency_p50_ms", 0.0),
        "latency_p95_ms": run_meta.get("latency_p95_ms", 0.0),
        "bootstrap_ci_95_person": ci,
        "person": class_metrics["person"],
        "truck": class_metrics["truck"],
        "car": class_metrics["car"],
        "bus": class_metrics["bus"]
    }


def format_markdown_row(res: Dict[str, Any]) -> str:
    """
    Formats a single zero-shot bakeoff row matching BENCHMARKS.md table format.
    """
    model_name = Path(res.get("model", "")).stem
    imgsz = res.get("imgsz", 640)
    dev = res.get("device", "cpu").upper()
    lat = res.get("latency_mean_ms", 0.0)

    person = res["person"]
    truck = res["truck"]
    car = res["car"]
    ci = res["bootstrap_ci_95_person"]

    p_ap50 = f"{person['ap50']:.3f} [{ci['ap50_ci'][0]:.3f}, {ci['ap50_ci'][1]:.3f}]"
    p_rec = f"{person['recall_025']:.3f} [{ci['recall_ci'][0]:.3f}, {ci['recall_ci'][1]:.3f}]"

    return (
        f"| **{model_name} @ {imgsz}px** | {dev} | `{p_ap50}` | `{p_rec}` | "
        f"{person['precision_025']:.3f} | {person['recall_025']:.3f} | "
        f"{person['precision_035']:.3f} | {person['recall_035']:.3f} | "
        f"{person['fp_per_frame_025']:.3f} | {truck['ap50']:.3f} | "
        f"{car['ap50']:.3f}* | {lat:.1f} ms ({dev}) |"
    )


def main():
    parser = argparse.ArgumentParser(description="Compute benchmark tables directly from raw predictions.")
    parser.add_argument("--raw-root", default=str(PROJECT_ROOT / "docs" / "results" / "raw"), help="Path to raw results directory")
    parser.add_argument("--run-dir", default=None, help="Compute for a single run directory")
    parser.add_argument("--labels-dir", default=str(PROJECT_ROOT / "vision" / "eval" / "labels"), help="Path to labels directory")
    parser.add_argument("--manifest", default=str(PROJECT_ROOT / "vision" / "data" / "split_manifest.json"), help="Path to split manifest")
    parser.add_argument("--out", default=None, help="Optional output JSON path for computed metrics")
    args = parser.parse_args()

    raw_root = Path(args.raw_root)
    labels_path = Path(args.labels_dir)
    manifest_path = Path(args.manifest)

    if args.run_dir:
        run_dirs = [Path(args.run_dir)]
    elif raw_root.exists():
        run_dirs = sorted([d for d in raw_root.iterdir() if d.is_dir() and (d / "predictions.json").exists()])
    else:
        run_dirs = []

    if not run_dirs:
        print(f"No completed raw runs found in {raw_root}.")
        print("Status: All configurations remain marked 'NOT RUN'.")
        sys.exit(0)

    computed_results = []
    print(f"Recomputing metrics for {len(run_dirs)} raw run(s)...")

    for r_dir in run_dirs:
        try:
            res = compute_metrics_for_run(r_dir, labels_dir=labels_path, manifest_path=manifest_path)
            computed_results.append(res)
            print(f"✓ Recomputed: {r_dir.name}")
            print("  Markdown row:")
            print("  " + format_markdown_row(res))
        except Exception as e:
            print(f"✗ Failed {r_dir.name}: {e}", file=sys.stderr)

    if args.out:
        out_p = Path(args.out)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "w", encoding="utf-8") as f:
            json.dump(computed_results, f, indent=2)
        print(f"\nSaved recomputed metrics to {out_p}")


if __name__ == "__main__":
    main()
