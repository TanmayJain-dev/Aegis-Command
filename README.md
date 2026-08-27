<div align="center">

# AEGIS COMMAND
### Autonomous Threat Intelligence & Tactical Decision Support

**Computer Vision · Retrieval-Augmented Intelligence · Real-Time Telemetry · Operator Decision Support**

Built by **Tanmay Jain · Aryan Garg · Rishabh Bansal**

</div>

---

> **Aegis Command turns fragmented surveillance signals into an evidence-grounded operational picture.**
>
> Instead of asking an operator to manually correlate video detections, intercepted intelligence and historical incidents, Aegis connects those signals into a single real-time decision-support workflow.

## Why Aegis?

Surveillance systems generate data faster than humans can correlate it.

A camera can detect an object. An intercepted transcript can describe activity. A historical incident can contain relevant context. Individually, those signals are useful; together, they can support a more informed operator response.

**Aegis Command is the orchestration layer between those signals.**

```text
VIDEO / SENSOR INPUT
        │
        ▼
┌───────────────────┐
│   EDGE VISION     │  YOLO detections + tracking telemetry
└─────────┬─────────┘
          │ compact threat event
          ▼
┌───────────────────┐
│  THREAT ENGINE    │  WebSocket / FastAPI orchestration
└─────────┬─────────┘
          │ semantic query
          ▼
┌───────────────────┐
│   RAG + FAISS     │  retrieve relevant intelligence
└─────────┬─────────┘
          │ evidence context
          ▼
┌───────────────────┐
│ GROUNDED REASONING│  constrained assessment + action
└─────────┬─────────┘
          │
          ▼
      OPERATOR
```

<p align="center">
  <img src="assets/architecture.svg" alt="Aegis Command architecture" width="100%" />
</p>

---

## System Architecture

Aegis is deliberately split into independent layers so perception, retrieval and operator interaction do not become one monolithic pipeline.

| Layer | Responsibility | Implementation |
|---|---|---|
| **Vision** | Detect and track relevant objects from video | YOLOv8 + detection telemetry |
| **Threat Gateway** | Render events and stream threat state | Next.js + React + WebSockets |
| **Intelligence Retrieval** | Embed queries and retrieve relevant reports | SentenceTransformers + FAISS |
| **Reasoning** | Produce evidence-constrained summaries | Groq + Llama 3.1 |
| **Incident Memory** | Persist and retrieve prior assessments | Dedicated incident memory layer |

### The important architectural decision

Aegis does **not** need to continuously move raw video through every layer of the system.

The vision layer extracts compact telemetry such as object class, confidence, position and motion. That event can then trigger retrieval and reasoning without treating the entire downstream pipeline as a video-processing system.

This keeps the expensive perception workload separate from the intelligence workflow and makes the architecture easier to evolve.

---

## What happens when a threat is detected?

### 1. Perception

The video layer detects objects and extracts structured telemetry.

```text
class        → detected object type
confidence   → model confidence
box          → bounding coordinates
speed        → movement telemetry when available
position     → projected tactical map coordinates
```

The frontend renders detections directly over the video stream and maps the detection into the tactical operating area.

### 2. Event transport

A threat event is sent through a WebSocket channel to the threat engine.

This allows the operator interface to receive asynchronous assessment results instead of blocking the UI on a synchronous request-response cycle.

### 3. Retrieval

The backend embeds the query using `all-MiniLM-L6-v2` and searches a 384-dimensional FAISS index for the most relevant intelligence records.

Only the retrieved evidence is passed forward as context.

### 4. Grounded assessment

The reasoning layer is instructed to base its response on the supplied evidence and identify the evidence IDs used for the assessment.

The intended output is therefore not simply a free-form model opinion:

```text
Threat detected
↓
Retrieved evidence
↓
Evidence-grounded assessment
↓
Recommended operator action
```

### 5. Incident memory

Assessments can be persisted and exposed through incident-history APIs so the system has an operator-reviewable record of prior events.

---

## Engineering Details Worth Looking At

### ⚡ Efficient telemetry lookup

Detection timestamps are sorted and searched using a binary-search style lookup rather than scanning every detection frame on each video update.

### 🔄 WebSocket-based threat flow

Threat assessment is asynchronous. The frontend maintains a dedicated socket connection, reconnect behavior and request-in-flight protection so the UI is not tightly coupled to individual model requests.

### 🗺️ Bounded geo-projection

Video detections do not inherently contain GPS coordinates. The dashboard projects detection centers into a bounded tactical area for visualization while clamping coordinates to prevent extreme map jumps.

### 🧠 Retrieval before generation

The LLM is used after relevant intelligence has been retrieved, rather than treating the language model as the intelligence database itself.

### 📜 Operator history

The backend exposes both intelligence history and incident history so previously generated assessments remain inspectable.

---

## Technology Stack

<div align="center">

`Next.js` · `React` · `TypeScript` · `Python` · `FastAPI` · `WebSockets` · `YOLOv8` · `FAISS` · `SentenceTransformers` · `Groq` · `Docker`

</div>

---

## Repository Structure

```text
Aegis-Command/
├── frontend/              # Next.js tactical operator console
│   └── src/
│       ├── app/           # Dashboard
│       └── components/    # Tactical map and UI components
│
├── backend/               # FastAPI intelligence engine
│   ├── main.py            # Retrieval, APIs and WebSocket flow
│   └── incident_memory.py # Assessment persistence
│
├── vision/                # Computer vision pipeline
├── assets/                # Documentation visuals
└── docker-compose.yml     # Local orchestration
```

---

## Running Locally

The repository contains separate frontend, backend and vision components. Environment-specific credentials should be provided through local environment configuration rather than committed to source control.

```bash
# Clone
git clone https://github.com/TanmayJain-dev/Aegis-Command.git
cd Aegis-Command

# Start the stack
# See the component-level configuration before running production services.
docker compose up --build
```

> Some components rely on model weights, local datasets or API credentials that are intentionally environment-specific.

---

## Project Context

Aegis Command was built for **HackerRank Infinity Hacks 2026**, where the team finished **#14 out of 2,000+ global participants**.

The project focused on the problem of **information fragmentation**: surveillance, intelligence and historical context often exist in separate interfaces, forcing a human operator to perform the correlation manually.

Aegis explores how computer vision, semantic retrieval and grounded language models can be combined into one operator-facing system.

---

## Team

| Member | Focus |
|---|---|
| **Tanmay Jain** | Team Lead · System architecture · Backend · AI/RAG integration |
| **Aryan Garg** | Computer vision · Detection pipeline |
| **Rishabh Bansal** | UI/UX · Interface design · Product presentation |

---

<div align="center">

### Aegis Command is not an autonomous decision-maker.

It is a **decision-support system** designed to surface relevant evidence, connect fragmented signals and reduce the time required for an operator to understand what the system has observed.

</div>
