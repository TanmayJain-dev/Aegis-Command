import cv2
import json
from ultralytics import YOLO

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

    print("Extracting coordinates... This will take a moment.")
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
            
        # Run YOLO inference
        results = model(frame, verbose=False)
        frame_detections = []
        
        for result in results:
            for box in result.boxes:
                conf = float(box.conf[0])
                cls = int(box.cls[0])
                name = model.names[cls]
                
                # Filter to only care about vehicles/threats
                if name in ['car', 'truck', 'bus', 'person'] and conf > 0.4:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    frame_detections.append({
                        "class": name,
                        "confidence": round(conf, 2),
                        "box": [round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)]
                    })
        
        # If we found something, map it to the exact second in the video
        if frame_detections:
            timestamp = round(frame_count / fps, 2)
            # Use string of timestamp as key for JSON serialization
            timeline_detections[str(timestamp)] = frame_detections
            
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