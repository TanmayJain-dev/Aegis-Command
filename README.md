# Aegis Command
Threat Intelligence Network

**HackerRank Infinity Hacks 2026 — Defence Track**

Aegis Command is a unified threat intelligence dashboard built for fast, high-stakes decision-making. It combines pre-processed UAV footage, computer vision detections, and a retrieval-augmented intelligence layer to turn fragmented battlefield data into something commanders can act on immediately.

![Next.js](https://img.shields.io/badge/Next.js-14-black?style=for-the-badge&logo=next.js)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=for-the-badge&logo=fastapi)
![FAISS](https://img.shields.io/badge/Meta_FAISS-Vector_DB-0467DF?style=for-the-badge&logo=meta)
![Groq](https://img.shields.io/badge/Groq-Llama_3-F55036?style=for-the-badge)
![YOLOv8](https://img.shields.io/badge/YOLOv8-Vision_AI-00FFFF?style=for-the-badge)

---

## Core Features

- **Low-latency threat overlay:** UAV footage is pre-processed with YOLOv8, and the detected coordinates are mapped into a fast lookup structure so the frontend can render bounding boxes smoothly in the browser.
- **Intelligence search at speed:** The system searches through a large corpus of intercepted communications using FAISS-powered vector indexing, enabling fast retrieval of relevant reports.
- **Tactical summaries:** The backend can generate short, actionable summaries from retrieved intelligence using Groq-powered language models.
- **Interactive timeline and map:** Threats can be explored through a synchronized timeline and a geospatial view, helping operators move from raw data to context quickly.

---

## Core Team

- **[Tanmay Jain](https://github.com/TanmayJain-dev)** — Tech Lead, full-stack architecture, RAG NLP, and command interface design
- **[Aryan Garg](https://github.com/Aryangarg372)** — Computer vision pipeline and YOLOv8-based detection workflow
- **[Rishabh]** — Product strategy, presentation, and storytelling

---

## System Architecture

Aegis Command is built as a decoupled frontend-backend system:

1. **Intelligence Backend (Port 8000):** Powered by Python, FastAPI, and Hugging Face SentenceTransformers. It indexes mock intelligence reports into FAISS and supports AI-generated tactical summaries.
2. **Command Interface (Port 3000):** A Next.js UI that handles video playback, threat overlays, timeline navigation, and geospatial visualization.

---

## Run Locally

Run the backend and frontend in separate terminals.

### 1. Intelligence Backend (Port 8000)

```bash
cd backend
python -m venv venv

# Windows: venv\Scripts\activate
# Linux/Mac: source venv/bin/activate

pip install -r requirements.txt
```

Create a `.env` file inside the backend folder and add your Groq API key:

```env
GROQ_API_KEY=gsk_your_api_key_here
```

Start the server:

```bash
uvicorn main:app --reload --port 8000
```

### 2. Command Interface (Port 3000)

Make sure `drone_feed.mp4` and `detections.json` are present in the frontend/public directory before starting.

```bash
cd frontend
npm install
npm run dev
```

Once both services are running, open http://localhost:3000 in your browser.

Click play on the video feed to begin the automated threat detection loop.

