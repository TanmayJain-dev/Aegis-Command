# Aegis Command — Backend Deployment Guide (Render)

This guide documents the exact configuration and manual dashboard steps to deploy the Aegis Command autonomous threat engine backend to Render's free tier, and wire it to the Vercel frontend.

---

## 1. Architecture & Memory Strategy

Render's free tier provides **512 MB RAM** and **0.1 vCPU**. If PyTorch/Transformers full model weights are loaded on startup, memory exceeds 512 MB and the container is killed with an OOM error.

Aegis Command provides **`LOW_MEMORY_MODE=true`**:
- Uses an MD5 hash-space vector encoder with tactical synonym expansion (<30 MB RAM footprint).
- Uses FAISS L2 indexing with cosine normalization.
- Retains full Groq LLM integration (`qwen/qwen3.8-27b`) for autonomous synthesis.
- Provides sub-second cold starts and 0 OOM risk on Render free tier.

---

## 2. Deploy Checklist (Step-by-Step)

### Step 1: Open Render Dashboard
1. Go to [https://dashboard.render.com](https://dashboard.render.com).
2. Click **New +** → **Web Service**.
3. Select **Build and deploy from a Git repository**.
4. Choose the repository: `TanmayJain-dev/Aegis-Command`.

### Step 2: Configure Web Service Parameters
Fill in the following fields:

| Field | Value | Notes |
|---|---|---|
| **Name** | `aegis-api` | Will produce `https://aegis-api.onrender.com` |
| **Region** | `Singapore` | Low latency for IST / hackathon demo |
| **Branch** | `feat/demo-hardening` (or `main` after PR merge) | Ensure branch has the hardened code |
| **Root Directory** | `backend` | Crucial: isolates backend code and requirements |
| **Runtime** | `Python 3` | Native Python runtime |
| **Build Command** | `pip install -r requirements.txt` | Installs FastAPI, Uvicorn, Faiss, Groq |
| **Start Command** | `uvicorn main:app --host 0.0.0.0 --port $PORT` | Binds to Render's dynamic port |
| **Instance Type** | `Free` | 512 MB RAM / 0.1 vCPU |

### Step 3: Configure Environment Variables
Under the **Environment Variables** section, add:

```env
PYTHON_VERSION = 3.11.9
PORT = 10000
LOW_MEMORY_MODE = true
GROQ_API_KEY = <your-groq-api-key>
GROQ_MODEL = qwen/qwen3.8-27b
```

> [!IMPORTANT]
> `LOW_MEMORY_MODE=true` is required for Render free tier to prevent memory exhaustion during startup.

### Step 4: Health Check Path
Under **Advanced**:
- **Health Check Path**: `/health`

Click **Create Web Service**.

---

## 3. Post-Deploy Verification

Wait 2–3 minutes for the build to finish. Once the status shows **Live**, verify using these commands:

### A. Health & Availability Check
```bash
curl -s https://aegis-api.onrender.com/health | jq .
```
Expected output:
```json
{
  "status": "healthy",
  "service": "Aegis Autonomous Threat Engine",
  "version": "1.0",
  "groq_configured": true,
  "groq_model": "qwen/qwen3.8-27b",
  "indexed_reports": 1251
}
```

### B. Honest Retrieval Verification
```bash
# Relevant query -> returns INTEL-9999
curl -s -X POST https://aegis-api.onrender.com/api/intel/search \
  -H "Content-Type: application/json" \
  -d '{"query":"truck"}' | jq .

# Irrelevant query -> returns empty data, no noise
curl -s -X POST https://aegis-api.onrender.com/api/intel/search \
  -H "Content-Type: application/json" \
  -d '{"query":"banana"}' | jq .
```

### C. Incident History Check
```bash
curl -s https://aegis-api.onrender.com/api/incidents/history | jq .
```

---

## 4. Vercel Frontend Configuration

Once `aegis-api.onrender.com` is live, link it to the Vercel frontend:

1. Open [https://vercel.com](https://vercel.com) and navigate to your **Aegis Command** project.
2. Go to **Settings** → **Environment Variables**.
3. Add the following variables (for Production & Preview):

| Key | Value |
|---|---|
| `NEXT_PUBLIC_BACKEND_URL` | `https://aegis-api.onrender.com` |
| `NEXT_PUBLIC_WS_URL` | `wss://aegis-api.onrender.com/ws/threat-engine` |
| `BACKEND_URL` | `https://aegis-api.onrender.com` |

4. Trigger a **Redeploy** on Vercel:
   - Go to **Deployments** → click the three dots on the latest deployment → **Redeploy**.

---

## 5. Cold-Start Handling During Hackathon Demo

- Render free instances spin down after 15 minutes of inactivity.
- The Aegis Command frontend automatically detects waking state and displays an amber banner:
  `AUTONOMOUS BACKEND WAKING UP (~60s) // ENGINE OPERATING IN DEGRADED DETERMINISTIC MODE`
- **Demo Tip**: 5 minutes before your demo/presentation, visit `https://aegis-api.onrender.com/health` in your browser to warm up the instance so it is `LIVE` when judges arrive.
