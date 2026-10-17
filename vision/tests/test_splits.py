"""
Unit tests for contiguous time-based dataset partitioning and training configuration.
"""

import json
import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "eval"))
from split_dataset import get_contiguous_splits, split_dataset


def test_contiguous_splits_partition_logic():
    stems = [f"frame_{i:04d}" for i in range(155)]
    splits = get_contiguous_splits(stems)

    assert splits["total"] == 155
    f1 = splits["fold_1"]
    f2 = splits["fold_2"]

    # Fold 1 sizes
    assert f1["train_count"] == 108
    assert f1["buffer_count"] == 5
    assert f1["val_count"] == 42
    assert len(f1["train_stems"]) == 108
    assert len(f1["purged_buffer_stems"]) == 5
    assert len(f1["val_stems"]) == 42

    # Fold 1 zero leakage / disjointness
    s_f1_train = set(f1["train_stems"])
    s_f1_buf = set(f1["purged_buffer_stems"])
    s_f1_val = set(f1["val_stems"])
    assert s_f1_train.isdisjoint(s_f1_buf)
    assert s_f1_train.isdisjoint(s_f1_val)
    assert s_f1_buf.isdisjoint(s_f1_val)
    assert len(s_f1_train | s_f1_buf | s_f1_val) == 155

    # Fold 2 sizes
    assert f2["train_count"] == 108
    assert f2["buffer_count"] == 5
    assert f2["val_count"] == 42

    # Fold 2 zero leakage / disjointness
    s_f2_train = set(f2["train_stems"])
    s_f2_buf = set(f2["purged_buffer_stems"])
    s_f2_val = set(f2["val_stems"])
    assert s_f2_train.isdisjoint(s_f2_buf)
    assert s_f2_train.isdisjoint(s_f2_val)
    assert s_f2_buf.isdisjoint(s_f2_val)
    assert len(s_f2_train | s_f2_buf | s_f2_val) == 155


def test_manifest_and_yaml_generation(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    eval_dir = tmp_path / "eval"
    img_dir = eval_dir / "images"
    lbl_dir = eval_dir / "labels"
    img_dir.mkdir(parents=True)
    lbl_dir.mkdir(parents=True)

    # Create dummy images & labels
    for i in range(155):
        (img_dir / f"frame_{i:04d}.jpg").touch()
        (lbl_dir / f"frame_{i:04d}.txt").write_text("0 0.5 0.5 0.1 0.1\n")

    # Patch paths
    import split_dataset as sd
    monkeypatch.setattr(sd, "IMAGES_DIR", img_dir)
    monkeypatch.setattr(sd, "LABELS_DIR", lbl_dir)
    monkeypatch.setattr(sd, "DATA_DIR", data_dir)

    # Test Fold 1
    m1 = sd.split_dataset(fold=1)
    assert m1["active_fold"] == 1
    assert (data_dir / "split_manifest.json").exists()
    assert (data_dir / "aegis_data.yaml").exists()
    assert len(list((data_dir / "images" / "train").glob("*.jpg"))) == 108
    assert len(list((data_dir / "images" / "val").glob("*.jpg"))) == 42

    # Test Fold 2
    m2 = sd.split_dataset(fold=2)
    assert m2["active_fold"] == 2
    assert len(list((data_dir / "images" / "train").glob("*.jpg"))) == 108
    assert len(list((data_dir / "images" / "val").glob("*.jpg"))) == 42


def test_5fold_contiguous_splits_partition_logic():
    stems = [f"frame_{i:04d}" for i in range(155)]
    splits = get_contiguous_splits(stems, num_folds=5, buffer_frames=4)

    assert splits["total"] == 155
    assert splits["num_folds"] == 5
    assert splits["buffer_frames"] == 4

    all_val_stems = []
    for f in range(1, 6):
        fold = splits[f"fold_{f}"]
        assert fold["val_count"] == 31
        assert len(fold["val_stems"]) == 31
        all_val_stems.extend(fold["val_stems"])

        s_train = set(fold["train_stems"])
        s_buf = set(fold["purged_buffer_stems"])
        s_val = set(fold["val_stems"])

        # Disjointness and completeness
        assert s_train.isdisjoint(s_buf)
        assert s_train.isdisjoint(s_val)
        assert s_buf.isdisjoint(s_val)
        assert len(s_train | s_buf | s_val) == 155

        # Check edge vs interior buffer counts
        if f in (1, 5):
            assert fold["buffer_count"] == 4
            assert fold["train_count"] == 120
        else:
            assert fold["buffer_count"] == 8
            assert fold["train_count"] == 116

    # Verify all 155 stems appear in exactly one validation fold
    assert len(all_val_stems) == 155
    assert set(all_val_stems) == set(stems)


def test_5fold_manifest_and_yaml_generation(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    eval_dir = tmp_path / "eval"
    img_dir = eval_dir / "images"
    lbl_dir = eval_dir / "labels"
    img_dir.mkdir(parents=True)
    lbl_dir.mkdir(parents=True)

    for i in range(155):
        (img_dir / f"frame_{i:04d}.jpg").touch()
        (lbl_dir / f"frame_{i:04d}.txt").write_text("0 0.5 0.5 0.1 0.1\n")

    import split_dataset as sd
    monkeypatch.setattr(sd, "IMAGES_DIR", img_dir)
    monkeypatch.setattr(sd, "LABELS_DIR", lbl_dir)
    monkeypatch.setattr(sd, "DATA_DIR", data_dir)

    # Test Fold 3 (interior fold: 31 val, 8 buffer, 116 train)
    m3 = sd.split_dataset(fold=3, num_folds=5, buffer_frames=4)
    assert m3["active_fold"] == 3
    assert len(list((data_dir / "images" / "train").glob("*.jpg"))) == 116
    assert len(list((data_dir / "images" / "val").glob("*.jpg"))) == 31
    assert len(m3["purged_buffer_stems"]) == 8

