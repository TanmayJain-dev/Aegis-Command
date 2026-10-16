"""
Unit tests for the raw-first benchmarking pipeline.
Tests compute_tables.py and verify_benchmarks.py using synthetic raw predictions.
"""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "vision" / "eval"))

from compute_tables import compute_metrics_for_run, format_markdown_row
from verify_benchmarks import verify_benchmarks, extract_floats
from finalize_labels import compute_labels_sha256


@pytest.fixture
def synthetic_raw_run(tmp_path):
    """
    Creates a temporary valid raw run directory with predictions.json and run_meta.json.
    """
    labels_dir = PROJECT_ROOT / "vision" / "eval" / "labels"
    current_sha = compute_labels_sha256(labels_dir)

    raw_dir = tmp_path / "raw" / "yolov8s_640px_all"
    raw_dir.mkdir(parents=True)

    # Pick 2 actual frames from labels dir
    label_files = sorted(labels_dir.glob("*.txt"))
    assert len(label_files) >= 2
    f0 = label_files[0].stem
    f1 = label_files[1].stem

    predictions = [
        {
            "frame_id": f0,
            "image_id": f0,
            "class_id": 0,
            "class": 0,
            "conf": 0.85,
            "bbox_xywh_norm": [0.5, 0.5, 0.1, 0.2],
            "box": [0.45, 0.4, 0.55, 0.6]
        },
        {
            "frame_id": f1,
            "image_id": f1,
            "class_id": 0,
            "class": 0,
            "conf": 0.72,
            "bbox_xywh_norm": [0.3, 0.3, 0.05, 0.1],
            "box": [0.275, 0.25, 0.325, 0.35]
        }
    ]

    run_meta = {
        "run_id": "yolov8s_640px_all",
        "command": "python3 eval_detection.py --save-raw",
        "git_commit": "abcdef123456",
        "device": "cpu",
        "torch_version": "2.14.1",
        "ultralytics_version": "8.4.175",
        "imgsz": 640,
        "weights": "yolov8s.pt",
        "timestamp": "2026-10-13T18:00:00Z",
        "wall_seconds": 2.5,
        "labels_sha256": current_sha,
        "num_frames": 2,
        "split": "all",
        "fold": 1,
        "latency_mean_ms": 1250.0,
        "latency_p50_ms": 1240.0,
        "latency_p95_ms": 1260.0
    }

    with open(raw_dir / "predictions.json", "w", encoding="utf-8") as f:
        json.dump(predictions, f)
    with open(raw_dir / "run_meta.json", "w", encoding="utf-8") as f:
        json.dump(run_meta, f)

    return raw_dir


def test_compute_metrics_synthetic(synthetic_raw_run):
    labels_dir = PROJECT_ROOT / "vision" / "eval" / "labels"
    res = compute_metrics_for_run(synthetic_raw_run, labels_dir=labels_dir, n_bootstraps=20, seed=42)

    assert res["run_id"] == "yolov8s_640px_all"
    assert res["imgsz"] == 640
    assert "person" in res
    assert "truck" in res
    assert "car" in res
    assert "bootstrap_ci_95_person" in res
    assert isinstance(res["person"]["ap50"], float)
    assert len(res["bootstrap_ci_95_person"]["ap50_ci"]) == 2

    # Check markdown formatter
    md_row = format_markdown_row(res)
    assert "**yolov8s @ 640px**" in md_row
    assert "1250.0 ms" in md_row


def test_verify_benchmarks_valid_match(tmp_path, synthetic_raw_run):
    labels_dir = PROJECT_ROOT / "vision" / "eval" / "labels"
    res = compute_metrics_for_run(synthetic_raw_run, labels_dir=labels_dir, n_bootstraps=20, seed=42)
    md_row = format_markdown_row(res)

    md_content = f"""# Test Benchmarks
## Planned Zero-Shot Bake-Off Matrix (155 Frames)

| Model Architecture & Resolution | Target Device / Backend | Person AP50 [95% Bootstrap CI] | Person Recall [95% Bootstrap CI] | Person P @ 0.25 | Person R @ 0.25 | Person P @ 0.35 | Person R @ 0.35 | Person FP / frame | Truck AP50 | Car AP50 ($n=58$, unreliable) | Latency (ms/frame) |
|---|---|---|---|---|---|---|---|---|---|---|---|
{md_row}
"""
    md_file = tmp_path / "BENCHMARKS.md"
    md_file.write_text(md_content, encoding="utf-8")

    raw_root = synthetic_raw_run.parent
    ok = verify_benchmarks(benchmarks_path=md_file, raw_root=raw_root, labels_dir=labels_dir)
    assert ok is True


def test_verify_benchmarks_missing_raw_fails(tmp_path):
    labels_dir = PROJECT_ROOT / "vision" / "eval" / "labels"
    md_content = """# Test Benchmarks
## Planned Zero-Shot Bake-Off Matrix (155 Frames)

| Model Architecture & Resolution | Target Device / Backend | Person AP50 [95% Bootstrap CI] | Person Recall [95% Bootstrap CI] | Person P @ 0.25 | Person R @ 0.25 | Person P @ 0.35 | Person R @ 0.35 | Person FP / frame | Truck AP50 | Car AP50 ($n=58$, unreliable) | Latency (ms/frame) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **YOLOv8n @ 640px** | CPU | `0.550 [0.500, 0.600]` | `0.600 [0.550, 0.650]` | 0.700 | 0.600 | 0.750 | 0.550 | 0.250 | 0.600 | 0.400* | 1200.0 ms (CPU) |
"""
    md_file = tmp_path / "BENCHMARKS.md"
    md_file.write_text(md_content, encoding="utf-8")

    empty_raw_root = tmp_path / "raw"
    empty_raw_root.mkdir()

    ok = verify_benchmarks(benchmarks_path=md_file, raw_root=empty_raw_root, labels_dir=labels_dir)
    assert ok is False


def test_verify_benchmarks_mismatch_fails(tmp_path, synthetic_raw_run):
    labels_dir = PROJECT_ROOT / "vision" / "eval" / "labels"
    res = compute_metrics_for_run(synthetic_raw_run, labels_dir=labels_dir, n_bootstraps=20, seed=42)
    md_row = format_markdown_row(res)

    # Tamper with the row by replacing AP50 with an invented 0.999
    tampered_row = md_row.replace(f"`{res['person']['ap50']:.3f}", "`0.999")

    md_content = f"""# Test Benchmarks
## Planned Zero-Shot Bake-Off Matrix (155 Frames)

| Model Architecture & Resolution | Target Device / Backend | Person AP50 [95% Bootstrap CI] | Person Recall [95% Bootstrap CI] | Person P @ 0.25 | Person R @ 0.25 | Person P @ 0.35 | Person R @ 0.35 | Person FP / frame | Truck AP50 | Car AP50 ($n=58$, unreliable) | Latency (ms/frame) |
|---|---|---|---|---|---|---|---|---|---|---|---|
{tampered_row}
"""
    md_file = tmp_path / "BENCHMARKS.md"
    md_file.write_text(md_content, encoding="utf-8")

    raw_root = synthetic_raw_run.parent
    ok = verify_benchmarks(benchmarks_path=md_file, raw_root=raw_root, labels_dir=labels_dir)
    assert ok is False


def test_verify_benchmarks_unrun_passes(tmp_path):
    labels_dir = PROJECT_ROOT / "vision" / "eval" / "labels"
    md_content = """# Test Benchmarks
## Planned Zero-Shot Bake-Off Matrix (155 Frames)

| Model Architecture & Resolution | Target Device / Backend | Status | Raw Predictions Source |
|---|---|---|---|
| **YOLOv8n @ 640px** | Local CPU | `NOT RUN` | None |
| **YOLOv8s @ 640px** | Local CPU | `NOT RUN` | None |
"""
    md_file = tmp_path / "BENCHMARKS.md"
    md_file.write_text(md_content, encoding="utf-8")

    empty_raw = tmp_path / "raw"
    empty_raw.mkdir()

    ok = verify_benchmarks(benchmarks_path=md_file, raw_root=empty_raw, labels_dir=labels_dir)
    assert ok is True


def test_demo_weights_provenance():
    """Asserts that uav-alpha meta has verified weights, generator commit, and body hash."""
    uav_json = PROJECT_ROOT / "frontend" / "public" / "feeds" / "uav-alpha" / "detections.json"
    manifest_json = PROJECT_ROOT / "docs" / "results" / "raw" / "checkpoints_manifest.json"

    with open(uav_json, "r", encoding="utf-8") as f:
        uav_data = json.load(f)
    meta = uav_data.get("meta", {})

    if meta.get("evaluated"):
        assert manifest_json.exists(), "checkpoints_manifest.json must exist when feed is evaluated"
        with open(manifest_json, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        # 1. meta.weights_sha256 is in checkpoints_manifest.json
        weights_sha = meta.get("weights_sha256")
        assert weights_sha in manifest.values(), (
            f"Weights SHA-256 {weights_sha} not found in {manifest_json}"
        )

        # 2. meta.generator_commit is an actual commit in git log (verify with git cat-file -e <commit>^{commit})
        generator_commit = meta.get("generator_commit")
        assert generator_commit, "meta.generator_commit must be present in evaluated feed"
        git_check = subprocess.run(
            ["git", "cat-file", "-e", f"{generator_commit}^{{commit}}"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
        )
        assert git_check.returncode == 0, (
            f"meta.generator_commit {generator_commit} does not exist in git history"
        )

        # 3. meta.weights_sha256 is NOT the sha of yolov8s.pt when meta.model claims the demo checkpoint
        YOLOV8S_SHA256 = "1f47a78bf100391c2a140b7ac73a1caae18c32779be7d310658112f7ac9aa78a"
        if "demo" in meta.get("model", "").lower():
            assert weights_sha != YOLOV8S_SHA256, (
                f"Demo model claims {meta.get('model')} but uses stock yolov8s.pt weights SHA-256"
            )

        # 4. meta.detections_sha256 matches actual hash of detection body
        body = {k: v for k, v in uav_data.items() if k != "meta"}
        computed_body_sha = hashlib.sha256(json.dumps(body, sort_keys=True).encode("utf-8")).hexdigest()
        assert meta.get("detections_sha256") == computed_body_sha, (
            f"meta.detections_sha256 {meta.get('detections_sha256')} does not match computed body hash {computed_body_sha}"
        )


def test_detection_bodies_change_with_weights():
    """Asserts detection bodies change when weights change (comparing demo output to stock yolov8s output)."""
    uav_json = PROJECT_ROOT / "frontend" / "public" / "feeds" / "uav-alpha" / "detections.json"
    with open(uav_json, "r", encoding="utf-8") as f:
        uav_data = json.load(f)

    meta = uav_data.get("meta", {})
    body = {k: v for k, v in uav_data.items() if k != "meta"}
    current_body_sha = hashlib.sha256(json.dumps(body, sort_keys=True).encode("utf-8")).hexdigest()

    # Known SHA-256 of stock yolov8s.pt zero-shot body from commit 5ebf46a
    STOCK_YOLOV8S_BODY_SHA256 = "7b52c6a7802c74d9e5ee6d3d8c2f87e3c18ccca92ae8fa0f918e28043c62f9b1"

    assert current_body_sha != STOCK_YOLOV8S_BODY_SHA256, (
        f"Detection bodies in {uav_json} are byte-identical to the stock yolov8s.pt output ({STOCK_YOLOV8S_BODY_SHA256}). "
        "The model weights were changed but the detection bodies were not regenerated."
    )
    if "detections_sha256" in meta:
        assert meta["detections_sha256"] != STOCK_YOLOV8S_BODY_SHA256

