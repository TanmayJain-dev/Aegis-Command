#!/usr/bin/env python3
"""
Aegis Command - Ground Truth Label QA Tool.

Inspects all verified label files in vision/eval/labels/ and flags suspicious annotations:
1. Implausible Person Area: Extreme pixel area (> 25,000 px^2 or < 30 px^2 in 1920x1080).
2. Implausible Aspect Ratio: Person boxes with width > 2.0 * height or height > 6.0 * width.
3. Person-Vehicle Heavy Overlap: Person overlapping a car or truck with IoU >= 0.40 or containment >= 70%.
4. Sub-resolution Boxes: Dimensions < 8 pixels in 1920x1080 space.
5. Duplicates: Identical or near-duplicate annotations (same class, IoU >= 0.90) in the same frame.
6. Out-of-Frame Geometry: Bounding boxes that extend outside [0, 1] normalized coordinates.

Outputs:
- CSV report detailing every suspicious box, frame ID, class, coordinates, and failure reason.
- Annotated diagnostic images with highlighted warning boxes in the scratch review folder.
- Re-signing documentation for annotator verification workflow.
"""

import os
import sys
import csv
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_LABELS_DIR = REPO_ROOT / "vision" / "eval" / "labels"
DEFAULT_IMAGES_DIR = REPO_ROOT / "vision" / "eval" / "images"

CLASS_NAMES = {
    0: "person",
    1: "car",
    2: "truck",
    3: "bus"
}

def box_iou(b1: List[float], b2: List[float]) -> float:
    """Computes IoU between two [x1, y1, x2, y2] normalized boxes."""
    x1 = max(b1[0], b2[0])
    y1 = max(b1[1], b2[1])
    x2 = min(b1[2], b2[2])
    y2 = min(b1[3], b2[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    a1 = max(0.0, b1[2] - b1[0]) * max(0.0, b1[3] - b1[1])
    a2 = max(0.0, b2[2] - b2[0]) * max(0.0, b2[3] - b2[1])
    union = a1 + a2 - inter
    return inter / union if union > 0 else 0.0

def box_intersection_ratio(b1: List[float], b2: List[float]) -> float:
    """Returns ratio of intersection area over b1 area (containment of b1 in b2)."""
    x1 = max(b1[0], b2[0])
    y1 = max(b1[1], b2[1])
    x2 = min(b1[2], b2[2])
    y2 = min(b1[3], b2[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    a1 = max(0.0, b1[2] - b1[0]) * max(0.0, b1[3] - b1[1])
    return inter / a1 if a1 > 0 else 0.0

def inspect_label_file(
    file_path: Path,
    img_w: int = 1920,
    img_h: int = 1080
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Inspects a single YOLO label file and returns (all_boxes, flagged_issues)."""
    raw_lines = [l.strip() for l in file_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    boxes = []
    issues = []
    stem = file_path.stem

    seen_raw_lines = set()

    for idx, line in enumerate(raw_lines):
        # 1. Exact text duplicate check
        if line in seen_raw_lines:
            issues.append({
                "frame": stem,
                "box_idx": idx,
                "class": "unknown",
                "issue_type": "DUPLICATE_LINE",
                "severity": "HIGH",
                "description": f"Exact duplicate label line: '{line}'",
                "box_xyxy_norm": []
            })
        seen_raw_lines.add(line)

        parts = line.split()
        if len(parts) != 5:
            issues.append({
                "frame": stem,
                "box_idx": idx,
                "class": "unknown",
                "issue_type": "SYNTAX_ERROR",
                "severity": "CRITICAL",
                "description": f"Malformed line has {len(parts)} tokens instead of 5",
                "box_xyxy_norm": []
            })
            continue

        try:
            cid = int(parts[0])
            xc, yc, w, h = map(float, parts[1:])
        except ValueError as e:
            issues.append({
                "frame": stem,
                "box_idx": idx,
                "class": "unknown",
                "issue_type": "SYNTAX_ERROR",
                "severity": "CRITICAL",
                "description": f"Non-numeric value: {e}",
                "box_xyxy_norm": []
            })
            continue

        cname = CLASS_NAMES.get(cid, f"class_{cid}")
        x1 = xc - w / 2.0
        y1 = yc - h / 2.0
        x2 = xc + w / 2.0
        y2 = yc + h / 2.0
        w_px = w * img_w
        h_px = h * img_h
        area_px = w_px * h_px

        b_entry = {
            "idx": idx,
            "class_id": cid,
            "class_name": cname,
            "xc": xc,
            "yc": yc,
            "w": w,
            "h": h,
            "box": [x1, y1, x2, y2],
            "w_px": w_px,
            "h_px": h_px,
            "area_px": area_px
        }
        boxes.append(b_entry)

        # 2. Out-of-frame geometry check
        if x1 < -0.005 or y1 < -0.005 or x2 > 1.005 or y2 > 1.005 or w <= 0 or h <= 0:
            issues.append({
                "frame": stem,
                "box_idx": idx,
                "class": cname,
                "issue_type": "OUT_OF_FRAME",
                "severity": "HIGH",
                "description": f"Box boundaries exceed frame [0,1]: [{x1:.3f}, {y1:.3f}, {x2:.3f}, {y2:.3f}]",
                "box_xyxy_norm": [round(v, 4) for v in [x1, y1, x2, y2]]
            })

        # 3. Sub-resolution box (< 8 px in either dimension)
        if w_px < 8.0 or h_px < 8.0:
            issues.append({
                "frame": stem,
                "box_idx": idx,
                "class": cname,
                "issue_type": "TOO_SMALL",
                "severity": "MEDIUM",
                "description": f"Box dimension below 8px: {w_px:.1f}x{h_px:.1f}px (area: {area_px:.1f}px^2)",
                "box_xyxy_norm": [round(v, 4) for v in [x1, y1, x2, y2]]
            })

        # 4. Implausible Person Area
        if cname == "person":
            if area_px > 25000:
                issues.append({
                    "frame": stem,
                    "box_idx": idx,
                    "class": cname,
                    "issue_type": "IMPLAUSIBLE_PERSON_AREA_LARGE",
                    "severity": "CRITICAL",
                    "description": f"Person box area {area_px:.0f}px^2 is implausibly large for aerial feed (>25k px^2, likely mislabeled vehicle)",
                    "box_xyxy_norm": [round(v, 4) for v in [x1, y1, x2, y2]]
                })
            elif area_px < 30:
                issues.append({
                    "frame": stem,
                    "box_idx": idx,
                    "class": cname,
                    "issue_type": "IMPLAUSIBLE_PERSON_AREA_TINY",
                    "severity": "LOW",
                    "description": f"Person box area {area_px:.1f}px^2 is exceptionally small (<30px^2)",
                    "box_xyxy_norm": [round(v, 4) for v in [x1, y1, x2, y2]]
                })

        # 5. Implausible Aspect Ratio for Person
        if cname == "person" and w > 0 and h > 0:
            aspect = h / w
            if aspect < 0.5:
                issues.append({
                    "frame": stem,
                    "box_idx": idx,
                    "class": cname,
                    "issue_type": "IMPLAUSIBLE_ASPECT_RATIO_FLAT",
                    "severity": "HIGH",
                    "description": f"Person box is much wider than tall (h/w = {aspect:.2f} < 0.5; width: {w_px:.1f}px, height: {h_px:.1f}px)",
                    "box_xyxy_norm": [round(v, 4) for v in [x1, y1, x2, y2]]
                })
            elif aspect > 6.0:
                issues.append({
                    "frame": stem,
                    "box_idx": idx,
                    "class": cname,
                    "issue_type": "IMPLAUSIBLE_ASPECT_RATIO_TALL",
                    "severity": "MEDIUM",
                    "description": f"Person box is exceptionally elongated (h/w = {aspect:.2f} > 6.0)",
                    "box_xyxy_norm": [round(v, 4) for v in [x1, y1, x2, y2]]
                })

    # 6. Geometric Near-Duplicates within frame (same class, IoU >= 0.90)
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            b1 = boxes[i]
            b2 = boxes[j]
            if b1["class_id"] == b2["class_id"]:
                iou = box_iou(b1["box"], b2["box"])
                if iou >= 0.90:
                    issues.append({
                        "frame": stem,
                        "box_idx": b2["idx"],
                        "class": b2["class_name"],
                        "issue_type": "GEOMETRIC_DUPLICATE",
                        "severity": "HIGH",
                        "description": f"Near-duplicate box (IoU={iou:.3f}) with box {b1['idx']}",
                        "box_xyxy_norm": [round(v, 4) for v in b2["box"]]
                    })

    # 7. Person Overlapping Vehicle Heavily
    for p_box in [b for b in boxes if b["class_name"] == "person"]:
        for v_box in [b for b in boxes if b["class_name"] in ("car", "truck")]:
            iou = box_iou(p_box["box"], v_box["box"])
            containment = box_intersection_ratio(p_box["box"], v_box["box"])
            if iou >= 0.40 or containment >= 0.70:
                issues.append({
                    "frame": stem,
                    "box_idx": p_box["idx"],
                    "class": "person",
                    "issue_type": "PERSON_VEHICLE_OVERLAP",
                    "severity": "HIGH",
                    "description": f"Person box heavily overlaps {v_box['class_name']} (box {v_box['idx']}): IoU={iou:.2f}, containment={containment*100:.1f}%",
                    "box_xyxy_norm": [round(v, 4) for v in p_box["box"]]
                })

    return boxes, issues


def render_overlay(
    image_path: Path,
    boxes: List[Dict[str, Any]],
    issues: List[Dict[str, Any]],
    output_path: Path
):
    """Draws visual inspection overlay highlighting flagged suspicious annotations."""
    try:
        import cv2
    except ImportError:
        return

    if not image_path.exists():
        return

    im = cv2.imread(str(image_path))
    if im is None:
        return

    h, w = im.shape[:2]
    flagged_indices = {iss["box_idx"]: iss for iss in issues}

    # First draw normal boxes in thin cyan
    for b in boxes:
        idx = b["idx"]
        if idx in flagged_indices:
            continue
        x1 = int(b["box"][0] * w)
        y1 = int(b["box"][1] * h)
        x2 = int(b["box"][2] * w)
        y2 = int(b["box"][3] * h)
        cv2.rectangle(im, (x1, y1), (x2, y2), (255, 200, 0), 1)

    # Now draw flagged boxes in thick red or magenta with issue label
    for b in boxes:
        idx = b["idx"]
        if idx not in flagged_indices:
            continue
        iss = flagged_indices[idx]
        x1 = int(b["box"][0] * w)
        y1 = int(b["box"][1] * h)
        x2 = int(b["box"][2] * w)
        y2 = int(b["box"][3] * h)

        color = (0, 0, 255) if iss["severity"] in ("CRITICAL", "HIGH") else (0, 165, 255)
        cv2.rectangle(im, (x1, y1), (x2, y2), color, 3)
        label_text = f"FLAG: {iss['issue_type']} ({b['class_name']})"
        cv2.putText(im, label_text, (x1, max(15, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)

    # Header banner
    cv2.rectangle(im, (0, 0), (w, 30), (0, 0, 0), -1)
    banner_txt = f"{image_path.name} - {len(boxes)} total boxes, {len(issues)} flagged issues"
    cv2.putText(im, banner_txt, (15, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), im)


def run_qa(
    labels_dir: Path = DEFAULT_LABELS_DIR,
    images_dir: Path = DEFAULT_IMAGES_DIR,
    out_csv: Path = Path("docs/results/raw/task1_label_qa_report.csv"),
    scratch_dir: Path = Path("scratch/label_qa")
) -> Dict[str, Any]:
    """Runs complete QA suite across all label files."""
    if not labels_dir.exists():
        raise FileNotFoundError(f"Labels directory not found: {labels_dir}")

    txt_files = sorted(labels_dir.glob("*.txt"))
    all_issues = []
    frames_with_issues = set()
    total_boxes = 0

    scratch_dir.mkdir(parents=True, exist_ok=True)
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("AEGIS COMMAND - GROUND TRUTH LABEL QA SUITE")
    print(f"Target Labels Directory: {labels_dir}")
    print(f"Total Frame Files:       {len(txt_files)}")
    print("=" * 70)

    for tf in txt_files:
        boxes, issues = inspect_label_file(tf)
        total_boxes += len(boxes)
        if issues:
            frames_with_issues.add(tf.stem)
            for iss in issues:
                all_issues.append(iss)
                # Render overlay image
                img_p = images_dir / f"{tf.stem}.jpg"
                if img_p.exists():
                    out_img = scratch_dir / f"{tf.stem}_qa.jpg"
                    render_overlay(img_p, boxes, issues, out_img)

    # Write CSV Report
    fieldnames = ["frame", "box_idx", "class", "issue_type", "severity", "description", "box_xyxy_norm"]
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for iss in all_issues:
            writer.writerow(iss)

    # Issue breakdown summary
    type_counts = {}
    sev_counts = {}
    for iss in all_issues:
        type_counts[iss["issue_type"]] = type_counts.get(iss["issue_type"], 0) + 1
        sev_counts[iss["severity"]] = sev_counts.get(iss["severity"], 0) + 1

    summary = {
        "total_frames_inspected": len(txt_files),
        "total_boxes_inspected": total_boxes,
        "total_issues_flagged": len(all_issues),
        "frames_with_issues_count": len(frames_with_issues),
        "breakdown_by_severity": sev_counts,
        "breakdown_by_type": type_counts,
        "csv_report": str(out_csv),
        "overlays_dir": str(scratch_dir)
    }

    summary_json_path = out_csv.with_suffix(".json")
    with open(summary_json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"\nQA Complete!")
    print(f"Total Boxes Inspected: {total_boxes}")
    print(f"Issues Flagged:        {len(all_issues)} across {len(frames_with_issues)} frames")
    print("\nBreakdown by Severity:")
    for sev, cnt in sorted(sev_counts.items()):
        print(f"  {sev:<10}: {cnt}")
    print("\nBreakdown by Issue Type:")
    for itype, cnt in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {itype:<30}: {cnt}")
    print(f"\nCSV Report Saved:   {out_csv}")
    print(f"Summary JSON Saved: {summary_json_path}")
    print(f"Overlays Directory: {scratch_dir}")

    return summary


def print_resigning_instructions():
    """Prints clear instructions on how to re-sign VERIFIED marker while keeping historical log."""
    print("\n" + "=" * 70)
    print("HOW TO RE-SIGN THE VERIFIED HASH AFTER ANNOTATOR FIXES")
    print("=" * 70)
    print("""
When annotator Prachi finishes correcting flagged labels:
1. Run label validation gate to confirm geometric validity:
   python3 vision/eval/finalize_labels.py --skip-convert

2. To re-sign vision/eval/labels/VERIFIED preserving the previous entry:
   Append the new verification block to the bottom of the file while updating
   the active top block, or record the audit chain as follows:

   Annotator: Prachi
   Date: <YYYY-MM-DD>
   Base Commit: <current_git_commit>
   Tool Used: X-AnyLabeling
   Frame Count: 155
   SHA256: <new_sha256_checksum>
   Verified Status: APPROVED
   Revision: 2 (Post-QA Corrections)

   # --- Historical Certification Ledger ---
   # Entry 1:
   # Annotator: Prachi
   # Date: 2026-10-13
   # Base Commit: 79840d786ba8e8cbed7be4991d14241a0c28426b
   # SHA256: a7fb1542fdb1e911299bb73971abc3abeea4aed675ef2a172933a4b168f595fc
   # Status: SUPERSEDED

3. Note: eval_detection.py reads the FIRST occurrence of 'SHA256:', so the active
   approved checksum must remain at the top of the file.
""")
    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Aegis Ground Truth Label QA Tool")
    parser.add_argument("--labels-dir", default=str(DEFAULT_LABELS_DIR))
    parser.add_argument("--images-dir", default=str(DEFAULT_IMAGES_DIR))
    parser.add_argument("--csv", default="docs/results/raw/task1_label_qa_report.csv")
    parser.add_argument("--scratch-dir", default="scratch/label_qa")
    args = parser.parse_args()

    run_qa(
        labels_dir=Path(args.labels_dir),
        images_dir=Path(args.images_dir),
        out_csv=Path(args.csv),
        scratch_dir=Path(args.scratch_dir)
    )
    print_resigning_instructions()
