# Aegis Command — Threat Intelligence Network

HackerRank Infinity Hacks 2026 — Defence Track

Aegis Command is a unified threat-intelligence dashboard that combines real-time drone video reconnaissance with a vector-search intelligence engine to provide commanders with context-aware battlefield information.

## System Architecture

Aegis Command uses a decoupled microservice architecture:

1. Vision AI Microservice (port 8001)
	- Processes drone video feeds with OpenCV and YOLOv8
	- Detects threats and streams an MJPEG feed

2. Intelligence RAG Backend (port 8000)
	- FastAPI + FAISS + SentenceTransformers
	- Embeds and searches intercepted communications

3. Command Interface (port 3000)
	- Next.js + Tailwind CSS
	- Correlates vision detections with the intelligence database

## Running Locally

Run the three services in separate terminals (do not share virtual environments between Python services). Example commands for Linux/macOS are shown below.

Vision AI (port 8001)
```bash
cd vision
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn vision_engine:app --reload --port 8001
```

Intelligence Backend (port 8000)
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Command Interface (port 3000)
```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000 in your browser after starting the services.

Notes
- If you're on Windows, activate virtual environments with `venv\Scripts\activate`.
- Ensure each Python backend uses its own virtual environment to avoid dependency conflicts.

## Contributing

If you'd like to contribute, open an issue or submit a pull request. Include service-specific notes and which port you worked on.

---