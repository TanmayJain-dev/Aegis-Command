#!/usr/bin/env python3
"""
Aegis Command - Automated Demo Readiness & Provenance Checker.

Read-only verification script for demo readiness:
For each entry in frontend/public/feeds/index.json:
- Video and detections files exist
- ffprobe video duration is within 0.15s of meta.duration_s
- Video aspect ratio matches meta.width / meta.height
- Detections JSON is <= 500 KB
- 'evaluated' flag is present in meta
- For evaluated:true:
  - weights_sha256 exists in docs/results/raw/checkpoints_manifest.json
  - detections_sha256 matches recomputed canonical body hash
"""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent


def get_video_stream_info(video_path: Path) -> Tuple[float, int, int]:
    """Extract format duration, stream width, and stream height via ffprobe."""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,duration:format=duration",
        "-of", "json",
        str(video_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    info = json.loads(res.stdout)

    fmt_dur = None
    if "format" in info and "duration" in info["format"]:
        fmt_dur = float(info["format"]["duration"])

    streams = info.get("streams", [])
    if not streams:
        raise ValueError(f"No video streams found in {video_path}")

    stream = streams[0]
    stream_w = int(stream["width"])
    stream_h = int(stream["height"])

    stream_dur = float(stream.get("duration", 0.0)) if stream.get("duration") else None
    duration = fmt_dur if fmt_dur is not None else (stream_dur or 0.0)

    return (duration, stream_w, stream_h)


def run_checks() -> Tuple[bool, List[Dict[str, Any]]]:
    index_path = REPO_ROOT / "frontend" / "public" / "feeds" / "index.json"
    manifest_path = REPO_ROOT / "docs" / "results" / "raw" / "checkpoints_manifest.json"

    if not index_path.exists():
        print(f"FAIL: Missing feeds index at {index_path}")
        return False, []

    with open(index_path, "r", encoding="utf-8") as f:
        feeds = json.load(f)

    manifest_hashes = set()
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
            manifest_hashes = set(manifest.values())

    results = []
    all_ok = True

    for feed_entry in feeds:
        feed_id = feed_entry["id"]
        v_rel = feed_entry["video"].lstrip("/")
        d_rel = feed_entry["detections"].lstrip("/")

        v_path = REPO_ROOT / "frontend" / "public" / v_rel
        d_path = REPO_ROOT / "frontend" / "public" / d_rel

        row: Dict[str, Any] = {
            "feed_id": feed_id,
            "video_exists": False,
            "json_exists": False,
            "duration_ok": False,
            "aspect_ok": False,
            "size_ok": False,
            "evaluated_present": False,
            "provenance_ok": "N/A",
            "overall": False,
            "details": [],
        }

        # 1. Existence
        row["video_exists"] = v_path.exists()
        row["json_exists"] = d_path.exists()

        if not row["video_exists"]:
            row["details"].append(f"Missing video: {v_path}")
            all_ok = False
        if not row["json_exists"]:
            row["details"].append(f"Missing detections: {d_path}")
            all_ok = False

        if not row["json_exists"] or not row["video_exists"]:
            results.append(row)
            continue

        # 2. JSON Size & parsing
        sz_bytes = d_path.stat().st_size
        sz_kb = sz_bytes / 1024.0
        row["size_kb"] = round(sz_kb, 1)
        row["size_ok"] = sz_kb <= 500.0
        if not row["size_ok"]:
            row["details"].append(f"JSON size {sz_kb:.1f} KB > 500 KB")
            all_ok = False

        with open(d_path, "r", encoding="utf-8") as f:
            d_data = json.load(f)

        meta = d_data.get("meta", {})
        row["evaluated_present"] = "evaluated" in meta
        if not row["evaluated_present"]:
            row["details"].append("Missing 'evaluated' flag in meta")
            all_ok = False

        is_evaluated = bool(meta.get("evaluated", False))

        # 3. Video metadata & ffprobe checks
        try:
            ff_dur, ff_w, ff_h = get_video_stream_info(v_path)
            row["ff_duration"] = round(ff_dur, 2)
            row["ff_res"] = f"{ff_w}x{ff_h}"

            meta_dur = float(meta.get("duration_s", 0.0))
            dur_diff = abs(ff_dur - meta_dur)
            row["dur_diff"] = round(dur_diff, 3)
            row["duration_ok"] = dur_diff <= 0.15
            if not row["duration_ok"]:
                row["details"].append(f"Duration diff {dur_diff:.3f}s > 0.15s (video={ff_dur:.2f}s, meta={meta_dur:.2f}s)")
                all_ok = False

            meta_w = int(meta.get("width", 1280))
            meta_h = int(meta.get("height", 720))
            ff_aspect = ff_w / ff_h
            meta_aspect = meta_w / meta_h
            row["aspect_ok"] = abs(ff_aspect - meta_aspect) < 0.01
            if not row["aspect_ok"]:
                row["details"].append(f"Aspect ratio mismatch: video {ff_w}x{ff_h} ({ff_aspect:.3f}) vs meta {meta_w}x{meta_h} ({meta_aspect:.3f})")
                all_ok = False
        except Exception as e:
            row["details"].append(f"ffprobe error: {e}")
            all_ok = False

        # 4. Provenance for evaluated:true
        if is_evaluated:
            w_sha = meta.get("weights_sha256")
            in_manifest = w_sha in manifest_hashes
            body = {k: v for k, v in d_data.items() if k != "meta"}
            recomputed_sha = hashlib.sha256(json.dumps(body, sort_keys=True).encode("utf-8")).hexdigest()
            body_hash_match = (meta.get("detections_sha256") == recomputed_sha)

            if in_manifest and body_hash_match:
                row["provenance_ok"] = "PASS"
            else:
                row["provenance_ok"] = "FAIL"
                all_ok = False
                if not in_manifest:
                    row["details"].append(f"Weights SHA-256 {w_sha} not in checkpoints_manifest.json")
                if not body_hash_match:
                    row["details"].append("meta.detections_sha256 does not match recomputed body hash")
        else:
            row["provenance_ok"] = "N/A (zero-shot)"

        row["overall"] = (
            row["video_exists"]
            and row["json_exists"]
            and row["duration_ok"]
            and row["aspect_ok"]
            and row["size_ok"]
            and row["evaluated_present"]
            and (row["provenance_ok"] != "FAIL")
        )
        results.append(row)

    return all_ok, results


def print_table(results: List[Dict[str, Any]]):
    print("=" * 105)
    print(f"{'Feed ID':<16} | {'Files':<7} | {'Duration (diff)':<16} | {'Aspect':<8} | {'Size':<10} | {'Evaluated':<9} | {'Provenance':<16} | {'Status':<6}")
    print("-" * 105)
    for r in results:
        feed_id = r["feed_id"]
        files_str = "PASS" if r["video_exists"] and r["json_exists"] else "FAIL"
        dur_str = f"PASS ({r.get('dur_diff', 0):.3f}s)" if r["duration_ok"] else f"FAIL ({r.get('dur_diff', 0):.3f}s)"
        aspect_str = "PASS" if r["aspect_ok"] else "FAIL"
        sz_str = f"{r.get('size_kb', 0):.1f} KB"
        eval_str = "PASS" if r["evaluated_present"] else "FAIL"
        prov_str = r["provenance_ok"]
        status_str = "PASS" if r["overall"] else "FAIL"

        print(f"{feed_id:<16} | {files_str:<7} | {dur_str:<16} | {aspect_str:<8} | {sz_str:<10} | {eval_str:<9} | {prov_str:<16} | {status_str:<6}")

    print("=" * 105)
    for r in results:
        if r["details"]:
            print(f"[{r['feed_id']}] Issues:")
            for d in r["details"]:
                print(f"  - {d}")


def main():
    print("=== AEGIS COMMAND: DEMO READINESS & PROVENANCE AUDIT ===")
    all_ok, results = run_checks()
    print_table(results)

    if not all_ok:
        print("\nAudit Result: FAIL (Issues detected above)")
        sys.exit(1)
    else:
        print("\nAudit Result: ALL FEEDS DEMO-READY (100% PASS)")
        sys.exit(0)


if __name__ == "__main__":
    main()
