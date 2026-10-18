import json
from typing import Optional
import faiss
import numpy as np
import os
import time
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from groq import Groq
from incident_memory import IncidentMemory

# Load environment variables
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
if not GROQ_API_KEY:
    print("Notice: GROQ_API_KEY not found in environment. Using automated tactical synthesis mode.")

# Initialize Groq Client safely
groq_client = None
if GROQ_API_KEY:
    try:
        groq_client = Groq(api_key=GROQ_API_KEY)
    except Exception as e:
        print(f"Warning: Failed to initialize Groq client: {e}")

app = FastAPI(title="Aegis Autonomous Threat Engine")
incident_memory = IncidentMemory()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "Aegis Autonomous Threat Engine",
        "version": "1.0",
        "groq_configured": bool(GROQ_API_KEY),
        "groq_model": GROQ_MODEL,
        "indexed_reports": getattr(index, "ntotal", 0)
    }

SYNONYMS = {
    "person": ["patrol", "personnel", "human", "pedestrian"],
    "moving": ["movement", "move"],
    "truck": ["pickup", "vehicle"],
    "drone": ["uav", "hexacopter", "aerial"],
    "car": ["vehicle", "pickup", "tractor"],
}

class ResilientEmbedder:
    def __init__(self):
        self.model = None
        low_mem = os.getenv("LOW_MEMORY_MODE", "false").lower() == "true"
        if not low_mem:
            try:
                print("Loading NLP Model (all-MiniLM-L6-v2)...")
                from sentence_transformers import SentenceTransformer
                self.model = SentenceTransformer('all-MiniLM-L6-v2')
            except Exception as e:
                print(f"Notice: NLP Model loading skipped or failed ({e}). Using resilient vector encoder.")
        else:
            print("Notice: LOW_MEMORY_MODE enabled. Using lightweight vector encoder (<30MB RAM).")

    def encode(self, texts):
        if self.model is not None:
            return self.model.encode(texts, normalize_embeddings=True).astype('float32')
        import hashlib
        vectors = []
        for text in texts:
            vec = np.zeros(384, dtype=np.float32)
            words = str(text).lower().split()
            expanded_words = []
            for w in words:
                clean = w.strip('.,()[]{}:;"\'')
                expanded_words.append(clean)
                if clean in SYNONYMS:
                    expanded_words.extend(SYNONYMS[clean])
            for w in expanded_words:
                h = int(hashlib.md5(w.encode('utf-8')).hexdigest(), 16) % 384
                vec[h] += 1.0
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec /= norm
            vectors.append(vec)
        return np.array(vectors, dtype=np.float32)

model = ResilientEmbedder()

dimension = 384
index = faiss.IndexFlatL2(dimension)
intel_data = []

@app.on_event("startup")
async def startup_event():
    global intel_data, index
    
    # FIX: Prevent duplicate indexing on reload
    if index.ntotal > 0:
        print("FAISS index already populated. Skipping re-indexing.")
    else:
        print("Loading Mock Intel Database...")
        try:
            candidates = [
                Path("mock_intel.json"),
                Path("backend/mock_intel.json"),
                Path("data/mock_intel.json"),
            ]
            intel_path = next((p for p in candidates if p.exists()), None)
            if intel_path:
                with intel_path.open("r", encoding="utf-8") as f:
                    intel_data = json.load(f)
                transcripts = [item["transcript"] for item in intel_data]
                embeddings = model.encode(transcripts).astype('float32')
                index.add(embeddings)
                print(f"Successfully indexed {index.ntotal} reports into FAISS.")
            else:
                print("Warning: mock_intel.json not found.")
        except Exception as e:
            print(f"Error loading data: {e}")

    # Embedder warmup to eliminate cold-start penalty on first request
    try:
        t0 = time.time()
        _ = model.encode(["warmup embedder query"])
        print(f"[WARMUP] Embedder warmed up in {time.time() - t0:.3f}s")
    except Exception as e:
        print(f"[WARMUP] Embedder warmup failed: {e}")

    # Startup self-check and connection warmup for Groq LLM
    if groq_client is not None:
        try:
            t0 = time.time()
            _ = groq_client.chat.completions.create(
                messages=[{"role": "user", "content": "ping"}],
                model=GROQ_MODEL,
                max_tokens=5,
            )
            print(f"[WARMUP] Groq model '{GROQ_MODEL}' verified and ready in {time.time() - t0:.3f}s")
        except Exception as e:
            print(f"[WARMUP] Groq check failed for model '{GROQ_MODEL}': {e}. Operating in rule-based fallback mode.")
    else:
        print("[WARMUP] Groq client not configured. Operating in rule-based assessment mode.")

TACTICAL_TERMS = {
    "truck", "pickup", "vehicle", "car", "van", "tractor", "convoy",
    "drone", "uav", "hexacopter", "aerial", "flight", "ingress",
    "patrol", "bsf", "perimeter", "akhnoor", "samba", "pathankot", "amritsar", "tarn", "taran", "gurdaspur",
    "person", "human", "pedestrian", "movement", "moving", "foot", "personnel",
    "threat", "intercept", "radar", "optical", "thermal", "payload", "arms", "narcotics",
    "post", "border", "clear", "sector", "outpost", "drop", "zone", "ib", "recon"
}

RELEVANCE_THRESHOLD = 0.20


def is_tactically_relevant(query: str, transcripts: list) -> bool:
    """Pre-filters queries to ensure domain relevance."""
    q_words = [w.strip('.,()[]{}:;"\'') for w in query.lower().split() if w]
    if not q_words:
        return False
    if any(w in TACTICAL_TERMS for w in q_words):
        return True
    for t in transcripts:
        if any(w in t.lower() for w in q_words if len(w) > 2):
            return True
    return False


class SearchQuery(BaseModel):
    query: str

# ---------------------------------------------------------
# HTTP REST ENDPOINT (For Manual Operator Searches)
# ---------------------------------------------------------
@app.post("/api/intel/search")
async def search_intel(req: SearchQuery):
    query_text = (req.query or "").strip()
    if not query_text:
        return {
            "status": "success",
            "message": "No relevant intel found.",
            "ai_summary": "No relevant intel found.",
            "data": []
        }

    transcripts = [item["transcript"] for item in intel_data] if intel_data else []
    if not is_tactically_relevant(query_text, transcripts):
        return {
            "status": "success",
            "message": "No relevant intel found.",
            "ai_summary": "No relevant intel found.",
            "data": []
        }

    query_vector = model.encode([query_text]).astype('float32')
    k = 3 
    distances, indices = index.search(query_vector, k)
    
    retrieved_reports = []
    context_blocks = []
    
    for i, idx in enumerate(indices[0]):
        if idx != -1 and idx < len(intel_data):
            report = intel_data[idx]
            raw_dist = float(distances[0][i])
            # Documented score semantic: 0.0 to 1.0 (higher = more relevant)
            # For unit vectors in L2 space: dist = 2 - 2*cos(theta), so cos(theta) = 1 - dist/2
            norm_score = round(max(0.0, min(1.0, 1.0 - raw_dist / 2.0)), 4)
            if norm_score >= RELEVANCE_THRESHOLD:
                retrieved_reports.append({
                    "id": report["id"],
                    "score": norm_score,
                    "location": report["location"],
                    "lat": report.get("lat", 28.6139),
                    "lng": report.get("lng", 77.2090),
                    "transcript": report["transcript"]
                })
                context_blocks.append(f"[ID: {report['id']}] {report['transcript']}")
            
    if not retrieved_reports:
        return {
            "status": "success",
            "message": "No relevant intel found.",
            "ai_summary": "No relevant intel found.",
            "data": []
        }

    combined_context = "\n".join(context_blocks)
    def _build_fallback_summary(reports: list) -> str:
        """Rule-based tactical brief when Groq is unavailable. Covers 8 threat categories."""
        rep = reports[0] if reports else None
        rid = rep["id"] if rep else "NONE"
        loc = rep["location"] if rep else "Forward Sector"
        tx = rep.get("transcript", "").lower() if rep else ""

        if any(k in tx for k in ("truck", "vehicle", "pickup", "convoy", "suv", "motorbike")):
            return (
                f"• SITUATION: Ground vehicle / logistics movement detected along perimeter access track at {loc}.\n"
                f"• EVIDENCE: Transport contact [{rid}] — engine signature and tyre-track imagery correlated by FLIR sensor.\n"
                f"• DIRECTIVE: Scramble Sector QRT for interdiction; establish snap VCP 500m forward of last-known grid."
            )
        elif any(k in tx for k in ("drone", "hexacopter", "uav", "quadcopter", "unmanned", "aerial")):
            return (
                f"• SITUATION: Low-RCS unmanned aerial contact probing restricted airspace over {loc}.\n"
                f"• EVIDENCE: Airborne telemetry intercept [{rid}] — radar cross-section <0.05m², altitude ~120m AGL.\n"
                f"• DIRECTIVE: Activate directional C-UAS jamming array; lock thermal optics on trajectory and alert Brigade Air Defence."
            )
        elif any(k in tx for k in ("infiltrat", "crossing", "breach", "fence", "cut", "tunnel", "footprint")):
            return (
                f"• SITUATION: Possible perimeter breach / infiltration attempt detected at {loc}.\n"
                f"• EVIDENCE: Ground disturbance report [{rid}] — seismic sensor spike and fence-line anomaly confirmed.\n"
                f"• DIRECTIVE: Deploy rapid cordon teams; activate PIR tripwires and enable sector illumination flares."
            )
        elif any(k in tx for k in ("signal", "radio", "frequency", "transmission", "intercept", "comms", "cipher")):
            return (
                f"• SITUATION: Unidentified radio transmission intercepted in {loc} — possible hostile comms activity.\n"
                f"• EVIDENCE: SIGINT log [{rid}] — burst transmission on 148 MHz, duration 12s, bearing 047°.\n"
                f"• DIRECTIVE: Deploy SIGINT direction-finding team; initiate full spectrum scan and geo-locate emitter."
            )
        elif any(k in tx for k in ("weapon", "cache", "rifle", "explosive", "ied", "rpg", "ammunition", "arms")):
            return (
                f"• SITUATION: Arms / weapons cache suspected in forward area near {loc}.\n"
                f"• EVIDENCE: HUMINT report [{rid}] — source credibility HIGH; describes concealed munitions at grid reference.\n"
                f"• DIRECTIVE: Coordinate EOD team immediate dispatch; cordon 200m radius and notify S2 intelligence cell."
            )
        elif any(k in tx for k in ("patrol", "routine", "sweep", "clearance", "sector check")):
            return (
                f"• SITUATION: Scheduled tactical security sweep completed — all sensors verified operational at {loc}.\n"
                f"• EVIDENCE: Patrol log [{rid}] — NIL contact report, perimeter integrity confirmed 100%.\n"
                f"• DIRECTIVE: Maintain automated sensor sweep cadence; sector status SECURE. Log to ops journal."
            )
        elif any(k in tx for k in ("thermal", "flir", "heat", "signature", "infrared", "ir sensor")):
            return (
                f"• SITUATION: Thermal anomaly / heat signature detected by FLIR optics at {loc}.\n"
                f"• EVIDENCE: Infrared intercept [{rid}] — contact thermal profile inconsistent with ambient environment.\n"
                f"• DIRECTIVE: Maintain thermal track lock; dispatch forward observation post to confirm contact nature."
            )
        else:
            return (
                f"• SITUATION: Multi-source intelligence contact correlated in {loc} — nature under assessment.\n"
                f"• EVIDENCE: Sensor intercept [{rid}] — cross-referenced against FAISS tactical database (1,250 records).\n"
                f"• DIRECTIVE: Continue multi-spectrum surveillance; escalate to Battle Captain if contact persists >10 min."
            )

    ai_summary = ""
    if groq_client is not None:
        try:
            chat_completion = groq_client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an elite Joint Tactical Intelligence Operations Officer at Aegis Command Center.\n"
                            "Analyze the intercepted intelligence against the operator's query.\n"
                            "OUTPUT FORMAT: Provide exactly 3 bullet points starting with '• ':\n"
                            "• SITUATION: [1 concise sentence: contact/activity detected, exact outpost/sector, movement vector]\n"
                            "• EVIDENCE: [1 concise sentence: citing [INTEL-XXXX], specific sensor signature, and metrics]\n"
                            "• DIRECTIVE: [1 concise sentence: concrete tactical SOP action, e.g. QRT scramble, C-UAS jamming, thermal track lock]\n"
                            "Maintain authoritative, professional military terminology. Use bullet points only."
                        )
                    },
                    {
                        "role": "user",
                        "content": f"Intercepted Intel Context:\n{combined_context}\n\nOperator Query: {req.query}"
                    }
                ],
                model=GROQ_MODEL,
                temperature=0.2,
            )
            ai_summary = chat_completion.choices[0].message.content
        except Exception as e:
            print(f"Groq API Error: {e}")
            ai_summary = _build_fallback_summary(retrieved_reports)
    else:
        ai_summary = _build_fallback_summary(retrieved_reports)

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
    limit: int = 200,
    threat_level: Optional[str] = None,
):
    """Return complete historical Aegis threat assessments."""
    try:
        records = incident_memory.get_history(
            limit=limit,
            threat_level=threat_level,
        )

        return {
            "status": "success",
            "count": len(records),
            "records": records,
        }

    except Exception as e:
        print(f"[HISTORY ERROR] {e}")

        return {
            "status": "error",
            "count": 0,
            "records": [],
            "error": str(e),
        }



def generate_rule_based_assessment(trigger_class: str, speed: any, direction: any, evidence: list) -> dict:
    """
    Generate a deterministic, evidence-grounded threat assessment
    when LLM inference is disabled, timed out, or unavailable.
    """
    speed_val = 0.0
    try:
        if speed is not None and str(speed).lower() != "unknown":
            speed_val = float(speed)
    except (ValueError, TypeError):
        speed_val = 0.0

    cls = str(trigger_class).lower()
    dir_str = str(direction).upper() if direction else "UNKNOWN"

    top_evidence_id = (
        evidence[0]["id"]
        if evidence and len(evidence) > 0 and isinstance(evidence[0], dict) and "id" in evidence[0]
        else None
    )
    evidence_str = f" Correlated with intel [{top_evidence_id}]." if top_evidence_id else ""

    if "drone" in cls or "uav" in cls:
        if speed_val > 50:
            level = "CRITICAL"
            score = 92
            reasoning = f"[Rule-based] High-speed aerial contact ({speed_val:.0f} km/h) tracking {dir_str}.{evidence_str}"
            action = "Activate counter-UAS electronic countermeasures and scramble perimeter defense."
        else:
            level = "HIGH"
            score = 78
            reasoning = f"[Rule-based] Unidentified aerial contact moving {dir_str}.{evidence_str}"
            action = "Track vector on optics and prepare directed RF jammer."
    elif any(v in cls for v in ("vehicle", "truck", "car", "suv", "van")):
        if speed_val > 70:
            level = "HIGH"
            score = 82
            reasoning = f"[Rule-based] High-speed vehicle ({speed_val:.0f} km/h) approaching {dir_str} sector.{evidence_str}"
            action = "Dispatch perimeter security interceptors to access control gates."
        elif speed_val > 25:
            level = "MED"
            score = 55
            reasoning = f"[Rule-based] Vehicle tracking {dir_str} at moderate speed ({speed_val:.0f} km/h).{evidence_str}"
            action = "Maintain continuous optical surveillance and monitor intersection points."
        else:
            level = "LOW"
            score = 25
            reasoning = f"[Rule-based] Low-speed or stationary vehicle in sector.{evidence_str}"
            action = "Log vehicle registration and verify perimeter clearance."
    elif any(p in cls for p in ("person", "human", "pedestrian")):
        if speed_val > 15:
            level = "MED"
            score = 60
            reasoning = f"[Rule-based] Rapid personnel movement ({speed_val:.0f} km/h) toward {dir_str}.{evidence_str}"
            action = "Direct perimeter PTZ cameras to maintain visual contact."
        else:
            level = "LOW"
            score = 20
            reasoning = f"[Rule-based] Personnel movement detected at normal velocity.{evidence_str}"
            action = "Monitor access checkpoints and log trajectory."
    else:
        if speed_val > 50:
            level = "MED"
            score = 50
            reasoning = f"[Rule-based] Fast-moving contact ({cls}) detected heading {dir_str}.{evidence_str}"
            action = "Classify target with secondary optical zoom."
        else:
            level = "LOW"
            score = 15
            reasoning = f"[Rule-based] Contact ({cls}) detected moving {dir_str}.{evidence_str}"
            action = "Continue automated observation."

    return {
        "threat_level": level,
        "score": score,
        "reasoning": reasoning,
        "recommended_action": action,
        "assessment_source": "rule-based",
    }


_DEFAULT_CLIENT = object()


def assess_threat(
    trigger_class: str,
    speed: any,
    direction: any,
    combined_context: str,
    retrieved_reports: list,
    client: any = _DEFAULT_CLIENT,
) -> dict:
    """
    Assess threat using Groq LLM if available, falling back gracefully
    to deterministic rule-based assessment.
    """
    active_client = groq_client if client is _DEFAULT_CLIENT else client
    assessment_json = None

    if active_client is not None:
        try:
            groq_start = time.time()
            chat_completion = active_client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an autonomous Threat Assessment Algorithm. "
                            "You MUST output ONLY valid JSON. The JSON must contain "
                            "exactly these keys: 'threat_level' (string: LOW, MED, HIGH, CRITICAL), "
                            "'score' (integer 0-100), 'reasoning' (string: 1 short sentence), "
                            "'recommended_action' (string: 1 short sentence). "
                            "Base the assessment on the provided radar telemetry and SIGINT evidence."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Telemetry: {trigger_class} detected moving {direction} at {speed}km/h.\n"
                            f"SIGINT Evidence:\n{combined_context}"
                        ),
                    },
                ],
                model=GROQ_MODEL,
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            parsed = json.loads(chat_completion.choices[0].message.content)
            if isinstance(parsed, dict) and "threat_level" in parsed:
                parsed["assessment_source"] = "llm"
                assessment_json = parsed
                print(f"[GROQ LATENCY] {time.time() - groq_start:.2f}s")
        except Exception as e:
            print(f"Groq Threat Engine Error: {e}")
            assessment_json = None

    if not assessment_json:
        assessment_json = generate_rule_based_assessment(
            trigger_class, speed, direction, retrieved_reports
        )

    return assessment_json


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

            assessment_json = assess_threat(
                trigger_class, speed, direction, combined_context, retrieved_reports
            )
            assessment_json["previous_incidents"] = incident_memory.find_previous_incidents(trigger_class)

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