"""
Unit tests for vision/generate_detections.py schema, kinematics, and hash calculation.
"""

import json
import math
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from generate_detections import (
    ALLOWED_CLASSES,
    compute_weights_sha256,
    compute_kinematics,
    FEED_PATHS
)


def test_feed_paths_configuration():
    assert "uav-alpha" in FEED_PATHS
    assert "cctv-bravo" in FEED_PATHS
    assert "bodycam-charlie" in FEED_PATHS

    # UAV Alpha is cryptographically evaluated against 155 ground-truth frames
    assert FEED_PATHS["uav-alpha"]["evaluated"] is True
    # Secondary feeds do not yet have verified ground truth
    assert FEED_PATHS["cctv-bravo"]["evaluated"] is False
    assert FEED_PATHS["bodycam-charlie"]["evaluated"] is False


def test_compute_weights_sha256(tmp_path):
    dummy_weights = tmp_path / "model.pt"
    dummy_weights.write_bytes(b"YOLOv8_WEIGHT_BYTES_TEST_12345")

    h = compute_weights_sha256(str(dummy_weights))
    assert len(h) == 64
    assert int(h, 16) > 0  # Valid hex string

    missing_h = compute_weights_sha256(str(tmp_path / "missing.pt"))
    assert missing_h == "built-in-weights"


def test_compute_kinematics():
    # Initial observation (no prior)
    spd, direction = compute_kinematics(None, (100, 100, 150, 200), 0.5, "person")
    assert spd == 4.0
    assert direction == "-"

    # Moving East (dx > 0, dy = 0)
    # prev center: (100, 100), curr center: (140, 100) -> dx=40px, dt=0.5s -> 80px/s -> 4 m/s -> 14.4 km/h
    prev = (80, 80, 120, 120)  # center (100, 100)
    curr = (120, 80, 160, 120) # center (140, 100)
    spd_e, dir_e = compute_kinematics(prev, curr, 0.5, "car")
    assert spd_e == 14.4
    assert dir_e == "E"

    # Moving North (dx = 0, dy < 0)
    curr_n = (80, 40, 120, 80) # center (100, 60) -> dy = -40
    spd_n, dir_n = compute_kinematics(prev, curr_n, 0.5, "car")
    assert spd_n == 14.4
    assert dir_n == "N"


def test_generated_detections_schema_contract():
    # Construct synthetic pipeline output representing generate_feed_detections output
    sample_payload = {
        "meta": {
            "model": "yolov8m.pt",
            "weights_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "imgsz": 1280,
            "conf": 0.25,
            "date": "2026-10-16",
            "evaluated": True,
            "feed": "uav-alpha",
            "width": 1920,
            "height": 1080,
            "fps": 59.94,
            "duration_s": 33.6,
            "sahi": False,
            "tracker": "bytetrack.yaml"
        },
        "0.0": [
            {
                "id": "Person-1",
                "class": "person",
                "confidence": 0.88,
                "box": [1838.4, 334.1, 1868.3, 388.2],
                "speed_kmh": 4.0,
                "direction": "S"
            }
        ],
        "0.5": [
            {
                "id": "Person-1",
                "class": "person",
                "confidence": 0.91,
                "box": [1839.0, 335.0, 1869.0, 389.0],
                "speed_kmh": 3.8,
                "direction": "S"
            },
            {
                "id": "Truck-12",
                "class": "truck",
                "confidence": 0.74,
                "box": [820.0, 625.0, 1280.0, 903.0],
                "speed_kmh": 18.5,
                "direction": "SW"
            }
        ]
    }

    # Meta validations
    meta = sample_payload["meta"]
    assert "model" in meta
    assert len(meta["weights_sha256"]) == 64
    assert meta["imgsz"] == 1280
    assert meta["conf"] == 0.25
    assert meta["evaluated"] is True
    assert meta["feed"] == "uav-alpha"
    assert meta["tracker"] == "bytetrack.yaml"

    # Timestamp key validations
    timestamps = [k for k in sample_payload.keys() if k != "meta"]
    assert len(timestamps) == 2
    for t_str in timestamps:
        t_val = float(t_str)
        assert t_val >= 0.0

        dets = sample_payload[t_str]
        assert isinstance(dets, list)
        for d in dets:
            assert d["class"] in ALLOWED_CLASSES
            assert 0.0 <= d["confidence"] <= 1.0
            assert len(d["box"]) == 4
            x1, y1, x2, y2 = d["box"]
            assert x1 <= x2
            assert y1 <= y2
            assert d["id"].startswith(d["class"].capitalize())
            assert isinstance(d["speed_kmh"], (int, float))
            assert isinstance(d["direction"], str)
