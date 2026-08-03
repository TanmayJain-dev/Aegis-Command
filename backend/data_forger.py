import json
import faiss
import numpy as np
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
groq_client = Groq(api_key=GROQ_API_KEY)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

print("Loading NLP Model...")
model = SentenceTransformer('all-MiniLM-L6-v2')

dimension = 384
index = faiss.IndexFlatL2(dimension)
intel_data = []

@app.on_event("startup")
async def startup_event():
    global intel_data, index
    
    # FIX: Prevent duplicate indexing on reload
    if index.ntotal > 0:
        index.reset()
        
    print("Loading Mock Intel Data...")
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

@app.post("/api/intel/search")
async def search_intel(req: SearchQuery):
    query_vector = model.encode([req.query]).astype('float32')
    
    # Retrieve TOP 3 matches instead of 1
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
                "lat": report.get("lat", 28.6139), # Fallback just in case
                "lng": report.get("lng", 77.2090),
                "transcript": report["transcript"]
            })
            context_blocks.append(f"[Evidence ID: {report['id']}] {report['transcript']}")
            
    if not retrieved_reports:
        return {"status": "error", "message": "No relevant intel found."}

    # Generate Grounded Tactical Summary
    combined_context = "\n".join(context_blocks)
    try:
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
            model="llama-3.1-8b-instant", # UPGRADED MODEL
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

@app.get("/api/health")
def health_check():
    return {"status": "Aegis Backend Operational", "faiss_index_size": index.ntotal}