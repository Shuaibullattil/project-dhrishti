import datetime
import time
import numpy as np
import imutils
import cv2
import os
import shutil
import csv
import json
import subprocess
import pandas as pd
from math import ceil
from scipy.spatial.distance import euclidean
from video_process import video_process
from tracking import create_tracker, load_detector
from config import YOLO_CONFIG, VIDEO_CONFIG, DATA_RECORD_RATE, FRAME_SIZE, TRACK_MAX_AGE
from analysis_utils import calculate_abnormal_stats

# Try to import db, but don't fail if we are running standalone
try:
    import sys
    import os
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "apis")))
    from db import db
except ImportError:
    db = None

def run_processing(video_path, session_id=None, callback=None, yolo_model=sys.modules.get('config').YOLO_CONFIG["YOLO_V8_MODEL"] if sys.modules.get('config') else "../nano.pt"):
    # Get the directory of this script to resolve paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Determine if this is a webcam stream
    is_cam = video_path == 0 or str(video_path) == "0"
    
    # Override video path from config
    cap = cv2.VideoCapture(video_path)
    
    if yolo_model:
        model_path = os.path.join(script_dir, yolo_model)
    else:
        model_path = os.path.join(script_dir, YOLO_CONFIG["YOLO_V8_MODEL"])
        
    net = load_detector(model_path)
    ln = None
    print(f"Loaded YOLOv8 model for API processing from {model_path}.")
    
    max_age = DATA_RECORD_RATE * TRACK_MAX_AGE
    if max_age > 30:
        max_age = 30

    frame_rate = cap.get(cv2.CAP_PROP_FPS)
    if frame_rate <= 0:
        frame_rate = 30

    encoder = None
    tracker = create_tracker(frame_rate=frame_rate, max_age=max_age, n_init=3)
    
    # Stop creating local folders and CSVs. 
    # video_process now returns VID_FPS and collected_movement_data
    vid_fps, movement_data, heatmap_url = video_process(cap, FRAME_SIZE, net, ln, encoder, tracker, None, None, callback, session_id, is_cam=is_cam)
    
    total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    
    video_data = {
        "VIDEO_CAP": video_path,
        "IS_CAM": is_cam,
        "DATA_RECORD_FRAME" : 2 if is_cam else int(vid_fps / DATA_RECORD_RATE),
        "VID_FPS" : vid_fps,
        "PROCESSED_FRAME_SIZE": FRAME_SIZE,
        "TRACK_MAX_AGE": TRACK_MAX_AGE,
        "START_TIME": datetime.datetime.now().strftime("%d/%m/%Y, %H:%M:%S"),
        "TOTAL_FRAMES": total_frames
    }
    
    if db and session_id:
        db.update_session_meta(session_id, video_data)
        
        # Calculate and save abnormal stats to MongoDB
        orig_stats, clean_stats = calculate_abnormal_stats(
            movement_data, 
            vid_fps, 
            video_data["DATA_RECORD_FRAME"], 
            FRAME_SIZE, 
            TRACK_MAX_AGE
            )
        if orig_stats and clean_stats:
            db.insert_abnormal_stats(session_id, orig_stats, clean_stats)
            
        if heatmap_url:
            db.update_session_heatmap(session_id, heatmap_url)
            
    cap.release()
    
    return None # No local folder returned anymore

def get_analysis_results(session_id):
    """Fetches session results from MongoDB and returns a summary JSON."""
    if not db:
        return {"error": "Database not initialized"}
        
    session = db.get_session(session_id)
    if not session:
        return {"error": "Session not found"}
        
    # Get trends (frame-by-frame data)
    trends = db.get_session_trends(session_id)
    
    # Calculate summary statistics from trends
    if trends:
        human_counts = [t.get("human_count", 0) for t in trends]
        violate_counts = [t.get("violate_count", 0) for t in trends]
        abnormal_flags = [1 if t.get("abnormal_activity", False) else 0 for t in trends]
        abnormal_frames = sum(abnormal_flags)
        
        peak_count = max(human_counts) if human_counts else 0
        avg_count = round(sum(human_counts) / len(human_counts), 1) if human_counts else 0
        total_violations = sum(violate_counts)
        
        summary = {
            "peak_count": peak_count,
            "avg_count": avg_count,
            "total_abnormal_frames": abnormal_frames,
            "total_violations": total_violations
        }
    else:
        summary = session.get("summary", {})

    # Reconstruct the analysis format used by the UI
    # The UI prepares chart data by mapping:
    # count: item.human_count, violations: item.violate_count, abnormal: item.abnormal
    # We ensure these keys exist in the trends array.
    processed_trends = []
    for t in trends:
        processed_trends.append({
            **t,
            "count": t.get("human_count", 0),
            "violations": t.get("violate_count", 0),
            "abnormal": t.get("abnormal_activity", False)
        })

    analysis = {
        "meta": session.get("video_meta", {}),
        "summary": summary,
        "movement_data": session.get("movement_data", []),
        "heatmap_url": session.get("heatmap_url", None),
        "trends": processed_trends,
        "images": {
            "crowd_statistics_time": "" # No local images anymore
        }
    }

    return analysis
