import cv2
import time
import threading
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from ultralytics import YOLO

app = FastAPI(title="Aegis Command - Vision AI Microservice")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

model = YOLO("yolov8s.pt")

state_lock = threading.Lock()
latest_frame_jpeg = None
latest_detection = {"detected": None, "timestamp": None}


def iou(box_a, box_b):
    """Intersection over Union between two (x1, y1, x2, y2) boxes."""
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b

    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)

    inter_w = max(0, inter_x2 - inter_x1)
    inter_h = max(0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h

    area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
    union_area = area_a + area_b - inter_area

    if union_area <= 0:
        return 0.0
    return inter_area / union_area


def union_box(box_a, box_b):
    """Smallest box that fully contains both input boxes."""
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b
    return (min(ax1, bx1), min(ay1, by1), max(ax2, bx2), max(ay2, by2))


def merge_overlapping_boxes(detections, iou_threshold=0.15):
    """
    Groups same-frame detections that overlap and merges each group into
    a single box (union of all boxes in the group). Prevents multiple
    boxes on the same physical object within one frame.
    """
    remaining = list(detections)
    merged = []

    while remaining:
        current = remaining.pop(0)
        group_box = current["box"]
        group_conf = current["conf"]
        group_label = current["raw_label"]

        changed = True
        while changed:
            changed = False
            still_remaining = []
            for det in remaining:
                if iou(group_box, det["box"]) > iou_threshold:
                    group_box = union_box(group_box, det["box"])
                    group_conf = max(group_conf, det["conf"])
                    changed = True
                else:
                    still_remaining.append(det)
            remaining = still_remaining

        merged.append({"box": group_box, "conf": group_conf, "raw_label": group_label})

    return merged


def process_video_loop():
    global latest_frame_jpeg, latest_detection

    cap = cv2.VideoCapture("drone_feed.mp4")

    # tracked_objects: list of dicts, each representing one persistent tracked
    # vehicle. Matched frame-to-frame by IoU instead of a fixed position bucket,
    # so slow drift/motion doesn't create duplicate parallel tracks.
    tracked_objects = []
    next_track_id = 0
    PERSIST_FRAMES = 15
    VEHICLE_CLASSES_BROAD = {"car", "truck", "bus", "motorcycle", "boat", "train"}
    CONF_THRESHOLD = 0.20
    MERGE_IOU_THRESHOLD = 0.15     # merging overlapping boxes within one frame
    TRACK_MATCH_IOU_THRESHOLD = 0.25  # matching a detection to an existing track across frames

    while True:
        try:
            ret, frame = cap.read()
            if not ret:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue

            frame = cv2.resize(frame, (960, 540))
            results = model(frame, verbose=False)[0]  # auto-detects GPU if available, else CPU

            raw_detections = []
            for box in results.boxes:
                cls_id = int(box.cls[0])
                raw_label = model.names[cls_id]
                conf = float(box.conf[0])

                if raw_label in VEHICLE_CLASSES_BROAD and conf > CONF_THRESHOLD:
                    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                    raw_detections.append({
                        "box": (x1, y1, x2, y2),
                        "conf": conf,
                        "raw_label": raw_label,
                    })

            # Step 1: merge overlapping boxes within this single frame
            frame_detections = merge_overlapping_boxes(raw_detections, MERGE_IOU_THRESHOLD)

            # Step 2: match each merged detection to an existing tracked object
            # by best IoU overlap; fall back to creating a new track if no
            # existing track overlaps well enough.
            matched_track_ids = set()

            for det in frame_detections:
                best_track = None
                best_iou = 0.0
                for track in tracked_objects:
                    score = iou(det["box"], track["box"])
                    if score > best_iou:
                        best_iou = score
                        best_track = track

                if best_track is not None and best_iou > TRACK_MATCH_IOU_THRESHOLD:
                    best_track["box"] = det["box"]
                    best_track["conf"] = det["conf"]
                    best_track["raw_label"] = det["raw_label"]
                    best_track["ttl"] = PERSIST_FRAMES
                    matched_track_ids.add(best_track["id"])
                else:
                    new_track = {
                        "id": next_track_id,
                        "box": det["box"],
                        "conf": det["conf"],
                        "raw_label": det["raw_label"],
                        "ttl": PERSIST_FRAMES,
                    }
                    next_track_id += 1
                    tracked_objects.append(new_track)
                    matched_track_ids.add(new_track["id"])

            # Step 3: age out tracks that weren't matched this frame
            still_alive = []
            for track in tracked_objects:
                if track["id"] not in matched_track_ids:
                    track["ttl"] -= 1
                    if track["ttl"] <= 0:
                        continue
                still_alive.append(track)
            tracked_objects = still_alive

            if tracked_objects:
                with state_lock:
                    latest_detection = {"detected": "vehicle", "timestamp": time.strftime("%H:%M:%S")}

            # Step 4: draw all currently alive tracks
            for track in tracked_objects:
                x1, y1, x2, y2 = track["box"]
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                cv2.putText(frame, f"vehicle {track['conf']:.2f}", (x1, max(y1 - 10, 15)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

            success, jpeg = cv2.imencode(".jpg", frame)
            if success:
                with state_lock:
                    latest_frame_jpeg = jpeg.tobytes()

        except Exception as e:
            print(f"[process_video_loop error]: {e}")

        time.sleep(0.03)


threading.Thread(target=process_video_loop, daemon=True).start()


def mjpeg_generator():
    boundary = b"--frame"
    while True:
        with state_lock:
            frame_bytes = latest_frame_jpeg
        if frame_bytes is not None:
            yield (
                boundary + b"\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
            )
        time.sleep(0.03)


@app.get("/api/vision/stream")
def video_stream():
    return StreamingResponse(
        mjpeg_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/api/vision/latest-detection")
def get_latest_detection():
    with state_lock:
        return latest_detection


@app.get("/")
def health_check():
    return {"status": "vision microservice running", "port": 8001}