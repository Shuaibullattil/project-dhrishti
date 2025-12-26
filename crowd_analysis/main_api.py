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
    
    # Standardize results to a 'processed_results' folder in the project root
    # This avoids confusion between 'apis/processed_data' and 'crowd_analysis/processed_data'
    project_root = os.path.dirname(script_dir)
    base_results_dir = os.path.abspath(os.path.join(project_root, 'processed_results'))
    
    run_id = str(int(time.time()))
    results_dir = os.path.join(base_results_dir, f'run_{run_id}')
    os.makedirs(results_dir, exist_ok=True)
    
    # We still keep local CSVs for the legacy presentation scripts if needed, 
    # but we primarily want MongoDB.
    movement_data_path = os.path.join(results_dir, 'movement_data.csv')
    crowd_data_path = os.path.join(results_dir, 'crowd_data.csv')
    
    movement_data_writer_file = open(movement_data_path, 'w', newline='') 
    crowd_data_writer_file = open(crowd_data_path, 'w', newline='')
    
    movement_data_writer = csv.writer(movement_data_writer_file)
    crowd_data_writer = csv.writer(crowd_data_writer_file)
    
    movement_data_writer.writerow(['Track ID', 'Entry time', 'Exit Time', 'Movement Tracks'])
    crowd_data_writer.writerow(['Time', 'Human Count', 'Social Distance violate', 'Restricted Entry', 'Abnormal Activity'])
    
    start_ts = time.time()
    
    video_process(cap, FRAME_SIZE, net, ln, encoder, tracker, movement_data_writer, crowd_data_writer, callback, session_id)
    
    movement_data_writer_file.close()
    crowd_data_writer_file.close()
    
    vid_fps = cap.get(cv2.CAP_PROP_FPS) or 30
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
        
    with open(os.path.join(results_dir, 'video_data.json'), 'w') as video_data_file:
        json.dump(video_data, video_data_file)
        
    cap.release()
    
    # Run the presentation scripts to generate PNGs
    try:
        # Create root processed_data for scripts if it doesn't exist
        # We need this root folder because the visual scripts are hardcoded to use 'processed_data/'
        # Since we can't easily change all scripts, we'll use a shared root 'processed_data' 
        # inside the crowd_analysis folder.
        shared_processed_dir = os.path.join(script_dir, 'processed_data')
        os.makedirs(shared_processed_dir, exist_ok=True)
        
        # Clean ONLY the root files that the scripts use in the shared folder
        for root_file in ['movement_data.csv', 'crowd_data.csv', 'video_data.json']:
            target = os.path.join(shared_processed_dir, root_file)
            if os.path.exists(target):
                os.remove(target)
        
        # Copy our specific run data to the shared 'processed_data/' temporarily
        shutil.copy(os.path.join(results_dir, 'movement_data.csv'), os.path.join(shared_processed_dir, 'movement_data.csv'))
        shutil.copy(os.path.join(results_dir, 'crowd_data.csv'), os.path.join(shared_processed_dir, 'crowd_data.csv'))
        shutil.copy(os.path.join(results_dir, 'video_data.json'), os.path.join(shared_processed_dir, 'video_data.json'))

        venv_python = os.path.abspath(os.path.join(script_dir, "../venv/Scripts/python.exe"))
        
        # Run scripts via subprocess, setting the CWD to script_dir for THAT PROCESS only
        subprocess.run([venv_python, "abnormal_data_process.py", session_id or ""], cwd=script_dir, check=False, capture_output=True)
        subprocess.run([venv_python, "movement_data_present.py"], cwd=script_dir, check=False, capture_output=True)
        subprocess.run([venv_python, "crowd_data_present.py"], cwd=script_dir, check=False, capture_output=True)
        
        # Move generated PNGs from shared folder back to specific results_dir
        for f in os.listdir(shared_processed_dir):
            if f.endswith(".png"):
                shutil.move(os.path.join(shared_processed_dir, f), os.path.join(results_dir, f))
                
    except Exception as e:
        print(f"Error generating plots: {e}")
        
    return results_dir

def get_analysis_results(results_dir):
    """Parses the generated files in results_dir and returns a summary JSON."""
    analysis = {}
    
    # 1. Video Meta
    with open(os.path.join(results_dir, 'video_data.json'), 'r') as f:
        meta = json.load(f)
        analysis['meta'] = meta

    # 2. Crowd Stats (Trend Data)
    trend_data = []
    max_count = 0
    abnormal_frames = 0
    with open(os.path.join(results_dir, 'crowd_data.csv'), 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            count = int(row['Human Count'])
            abnormal = bool(int(row['Abnormal Activity']))
            if count > max_count: max_count = count
            if abnormal: abnormal_frames += 1
            
            trend_data.append({
                "time": row['Time'],
                "count": count,
                "violations": int(row['Social Distance violate']),
                "restricted": bool(int(row['Restricted Entry'])),
                "abnormal": abnormal
            })
    analysis['trends'] = trend_data
    analysis['summary'] = {
        "peak_count": max_count,
        "total_abnormal_frames": abnormal_frames,
        "processed_at": meta.get("START_TIME")
    }

    # 3. Energy stats (Abnormal Detection)
    # We re-run the calculation logic here or parse if it was saved
    # For now, let's extract basic stats from the energies if we can
    # Or just return path to the images
    analysis['images'] = {
        "crowd_statistics_time": "crowd_statistics_time.png"
    }

    if db and analysis.get('meta') and analysis.get('summary'):
        # We can update the session with final results here
        # movement_data parsing
        movement_data = []
        try:
            with open(os.path.join(results_dir, 'movement_data.csv'), 'r') as f:
                reader = csv.reader(f)
                next(reader) # skip header
                for row in reader:
                    movement_data.append({
                        "track_id": row[0],
                        "entry": row[1],
                        "exit": row[2],
                        "positions": row[3:]
                    })
        except: pass
        
        # Determine session_id from results_dir if not passed (though it should be)
        # For this refactor, we assume session_id is available or we find it
        pass 

    return analysis
