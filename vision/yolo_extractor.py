import cv2
import json
from collections import deque
from ultralytics import YOLO

# How many frames back we look to compute direction/speed (per Aryan's spec: "5 frames ago")
HISTORY_FRAMES = 5

# Simulated speed constant: pixel_distance * SPEED_CONSTANT ~= km/h for the demo
SPEED_CONSTANT = 0.5


def get_direction(dx, dy):
    """Combine horizontal/vertical movement into a compass string like N, NE, SW, etc."""
    vertical = ""
    horizontal = ""

    if dy < 0:
        vertical = "N"
    elif dy > 0:
        vertical = "S"

    if dx > 0:
        horizontal = "E"
    elif dx < 0:
        horizontal = "W"

    direction = vertical + horizontal
    return direction if direction else "-"


def process_video():
    print("Loading YOLOv8 Model...")
    # Using the nano model for speed
    model = YOLO('yolov8n.pt')

    video_path = 'drone_feed.mp4'
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        print("Error: Could not open video file.")
        return

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"Video loaded: {fps} FPS | {total_frames} Total Frames")

    # Dictionary to hold detections mapped to the video timestamp
    timeline_detections = {}
    frame_count = 0

    # track_id -> deque of last HISTORY_FRAMES+1 centroids, for speed/direction math
    track_history = {}

    print("Extracting coordinates with ByteTrack... This will take a moment.")
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        # Run YOLO inference + ByteTrack (persistent IDs across frames)
        results = model.track(frame, persist=True, tracker="bytetrack.yaml", verbose=False)
        frame_detections = []

        for result in results:
            if result.boxes is None or result.boxes.id is None:
                # Tracker hasn't assigned an ID yet for these boxes (e.g. first frame(s))
                continue

            for box in result.boxes:
                conf = float(box.conf[0])
                cls = int(box.cls[0])
                name = model.names[cls]
                track_id = int(box.id[0])

                # Filter to only care about vehicles/threats
                if name in ['car', 'truck', 'bus', 'person'] and conf > 0.4:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    cx = (x1 + x2) / 2
                    cy = (y1 + y2) / 2

                    # Update this track's centroid history
                    if track_id not in track_history:
                        track_history[track_id] = deque(maxlen=HISTORY_FRAMES + 1)
                    track_history[track_id].append((cx, cy))

                    speed_kmh = 0
                    direction = "-"

                    # Only compute speed/direction once we have a centroid from
                    # HISTORY_FRAMES frames ago for this specific track
                    history = track_history[track_id]
                    if len(history) > HISTORY_FRAMES:
                        old_cx, old_cy = history[0]
                        dx = cx - old_cx
                        dy = cy - old_cy

                        pixel_distance = ((dx ** 2) + (dy ** 2)) ** 0.5
                        speed_kmh = round(pixel_distance * SPEED_CONSTANT)
                        direction = get_direction(dx, dy)

                    vehicle_id = f"Vehicle-{track_id}"

                    frame_detections.append({
                        "id": vehicle_id,
                        "class": name,
                        "confidence": round(conf, 2),
                        "box": [round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)],
                        "speed_kmh": speed_kmh,
                        "direction": direction
                    })

        # If we found something, map it to the exact second in the video
        if frame_detections:
            timestamp = round(frame_count / fps, 2)
            timeline_detections[str(timestamp)] = frame_detections

            # Required terminal logging so this is verifiable, not just trusted
            for det in frame_detections:
                print(f"[Time: {timestamp}s] {det['id']} ({det['class'].capitalize()}) "
                      f"moving {det['direction']} at {det['speed_kmh']} km/h")

        frame_count += 1

        if frame_count % 50 == 0:
            print(f"Processed {frame_count} / {total_frames} frames...")

    cap.release()

    # Save the output to a JSON file
    output_file = 'detections.json'
    with open(output_file, 'w') as f:
        json.dump(timeline_detections, f)

    print(f"Extraction complete! Saved to {output_file}.")


if __name__ == "__main__":
    process_video()