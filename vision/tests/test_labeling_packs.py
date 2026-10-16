"""
Unit tests for Task 7 secondary feed labeling packs and manifests.
"""

import json
from pathlib import Path
import pytest
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "vision" / "eval"))

from build_labeling_pack import CLASSES, FEEDS


@pytest.mark.parametrize("feed_id", ["cctv-bravo", "bodycam-charlie"])
def test_labeling_pack_manifest_and_structure(feed_id):
    pack_dir = REPO_ROOT / "vision" / "labeling_packs" / feed_id
    assert pack_dir.exists(), f"Pack directory missing: {pack_dir}"

    manifest_file = pack_dir / "manifest.json"
    assert manifest_file.exists(), f"Manifest file missing: {manifest_file}"

    with open(manifest_file, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # Invariant: Must mark reviewed=False and prelabels_used=False
    assert manifest["feed"] == feed_id
    assert manifest["reviewed"] is False, "Must not mark unreviewed pack as reviewed"
    assert manifest["prelabels_used"] is False, "Must not use model pre-labels"
    assert manifest["total_frames_sampled"] == 40
    assert len(manifest["frames"]) == 40
    assert manifest["classes"] == CLASSES

    # Check images directory
    img_dir = pack_dir / "images"
    assert img_dir.exists()
    images = sorted(list(img_dir.glob("*.jpg")))
    assert len(images) == 40, f"Expected 40 images, found {len(images)}"

    # Check labels directory (strictly empty files for human annotation)
    lbl_dir = pack_dir / "labels"
    assert lbl_dir.exists()
    labels = sorted(list(lbl_dir.glob("*.txt")))
    assert len(labels) == 40, f"Expected 40 label files, found {len(labels)}"

    for lbl in labels:
        assert lbl.stat().st_size == 0, f"Label file {lbl.name} must be empty (0 bytes) to avoid model prelabel leakage"

    # Check classes.txt
    classes_file = pack_dir / "classes.txt"
    assert classes_file.exists()
    classes_lines = classes_file.read_text(encoding="utf-8").strip().splitlines()
    assert classes_lines == CLASSES


def test_build_labeling_pack_config():
    assert "person" in CLASSES
    assert "motorcycle" in CLASSES
    assert len(CLASSES) == 5

    assert "cctv-bravo" in FEEDS
    assert "bodycam-charlie" in FEEDS
