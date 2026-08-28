# Aegis Command — Frontend

The frontend is the operator-facing tactical dashboard for Aegis Command.

## Responsibilities

- Replay the canonical surveillance feed from `public/drone_feed.mp4`.
- Render detection overlays from `public/detections.json`.
- Display the tactical map and projected threat location.
- Maintain the WebSocket connection to the backend threat engine.
- Surface retrieved intelligence and grounded threat assessments.

## Development

```bash
npm install
npm run dev
```

The frontend is served on `http://localhost:3000`.

For the full multi-service setup, use the root-level Docker Compose configuration instead:

```bash
docker compose up --build
```

See the root [README](../README.md) for the complete architecture and setup instructions.
