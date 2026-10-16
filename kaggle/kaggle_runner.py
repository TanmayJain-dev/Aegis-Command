#!/usr/bin/env python3
"""
Aegis Command - Autonomous Kaggle GPU Pipeline Runner.

Thin adapter that runs in Kaggle script kernels:
- Maps read-only /kaggle/input and writable /kaggle/working
- Clones repo at pinned branch/commit
- Installs ultralytics at pinned version
- Trains fixed-epoch (epochs=50, val=False, seed=42) 5-fold CV models
- Evaluates holdouts with vision/eval/eval_detection.py
- Trains Phase 6 final demo model on all 155 frames
- Generates checkpoints_manifest.json with SHA-256 checksums
"""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def run_cmd(cmd, cwd=None):
    log(f"CMD: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    res = subprocess.run(cmd, shell=isinstance(cmd, str), cwd=cwd, check=True)
    return res


def compute_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def find_dataset_dir() -> Path:
    candidates = [
        Path("/kaggle/input/aegis-command-dataset"),
        Path("/kaggle/input/aegis_command_dataset"),
    ]
    # Scan /kaggle/input for any dir containing images and labels
    input_root = Path("/kaggle/input")
    if input_root.exists():
        for d in input_root.iterdir():
            if (d / "images").exists() and (d / "labels").exists():
                return d
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError("Could not locate Aegis dataset in /kaggle/input")


def main():
    log("=== AEGIS COMMAND - KAGGLE GPU RUNNER START ===")

    # 1. Environment & Paths
    work_dir = Path("/kaggle/working")
    checkpoints_dir = work_dir / "checkpoints"
    results_dir = work_dir / "results"
    checkpoints_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    # 2. Verify GPU
    try:
        import torch
        assert torch.cuda.is_available(), "CUDA is not available!"
        log(f"CUDA Available: True | Device: {torch.cuda.get_device_name(0)}")
    except Exception as e:
        log(f"CUDA Check Warning: {e}")

    # 3. Pip install pinned packages
    log("Installing pinned ultralytics...")
    run_cmd([sys.executable, "-m", "pip", "install", "-q", "ultralytics==8.4.175"])

    # 4. Clone repo
    repo_dir = work_dir / "repo"
    branch = os.environ.get("GIT_BRANCH", "feat/detection-v4")
    if not repo_dir.exists():
        log(f"Cloning repo into {repo_dir} (branch: {branch})...")
        run_cmd(["git", "clone", "-b", branch, "https://github.com/TanmayJain-dev/Aegis-Command.git", str(repo_dir)])
    else:
        log(f"Repo already exists at {repo_dir}")

    # 5. Locate dataset and link into repo
    dataset_dir = find_dataset_dir()
    log(f"Found input dataset at: {dataset_dir}")

    eval_images_dir = repo_dir / "vision" / "eval" / "images"
    eval_labels_dir = repo_dir / "vision" / "eval" / "labels"
    eval_images_dir.mkdir(parents=True, exist_ok=True)
    eval_labels_dir.mkdir(parents=True, exist_ok=True)

    for img in (dataset_dir / "images").glob("*.jpg"):
        dst = eval_images_dir / img.name
        if not dst.exists():
            os.symlink(img.resolve(), dst)

    for lbl in (dataset_dir / "labels").glob("*.txt"):
        dst = eval_labels_dir / lbl.name
        if not dst.exists():
            os.symlink(lbl.resolve(), dst)

    log(f"Linked {len(list(eval_images_dir.glob('*.jpg')))} images and {len(list(eval_labels_dir.glob('*.txt')))} labels.")

    # Base model weights
    weights_dir = repo_dir / "weights"
    weights_dir.mkdir(parents=True, exist_ok=True)
    src_weights = dataset_dir / "yolov8m.pt"
    if src_weights.exists():
        dst_weights = weights_dir / "yolov8m.pt"
        if not dst_weights.exists():
            shutil.copy2(src_weights, dst_weights)
        log(f"Verified yolov8m.pt baseline (SHA-256: {compute_sha256(dst_weights)})")

    # Add repo to sys.path
    os.chdir(str(repo_dir))
    sys.path.insert(0, str(repo_dir))
    sys.path.insert(0, str(repo_dir / "vision" / "eval"))

    from ultralytics import YOLO
    from vision.eval.split_dataset import split_dataset
    from vision.eval.eval_detection import run_evaluation

    # 6. Training Configuration for Fixed-Epoch last.pt
    FIXED_CONFIG = {
        "base_model": str(weights_dir / "yolov8m.pt"),
        "epochs": 50,
        "imgsz": 1280,
        "batch": 8,
        "lr0": 0.01,
        "lrf": 0.01,
        "mosaic": 1.0,
        "mixup": 0.15,
        "box": 7.5,
        "cls": 0.5,
        "seed": 42,
        "temporal_purge_buffer_frames": 4,
    }

    manifest_map = {}

    # Run Folds 1 to 5
    for fold in range(1, 6):
        log(f"\n=================== FOLD {fold} / 5 (Fixed 50 Epochs, val=False) ===================")
        split_manifest = split_dataset(fold=fold, num_folds=5, buffer_frames=FIXED_CONFIG["temporal_purge_buffer_frames"])

        last_weights_path = checkpoints_dir / f"aegis_5fold_fold{fold}_last.pt"
        run_id_fixed = f"yolov8m_1280px_val_fold{fold}_fixed50"
        eval_out_fixed = results_dir / run_id_fixed / "eval_results.json"
        eval_out_fixed.parent.mkdir(parents=True, exist_ok=True)

        if last_weights_path.exists() and eval_out_fixed.exists():
            log(f"[SKIP] Fold {fold} already complete: {last_weights_path} and {eval_out_fixed}")
            manifest_map[f"fold_{fold}_last"] = compute_sha256(last_weights_path)
            continue

        if not last_weights_path.exists():
            log(f"Training Fold {fold} fixed-epoch model (val=False, seed=42)...")
            model = YOLO(FIXED_CONFIG["base_model"])
            train_fixed = model.train(
                data="vision/data/aegis_data.yaml",
                epochs=FIXED_CONFIG["epochs"],
                imgsz=FIXED_CONFIG["imgsz"],
                batch=FIXED_CONFIG["batch"],
                device=0,
                workers=2,
                lr0=FIXED_CONFIG["lr0"],
                lrf=FIXED_CONFIG["lrf"],
                mosaic=FIXED_CONFIG["mosaic"],
                mixup=FIXED_CONFIG["mixup"],
                box=FIXED_CONFIG["box"],
                cls=FIXED_CONFIG["cls"],
                seed=FIXED_CONFIG["seed"],
                val=False,
                project="runs/train",
                name=f"aegis_fold{fold}_fixed50",
                save=True,
                plots=False
            )
            # Find last.pt
            candidates = [
                Path(train_fixed.save_dir) / "weights" / "last.pt",
                repo_dir / "runs" / "train" / f"aegis_fold{fold}_fixed50" / "weights" / "last.pt",
            ]
            found_last = None
            for p in candidates:
                if p.exists():
                    found_last = p
                    break
            assert found_last is not None, f"last.pt missing for Fold {fold}"
            shutil.copy2(found_last, last_weights_path)

        last_sha256 = compute_sha256(last_weights_path)
        manifest_map[f"fold_{fold}_last"] = last_sha256
        log(f"Fold {fold} fixed-epoch checkpoint: {last_weights_path} (SHA-256: {last_sha256})")

        # Evaluate on holdout val split
        log(f"Evaluating Fold {fold} last.pt on holdout val split...")
        run_evaluation(
            model_path=str(last_weights_path),
            split="val",
            fold=fold,
            imgsz=FIXED_CONFIG["imgsz"],
            device="cuda:0",
            native_classes=True,
            save_raw=True,
            raw_root=str(results_dir),
            run_id=run_id_fixed,
            out_results=str(eval_out_fixed)
        )
        log(f"Fold {fold} evaluation complete -> {eval_out_fixed}")

    # 7. Phase 6: Final Demo Model Training on all 155 frames
    log("\n=================== PHASE 6: FINAL DEMO MODEL (All 155 Frames) ===================")
    demo_weights_path = checkpoints_dir / "aegis_demo_full_last.pt"
    if not demo_weights_path.exists():
        demo_data_dir = repo_dir / "vision" / "data" / "demo_full"
        for sub in ["images/train", "labels/train"]:
            p = demo_data_dir / sub
            if p.exists():
                shutil.rmtree(p)
            p.mkdir(parents=True, exist_ok=True)

        eval_images = sorted(list(eval_images_dir.glob("*.jpg")))
        for img_path in eval_images:
            stem = img_path.stem
            lbl_path = eval_labels_dir / f"{stem}.txt"
            os.symlink(img_path.resolve(), demo_data_dir / "images" / "train" / f"{stem}.jpg")
            if lbl_path.exists():
                os.symlink(lbl_path.resolve(), demo_data_dir / "labels" / "train" / f"{stem}.txt")
            else:
                (demo_data_dir / "labels" / "train" / f"{stem}.txt").touch()

        from vision.eval.class_map import CLASS_MAP
        names_yaml = "\n".join([f"  {cid}: {name}" for cid, name in CLASS_MAP.items()])
        demo_yaml_content = f"""# Aegis Command - Full 155-Frame Demo Model Training
path: {demo_data_dir.resolve()}
train: images/train
val: images/train

names:
{names_yaml}
"""
        demo_yaml_path = demo_data_dir / "demo_data.yaml"
        with open(demo_yaml_path, "w", encoding="utf-8") as f:
            f.write(demo_yaml_content)

        log("Training Phase 6 demo model on all 155 frames (50 epochs, val=False)...")
        demo_model = YOLO(FIXED_CONFIG["base_model"])
        demo_train = demo_model.train(
            data=str(demo_yaml_path),
            epochs=50,
            imgsz=1280,
            batch=8,
            device=0,
            workers=2,
            lr0=0.01,
            lrf=0.01,
            mosaic=1.0,
            mixup=0.15,
            box=7.5,
            cls=0.5,
            seed=42,
            val=False,
            project="runs/train",
            name="aegis_demo_full",
            save=True,
            plots=False
        )
        candidates = [
            Path(demo_train.save_dir) / "weights" / "last.pt",
            repo_dir / "runs" / "train" / "aegis_demo_full" / "weights" / "last.pt",
        ]
        found_demo = None
        for p in candidates:
            if p.exists():
                found_demo = p
                break
        assert found_demo is not None, "Phase 6 last.pt missing"
        shutil.copy2(found_demo, demo_weights_path)

    demo_sha256 = compute_sha256(demo_weights_path)
    manifest_map["aegis_demo_full_last"] = demo_sha256
    log(f"Phase 6 demo model saved: {demo_weights_path} (SHA-256: {demo_sha256})")

    # 8. Checkpoints Manifest
    manifest_file = work_dir / "checkpoints_manifest.json"
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest_map, f, indent=2)
    log(f"Checkpoints manifest saved to: {manifest_file}")

    log("=== AEGIS COMMAND - KAGGLE GPU RUNNER COMPLETE ===")


if __name__ == "__main__":
    main()
