# ingest_target.py
import os
import sys
import shutil
import cv2
import json
from collections import deque
from ultralytics import YOLO

# Constants
FRONTEND_PUBLIC = os.path.join("frontend", "public")
HISTORY_FRAMES = 5
SPEED_CONSTANT = 0.5

def get_direction(dx, dy):
    vertical = "N" if dy < 0 else "S" if dy > 0 else ""
    horizontal = "E" if dx > 0 else "W" if dx < 0 else ""
    direction = vertical + horizontal
    return direction if direction else "-"

def ingest_new_video(source_video_path):
    if not os.path.exists(source_video_path):
        print(f"[ERROR] Cannot find video: {source_video_path}")
        sys.exit(1)

    print(f"[AEGIS INGESTION] Processing new target video: {source_video_path}")
    
    # 1. Copy the new video to the frontend public folder, renaming it to what Next.js expects
    target_video_path = os.path.join(FRONTEND_PUBLIC, "drone_feed.mp4")
    shutil.copy(source_video_path, target_video_path)
    print(f"[AEGIS INGESTION] Video hot-swapped into Next.js UI.")

    # 2. Run YOLOv8 Extraction
    print("[AEGIS INGESTION] Booting YOLOv8s AI Core...")
    model = YOLO('yolov8s.pt')
    cap = cv2.VideoCapture(target_video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    timeline_detections = {}
    track_history = {}
    frame_count = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: break

        # Using ByteTrack for object persistence
        results = model.track(frame, persist=True, tracker="bytetrack.yaml", verbose=False)
        frame_detections = []

        for result in results:
            if result.boxes is None or result.boxes.id is None: continue

            for box in result.boxes:
                conf = float(box.conf[0])
                cls = int(box.cls[0])
                name = model.names[cls]
                track_id = int(box.id[0])

                if name in ['car', 'truck', 'bus', 'person'] and conf > 0.35: # Lowered threshold slightly for better demoing
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2

                    if track_id not in track_history:
                        track_history[track_id] = deque(maxlen=HISTORY_FRAMES + 1)
                    track_history[track_id].append((cx, cy))

                    speed_kmh = 0
                    direction = "-"
                    if len(track_history[track_id]) > HISTORY_FRAMES:
                        old_cx, old_cy = track_history[track_id][0]
                        dx, dy = cx - old_cx, cy - old_cy
                        pixel_distance = ((dx ** 2) + (dy ** 2)) ** 0.5
                        speed_kmh = round(pixel_distance * SPEED_CONSTANT)
                        direction = get_direction(dx, dy)

                    frame_detections.append({
                        "id": f"Target-{track_id}",
                        "class": name,
                        "confidence": round(conf, 2),
                        "box": [round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)],
                        "speed_kmh": speed_kmh,
                        "direction": direction
                    })

        if frame_detections:
            timestamp = round(frame_count / fps, 2)
            timeline_detections[str(timestamp)] = frame_detections

        frame_count += 1
        if frame_count % 30 == 0:
            print(f"[AEGIS INGESTION] Analyzed {frame_count}/{total_frames} frames...")

    cap.release()

    # 3. Inject the new detections.json directly into the frontend
    target_json_path = os.path.join(FRONTEND_PUBLIC, "detections.json")
    with open(target_json_path, 'w') as f:
        json.dump(timeline_detections, f)
        
    print(f"\n[AEGIS INGESTION COMPLETE] Telemetry mapped to {target_json_path}.")
    print(">>> Tell the judge to refresh the browser (F5). The new video is now live.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ingest_target.py <path_to_video.mp4>")
        sys.exit(1)
    
    ingest_new_video(sys.argv[1])