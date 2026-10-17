#!/usr/bin/env python3
"""
Unit tests for the Unified Tactical Class Map.
Ensures zero class ID divergence across evaluation, models, labeling packs, and UI.
"""

import sys
import pytest
from pathlib import Path

# Add vision/eval to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "eval"))

from class_map import (
    CLASS_MAP,
    CLASS_TO_ID,
    CLASS_NAMES,
    COCO_TO_UNIFIED,
    ALLOWED_CLASSES,
    get_canonical_class_names,
    validate_class_id,
    validate_class_name,
)


def test_canonical_class_map_invariants():
    """Verify class map defines exactly the 5 required tactical classes in canonical order."""
    expected = {
        0: "person",
        1: "car",
        2: "truck",
        3: "bus",
        4: "motorcycle",
    }
    assert CLASS_MAP == expected, f"Class map mismatch: expected {expected}, got {CLASS_MAP}"
    assert len(CLASS_MAP) == 5
    assert get_canonical_class_names() == ["person", "car", "truck", "bus", "motorcycle"]


def test_bidirectional_consistency():
    """Verify CLASS_TO_ID perfectly inverts CLASS_MAP."""
    for cid, name in CLASS_MAP.items():
        assert CLASS_TO_ID[name] == cid
        assert validate_class_id(cid) is True
        assert validate_class_name(name) is True

    assert validate_class_id(999) is False
    assert validate_class_name("airplane") is False


def test_coco_remapping_validity():
    """Verify COCO remapping maps standard COCO 80 categories into valid unified IDs."""
    coco_expected = {
        0: 0,  # person -> person
        2: 1,  # car -> car
        7: 2,  # truck -> truck
        5: 3,  # bus -> bus
        3: 4,  # motorcycle -> motorcycle
    }
    assert COCO_TO_UNIFIED == coco_expected
    for coco_id, unified_id in COCO_TO_UNIFIED.items():
        assert unified_id in CLASS_MAP, f"COCO id {coco_id} maps to invalid target {unified_id}"


def test_allowed_classes_set():
    """Verify ALLOWED_CLASSES matches all tactical classes."""
    assert ALLOWED_CLASSES == {"person", "car", "truck", "bus", "motorcycle"}


def test_existing_labels_compatible():
    """Verify all existing ground truth labels use valid class IDs within CLASS_MAP."""
    labels_dir = Path(__file__).resolve().parent.parent / "eval" / "labels"
    if not labels_dir.exists():
        pytest.skip("Labels directory not found")

    for txt_path in labels_dir.glob("*.txt"):
        if txt_path.name == "VERIFIED":
            continue
        for line in txt_path.read_text(encoding="utf-8").splitlines():
            parts = line.strip().split()
            if not parts:
                continue
            cid = int(parts[0])
            assert cid in CLASS_MAP, f"Label {txt_path.name} contains invalid class ID {cid} (not in CLASS_MAP)"
