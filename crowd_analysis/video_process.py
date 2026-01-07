import time
import datetime
import numpy as np
import imutils
import cv2
import time
import base64
from math import ceil
from scipy.spatial.distance import euclidean
from tracking import detect_human
from util import rect_distance, progress, kinetic_energy
from colors import RGB_COLORS
from config import SHOW_DETECT, DATA_RECORD, RE_CHECK, RE_START_TIME, RE_END_TIME, SD_CHECK, SHOW_VIOLATION_COUNT, SHOW_TRACKING_ID, SOCIAL_DISTANCE,\
	SHOW_PROCESSING_OUTPUT, YOLO_CONFIG, VIDEO_CONFIG, DATA_RECORD_RATE, ABNORMAL_CHECK, ABNORMAL_ENERGY, ABNORMAL_THRESH, ABNORMAL_MIN_PEOPLE, SPEED_THRESHOLD
from deep_sort import nn_matching
from deep_sort.detection import Detection
from deep_sort.tracker import Tracker
from deep_sort import generate_detections as gdet

# Try to import db and cloudinary_utils
try:
    import sys
    import os
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "apis")))
    from db import db
    from cloudinary_utils import upload_frame_to_cloudinary
    cloudinary_available = True
except ImportError as e:
    db = None
    cloudinary_available = False
    print(f"Cloudinary not available: {e}")

IS_CAM = VIDEO_CONFIG["IS_CAM"]
HIGH_CAM = VIDEO_CONFIG["HIGH_CAM"]

def _record_movement_data(movement_data_writer, movement):
	if movement_data_writer is None:
		if hasattr(movement, 'positions'): # Track object
			track_id = movement.track_id 
			entry_time = movement.entry 
			exit_time = movement.exit		
			positions = list(np.array(movement.positions).flatten())
			return [track_id, entry_time, exit_time] + positions
		return None
	track_id = movement.track_id 
	entry_time = movement.entry 
	exit_time = movement.exit		
	positions = movement.positions
	positions = np.array(positions).flatten()
	positions = list(positions)
	data = [track_id] + [entry_time] + [exit_time] + positions
	movement_data_writer.writerow(data)

def _record_crowd_data(time, human_count, violate_count, restricted_entry, abnormal_activity, crowd_data_writer):
	if crowd_data_writer is None:
		return
	data = [time, human_count, violate_count, int(restricted_entry), int(abnormal_activity)]
	crowd_data_writer.writerow(data)

def _end_video(tracker, frame_count, movement_data_writer):
	data_list = []
	for t in tracker.tracks:
		if t.is_confirmed():
			t.exit = frame_count
			res = _record_movement_data(movement_data_writer, t)
			if res: data_list.append(res)
	return data_list
		

def video_process(cap, frame_size, net, ln, encoder, tracker, movement_data_writer, crowd_data_writer, callback=None, session_id=None):
	def _calculate_FPS():
		t1 = time.time() - t0
		VID_FPS = frame_count / t1

	if IS_CAM:
		VID_FPS = None
		DATA_RECORD_FRAME = 1
		TIME_STEP = 1
		t0 = time.time()
	else:
		VID_FPS = cap.get(cv2.CAP_PROP_FPS)
		# Handle case where FPS is 0 or invalid (corrupted video or unsupported format)
		if VID_FPS <= 0:
			print(f"Warning: Invalid FPS detected ({VID_FPS}). Using default FPS of 30.")
			VID_FPS = 30
		DATA_RECORD_FRAME = int(VID_FPS / DATA_RECORD_RATE)
		TIME_STEP = DATA_RECORD_FRAME/VID_FPS

	frame_count = 0
	display_frame_count = 0
	re_warning_timeout = 0
	sd_warning_timeout = 0
	ab_warning_timeout = 0
	
	collected_movement_data = []

	RE = False
	ABNORMAL = False

	while True:
		(ret, frame) = cap.read()

		# Stop the loop when video ends
		if not ret:
			res = _end_video(tracker, frame_count, movement_data_writer)
			if res: collected_movement_data.extend(res)
			if not VID_FPS:
				_calculate_FPS()
			break

		# Update frame count
		if frame_count > 1000000:
			if not VID_FPS:
				_calculate_FPS()
			frame_count = 0
			display_frame_count = 0
		frame_count += 1
		
		# Skip frames according to given rate
		if frame_count % DATA_RECORD_FRAME != 0:
			continue

		display_frame_count += 1

		# Resize Frame to given size (preserve aspect ratio for vertical/horizontal videos)
		h, w = frame.shape[:2]
		if h > w:  # Vertical video (portrait)
			frame = imutils.resize(frame, height=frame_size)
		else:  # Horizontal video (landscape)
			frame = imutils.resize(frame, width=frame_size)

		# Get current time
		current_datetime = datetime.datetime.now()

		# Run detection algorithm
		if IS_CAM:
			record_time = current_datetime
		else:
			record_time = frame_count
		
		# Run tracking algorithm
		[humans_detected, expired] = detect_human(net, ln, frame, encoder, tracker, record_time)

		# Record movement data
		for movement in expired:
			res = _record_movement_data(movement_data_writer, movement)
			if res: collected_movement_data.append(res)
		
		# Check for restricted entry
		if RE_CHECK:
			RE = False
			if (current_datetime.time() > RE_START_TIME) and (current_datetime.time() < RE_END_TIME) :
				if len(humans_detected) > 0:
					RE = True
			
		# Initiate video process loop
		if SHOW_PROCESSING_OUTPUT or SHOW_DETECT or SD_CHECK or RE_CHECK or ABNORMAL_CHECK:
			# Initialize set for violate so an individual will be recorded only once
			violate_set = set()
			# Initialize list to record violation count for each individual detected
			violate_count = np.zeros(len(humans_detected))

			# Initialize list to record id of individual with abnormal energy level
			# abnormal_individual: stores track_id of each person whose KE exceeds ABNORMAL_ENERGY threshold
			abnormal_individual = []
			# ABNORMAL: frame-level flag set to True if proportion of abnormal people exceeds ABNORMAL_THRESH
			ABNORMAL = False
			for i, track in enumerate(humans_detected):
				# Get object bounding box
				[x, y, w, h] = list(map(int, track.to_tlbr().tolist()))
				# Get object centroid
				[cx, cy] = list(map(int, track.positions[-1]))
				# Get object id
				idx = track.track_id
				# Check for social distance violation
				if SD_CHECK:
					if len(humans_detected) >= 2:
						# Check the distance between current loop object with the rest of the object in the list
						for j, track_2 in enumerate(humans_detected[i+1:], start=i+1):
							if HIGH_CAM:
								[cx_2, cy_2] = list(map(int, track_2.positions[-1]))
								distance = euclidean((cx, cy), (cx_2, cy_2))
							else:
								[x_2, y_2, w_2, h_2] = list(map(int, track_2.to_tlbr().tolist()))
								distance = rect_distance((x, y, w, h), (x_2, y_2, w_2, h_2))
							if distance < SOCIAL_DISTANCE:
								# Distance between detection less than minimum social distance 
								violate_set.add(i)
								violate_count[i] += 1
								violate_set.add(j)
								violate_count[j] += 1

				# Per-person abnormal detection: calculate kinetic energy (speed-based metric)
				if ABNORMAL_CHECK:
					# KE = 0.5 * (speed)^2 where speed = pixel distance / TIME_STEP
					if len(track.positions) >= 2:
						ke = kinetic_energy(track.positions[-1], track.positions[-2], TIME_STEP)
						# ABNORMAL_ENERGY: threshold (default=1866) above which a person's movement is flagged
						# If any person's KE > ABNORMAL_ENERGY, add their ID to abnormal_individual list
						if ke > ABNORMAL_ENERGY:
							abnormal_individual.append(track.track_id)

				# If restrited entry is on, draw red boxes around each detection
				if RE:
					cv2.rectangle(frame, (x + 5 , y + 5 ), (w - 5, h - 5), RGB_COLORS["red"], 5)

				# Draw yellow boxes for detection with social distance violation, green boxes for no violation
				# Place a number of violation count on top of the box
				if i in violate_set:
					cv2.rectangle(frame, (x, y), (w, h), RGB_COLORS["yellow"], 2)
					if SHOW_VIOLATION_COUNT:
						cv2.putText(frame, str(int(violate_count[i])), (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, RGB_COLORS["yellow"], 2)
				elif SHOW_DETECT and not RE:
					cv2.rectangle(frame, (x, y), (w, h), RGB_COLORS["green"], 2)
					if SHOW_VIOLATION_COUNT:
						cv2.putText(frame, str(int(violate_count[i])), (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, RGB_COLORS["green"], 2)
				
				if SHOW_TRACKING_ID:
					cv2.putText(frame, str(int(idx)), (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, RGB_COLORS["green"], 2)
			
			# Check for overall abnormal level, trigger notification if exceeds threshold
			# Frame-level abnormal detection: decide if crowd behavior is abnormal
			# ABNORMAL_MIN_PEOPLE (default=5): minimum crowd size to check for abnormal behavior
			if len(humans_detected) > ABNORMAL_MIN_PEOPLE:
				# ABNORMAL_THRESH (default=0.66): proportion of abnormal people needed to flag frame
				# Example: if 5+ people detected and >66% are moving abnormally, set ABNORMAL=True
				if len(abnormal_individual) / len(humans_detected) > ABNORMAL_THRESH:
					ABNORMAL = True

		# Place violation count on frames
		if SD_CHECK:
			# Warning stays on screen for 10 frames
			if (len(violate_set) > 0):
				sd_warning_timeout = 10
			else: 
				sd_warning_timeout -= 1
			# Display violation warning and count on screen
			if sd_warning_timeout > 0:
				text = "Violation count: {}".format(len(violate_set))
				cv2.putText(frame, text, (200, frame.shape[0] - 30),
					cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)

		# Place restricted entry warning
		if RE_CHECK:
			# Warning stays on screen for 10 frames
			if RE:
				re_warning_timeout = 10
			else: 
				re_warning_timeout -= 1
			# Display restricted entry warning and count on screen
			if re_warning_timeout > 0:
				if display_frame_count % 3 != 0 :
					cv2.putText(frame, "RESTRICTED ENTRY", (200, 100),
						cv2.FONT_HERSHEY_SIMPLEX, 1, RGB_COLORS["red"], 3)

		# Place abnormal activity warning
		if ABNORMAL_CHECK:
			if ABNORMAL:
				# Warning stays on screen for 10 frames
				ab_warning_timeout = 10
				# Draw blue boxes over the the abnormally behave detection if abnormal activity detected
				for track in humans_detected:
					if track.track_id in abnormal_individual:
						[x, y, w, h] = list(map(int, track.to_tlbr().tolist()))
						cv2.rectangle(frame, (x , y ), (w, h), RGB_COLORS["blue"], 5)
			else:
				ab_warning_timeout -= 1
			if ab_warning_timeout > 0:
				if display_frame_count % 3 != 0:
					cv2.putText(frame, "ABNORMAL ACTIVITY", (130, 250),
						cv2.FONT_HERSHEY_SIMPLEX, 1.5, RGB_COLORS["blue"], 5)

		# Display crowd count on screen
		if SHOW_DETECT:
			text = "Crowd count: {}".format(len(humans_detected))
			cv2.putText(frame, text, (10, 30),
				cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 3)

		# Display current time on screen
		# current_date = str(current_datetime.strftime("%b-%d-%Y"))
		# current_time = str(current_datetime.strftime("%I:%M:%S %p"))
		# cv2.putText(frame, (current_date), (500, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 3)
		# cv2.putText(frame, (current_time), (500, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 3)
			
		# Store cloudinary_url for callback
		cloudinary_url_for_callback = None
		
		# Calculate new metrics for frame analysis
		# Get frame dimensions for normalization
		frame_height, frame_width = frame.shape[:2]
		frame_area = frame_width * frame_height
		
		# Initialize metric accumulators
		bbox_areas = []
		motion_speeds = []
		fast_motion_count = 0
		
		# Calculate metrics for each tracked person
		for track in humans_detected:
			# 1. Calculate bounding box area (normalized)
			[x, y, w, h] = list(map(int, track.to_tlbr().tolist()))
			bbox_area = w * h
			normalized_area = bbox_area / frame_area if frame_area > 0 else 0.0
			bbox_areas.append(normalized_area)
			
			# 2. Calculate motion speed (if previous position exists)
			if len(track.positions) >= 2:
				current_pos = track.positions[-1]
				previous_pos = track.positions[-2]
				# Calculate distance moved
				distance = euclidean(current_pos, previous_pos)
				# Speed = distance / time_delta
				speed = distance / TIME_STEP if TIME_STEP > 0 else 0.0
				motion_speeds.append(speed)
				
				# Count fast motion
				if speed > SPEED_THRESHOLD:
					fast_motion_count += 1
			else:
				# No previous position, speed is 0
				motion_speeds.append(0.0)
		
		# Calculate aggregated metrics
		avg_bbox_area = np.mean(bbox_areas) if len(bbox_areas) > 0 else 0.0
		crowd_density_score = len(humans_detected) * avg_bbox_area
		avg_motion_speed = np.mean(motion_speeds) if len(motion_speeds) > 0 else 0.0
		fast_motion_ratio = fast_motion_count / len(humans_detected) if len(humans_detected) > 0 else 0.0
		
		# Calculate frame_abnormal_score (weighted combination)
		# Normalize each component to 0-1 range (using reasonable max values)
		max_human_count = 50  # Reasonable max for normalization
		max_speed = 50.0  # Reasonable max speed for normalization
		max_density = 10.0  # Reasonable max density score
		
		normalized_human_count = min(len(humans_detected) / max_human_count, 1.0) if max_human_count > 0 else 0.0
		normalized_speed = min(avg_motion_speed / max_speed, 1.0) if max_speed > 0 else 0.0
		normalized_density = min(crowd_density_score / max_density, 1.0) if max_density > 0 else 0.0
		
		frame_abnormal_score = (
			0.4 * normalized_human_count +
			0.3 * normalized_speed +
			0.3 * normalized_density
		)
		
		# Record crowd data to file
		if DATA_RECORD:
			_record_crowd_data(record_time, len(humans_detected), len(violate_set), RE, ABNORMAL, crowd_data_writer)
			
			# For standalone testing: print metrics every 30 frames
			if not db and display_frame_count % 30 == 0:
				print(f"\nFrame {frame_count} Metrics:")
				print(f"  Human Count: {len(humans_detected)}")
				print(f"  Avg BBox Area: {avg_bbox_area:.4f}")
				print(f"  Crowd Density Score: {crowd_density_score:.4f}")
				print(f"  Avg Motion Speed: {avg_motion_speed:.4f}")
				print(f"  Fast Motion Ratio: {fast_motion_ratio:.4f}")
				print(f"  Frame Abnormal Score: {frame_abnormal_score:.4f}")
			
			if db and session_id:
				# Prepare frame data with all metrics
				frame_data = {
					"frame": frame_count,
					"human_count": len(humans_detected),
					"violate_count": len(violate_set),
					"restricted_entry": bool(RE),
					"abnormal_activity": bool(ABNORMAL),
					# New metrics
					"avg_bbox_area": round(float(avg_bbox_area), 4),
					"crowd_density_score": round(float(crowd_density_score), 4),
					"avg_motion_speed": round(float(avg_motion_speed), 4),
					"fast_motion_ratio": round(float(fast_motion_ratio), 4),
					"frame_abnormal_score": round(float(frame_abnormal_score), 4)
				}
				
				# Upload to Cloudinary if abnormal activity is detected
				if ABNORMAL and cloudinary_available:
					uploaded_url = upload_frame_to_cloudinary(
						frame, 
						session_id, 
						frame_count,
						folder="abnormal_frames"
					)
					if uploaded_url:
						frame_data["cloudinary_url"] = uploaded_url
						cloudinary_url_for_callback = uploaded_url
						print(f"Uploaded abnormal frame {frame_count} to Cloudinary: {uploaded_url}")
				
				# Insert frame data into MongoDB
				db.insert_frame_data(session_id, frame_data)

		# Display video output or processing indicator
		if SHOW_PROCESSING_OUTPUT:
			cv2.imshow("Processed Output", frame)
		else:
			progress(display_frame_count)

		if callback:
			# Encode frame as base64 JPEG for WebSocket transmission
			# Resize frame to reduce data size (max width 800px for better performance)
			frame_for_transmission = frame.copy()
			h, w = frame_for_transmission.shape[:2]
			if w > 800:
				scale = 800 / w
				new_w = 800
				new_h = int(h * scale)
				frame_for_transmission = cv2.resize(frame_for_transmission, (new_w, new_h))
			
			# Encode frame as JPEG
			_, buffer = cv2.imencode('.jpg', frame_for_transmission, [cv2.IMWRITE_JPEG_QUALITY, 85])
			frame_base64 = base64.b64encode(buffer).decode('utf-8')
			
			# Prepare callback data
			callback_data = {
				"human_count": len(humans_detected),
				"violate_count": len(violate_set),
				"abnormal": ABNORMAL,
				"restricted_entry": RE,
				"frame": frame_count,
				"frame_image": frame_base64  # Base64 encoded JPEG image
			}
			
			# Add cloudinary_url if abnormal frame was uploaded
			if cloudinary_url_for_callback:
				callback_data["cloudinary_url"] = cloudinary_url_for_callback
			
			callback(callback_data)

		# Press 'Q' to stop the video display
		if cv2.waitKey(1) & 0xFF == ord('q'):
			# Record the movement when video ends
			_end_video(tracker, frame_count, movement_data_writer)
			# Compute the processing speed
			if not VID_FPS:
				_calculate_FPS()
			break
	
	cv2.destroyAllWindows()
	return VID_FPS, collected_movement_data
