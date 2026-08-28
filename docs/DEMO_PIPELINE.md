# Demo Pipeline

Aegis ships with a deterministic replay pipeline rather than requiring a live drone feed.

## Canonical assets

- `frontend/public/drone_feed.mp4` — the video rendered by the operator console.
- `frontend/public/detections.json` — timestamped object detections consumed by the frontend.

These two files belong together. Replacing the video without regenerating the detection timeline will produce an invalid replay.

## Regenerating the demo

The optional ingestion utility lives at `vision/ingest_target.py`. Run it from the repository root after installing the vision dependencies:

```bash
cd vision
python -m venv .venv
# Activate .venv using your platform's command, then:
pip install -r requirements.txt
cd ..
python vision/ingest_target.py path/to/video.mp4
```

The utility copies the selected source video to `frontend/public/drone_feed.mp4`, runs YOLOv8 + ByteTrack processing, and writes the matching detection timeline to `frontend/public/detections.json`.

## Repository policy

The canonical demo video and its generated detection timeline are intentionally versioned because they are required to reproduce the operator experience. Local source videos, model weights, archives, virtual environments, and transient processing outputs should not be committed.
