#!/usr/bin/env python3
"""
Aegis Command - Error Analysis on Fine-Tuned Predictions.

Performs:
1. Recall by height bucket (<16px, 16-32px, 32-64px, >64px) for baseline vs fine-tuned.
2. Person-vs-vehicle confusion cross-referenced against the 78 label-QA overlap flags.
3. Top 10 false negatives per fold extracted into scratch/fn_overlays/.
4. Quantitative report output to docs/results/raw/task2_error_analysis.json and markdown.
"""

import sys
import json
import math
from pathlib import Path
from typing import Dict, List, Any, Tuple
import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "vision" / "eval"))

from class_map import CLASS_MAP, CLASS_NAMES
from eval_detection import load_yolo_labels
from split_dataset import get_contiguous_splits
from metrics import box_iou


def analyze_height_buckets(
    raw_root: Path,
    labels_dir: Path,
    images_dir: Path,
    img_height: int = 1080,
    img_width: int = 1920,
    conf_thresh: float = 0.25,
    iou_thresh: float = 0.5
) -> Dict[str, Any]:
    images = sorted(list(images_dir.glob("*.jpg")))
    stems = [img.stem for img in images]
    splits = get_contiguous_splits(stems, num_folds=5)

    buckets = ["<16px", "16-32px", "32-64px", ">64px"]

    stats = {
        "baseline": {b: {"gt": 0, "tp": 0} for b in buckets},
        "finetuned": {b: {"gt": 0, "tp": 0} for b in buckets},
        "per_fold": {}
    }

    def get_bucket(h_px: float) -> str:
        if h_px < 16.0:
            return "<16px"
        elif h_px < 32.0:
            return "16-32px"
        elif h_px < 64.0:
            return "32-64px"
        else:
            return ">64px"

    for fold in range(1, 6):
        val_stems = splits[f"fold_{fold}"]["val_stems"]
        gts = load_yolo_labels(labels_dir, val_stems)
        person_gts = [g for g in gts if g["class"] == 0]

        # Group by image
        gts_by_image = {}
        for g in person_gts:
            gts_by_image.setdefault(g["image_id"], []).append(g)

        fold_stats = {
            "baseline": {b: {"gt": 0, "tp": 0} for b in buckets},
            "finetuned": {b: {"gt": 0, "tp": 0} for b in buckets}
        }

        # Count GTs by bucket
        for g in person_gts:
            x1, y1, x2, y2 = g["box"]
            h_px = (y2 - y1) * img_height
            b = get_bucket(h_px)
            stats["baseline"][b]["gt"] += 1
            stats["finetuned"][b]["gt"] += 1
            fold_stats["baseline"][b]["gt"] += 1
            fold_stats["finetuned"][b]["gt"] += 1

        # Match baseline
        base_dir = raw_root / f"yolov8m_1280px_val_fold{fold}_baseline"
        if (base_dir / "predictions.json").exists():
            with open(base_dir / "predictions.json", "r") as f:
                preds = json.load(f)
            p_preds = [p for p in preds if (p.get("class") == 0 or p.get("class_id") == 0) and p.get("conf", 0.0) >= conf_thresh]
            p_by_image = {}
            for p in p_preds:
                p_by_image.setdefault(p.get("frame_id") or p.get("image_id"), []).append(p)

            for img_id, img_gts in gts_by_image.items():
                img_preds = p_by_image.get(img_id, [])
                matched_gt = [False] * len(img_gts)
                for p in sorted(img_preds, key=lambda x: x.get("conf", 0), reverse=True):
                    for g_idx, g in enumerate(img_gts):
                        if not matched_gt[g_idx] and box_iou(p["box"], g["box"]) >= iou_thresh:
                            matched_gt[g_idx] = True
                            break
                for g_idx, g in enumerate(img_gts):
                    if matched_gt[g_idx]:
                        h_px = (g["box"][3] - g["box"][1]) * img_height
                        b = get_bucket(h_px)
                        stats["baseline"][b]["tp"] += 1
                        fold_stats["baseline"][b]["tp"] += 1

        # Match finetuned
        ft_dir = raw_root / f"yolov8m_1280px_val_fold{fold}_finetuned"
        if (ft_dir / "predictions.json").exists():
            with open(ft_dir / "predictions.json", "r") as f:
                preds = json.load(f)
            p_preds = [p for p in preds if (p.get("class") == 0 or p.get("class_id") == 0) and p.get("conf", 0.0) >= conf_thresh]
            p_by_image = {}
            for p in p_preds:
                p_by_image.setdefault(p.get("frame_id") or p.get("image_id"), []).append(p)

            for img_id, img_gts in gts_by_image.items():
                img_preds = p_by_image.get(img_id, [])
                matched_gt = [False] * len(img_gts)
                for p in sorted(img_preds, key=lambda x: x.get("conf", 0), reverse=True):
                    for g_idx, g in enumerate(img_gts):
                        if not matched_gt[g_idx] and box_iou(p["box"], g["box"]) >= iou_thresh:
                            matched_gt[g_idx] = True
                            break
                for g_idx, g in enumerate(img_gts):
                    if matched_gt[g_idx]:
                        h_px = (g["box"][3] - g["box"][1]) * img_height
                        b = get_bucket(h_px)
                        stats["finetuned"][b]["tp"] += 1
                        fold_stats["finetuned"][b]["tp"] += 1

        stats["per_fold"][f"fold_{fold}"] = fold_stats

    # Compute recalls
    summary = {"baseline": {}, "finetuned": {}}
    for b in buckets:
        gt_b = stats["baseline"][b]["gt"]
        tp_base = stats["baseline"][b]["tp"]
        tp_ft = stats["finetuned"][b]["tp"]
        summary["baseline"][b] = {
            "gt_count": gt_b,
            "tp_count": tp_base,
            "recall": round(tp_base / gt_b, 4) if gt_b > 0 else 0.0
        }
        summary["finetuned"][b] = {
            "gt_count": gt_b,
            "tp_count": tp_ft,
            "recall": round(tp_ft / gt_b, 4) if gt_b > 0 else 0.0
        }

    return {"summary": summary, "raw_counts": stats}


def analyze_person_vehicle_overlaps(
    raw_root: Path,
    qa_csv_path: Path,
    labels_dir: Path,
    images_dir: Path,
    conf_thresh: float = 0.25,
    iou_thresh: float = 0.5
) -> Dict[str, Any]:
    import csv
    images = sorted(list(images_dir.glob("*.jpg")))
    stems = [img.stem for img in images]
    splits = get_contiguous_splits(stems, num_folds=5)

    stem_to_fold = {}
    for f in range(1, 6):
        for s in splits[f"fold_{f}"]["val_stems"]:
            stem_to_fold[s] = f

    overlap_rows = []
    if qa_csv_path.exists():
        with open(qa_csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("issue_type") == "PERSON_VEHICLE_OVERLAP":
                    overlap_rows.append(row)

    total_overlaps = len(overlap_rows)

    fold_preds_ft = {}
    fold_preds_base = {}
    for f in range(1, 6):
        ft_pred_file = raw_root / f"yolov8m_1280px_val_fold{f}_finetuned" / "predictions.json"
        base_pred_file = raw_root / f"yolov8m_1280px_val_fold{f}_baseline" / "predictions.json"
        if ft_pred_file.exists():
            with open(ft_pred_file, "r") as fp:
                fold_preds_ft[f] = json.load(fp)
        if base_pred_file.exists():
            with open(base_pred_file, "r") as fp:
                fold_preds_base[f] = json.load(fp)

    person_detected_ft = 0
    person_detected_base = 0
    vehicle_detected_overlapping_ft = 0
    vehicle_detected_overlapping_base = 0
    examples = []

    for row in overlap_rows:
        frame_id = row["frame"]
        box_coords = json.loads(row["box_xyxy_norm"])
        fold = stem_to_fold.get(frame_id)
        if not fold or fold not in fold_preds_ft:
            continue

        preds_ft = [p for p in fold_preds_ft[fold] if (p.get("frame_id") or p.get("image_id")) == frame_id and p.get("conf", 0) >= conf_thresh]
        preds_base = [p for p in fold_preds_base.get(fold, []) if (p.get("frame_id") or p.get("image_id")) == frame_id and p.get("conf", 0) >= conf_thresh]

        has_person_ft = any((p.get("class") == 0 or p.get("class_id") == 0) and box_iou(p["box"], box_coords) >= iou_thresh for p in preds_ft)
        has_person_base = any((p.get("class") == 0 or p.get("class_id") == 0) and box_iou(p["box"], box_coords) >= iou_thresh for p in preds_base)
        if has_person_ft:
            person_detected_ft += 1
        if has_person_base:
            person_detected_base += 1

        has_veh_ft = any((p.get("class") in (1, 2, 3) or p.get("class_id") in (1, 2, 3)) and box_iou(p["box"], box_coords) >= 0.1 for p in preds_ft)
        has_veh_base = any((p.get("class") in (1, 2, 3) or p.get("class_id") in (1, 2, 3)) and box_iou(p["box"], box_coords) >= 0.1 for p in preds_base)
        if has_veh_ft:
            vehicle_detected_overlapping_ft += 1
        if has_veh_base:
            vehicle_detected_overlapping_base += 1

        if len(examples) < 10:
            examples.append({
                "frame_id": frame_id,
                "box": box_coords,
                "description": row["description"],
                "finetuned_detected_person": has_person_ft,
                "baseline_detected_person": has_person_base
            })

    return {
        "total_flagged_overlaps": total_overlaps,
        "frames_involved": len(set(r["frame"] for r in overlap_rows)),
        "finetuned_person_recall_on_overlaps": round(person_detected_ft / total_overlaps, 4) if total_overlaps > 0 else 0.0,
        "baseline_person_recall_on_overlaps": round(person_detected_base / total_overlaps, 4) if total_overlaps > 0 else 0.0,
        "finetuned_detected_count": person_detected_ft,
        "baseline_detected_count": person_detected_base,
        "vehicle_confusion_overlap_count_ft": vehicle_detected_overlapping_ft,
        "vehicle_confusion_overlap_count_base": vehicle_detected_overlapping_base,
        "sample_cases": examples
    }


def extract_top10_fn_overlays(
    raw_root: Path,
    labels_dir: Path,
    images_dir: Path,
    out_dir: Path,
    conf_thresh: float = 0.25,
    iou_thresh: float = 0.5
) -> Dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    images = sorted(list(images_dir.glob("*.jpg")))
    stems = [img.stem for img in images]
    splits = get_contiguous_splits(stems, num_folds=5)

    fn_summary = {}

    for fold in range(1, 6):
        val_stems = splits[f"fold_{fold}"]["val_stems"]
        gts = load_yolo_labels(labels_dir, val_stems)
        person_gts = [g for g in gts if g["class"] == 0]

        gts_by_image = {}
        for g in person_gts:
            gts_by_image.setdefault(g["image_id"], []).append(g)

        ft_dir = raw_root / f"yolov8m_1280px_val_fold{fold}_finetuned"
        if not (ft_dir / "predictions.json").exists():
            continue

        with open(ft_dir / "predictions.json", "r") as f:
            preds = json.load(f)

        p_preds = [p for p in preds if (p.get("class") == 0 or p.get("class_id") == 0) and p.get("conf", 0.0) >= conf_thresh]
        p_by_image = {}
        for p in p_preds:
            p_by_image.setdefault(p.get("frame_id") or p.get("image_id"), []).append(p)

        unmatched_gts = []

        for img_id, img_gts in gts_by_image.items():
            img_preds = p_by_image.get(img_id, [])
            matched_gt = [False] * len(img_gts)
            for p in sorted(img_preds, key=lambda x: x.get("conf", 0), reverse=True):
                for g_idx, g in enumerate(img_gts):
                    if not matched_gt[g_idx] and box_iou(p["box"], g["box"]) >= iou_thresh:
                        matched_gt[g_idx] = True
                        break

            for g_idx, g in enumerate(img_gts):
                if not matched_gt[g_idx]:
                    x1, y1, x2, y2 = g["box"]
                    w = x2 - x1
                    h = y2 - y1
                    area = w * h
                    unmatched_gts.append({
                        "frame_id": img_id,
                        "box": g["box"],
                        "area": area,
                        "height_px": round(h * 1080, 1),
                        "width_px": round(w * 1920, 1),
                    })

        # Sort FNs by height descending (larger missed targets are more critical)
        unmatched_gts.sort(key=lambda x: x["height_px"], reverse=True)
        top10_fn = unmatched_gts[:10]
        fn_summary[f"fold_{fold}"] = {
            "total_false_negatives": len(unmatched_gts),
            "top10": top10_fn
        }

        # Render overlay crops for top 10
        for idx, fn in enumerate(top10_fn):
            img_path = images_dir / f"{fn['frame_id']}.jpg"
            if not img_path.exists():
                continue
            img = cv2.imread(str(img_path))
            if img is None:
                continue

            ih, iw = img.shape[:2]
            bx1, by1, bx2, by2 = fn["box"]
            px1, py1, px2, py2 = int(bx1 * iw), int(by1 * ih), int(bx2 * iw), int(by2 * ih)

            # Add context padding of 40px
            pad = 50
            cx1 = max(0, px1 - pad)
            cy1 = max(0, py1 - pad)
            cx2 = min(iw, px2 + pad)
            cy2 = min(ih, py2 + pad)

            crop = img[cy1:cy2, cx1:cx2].copy()
            # Draw red rectangle around the missed GT
            cv2.rectangle(
                crop,
                (px1 - cx1, py1 - cy1),
                (px2 - cx1, py2 - cy1),
                (0, 0, 255),
                2
            )
            cv2.putText(
                crop,
                f"FN: {fn['height_px']}px",
                (px1 - cx1, max(15, py1 - cy1 - 5)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (0, 0, 255),
                1
            )

            out_crop_name = f"fold{fold}_fn_{idx+1:02d}_{fn['frame_id']}.jpg"
            cv2.imwrite(str(out_dir / out_crop_name), crop)

    return fn_summary


def main():
    raw_root = PROJECT_ROOT / "docs" / "results" / "raw"
    labels_dir = PROJECT_ROOT / "vision" / "eval" / "labels"
    images_dir = PROJECT_ROOT / "vision" / "eval" / "images"
    qa_report_path = raw_root / "task1_label_qa_report.json"
    scratch_fn_dir = Path("/home/tanmay/.gemini/antigravity-cli/brain/0bc2941e-2229-4873-a339-2c9ba11257b5/scratch/fn_overlays")

    print("[1/3] Computing Recall by Height Bucket across 5 folds...")
    height_bucket_results = analyze_height_buckets(raw_root, labels_dir, images_dir)
    print("      Height Bucket Summary:")
    print("      Bucket      Baseline Recall      Fine-Tuned Recall      Total GTs")
    for b in ["<16px", "16-32px", "32-64px", ">64px"]:
        b_base = height_bucket_results["summary"]["baseline"][b]
        b_ft = height_bucket_results["summary"]["finetuned"][b]
        print(f"      {b:<10}  {b_base['recall']*100:6.2f}% ({b_base['tp_count']}/{b_base['gt_count']})       {b_ft['recall']*100:6.2f}% ({b_ft['tp_count']}/{b_ft['gt_count']})       {b_ft['gt_count']}")

    qa_csv_path = raw_root / "task1_label_qa_report.csv"
    overlap_results = analyze_person_vehicle_overlaps(raw_root, qa_csv_path, labels_dir, images_dir)
    print(f"      Total flagged overlaps: {overlap_results['total_flagged_overlaps']} across {overlap_results['frames_involved']} frames")
    print(f"      Baseline Person Recall on Overlaps:   {overlap_results['baseline_person_recall_on_overlaps']*100:.2f}% ({overlap_results['baseline_detected_count']}/{overlap_results['total_flagged_overlaps']})")
    print(f"      Fine-Tuned Person Recall on Overlaps: {overlap_results['finetuned_person_recall_on_overlaps']*100:.2f}% ({overlap_results['finetuned_detected_count']}/{overlap_results['total_flagged_overlaps']})")

    print(f"\n[3/3] Extracting Top 10 False Negatives per Fold into {scratch_fn_dir}...")
    fn_results = extract_top10_fn_overlays(raw_root, labels_dir, images_dir, scratch_fn_dir)
    for fold in range(1, 6):
        fold_fn = fn_results.get(f"fold_{fold}", {})
        print(f"      Fold {fold}: {fold_fn.get('total_false_negatives', 0)} total FNs; top 10 rendered.")

    # Save comprehensive report
    report_data = {
        "height_bucket_recall": height_bucket_results,
        "person_vehicle_overlap_qa": overlap_results,
        "false_negatives_top10": fn_results
    }
    out_json = raw_root / "task2_error_analysis.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)
    print(f"\n[SAVED] Comprehensive error analysis saved to {out_json}")


if __name__ == "__main__":
    main()
