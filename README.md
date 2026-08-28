<div align="center">

# AEGIS COMMAND
### AI-Assisted Tactical Intelligence & Decision Support

**Computer Vision · Retrieval-Augmented Intelligence · Real-Time Telemetry · Operator Decision Support**

Built by **Tanmay Jain · Aryan Garg · Rishabh Bansal**

</div>

---

> **Aegis Command turns fragmented surveillance signals into an evidence-grounded operational picture.**
>
> Video detections, intercepted intelligence and prior incidents become one operator-facing workflow instead of three disconnected sources of information.

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

## Why Aegis?

Surveillance systems can produce more information than an operator can efficiently correlate in real time.

A camera can identify an object. An intelligence record can provide context. Historical incidents can reveal patterns. Aegis connects those signals into a single decision-support workflow.

It is intentionally a **decision-support system**, not an autonomous decision-maker.

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

### Perception

The frontend replays `frontend/public/drone_feed.mp4` and uses the matching `frontend/public/detections.json` timeline to render object detections over the video.

Each event can carry class, confidence, bounding-box coordinates, movement information and projected map coordinates.

### Event transport

Threat assessment is asynchronous. The dashboard maintains a WebSocket connection to `/ws/threat-engine` so perception events can trigger downstream reasoning without blocking the UI.

### Retrieval

The intelligence layer uses `all-MiniLM-L6-v2` embeddings with a 384-dimensional FAISS index. Retrieval happens before generation so the language model receives relevant evidence instead of acting as the database itself.

### Grounded reasoning

The assessment layer returns reasoning, threat level/score and a recommended action while retaining the evidence context used to reach the assessment.

### Incident memory

Threat assessments can be persisted and reviewed later, allowing the operator workflow to retain an inspectable history rather than treating each event as ephemeral.

---

## Engineering Details

### ⚡ Efficient telemetry lookup

Detection timestamps are ordered and searched with a binary-search style lookup rather than scanning every frame on every update.

### 🔄 Asynchronous threat flow

The frontend uses WebSockets with reconnect handling and in-flight request protection so model latency does not become a UI lock-up.

### 🗺️ Bounded geo-projection

Video detections contain pixel coordinates rather than GPS coordinates. A deterministic projection maps detection centers into a bounded tactical operating box while clamping extreme values.

### 🧠 Retrieval before generation

Relevant evidence is retrieved first and then supplied to the reasoning layer, reducing the chance of treating unconstrained model output as the source of truth.

---

## Technology Stack

<div align="center">

`Next.js` · `React` · `TypeScript` · `Python` · `FastAPI` · `WebSockets` · `YOLOv8` · `FAISS` · `SentenceTransformers` · `Groq` · `Docker`

</div>

---

## Repository Structure

```text
Aegis-Command/
├── assets/
│   ├── architecture.svg
│   ├── demo-video-placeholder.svg
│   └── screenshots/
│       ├── dashboard.jpg
│       ├── video-feed.jpg
│       ├── tactical-map.jpg
│       └── intel-feed.jpg
│
├── backend/
│   ├── main.py
│   ├── incident_memory.py
│   ├── data_forger.py
│   ├── mock_intel.json
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   ├── public/
│   │   ├── drone_feed.mp4
│   │   └── detections.json
│   └── package.json
│
├── vision/
│   ├── vision_engine.py
│   ├── yolo_extractor.py
│   ├── ingest_target.py
│   ├── viewer.html
│   ├── requirements.txt
│   └── README.md
│
├── docs/
├── docker-compose.yml
└── README.md
```

---

## Running Locally

### Recommended: Docker Compose

The root `docker-compose.yml` starts the **FastAPI backend** and **Next.js frontend**. The dashboard already contains the canonical replay video and detection timeline, so the basic demo does not require starting the separate vision microservice.

#### 1. Prerequisites

Install:

- Git
- Docker Engine
- Docker Compose

You also need a Groq API key for the reasoning layer.

#### 2. Clone the repository

```bash
git clone https://github.com/TanmayJain-dev/Aegis-Command.git
cd Aegis-Command
```

#### 3. Configure the backend

```bash
cp backend/.env.example backend/.env
```

Open `backend/.env` and add your API key:

```env
GROQ_API_KEY=your_key_here
```

Do not commit `backend/.env`.

#### 4. Start Aegis

```bash
docker compose up --build
```

Wait for both services to start, then open:

- **Frontend:** http://localhost:3000
- **Backend:** http://localhost:8000

The frontend talks to the backend through the configured Next.js API/WebSocket rewrites.

#### 5. Stop the stack

```bash
docker compose down
```

### Frontend-only development

For UI work, you can run the Next.js app directly:

```bash
cd frontend
npm install
npm run dev
```

Then open **http://localhost:3000**.

The frontend's dependencies are isolated under `frontend/`; there is intentionally no Node package manifest at the repository root.

### Vision pipeline

The optional vision module lives under `vision/` and contains the ingestion utility used to regenerate the replay video and detection timeline.

Install its dependencies:

```bash
cd vision
python -m venv .venv
```

Activate the environment, then:

```bash
pip install -r requirements.txt
```

From the repository root, a replacement video can be processed with:

```bash
python vision/ingest_target.py path/to/video.mp4
```

That utility updates `frontend/public/drone_feed.mp4` and `frontend/public/detections.json` together. Because the canonical replay already ships with the repository, this step is only needed when regenerating the demo data.

---

## Project Context

Aegis Command was built for **HackerRank Infinity Hacks 2026**, where the team finished **#14 out of 6,000+ global participants**.

The project focused on the problem of **information fragmentation**: surveillance, intelligence and historical context often live in separate systems, forcing an operator to perform the correlation manually.

Aegis explores how computer vision, semantic retrieval and grounded language models can be composed into a single operator-facing system.

---

## Team

| Member | Focus |
|---|---|
| **Tanmay Jain** | Team Lead · System architecture · Backend · AI/RAG integration |
| **Aryan Garg** | Computer vision · Detection pipeline |
| **Rishabh Bansal** | UI/UX · Interface design · Product presentation |

---

<div align="center">

### Aegis Command is built to help an operator understand the signal faster.

**Detect. Correlate. Retrieve. Assess.**

</div>
