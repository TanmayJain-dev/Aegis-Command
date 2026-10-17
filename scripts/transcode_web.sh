#!/usr/bin/env bash
set -euo pipefail

# Aegis Command - Web Video Transcoder
# Converts raw 1080p source video into web-optimized 720p 30fps MP4 (target <= 10MB)

INPUT="${1:-vision/source/drone_feed.mp4}"
OUTPUT="${2:-frontend/public/feeds/uav-alpha/video.mp4}"

if [ ! -f "$INPUT" ]; then
  echo "Error: Input file '$INPUT' does not exist." >&2
  echo "Source video not found. Download with: python scripts/download_weights.py --include-source or from GitHub Release v0.4.0." >&2
  exit 1
fi

mkdir -p "$(dirname "$OUTPUT")"

echo "============================================================"
echo "AEGIS COMMAND - WEB VIDEO TRANSCODER"
echo "============================================================"
echo "Source Input:   $INPUT"
echo "Target Output:  $OUTPUT"

ORIG_BYTES=$(stat -c%s "$INPUT" 2>/dev/null || stat -f%z "$INPUT")
ORIG_MB=$(echo "scale=2; $ORIG_BYTES / 1048576" | bc)
echo "Original Size:  ${ORIG_MB} MB (${ORIG_BYTES} bytes)"
echo "------------------------------------------------------------"

# Check if audio stream exists
HAS_AUDIO=$(ffprobe -i "$INPUT" -show_streams -select_streams a -loglevel error | grep -q "codec_type=audio" && echo "yes" || echo "no")

if [ "$HAS_AUDIO" = "yes" ]; then
  echo "Audio stream detected. Transcoding video to 720p 30fps (CRF 26) and audio to AAC 96k..."
  ffmpeg -y -i "$INPUT" \
    -vf "scale=-2:720,fps=30" \
    -c:v libx264 -crf 26 -preset medium -pix_fmt yuv420p \
    -c:a aac -b:a 96k \
    -movflags +faststart \
    "$OUTPUT"
else
  echo "No audio stream detected. Transcoding video to 720p 30fps (CRF 26)..."
  ffmpeg -y -i "$INPUT" \
    -vf "scale=-2:720,fps=30" \
    -c:v libx264 -crf 26 -preset medium -pix_fmt yuv420p \
    -an \
    -movflags +faststart \
    "$OUTPUT"
fi

NEW_BYTES=$(stat -c%s "$OUTPUT" 2>/dev/null || stat -f%z "$OUTPUT")
NEW_MB=$(echo "scale=2; $NEW_BYTES / 1048576" | bc)
REDUCTION=$(echo "scale=1; (1 - $NEW_BYTES / $ORIG_BYTES) * 100" | bc)

echo "------------------------------------------------------------"
echo "Transcode Complete:"
echo "Transcoded Size: ${NEW_MB} MB (${NEW_BYTES} bytes)"
echo "Size Reduction:  ${REDUCTION}%"
echo "Target <= 10 MB: $([ "$NEW_BYTES" -le 10485760 ] && echo 'PASSED' || echo 'FAILED')"
echo "============================================================"
