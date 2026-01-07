from config import YOLO_CONFIG, VIDEO_CONFIG, SHOW_PROCESSING_OUTPUT, DATA_RECORD_RATE, FRAME_SIZE, TRACK_MAX_AGE

if FRAME_SIZE > 1920:
	print("Frame size is too large!")
	quit()
elif FRAME_SIZE < 480:
	print("Frame size is too small! You won't see anything")
	quit()

import datetime
import time
import numpy as np
import imutils
import cv2
import os
import csv
import json
from video_process import video_process
from deep_sort import nn_matching
from deep_sort.detection import Detection
from deep_sort.tracker import Tracker
from deep_sort import generate_detections as gdet

# Read from video
IS_CAM = VIDEO_CONFIG["IS_CAM"]
cap = cv2.VideoCapture(VIDEO_CONFIG["VIDEO_CAP"])

# Load YOLOv3-tiny weights and config
WEIGHTS_PATH = YOLO_CONFIG["WEIGHTS_PATH"]
CONFIG_PATH = YOLO_CONFIG["CONFIG_PATH"]

# Load the YOLOv3-tiny pre-trained COCO dataset 
net = cv2.dnn.readNetFromDarknet(CONFIG_PATH, WEIGHTS_PATH)
# Set the preferable backend to CPU since we are not using GPU
net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)

# Get the names of all the layers in the network
ln = net.getLayerNames()
# Filter out the layer names we dont need for YOLO
ln = [ln[i - 1] for i in net.getUnconnectedOutLayers()]

# Tracker parameters
max_cosine_distance = 0.7
nn_budget = None

#initialize deep sort object
if IS_CAM: 
	max_age = VIDEO_CONFIG["CAM_APPROX_FPS"] * TRACK_MAX_AGE
else:
	max_age=DATA_RECORD_RATE * TRACK_MAX_AGE
	if max_age > 30:
		max_age = 30
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROCESSED_DATA_DIR = os.path.join(SCRIPT_DIR, 'processed_data')

if not os.path.exists(PROCESSED_DATA_DIR):
	os.makedirs(PROCESSED_DATA_DIR)

model_filename = os.path.join(SCRIPT_DIR, 'model_data/mars-small128.pb')
encoder = gdet.create_box_encoder(model_filename, batch_size=1)
metric = nn_matching.NearestNeighborDistanceMetric("cosine", max_cosine_distance, nn_budget)
tracker = Tracker(metric, max_age=max_age)

movement_data_file = open(os.path.join(PROCESSED_DATA_DIR, 'movement_data.csv'), 'w', newline='') 
crowd_data_file = open(os.path.join(PROCESSED_DATA_DIR, 'crowd_data.csv'), 'w', newline='')

movement_data_writer = csv.writer(movement_data_file)
crowd_data_writer = csv.writer(crowd_data_file)

movement_data_writer.writerow(['Track ID', 'Entry time', 'Exit Time', 'Movement Tracks'])
crowd_data_writer.writerow(['Time', 'Human Count', 'Social Distance violate', 'Restricted Entry', 'Abnormal Activity'])

START_TIME_TS = time.time()

# Run the process with local writers for standalone testing
processing_FPS, _ = video_process(cap, FRAME_SIZE, net, ln, encoder, tracker, movement_data_writer, crowd_data_writer)
cv2.destroyAllWindows()

movement_data_file.close()
crowd_data_file.close()

END_TIME_TS = time.time()
PROCESS_TIME = END_TIME_TS - START_TIME_TS
print("Time elapsed: ", PROCESS_TIME)
if IS_CAM:
	print("Processed FPS: ", processing_FPS)
	VID_FPS = processing_FPS
	DATA_RECORD_FRAME = 1
else:
	if PROCESS_TIME > 0:
		print("Processed FPS: ", round(cap.get(cv2.CAP_PROP_FRAME_COUNT) / PROCESS_TIME, 2))
	else:
		print("Processed FPS: ", 0)
	VID_FPS = cap.get(cv2.CAP_PROP_FPS)
	# Handle case where FPS is 0 or invalid (corrupted video or unsupported format)
	if VID_FPS <= 0:
		print(f"Warning: Invalid FPS detected ({VID_FPS}). Using default FPS of 30.")
		VID_FPS = 30
	DATA_RECORD_FRAME = int(VID_FPS / DATA_RECORD_RATE)
	START_DT = VIDEO_CONFIG["START_TIME"]
	time_elapsed = round(cap.get(cv2.CAP_PROP_FRAME_COUNT) / VID_FPS)
	END_DT = START_DT + datetime.timedelta(seconds=time_elapsed)

cap.release()

video_data = {
	"IS_CAM": IS_CAM,
	"DATA_RECORD_FRAME" : DATA_RECORD_FRAME,
	"VID_FPS" : VID_FPS,
	"PROCESSED_FRAME_SIZE": FRAME_SIZE,
	"TRACK_MAX_AGE": TRACK_MAX_AGE,
	"START_TIME": START_DT.strftime("%d/%m/%Y, %H:%M:%S"),
	"END_TIME": END_DT.strftime("%d/%m/%Y, %H:%M:%S")
}

with open('processed_data/video_data.json', 'w') as video_data_file:
	json.dump(video_data, video_data_file)
