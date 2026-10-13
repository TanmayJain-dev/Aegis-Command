#!/usr/bin/env python3
"""
Finalize human-verified evaluation labels for Aegis Command.

Reads X-AnyLabeling JSON annotations from local_assets/labeling/,
converts them to YOLO-format .txt files in vision/eval/labels/,
and executes strict schema and geometric validation gates.

Validation checks:
  1. Exactly 155 label files present (empty file allowed for frames with 0 objects).
  2. Exactly 5 numbers per non-empty line (class_id, x_center, y_center, width, height).
  3. Class IDs strictly within {0, 1, 2, 3} (person, car, truck, bus).
  4. Coordinates normalized within [0.0, 1.0].
  5. Width and height strictly > 0.
  6. No duplicate lines within any label file.
  7. Warning issued for bounding boxes smaller than 6 px in 1920x1080 space.

Certification Gate:
  Writes vision/eval/labels/VERIFIED ONLY when invoked with --annotator "Full Name"
  and all validation checks pass.
"""

import os
import sys
import json
import hashlib
import argparse
import datetime
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Optional

CLASS_NAMES = ["person", "car", "truck", "bus"]
CLASS_TO_ID = {name: i for i, name in enumerate(CLASS_NAMES)}

class ValidationError(Exception):
    """Raised when label files violate formatting or geometric integrity."""
    pass


def convert_shapes_to_yolo(shapes: List[dict], img_w: int = 1920, img_h: int = 1080) -> Tuple[List[str], int]:
    """
    Convert X-AnyLabeling shape objects into YOLO format string lines.
    Clamps points to image bounds [0, img_w] x [0, img_h] and reports count of clamped points.
    """
    yolo_lines = []
    clamped_count = 0
    for s in shapes:
        label = s.get("label", "").strip().lower()
        if label not in CLASS_TO_ID:
            raise ValidationError(f"Unknown class label '{label}'. Must be one of {CLASS_NAMES}")

        cls_id = CLASS_TO_ID[label]
        points = s.get("points", [])
        if not points or len(points) < 2:
            raise ValidationError(f"Invalid shape points for {label}: {points}")

        xs = []
        ys = []
        for p in points:
            orig_x, orig_y = float(p[0]), float(p[1])
            cx = max(0.0, min(float(img_w), orig_x))
            cy = max(0.0, min(float(img_h), orig_y))
            if cx != orig_x or cy != orig_y:
                clamped_count += 1
            xs.append(cx)
            ys.append(cy)

        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)

        box_w = x_max - x_min
        box_h = y_max - y_min

        if box_w <= 0.0 or box_h <= 0.0:
            raise ValidationError(f"Box collapsed to zero dimension after clamping for {label}: {points}")

        x_center = (x_min + x_max) / 2.0 / img_w
        y_center = (y_min + y_max) / 2.0 / img_h
        w_norm = box_w / img_w
        h_norm = box_h / img_h

        yolo_lines.append(f"{cls_id} {x_center:.6f} {y_center:.6f} {w_norm:.6f} {h_norm:.6f}")

    return yolo_lines, clamped_count


def convert_labeling_dir(input_dir: Path, output_dir: Path) -> Tuple[int, int]:
    """Convert all X-AnyLabeling JSONs in input_dir to YOLO .txt files in output_dir. Returns (converted_count, total_clamped)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_files = sorted(input_dir.glob("*.json"))
    if not json_files:
        raise ValidationError(f"No JSON files found in {input_dir}")

    converted_count = 0
    total_clamped = 0
    for jf in json_files:
        with open(jf, "r", encoding="utf-8") as f:
            data = json.load(f)

        img_w = data.get("imageWidth", 1920) or 1920
        img_h = data.get("imageHeight", 1080) or 1080
        shapes = data.get("shapes", [])

        lines, clamped = convert_shapes_to_yolo(shapes, img_w=img_w, img_h=img_h)
        total_clamped += clamped

        out_txt = output_dir / f"{jf.stem}.txt"
        with open(out_txt, "w", encoding="utf-8") as f:
            if lines:
                f.write("\n".join(lines) + "\n")

        converted_count += 1

    return converted_count, total_clamped


def validate_labels(
    labels_dir: Path,
    expected_count: int = 155,
    min_px: int = 6,
    img_w: int = 1920,
    img_h: int = 1080
) -> Tuple[Dict[int, int], List[str]]:
    """
    Validate all YOLO label files in labels_dir.
    Returns (class_counts, warnings).
    Raises ValidationError on schema or geometric violations.
    """
    txt_files = sorted(labels_dir.glob("*.txt"))
    if len(txt_files) != expected_count:
        raise ValidationError(
            f"Expected exactly {expected_count} label files in {labels_dir}, but found {len(txt_files)}"
        )

    class_counts = {0: 0, 1: 0, 2: 0, 3: 0}
    warnings = []

    for tf in txt_files:
        with open(tf, "r", encoding="utf-8") as f:
            raw_lines = [l.strip() for l in f if l.strip()]

        seen_lines = set()
        for idx, line in enumerate(raw_lines, 1):
            if line in seen_lines:
                raise ValidationError(f"Duplicate line in {tf.name} line {idx}: '{line}'")
            seen_lines.add(line)

            parts = line.split()
            if len(parts) != 5:
                raise ValidationError(
                    f"Invalid token count ({len(parts)} != 5) in {tf.name} line {idx}: '{line}'"
                )

            try:
                cls_id = int(parts[0])
            except ValueError:
                raise ValidationError(f"Non-integer class ID '{parts[0]}' in {tf.name} line {idx}")

            if cls_id not in (0, 1, 2, 3):
                raise ValidationError(
                    f"Class ID {cls_id} out of bounds (must be 0..3) in {tf.name} line {idx}"
                )

            try:
                x_c, y_c, w, h = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
            except ValueError:
                raise ValidationError(f"Non-float coordinate values in {tf.name} line {idx}: '{line}'")

            for name, val in [("x_center", x_c), ("y_center", y_c), ("width", w), ("height", h)]:
                if not (0.0 <= val <= 1.0):
                    raise ValidationError(
                        f"Coordinate {name}={val} out of bounds [0.0, 1.0] in {tf.name} line {idx}"
                    )

            if w <= 0.0 or h <= 0.0:
                raise ValidationError(
                    f"Dimensions must be > 0 (got w={w}, h={h}) in {tf.name} line {idx}"
                )

            # Warning check on small boxes (< 6 px in 1920x1080)
            w_px = w * img_w
            h_px = h * img_h
            if w_px < min_px or h_px < min_px:
                warnings.append(
                    f"[WARN] Small box (< {min_px}px) in {tf.name}: cls={cls_id} size={w_px:.1f}x{h_px:.1f}px"
                )

            class_counts[cls_id] += 1

    return class_counts, warnings


def count_labels_in_dir(labels_dir: Path) -> Dict[int, int]:
    """Count annotations per class across all text files in labels_dir."""
    counts = {0: 0, 1: 0, 2: 0, 3: 0}
    if not labels_dir.exists():
        return counts

    for tf in labels_dir.glob("*.txt"):
        with open(tf, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) == 5:
                    try:
                        cid = int(parts[0])
                        if cid in counts:
                            counts[cid] += 1
                    except ValueError:
                        pass
    return counts


def get_git_commit() -> str:
    """Retrieve current Git commit SHA."""
    try:
        res = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception:
        return "UNKNOWN_COMMIT"


def compute_labels_sha256(labels_dir: Path) -> str:
    """Compute deterministic SHA256 checksum across all sorted .txt label files."""
    hasher = hashlib.sha256()
    for txt_path in sorted(labels_dir.glob("*.txt")):
        hasher.update(txt_path.name.encode("utf-8"))
        hasher.update(b"\n")
        hasher.update(txt_path.read_bytes())
    return hasher.hexdigest()


def find_unchanged_frames(final_dir: Path, draft_dir: Path) -> List[str]:
    """Find frame file names whose annotations are identical to draft."""
    unchanged = []
    for f in sorted(final_dir.glob("*.txt")):
        df = draft_dir / f.name
        if not df.exists():
            continue

        def parse_boxes(p: Path):
            boxes = []
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                if len(parts) == 5:
                    boxes.append((int(parts[0]), round(float(parts[1]), 4), round(float(parts[2]), 4), round(float(parts[3]), 4), round(float(parts[4]), 4)))
            return sorted(boxes)

        if parse_boxes(f) == parse_boxes(df):
            unchanged.append(f.name)
    return unchanged


def write_verified_marker(marker_path: Path, annotator: str, frame_count: int = 155, sha256_hash: Optional[str] = None) -> str:
    """Write the VERIFIED certification marker file with annotator metadata and labels SHA256."""
    commit_sha = get_git_commit()
    today_str = datetime.date.today().isoformat()
    if sha256_hash is None:
        sha256_hash = compute_labels_sha256(marker_path.parent)

    content = (
        f"Annotator: {annotator}\n"
        f"Date: {today_str}\n"
        f"Base Commit: {commit_sha}\n"
        f"Tool Used: X-AnyLabeling\n"
        f"Frame Count: {frame_count}\n"
        f"SHA256: {sha256_hash}\n"
        f"Verified Status: APPROVED\n"
    )

    marker_path.parent.mkdir(parents=True, exist_ok=True)
    with open(marker_path, "w", encoding="utf-8") as f:
        f.write(content)
    return sha256_hash


def main():
    parser = argparse.ArgumentParser(description="Finalize and validate human-labeled ground truth.")
    parser.add_argument("--input", default="local_assets/labeling", help="Path to X-AnyLabeling annotations")
    parser.add_argument("--output", default="vision/eval/labels", help="Output directory for YOLO labels")
    parser.add_argument("--draft-dir", default="vision/eval/labels_draft", help="Directory of initial draft labels")
    parser.add_argument("--annotator", default=None, help="Full name of human annotator (required to write VERIFIED)")
    parser.add_argument("--confirm-unchanged", action="store_true", help="Print frames whose annotations are identical to draft labels")
    parser.add_argument("--skip-convert", action="store_true", help="Skip conversion and run validation only")
    args = parser.parse_args()

    input_dir = Path(args.input)
    output_dir = Path(args.output)
    draft_dir = Path(args.draft_dir)

    print("================================================================")
    print("AEGIS GROUND TRUTH FINALIZATION & VALIDATION GATE")
    print(f"Input JSON directory:  {input_dir}")
    print(f"Output YOLO directory: {output_dir}")
    print("================================================================")

    if not args.skip_convert:
        if not input_dir.exists():
            print(f"Error: input labeling directory not found: {input_dir}", file=sys.stderr)
            sys.exit(1)
        print(f"Converting X-AnyLabeling JSON annotations from {input_dir}...")
        try:
            converted, clamped = convert_labeling_dir(input_dir, output_dir)
            print(f"Successfully converted {converted} files to {output_dir}.")
            print(f"Points clamped to image bounds: {clamped}")
        except Exception as e:
            print(f"Conversion failed: {e}", file=sys.stderr)
            sys.exit(1)

    print("\nExecuting validation gate...")
    try:
        final_counts, warnings = validate_labels(output_dir, expected_count=155)
        print("Validation PASSED: All 155 label files satisfy geometric and schema rules.")
    except ValidationError as ve:
        print(f"VALIDATION FAILED: {ve}", file=sys.stderr)
        sys.exit(1)

    if warnings:
        print(f"\nRecorded {len(warnings)} geometric warnings:")
        for w in warnings[:10]:
            print(f"  {w}")
        if len(warnings) > 10:
            print(f"  ... and {len(warnings) - 10} more warnings.")

    draft_counts = count_labels_in_dir(draft_dir)

    print("\n----------------------------------------------------------------")
    print("CLASS DISTRIBUTION COMPARISON: DRAFT vs FINAL (VERIFIED)")
    print("----------------------------------------------------------------")
    print(f"{'Class ID':<10} {'Class Name':<12} {'Draft Count':<14} {'Final Count':<14} {'Delta':<10}")
    print("-" * 62)

    total_draft = 0
    total_final = 0
    for cid in (0, 1, 2, 3):
        cname = CLASS_NAMES[cid]
        d_cnt = draft_counts.get(cid, 0)
        f_cnt = final_counts.get(cid, 0)
        delta = f_cnt - d_cnt
        total_draft += d_cnt
        total_final += f_cnt
        print(f"{cid:<10} {cname:<12} {d_cnt:<14} {f_cnt:<14} {delta:+d}")

    print("-" * 62)
    print(f"{'TOTAL':<22} {total_draft:<14} {total_final:<14} {total_final - total_draft:+d}")
    print("----------------------------------------------------------------")

    if args.confirm_unchanged:
        unchanged = find_unchanged_frames(output_dir, draft_dir)
        print(f"\n[CONFIRM-UNCHANGED] Identical to draft ({len(unchanged)} frames):")
        for fname in unchanged:
            print(f"  {fname}")

    verified_file = output_dir / "VERIFIED"
    if args.annotator:
        annotator_clean = args.annotator.strip()
        if not annotator_clean:
            print("Error: --annotator must provide a non-empty human name.", file=sys.stderr)
            sys.exit(1)
        sha256_hex = write_verified_marker(verified_file, annotator_clean, frame_count=155)
        print(f"\n[CERTIFICATION GATE] Created marker file: {verified_file}")
        print(f"  Annotator: {annotator_clean}")
        print(f"  SHA256: {sha256_hex}")
        print("  Status: APPROVED")
    else:
        print("\n[NOTE] --annotator flag was not provided.")
        print(f"Verification marker ({verified_file}) was NOT written.")
        print("To create the VERIFIED gate after human labeling, run:")
        print(f"  python vision/eval/finalize_labels.py --annotator \"<Your Full Name>\"")


if __name__ == "__main__":
    main()
