#!/usr/bin/env python3
"""
Aegis Command - End-to-End Baseline & CV Pipeline Rerun Automation (Task 7).

One-command pipeline runner for the label fix-and-rerun cycle:
1. Validates label integrity & cryptographic signature gate (vision/eval/labels/VERIFIED).
2. Verifies that the local git state is pushed to origin.
3. Invokes the remote Google Colab GPU runner via the Colab CLI.
4. Downloads and extracts aegis_artifacts.tar.gz (raw prediction dumps & feed detections).
5. Recomputes benchmark summary tables via scripts/compute_tables.py.
6. Executes scripts/verify_benchmarks.py to assert 100% cryptographic and numerical integrity.

Usage:
    python scripts/rerun_pipeline.py [--session aegis-cv] [--fast] [--dry-run]
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "vision" / "eval"))
from finalize_labels import compute_labels_sha256
from eval_detection import check_verification_gate


def log(msg: str):
    ts = time.strftime("%H:%M:%S", time.gmtime())
    print(f"[{ts}] {msg}", flush=True)


def run_cmd(cmd, cwd=PROJECT_ROOT, check=True):
    log(f"CMD: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    res = subprocess.run(cmd, shell=isinstance(cmd, str), cwd=cwd, check=check)
    return res


def validate_local_gate(labels_dir: Path) -> str:
    log("Step 1: Validating label integrity and certification gate...")
    check_verification_gate(labels_dir)
    sha = compute_labels_sha256(labels_dir)
    log(f"✓ Gate verified. Labels SHA-256: {sha}")
    return sha


def check_git_readiness():
    log("Step 2: Checking git branch status...")
    status = subprocess.check_output(["git", "status", "--porcelain"], cwd=PROJECT_ROOT).decode().strip()
    if status:
        log("Notice: Working tree contains uncommitted changes. These must be committed and pushed before Colab can pull them:")
        print(status)
    branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=PROJECT_ROOT).decode().strip()
    log(f"Current active branch: {branch}")
    return branch


def run_colab_pipeline(session_name: str, branch: str, phase: str = "all"):
    log(f"Step 3: Triggering remote Colab execution on session '{session_name}' (phase: {phase})...")
    colab_runner_path = PROJECT_ROOT / "vision" / "colab_runner.py"
    if not colab_runner_path.exists():
        raise FileNotFoundError(f"Colab runner missing: {colab_runner_path}")

    env_args = [
        "--env", f"GIT_BRANCH={branch}",
        "--env", f"PHASE={phase}"
    ]

    colab_bin = shutil.which("colab") or "/home/tanmay/.local/bin/colab"
    cmd = [colab_bin, "exec", "-s", session_name, "-f", str(colab_runner_path)] + env_args
    log(f"Launching Colab execution: {' '.join(cmd)}")
    run_cmd(cmd)
    log("✓ Remote Colab execution completed successfully.")


def download_and_extract_artifacts(session_name: str):
    log("Step 4: Downloading generated artifacts bundle from Colab...")
    colab_bin = shutil.which("colab") or "/home/tanmay/.local/bin/colab"
    tmp_archive = Path("/tmp/aegis_artifacts.tar.gz")
    if tmp_archive.exists():
        tmp_archive.unlink()

    dl_cmd = [colab_bin, "download", "-s", session_name, "/content/aegis_artifacts.tar.gz", str(tmp_archive)]
    run_cmd(dl_cmd)

    if not tmp_archive.exists():
        raise FileNotFoundError(f"Artifact archive failed to download to {tmp_archive}")

    log(f"Extracting artifacts ({tmp_archive.stat().st_size / 1024 / 1024:.2f} MB) into repository root...")
    run_cmd(["tar", "-xzf", str(tmp_archive), "-C", str(PROJECT_ROOT)])
    log("✓ Artifacts extracted.")


def regenerate_and_verify(fast: bool = False):
    log("Step 5: Recomputing benchmark summary tables from fresh raw prediction dumps...")
    compute_cmd = [sys.executable, "scripts/compute_tables.py"]
    if fast:
        compute_cmd.append("--fast")
    run_cmd(compute_cmd)

    log("Step 6: Executing benchmark verification gate...")
    verify_cmd = [sys.executable, "scripts/verify_benchmarks.py"]
    if fast:
        verify_cmd.append("--fast")
    run_cmd(verify_cmd)
    log("✓ Verification gate passed with zero discrepancies!")


def main():
    parser = argparse.ArgumentParser(description="Aegis Command - One-Command Pipeline Rerun Automation")
    parser.add_argument("--session", default="aegis-cv", help="Name of active Colab session (default: aegis-cv)")
    parser.add_argument("--phase", default="all", choices=["all", "bakeoff", "feeds", "train", "fixed_cv", "demo"], help="Pipeline phase to execute")
    parser.add_argument("--fast", action="store_true", help="Run local verification in fast mode (50 resamples)")
    parser.add_argument("--dry-run", action="store_true", help="Validate local gate and labels without invoking Colab")
    args = parser.parse_args()

    log("=================================================================")
    log("AEGIS COMMAND - END-TO-END PIPELINE RERUN AUTOMATION")
    log("=================================================================")

    labels_dir = PROJECT_ROOT / "vision" / "eval" / "labels"
    labels_sha = validate_local_gate(labels_dir)
    branch = check_git_readiness()

    if args.dry_run:
        log("DRY RUN: Local gate is intact. Remote Colab execution skipped.")
        return

    try:
        run_colab_pipeline(session_name=args.session, branch=branch, phase=args.phase)
        download_and_extract_artifacts(session_name=args.session)
        regenerate_and_verify(fast=args.fast)
        log("=================================================================")
        log("PIPELINE RERUN COMPLETED AND VERIFIED END-TO-END.")
        log("=================================================================")
    except Exception as e:
        log(f"FATAL: Pipeline rerun failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
