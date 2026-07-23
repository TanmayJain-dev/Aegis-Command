from ultralytics import YOLO
import cv2

model = YOLO("yolov8n.pt")

cap = cv2.VideoCapture("drone_feed.mp4")
cv2.namedWindow("YOLO Detection", cv2.WINDOW_NORMAL)   # makes the popup window resizable
frame_num = 0

fps = cap.get(cv2.CAP_PROP_FPS) or 24
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fourcc = cv2.VideoWriter_fourcc(*"mp4v")
out = cv2.VideoWriter("output_with_boxes.mp4", fourcc, fps, (width, height))

VEHICLE_CLASSES = {"car", "truck", "bus", "motorcycle"}
trigger_events = []   # will store {frame, time, label} for every vehicle detection

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    results = model(frame, device=0, verbose=False)[0]
    annotated_frame = results.plot()   # draws boxes + labels automatically

    for box in results.boxes:
        label = model.names[int(box.cls[0])]
        conf = float(box.conf[0])
        if label in VEHICLE_CLASSES and conf > 0.5:
            timestamp_sec = round(frame_num / fps, 2)
            print(f"Frame {frame_num} (t={timestamp_sec}s): {label} ({conf:.2f})")
            trigger_events.append({"frame": frame_num, "time": timestamp_sec, "label": label})

    out.write(annotated_frame)          # full-resolution frame saved to output video
    cv2.imshow("YOLO Detection", annotated_frame)   # window is resizable, drag corners to fit your screen

    if cv2.waitKey(1) & 0xFF == ord('q'):   # press 'q' to quit early
        break

    frame_num += 1

cap.release()
out.release()
cv2.destroyAllWindows()

print("\nDone. Total frames:", frame_num)
print("Saved annotated video as: output_with_boxes.mp4")
print(f"\nTotal vehicle detections: {len(trigger_events)}")