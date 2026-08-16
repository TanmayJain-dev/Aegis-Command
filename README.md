# 🛡️ Aegis Command | Threat Intelligence Fusion
**HackerRank Infinity Hacks 2026 - Defence Track**

Aegis Command is an AI-assisted Tactical Intelligence Fusion platform built to solve the "Information Fragmentation" crisis at forward operating bases. Designed as a situational awareness overlay for border security operations (e.g., BSF Punjab counter-drone grid / Project SANJAY), it autonomously fuses Edge-processed optical reconnaissance with intercepted Signal Intelligence (SIGINT) to output instantaneous, grounded tactical summaries.

![Next.js](https://img.shields.io/badge/Next.js-14-black?style=for-the-badge&logo=next.js)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=for-the-badge&logo=fastapi)
![FAISS](https://img.shields.io/badge/Meta_FAISS-Vector_DB-0467DF?style=for-the-badge&logo=meta)
![Groq](https://img.shields.io/badge/Groq-Llama_3.1-F55036?style=for-the-badge)
![YOLOv8](https://img.shields.io/badge/YOLOv8-Vision_AI-00FFFF?style=for-the-badge)

---

## ⚡ Technical Innovations
* **Bandwidth-Aware Edge Computing:** Inference runs on the edge device, transmitting only lightweight JSON telemetry (classes, coordinates, confidence). Reduces bandwidth overhead by ~99% compared to raw video streaming.
* **O(log N) Threat Rendering:** The Next.js frontend uses Binary Search on pre-sorted telemetry to render HTML5 Canvas bounding boxes at 60fps with near-zero CPU load, ensuring viability for rugged military field laptops.
* **Grounded Generative RAG:** Queries 1,250+ embedded intercepts in Meta FAISS. The LLM strictly cites the military `INTEL-ID` of the retrieved intercepts to eliminate hallucination risks.

---

## 🚀 How to Run (Dockerized)

Aegis Command uses a decoupled microservice architecture (UI on Port 3000, NLP/RAG on Port 8000). 

**1. Set Environment Variables**
Create a `.env` file in the `backend/` directory:
\`\`\`env
GROQ_API_KEY=gsk_your_api_key_here
\`\`\`

**2. Boot the Cluster**
\`\`\`bash
docker compose up --build
\`\`\`
*Open \`http://localhost:3000\` in your browser.*

---

## ⚙️ Administrative Scripts (For Demoing)

* **Ingest New Drone Feed:** \`python ingest_target.py <path_to_video.mp4>\` (Runs ByteTrack YOLO extraction and hot-swaps the UI JSON).
* **Wipe Incident Memory:** \`./reset_aegis.sh\` (Wipes the SQLite database of prior threats for a clean demo state).

---
*Developed by Team Aegis AI (Tanmay Jain, Aryan Garg, Rishabh Bansal)*
