#!/usr/bin/env python3
"""
Aegis Command - Evaluate and Score Shipped detections.json Artifacts.

Scores any detections.json (pixel coordinates, timestamp string keys)
against the verified 155 evaluation frames.

Evaluation methodology:
- Normalizes pixel bounding boxes by source video resolution (default 1920x1080).
- Matches video manifest frame timestamps with detections keyframes (tolerance default 0.05s).
- Greedy IoU matching at IoU >= 0.50 per class.
- Evaluates per-class Precision, Recall, F1, AP50, and AP50-95.
- Computes Recall broken down by GT object height buckets:
    - < 16 px (Extremely tiny / sub-scale)
    - 16 - 32 px (Small aerial targets)
    - 32 - 64 px (Medium targets)
    - > 64 px (Large foreground targets)
- Computes Best-F1 confidence threshold per class via fine-grained threshold sweep (0.01..0.95).
- Saves raw evaluation metrics to docs/results/raw/ for verification.
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "vision" / "eval"))

from metrics import box_iou, compute_ap
from finalize_labels import compute_labels_sha256
from eval_detection import check_verification_gate, load_yolo_labels, CLASS_NAMES

CLASS_STR_TO_ID = {
    "person": 0,
    "car": 1,
    "truck": 2,
    "bus": 3
}

HEIGHT_BUCKETS = [
    ("<16px", 0.0, 16.0),
    ("16-32px", 16.0, 32.0),
    ("32-64px", 32.0, 64.0),
    (">64px", 64.0, float("inf")),
]


def score_detections(
    detections_path: Path,
    labels_dir: Path = REPO_ROOT / "vision" / "eval" / "labels",
    manifest_path: Path = REPO_ROOT / "vision" / "eval" / "manifest.json",
    source_width: int = 1920,
    source_height: int = 1080,
    time_tolerance: float = 0.05,
    out_json: Optional[Path] = None
) -> Dict[str, Any]:
    # 1. Gate check
    check_verification_gate(labels_dir)
    labels_sha256 = compute_labels_sha256(labels_dir)

    # 2. Load manifest
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # 3. Load ground truth
    image_ids = [f["filename"].replace(".jpg", "") for f in manifest["frames"]]
    gts = load_yolo_labels(labels_dir, image_ids)

    # Augment GT with height in pixels and height bucket
    for g in gts:
        h_norm = g["box"][3] - g["box"][1]
        h_px = round(h_norm * source_height, 2)
        g["height_px"] = h_px
        for b_name, b_min, b_max in HEIGHT_BUCKETS:
            if b_min <= h_px < b_max:
                g["height_bucket"] = b_name
                break

    # 4. Load detections.json
    if not detections_path.exists():
        raise FileNotFoundError(f"Detections JSON not found: {detections_path}")
    with open(detections_path, "r", encoding="utf-8") as f:
        det_data = json.load(f)

    # 5. Extract and normalize predictions aligned to manifest timestamps
    det_timestamps = sorted([float(k) for k in det_data.keys()])
    normalized_preds = []

    matched_frames_count = 0
    empty_frames_count = 0

    for frame in manifest["frames"]:
        f_stem = frame["filename"].replace(".jpg", "")
        f_time = frame["time_s"]

        # Find closest detection timestamp within tolerance
        closest_t = None
        min_dt = time_tolerance
        for dt in det_timestamps:
            delta = abs(dt - f_time)
            if delta <= min_dt:
                min_dt = delta
                closest_t = dt

        if closest_t is not None:
            key_str = str(closest_t) if str(closest_t) in det_data else f"{closest_t:.2f}"
            if key_str not in det_data:
                # Try finding exact matching key in raw dict
                for k in det_data:
                    if abs(float(k) - closest_t) < 1e-4:
                        key_str = k
                        break

            raw_list = det_data.get(key_str, [])
            if raw_list:
                matched_frames_count += 1
            else:
                empty_frames_count += 1

            for item in raw_list:
                c_name = str(item.get("class", "")).lower()
                if c_name not in CLASS_STR_TO_ID:
                    continue
                cid = CLASS_STR_TO_ID[c_name]
                conf = float(item.get("confidence", 1.0))
                b = item["box"]  # [x1, y1, x2, y2] in pixels
                x1 = max(0.0, min(1.0, b[0] / source_width))
                y1 = max(0.0, min(1.0, b[1] / source_height))
                x2 = max(0.0, min(1.0, b[2] / source_width))
                y2 = max(0.0, min(1.0, b[3] / source_height))

                normalized_preds.append({
                    "frame_id": f_stem,
                    "image_id": f_stem,
                    "class": cid,
                    "class_id": cid,
                    "conf": conf,
                    "box": [round(x1, 6), round(y1, 6), round(x2, 6), round(y2, 6)]
                })
        else:
            empty_frames_count += 1

    # 6. Per-class metrics & Best-F1 threshold search
    class_eval = {}
    macro_ap50 = []

    for cid, cname in CLASS_NAMES.items():
        class_gts = [g for g in gts if g["class"] == cid]
        class_preds = [p for p in normalized_preds if p["class"] == cid]
        n_gt = len(class_gts)
        n_pred = len(class_preds)

        if n_gt == 0:
            class_eval[cname] = {
                "n_gt": 0,
                "n_pred": n_pred,
                "note": "excluded_no_gt"
            }
            continue

        # Sort predictions by confidence descending
        sorted_preds = sorted(class_preds, key=lambda p: p["conf"], reverse=True)

        # 6a. AP50 and AP50-95
        iou_thresholds = [round(x, 2) for x in np.arange(0.5, 1.0, 0.05)]
        ap_per_iou = []

        for iou_th in iou_thresholds:
            tp = np.zeros(n_pred)
            fp = np.zeros(n_pred)
            img_gt_matched = {}

            for p_idx, p in enumerate(sorted_preds):
                img_id = p["image_id"]
                img_gts = [g for g in class_gts if g["image_id"] == img_id]
                if img_id not in img_gt_matched:
                    img_gt_matched[img_id] = [False] * len(img_gts)

                best_iou = 0.0
                best_gt_idx = -1
                for g_idx, g in enumerate(img_gts):
                    iou = box_iou(p["box"], g["box"])
                    if iou > best_iou:
                        best_iou = iou
                        best_gt_idx = g_idx

                if best_iou >= iou_th and best_gt_idx >= 0:
                    if not img_gt_matched[img_id][best_gt_idx]:
                        tp[p_idx] = 1
                        img_gt_matched[img_id][best_gt_idx] = True
                    else:
                        fp[p_idx] = 1
                else:
                    fp[p_idx] = 1

            cum_tp = np.cumsum(tp)
            cum_fp = np.cumsum(fp)
            recalls = cum_tp / n_gt
            precisions = cum_tp / (cum_tp + cum_fp)
            ap_per_iou.append(compute_ap(recalls, precisions))

        ap50 = ap_per_iou[0]
        ap50_95 = float(np.mean(ap_per_iou))
        macro_ap50.append(ap50)

        # 6b. Standard metrics at confidence >= 0.25
        preds_025 = [p for p in sorted_preds if p["conf"] >= 0.25]
        img_gt_matched_025 = {}
        tp_025 = 0
        fp_025 = 0

        for p in preds_025:
            img_id = p["image_id"]
            img_gts = [g for g in class_gts if g["image_id"] == img_id]
            if img_id not in img_gt_matched_025:
                img_gt_matched_025[img_id] = [False] * len(img_gts)

            best_iou = 0.0
            best_gt_idx = -1
            for g_idx, g in enumerate(img_gts):
                iou = box_iou(p["box"], g["box"])
                if iou > best_iou:
                    best_iou = iou
                    best_gt_idx = g_idx

            if best_iou >= 0.5 and best_gt_idx >= 0 and not img_gt_matched_025[img_id][best_gt_idx]:
                tp_025 += 1
                img_gt_matched_025[img_id][best_gt_idx] = True
            else:
                fp_025 += 1

        prec_025 = tp_025 / (tp_025 + fp_025) if (tp_025 + fp_025) > 0 else 0.0
        rec_025 = tp_025 / n_gt if n_gt > 0 else 0.0
        f1_025 = (2 * prec_025 * rec_025) / (prec_025 + rec_025) if (prec_025 + rec_025) > 0 else 0.0

        # 6c. Best-F1 Confidence Threshold Sweep (0.01 to 0.95 with step 0.01)
        best_f1 = 0.0
        best_conf = 0.25
        best_prec = 0.0
        best_rec = 0.0

        for thresh in np.arange(0.05, 0.96, 0.01):
            thresh = round(float(thresh), 2)
            c_preds = [p for p in sorted_preds if p["conf"] >= thresh]
            c_matched = {}
            c_tp = 0
            c_fp = 0
            for p in c_preds:
                img_id = p["image_id"]
                img_gts = [g for g in class_gts if g["image_id"] == img_id]
                if img_id not in c_matched:
                    c_matched[img_id] = [False] * len(img_gts)
                b_iou = 0.0
                b_idx = -1
                for g_idx, g in enumerate(img_gts):
                    iou = box_iou(p["box"], g["box"])
                    if iou > b_iou:
                        b_iou = iou
                        b_idx = g_idx
                if b_iou >= 0.5 and b_idx >= 0 and not c_matched[img_id][b_idx]:
                    c_tp += 1
                    c_matched[img_id][b_idx] = True
                else:
                    c_fp += 1
            p_val = c_tp / (c_tp + c_fp) if (c_tp + c_fp) > 0 else 0.0
            r_val = c_tp / n_gt if n_gt > 0 else 0.0
            f1_val = (2 * p_val * r_val) / (p_val + r_val) if (p_val + r_val) > 0 else 0.0
            if f1_val > best_f1:
                best_f1 = f1_val
                best_conf = thresh
                best_prec = p_val
                best_rec = r_val

        class_eval[cname] = {
            "n_gt": n_gt,
            "n_pred": n_pred,
            "metrics_at_conf_0.25": {
                "tp": tp_025,
                "fp": fp_025,
                "precision": round(prec_025, 4),
                "recall": round(rec_025, 4),
                "f1": round(f1_025, 4)
            },
            "best_f1_threshold": {
                "best_conf": best_conf,
                "best_f1": round(best_f1, 4),
                "precision": round(best_prec, 4),
                "recall": round(best_rec, 4)
            },
            "ap50": round(ap50, 4),
            "ap50_95": round(ap50_95, 4)
        }

    # 7. Recall by Object Height Bucket (Evaluated across all GTs at conf >= 0.25)
    # Determine which GT boxes were matched by ANY prediction of matching class at conf >= 0.25
    height_bucket_stats = {}
    for b_name, _, _ in HEIGHT_BUCKETS:
        height_bucket_stats[b_name] = {
            "gt_total": 0,
            "gt_matched": 0,
            "recall": 0.0,
            "by_class": {}
        }

    # Track GT matching across all classes at conf >= 0.25
    gt_global_matched = [False] * len(gts)
    preds_conf025 = [p for p in sorted(normalized_preds, key=lambda x: x["conf"], reverse=True) if p["conf"] >= 0.25]

    for p in preds_conf025:
        img_id = p["image_id"]
        p_cls = p["class"]
        best_iou = 0.0
        best_gt_idx = -1
        for idx, g in enumerate(gts):
            if g["image_id"] == img_id and g["class"] == p_cls and not gt_global_matched[idx]:
                iou = box_iou(p["box"], g["box"])
                if iou > best_iou:
                    best_iou = iou
                    best_gt_idx = idx
        if best_iou >= 0.5 and best_gt_idx >= 0:
            gt_global_matched[best_gt_idx] = True

    for idx, g in enumerate(gts):
        b_name = g.get("height_bucket", ">64px")
        cname = CLASS_NAMES.get(g["class"], str(g["class"]))
        st = height_bucket_stats[b_name]
        st["gt_total"] += 1
        st["by_class"].setdefault(cname, {"gt": 0, "matched": 0})
        st["by_class"][cname]["gt"] += 1

        if gt_global_matched[idx]:
            st["gt_matched"] += 1
            st["by_class"][cname]["matched"] += 1

    for b_name, st in height_bucket_stats.items():
        st["recall"] = round(st["gt_matched"] / st["gt_total"], 4) if st["gt_total"] > 0 else 0.0
        for cname, c_st in st["by_class"].items():
            c_st["recall"] = round(c_st["matched"] / c_st["gt"], 4) if c_st["gt"] > 0 else 0.0

    report = {
        "artifact": str(detections_path),
        "source_resolution": f"{source_width}x{source_height}",
        "time_tolerance_s": time_tolerance,
        "labels_sha256": labels_sha256,
        "total_eval_frames": len(manifest["frames"]),
        "frames_with_detections": matched_frames_count,
        "frames_empty": empty_frames_count,
        "total_ground_truth_boxes": len(gts),
        "total_candidate_predictions": len(normalized_preds),
        "per_class_evaluation": class_eval,
        "macro_ap50": round(float(np.mean(macro_ap50)), 4) if macro_ap50 else 0.0,
        "recall_by_height_bucket": height_bucket_stats
    }

    if out_json:
        out_json.parent.mkdir(parents=True, exist_ok=True)
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

    # Print summary tables
    print("=" * 80)
    print(f"AEGIS ARTIFACT EVALUATION REPORT: {detections_path}")
    print("=" * 80)
    print(f"Frames: {len(manifest['frames'])} | Ground Truth Boxes: {len(gts)} | Predictions Evaluated: {len(normalized_preds)}")
    print(f"\n--- PER-CLASS METRICS & BEST-F1 THRESHOLD ---")
    print(f"{'Class':<10} {'GT':<6} {'Pred':<6} {'P@0.25':<8} {'R@0.25':<8} {'F1@0.25':<8} {'AP50':<8} {'AP50-95':<9} {'Best-F1 (Conf)':<18}")
    print("-" * 80)
    for cname, ce in class_eval.items():
        if ce.get("note") == "excluded_no_gt":
            continue
        m25 = ce["metrics_at_conf_0.25"]
        bf1 = ce["best_f1_threshold"]
        print(f"{cname:<10} {ce['n_gt']:<6} {ce['n_pred']:<6} {m25['precision']:<8.4f} {m25['recall']:<8.4f} {m25['f1']:<8.4f} {ce['ap50']:<8.4f} {ce['ap50_95']:<9.4f} {bf1['best_f1']:.4f} (@{bf1['best_conf']:.2f})")

    print(f"\n--- RECALL BY OBJECT HEIGHT BUCKET (Conf >= 0.25) ---")
    print(f"{'Height Bucket':<16} {'GT Total':<10} {'GT Matched':<12} {'Recall':<10}")
    print("-" * 50)
    for b_name, st in height_bucket_stats.items():
        print(f"{b_name:<16} {st['gt_total']:<10} {st['gt_matched']:<12} {st['recall']*100:.2f}%")
    print("=" * 80)

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Score detections.json artifact against verified labels")
    parser.add_argument("--detections", default="frontend/public/feeds/uav-alpha/detections.json", help="Path to detections.json")
    parser.add_argument("--labels-dir", default=str(REPO_ROOT / "vision" / "eval" / "labels"), help="Path to labels dir")
    parser.add_argument("--manifest", default=str(REPO_ROOT / "vision" / "eval" / "manifest.json"), help="Path to manifest")
    parser.add_argument("--source-width", type=int, default=1920)
    parser.add_argument("--source-height", type=int, default=1080)
    parser.add_argument("--time-tolerance", type=float, default=0.05)
    parser.add_argument("--out", default="docs/results/raw/task2_uav_alpha_baseline.json", help="Output JSON path")
    args = parser.parse_args()

    score_detections(
        detections_path=Path(args.detections),
        labels_dir=Path(args.labels_dir),
        manifest_path=Path(args.manifest),
        source_width=args.source_width,
        source_height=args.source_height,
        time_tolerance=args.time_tolerance,
        out_json=Path(args.out)
    )
