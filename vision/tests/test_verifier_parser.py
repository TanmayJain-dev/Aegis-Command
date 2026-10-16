import sys
import tempfile
from pathlib import Path
import pytest

# Ensure scripts is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from verify_benchmarks import extract_table_rows, extract_floats, find_matching_raw_run


def test_extract_table_rows_basic():
    content = """# Title

## Section A
Some descriptive text.

| Model | Device | AP50 | Recall |
|---|---|---|---|
| **YOLOv8s @ 640px** | CPU | 0.380 | 0.440 |
| **YOLOv8m @ 1280px** | T4 GPU | 0.821 | 0.841 |

## Section B
| Other | Table |
|---|---|
| Value 1 | Value 2 |
"""
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write(content)
        tmp_path = Path(f.name)

    try:
        rows_a = extract_table_rows(tmp_path, "Section A")
        assert len(rows_a) == 2
        assert rows_a[0] == ["**YOLOv8s @ 640px**", "CPU", "0.380", "0.440"]
        assert rows_a[1] == ["**YOLOv8m @ 1280px**", "T4 GPU", "0.821", "0.841"]

        rows_b = extract_table_rows(tmp_path, "section b")
        assert len(rows_b) == 1
        assert rows_b[0] == ["Value 1", "Value 2"]
    finally:
        tmp_path.unlink()


def test_extract_table_rows_missing_section():
    content = """# Document
## Existing Section
| A | B |
|---|---|
| 1 | 2 |
"""
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write(content)
        tmp_path = Path(f.name)

    try:
        rows = extract_table_rows(tmp_path, "Nonexistent Section")
        assert rows == []
    finally:
        tmp_path.unlink()


def test_extract_table_rows_file_not_found():
    with pytest.raises(FileNotFoundError):
        extract_table_rows(Path("/tmp/nonexistent_file_12345.md"), "Section")


def test_extract_table_rows_empty_table():
    content = """# Document
## Section Empty
No table here, just words.
"""
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write(content)
        tmp_path = Path(f.name)

    try:
        rows = extract_table_rows(tmp_path, "Section Empty")
        assert rows == []
    finally:
        tmp_path.unlink()


def test_extract_floats():
    assert extract_floats("AP50: 0.821 [0.772, 0.865]") == [0.821, 0.772, 0.865]
    assert extract_floats("Latency 12.5 ms (CPU)") == [12.5]
    assert extract_floats("No numbers here") == []
    assert extract_floats("Integer 640 is ignored") == []


def test_find_matching_raw_run_missing_dir():
    res = find_matching_raw_run(Path("/tmp/nonexistent_raw_dir"), "yolov8m", 1280)
    assert res is None
