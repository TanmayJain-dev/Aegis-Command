import json
import faiss
import numpy as np
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

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
    
    k = 1 
    distances, indices = index.search(query_vector, k)
    
    match_index = indices[0][0]
    
    if match_index != -1 and match_index < len(intel_data):
        matched_report = intel_data[match_index]
        return {
            "status": "success",
            "data": [
                {
                    "id": matched_report["id"],
                    "score": float(distances[0][0]),
                    "location": matched_report["location"],
                    "transcript": matched_report["transcript"]
                }
            ]
        }
    return {"status": "error", "message": "No relevant intel found."}