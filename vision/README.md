Aegis Command — Vision AI Microservice (Proof of Concept)

This is a proof-of-concept, not a production-ready system. It demonstrates a working pipeline: YOLOv8 object detection + simple IoU-based tracking + live MJPEG video streaming over HTTP, built for a hackathon project.

What it does
Loads a local video file (drone_feed.mp4) and processes it frame by frame
Detects vehicles (car/truck/bus/motorcycle/boat/train) using YOLOv8
Draws a single tracked red box per vehicle (deduplicated + merged, not raw overlapping boxes)
Streams the processed video as MJPEG at /api/vision/stream
Exposes the latest detection as JSON at /api/vision/latest-detection
Known limitations (read before judging it too harshly)
Detection confidence thresholds were tuned specifically for the included demo footage — a different video may need re-tuning
No GPU-specific optimization; runs on CPU fine but slower than with a GPU
No database/logging — only the single "latest detection" is kept in memory
Single video file, not a live camera/stream source
Not stress-tested for multiple concurrent viewers
Setup
1. Install Python

You need Python 3.9–3.11 installed. Check with:

python --version
2. Clone the repo
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO
3. Create and activate a virtual environment

Windows (PowerShell):

python -m venv venv
venv\Scripts\Activate.ps1

Mac/Linux:

python3 -m venv venv
source venv/bin/activate

You should see (venv) appear at the start of your terminal prompt.

4. Install dependencies
pip install -r requirements.txt

This installs FastAPI, Uvicorn, OpenCV, and Ultralytics (YOLOv8).

5. Add the video file

Place a video named exactly drone_feed.mp4 in the project's root folder (same folder as vision_engine.py). If you don't have the original demo clip, any vehicle/traffic footage will work, though detection accuracy may vary.

6. Run the server
uvicorn vision_engine:app --reload --port 8001

Wait for Application startup complete in the terminal. On first run, it will automatically download the YOLOv8 model weights (~22MB) — this only happens once.

7. Watch it work

Open this URL in your browser:

http://localhost:8001/api/vision/stream

You should see the video playing with red boxes drawn around detected vehicles.

You can also check the latest detection as JSON:

http://localhost:8001/api/vision/latest-detection
About GPU vs CPU

You do not need a dedicated GPU to run this. The code automatically detects whether a GPU is available and uses it if present — otherwise it falls back to CPU automatically. On CPU, expect it to run slower (a few frames per second rather than smooth real-time), but it will work.
run the index.html file after hitting uvicorn vision_engine:app --reload --port 8001 in the vs code terminal so you do not have to paste the link to open the video on the brower . however for opening the other output you still need to paste the link
Stopping the server


Press Ctrl + C in the terminal where it's running.