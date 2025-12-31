"""
Time-based tumbling window aggregation service for frame data.
Aggregates frame data into 5-second windows and generates crowd state classifications.
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pymongo import ASCENDING
from db import db


def normalize_datetime(dt) -> datetime:
    """Convert various datetime formats to datetime object."""
    if isinstance(dt, datetime):
        return dt
    elif isinstance(dt, str):
        # Handle ISO format strings
        dt = dt.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(dt)
        except:
            # Fallback for other formats
            return datetime.fromisoformat(dt.replace("Z", ""))
    return dt


def get_unprocessed_frames(session_id: str, last_window_end: Optional[datetime]) -> List[Dict]:
    """
    Fetch frames that haven't been aggregated yet for a session.
    
    Args:
        session_id: Session identifier
        last_window_end: Timestamp of last processed window (None if first time)
    
    Returns:
        List of frame documents sorted by timestamp
    """
    query = {"session_id": session_id}
    
    if last_window_end:
        query["timestamp"] = {"$gt": last_window_end}
    
    frames = list(db.yolov.find(query, {"_id": 0}).sort("timestamp", ASCENDING))
    return frames


def aggregate_window(frames: List[Dict], window_start: datetime, window_end: datetime) -> Optional[Dict]:
    """
    Aggregate frames within a time window.
    
    Args:
        frames: List of frame documents in the window
        window_start: Start timestamp of the window
        window_end: End timestamp of the window
    
    Returns:
        Aggregated document or None if insufficient frames
    """
    if len(frames) < 3:  # Minimum frames required
        return None
    
    # Extract metrics
    human_counts = [f.get("human_count", 0) for f in frames]
    bbox_areas = [f.get("avg_bbox_area", 0.0) for f in frames]
    density_scores = [f.get("crowd_density_score", 0.0) for f in frames]
    motion_speeds = [f.get("avg_motion_speed", 0.0) for f in frames]
    fast_motion_ratios = [f.get("fast_motion_ratio", 0.0) for f in frames]
    abnormal_scores = [f.get("frame_abnormal_score", 0.0) for f in frames]
    restricted_entries = [f.get("restricted_entry", False) for f in frames]
    
    # Calculate aggregated metrics
    aggregated = {
        "session_id": frames[0]["session_id"],
        "window_start": window_start,
        "window_end": window_end,
        "frame_count": len(frames),
        "avg_human_count": round(sum(human_counts) / len(human_counts), 2) if human_counts else 0.0,
        "max_human_count": max(human_counts) if human_counts else 0,
        "avg_bbox_area": round(sum(bbox_areas) / len(bbox_areas), 4) if bbox_areas else 0.0,
        "max_density_score": round(max(density_scores), 4) if density_scores else 0.0,
        "avg_motion_speed": round(sum(motion_speeds) / len(motion_speeds), 4) if motion_speeds else 0.0,
        "avg_fast_motion_ratio": round(sum(fast_motion_ratios) / len(fast_motion_ratios), 4) if fast_motion_ratios else 0.0,
        "avg_abnormal_score": round(sum(abnormal_scores) / len(abnormal_scores), 4) if abnormal_scores else 0.0,
        "restricted_entry_detected": any(restricted_entries),
        "timestamp": window_end
    }
    
    return aggregated


def calculate_crowd_growth_rate(session_id: str, current_avg_human_count: float) -> float:
    """
    Calculate crowd growth rate by comparing with previous window.
    
    Args:
        session_id: Session identifier
        current_avg_human_count: Average human count of current window
    
    Returns:
        Growth rate (0.0 if no previous window exists)
    """
    # Get the most recent aggregated window for this session
    last_aggregate = db.aggregate_frame_data.find_one(
        {"session_id": session_id},
        sort=[("window_end", -1)]
    )
    
    if not last_aggregate or "avg_human_count" not in last_aggregate:
        return 0.0
    
    previous_avg = last_aggregate.get("avg_human_count", 0.0)
    
    if previous_avg == 0:
        return 0.0
    
    growth_rate = (current_avg_human_count - previous_avg) / previous_avg
    return round(growth_rate, 4)


def classify_crowd_state(
    max_density_score: float,
    avg_fast_motion_ratio: float,
    crowd_growth_rate: float,
    avg_abnormal_score: float
) -> Tuple[str, str]:
    """
    Classify crowd state and severity based on rule-based logic.
    
    Args:
        max_density_score: Maximum density score in window
        avg_fast_motion_ratio: Average fast motion ratio
        crowd_growth_rate: Crowd growth rate
        avg_abnormal_score: Average abnormal score
    
    Returns:
        Tuple of (crowd_state, severity)
    """
    # Rule 1: DENSE_FAST_MOVING
    if max_density_score > 18 and avg_fast_motion_ratio > 0.8:
        return "DENSE_FAST_MOVING", "CRITICAL"
    
    # Rule 2: SUDDEN_SURGE
    if crowd_growth_rate > 0.25:
        return "SUDDEN_SURGE", "HIGH"
    
    # Rule 3: SUSTAINED_ABNORMAL
    if avg_abnormal_score > 0.7:
        return "SUSTAINED_ABNORMAL", "MEDIUM"
    
    # Default: NORMAL
    return "NORMAL", "LOW"


def generate_remark(crowd_state: str) -> str:
    """
    Generate a remark based on crowd state.
    
    Args:
        crowd_state: Classified crowd state
    
    Returns:
        Human-readable remark string
    """
    remarks = {
        "DENSE_FAST_MOVING": "Extremely dense crowd with widespread fast movement detected",
        "SUDDEN_SURGE": "Sudden increase in crowd density observed",
        "SUSTAINED_ABNORMAL": "Sustained abnormal movement detected",
        "NORMAL": "Crowd behavior within normal limits"
    }
    
    return remarks.get(crowd_state, "Crowd behavior within normal limits")


def get_last_window_end(session_id: str) -> Optional[datetime]:
    """
    Get the last processed window end timestamp for a session.
    
    Args:
        session_id: Session identifier
    
    Returns:
        Last window end datetime or None
    """
    last_state = db.last_aggregate_frame.find_one({"session_id": session_id})
    
    if last_state and "last_window_end" in last_state:
        return normalize_datetime(last_state["last_window_end"])
    
    return None


def update_last_window_end(session_id: str, window_end: datetime):
    """
    Update the last processed window end timestamp for a session.
    
    Args:
        session_id: Session identifier
        window_end: End timestamp of processed window
    """
    db.last_aggregate_frame.update_one(
        {"session_id": session_id},
        {
            "$set": {
                "session_id": session_id,
                "last_window_end": window_end
            }
        },
        upsert=True
    )


def process_session_window(session_id: str) -> bool:
    """
    Process one 5-second window for a session.
    
    Args:
        session_id: Session identifier
    
    Returns:
        True if a window was processed, False otherwise
    """
    # Get last processed window end
    last_window_end = get_last_window_end(session_id)
    
    # Get unprocessed frames
    frames = get_unprocessed_frames(session_id, last_window_end)
    
    if len(frames) < 3:
        return False  # Not enough frames for a window
    
    # Determine window boundaries
    if last_window_end:
        window_start = last_window_end
    else:
        # First window: start from first frame
        first_frame_time = normalize_datetime(frames[0].get("timestamp"))
        window_start = first_frame_time
    
    window_end = window_start + timedelta(seconds=5)
    
    # Filter frames within the window
    window_frames = []
    for frame in frames:
        frame_time = normalize_datetime(frame.get("timestamp"))
        
        if window_start <= frame_time < window_end:
            window_frames.append(frame)
        elif frame_time >= window_end:
            break  # Frames are sorted, so we can stop
    
    if len(window_frames) < 3:
        return False  # Not enough frames in this window
    
    # Aggregate the window
    aggregated = aggregate_window(window_frames, window_start, window_end)
    
    if not aggregated:
        return False
    
    # Calculate crowd growth rate
    crowd_growth_rate = calculate_crowd_growth_rate(session_id, aggregated["avg_human_count"])
    aggregated["crowd_growth_rate"] = crowd_growth_rate
    
    # Classify crowd state
    crowd_state, severity = classify_crowd_state(
        aggregated["max_density_score"],
        aggregated["avg_fast_motion_ratio"],
        crowd_growth_rate,
        aggregated["avg_abnormal_score"]
    )
    
    aggregated["crowd_state"] = crowd_state
    aggregated["severity"] = severity
    
    # Generate remark
    aggregated["remark"] = generate_remark(crowd_state)
    
    # Save aggregated window
    db.aggregate_frame_data.insert_one(aggregated)
    
    # Update last window end
    update_last_window_end(session_id, window_end)
    
    return True


def get_active_sessions() -> List[str]:
    """
    Get list of active session IDs that have frames but may not be fully aggregated.
    Active sessions are those that:
    1. Have frames in the last 30 seconds (currently processing or recently completed)
    2. Have unprocessed frames
    
    Returns:
        List of active session IDs
    """
    from datetime import datetime, timedelta
    
    # Get sessions with frames in the last 30 seconds (active/recent)
    recent_time = datetime.utcnow() - timedelta(seconds=30)
    
    # Find sessions with recent frames
    recent_sessions = db.yolov.distinct(
        "session_id",
        {"timestamp": {"$gte": recent_time}}
    )
    
    # Also check for sessions with unprocessed frames (may have completed but not aggregated)
    all_sessions = db.yolov.distinct("session_id")
    
    # Combine and deduplicate
    active_sessions = list(set(recent_sessions + all_sessions))
    
    # Filter to only sessions that have unprocessed frames
    active_with_unprocessed = []
    for session_id in active_sessions:
        last_window_end = get_last_window_end(session_id)
        unprocessed = get_unprocessed_frames(session_id, last_window_end)
        if len(unprocessed) >= 3:  # Has enough frames for at least one window
            active_with_unprocessed.append(session_id)
    
    return active_with_unprocessed


def run_window_aggregator():
    """
    Main aggregator function that processes windows for all active sessions.
    Processes one window per session per call to avoid blocking.
    
    Returns:
        Number of windows processed
    """
    active_sessions = get_active_sessions()
    processed_count = 0
    
    for session_id in active_sessions:
        try:
            if process_session_window(session_id):
                processed_count += 1
        except Exception as e:
            print(f"Error processing session {session_id}: {e}")
            continue
    
    return processed_count


def run_window_aggregator_for_session(session_id: str) -> int:
    """
    Process all available windows for a specific session.
    
    Args:
        session_id: Session identifier
    
    Returns:
        Number of windows processed
    """
    processed_count = 0
    
    while True:
        try:
            if process_session_window(session_id):
                processed_count += 1
            else:
                break  # No more windows to process
        except Exception as e:
            print(f"Error processing session {session_id}: {e}")
            break
    
    return processed_count

