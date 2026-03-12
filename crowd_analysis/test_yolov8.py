import cv2
import os
import sys
import numpy as np
from ultralytics import YOLO

# Add parent directory to path to import local modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import YOLO_CONFIG, MIN_CONF, NMS_THRESH
from tracking import create_tracker, detect_human

def test_yolov8_integration():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(script_dir, YOLO_CONFIG["YOLO_V8_MODEL"])
    
    print(f"Loading model from: {model_path}")
    net = YOLO(model_path)
    
    encoder = None
    tracker = create_tracker(frame_rate=30, max_age=30, n_init=3)
    
    # Load a dummy frame (or a black image if video not found)
    video_path = os.path.join(script_dir, "../video/airport.mp4")
    cap = cv2.VideoCapture(video_path)
    ret, frame = cap.read()
    if not ret:
        print("Could not read video, using dummy frame.")
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cap.release()
    
    # Run detection
    print("Running detection...")
    [humans_detected, expired] = detect_human(net, None, frame, encoder, tracker, 1)
    
    print(f"Detection successful. Humans detected: {len(humans_detected)}")
    for track in humans_detected:
        bbox = track.to_tlwh()
        print(f"Track ID: {track.track_id}, BBox: {bbox}")

if __name__ == "__main__":
    test_yolov8_integration()
