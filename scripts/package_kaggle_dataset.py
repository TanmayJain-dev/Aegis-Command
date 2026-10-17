#!/usr/bin/env python3
"""
Aegis Command - Kaggle Dataset Packaging Script.

Packages the 155 labeled evaluation frames, ground-truth labels,
5-fold split definitions, manifest, and verified yolov8m.pt baseline
into a staging directory ready for `kaggle datasets create`.
"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "vision" / "eval"))
from split_dataset import split_dataset
from finalize_labels import compute_labels_sha256

EXPECTED_YOLOV8M_SHA256 = "5d4a90cdc7a21786cc59cd19778e9eafff836df9e2da32524737c7ee6efe4fe5"


def compute_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def package_dataset(out_dir: Path, username: str = "tanmayjain"):
    print(f"Packaging Aegis Kaggle dataset to: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Images
    src_images = sorted(list((REPO_ROOT / "vision" / "eval" / "images").glob("*.jpg")))
    if len(src_images) != 155:
        raise RuntimeError(f"Expected 155 frames in vision/eval/images, found {len(src_images)}")
    dst_images = out_dir / "images"
    dst_images.mkdir(parents=True, exist_ok=True)
    for p in src_images:
        shutil.copy2(p, dst_images / p.name)
    print(f"  ✓ Copied 155 images ({len(list(dst_images.glob('*.jpg')))})")

    # 2. Labels
    src_labels = sorted(list((REPO_ROOT / "vision" / "eval" / "labels").glob("*.txt")))
    dst_labels = out_dir / "labels"
    dst_labels.mkdir(parents=True, exist_ok=True)
    for p in src_labels:
        shutil.copy2(p, dst_labels / p.name)
    labels_sha = compute_labels_sha256(dst_labels)
    print(f"  ✓ Copied ground-truth labels (SHA-256: {labels_sha})")

    # 3. Manifest & Splits
    src_manifest = REPO_ROOT / "vision" / "eval" / "manifest.json"
    if src_manifest.exists():
        shutil.copy2(src_manifest, out_dir / "manifest.json")

    # Generate 5-fold splits
    splits_summary = {}
    for fold in range(1, 6):
        manifest = split_dataset(fold=fold, num_folds=5, buffer_frames=4)
        splits_summary[f"fold_{fold}"] = manifest[f"fold_{fold}"]
    with open(out_dir / "splits_5fold_manifest.json", "w", encoding="utf-8") as f:
        json.dump(splits_summary, f, indent=2)
    print("  ✓ Generated 5-fold split definitions")

    # 4. Baseline weights
    weights_path = REPO_ROOT / "weights" / "yolov8m.pt"
    if not weights_path.exists():
        raise FileNotFoundError(f"Missing {weights_path}. Run scripts/download_weights.py first.")
    actual_sha = compute_sha256(weights_path)
    if actual_sha != EXPECTED_YOLOV8M_SHA256:
        raise ValueError(f"yolov8m.pt SHA-256 mismatch: {actual_sha} != {EXPECTED_YOLOV8M_SHA256}")
    shutil.copy2(weights_path, out_dir / "yolov8m.pt")
    print(f"  ✓ Verified and copied yolov8m.pt (SHA-256: {actual_sha})")

    # 5. Dataset metadata for Kaggle
    meta = {
        "title": "Aegis Command Tactical Drone Dataset",
        "id": f"{username}/aegis-command-dataset",
        "licenses": [{"name": "CC0-1.0"}],
        "isPrivate": True
    }
    with open(out_dir / "dataset-metadata.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(f"  ✓ Created dataset-metadata.json (isPrivate: True, id: {meta['id']})")
    print(f"\nDataset package ready at {out_dir}.")


def main():
    parser = argparse.ArgumentParser(description="Package Kaggle dataset for Aegis Command")
    parser.add_argument("--out-dir", default="/tmp/aegis_kaggle_dataset", help="Output directory")
    parser.add_argument("--username", default="tanmayjain", help="Kaggle username for dataset slug")
    args = parser.parse_args()
    package_dataset(Path(args.out_dir), username=args.username)


if __name__ == "__main__":
    main()
