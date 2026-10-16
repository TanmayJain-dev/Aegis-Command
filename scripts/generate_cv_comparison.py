#!/usr/bin/env python3
"""
Aegis Command - Cross-Validation Comparison Table & Metrics Generator.

Reads raw evaluation results from docs/results/raw/ and generates:
1. docs/results/raw/task1_5fold_comparison.md (deterministic markdown)
2. docs/results/raw/cv_metrics_summary.json (for UI badge and frontend consumption)

Enforces zero-memory derivation and strict ddof=1 sample standard deviation.
"""

import json
import math
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_ROOT = REPO_ROOT / "docs" / "results" / "raw"


def sample_std(values: list) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
    return math.sqrt(variance)


def extract_metrics(eval_file: Path) -> dict:
    if not eval_file.exists():
        return None
    with open(eval_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Support both metrics_at_conf_0.25 and top-level class metrics
    m25 = data.get("metrics_at_conf_0.25", data)
    person = m25.get("person", {})
    truck = m25.get("truck", {})

    return {
        "person_ap50": float(person.get("ap50", 0.0)),
        "person_recall": float(person.get("recall", person.get("recall_025", 0.0))),
        "truck_ap50": float(truck.get("ap50", 0.0)),
        "truck_recall": float(truck.get("recall", truck.get("recall_025", 0.0))),
    }


def generate_comparison():
    print(f"Reading raw fold results from {RAW_ROOT}...")

    baseline_folds = []
    best_folds = []
    fixed_folds = []

    for fold in range(1, 6):
        base_f = RAW_ROOT / f"yolov8m_1280px_val_fold{fold}_baseline" / "eval_results.json"
        best_f = RAW_ROOT / f"yolov8m_1280px_val_fold{fold}_finetuned" / "eval_results.json"
        fixed_f = RAW_ROOT / f"yolov8m_1280px_val_fold{fold}_fixed50" / "eval_results.json"

        baseline_folds.append(extract_metrics(base_f))
        best_folds.append(extract_metrics(best_f))
        fixed_folds.append(extract_f := extract_metrics(fixed_f))

    # Calculate summary statistics
    def calc_group_stats(group_list):
        valid = [g for g in group_list if g is not None]
        n = len(valid)
        if n == 0:
            return None
        return {
            "n": n,
            "person_ap50_mean": sum(g["person_ap50"] for g in valid) / n,
            "person_ap50_std": sample_std([g["person_ap50"] for g in valid]),
            "person_recall_mean": sum(g["person_recall"] for g in valid) / n,
            "person_recall_std": sample_std([g["person_recall"] for g in valid]),
            "truck_ap50_mean": sum(g["truck_ap50"] for g in valid) / n,
            "truck_ap50_std": sample_std([g["truck_ap50"] for g in valid]),
            "truck_recall_mean": sum(g["truck_recall"] for g in valid) / n,
            "truck_recall_std": sample_std([g["truck_recall"] for g in valid]),
        }

    base_stats = calc_group_stats(baseline_folds)
    best_stats = calc_group_stats(best_folds)
    fixed_stats = calc_group_stats(fixed_folds)

    # Generate Markdown Content
    md_lines = [
        "# Aegis Command - Cross-Validation Protocol Comparison Table",
        "",
        "## 1. Protocol Overview",
        "",
        "This document presents the empirical comparison across three model evaluation protocols on the 155-frame UAV dataset:",
        "1. **Zero-Shot Pre-trained Baseline** (`yolov8m.pt` @ 1280px, evaluated on each holdout fold).",
        "2. **Fine-Tuned `best.pt`** (optimistic baseline: checkpoint selected via validation set fitness snooping on each holdout fold).",
        "3. **Fixed-Epoch `last.pt`** (headline metric: trained for exactly 50 epochs with `val=False`, zero holdout snooping, evaluated on each holdout fold).",
        "",
        "---",
        "",
        "## 2. Headline Summary Table (Like-for-Like 5-Fold Comparison)",
        "",
        "| Metric | Pre-trained Baseline (Mean ± Std) | Fine-Tuned `best.pt` (Optimistic, Validation-Selected) | Fixed-Epoch `last.pt` (Headline, Zero Snooping) | Delta (`last.pt` vs Baseline) | Status |",
        "|:---|:---:|:---:|:---:|:---:|:---|"
    ]

    def fmt_cell(val, std, n):
        note = "*" if n < 5 else ""
        return f"${val:.4f} \\pm {std:.4f}{note}$"

    if base_stats and best_stats and fixed_stats:
        delta_p_ap50 = fixed_stats["person_ap50_mean"] - base_stats["person_ap50_mean"]
        delta_p_rec = fixed_stats["person_recall_mean"] - base_stats["person_recall_mean"]
        delta_t_ap50 = fixed_stats["truck_ap50_mean"] - base_stats["truck_ap50_mean"]
        delta_t_rec = fixed_stats["truck_recall_mean"] - base_stats["truck_recall_mean"]

        status = "[MEASURED]" if fixed_stats["n"] == 5 else f"[PARTIAL: {fixed_stats['n']}/5 FOLDS]"

        md_lines.extend([
            f"| **Person $\\text{{AP}}_{{50}}$** | {fmt_cell(base_stats['person_ap50_mean'], base_stats['person_ap50_std'], base_stats['n'])} | {fmt_cell(best_stats['person_ap50_mean'], best_stats['person_ap50_std'], best_stats['n'])} | {fmt_cell(fixed_stats['person_ap50_mean'], fixed_stats['person_ap50_std'], fixed_stats['n'])} | ${delta_p_ap50:+.4f}$ ({delta_p_ap50*100:+.2f} pp) | {status} |",
            f"| **Person Recall@0.25** | {fmt_cell(base_stats['person_recall_mean'], base_stats['person_recall_std'], base_stats['n'])} | {fmt_cell(best_stats['person_recall_mean'], best_stats['person_recall_std'], best_stats['n'])} | {fmt_cell(fixed_stats['person_recall_mean'], fixed_stats['person_recall_std'], fixed_stats['n'])} | ${delta_p_rec:+.4f}$ ({delta_p_rec*100:+.2f} pp) | {status} |",
            f"| **Vehicle (Truck) $\\text{{AP}}_{{50}}$** | {fmt_cell(base_stats['truck_ap50_mean'], base_stats['truck_ap50_std'], base_stats['n'])} | {fmt_cell(best_stats['truck_ap50_mean'], best_stats['truck_ap50_std'], best_stats['n'])} | {fmt_cell(fixed_stats['truck_ap50_mean'], fixed_stats['truck_ap50_std'], fixed_stats['n'])} | ${delta_t_ap50:+.4f}$ ({delta_t_ap50*100:+.2f} pp) | {status} |",
            f"| **Vehicle (Truck) Recall@0.25** | {fmt_cell(base_stats['truck_recall_mean'], base_stats['truck_recall_std'], base_stats['n'])} | {fmt_cell(best_stats['truck_recall_mean'], best_stats['truck_recall_std'], best_stats['n'])} | {fmt_cell(fixed_stats['truck_recall_mean'], fixed_stats['truck_recall_std'], fixed_stats['n'])} | ${delta_t_rec:+.4f}$ ({delta_t_rec*100:+.2f} pp) | {status} |",
        ])

    md_lines.extend([
        "",
        f"> **Statistical note**: Sample standard deviation calculated with Bessel's correction ($ddof=1$, $s = \\sqrt{{\\frac{{1}}{{N-1}}\\sum (x_i - \\bar{{x}})^2}}$).",
        "",
        "---",
        "",
        "## 3. Per-Fold Breakdown (Direct from Raw `eval_results.json`)",
        ""
    ])

    for fold in range(1, 6):
        base = baseline_folds[fold - 1]
        best = best_folds[fold - 1]
        fixed = fixed_folds[fold - 1]

        md_lines.append(f"### Fold {fold} (31 Holdout Frames)")
        if base:
            md_lines.append(f"- **Baseline**: Person $\\text{{AP}}_{{50}} = {base['person_ap50']:.4f}$, Recall = ${base['person_recall']:.4f}$ | Truck $\\text{{AP}}_{{50}} = {base['truck_ap50']:.4f}$, Recall = ${base['truck_recall']:.4f}$ [MEASURED]")
        else:
            md_lines.append("- **Baseline**: `UNMEASURED`")

        if best:
            md_lines.append(f"- **Fine-Tuned `best.pt`**: Person $\\text{{AP}}_{{50}} = {best['person_ap50']:.4f}$, Recall = ${best['person_recall']:.4f}$ | Truck $\\text{{AP}}_{{50}} = {best['truck_ap50']:.4f}$, Recall = ${best['truck_recall']:.4f}$ [MEASURED]")
        else:
            md_lines.append("- **Fine-Tuned `best.pt`**: `UNMEASURED`")

        if fixed:
            md_lines.append(f"- **Fixed-Epoch `last.pt`**: Person $\\text{{AP}}_{{50}} = {fixed['person_ap50']:.4f}$, Recall = ${fixed['person_recall']:.4f}$ | Truck $\\text{{AP}}_{{50}} = {fixed['truck_ap50']:.4f}$, Recall = ${fixed['truck_recall']:.4f}$ [MEASURED]")
            if best:
                snooping_ap50 = best["person_ap50"] - fixed["person_ap50"]
                snooping_rec = best["person_recall"] - fixed["person_recall"]
                md_lines.append(f"- *Holdout Snooping Bias*: `best.pt` inflated Person $\\text{{AP}}_{{50}}$ by ${snooping_ap50:+.4f}$ ({snooping_ap50*100:+.2f} pp) and Person Recall by ${snooping_rec:+.4f}$ ({snooping_rec*100:+.2f} pp).")
        else:
            md_lines.append("- **Fixed-Epoch `last.pt`**: `UNMEASURED`")
        md_lines.append("")

    out_md = RAW_ROOT / "task1_5fold_comparison.md"
    out_md.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"✓ Written {out_md}")

    # Generate JSON summary for UI / frontend
    if fixed_stats:
        summary_payload = {
            "headline_model": "last.pt (fixed 50 epochs, val=False, zero holdout snooping)",
            "folds_evaluated": fixed_stats["n"],
            "person_ap50_mean": round(fixed_stats["person_ap50_mean"], 4),
            "person_ap50_std": round(fixed_stats["person_ap50_std"], 4),
            "person_recall_mean": round(fixed_stats["person_recall_mean"], 4),
            "person_recall_std": round(fixed_stats["person_recall_std"], 4),
            "vehicle_ap50_mean": round(fixed_stats["truck_ap50_mean"], 4),
            "vehicle_ap50_std": round(fixed_stats["truck_ap50_std"], 4),
            "optimistic_best_comparison": {
                "person_ap50_mean": round(best_stats["person_ap50_mean"], 4) if best_stats else None,
                "person_ap50_std": round(best_stats["person_ap50_std"], 4) if best_stats else None,
            }
        }
        out_json = RAW_ROOT / "cv_metrics_summary.json"
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(summary_payload, f, indent=2)
        print(f"✓ Written {out_json}")


if __name__ == "__main__":
    generate_comparison()
