# Demo Pipeline

Aegis ships with a deterministic replay pipeline rather than requiring a live drone feed.

## Canonical assets

- `vision/source/drone_feed.mp4` — canonical 1080p source video of truth for extraction.
- `frontend/public/feeds/index.json` — feeds manifest registry.
- `frontend/public/feeds/uav-alpha/video.mp4` — web-transcoded video (720p 30fps <= 10MB) rendered by the operator console.
- `frontend/public/feeds/uav-alpha/detections.json` — timestamped object detections consumed by the frontend.
- `frontend/public/drone_feed.mp4` & `frontend/public/detections.json` — legacy compatibility aliases.

These assets belong together. Replacing the video without regenerating the detection timeline will produce an invalid replay.

## Web Transcoder

To compress source footage to web-ready 720p 30fps (<= 10MB) while maintaining bounding box coordinate alignment:

```bash
./scripts/transcode_web.sh vision/source/drone_feed.mp4 frontend/public/feeds/uav-alpha/video.mp4
```

## Regenerating the demo

The ingestion utility lives at `vision/ingest_target.py`. Run it from the repository root after installing the vision dependencies:

```bash
cd vision
python -m venv .venv
# Activate .venv using your platform's command, then:
pip install -r requirements.txt
cd ..
python vision/ingest_target.py path/to/video.mp4
```

The utility ingests the source video into `frontend/public/feeds/uav-alpha/video.mp4` (and legacy paths), runs YOLOv8 + ByteTrack processing, and writes the matching detection timeline to `frontend/public/feeds/uav-alpha/detections.json`.

## Repository policy

The canonical demo video and its generated detection timeline are intentionally versioned because they are required to reproduce the operator experience. Local source videos, model weights, archives, virtual environments, and transient processing outputs should not be committed.
