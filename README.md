<div align="center">

# AEGIS COMMAND
### AI-Assisted Tactical Intelligence & Decision Support

<p align="center">
  <a href="https://aegis-command-ui.vercel.app"><img src="https://img.shields.io/badge/Live%20Demo-aegis--command--ui.vercel.app-2563eb?style=for-the-badge&logo=vercel&logoColor=white" alt="Live Demo" /></a>
  <img src="https://img.shields.io/badge/Next.js-16-black?style=for-the-badge&logo=next.js&logoColor=white" alt="Next.js" />
  <img src="https://img.shields.io/badge/FastAPI-Python-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/HackerRank%20Infinity%20Hacks-Top%2014-gold?style=for-the-badge" alt="Hackathon" />
</p>

**Computer Vision · Retrieval-Augmented Intelligence · Real-Time Telemetry · Operator Decision Support**

Built by **Tanmay Jain · Aryan Garg · Rishabh Bansal**

🔗 **Live Tactical Web Console:** [https://aegis-command-ui.vercel.app](https://aegis-command-ui.vercel.app)

*Prototype · decision-support demo · human in the loop*

</div>

---

> **Aegis Command turns fragmented surveillance signals into an evidence-grounded operational picture.**
>
> Video detections, intercepted intelligence and prior incidents become one operator-facing workflow instead of three disconnected sources of information.

---

## The Problem

Tactical monitoring environments frequently generate more concurrent data than a human operator can manually synthesize under time constraints:

- **Operator overload:** Continuous high-resolution video streams require intense visual concentration, making sustained manual tracking difficult.
- **Alert fatigue:** Repetitive detection pings without contextual grounding lead to cognitive saturation and slower reaction times.
- **Fragmented context:** Sensor telemetry, intelligence intercepts, and historical incident logs typically reside across disconnected databases and consoles.
- **Slow reporting:** Manually cross-referencing an observed contact against external logs introduces delays before an authorized response can occur.

---

## The Operator Experience

The system is designed around a simple loop: **detect → correlate → retrieve → assess**.

### Command Center

<p align="center">
  <img src="assets/screenshots/dashboard.jpg" alt="Aegis Command operational dashboard" width="100%" />
</p>

The dashboard combines replay video, detection telemetry, tactical mapping, intelligence retrieval and threat state in one operating surface.

<table>
<tr>
<td width="50%" align="center">
  <img src="assets/screenshots/video-feed.jpg" alt="Aegis computer vision video feed" width="100%" />
  <br/><b>01 · Video & Detection</b><br/>
  <sub>YOLO-derived detection telemetry rendered over the surveillance feed.</sub>
</td>
<td width="50%" align="center">
  <img src="assets/screenshots/tactical-map.jpg" alt="Aegis tactical map" width="100%" />
  <br/><b>02 · Tactical Map</b><br/>
  <sub>Detection events projected into a bounded operational area.</sub>
</td>
</tr>
<tr>
<td width="50%" align="center">
  <img src="assets/screenshots/intel-feed.jpg" alt="Aegis intelligence retrieval feed" width="100%" />
  <br/><b>03 · Intelligence Retrieval</b><br/>
  <sub>Semantic evidence surfaced alongside the active event.</sub>
</td>
<td width="50%" align="center">
  <img src="assets/architecture.svg" alt="Aegis Command system architecture" width="100%" />
  <br/><b>04 · System Architecture</b><br/>
  <sub>Perception, transport, retrieval, reasoning and operator interaction.</sub>
</td>
</tr>
</table>

---

## System Architecture

<p align="center">
  <img src="assets/architecture.svg" alt="Aegis Command architecture diagram" width="100%" />
</p>

| Layer | Responsibility | Implementation |
|---|---|---|
| **Vision** | Detect and track objects from the replay feed | YOLOv8 + detection telemetry |
| **Threat Gateway** | Stream events and coordinate the live UI | Next.js + React + WebSockets |
| **Intelligence Retrieval** | Embed queries and retrieve relevant records | SentenceTransformers + FAISS |
| **Reasoning** | Produce evidence-grounded assessments | Groq + Llama 3.1 |
| **Incident Memory** | Persist and expose prior assessments | FastAPI + dedicated memory layer |

### What happens when a threat appears?

```text
Video / sensor input
        ↓
YOLO detection + tracking
        ↓
Compact threat telemetry
        ↓
WebSocket → FastAPI threat engine
        ↓
Semantic retrieval from FAISS
        ↓
Evidence-grounded LLM assessment
        ↓
Operator dashboard + incident memory
```

### Perception & Detection Replay Architecture

The frontend streams canonical video feeds configured in `frontend/public/feeds/index.json` (such as `uav-alpha/video.mp4`) and uses the matching `detections.json` timeline to render object detections over the video with calibrated letterbox/pillarbox offset scaling.

> [!NOTE]
> **Deterministic Replay vs Live Inference Architecture**:
> To guarantee deterministic evaluation telemetry, sub-millisecond timeline sampling, and zero client GPU overhead on low-resource hardware, the web console replays **precomputed detection timelines** (`detections.json` generated via `vision/generate_detections.py` with YOLOv8 + ByteTrack) rather than running in-browser live inference. Live perception events stream asynchronously to the FastAPI threat engine via WebSockets.
>
> All benchmark and accuracy metrics strictly adhere to the project's zero-unverified-numbers policy: no accuracy number may be claimed without raw candidate predictions recorded in `docs/results/raw/` and verified by `scripts/verify_benchmarks.py`.

Each event carries class, confidence, bounding-box coordinates, movement velocity/heading, and projected tactical coordinates.

### Event transport

Threat assessment is asynchronous. The dashboard connects directly via WebSockets to `/ws/threat-engine` (reading `NEXT_PUBLIC_WS_URL` or `NEXT_PUBLIC_BACKEND_URL`), ensuring real-time perception triggers stream to the backend without blocking UI rendering.

### Retrieval

The intelligence layer uses `all-MiniLM-L6-v2` embeddings (or the zero-dependency MD5 hash encoder in `LOW_MEMORY_MODE`) with a 384-dimensional FAISS index. Honest retrieval pre-filtering and score normalization ensure irrelevant queries (such as out-of-domain words) return explicit empty responses instead of top-k hallucinated noise.

### Grounded reasoning

The assessment layer utilizes Groq (`llama-3.1-8b-instant` or configured model via `GROQ_MODEL`) to return evidence-grounded threat levels, scores, reasoning, and recommended actions. If the LLM is unavailable, timed out, or unconfigured, the system automatically falls back to an evidence-grounded deterministic rule-based engine, clearly labeling the assessment source in the UI.

### Incident memory

Threat assessments are persistently deduplicated and logged in SQLite via `IncidentMemory`. Operators can inspect complete historical logs across feeds without duplicate frame flooding.

---

## Engineering Details

### ⚡ Efficient telemetry lookup

Detection timestamps are ordered and searched with a binary-search style lookup rather than scanning every frame on every update.

### 🔄 Asynchronous threat flow & connection health

The frontend monitors WebSocket readiness, displaying real-time connection status (`LIVE`, `DEGRADED`, or `OFFLINE`) with automatic reconnection backoff and graceful local fallback.

### 🗺️ Bounded geo-projection & uniform box rendering

Video detections contain pixel coordinates. A deterministic projection maps detection centers into bounded tactical operating coordinates, while uniform aspect-ratio scaling eliminates letterbox drift across desktop, tablet, and mobile displays.

### 🧠 Retrieval before generation

Relevant evidence is retrieved first and then supplied to the reasoning layer, reducing the chance of treating unconstrained model output as the source of truth.

---

## Technology Stack

<div align="center">

`Next.js 16` · `React 19` · `TypeScript` · `Python 3.11+` · `FastAPI` · `WebSockets` · `YOLOv8` · `FAISS` · `SentenceTransformers` · `Groq` · `Docker`

</div>

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

## Repository Structure

```text
Aegis-Command/
├── .github/
│   └── workflows/
│       └── ci.yml
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
│   ├── test_ai_layer.py
│   ├── test_honest_retrieval.py
│   └── requirements.txt
├── docs/
│   ├── BENCHMARKS.md
│   ├── DEMO_PIPELINE.md
│   └── RENDER_DEPLOY.md
├── frontend/
│   ├── public/
│   │   └── feeds/
│   │       ├── index.json
│   │       ├── uav-alpha/
│   │       │   ├── video.mp4
│   │       │   └── detections.json
│   │       ├── cctv-bravo/
│   │       │   └── detections.json
│   │       └── bodycam-charlie/
│   │           └── detections.json
│   ├── src/
│   │   ├── app/
│   │   │   ├── api/
│   │   │   │   ├── incidents/history/route.ts
│   │   │   │   └── intel/search/route.ts
│   │   │   ├── layout.tsx
│   │   │   └── page.tsx
│   │   ├── components/
│   │   ├── hooks/
│   │   └── lib/
│   ├── Dockerfile
│   ├── eslint.config.mjs
│   ├── next.config.ts
│   ├── package.json
│   ├── postcss.config.mjs
│   └── tsconfig.json
├── vision/
│   ├── eval/
│   ├── tests/
│   ├── vision_engine.py
│   ├── ingest_target.py
│   ├── yolo_extractor.py
│   └── requirements.txt
├── .gitignore
├── docker-compose.yml
├── LICENSE
├── render.yaml
└── README.md
```

---

## Surveillance Feeds & Video Assets

Aegis Command supports multi-feed operational switching:
- **`uav-alpha` (Canonical Primary Feed):** Tracked directly in git (`frontend/public/feeds/uav-alpha/video.mp4` and `detections.json`). Ready out-of-the-box on clone.
- **`cctv-bravo` & `bodycam-charlie` (Secondary Feeds):** Detection timelines are committed in git. Binary `video.mp4` files are gitignored (via `*.mp4`) to keep repository size lean. To populate these feeds locally:
  - Copy any MP4 footage to `frontend/public/feeds/cctv-bravo/video.mp4` or `frontend/public/feeds/bodycam-charlie/video.mp4`.
  - Or run the vision ingestion pipeline: `python vision/ingest_target.py path/to/raw_video.mp4`.
- **Dynamic Operator Uploads:** Operators can click **"UPLOAD SURVEILLANCE FEED"** in the dashboard header to drop any `.mp4` video. The client-side feed manager instantiates an object URL, extracts video dimensions, and renders detections without server-side storage overhead.

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
Open [http://localhost:3000](http://localhost:3000). The video replay and canvas telemetry overlay operate client-side from `public/feeds/uav-alpha/video.mp4` and `public/feeds/uav-alpha/detections.json`.

The frontend's dependencies are isolated under `frontend/`; there is intentionally no Node package manifest at the repository root.

---

### Option 3: Vision Extraction Pipeline

To process a new source video and regenerate the precomputed detection timeline:

```bash
cd vision
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scriptsctivate
pip install -r requirements.txt
python ingest_target.py path/to/source_video.mp4
```

This utility ingests into `frontend/public/feeds/uav-alpha/video.mp4` and `frontend/public/feeds/uav-alpha/detections.json` (as well as legacy paths). The web transcode utility `scripts/transcode_web.sh` converts raw 1080p source footage into lightweight 720p 30fps web video (<= 10MB). Because the canonical replay already ships with the repository, this step is only needed when regenerating the demo data.

---

## Methodological Scope & Limitations

Aegis Command is engineered for transparent and accountable decision-support. In strict adherence to the project truth hierarchy (**Raw Evidence -> Deterministic Math -> Governed Reasoning -> Human Decision**), the following limitations govern the current deployment:

1. **Homogeneous UAV Trajectory (Single Source Video)**:
   All 155 certified ground-truth frames originate from a single continuous UAV flight over an industrial facility. While contiguous holdout splitting with 4-frame temporal buffers successfully prevents frame duplication leakage, the physical domain (sun elevation, asphalt surface reflectance, 15–25m flight ceiling, camera optical sensor) represents a single operational scenario. Cross-domain performance across adverse weather, low-light dawn/dusk conditions, or higher altitudes (>50m) remains unverified.

2. **Same-Scene Cross-Validation vs Demo Video Framing**:
   The primary feed in the live demo (`uav-alpha`) displays bounding boxes generated by `aegis_demo_full_last.pt`, a demo model trained on this surveillance footage; the boxes displayed in the interface are therefore an operational demonstration, not an independent test of model accuracy. The reported 5-fold cross-validation headline metric on fixed-epoch training (`last.pt`, 50 epochs, `val=False`, zero holdout snooping) achieves **Person $	ext{AP}_{50} = 82.8\% \pm 5.2\%$** and **Person Recall @ 0.25 = $84.6\% \pm 4.4\%$** across 5 contiguous holdout folds ([MEASURED](docs/results/raw/task1_5fold_comparison.md)). This CV figure is an estimate of same-scene performance on held-out temporal slices, not accuracy on the demo video itself. Validation-selected `best.pt` scores $85.9\% \pm 6.1\%$, exhibiting a +3.16 pp holdout snooping bias. Both reflect holdout segments within the same operational flight sequence, demonstrating temporal robustness across video intervals without claiming generalization to novel unseen geographical locations.

3. **Secondary Feeds Unevaluated**:
   Detections for secondary surveillance feeds (`cctv-bravo` and `bodycam-charlie`) are generated using zero-shot inference (`yolov8m.pt` @ 1280px) and have not been annotated with human-verified ground-truth bounding boxes. They are explicitly configured with `evaluated: false` and render a warning badge in the dashboard. Ready-to-label 30-frame starting packs are available under `vision/labeling_packs/`.

4. **Precomputed Timeline Replay vs In-Browser Live Inference**:
   To ensure reproducible sub-millisecond seeking and zero GPU load on resource-constrained operator workstations (e.g., dual-core client machines), the dashboard streams precomputed detection timelines (`detections.json`) over HTML5 video. Live perception events stream asynchronously to the FastAPI threat engine via WebSockets.

5. **Resolution Impact vs The "Small-Object" Myth**:
   Rigorous error analysis across all 1,737 human-verified ground-truth personnel reveals that **94.5% of people in this footage are $\ge 32	ext{px}$ tall** (44.5% in the 32–64px bucket, 50.0% in the >64px bucket; only 0.46% are <16px). The poor recall of default stock detectors (e.g. legacy 8.8% recall) was caused by aggressive input downsampling (`imgsz=640px` collapsing 32px targets down to 10px blobs), a high confidence floor, and ByteTrack track eviction on 1.5s sampling gaps—not an intrinsic small-object resolution barrier. Evaluating at native 1280px resolution elevates zero-shot person recall from 8.8% to 49.2%, and fixed-epoch fine-tuning reaches 84.6% recall (82.8% $	ext{AP}_{50}$) on unseen contiguous holdouts.

For full raw benchmark logs, bootstrap confidence intervals, and evaluation scripts, refer to [`docs/BENCHMARKS.md`](docs/BENCHMARKS.md).

---

## Project Context

Aegis Command was developed for **HackerRank Infinity Hacks 2026**, placing **#14 out of 6,000+ global participants**.

The project addresses the challenge of information fragmentation in time-critical decision environments by exploring how computer vision telemetry, semantic retrieval, and governed language models can be combined into a structured operator workflow.

---

## Team

| Member | Focus |
|---|---|
| **Tanmay Jain** | Team Lead · System architecture · Backend · AI/RAG integration |
| **Aryan Garg** | Computer vision · Detection pipeline |
| **Rishabh Bansal** | UI/UX · Interface design · Product presentation |

---

## Disclaimer

Fictional scenarios and synthetic data. Not affiliated with or endorsed by any government agency. For research and education.

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

<div align="center">

### Aegis Command is built to help an operator understand the signal faster.

**Detect. Correlate. Retrieve. Assess.**

</div>
