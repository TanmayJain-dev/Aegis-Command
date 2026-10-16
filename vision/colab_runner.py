#!/usr/bin/env python3
"""
Aegis Command - Autonomous Colab GPU Pipeline Runner.

Orchestrates headless execution on Google Colab:
- Phase 1: Environment bootstrap & video frame extraction
- Phase 2: Zero-shot model bake-off (YOLOv8s/m/l at 960 & 1280, plus SAHI)
- Phase 3: Unified feed detection generation (uav-alpha, cctv-bravo, bodycam-charlie)
- Phase 4: 5-Fold contiguous holdout fine-tuning (50 epochs, temporal buffer)
- Phase 5: Verification & artifact packaging
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


def log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def run_cmd(cmd, cwd=None):
    log(f"CMD: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    res = subprocess.run(cmd, shell=isinstance(cmd, str), cwd=cwd, check=True)
    return res


def bootstrap_environment(repo_dir: Path):
    log("=== PHASE 1: BOOTSTRAP ENVIRONMENT ===")

    # 1. Verify GPU
    try:
        import torch
        assert torch.cuda.is_available(), "CUDA is not available!"
        device_name = torch.cuda.get_device_name(0)
        log(f"CUDA Available: True | Device: {device_name}")
    except Exception as e:
        log(f"WARNING / ERROR on CUDA check: {e}")

    # 2. Check repository
    if not repo_dir.exists():
        log(f"Cloning repo into {repo_dir}...")
        run_cmd(["git", "clone", "https://github.com/TanmayJain-dev/Aegis-Command.git", str(repo_dir)])
        run_cmd(["git", "checkout", "feat/detection-v3"], cwd=str(repo_dir))
    else:
        log(f"Repository exists at {repo_dir}. Pulling latest on feat/detection-v3...")
        run_cmd(["git", "checkout", "feat/detection-v3"], cwd=str(repo_dir))
        try:
            run_cmd(["git", "pull", "origin", "feat/detection-v3"], cwd=str(repo_dir))
        except Exception as e:
            log(f"git pull warning: {e}")

    # 3. Extract uploaded feed videos if available
    video_archive = Path("/content/feed_videos.tar.gz")
    if video_archive.exists():
        log(f"Extracting {video_archive} into {repo_dir}...")
        run_cmd(["tar", "-xzf", str(video_archive), "-C", str(repo_dir)])
    else:
        log(f"Note: {video_archive} not found in /content, relying on existing repo files.")

    # 4. Extract 155 evaluation frames if missing
    os.chdir(str(repo_dir))
    sys.path.insert(0, str(repo_dir))
    sys.path.insert(0, str(repo_dir / "vision" / "eval"))
    sys.path.insert(0, str(repo_dir / "scripts"))

    images_dir = repo_dir / "vision" / "eval" / "images"
    existing_images = list(images_dir.glob("*.jpg")) if images_dir.exists() else []
    if len(existing_images) < 155:
        drone_video = repo_dir / "vision" / "source" / "drone_feed.mp4"
        assert drone_video.exists(), f"Source video {drone_video} missing!"
        log(f"Extracting 155 evaluation frames from {drone_video}...")
        from vision.eval.sample_frames import sample_frames
        sample_frames(video_path=str(drone_video), out_dir=str(images_dir))
    else:
        log(f"Evaluation frames verified ({len(existing_images)} frames present).")

    # 5. Cryptographic certification gate
    from vision.eval.eval_detection import check_verification_gate
    from vision.eval.finalize_labels import compute_labels_sha256
    labels_dir = repo_dir / "vision" / "eval" / "labels"
    check_verification_gate(labels_dir)
    labels_sha = compute_labels_sha256(labels_dir)
    log(f"Ground truth labels verified! SHA-256: {labels_sha}")

    # 6. Install required vision packages
    try:
        import ultralytics
        import sahi
    except ImportError:
        log("Installing ultralytics, sahi, albumentations...")
        run_cmd([sys.executable, "-m", "pip", "install", "-q", "ultralytics", "sahi", "albumentations"])
        import ultralytics
        import sahi

    log("Bootstrap complete.")


def run_bakeoff(repo_dir: Path):
    log("=== PHASE 2: ZERO-SHOT MODEL BAKEOFF & SAHI ===")
    os.chdir(str(repo_dir))
    from vision.eval.eval_detection import run_evaluation
    from sahi import AutoDetectionModel
    from sahi.predict import get_sliced_prediction
    from vision.eval.finalize_labels import compute_labels_sha256

    CONFIGURATIONS = [
        ("yolov8s.pt", 960),
        ("yolov8s.pt", 1280),
        ("yolov8m.pt", 960),
        ("yolov8m.pt", 1280),
        ("yolov8l.pt", 960),
        ("yolov8l.pt", 1280),
    ]

    for model_name, imgsz in CONFIGURATIONS:
        stem = Path(model_name).stem
        run_id = f"{stem}_{imgsz}px_all"
        log(f"Evaluating {model_name} @ {imgsz}px (run_id: {run_id})...")
        run_evaluation(
            images_dir="vision/eval/images",
            labels_dir="vision/eval/labels",
            model_path=model_name,
            imgsz=imgsz,
            device="cuda:0",
            save_raw=True,
            raw_root="docs/results/raw",
            run_id=run_id
        )

    # SAHI Sliced Evaluation with yolov8m
    log("Evaluating SAHI with yolov8m (slice=640x640, overlap=0.2)...")
    detection_model = AutoDetectionModel.from_pretrained(
        model_type="yolov8",
        model_path="yolov8m.pt",
        confidence_threshold=0.001,
        device="cuda:0"
    )

    images_dir = repo_dir / "vision" / "eval" / "images"
    labels_path = repo_dir / "vision" / "eval" / "labels"
    images = sorted(list(images_dir.glob("*.jpg")) + list(images_dir.glob("*.png")))
    sahi_raw_predictions = []
    latencies_ms = []

    t_start = time.perf_counter()
    COCO_TO_EVAL = {0: 0, 2: 1, 7: 2, 5: 3}

    for img in images:
        t0 = time.perf_counter()
        result = get_sliced_prediction(
            str(img),
            detection_model,
            slice_height=640,
            slice_width=640,
            overlap_height_ratio=0.2,
            overlap_width_ratio=0.2,
            verbose=0
        )
        t1 = time.perf_counter()
        latencies_ms.append((t1 - t0) * 1000.0)

        for obj in result.object_prediction_list:
            cid = obj.category.id
            if cid in COCO_TO_EVAL:
                bbox = obj.bbox.to_xyxy()
                x1, y1, x2, y2 = bbox[0] / 1920.0, bbox[1] / 1080.0, bbox[2] / 1920.0, bbox[3] / 1080.0
                sahi_raw_predictions.append({
                    "frame_id": img.stem,
                    "image_id": img.stem,
                    "class_id": COCO_TO_EVAL[cid],
                    "class": COCO_TO_EVAL[cid],
                    "conf": round(float(obj.score.value), 6),
                    "box": [round(x1, 6), round(y1, 6), round(x2, 6), round(y2, 6)]
                })

    total_wall = time.perf_counter() - t_start
    sahi_dir = repo_dir / "docs" / "results" / "raw" / "sahi_yolov8m_640px_all"
    sahi_dir.mkdir(parents=True, exist_ok=True)

    sahi_meta = {
        "run_id": "sahi_yolov8m_640px_all",
        "command": "SAHI get_sliced_prediction yolov8m.pt (640x640 slices, overlap=0.2)",
        "device": "cuda:0",
        "imgsz": 640,
        "weights": "yolov8m.pt",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "wall_seconds": round(total_wall, 2),
        "labels_sha256": compute_labels_sha256(labels_path),
        "num_frames": len(images),
        "split": "all",
        "fold": 1,
        "latency_mean_ms": round(float(sum(latencies_ms) / len(latencies_ms)), 2),
        "latency_p50_ms": round(float(sorted(latencies_ms)[len(latencies_ms)//2]), 2)
    }

    with open(sahi_dir / "predictions.json", "w", encoding="utf-8") as f:
        json.dump(sahi_raw_predictions, f, indent=2)
    with open(sahi_dir / "run_meta.json", "w", encoding="utf-8") as f:
        json.dump(sahi_meta, f, indent=2)

    log(f"Saved {len(sahi_raw_predictions)} SAHI predictions to {sahi_dir}")


def run_feed_detections(repo_dir: Path):
    log("=== PHASE 3: UNIFIED FEED DETECTION GENERATION ===")
    os.chdir(str(repo_dir))
    feeds = [
        ("uav-alpha", "true"),
        ("cctv-bravo", "false"),
        ("bodycam-charlie", "false"),
    ]
    for feed_name, evaluated_flag in feeds:
        log(f"Generating detections for {feed_name} (evaluated: {evaluated_flag})...")
        run_cmd([
            sys.executable,
            "vision/generate_detections.py",
            "--feed", feed_name,
            "--weights", "yolov8s.pt",
            "--imgsz", "1280",
            "--conf", "0.35",
            "--sample-interval", "0.5",
            "--device", "cuda:0",
            "--evaluated", evaluated_flag
        ])
    log("Feed detections generation complete.")


def run_finetuning_5fold(repo_dir: Path):
    log("=== PHASE 4: 5-FOLD CONTIGUOUS HOLDOUT FINE-TUNING ===")
    os.chdir(str(repo_dir))
    from ultralytics import YOLO
    from vision.eval.split_dataset import split_dataset
    from vision.eval.eval_detection import run_evaluation

    checkpoint_dir = Path("/content/checkpoints")
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    TRAIN_CONFIG = {
        "base_model": "yolov8m.pt",
        "epochs": 50,
        "imgsz": 1280,
        "batch": 8,
        "lr0": 0.01,
        "lrf": 0.01,
        "mosaic": 1.0,
        "mixup": 0.15,
        "box": 7.5,
        "cls": 0.5,
        "temporal_purge_buffer_frames": 4,
        "eval_scope": "same-scene performance (single source video)"
    }

    fold_results = []

    for fold in range(1, 6):
        log(f"--- STARTING FOLD {fold} / 5 (50 Epochs, {TRAIN_CONFIG['base_model']} @ {TRAIN_CONFIG['imgsz']}px) ---")
        split_manifest = split_dataset(fold=fold, num_folds=5, buffer_frames=TRAIN_CONFIG["temporal_purge_buffer_frames"])

        model = YOLO(TRAIN_CONFIG["base_model"])
        train_run = model.train(
            data="vision/data/aegis_data.yaml",
            epochs=TRAIN_CONFIG["epochs"],
            imgsz=TRAIN_CONFIG["imgsz"],
            batch=TRAIN_CONFIG["batch"],
            device=0,
            workers=4,
            lr0=TRAIN_CONFIG["lr0"],
            lrf=TRAIN_CONFIG["lrf"],
            mosaic=TRAIN_CONFIG["mosaic"],
            mixup=TRAIN_CONFIG["mixup"],
            box=TRAIN_CONFIG["box"],
            cls=TRAIN_CONFIG["cls"],
            project="runs/train",
            name=f"aegis_fold{fold}",
            save=True,
            plots=True
        )

        best_weights_path = repo_dir / "runs" / "train" / f"aegis_fold{fold}" / "weights" / "best.pt"
        weight_sha256 = "N/A"
        if best_weights_path.exists():
            weight_sha256 = hashlib.sha256(best_weights_path.read_bytes()).hexdigest()
            checkpoint_dst = checkpoint_dir / f"aegis_5fold_fold{fold}_best.pt"
            shutil.copy(best_weights_path, checkpoint_dst)
            log(f"Fold {fold} checkpoint saved to {checkpoint_dst} (SHA-256: {weight_sha256})")

        # Evaluate fine-tuned model on holdout val
        run_id_ft = f"yolov8m_1280px_val_fold{fold}_finetuned"
        eval_out_ft = f"docs/results/raw/{run_id_ft}/eval_results.json"
        log(f"Evaluating Fold {fold} fine-tuned model on val split...")
        run_evaluation(
            model_path=str(best_weights_path),
            split="val",
            fold=fold,
            imgsz=TRAIN_CONFIG["imgsz"],
            device="cuda:0",
            native_classes=True,
            save_raw=True,
            raw_root="docs/results/raw",
            run_id=run_id_ft,
            out_results=eval_out_ft
        )

        # Evaluate pre-trained baseline on same holdout val
        run_id_base = f"yolov8m_1280px_val_fold{fold}_baseline"
        eval_out_base = f"docs/results/raw/{run_id_base}/eval_results.json"
        log(f"Evaluating Fold {fold} pretrained baseline on val split...")
        run_evaluation(
            model_path=TRAIN_CONFIG["base_model"],
            split="val",
            fold=fold,
            imgsz=TRAIN_CONFIG["imgsz"],
            device="cuda:0",
            native_classes=False,
            save_raw=True,
            raw_root="docs/results/raw",
            run_id=run_id_base,
            out_results=eval_out_base
        )

        with open(eval_out_ft, "r", encoding="utf-8") as f:
            ft_data = json.load(f)
        with open(eval_out_base, "r", encoding="utf-8") as f:
            base_data = json.load(f)

        fold_results.append({
            "fold": fold,
            "train_count": split_manifest[f"fold_{fold}"]["train_count"],
            "buffer_count": split_manifest[f"fold_{fold}"]["buffer_count"],
            "val_count": split_manifest[f"fold_{fold}"]["val_count"],
            "weight_sha256": weight_sha256,
            "training_args": TRAIN_CONFIG,
            "finetuned_metrics": ft_data.get("metrics", {}),
            "baseline_metrics": base_data.get("metrics", {})
        })

    summary_path = repo_dir / "docs" / "results" / "raw" / "task4_5fold_finetune_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({
            "protocol": "5-fold contiguous holdout cross-validation",
            "evaluation_scope": "same-scene performance (single source video)",
            "train_config": TRAIN_CONFIG,
            "folds": fold_results
        }, f, indent=2)
    log(f"5-Fold fine-tuning complete. Summary saved to {summary_path}")


def package_artifacts(repo_dir: Path):
    log("=== PHASE 5: PACKAGE ARTIFACTS & COMPUTE TABLES ===")
    os.chdir(str(repo_dir))
    run_cmd([sys.executable, "scripts/compute_tables.py"])

    archive_dst = Path("/content/aegis_artifacts.tar.gz")
    log(f"Packaging raw outputs & feed detections into {archive_dst}...")
    run_cmd([
        "tar", "-czf", str(archive_dst),
        "docs/results/raw/",
        "frontend/public/feeds/uav-alpha/detections.json",
        "frontend/public/feeds/cctv-bravo/detections.json",
        "frontend/public/feeds/bodycam-charlie/detections.json"
    ])
    log(f"Archive created: {archive_dst} ({archive_dst.stat().st_size / 1024 / 1024:.2f} MB)")


def main():
    repo_dir = Path(os.environ.get("REPO_DIR", "/content/Aegis-Command"))
    phase = os.environ.get("PHASE", "bakeoff").lower()
    log(f"Starting Aegis Colab Runner | Repo: {repo_dir} | Phase: {phase}")

    bootstrap_environment(repo_dir)

    if phase in ("all", "bakeoff"):
        run_bakeoff(repo_dir)

    if phase in ("all", "feeds", "bakeoff"):
        run_feed_detections(repo_dir)

    if phase in ("all", "train"):
        run_finetuning_5fold(repo_dir)

    package_artifacts(repo_dir)
    log("ALL REQUESTED TASKS COMPLETED SUCCESSFULLY.")


if __name__ == "__main__":
    main()
