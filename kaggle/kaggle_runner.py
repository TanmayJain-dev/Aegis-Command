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


def safe_link_or_copy(src: Path, dst: Path):
    if dst.exists():
        return
    try:
        os.symlink(src.resolve(), dst)
    except OSError:
        shutil.copy2(src, dst)


def find_dataset_files(input_root: Path):
    images_dir = None
    labels_dir = None
    yolov8m_path = None
    images_zip = None
    labels_zip = None

    log(f"Recursively scanning {input_root}...")
    for root, dirs, files in os.walk(input_root):
        r_path = Path(root)
        if "yolov8m.pt" in files and yolov8m_path is None:
            yolov8m_path = r_path / "yolov8m.pt"
            log(f"Found yolov8m.pt at: {yolov8m_path}")
        if "images.zip" in files and images_zip is None:
            images_zip = r_path / "images.zip"
            log(f"Found images.zip at: {images_zip}")
        if "labels.zip" in files and labels_zip is None:
            labels_zip = r_path / "labels.zip"
            log(f"Found labels.zip at: {labels_zip}")
        if r_path.name == "images" and any(f.endswith(".jpg") for f in files):
            images_dir = r_path
            log(f"Found images dir at: {images_dir} ({len(files)} files)")
        elif "images" in dirs and any((r_path / "images").glob("*.jpg")) and images_dir is None:
            images_dir = r_path / "images"
            log(f"Found images dir child at: {images_dir}")
        if r_path.name == "labels" and any(f.endswith(".txt") for f in files):
            labels_dir = r_path
            log(f"Found labels dir at: {labels_dir} ({len(files)} files)")
        elif "labels" in dirs and any((r_path / "labels").glob("*.txt")) and labels_dir is None:
            labels_dir = r_path / "labels"
            log(f"Found labels dir child at: {labels_dir}")

    return {
        "images_dir": images_dir,
        "labels_dir": labels_dir,
        "yolov8m_path": yolov8m_path,
        "images_zip": images_zip,
        "labels_zip": labels_zip
    }


def generate_demo_feed_detections(repo_dir: Path, work_dir: Path):
    """
    Kaggle GPU step:
    1. Download v0.4.0 release asset 'aegis_demo_full_last.pt'
    2. Verify SHA-256 checksum against checkpoints_manifest.json
    3. Run scripts/generate_feed_detections.py on frontend/public/feeds/uav-alpha/video.mp4
       with imgsz=1280, conf=0.35, tracker=bytetrack.yaml, sample_interval=0.5, device=cuda:0
    4. Save to /kaggle/working/uav-alpha/detections.json and /kaggle/working/detections.json
    """
    log("\n=================== GENERATING DEMO FEED DETECTIONS ON GPU ===================")
    checkpoints_dir = work_dir / "checkpoints"
    checkpoints_dir.mkdir(parents=True, exist_ok=True)
    weights_path = checkpoints_dir / "aegis_demo_full_last.pt"

    manifest_path = repo_dir / "docs" / "results" / "raw" / "checkpoints_manifest.json"
    assert manifest_path.exists(), f"checkpoints_manifest.json missing at {manifest_path}"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    expected_sha256 = manifest.get("aegis_demo_full_last")
    assert expected_sha256, "aegis_demo_full_last key missing in checkpoints_manifest.json"

    # Download from v0.4.0 release asset if not present or corrupt
    if not weights_path.exists() or compute_sha256(weights_path) != expected_sha256:
        asset_url = "https://github.com/TanmayJain-dev/Aegis-Command/releases/download/v0.4.0/aegis_demo_full_last.pt"
        log(f"Downloading release asset: {asset_url} -> {weights_path}...")
        run_cmd(["curl", "-fsSL", "-o", str(weights_path), asset_url])

    actual_sha256 = compute_sha256(weights_path)
    log(f"Verified weights SHA-256: {actual_sha256}")
    assert actual_sha256 == expected_sha256, (
        f"Checksum mismatch: expected {expected_sha256}, got {actual_sha256}"
    )

    video_path = repo_dir / "frontend" / "public" / "feeds" / "uav-alpha" / "video.mp4"
    assert video_path.exists(), f"Video file missing: {video_path}"

    out_dir = work_dir / "uav-alpha"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_json = out_dir / "detections.json"
    root_out_json = work_dir / "detections.json"

    gen_script = repo_dir / "scripts" / "generate_feed_detections.py"
    cmd = [
        sys.executable,
        str(gen_script),
        "--video", str(video_path),
        "--weights", str(weights_path),
        "--out", str(out_json),
        "--imgsz", "1280",
        "--conf", "0.35",
        "--tracker", "bytetrack.yaml",
        "--sample-interval", "0.5",
        "--device", "cuda:0",
        "--feed", "uav-alpha",
        "--evaluated",
    ]
    log(f"Executing: {' '.join(cmd)}")
    run_cmd(cmd, cwd=str(repo_dir))

    # Also copy to root of working directory so it's readily accessible in kernel output
    shutil.copy2(out_json, root_out_json)
    log(f"Generated uav-alpha detections exported to {out_json} and {root_out_json}")


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
    repo_dir = Path("/tmp/repo")
    branch = os.environ.get("GIT_BRANCH", "feat/detection-v4")
    if not repo_dir.exists():
        log(f"Cloning repo into {repo_dir} (branch: {branch})...")
        run_cmd(["git", "clone", "-b", branch, "https://github.com/TanmayJain-dev/Aegis-Command.git", str(repo_dir)])
    else:
        log(f"Repo already exists at {repo_dir}")

    # 5. Generate Demo Feed Detections on GPU
    generate_demo_feed_detections(repo_dir=repo_dir, work_dir=work_dir)

    runner_mode = os.environ.get("RUNNER_MODE", "feed_only")
    if runner_mode != "full_cv":
        log("Feed generation complete. Default RUNNER_MODE=feed_only; skipping 5-fold CV rerun.")
        log("=== AEGIS COMMAND - KAGGLE GPU RUNNER COMPLETE ===")
        return

    # 6. Locate dataset and link into repo (for full_cv mode)
    input_root = Path("/kaggle/input")
    assert input_root.exists(), "Missing /kaggle/input"
    found = find_dataset_files(input_root)

    eval_images_dir = repo_dir / "vision" / "eval" / "images"
    eval_labels_dir = repo_dir / "vision" / "eval" / "labels"
    eval_images_dir.mkdir(parents=True, exist_ok=True)
    eval_labels_dir.mkdir(parents=True, exist_ok=True)

    import zipfile
    if found["images_zip"]:
        log(f"Extracting {found['images_zip']}...")
        with zipfile.ZipFile(found["images_zip"], "r") as z:
            z.extractall(eval_images_dir.parent)
    elif found["images_dir"]:
        log(f"Copying images from {found['images_dir']} to {eval_images_dir}...")
        for img in found["images_dir"].glob("*.jpg"):
            safe_link_or_copy(img, eval_images_dir / img.name)
    else:
        log("Searching for all .jpg files under /kaggle/input...")
        for root, _, files in os.walk(input_root):
            for f in files:
                if f.endswith(".jpg"):
                    safe_link_or_copy(Path(root) / f, eval_images_dir / f)

    if found["labels_zip"]:
        log(f"Extracting {found['labels_zip']}...")
        with zipfile.ZipFile(found["labels_zip"], "r") as z:
            z.extractall(eval_labels_dir.parent)
    elif found["labels_dir"]:
        log(f"Copying labels from {found['labels_dir']} to {eval_labels_dir}...")
        for lbl in found["labels_dir"].glob("*.txt"):
            safe_link_or_copy(lbl, eval_labels_dir / lbl.name)

    img_count = len(list(eval_images_dir.glob("*.jpg")))
    lbl_count = len(list(eval_labels_dir.glob("*.txt")))
    log(f"Verified dataset: {img_count} images and {lbl_count} labels.")
    assert img_count == 155, f"Expected 155 images in {eval_images_dir}, found {img_count}"
    assert lbl_count == 155, f"Expected 155 labels in {eval_labels_dir}, found {lbl_count}"

    # Base model weights
    weights_dir = repo_dir / "weights"
    weights_dir.mkdir(parents=True, exist_ok=True)
    if found["yolov8m_path"]:
        dst_weights = weights_dir / "yolov8m.pt"
        if not dst_weights.exists():
            shutil.copy2(found["yolov8m_path"], dst_weights)
        log(f"Verified yolov8m.pt baseline (SHA-256: {compute_sha256(dst_weights)})")
    else:
        raise FileNotFoundError("Could not find yolov8m.pt in /kaggle/input")

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
                data=str(repo_dir / "vision" / "data" / "aegis_data.yaml"),
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
            images_dir=str(eval_images_dir),
            labels_dir=str(eval_labels_dir),
            manifest_path=str(repo_dir / "vision" / "data" / "split_manifest.json"),
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
            safe_link_or_copy(img_path, demo_data_dir / "images" / "train" / f"{stem}.jpg")
            if lbl_path.exists():
                safe_link_or_copy(lbl_path, demo_data_dir / "labels" / "train" / f"{stem}.txt")
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
