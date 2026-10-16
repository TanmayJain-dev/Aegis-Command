#!/usr/bin/env python3
"""
Aegis Command - Benchmarks Integrity Verification Script.

Strict Verification Gate:
- Parses docs/BENCHMARKS.md and checks every table row.
- Any row with benchmark numbers MUST have a corresponding raw prediction directory in docs/results/raw/.
- Recomputes metrics from the raw predictions at tolerance 0.001.
- Fails (exit 1) on missing raw sources, number mismatches, or unsourced claims (e.g. Colab/GPU when raw is CPU).
- Configurations marked NOT RUN must have no fabricated metrics.
"""

import sys
import os
import re
import json
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from compute_tables import compute_metrics_for_run


def extract_table_rows(markdown_path: Path, section_header: str) -> List[List[str]]:
    """
    Finds markdown table under a specific section header and parses rows.
    """
    if not markdown_path.exists():
        raise FileNotFoundError(f"Markdown file not found: {markdown_path}")

    content = markdown_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    in_section = False
    in_table = False
    table_rows = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            if section_header.lower() in stripped.lower():
                in_section = True
            elif in_section and (stripped.startswith("## ") or stripped.startswith("# ")):
                break # Reached next major section

        if in_section and stripped.startswith("|"):
            cells = [c.strip() for c in stripped.split("|")[1:-1]]
            if not cells:
                continue
            # Skip separator line (e.g. |---|---|)
            if all(set(c).issubset({"-", ":", " "}) for c in cells):
                in_table = True
                continue
            if in_table:
                table_rows.append(cells)
        elif in_table and not stripped.startswith("|") and stripped != "":
            # End of table
            in_table = False

    return table_rows


def extract_floats(text: str) -> List[float]:
    """
    Extracts all floating point numbers from a text string.
    """
    # Matches decimals like 0.482, 12.5, 44767.0
    matches = re.findall(r"\b\d+\.\d+\b", text)
    return [float(m) for m in matches]


def find_matching_raw_run(raw_root: Path, model_name: str, imgsz: int, split: str = "all", fold: int = 1) -> Optional[Path]:
    """
    Finds directory in docs/results/raw/ where run_meta matches the target configuration.
    """
    if not raw_root.exists():
        return None

    norm_model = model_name.lower().replace("-", "").replace("_", "")

    for r_dir in raw_root.iterdir():
        if not r_dir.is_dir() or not (r_dir / "run_meta.json").exists():
            continue
        try:
            with open(r_dir / "run_meta.json", "r", encoding="utf-8") as f:
                meta = json.load(f)
            meta_weights = Path(meta.get("weights", "")).stem.lower().replace("-", "").replace("_", "")
            meta_imgsz = int(meta.get("imgsz", 0))
            meta_split = meta.get("split", "all")
            meta_fold = int(meta.get("fold", 1))

            matches_model = (
                norm_model in meta_weights
                or (norm_model == "last" and ("fixed50" in r_dir.name.lower() or "last" in meta_weights))
                or (norm_model == "best" and ("finetuned" in r_dir.name.lower() or "best" in meta_weights))
            )
            if matches_model and meta_imgsz == imgsz and meta_split == split:
                if split in ("train", "val") and meta_fold != fold:
                    continue
                return r_dir
        except Exception:
            continue
    return None


def verify_benchmarks(
    benchmarks_path: Path = PROJECT_ROOT / "docs" / "BENCHMARKS.md",
    raw_root: Path = PROJECT_ROOT / "docs" / "results" / "raw",
    labels_dir: Path = PROJECT_ROOT / "vision" / "eval" / "labels",
    manifest_path: Path = PROJECT_ROOT / "vision" / "data" / "split_manifest.json",
    tolerance: float = 0.001,
    fast: bool = False
) -> bool:
    print(f"Verifying benchmarks in {benchmarks_path}...")
    if fast:
        print("[FAST MODE] Active: bootstrap resamples set to 50 for rapid CI/local execution. Release gate requires full mode (1,000 resamples).")
        ci_tolerance = 0.05
    else:
        ci_tolerance = tolerance

    if not benchmarks_path.exists():
        print(f"ERROR: {benchmarks_path} does not exist!", file=sys.stderr)
        return False

    content = benchmarks_path.read_text(encoding="utf-8")

    # Hard rule: Ensure no unsourced mentions of Colab/GPU/T4 next to fabricated numbers
    colab_mentions = re.findall(r"\|.*Colab.*\|", content)
    for line in colab_mentions:
        if "NOT RUN" not in line:
            floats = extract_floats(line)
            if floats:
                print(f"ERROR: Found unsourced Colab numbers in line: {line.strip()}", file=sys.stderr)
                return False

    # Extract all tables under Zero-Shot and Fine-Tuning sections
    zero_shot_rows = extract_table_rows(benchmarks_path, "Zero-Shot")
    holdout_rows = extract_table_rows(benchmarks_path, "Holdout")

    all_rows = zero_shot_rows + holdout_rows
    if not all_rows:
        print("Note: No evaluation table rows found to verify.")
        return True

    verified_count = 0
    not_run_count = 0

    for row in all_rows:
        row_str = " | ".join(row)
        if "NOT RUN" in row_str:
            not_run_count += 1
            # Verify no phantom numbers in NOT RUN rows
            floats = extract_floats(row_str)
            # Allow imgsz like 640, 960, 1280 (not decimals)
            if floats:
                print(f"ERROR: Row marked NOT RUN contains unexpected numeric metric values: {row_str}", file=sys.stderr)
                return False
            continue

        # Non-NOT RUN row: MUST be backed by a verified raw run
        # Extract model and resolution, e.g. **YOLOv8n @ 640px**
        match_cfg = re.search(r"\*\*([A-Za-z0-9_\-]+)\s*@\s*(\d+)px\*\*", row[0])
        if not match_cfg:
            # Check alternative row formatting
            match_cfg = re.search(r"([A-Za-z0-9_\-]+)\s*@\s*(\d+)", row[0])

        if not match_cfg:
            print(f"ERROR: Could not parse model configuration from row cell: '{row[0]}'", file=sys.stderr)
            return False

        model_name = match_cfg.group(1)
        imgsz = int(match_cfg.group(2))

        # Check split / fold
        split = "all"
        fold = 1
        match_fold = re.search(r"fold\s*(\d+)", row_str, re.IGNORECASE)
        if match_fold:
            split = "val"
            fold = int(match_fold.group(1))

        raw_run_dir = find_matching_raw_run(raw_root, model_name, imgsz, split=split, fold=fold)
        if not raw_run_dir:
            print(
                f"ERROR: Row '{row[0]}' has benchmark numbers, but NO raw run directory\n"
                f"exists under {raw_root} for model={model_name}, imgsz={imgsz}, split={split}!",
                file=sys.stderr
            )
            return False

        # Recompute from raw
        try:
            computed = compute_metrics_for_run(raw_run_dir, labels_dir=labels_dir, manifest_path=manifest_path, fast=fast)
        except Exception as e:
            print(f"ERROR: Failed to recompute metrics for {raw_run_dir}: {e}", file=sys.stderr)
            return False

        # Verify device claim
        row_dev = row[1].upper() if len(row) > 1 else ""
        meta_dev = computed.get("device", "").upper()
        if ("GPU" in row_dev or "T4" in row_dev or "COLAB" in row_dev) and "CUDA" not in meta_dev and "GPU" not in meta_dev:
            print(f"ERROR: Markdown claims GPU/Colab for {model_name}, but raw run meta specifies {meta_dev}!", file=sys.stderr)
            return False

        # Check Person AP50 and CI in cell 2
        if len(row) > 2:
            cell_ap50 = row[2]
            floats_ap50 = extract_floats(cell_ap50)
            if not floats_ap50:
                print(f"ERROR: No numeric AP50 found in cell '{cell_ap50}'", file=sys.stderr)
                return False
            ap50_md = floats_ap50[0]
            ap50_expected = computed["person"]["ap50"]
            if abs(ap50_md - ap50_expected) > tolerance:
                print(
                    f"ERROR: Mismatch in Person AP50 for {model_name}@{imgsz}px:\n"
                    f"  Markdown: {ap50_md}\n"
                    f"  Computed: {ap50_expected}\n"
                    f"  Diff:     {abs(ap50_md - ap50_expected):.4f} > {tolerance}",
                    file=sys.stderr
                )
                return False

            if len(floats_ap50) >= 3:
                ci_md = (floats_ap50[1], floats_ap50[2])
                ci_expected = computed["bootstrap_ci_95_person"]["ap50_ci"]
                if abs(ci_md[0] - ci_expected[0]) > ci_tolerance or abs(ci_md[1] - ci_expected[1]) > ci_tolerance:
                    print(
                        f"ERROR: Mismatch in Person AP50 CI for {model_name}@{imgsz}px:\n"
                        f"  Markdown: {ci_md}\n"
                        f"  Computed: {ci_expected}\n"
                        f"  Diff:     max({abs(ci_md[0] - ci_expected[0]):.4f}, {abs(ci_md[1] - ci_expected[1]):.4f}) > {ci_tolerance}",
                        file=sys.stderr
                    )
                    return False

        # Check Person Recall and CI in cell 3
        if len(row) > 3:
            cell_rec = row[3]
            floats_rec = extract_floats(cell_rec)
            if floats_rec:
                rec_md = floats_rec[0]
                rec_expected = computed["person"]["recall_025"]
                if abs(rec_md - rec_expected) > tolerance:
                    print(
                        f"ERROR: Mismatch in Person Recall for {model_name}@{imgsz}px:\n"
                        f"  Markdown: {rec_md}\n"
                        f"  Computed: {rec_expected}",
                        file=sys.stderr
                    )
                    return False

        # Check Truck AP50 in cell 9 if available
        if len(row) > 9:
            floats_truck = extract_floats(row[9])
            if floats_truck:
                truck_md = floats_truck[0]
                truck_expected = computed["truck"]["ap50"]
                if abs(truck_md - truck_expected) > tolerance:
                    print(
                        f"ERROR: Mismatch in Truck AP50 for {model_name}@{imgsz}px:\n"
                        f"  Markdown: {truck_md}\n"
                        f"  Computed: {truck_expected}",
                        file=sys.stderr
                    )
                    return False

        # Check Car AP50 in cell 10 if available
        if len(row) > 10:
            floats_car = extract_floats(row[10])
            if floats_car:
                car_md = floats_car[0]
                car_expected = computed["car"]["ap50"]
                if abs(car_md - car_expected) > tolerance:
                    print(
                        f"ERROR: Mismatch in Car AP50 for {model_name}@{imgsz}px:\n"
                        f"  Markdown: {car_md}\n"
                        f"  Computed: {car_expected}",
                        file=sys.stderr
                    )
                    return False

        verified_count += 1
        print(f"✓ Verified: {model_name} @ {imgsz}px against {raw_run_dir.name}")

    print(f"\nBenchmark Verification Summary:")
    print(f"  Verified runs: {verified_count}")
    print(f"  NOT RUN configs: {not_run_count}")
    print(f"  Discrepancies: 0")
    return True


def main():
    parser = argparse.ArgumentParser(description="Verify benchmark numbers in documentation against raw outputs.")
    parser.add_argument("--benchmarks", default=str(PROJECT_ROOT / "docs" / "BENCHMARKS.md"), help="Path to BENCHMARKS.md")
    parser.add_argument("--raw-root", default=str(PROJECT_ROOT / "docs" / "results" / "raw"), help="Path to raw results directory")
    parser.add_argument("--fast", action="store_true", help="Fast mode: 50 bootstrap resamples instead of 1,000 for local/CI use")
    args = parser.parse_args()

    success = verify_benchmarks(
        benchmarks_path=Path(args.benchmarks),
        raw_root=Path(args.raw_root),
        fast=args.fast
    )

    if not success:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
