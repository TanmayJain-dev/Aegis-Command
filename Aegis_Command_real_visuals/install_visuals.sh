#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${1:-.}"
ASSET_DIR="$REPO_DIR/assets/screenshots"

mkdir -p "$ASSET_DIR"

cp dashboard.jpg "$ASSET_DIR/dashboard.jpg"
cp video-feed.jpg "$ASSET_DIR/video-feed.jpg"
cp tactical-map.jpg "$ASSET_DIR/tactical-map.jpg"
cp intel-feed.jpg "$ASSET_DIR/intel-feed.jpg"

echo "Copied authentic Aegis UI screenshots into:"
echo "$ASSET_DIR"
echo
echo "Verify:"
file "$ASSET_DIR"/*.jpg
echo
echo "Then edit README.md and insert README_visual_section.md where desired."
