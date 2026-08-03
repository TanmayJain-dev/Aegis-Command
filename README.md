# Aegis Command

Threat Intelligence Network

HackerRank Infinity Hacks 2026 — Defence Track

Aegis Command is a lightweight intelligence dashboard built for fast decision-making. It brings together UAV detections, text-based intelligence, and AI-generated summaries in one place so operators can understand what is happening without jumping between tools.

![Next.js](https://img.shields.io/badge/Next.js-14-0a0a0a?style=for-the-badge&logo=next.js)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=for-the-badge&logo=fastapi)
![FAISS](https://img.shields.io/badge/Meta_FAISS-Vector_DB-0467DF?style=for-the-badge&logo=meta)
![Docker](https://img.shields.io/badge/Docker-Containerized-2496ED?style=for-the-badge&logo=docker)

## What it does

The system takes in several streams of information and turns them into something usable on a single operational view:

- UAV footage is processed through a vision pipeline to identify objects and extract structured detections.
- Intercepted communications are indexed and searched so relevant evidence can be retrieved quickly.
- A language model is used to generate concise summaries grounded in the retrieved data.

The result is a dashboard that helps surface patterns, context, and likely next steps without requiring a long manual review.

## How it works

The project is split into three main parts:

1. Vision processing
   - YOLO-based detection is used to extract visual targets from UAV data.
   - The output is converted into structured JSON that can be consumed by the frontend.

2. Intelligence retrieval
   - Text data is indexed and searched using FAISS to find relevant messages and evidence.
   - The retrieval layer helps connect raw intelligence to spatial and contextual information.

3. User-facing dashboard
   - A Next.js frontend renders the detections and retrieved context in a responsive interface.
   - The backend serves the data and coordinates the summarization flow.

## Stack

- Frontend: Next.js
- Backend: FastAPI
- Vector search: FAISS
- Vision: YOLO-based processing
- Containerization: Docker Compose

## Running locally

1. Create a `.env` file in the `backend/` directory with your Groq API key:

```env
GROQ_API_KEY=gsk_your_api_key_here
```

2. Start the full stack from the project root:

```bash
docker compose up --build
```

3. Open the application:

- Frontend: http://localhost:3000
- API docs: http://localhost:8000/docs

## Project structure

```text
backend/     FastAPI service and intelligence processing
frontend/    Next.js dashboard UI
vision/      Detection pipeline and preprocessing scripts
```

## Notes

The project is designed to feel practical rather than purely experimental. The focus is on making the flow from raw data to usable insight feel clear, quick, and easy to follow.