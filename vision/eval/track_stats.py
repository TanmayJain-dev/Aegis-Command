#!/usr/bin/env python3
"""
Computes track and detection statistics from legacy/baseline detections.json.
Provides grounded distribution baselines without claiming unverified accuracy metrics.
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, Any
import numpy as np


def compute_track_stats(detections_path: Path) -> Dict[str, Any]:
    with open(detections_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    track_obs = defaultdict(list)
    all_confs = []
    class_counts = defaultdict(int)
    total_detections = 0

    timestamps = [float(k) for k in data.keys()]
    if not timestamps:
        return {"error": "Empty detections file"}

    min_ts = min(timestamps)
    max_ts = max(timestamps)
    duration_s = max_ts - min_ts

    for ts, dets in data.items():
        t = float(ts)
        for d in dets:
            total_detections += 1
            track_obs[d["id"]].append(t)
            all_confs.append(float(d.get("confidence", 0.0)))
            class_counts[d.get("class", "unknown")] += 1

    track_lengths = [len(v) for v in track_obs.values()]
    track_durations = [max(v) - min(v) for v in track_obs.values()]
    short_tracks = sum(1 for length in track_lengths if length <= 10)
    total_tracks = len(track_obs)

    stats = {
        "source_file": str(detections_path),
        "video_duration_s": round(duration_s, 2),
        "total_detections": total_detections,
        "total_tracks": total_tracks,
        "detections_per_second": round(total_detections / duration_s, 2) if duration_s > 0 else 0.0,
        "track_length_obs": {
            "median": float(np.median(track_lengths)) if track_lengths else 0.0,
            "mean": round(float(np.mean(track_lengths)), 2) if track_lengths else 0.0,
            "min": int(min(track_lengths)) if track_lengths else 0,
            "max": int(max(track_lengths)) if track_lengths else 0,
        },
        "track_duration_s": {
            "median": round(float(np.median(track_durations)), 2) if track_durations else 0.0,
            "mean": round(float(np.mean(track_durations)), 2) if track_durations else 0.0,
            "min": round(float(min(track_durations)), 2) if track_durations else 0.0,
            "max": round(float(max(track_durations)), 2) if track_durations else 0.0,
        },
        "tracks_le_10_obs": {
            "count": short_tracks,
            "percentage": round((short_tracks / total_tracks * 100), 2) if total_tracks else 0.0,
        },
        "class_counts": dict(class_counts),
        "confidence": {
            "mean": round(float(np.mean(all_confs)), 4) if all_confs else 0.0,
            "median": round(float(np.median(all_confs)), 4) if all_confs else 0.0,
            "share_under_0_5": round(sum(1 for c in all_confs if c < 0.5) / len(all_confs), 4) if all_confs else 0.0,
        },
    }
    return stats


def print_summary(stats: Dict[str, Any]) -> None:
    print("=" * 60)
    print("AEGIS COMMAND - DETECTION & TRACK STATISTICS BASELINE")
    print("=" * 60)
    print(f"Source File:            {stats['source_file']}")
    print(f"Video Duration:         {stats['video_duration_s']} s")
    print(f"Total Detections:       {stats['total_detections']}")
    print(f"Detections / sec:       {stats['detections_per_second']}")
    print(f"Unique Track IDs:       {stats['total_tracks']}")
    print("-" * 60)
    print("Track Continuity:")
    print(f"  Median Track Length:  {stats['track_length_obs']['median']} observations")
    print(f"  Mean Track Length:    {stats['track_length_obs']['mean']} observations")
    print(f"  Median Duration:      {stats['track_duration_s']['median']} s")
    print(f"  Mean Duration:        {stats['track_duration_s']['mean']} s")
    print(f"  Tracks <= 10 obs:     {stats['tracks_le_10_obs']['count']} ({stats['tracks_le_10_obs']['percentage']}%)")
    print("-" * 60)
    print("Class Distribution:")
    for cls, count in stats["class_counts"].items():
        share = (count / stats["total_detections"]) * 100 if stats["total_detections"] else 0.0
        print(f"  {cls:12s}: {count:5d} ({share:5.1f}%)")
    print("-" * 60)
    print("Confidence Distribution:")
    print(f"  Mean Confidence:      {stats['confidence']['mean']}")
    print(f"  Median Confidence:    {stats['confidence']['median']}")
    print(f"  Share under 0.5:      {stats['confidence']['share_under_0_5'] * 100:.2f}%")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Analyze track and detection baseline statistics.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("frontend/public/detections.json"),
        help="Path to detections.json input file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to output stats JSON",
    )
    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: input file {args.input} not found.", file=sys.stderr)
        sys.exit(1)

    stats = compute_track_stats(args.input)
    print_summary(stats)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2)
        print(f"Saved stats to {args.output}")


if __name__ == "__main__":
    main()
