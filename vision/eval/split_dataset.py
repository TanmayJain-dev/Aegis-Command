#!/usr/bin/env python3
"""
Aegis Command - Dataset Partitioning & YAML Generator.

Splits 155 human-verified drone frames into:
- 124 training frames (80%)
- 31 validation frames (20%)

Uses systematic 1-in-5 sampling to ensure the validation set covers
every phase of the drone flight without consecutive temporal overlap.
Generates vision/data/ directory with symlinks and aegis_data.yaml.
"""

import os
import sys
import json
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
IMAGES_DIR = REPO_ROOT / "vision" / "eval" / "images"
LABELS_DIR = REPO_ROOT / "vision" / "eval" / "labels"
DATA_DIR = REPO_ROOT / "vision" / "data"

CLASS_NAMES = ["person", "car", "truck", "bus"]


def split_dataset(val_interval: int = 5):
    if not IMAGES_DIR.exists():
        print(f"Error: {IMAGES_DIR} not found", file=sys.stderr)
        sys.exit(1)
    if not LABELS_DIR.exists():
        print(f"Error: {LABELS_DIR} not found", file=sys.stderr)
        sys.exit(1)

    images = sorted(list(IMAGES_DIR.glob("*.jpg")) + list(IMAGES_DIR.glob("*.png")))
    stems = [img.stem for img in images]

    if len(stems) != 155:
        print(f"Warning: Expected 155 images, found {len(stems)}", file=sys.stderr)

    train_stems = []
    val_stems = []

    for idx, stem in enumerate(stems):
        # Every 5th frame (indices 4, 9, 14, ...) goes to val
        if (idx + 1) % val_interval == 0:
            val_stems.append(stem)
        else:
            train_stems.append(stem)

    print(f"Total frames: {len(stems)}")
    print(f"Train split:  {len(train_stems)} frames ({len(train_stems)/len(stems)*100:.1f}%)")
    print(f"Val split:    {len(val_stems)} frames ({len(val_stems)/len(stems)*100:.1f}%)")

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
            # Empty label file for frames with zero detections
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
    manifest = {
        "total": len(stems),
        "train_count": len(train_stems),
        "val_count": len(val_stems),
        "train_stems": train_stems,
        "val_stems": val_stems
    }
    with open(DATA_DIR / "split_manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    # Write Ultralytics YAML
    yaml_content = f"""# Aegis Command - YOLO Fine-Tuning Dataset Definition
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
    with open(yaml_path, "w") as f:
        f.write(yaml_content)

    print(f"\n[OK] Dataset prepared in {DATA_DIR}")
    print(f"[OK] Manifest written to {DATA_DIR / 'split_manifest.json'}")
    print(f"[OK] Ultralytics YAML written to {yaml_path}")
    return manifest


if __name__ == "__main__":
    split_dataset()
