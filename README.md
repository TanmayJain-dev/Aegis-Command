<div align="center">

# AEGIS COMMAND
### AI-Assisted Tactical Intelligence & Decision Support

<p align="center">
  <a href="https://aegis-command-ui.vercel.app"><img src="https://img.shields.io/badge/Live%20Demo-aegis--command--ui.vercel.app-2563eb?style=for-the-badge&logo=vercel&logoColor=white" alt="Live Demo" /></a>
  <img src="https://img.shields.io/badge/Next.js-16-black?style=for-the-badge&logo=next.js&logoColor=white" alt="Next.js" />
  <img src="https://img.shields.io/badge/FastAPI-Python-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/HackerRank%20Infinity%20Hacks-Top%2014-gold?style=for-the-badge" alt="Hackathon" />
</p>

**Computer Vision · Retrieval-Augmented Intelligence · Telemetry Replay · Operator Decision Support**

Created by **Tanmay Jain**

🔗 **Live Tactical Web Console:** [https://aegis-command-ui.vercel.app](https://aegis-command-ui.vercel.app)

*Prototype · decision-support demo · human in the loop*

</div>

---

> **Aegis Command turns fragmented surveillance signals into an evidence-grounded operational picture.**
>
> Replay video detections, synthetic intelligence records, and prior assessments are presented in a unified operator interface rather than across separate consoles.

---

## The Problem

Tactical monitoring environments frequently generate more concurrent data than a human operator can manually synthesize under time constraints:

- **Operator overload:** Continuous high-resolution video streams require intense visual concentration, making sustained manual tracking difficult.
- **Alert fatigue:** Repetitive detection pings without contextual grounding lead to cognitive saturation and slower reaction times.
- **Fragmented context:** Sensor telemetry, intelligence intercepts, and historical incident logs typically reside across disconnected databases and consoles.
- **Slow reporting:** Manually cross-referencing an observed contact against external logs introduces delays before an authorized response can occur.

---

## What It Does Today

Aegis Command provides a functional demonstration of a decision-support workflow:

1. **Synchronized Telemetry Replay:** Streams surveillance video (`drone_feed.mp4`) while drawing precomputed YOLOv8 bounding boxes and kinematics (`detections.json`) onto an HTML canvas overlay synchronized to playback time.
2. **Simulated Tactical Mapping:** Linearly maps 2D detection coordinates into a bounded synthetic operating area displayed on an interactive Leaflet map.
3. **Live WebSocket Ingestion:** Forwards active detection events (`class`, `confidence`, `speed_kmh`, `direction`, simulated coordinates) to a FastAPI backend over `/ws/threat-engine`.
4. **Vector Intelligence Retrieval:** Embeds detection queries and queries a 1,251-record synthetic SIGINT dataset stored in a FAISS index, retrieving the top 3 nearest records.
5. **Grounded Threat Synthesis:** Generates a structured JSON assessment (`threat_level`, `score`, `reasoning`, `recommended_action`) using Groq-hosted Llama 3.1 based on retrieved context.
6. **Incident Memory Audit:** Automatically logs incoming telemetry, retrieved citations, and generated assessments to an SQLite database (`incidents.db`) for post-incident review.

---

## Operator Interface

The web console provides a consolidated view: **detect → correlate → retrieve → assess**.

<p align="center">
  <img src="assets/screenshots/dashboard.jpg" alt="Aegis Command operational dashboard" width="100%" />
</p>

<table>
<tr>
<td width="50%" align="center">
  <img src="assets/screenshots/video-feed.jpg" alt="Aegis computer vision video feed" width="100%" />
  <br/><b>01 · Video & Telemetry Overlay</b><br/>
  <sub>Precomputed YOLOv8 detection metadata rendered over the video stream.</sub>
</td>
<td width="50%" align="center">
  <img src="assets/screenshots/tactical-map.jpg" alt="Aegis tactical map" width="100%" />
  <br/><b>02 · Tactical Map</b><br/>
  <sub>Detection centers projected into a bounded simulated operating area.</sub>
</td>
</tr>
<tr>
<td width="50%" align="center">
  <img src="assets/screenshots/intel-feed.jpg" alt="Aegis intelligence retrieval feed" width="100%" />
  <br/><b>03 · Intelligence Retrieval</b><br/>
  <sub>FAISS-retrieved evidence reports displayed alongside active detections.</sub>
</td>
<td width="50%" align="center">
  <img src="assets/architecture.svg" alt="Aegis Command system architecture" width="100%" />
  <br/><b>04 · System Architecture</b><br/>
  <sub>Perception replay, WebSocket transport, vector retrieval, and LLM reasoning.</sub>
</td>
</tr>
</table>

---

## How It Works

<p align="center">
  <img src="assets/architecture.svg" alt="Aegis Command architecture diagram" width="100%" />
</p>

```text
Precomputed detections (.json) + video (.mp4)
                     ↓
       Synchronized canvas overlay
                     ↓
 WebSocket event (/ws/threat-engine)
                     ↓
  Vector retrieval from FAISS (IndexFlatL2)
                     ↓
 Groq Llama 3.1 structured assessment
                     ↓
  Operator dashboard + SQLite incident log
```

### 1. Perception and Telemetry Replay
The frontend (`frontend/src/app/page.tsx`) plays `frontend/public/drone_feed.mp4`. On video `timeupdate` events, it uses a binary search over the sorted timestamp keys in `frontend/public/detections.json` to find the closest detection frame within 200 ms. Canvas overlays are drawn to match client video scaling.

### 2. Event Transport
When a detection is active and not currently in flight, the frontend sends a telemetry payload over `/ws/threat-engine`. The payload contains object class, tracking confidence, estimated speed, direction, and projected coordinates.

### 3. Dual-Mode Retrieval Architecture
The backend (`backend/main.py`) converts the incoming query into a 384-dimensional vector:
- **Local & Docker environments (`LOW_MEMORY_MODE=false`):** Generates dense embeddings using `SentenceTransformer('all-MiniLM-L6-v2')`.
- **Hosted deployment (`LOW_MEMORY_MODE=true`):** Uses a lightweight MD5-hashed bag-of-words fallback encoder requiring less than 30 MB of RAM, matching Render free-tier constraints.
- **FAISS Index:** Uses `faiss.IndexFlatL2(384)` over 1,251 synthetic intelligence reports, returning the 3 nearest records by Euclidean (L2) distance.

### 4. Grounded Reasoning
Retrieved report transcripts are formatted into a prompt and submitted to Groq (`llama-3.1-8b-instant`) with `temperature=0.1` and JSON mode enabled. The model returns structured assessment attributes (`threat_level`, `score`, `reasoning`, `recommended_action`).

### 5. Incident Memory
Assessments, telemetry, and evidence IDs are written to an SQLite store via `backend/incident_memory.py`, accessible through `/api/incidents/history`.

---

## Potential Applications

These use cases represent potential functional applications for decision-support workflows rather than deployed systems:

- **Border outposts and unfenced stretches:** Correlating optical surveillance triggers with scheduled patrol routes and historical intercept logs.
- **Anti-drone and smuggling detection:** Associating acoustic or radar contact alerts with visual telemetry in vulnerable terrain corridors.
- **Critical infrastructure perimeters:** Cross-referencing perimeter camera trips against facility access logs and incident histories.
- **Railways and highway corridors:** Assisting dispatchers by highlighting track or lane obstructions with linked maintenance and clearance records.
- **Disaster response:** Screening aerial survey video to flag detected vehicles or structures and link them to geographical damage reports.
- **Large events (decision support only):** Providing operators with aggregated camera metadata and location logging without autonomous intervention.
- **Forest and wildlife reserves:** Monitoring vehicular movement along boundary checkpoints against known permit logs.
- **After-action reporting:** Reviewing timestamped, immutable logs of camera detections and associated intelligence citations for operational debriefs.

---

## Known Limitations

This project is a technical prototype. The following limitations apply to the code on `main`:

- **Precomputed detections:** Object detections are computed offline with YOLOv8s and ByteTrack and replayed from `detections.json`. Live video inference is not performed in the browser, and no precision/recall benchmarks have been established for the demo feed.
- **Single video feed:** The camera source buttons (`UAV-ALPHA`, `PERIMETER CCTV-04`, `MOBILE INFANTRY BODYCAM`) update UI labels and active state only; only one underlying video stream (`drone_feed.mp4`) is implemented.
- **Synthetic intelligence corpus:** `backend/mock_intel.json` consists of 1,251 synthetic records generated by `backend/data_forger.py` from 31 distinct template transcripts.
- **Hosted retrieval fallback:** On the hosted deployment, `LOW_MEMORY_MODE=true` is enabled, which replaces `all-MiniLM-L6-v2` with a bag-of-words hashing encoder.
- **Unfiltered L2 retrieval:** The FAISS index uses `IndexFlatL2` and unconditionally returns the top 3 nearest items. There is no distance threshold or relevance cutoff; even if no relevant context exists, 3 records are returned.
- **Demo-grade assessment prompt:** The system prompt instructs the language model to act as a threat assessment algorithm, biasing outputs toward a threat framing. Outputs are proof-of-concept assessments and not validated intelligence.
- **Cloud LLM dependency:** Reasoning relies on the external Groq cloud API. An operational deployment in secure environments would require an on-premises, air-gapped language model.
- **Simulated coordinates:** Latitudes and longitudes are mapped from 2D pixel centers to a synthetic bounding box (centered at 31.4520° N, 74.9250° E) and do not represent georeferenced sensor positions.
- **No authentication:** The backend endpoints and WebSocket server do not implement authentication, rate limiting, or role-based access control (RBAC).

---

## Roadmap

Active development is focused on operational rigor, currently in progress on the `feat/accuracy-v2` branch:

- **Ground-truth evaluation:** Benchmarking detection precision and recall against hand-labeled ground-truth video annotations.
- **Tracker comparison:** Comparing ByteTrack with alternative association algorithms across target occlusion scenarios.
- **Calibrated retrieval cutoff:** Implementing normalized similarity scoring and an abstention gate when retrieved context falls below threshold.
- **Frontend profiling:** Optimizing canvas draw timing and state updates to ensure deterministic frame rendering.

---

## Repository Structure

```text
Aegis-Command/
├── assets/
│   ├── architecture.svg
│   ├── demo-video-placeholder.svg
│   └── screenshots/
│       ├── dashboard.jpg
│       ├── intel-feed.jpg
│       ├── tactical-map.jpg
│       └── video-feed.jpg
├── backend/
│   ├── .env.example
│   ├── Dockerfile
│   ├── data_forger.py
│   ├── incident_memory.py
│   ├── main.py
│   ├── mock_intel.json
│   └── requirements.txt
├── docs/
│   └── DEMO_PIPELINE.md
├── frontend/
│   ├── public/
│   │   ├── detections.json
│   │   └── drone_feed.mp4
│   ├── src/
│   │   ├── app/
│   │   │   ├── api/intel/search/route.ts
│   │   │   ├── favicon.ico
│   │   │   ├── globals.css
│   │   │   ├── layout.tsx
│   │   │   └── page.tsx
│   │   └── components/
│   │       └── Map.tsx
│   ├── Dockerfile
│   ├── eslint.config.mjs
│   ├── next.config.ts
│   ├── package.json
│   ├── postcss.config.mjs
│   ├── tsconfig.json
│   └── README.md
├── vision/
│   ├── detections.json
│   ├── drone_feed.mp4
│   ├── ingest_target.py
│   ├── requirements.txt
│   ├── viewer.html
│   ├── vision_engine.py
│   ├── yolo_extractor.py
│   └── README.md
├── .gitignore
├── docker-compose.yml
├── LICENSE
├── render.yaml
└── README.md
```

---

## Running Locally

### Option 1: Docker Compose (Recommended)

Starts the FastAPI backend and Next.js frontend with containerized networking.

#### 1. Prerequisites
- Docker Engine and Docker Compose
- Groq API key (free tier available at [groq.com](https://console.groq.com))

#### 2. Configure Environment
```bash
cp backend/.env.example backend/.env
```
Edit `backend/.env` to supply your API key:
```env
GROQ_API_KEY=your_key_here
```

#### 3. Start the Stack
```bash
docker compose up --build
```
Access the application:
- **Frontend Dashboard:** [http://localhost:3000](http://localhost:3000)
- **Backend API Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)

#### 4. Stop the Stack
```bash
docker compose down
```

---

### Option 2: Frontend-Only Development

To run the Next.js UI locally without running the backend container:

```bash
cd frontend
npm install
npm run dev
```
Open [http://localhost:3000](http://localhost:3000). The video replay and canvas telemetry overlay operate client-side from `public/drone_feed.mp4` and `public/detections.json`.

---

### Option 3: Vision Extraction Pipeline

To process a new source video and regenerate the precomputed detection timeline:

```bash
cd vision
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
python ingest_target.py path/to/source_video.mp4
```

This utility copies the video to `frontend/public/drone_feed.mp4` and writes the tracking telemetry to `frontend/public/detections.json`.

---

## Project Context

Aegis Command was developed for **HackerRank Infinity Hacks 2026**, placing **#14 out of 6,000+ global participants**.

The project addresses the challenge of information fragmentation in time-critical decision environments by exploring how computer vision telemetry, semantic retrieval, and governed language models can be combined into a structured operator workflow.

---

## Disclaimer

Fictional scenarios and synthetic data. Not affiliated with or endorsed by any government agency. For research and education.

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
