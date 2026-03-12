import numpy as np
from ultralytics import YOLO
import supervision as sv

from config import MIN_CONF


class ByteTrackPerson:
	def __init__(self, track_id, entry, tlbr):
		self.track_id = track_id
		self.entry = entry
		self.exit = None
		self.positions = []
		self.time_since_update = 0
		self.hits = 0
		self._tlbr = np.asarray(tlbr, dtype=np.float32)
		self._confirmed = True
		self._update_geometry(self._tlbr)

	@property
	def id(self):
		return self.track_id

	def _update_geometry(self, tlbr):
		self._tlbr = np.asarray(tlbr, dtype=np.float32)
		x1, y1, x2, y2 = self._tlbr
		cx = int((x1 + x2) / 2.0)
		cy = int((y1 + y2) / 2.0)
		self.positions.append((cx, cy))
		self.hits += 1
		self.time_since_update = 0

	def update(self, tlbr):
		self._update_geometry(tlbr)

	def mark_missed(self):
		self.time_since_update += 1

	def to_tlwh(self):
		x1, y1, x2, y2 = self._tlbr
		return np.array([x1, y1, x2 - x1, y2 - y1], dtype=np.float32)

	def to_tlbr(self):
		return self._tlbr.copy()

	def is_confirmed(self):
		return self._confirmed

	def to_legacy_dict(self):
		x1, y1, x2, y2 = list(map(int, self.to_tlbr().tolist()))
		return {
			"id": int(self.track_id),
			"x1": x1,
			"y1": y1,
			"x2": x2,
			"y2": y2,
		}


class ByteTrackAdapter:
	def __init__(self, frame_rate=30, max_age=30, n_init=3):
		self._tracker = sv.ByteTrack(
			track_activation_threshold=MIN_CONF,
			lost_track_buffer=max_age,
			minimum_matching_threshold=0.8,
			frame_rate=frame_rate,
			minimum_consecutive_frames=n_init,
		)
		self.tracks = []
		self._tracks_by_id = {}
		self._removed_ids = set()

	def update(self, detections, time):
		detections = np.asarray(detections, dtype=np.float32)
		if detections.size == 0:
			detections = np.empty((0, 5), dtype=np.float32)
		elif detections.ndim == 1:
			detections = detections.reshape(1, 5)

		byte_tracks = self._tracker.update_with_tensors(detections)
		active_ids = set()
		active_tracks = []

		for byte_track in byte_tracks:
			track_id = int(byte_track.external_track_id)
			if track_id <= 0:
				continue

			person = self._tracks_by_id.get(track_id)
			if person is None:
				person = ByteTrackPerson(track_id=track_id, entry=time, tlbr=byte_track.tlbr)
				self._tracks_by_id[track_id] = person
			else:
				person.update(byte_track.tlbr)

			active_ids.add(track_id)
			active_tracks.append(person)

		for track_id, person in list(self._tracks_by_id.items()):
			if track_id not in active_ids:
				person.mark_missed()

		expired = []
		removed_ids = {
			int(track.external_track_id)
			for track in self._tracker.removed_tracks
			if int(track.external_track_id) > 0
		}
		newly_removed_ids = removed_ids - self._removed_ids
		for track_id in sorted(newly_removed_ids):
			person = self._tracks_by_id.pop(track_id, None)
			if person is None:
				continue
			person.exit = time
			expired.append(person)

		self._removed_ids.update(newly_removed_ids)
		self.tracks = active_tracks
		return expired


def load_detector(model_path):
	return YOLO(model_path)


def create_tracker(frame_rate=30, max_age=30, n_init=3):
	return ByteTrackAdapter(frame_rate=frame_rate, max_age=max_age, n_init=n_init)


def adapt_track_to_legacy_format(track):
	if hasattr(track, "to_legacy_dict"):
		return track.to_legacy_dict()

	x1, y1, x2, y2 = list(map(int, track.to_tlbr().tolist()))
	return {
		"id": int(track.track_id),
		"x1": x1,
		"y1": y1,
		"x2": x2,
		"y2": y2,
	}


def adapt_tracks_to_legacy_format(tracks):
	return [adapt_track_to_legacy_format(track) for track in tracks]


def extract_person_detections(model, frame):
	results = model(frame, verbose=False)[0]
	detections = []

	for result in results.boxes:
		if int(result.cls[0]) != 0:
			continue

		confidence = float(result.conf[0])
		if confidence <= MIN_CONF:
			continue

		x1, y1, x2, y2 = result.xyxy[0].tolist()
		detections.append({
			"x1": int(x1),
			"y1": int(y1),
			"x2": int(x2),
			"y2": int(y2),
			"confidence": confidence,
		})

	return detections


def detections_to_bytetrack_input(raw_detections):
	if not raw_detections:
		return np.empty((0, 5), dtype=np.float32)

	return np.asarray(
		[
			[
				detection["x1"],
				detection["y1"],
				detection["x2"],
				detection["y2"],
				detection["confidence"],
			]
			for detection in raw_detections
		],
		dtype=np.float32,
	)


def detect_human(net, ln, frame, encoder, tracker, time):
	raw_detections = extract_person_detections(net, frame)
	detections = detections_to_bytetrack_input(raw_detections)
	expired = tracker.update(detections, time)

	tracked_bboxes = []
	for track in tracker.tracks:
		if not track.is_confirmed() or track.time_since_update > 5:
			continue
		tracked_bboxes.append(track)

	return [tracked_bboxes, expired]
