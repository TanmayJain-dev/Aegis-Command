"""
Unit tests for label finalization and validation gates (vision/eval/finalize_labels.py).

Tests strict schema, geometric, and metadata validation:
- File count mismatch
- Invalid token counts per line
- Non-integer or out-of-bounds class IDs
- Out-of-range coordinates [0, 1]
- Non-positive dimensions
- Duplicate annotation lines
- Small bounding box warnings
- Shape conversion from X-AnyLabeling JSON
- Certification marker generation
"""

import sys
import pytest
from pathlib import Path

# Add vision/eval to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "eval"))

from finalize_labels import (
    ValidationError,
    validate_labels,
    convert_shapes_to_yolo,
    convert_labeling_dir,
    write_verified_marker,
    CLASS_NAMES,
)


def test_validate_labels_success(tmp_path):
    """Test clean validation on valid YOLO annotations."""
    # Create 3 valid files
    f1 = tmp_path / "frame_000001.txt"
    f1.write_text("0 0.500000 0.500000 0.100000 0.200000\n1 0.300000 0.400000 0.050000 0.050000\n")

    f2 = tmp_path / "frame_000002.txt"
    f2.write_text("2 0.800000 0.700000 0.150000 0.250000\n")

    f3 = tmp_path / "frame_000003.txt"
    f3.write_text("")  # Empty frame (0 objects) is allowed

    counts, warnings = validate_labels(tmp_path, expected_count=3, min_px=6)
    assert counts[0] == 1  # person
    assert counts[1] == 1  # car
    assert counts[2] == 1  # truck
    assert counts[3] == 0  # bus
    assert len(warnings) == 0


def test_validate_labels_file_count_mismatch(tmp_path):
    """Test validation raises error if file count does not match expected_count."""
    (tmp_path / "frame_000001.txt").write_text("0 0.5 0.5 0.1 0.1\n")

    with pytest.raises(ValidationError, match="Expected exactly 155 label files"):
        validate_labels(tmp_path, expected_count=155)


def test_validate_labels_invalid_token_count(tmp_path):
    """Test validation fails when a line does not have exactly 5 elements."""
    (tmp_path / "frame_000001.txt").write_text("0 0.5 0.5 0.1\n")  # 4 tokens

    with pytest.raises(ValidationError, match="Invalid token count"):
        validate_labels(tmp_path, expected_count=1)


def test_validate_labels_non_integer_class(tmp_path):
    """Test validation fails when class ID is not an integer."""
    (tmp_path / "frame_000001.txt").write_text("person 0.5 0.5 0.1 0.1\n")

    with pytest.raises(ValidationError, match="Non-integer class ID"):
        validate_labels(tmp_path, expected_count=1)


def test_validate_labels_out_of_bounds_class(tmp_path):
    """Test validation fails when class ID is not in {0, 1, 2, 3}."""
    (tmp_path / "frame_000001.txt").write_text("4 0.5 0.5 0.1 0.1\n")

    with pytest.raises(ValidationError, match="Class ID 4 out of bounds"):
        validate_labels(tmp_path, expected_count=1)

    (tmp_path / "frame_000001.txt").write_text("-1 0.5 0.5 0.1 0.1\n")
    with pytest.raises(ValidationError, match="Class ID -1 out of bounds"):
        validate_labels(tmp_path, expected_count=1)


def test_validate_labels_out_of_range_coords(tmp_path):
    """Test validation fails when coordinates exceed [0.0, 1.0]."""
    # x_center > 1.0
    (tmp_path / "frame_000001.txt").write_text("0 1.05 0.5 0.1 0.1\n")
    with pytest.raises(ValidationError, match="Coordinate x_center=1.05 out of bounds"):
        validate_labels(tmp_path, expected_count=1)

    # y_center < 0.0
    (tmp_path / "frame_000001.txt").write_text("0 0.5 -0.01 0.1 0.1\n")
    with pytest.raises(ValidationError, match="Coordinate y_center=-0.01 out of bounds"):
        validate_labels(tmp_path, expected_count=1)

    # width > 1.0
    (tmp_path / "frame_000001.txt").write_text("0 0.5 0.5 1.2 0.1\n")
    with pytest.raises(ValidationError, match="Coordinate width=1.2 out of bounds"):
        validate_labels(tmp_path, expected_count=1)


def test_validate_labels_non_positive_dimensions(tmp_path):
    """Test validation fails when width or height is <= 0."""
    (tmp_path / "frame_000001.txt").write_text("0 0.5 0.5 0.0 0.1\n")
    with pytest.raises(ValidationError, match="Dimensions must be > 0"):
        validate_labels(tmp_path, expected_count=1)

    (tmp_path / "frame_000001.txt").write_text("0 0.5 0.5 0.1 0.0\n")
    with pytest.raises(ValidationError, match="Dimensions must be > 0"):
        validate_labels(tmp_path, expected_count=1)


def test_validate_labels_duplicate_line(tmp_path):
    """Test validation fails when identical duplicate lines exist in a file."""
    content = (
        "0 0.500000 0.500000 0.100000 0.100000\n"
        "0 0.500000 0.500000 0.100000 0.100000\n"
    )
    (tmp_path / "frame_000001.txt").write_text(content)

    with pytest.raises(ValidationError, match="Duplicate line"):
        validate_labels(tmp_path, expected_count=1)


def test_validate_labels_small_box_warning(tmp_path):
    """Test warning issued when box dimension is under min_px (6px in 1920x1080)."""
    # 2px width in 1920px -> w = 2 / 1920 = 0.0010416
    (tmp_path / "frame_000001.txt").write_text("0 0.5 0.5 0.001 0.1\n")

    counts, warnings = validate_labels(tmp_path, expected_count=1, min_px=6, img_w=1920, img_h=1080)
    assert counts[0] == 1
    assert len(warnings) == 1
    assert "Small box (< 6px)" in warnings[0]


def test_convert_shapes_to_yolo():
    """Test conversion of X-AnyLabeling JSON shapes dictionary."""
    shapes = [
        {
            "label": "person",
            "points": [[100, 100], [200, 300]],
            "shape_type": "rectangle"
        },
        {
            "label": "truck",
            "points": [[300, 400], [500, 600]],
            "shape_type": "rectangle"
        }
    ]

    yolo_lines = convert_shapes_to_yolo(shapes, img_w=1000, img_h=1000)
    assert len(yolo_lines) == 2

    # Person: x_center = 150/1000 = 0.15, y_center = 200/1000 = 0.20, w = 100/1000 = 0.10, h = 200/1000 = 0.20
    assert yolo_lines[0] == "0 0.150000 0.200000 0.100000 0.200000"
    # Truck: x_center = 400/1000 = 0.40, y_center = 500/1000 = 0.50, w = 200/1000 = 0.20, h = 200/1000 = 0.20
    assert yolo_lines[1] == "2 0.400000 0.500000 0.200000 0.200000"


def test_convert_shapes_unknown_class():
    """Test conversion raises error on unknown class label."""
    shapes = [{"label": "motorcycle", "points": [[10, 10], [50, 50]]}]
    with pytest.raises(ValidationError, match="Unknown class label 'motorcycle'"):
        convert_shapes_to_yolo(shapes)


def test_write_verified_marker(tmp_path):
    """Test VERIFIED marker file structure and content."""
    marker_file = tmp_path / "VERIFIED"
    write_verified_marker(marker_file, annotator="Jane Doe", frame_count=155)

    assert marker_file.exists()
    content = marker_file.read_text()
    assert "Annotator: Jane Doe" in content
    assert "Frame Count: 155" in content
    assert "Tool Used: X-AnyLabeling" in content
    assert "Verified Status: APPROVED" in content
