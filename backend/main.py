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

# Load environment variables
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Initialize Groq Client
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
    if index.ntotal > 0:
        print("FAISS index already populated. Skipping re-indexing.")
        return

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
    # 1. Embed and Search FAISS
    query_vector = model.encode([req.query]).astype('float32')
    k = 1 
    distances, indices = index.search(query_vector, k)
    match_index = indices[0][0]
    
    if match_index != -1 and match_index < len(intel_data):
        matched_report = intel_data[match_index]
        transcript = matched_report["transcript"]
        
        # 2. Generate Tactical Summary using Groq (Llama-3)
        try:
            chat_completion = groq_client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "You are Aegis AI, a high-level military intelligence analyst. Read the intercepted report and provide a sharp, 2-sentence tactical summary of the threat, including location and recommended action. Keep it highly professional and concise."
                    },
                    {
                        "role": "user",
                        "content": f"Intercepted Intel: {transcript}"
                    }
                ],
                model="llama3-8b-8192",
                temperature=0.3,
            )
            ai_summary = chat_completion.choices[0].message.content
        except Exception as e:
            print(f"Groq API Error: {e}")
            ai_summary = "AI processing unavailable. Refer to raw transcript."

        # 3. Return Combined Payload
        return {
            "status": "success",
            "ai_summary": ai_summary,
            "data": [
                {
                    "id": matched_report["id"],
                    "score": float(distances[0][0]),
                    "location": matched_report["location"],
                    "transcript": transcript
                }
            ]
        }
    return {"status": "error", "message": "No relevant intel found."}