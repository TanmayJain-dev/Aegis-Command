"""
Detection evaluation metrics engine for Aegis Command.
Computes IoU, Precision, Recall, F1, AP50, mAP50-95, confusion matrices,
false-positive breakdowns, and false-negative area categorizations.
"""

from typing import List, Dict, Tuple, Any, Optional
import numpy as np

def box_iou(b1: Tuple[float, float, float, float], b2: Tuple[float, float, float, float]) -> float:
    """
    Computes Intersection over Union (IoU) between two boxes [x1, y1, x2, y2].
    """
    x1 = max(b1[0], b2[0])
    y1 = max(b1[1], b2[1])
    x2 = min(b1[2], b2[2])
    y2 = min(b1[3], b2[3])

    inter_w = max(0.0, x2 - x1)
    inter_h = max(0.0, y2 - y1)
    inter_area = inter_w * inter_h

    area1 = max(0.0, b1[2] - b1[0]) * max(0.0, b1[3] - b1[1])
    area2 = max(0.0, b2[2] - b2[0]) * max(0.0, b2[3] - b2[1])

    union_area = area1 + area2 - inter_area
    if union_area <= 0:
        return 0.0

    return inter_area / union_area

def compute_ap(recalls: np.ndarray, precisions: np.ndarray) -> float:
    """
    Computes Average Precision (AP) using standard continuous interpolation (area under PR curve).
    """
    if len(recalls) == 0:
        return 0.0

    # Append sentinel values
    mrec = np.concatenate(([0.0], recalls, [1.0]))
    mpre = np.concatenate(([0.0], precisions, [0.0]))

    # Compute maximum precision to the right
    for i in range(len(mpre) - 2, -1, -1):
        mpre[i] = max(mpre[i], mpre[i + 1])

    # Find points where recall changes
    i = np.where(mrec[1:] != mrec[:-1])[0]
    ap = np.sum((mrec[i + 1] - mrec[i]) * mpre[i + 1])
    return float(ap)

def match_image_predictions(
    preds: List[Dict[str, Any]],
    gts: List[Dict[str, Any]],
    iou_threshold: float = 0.5
) -> Dict[str, Any]:
    """
    Matches predictions to ground truths for a single image at a specific IoU threshold.
    preds: list of dicts with {"box": [x1, y1, x2, y2], "class": int, "conf": float}
    gts: list of dicts with {"box": [x1, y1, x2, y2], "class": int}
    """
    # Sort predictions by confidence descending
    sorted_preds = sorted(preds, key=lambda p: p.get("conf", 1.0), reverse=True)

    gt_matched = [False] * len(gts)
    pred_results = []

    for pred in sorted_preds:
        best_iou = 0.0
        best_gt_idx = -1

        # Match only with GT of the same class
        for gt_idx, gt in enumerate(gts):
            if pred["class"] == gt["class"]:
                iou = box_iou(pred["box"], gt["box"])
                if iou > best_iou:
                    best_iou = iou
                    best_gt_idx = gt_idx

        if best_iou >= iou_threshold and best_gt_idx >= 0:
            if not gt_matched[best_gt_idx]:
                gt_matched[best_gt_idx] = True
                pred_results.append({
                    "pred": pred,
                    "matched": True,
                    "gt_idx": best_gt_idx,
                    "iou": best_iou,
                    "fp_type": None
                })
            else:
                # Duplicate detection on already matched ground truth
                pred_results.append({
                    "pred": pred,
                    "matched": False,
                    "gt_idx": best_gt_idx,
                    "iou": best_iou,
                    "fp_type": "duplicate"
                })
        else:
            # Check if this FP overlaps with any GT of another class (confusion) or background
            cross_iou = 0.0
            cross_gt_class = None
            for gt in gts:
                iou = box_iou(pred["box"], gt["box"])
                if iou > cross_iou:
                    cross_iou = iou
                    cross_gt_class = gt["class"]

            if cross_iou >= 0.1 and cross_gt_class is not None and cross_gt_class != pred["class"]:
                fp_type = "wrong_class"
            else:
                fp_type = "background"

            pred_results.append({
                "pred": pred,
                "matched": False,
                "gt_idx": -1,
                "iou": best_iou,
                "fp_type": fp_type
            })

    unmatched_gts = [gt for idx, gt in enumerate(gts) if not gt_matched[idx]]

    return {
        "pred_results": pred_results,
        "unmatched_gts": unmatched_gts,
        "num_gts": len(gts)
    }

def calculate_metrics_for_class(
    all_preds: List[Dict[str, Any]],
    all_gts: List[Dict[str, Any]],
    target_class: int,
    iou_thresholds: Optional[List[float]] = None
) -> Dict[str, Any]:
    """
    Computes Precision, Recall, F1, AP50, and AP50-95 for a specific class across all frames.
    """
    if iou_thresholds is None:
        iou_thresholds = [round(x, 2) for x in np.arange(0.5, 1.0, 0.05)]

    # Filter by class
    class_preds = [p for p in all_preds if p["class"] == target_class]
    class_gts = [g for g in all_gts if g["class"] == target_class]

    n_gt = len(class_gts)
    n_pred = len(class_preds)

    if n_gt == 0:
        return {
            "n_gt": 0,
            "n_pred": n_pred,
            "tp": 0,
            "fp": n_pred,
            "precision": 0.0 if n_pred > 0 else 1.0,
            "recall": 1.0,
            "f1": 0.0,
            "ap50": 0.0,
            "ap50_95": 0.0,
        }

    if n_pred == 0:
        return {
            "n_gt": n_gt,
            "n_pred": 0,
            "tp": 0,
            "fp": 0,
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "ap50": 0.0,
            "ap50_95": 0.0,
        }

    # Sort predictions by confidence descending
    sorted_preds = sorted(class_preds, key=lambda p: p.get("conf", 1.0), reverse=True)

    # Pre-group ground truths by image_id for O(1) frame lookup
    gts_by_image = {}
    for g in class_gts:
        gts_by_image.setdefault(g.get("image_id", ""), []).append(g)

    ap_per_threshold = []

    for iou_thresh in iou_thresholds:
        tp = np.zeros(n_pred)
        fp = np.zeros(n_pred)

        # Track which GTs were matched per image
        image_gt_matched = {}

        for p_idx, pred in enumerate(sorted_preds):
            img_id = pred.get("image_id", "")
            img_gts = gts_by_image.get(img_id, [])
            if not img_gts:
                fp[p_idx] = 1
                continue

            if img_id not in image_gt_matched:
                image_gt_matched[img_id] = [False] * len(img_gts)

            best_iou = 0.0
            best_gt_idx = -1

            for g_idx, gt in enumerate(img_gts):
                iou = box_iou(pred["box"], gt["box"])
                if iou > best_iou:
                    best_iou = iou
                    best_gt_idx = g_idx

            if best_iou >= iou_thresh and best_gt_idx >= 0:
                if not image_gt_matched[img_id][best_gt_idx]:
                    tp[p_idx] = 1
                    image_gt_matched[img_id][best_gt_idx] = True
                else:
                    fp[p_idx] = 1
            else:
                fp[p_idx] = 1

        cum_tp = np.cumsum(tp)
        cum_fp = np.cumsum(fp)

        recalls = cum_tp / n_gt
        precisions = cum_tp / (cum_tp + cum_fp)

        ap = compute_ap(recalls, precisions)
        ap_per_threshold.append(ap)

    # Metrics at IoU 0.5
    ap50 = ap_per_threshold[0]
    ap50_95 = float(np.mean(ap_per_threshold))

    # Single-threshold summary metrics at IoU 0.5
    # Evaluate at threshold 0.5 on the whole set
    img_gt_matched = {}
    tp_count = 0
    fp_count = 0

    for pred in sorted_preds:
        img_id = pred.get("image_id", "")
        img_gts = gts_by_image.get(img_id, [])
        if not img_gts:
            fp_count += 1
            continue

        if img_id not in img_gt_matched:
            img_gt_matched[img_id] = [False] * len(img_gts)

        best_iou = 0.0
        best_gt_idx = -1
        for g_idx, gt in enumerate(img_gts):
            iou = box_iou(pred["box"], gt["box"])
            if iou > best_iou:
                best_iou = iou
                best_gt_idx = g_idx

        if best_iou >= 0.5 and best_gt_idx >= 0 and not img_gt_matched[img_id][best_gt_idx]:
            tp_count += 1
            img_gt_matched[img_id][best_gt_idx] = True
        else:
            fp_count += 1

    precision = tp_count / (tp_count + fp_count) if (tp_count + fp_count) > 0 else 0.0
    recall = tp_count / n_gt if n_gt > 0 else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "n_gt": n_gt,
        "n_pred": n_pred,
        "tp": tp_count,
        "fp": fp_count,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "ap50": round(ap50, 4),
        "ap50_95": round(ap50_95, 4),
    }

def perform_error_analysis(
    all_preds: List[Dict[str, Any]],
    all_gts: List[Dict[str, Any]],
    num_classes: int = 4,
    image_width: int = 1920,
    image_height: int = 1080
) -> Dict[str, Any]:
    """
    Computes confusion matrix, false-positive breakdown, and false-negative area categorizations.
    Area definitions (standard COCO in pixel^2):
      small: < 32^2 = 1024
      medium: 32^2 to 96^2 = 1024 to 9216
      large: > 96^2 = 9216
    """
    # Confusion matrix of size (num_classes + 1) x (num_classes + 1)
    # rows: Ground Truth (0..num_classes-1, last row is background)
    # cols: Prediction (0..num_classes-1, last col is background/miss)
    cm = np.zeros((num_classes + 1, num_classes + 1), dtype=int)

    fp_breakdown = {
        "background": 0,
        "wrong_class": 0,
        "duplicate": 0
    }

    fn_by_area = {
        "small": 0,   # area < 1024
        "medium": 0,  # 1024 <= area <= 9216
        "large": 0    # area > 9216
    }

    # Group by image
    all_images = set([p.get("image_id", "") for p in all_preds] + [g.get("image_id", "") for g in all_gts])

    for img_id in all_images:
        preds = [p for p in all_preds if p.get("image_id", "") == img_id]
        gts = [g for g in all_gts if g.get("image_id", "") == img_id]

        matched = match_image_predictions(preds, gts, iou_threshold=0.5)

        for pr in matched["pred_results"]:
            p_cls = pr["pred"]["class"]
            if pr["matched"]:
                gt_cls = gts[pr["gt_idx"]]["class"]
                cm[gt_cls, p_cls] += 1
            else:
                fp_type = pr.get("fp_type", "background")
                fp_breakdown[fp_type] += 1
                # Prediction with no GT is mapped from background row (num_classes)
                cm[num_classes, p_cls] += 1

        for gt in matched["unmatched_gts"]:
            gt_cls = gt["class"]
            # Missed GT mapped to background column (num_classes)
            cm[gt_cls, num_classes] += 1

            # Categorize FN by area
            b = gt["box"]
            w = max(0.0, b[2] - b[0])
            h = max(0.0, b[3] - b[1])
            # If coordinates are normalized in [0, 1], scale to pixel dimensions
            if b[2] <= 1.0 and b[3] <= 1.0:
                area = (w * image_width) * (h * image_height)
            else:
                area = w * h

            if area < 1024:
                fn_by_area["small"] += 1
            elif area <= 9216:
                fn_by_area["medium"] += 1
            else:
                fn_by_area["large"] += 1

    return {
        "confusion_matrix": cm.tolist(),
        "fp_breakdown": fp_breakdown,
        "fn_by_area": fn_by_area
    }


def bootstrap_metric_ci(
    all_preds: List[Dict[str, Any]],
    all_gts: List[Dict[str, Any]],
    image_ids: List[str],
    target_class: int = 0,
    n_bootstraps: int = 1000,
    seed: int = 42,
    alpha: float = 0.05
) -> Dict[str, Any]:
    """
    Computes 95% bootstrap confidence intervals for AP50 and Recall by resampling whole frames with replacement.
    """
    rng = np.random.RandomState(seed)
    n_images = len(image_ids)
    if n_images == 0:
        return {
            "ap50_ci": (0.0, 0.0),
            "recall_ci": (0.0, 0.0),
            "ap50_mean": 0.0,
            "recall_mean": 0.0
        }

    preds_by_img = {}
    for p in all_preds:
        if p.get("class") == target_class:
            preds_by_img.setdefault(p.get("image_id", ""), []).append(p)

    gts_by_img = {}
    for g in all_gts:
        if g.get("class") == target_class:
            gts_by_img.setdefault(g.get("image_id", ""), []).append(g)

    ap50_samples = []
    recall_samples = []

    for b in range(n_bootstraps):
        sampled_indices = rng.choice(n_images, size=n_images, replace=True)
        sampled_preds = []
        sampled_gts = []

        for new_idx, idx in enumerate(sampled_indices):
            orig_id = image_ids[idx]
            virtual_id = f"virtual_{new_idx}"
            for p in preds_by_img.get(orig_id, []):
                p_copy = dict(p)
                p_copy["image_id"] = virtual_id
                sampled_preds.append(p_copy)
            for g in gts_by_img.get(orig_id, []):
                g_copy = dict(g)
                g_copy["image_id"] = virtual_id
                sampled_gts.append(g_copy)

        m = calculate_metrics_for_class(sampled_preds, sampled_gts, target_class=target_class, iou_thresholds=[0.5])
        ap50_samples.append(m["ap50"])
        recall_samples.append(m["recall"])

    lower_p = (alpha / 2.0) * 100.0
    upper_p = (1.0 - alpha / 2.0) * 100.0

    return {
        "ap50_ci": (round(float(np.percentile(ap50_samples, lower_p)), 4), round(float(np.percentile(ap50_samples, upper_p)), 4)),
        "recall_ci": (round(float(np.percentile(recall_samples, lower_p)), 4), round(float(np.percentile(recall_samples, upper_p)), 4)),
        "ap50_mean": round(float(np.mean(ap50_samples)), 4),
        "recall_mean": round(float(np.mean(recall_samples)), 4)
    }

