# Demo Pipeline

Aegis ships with a deterministic replay pipeline rather than requiring a live drone feed.

## Canonical assets

- `frontend/public/drone_feed.mp4` — the video rendered by the operator console.
- `frontend/public/detections.json` — timestamped object detections consumed by the frontend.

These two files belong together. Replacing the video without regenerating the detection timeline will produce an invalid replay.

## Regenerating the demo

Use the vision ingestion pipeline to process a new input video. The pipeline copies the selected source to `frontend/public/drone_feed.mp4`, runs detection/tracking, and writes the matching detection timeline.

```bash
python vision/ingest_target.py path/to/video.mp4
```

Depending on your local implementation and dependencies, install the vision requirements first and ensure the required YOLO model is available locally.

## Repository policy

The canonical demo video and its generated detection timeline are intentionally versioned because they are required to reproduce the operator experience. Local source videos, model weights, archives, and transient processing outputs should not be committed.
