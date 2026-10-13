#!/usr/bin/env python3
"""
Aegis Command - Dataset Partitioning & YAML Generator.

Implements rigorous Time-Based Contiguous Holdout splits to prevent temporal leakage:
- 155 human-verified drone frames (1,948 ground truth boxes).
- Fold 1:
    Train: frames 0..107 (108 frames, ~70%)
    Buffer Purged: frames 108..112 (5 frames purged)
    Test / Val: frames 113..154 (42 frames, ~27%)
- Fold 2 (Reverse):
    Test / Val: frames 0..41 (42 frames, ~27%)
    Buffer Purged: frames 42..46 (5 frames purged)
    Train: frames 47..154 (108 frames, ~70%)

Generates vision/data/ directory with symlinks, split_manifest.json, and aegis_data.yaml.
"""

import os
import sys
import json
import shutil
import argparse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
IMAGES_DIR = REPO_ROOT / "vision" / "eval" / "images"
LABELS_DIR = REPO_ROOT / "vision" / "eval" / "labels"
DATA_DIR = REPO_ROOT / "vision" / "data"

CLASS_NAMES = ["person", "car", "truck", "bus"]


def get_contiguous_splits(stems: list) -> dict:
    """Computes Fold 1 and Fold 2 stem partitions."""
    total = len(stems)
    if total != 155:
        print(f"Warning: Expected 155 images, found {total}", file=sys.stderr)

    # Fold 1: train 0..107, buffer 108..112, val 113..154
    f1_train = stems[0:108]
    f1_buffer = stems[108:113]
    f1_val = stems[113:155]

    # Fold 2: val 0..41, buffer 42..46, train 47..154
    f2_val = stems[0:42]
    f2_buffer = stems[42:47]
    f2_train = stems[47:155]

    return {
        "total": total,
        "fold_1": {
            "train_stems": f1_train,
            "purged_buffer_stems": f1_buffer,
            "val_stems": f1_val,
            "train_count": len(f1_train),
            "buffer_count": len(f1_buffer),
            "val_count": len(f1_val),
        },
        "fold_2": {
            "train_stems": f2_train,
            "purged_buffer_stems": f2_buffer,
            "val_stems": f2_val,
            "train_count": len(f2_train),
            "buffer_count": len(f2_buffer),
            "val_count": len(f2_val),
        }
    }


def split_dataset(fold: int = 1):
    if not IMAGES_DIR.exists():
        print(f"Error: {IMAGES_DIR} not found", file=sys.stderr)
        sys.exit(1)
    if not LABELS_DIR.exists():
        print(f"Error: {LABELS_DIR} not found", file=sys.stderr)
        sys.exit(1)

    images = sorted(list(IMAGES_DIR.glob("*.jpg")) + list(IMAGES_DIR.glob("*.png")))
    stems = [img.stem for img in images]

    all_splits = get_contiguous_splits(stems)
    fold_key = f"fold_{fold}"
    if fold_key not in all_splits:
        print(f"Error: Invalid fold {fold}. Must be 1 or 2.", file=sys.stderr)
        sys.exit(1)

    current_split = all_splits[fold_key]
    train_stems = current_split["train_stems"]
    val_stems = current_split["val_stems"]
    buffer_stems = current_split["purged_buffer_stems"]

    print("=" * 65)
    print(f"TIME-BASED CONTIGUOUS SPLIT (Fold {fold})")
    print("=" * 65)
    print(f"Total Frames:          {len(stems)}")
    print(f"Train Frames:          {len(train_stems)} ({len(train_stems)/len(stems)*100:.1f}%)")
    print(f"Purged Buffer Frames:  {len(buffer_stems)} (5 frames temporal separation)")
    print(f"Val / Test Frames:     {len(val_stems)} ({len(val_stems)/len(stems)*100:.1f}%)")
    print("=" * 65)

    # Clean/create directories
    for sub in ["images/train", "images/val", "labels/train", "labels/val"]:
        p = DATA_DIR / sub
        if p.exists():
            shutil.rmtree(p)
        p.mkdir(parents=True, exist_ok=True)

    # Populate train
    for s in train_stems:
        img_src = IMAGES_DIR / f"{s}.jpg"
        lbl_src = LABELS_DIR / f"{s}.txt"
        img_dst = DATA_DIR / "images" / "train" / f"{s}.jpg"
        lbl_dst = DATA_DIR / "labels" / "train" / f"{s}.txt"

        if img_src.exists():
            os.symlink(img_src.resolve(), img_dst)
        if lbl_src.exists():
            os.symlink(lbl_src.resolve(), lbl_dst)
        else:
            lbl_dst.touch()

    # Populate val
    for s in val_stems:
        img_src = IMAGES_DIR / f"{s}.jpg"
        lbl_src = LABELS_DIR / f"{s}.txt"
        img_dst = DATA_DIR / "images" / "val" / f"{s}.jpg"
        lbl_dst = DATA_DIR / "labels" / "val" / f"{s}.txt"

        if img_src.exists():
            os.symlink(img_src.resolve(), img_dst)
        if lbl_src.exists():
            os.symlink(lbl_src.resolve(), lbl_dst)
        else:
            lbl_dst.touch()

    # Write split manifest
    manifest_data = dict(all_splits)
    manifest_data["active_fold"] = fold
    manifest_data["train_stems"] = train_stems
    manifest_data["val_stems"] = val_stems

    with open(DATA_DIR / "split_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    # Write Ultralytics YAML
    yaml_content = f"""# Aegis Command - YOLO Fine-Tuning Dataset Definition (Fold {fold})
path: {DATA_DIR.resolve()}
train: images/train
val: images/val

names:
  0: person
  1: car
  2: truck
  3: bus
"""
    yaml_path = DATA_DIR / "aegis_data.yaml"
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write(yaml_content)

    print(f"\n[OK] Fold {fold} dataset populated in {DATA_DIR}")
    print(f"[OK] Manifest written to {DATA_DIR / 'split_manifest.json'}")
    print(f"[OK] Ultralytics YAML written to {yaml_path}")
    return manifest_data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Partition dataset with time-based contiguous holdout.")
    parser.add_argument("--fold", type=int, default=1, choices=[1, 2], help="Fold index (1 or 2)")
    args = parser.parse_args()

    split_dataset(fold=args.fold)
