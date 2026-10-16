#!/usr/bin/env python3
"""
Aegis Command - Unified Tactical Class Map.

Defines the single source of truth for class IDs across all feeds,
evaluation pipelines, labeling packs, models, and detection generators:
  0: person
  1: car
  2: truck
  3: bus
  4: motorcycle
"""

from typing import Dict, List, Set

# Canonical ID -> Name mapping
CLASS_MAP: Dict[int, str] = {
    0: "person",
    1: "car",
    2: "truck",
    3: "bus",
    4: "motorcycle",
}

# Canonical Name -> ID mapping
CLASS_TO_ID: Dict[str, int] = {name: cid for cid, name in CLASS_MAP.items()}

# Backward-compatible alias for existing evaluation code
CLASS_NAMES: Dict[int, str] = CLASS_MAP

# Canonical COCO (80 classes) -> Aegis Unified Tactical (5 classes) mapping
# COCO classes: 0=person, 2=car, 7=truck, 5=bus, 3=motorcycle
COCO_TO_UNIFIED: Dict[int, int] = {
    0: 0,  # person
    2: 1,  # car
    7: 2,  # truck
    5: 3,  # bus
    3: 4,  # motorcycle
}

# Alias for backward compatibility with existing runner code
COCO_TO_EVAL: Dict[int, int] = COCO_TO_UNIFIED

# Set of allowed string class names for UI & telemetry filters
ALLOWED_CLASSES: Set[str] = set(CLASS_MAP.values())


def get_canonical_class_names() -> List[str]:
    """Returns class names sorted in ascending ID order [0..4]."""
    return [CLASS_MAP[i] for i in range(len(CLASS_MAP))]


def validate_class_id(class_id: int) -> bool:
    """Check if class_id is a valid registered tactical class."""
    return class_id in CLASS_MAP


def validate_class_name(class_name: str) -> bool:
    """Check if class_name is a valid registered tactical class name."""
    return class_name in CLASS_TO_ID
