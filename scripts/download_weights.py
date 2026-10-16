#!/usr/bin/env python3
"""
Aegis Command - Model Weights Retrieval & Verification Tool.

Downloads reproducible model checkpoints (or pulls from active Colab session)
and cryptographically verifies SHA-256 checksums before saving to weights/.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request

KNOWN_WEIGHTS = {
    "demo_full": {
        "filename": "aegis_demo_full_last.pt",
        "description": "Full 155-frame fine-tuned demo model (fixed 50 epochs, val=False)",
        "colab_path": "/content/checkpoints/aegis_demo_full_last.pt"
    },
    "fold1_fixed50": {
        "filename": "aegis_5fold_fold1_last.pt",
        "description": "Fold 1 holdout fixed-epoch model (last.pt, zero holdout snooping)",
        "colab_path": "/content/checkpoints/aegis_5fold_fold1_last.pt"
    },
    "fold2_fixed50": {
        "filename": "aegis_5fold_fold2_last.pt",
        "description": "Fold 2 holdout fixed-epoch model (last.pt, zero holdout snooping)",
        "colab_path": "/content/checkpoints/aegis_5fold_fold2_last.pt"
    },
    "fold3_fixed50": {
        "filename": "aegis_5fold_fold3_last.pt",
        "description": "Fold 3 holdout fixed-epoch model (last.pt, zero holdout snooping)",
        "colab_path": "/content/checkpoints/aegis_5fold_fold3_last.pt"
    },
    "fold4_fixed50": {
        "filename": "aegis_5fold_fold4_last.pt",
        "description": "Fold 4 holdout fixed-epoch model (last.pt, zero holdout snooping)",
        "colab_path": "/content/checkpoints/aegis_5fold_fold4_last.pt"
    },
    "fold5_fixed50": {
        "filename": "aegis_5fold_fold5_last.pt",
        "description": "Fold 5 holdout fixed-epoch model (last.pt, zero holdout snooping)",
        "colab_path": "/content/checkpoints/aegis_5fold_fold5_last.pt"
    },
    "yolov8m_baseline": {
        "filename": "yolov8m.pt",
        "description": "COCO pretrained YOLOv8m baseline",
        "sha256": "5d4a90cdc7a21786cc59cd19778e9eafff836df9e2da32524737c7ee6efe4fe5",
        "url": "https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8m.pt"
    },
    "yolov8s_baseline": {
        "filename": "yolov8s.pt",
        "description": "COCO pretrained YOLOv8s baseline",
        "sha256": "1f47a78bf100391c2a140b7ac73a1caae18c32779be7d310658112f7ac9aa78a",
        "url": "https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8s.pt"
    }
}


def compute_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def download_weight(key: str, info: dict, out_dir: Path, session: str = "aegis-cv"):
    dest = out_dir / info["filename"]
    print(f"\nProcessing [{key}] -> {dest}")
    print(f"  Description: {info['description']}")

    if dest.exists():
        actual_sha = compute_sha256(dest)
        if "sha256" in info and actual_sha == info["sha256"]:
            print(f"  ✓ Already exists and verified (SHA-256: {actual_sha})")
            return
        elif "sha256" not in info:
            print(f"  ✓ Exists locally (SHA-256: {actual_sha})")
            return

    # Download from URL if available
    if "url" in info:
        print(f"  Downloading from official release URL: {info['url']}...")
        urllib.request.urlretrieve(info["url"], dest)
    elif "colab_path" in info:
        print(f"  Pulling from Colab session '{session}': {info['colab_path']}...")
        cmd = ["colab", "download", "-s", session, info["colab_path"], str(dest)]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"  ✗ Colab download failed: {res.stderr.strip()}", file=sys.stderr)
            return

    if dest.exists():
        actual_sha = compute_sha256(dest)
        expected_sha = info.get("sha256")
        if expected_sha and actual_sha != expected_sha:
            print(f"  ✗ SHA-256 MISMATCH for {dest}: expected {expected_sha}, got {actual_sha}", file=sys.stderr)
            sys.exit(1)
        print(f"  ✓ Saved and verified: {dest} ({dest.stat().st_size / 1024 / 1024:.2f} MB)")
        print(f"    SHA-256: {actual_sha}")
    else:
        print(f"  ✗ Failed to save {dest}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Download and verify Aegis Command model checkpoints.")
    parser.add_argument("--model", default="demo_full", choices=list(KNOWN_WEIGHTS.keys()) + ["all"],
                        help="Model key to download or 'all'")
    parser.add_argument("--out-dir", default="weights", help="Directory to save weights (default: weights/)")
    parser.add_argument("--session", default="aegis-cv", help="Active Colab session name (default: aegis-cv)")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    targets = list(KNOWN_WEIGHTS.keys()) if args.model == "all" else [args.model]
    for key in targets:
        download_weight(key, KNOWN_WEIGHTS[key], out_dir, session=args.session)


if __name__ == "__main__":
    main()
