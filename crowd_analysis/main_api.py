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
from deep_sort import nn_matching
from deep_sort.detection import Detection
from deep_sort.tracker import Tracker
from deep_sort import generate_detections as gdet
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

def run_processing(video_path, session_id=None, callback=None):
    # Get the directory of this script to resolve paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Override video path from config
    cap = cv2.VideoCapture(video_path)
    
    # Load YOLO weights and config using absolute paths
    WEIGHTS_PATH = os.path.join(script_dir, YOLO_CONFIG["WEIGHTS_PATH"])
    CONFIG_PATH = os.path.join(script_dir, YOLO_CONFIG["CONFIG_PATH"])
    
    net = cv2.dnn.readNetFromDarknet(CONFIG_PATH, WEIGHTS_PATH)
    net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
    net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
    
    ln = net.getLayerNames()
    ln = [ln[i - 1] for i in net.getUnconnectedOutLayers()]
    
    max_cosine_distance = 0.7
    nn_budget = None
    
    max_age = DATA_RECORD_RATE * TRACK_MAX_AGE
    if max_age > 30:
        max_age = 30
        
    model_filename = os.path.join(script_dir, 'model_data/mars-small128.pb')
    encoder = gdet.create_box_encoder(model_filename, batch_size=1)
    metric = nn_matching.NearestNeighborDistanceMetric("cosine", max_cosine_distance, nn_budget)
    tracker = Tracker(metric, max_age=max_age)
    
    # Stop creating local folders and CSVs. 
    # video_process now returns VID_FPS and collected_movement_data
    vid_fps, movement_data = video_process(cap, FRAME_SIZE, net, ln, encoder, tracker, None, None, callback, session_id)
    
    total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    
    video_data = {
        "VIDEO_CAP": video_path,
        "IS_CAM": False,
        "DATA_RECORD_FRAME" : int(vid_fps / DATA_RECORD_RATE),
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
            
    cap.release()
    
    return None # No local folder returned anymore

def get_analysis_results(session_id):
    """Fetches session results from MongoDB and returns a summary JSON."""
    if not db:
        return {"error": "Database not initialized"}
        
    session = db.get_session(session_id)
    if not session:
        return {"error": "Session not found"}
        
    # Reconstruct the analysis format used by the UI
    analysis = {
        "meta": session.get("video_meta", {}),
        "summary": session.get("summary", {}),
        "movement_data": session.get("movement_data", []),
        "images": {
            "crowd_statistics_time": "" # No local images anymore
        }
    }
    
    # If we need trends (for graphs in the immediate response)
    # the UI usually fetches them via /sessions/{id}, but apis/main.py 
    # broadcasted them too.
    trends = db.get_session_trends(session_id)
    analysis['trends'] = trends

    return analysis
