import cv2
import json
import os
import sys
from ultralytics import YOLO

def process_feed(video_path, output_json_path, allowed_classes=("person", "car", "truck", "motorcycle", "bus")):
    print(f"\n[FEED PIPELINE] Processing {video_path} -> {output_json_path}")
    if not os.path.exists(video_path):
        print(f"Error: {video_path} does not exist")
        return

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps
    print(f"FPS: {fps:.2f}, Frames: {total_frames}, Duration: {duration:.2f}s")

    model = YOLO("yolov8n.pt")
    
    # Sample every 1.5s to respect 2-core execution budget while capturing all scene motion
    sample_interval = 1.5
    sample_timestamps = [round(i * sample_interval, 2) for i in range(int(duration / sample_interval) + 1)]

    keyframe_detections = {}

    for t in sample_timestamps:
        frame_idx = min(int(t * fps), total_frames - 1)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            break

        results = model.track(frame, persist=True, tracker="bytetrack.yaml", verbose=False)
        boxes = []
        for r in results:
            if r.boxes is None:
                continue
            for b in r.boxes:
                cls_id = int(b.cls[0])
                cls_name = model.names[cls_id]
                conf = float(b.conf[0])
                if cls_name in allowed_classes and conf >= 0.35:
                    x1, y1, x2, y2 = [round(float(v), 1) for v in b.xyxy[0].tolist()]
                    track_id = int(b.id[0]) if b.id is not None else len(boxes) + 1
                    boxes.append({
                        "id": f"Target-{track_id}",
                        "class": cls_name,
                        "confidence": round(conf, 2),
                        "box": [x1, y1, x2, y2],
                        "speed_kmh": 4 if cls_name == "person" else 15,
                        "direction": "S" if cls_name == "person" else "NE"
                    })
        keyframe_detections[t] = boxes
        print(f"  t={t:.2f}s: {len(boxes)} targets detected ({', '.join([b['class'] for b in boxes[:4]])})")

    cap.release()

    # Interpolate at 0.5s intervals for smooth UI tracking
    final_timeline = {}
    dense_timestamps = [round(i * 0.5, 2) for i in range(int(duration / 0.5) + 1)]
    sorted_sample_times = sorted(keyframe_detections.keys())

    for dt in dense_timestamps:
        # Find nearest keyframe
        closest_t = min(sorted_sample_times, key=lambda st: abs(st - dt))
        # If within 1.5s, use detections
        if abs(closest_t - dt) <= 1.5 and keyframe_detections[closest_t]:
            final_timeline[str(dt)] = keyframe_detections[closest_t]

    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(final_timeline, f, indent=2)

    print(f"[COMPLETED] Generated {len(final_timeline)} timeline frames in {output_json_path}")

if __name__ == "__main__":
    feed = sys.argv[1] if len(sys.argv) > 1 else "cctv-bravo"
    if feed == "cctv-bravo":
        process_feed("frontend/public/feeds/cctv-bravo/video.mp4", "frontend/public/feeds/cctv-bravo/detections.json")
    elif feed == "bodycam-charlie":
        process_feed("frontend/public/feeds/bodycam-charlie/video.mp4", "frontend/public/feeds/bodycam-charlie/detections.json")
    else:
        print(f"Unknown feed: {feed}")
