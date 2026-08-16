import json
import faiss
import numpy as np
import os
import time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
from groq import Groq
from incident_memory import IncidentMemory

# Load environment variables
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    print("WARNING: GROQ_API_KEY not found in .env file!")

# Initialize Groq Client
groq_client = Groq(api_key=GROQ_API_KEY)

app = FastAPI(title="Aegis Autonomous Threat Engine")
incident_memory = IncidentMemory()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

print("Loading NLP Model (all-MiniLM-L6-v2)...")
model = SentenceTransformer('all-MiniLM-L6-v2')

dimension = 384
index = faiss.IndexFlatL2(dimension)
intel_data = []

@app.on_event("startup")
async def startup_event():
    global intel_data, index
    
    # FIX: Prevent duplicate indexing on reload
    if index.ntotal > 0:
        print("FAISS index already populated. Skipping re-indexing.")
        return
        
    print("Loading Mock Intel Database...")
    try:
        with open("mock_intel.json", "r") as f:
            intel_data = json.load(f)
        
        transcripts = [item["transcript"] for item in intel_data]
        embeddings = model.encode(transcripts).astype('float32')
        index.add(embeddings)
        print(f"Successfully indexed {index.ntotal} reports into FAISS.")
    except Exception as e:
        print(f"Error loading data: {e}")

class SearchQuery(BaseModel):
    query: str

# ---------------------------------------------------------
# HTTP REST ENDPOINT (For Manual Operator Searches)
# ---------------------------------------------------------
@app.post("/api/intel/search")
async def search_intel(req: SearchQuery):
    query_vector = model.encode([req.query]).astype('float32')
    k = 3 
    distances, indices = index.search(query_vector, k)
    
    retrieved_reports = []
    context_blocks = []
    
    for i, idx in enumerate(indices[0]):
        if idx != -1 and idx < len(intel_data):
            report = intel_data[idx]
            retrieved_reports.append({
                "id": report["id"],
                "score": float(distances[0][i]),
                "location": report["location"],
                "lat": report.get("lat", 28.6139),
                "lng": report.get("lng", 77.2090),
                "transcript": report["transcript"]
            })
            context_blocks.append(f"[ID: {report['id']}] {report['transcript']}")
            
    if not retrieved_reports:
        return {"status": "error", "message": "No relevant intel found."}

    combined_context = "\n".join(context_blocks)
    try:
        groq_start = time.time()
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are Aegis AI, a military intelligence analyst. Base your summary ONLY on the provided evidence. Cite the Evidence ID. Format: 'Threat detected. Evidence: [ID]. Action: [Recommendation].'"
                },
                {
                    "role": "user",
                    "content": f"Intercepted Intel Context:\n{combined_context}\n\nQuery: {req.query}"
                }
            ],
            model="llama-3.1-8b-instant",
            temperature=0.2,
        )
        ai_summary = chat_completion.choices[0].message.content
    except Exception as e:
        print(f"Groq API Error: {e}")
        ai_summary = "AI processing unavailable. Refer to raw transcripts."

    return {
        "status": "success",
        "ai_summary": ai_summary,
        "data": retrieved_reports
    }

# ---------------------------------------------------------
# WEBSOCKET ENDPOINT (The Autonomous Engine)
# ---------------------------------------------------------


@app.get("/api/intel/history")
async def get_intel_history(limit: int = 100):
    """
    Return the currently loaded intelligence records.

    Uses the application's existing mock/locked intelligence
    dataset rather than introducing another data source.
    """
    try:
        import json
        from pathlib import Path

        candidates = [
            Path("intel_data.json"),
            Path("data/intel_data.json"),
            Path("mock_intel.json"),
            Path("data/mock_intel.json"),
        ]

        data = None

        for candidate in candidates:
            if candidate.exists():
                with candidate.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                break

        if data is None:
            # Fall back to common in-memory names used by the
            # existing application.
            for name in (
                "intel_database",
                "intel_data",
                "mock_intel_data",
                "reports"
            ):
                if name in globals():
                    data = globals()[name]
                    break

        if data is None:
            return {
                "count": 0,
                "records": [],
                "message": "No directly readable intel dataset found."
            }

        if isinstance(data, dict):
            data = list(data.values())

        return {
            "count": min(len(data), limit),
            "records": data[:max(1, min(limit, 500))]
        }

    except Exception as e:
        print(f"[INTEL HISTORY ERROR] {e}")

        return {
            "count": 0,
            "records": [],
            "error": str(e)
        }


@app.get("/api/incidents/history")
async def get_incident_history(
    limit: int = 100,
    threat_level: str | None = None
):
    """
    Return historical Aegis threat assessments.

    This endpoint intentionally reads through the existing
    IncidentMemory database rather than creating a second
    persistence layer.
    """
    try:
        import sqlite3

        db_path = getattr(
            incident_memory,
            "db_path",
            "incidents.db"
        )

        if hasattr(db_path, "__str__"):
            db_path = str(db_path)

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        query = """
            SELECT *
            FROM incidents
        """

        params = []

        if threat_level:
            query += " WHERE threat_level = ?"
            params.append(threat_level)

        query += " ORDER BY id DESC LIMIT ?"
        params.append(max(1, min(limit, 500)))

        rows = conn.execute(query, params).fetchall()
        conn.close()

        records = []

        for row in rows:
            record = dict(row)

            # Decode JSON fields where applicable.
            for key in (
                "telemetry",
                "assessment",
                "evidence",
                "payload"
            ):
                value = record.get(key)

                if isinstance(value, str):
                    try:
                        import json
                        record[key] = json.loads(value)
                    except Exception:
                        pass

            records.append(record)

        return {
            "count": len(records),
            "records": records
        }

    except Exception as e:
        print(f"[HISTORY ERROR] {e}")

        return {
            "count": 0,
            "records": [],
            "error": str(e)
        }


@app.websocket("/ws/threat-engine")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("Frontend Commander connected to Autonomous Engine.")
    try:
        while True:
            try:
                data = await websocket.receive_text()
            except WebSocketDisconnect:
                print("Frontend Commander disconnected while receiving.")
                break

            try:
                payload = json.loads(data)
            except json.JSONDecodeError as e:
                print(f"[WS BAD JSON] {e}")
                continue

            trigger_class = payload.get("class", "unknown object")
            speed = payload.get("speed_kmh", "unknown")
            direction = payload.get("direction", "unknown")

            latitude = payload.get("latitude")
            longitude = payload.get("longitude")

            try:
                latitude = float(latitude) if latitude is not None else None
            except (TypeError, ValueError):
                latitude = None

            try:
                longitude = float(longitude) if longitude is not None else None
            except (TypeError, ValueError):
                longitude = None

            print(
                f"[THREAT ENGINE] Trigger received: "
                f"{trigger_class} moving {direction} at {speed}km/h "
                f"| GPS=({latitude}, {longitude})"
            )

            search_query = f"{trigger_class} moving {direction}"
            query_vector = model.encode([search_query]).astype("float32")
            distances, indices = index.search(query_vector, 3)
            retrieved_reports = []
            context_blocks = []
            for i, idx in enumerate(indices[0]):
                if idx != -1 and idx < len(intel_data):
                    report = intel_data[idx]
                    retrieved_reports.append(report)
                    context_blocks.append(f"[ID: {report['id']}] {report['transcript']}")
            combined_context = "\n".join(context_blocks)

            assessment_json = {
                "threat_level": "UNKNOWN", "score": 0,
                "reasoning": "LLM processing failed.",
                "recommended_action": "MANUAL REVIEW REQUIRED.",
            }
            try:
                groq_start = time.time()
                chat_completion = groq_client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": "You are an autonomous Threat Assessment Algorithm. You MUST output ONLY valid JSON. The JSON must contain exactly these keys: 'threat_level' (string: LOW, MED, HIGH, CRITICAL), 'score' (integer 0-100), 'reasoning' (string: 1 short sentence), 'recommended_action' (string: 1 short sentence). Base the assessment on the provided radar telemetry and SIGINT evidence."},
                        {"role": "user", "content": f"Telemetry: {trigger_class} detected moving {direction} at {speed}km/h.\nSIGINT Evidence:\n{combined_context}"},
                    ],
                    model="llama-3.1-8b-instant",
                    temperature=0.1,
                    response_format={"type": "json_object"},
                )
                assessment_json = json.loads(chat_completion.choices[0].message.content)
                print(f"[GROQ LATENCY] {time.time() - groq_start:.2f}s")
                assessment_json["previous_incidents"] = incident_memory.find_previous_incidents(trigger_class)
            except Exception as e:
                print(f"Groq Threat Engine Error: {e}")

            # Return original telemetry untouched.
            # Frontend uses these coordinates as authoritative threat position.
            response_payload = {
                "event": "THREAT_ASSESSED",
                "telemetry": payload,
                "assessment": assessment_json,
                "evidence": retrieved_reports,
            }
            try:
                stored = incident_memory.store_incident(
                    payload,
                    assessment_json,
                    retrieved_reports
                )
                assessment_json["incident_stored"] = stored
                response_payload["assessment"] = assessment_json
            except Exception as e:
                print(f"[INCIDENT MEMORY ERROR] {e}")

            try:
                await websocket.send_text(json.dumps(response_payload))
                print("[WS SENT] Threat assessment delivered")
            except WebSocketDisconnect:
                print("Frontend Commander disconnected before response delivery.")
                break
            except Exception as e:
                print(f"[WS SEND ERROR] {e}")
                break
    except WebSocketDisconnect:
        print("Frontend Commander disconnected.")
    except Exception as e:
        print(f"WebSocket Error: {e}")

@app.get("/api/health")
def health_check():
    return {"status": "Aegis Backend Operational", "faiss_index_size": index.ntotal}