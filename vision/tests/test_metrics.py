"""
Unit tests for detection evaluation metrics engine (vision/eval/metrics.py).
Tests synthetic box edge cases: IoU math, matching, duplicate handling,
wrong-class confusion, area binning, and average precision calculation.
"""

import math
import pytest
import numpy as np
import sys
import subprocess
from pathlib import Path

# Add vision/eval to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "eval"))
from metrics import (
    box_iou,
    compute_ap,
    match_image_predictions,
    calculate_metrics_for_class,
    perform_error_analysis,
    bootstrap_metric_ci,
)


def test_box_iou_exact_match():
    box = (10.0, 10.0, 50.0, 50.0)
    assert box_iou(box, box) == pytest.approx(1.0)


def test_box_iou_no_overlap():
    b1 = (0.0, 0.0, 10.0, 10.0)
    b2 = (20.0, 20.0, 30.0, 30.0)
    assert box_iou(b1, b2) == pytest.approx(0.0)


def test_box_iou_partial_overlap():
    # b1: area 100 (0,0 to 10,10)
    # b2: area 100 (5,0 to 15,10)
    # intersection: (5,0 to 10,10) -> area 50
    # union: 100 + 100 - 50 = 150
    # iou: 50 / 150 = 1/3
    b1 = (0.0, 0.0, 10.0, 10.0)
    b2 = (5.0, 0.0, 15.0, 10.0)
    assert box_iou(b1, b2) == pytest.approx(1.0 / 3.0)


def test_box_iou_threshold_boundary():
    # Target: IoU just below 0.5 vs just above 0.5
    # For two boxes of width W, height H with horizontal shift S:
    # area1 = 100, area2 = 100
    # inter = (10 - S) * 10 = 100 - 10S
    # union = 200 - (100 - 10S) = 100 + 10S
    # IoU = (100 - 10S) / (100 + 10S)
    # At S = 3.333...: (100 - 33.33) / (100 + 33.33) = 66.67 / 133.33 = 0.5
    # S = 3.2 -> IoU = 68 / 132 = 0.515 (> 0.5)
    # S = 3.5 -> IoU = 65 / 135 = 0.481 (< 0.5)
    b_base = (0.0, 0.0, 10.0, 10.0)
    b_above = (3.2, 0.0, 13.2, 10.0)
    b_below = (3.5, 0.0, 13.5, 10.0)

    iou_above = box_iou(b_base, b_above)
    iou_below = box_iou(b_base, b_below)

    assert iou_above > 0.5
    assert iou_below < 0.5

    gt = [{"box": [0.0, 0.0, 10.0, 10.0], "class": 0}]
    pred_above = [{"box": [3.2, 0.0, 13.2, 10.0], "class": 0, "conf": 0.9}]
    pred_below = [{"box": [3.5, 0.0, 13.5, 10.0], "class": 0, "conf": 0.9}]

    match_above = match_image_predictions(pred_above, gt, iou_threshold=0.5)
    assert match_above["pred_results"][0]["matched"] is True

    match_below = match_image_predictions(pred_below, gt, iou_threshold=0.5)
    assert match_below["pred_results"][0]["matched"] is False
    assert match_below["pred_results"][0]["fp_type"] == "background"


def test_match_perfect():
    gt = [{"box": [10.0, 10.0, 50.0, 50.0], "class": 0}]
    pred = [{"box": [10.0, 10.0, 50.0, 50.0], "class": 0, "conf": 0.95}]

    res = match_image_predictions(pred, gt, iou_threshold=0.5)
    assert len(res["pred_results"]) == 1
    assert res["pred_results"][0]["matched"] is True
    assert res["pred_results"][0]["iou"] == pytest.approx(1.0)
    assert len(res["unmatched_gts"]) == 0


def test_match_one_miss():
    gt = [{"box": [10.0, 10.0, 50.0, 50.0], "class": 0}]
    pred = []

    res = match_image_predictions(pred, gt, iou_threshold=0.5)
    assert len(res["pred_results"]) == 0
    assert len(res["unmatched_gts"]) == 1
    assert res["unmatched_gts"][0]["class"] == 0


def test_match_false_positive_background():
    gt = []
    pred = [{"box": [10.0, 10.0, 50.0, 50.0], "class": 0, "conf": 0.8}]

    res = match_image_predictions(pred, gt, iou_threshold=0.5)
    assert len(res["pred_results"]) == 1
    assert res["pred_results"][0]["matched"] is False
    assert res["pred_results"][0]["fp_type"] == "background"


def test_match_duplicate_prediction():
    gt = [{"box": [10.0, 10.0, 50.0, 50.0], "class": 0}]
    preds = [
        {"box": [10.0, 10.0, 50.0, 50.0], "class": 0, "conf": 0.95},
        {"box": [11.0, 11.0, 50.0, 50.0], "class": 0, "conf": 0.85},
    ]

    res = match_image_predictions(preds, gt, iou_threshold=0.5)
    assert len(res["pred_results"]) == 2
    assert res["pred_results"][0]["matched"] is True
    assert res["pred_results"][0]["fp_type"] is None
    assert res["pred_results"][1]["matched"] is False
    assert res["pred_results"][1]["fp_type"] == "duplicate"


def test_match_wrong_class():
    gt = [{"box": [10.0, 10.0, 50.0, 50.0], "class": 0}]  # person
    pred = [{"box": [10.0, 10.0, 50.0, 50.0], "class": 1, "conf": 0.9}]  # car

    res = match_image_predictions(pred, gt, iou_threshold=0.5)
    assert len(res["pred_results"]) == 1
    assert res["pred_results"][0]["matched"] is False
    assert res["pred_results"][0]["fp_type"] == "wrong_class"
    assert len(res["unmatched_gts"]) == 1


def test_compute_ap():
    # Constant precision = 1.0, recall = 1.0
    recalls = np.array([0.5, 1.0])
    precisions = np.array([1.0, 1.0])
    assert compute_ap(recalls, precisions) == pytest.approx(1.0)

    # Empty
    assert compute_ap(np.array([]), np.array([])) == pytest.approx(0.0)


def test_calculate_metrics_for_class_perfect():
    gts = [
        {"image_id": "img1", "box": [10.0, 10.0, 50.0, 50.0], "class": 0},
        {"image_id": "img2", "box": [20.0, 20.0, 60.0, 60.0], "class": 0},
    ]
    preds = [
        {"image_id": "img1", "box": [10.0, 10.0, 50.0, 50.0], "class": 0, "conf": 0.9},
        {"image_id": "img2", "box": [20.0, 20.0, 60.0, 60.0], "class": 0, "conf": 0.85},
    ]

    metrics = calculate_metrics_for_class(preds, gts, target_class=0)
    assert metrics["n_gt"] == 2
    assert metrics["n_pred"] == 2
    assert metrics["precision"] == pytest.approx(1.0)
    assert metrics["recall"] == pytest.approx(1.0)
    assert metrics["f1"] == pytest.approx(1.0)
    assert metrics["ap50"] == pytest.approx(1.0)
    assert metrics["ap50_95"] == pytest.approx(1.0)


def test_perform_error_analysis():
    # 4 classes: 0, 1, 2, 3 + background (index 4)
    # img1: 1 person GT (small: 20x20 = 400 px^2), matched
    # img2: 1 car GT (medium: 50x50 = 2500 px^2), missed (FN)
    # img3: 1 truck GT (large: 120x120 = 14400 px^2), missed (FN)
    # img4: no GT, 1 person pred (FP background)
    gts = [
        {"image_id": "img1", "box": [10.0, 10.0, 30.0, 30.0], "class": 0},
        {"image_id": "img2", "box": [100.0, 100.0, 150.0, 150.0], "class": 1},
        {"image_id": "img3", "box": [200.0, 200.0, 320.0, 320.0], "class": 2},
    ]
    preds = [
        {"image_id": "img1", "box": [10.0, 10.0, 30.0, 30.0], "class": 0, "conf": 0.9},
        {"image_id": "img4", "box": [50.0, 50.0, 70.0, 70.0], "class": 0, "conf": 0.7},
    ]

    err = perform_error_analysis(preds, gts, num_classes=4, image_width=1920, image_height=1080)

    # Check confusion matrix shape: (5, 5)
    cm = np.array(err["confusion_matrix"])
    assert cm.shape == (5, 5)

    # img1: GT 0, Pred 0 -> cm[0, 0] == 1
    assert cm[0, 0] == 1
    # img2: GT 1, Missed -> cm[1, 4] == 1
    assert cm[1, 4] == 1
    # img3: GT 2, Missed -> cm[2, 4] == 1
    assert cm[2, 4] == 1
    # img4: Pred 0, Background GT -> cm[4, 0] == 1
    assert cm[4, 0] == 1

    # FP breakdown
    assert err["fp_breakdown"]["background"] == 1
    assert err["fp_breakdown"]["duplicate"] == 0
    assert err["fp_breakdown"]["wrong_class"] == 0

    # FN area categorization
    assert err["fn_by_area"]["small"] == 0  # matched, not FN
    assert err["fn_by_area"]["medium"] == 1  # 50x50 = 2500
    assert err["fn_by_area"]["large"] == 1   # 120x120 = 14400


def test_eval_detection_refuses_without_verified(tmp_path):
    """Verify eval_detection.py exits with code 2 when vision/eval/labels/VERIFIED is missing."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    script_path = repo_root / "vision" / "eval" / "eval_detection.py"

    proc = subprocess.run(
        [sys.executable, str(script_path), "--labels-dir", str(tmp_path)],
        cwd=str(repo_root),
        capture_output=True,
        text=True
    )
    assert proc.returncode == 2
    assert "STRICT GATE REJECTION" in proc.stderr


def test_bootstrap_metric_ci():
    """Test 95% bootstrap CI calculation produces valid bounds [0, 1] containing the mean."""
    image_ids = [f"frame_{i}" for i in range(10)]
    # Perfect detection on half the frames
    preds = [{"image_id": f"frame_{i}", "class": 0, "conf": 0.9, "box": [0.1, 0.1, 0.2, 0.2]} for i in range(5)]
    gts = [{"image_id": f"frame_{i}", "class": 0, "box": [0.1, 0.1, 0.2, 0.2]} for i in range(10)]

    ci_res = bootstrap_metric_ci(preds, gts, image_ids, target_class=0, n_bootstraps=100, seed=42)

    assert "ap50_ci" in ci_res
    assert "recall_ci" in ci_res
    ap_low, ap_high = ci_res["ap50_ci"]
    rec_low, rec_high = ci_res["recall_ci"]

    assert 0.0 <= ap_low <= ap_high <= 1.0
    assert 0.0 <= rec_low <= rec_high <= 1.0
    assert ap_low <= ci_res["ap50_mean"] <= ap_high
    assert rec_low <= ci_res["recall_mean"] <= rec_high


