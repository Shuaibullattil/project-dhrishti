"""
Time-based tumbling window aggregation service for frame data.
Aggregates frame data into 5-second windows and generates crowd state classifications.
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Callable
from pymongo import ASCENDING
import sys
import os

# Add the project root to sys.path so we can import from app.services
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from db import db
from app.services.risk_engine import RiskEngine
import requests
import cv2
import numpy as np
import sys

# Ensure we use the exact same module instance as the main application to access shared state
if "video_process" in sys.modules:
    video_process = sys.modules["video_process"]
else:
    try:
        import video_process
    except ImportError:
        from crowd_analysis import video_process

# Global callback for broadcasting remarks (set by main.py)
_remark_broadcast_callback: Optional[Callable] = None

# Global automation alert tracking to prevent spam (session_id -> bool)
ALERT_TRIGGERED: Dict[str, bool] = {}

def set_remark_broadcast_callback(callback: Callable):
    """Set the callback function for broadcasting remarks via WebSocket."""
    global _remark_broadcast_callback
    _remark_broadcast_callback = callback


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


# Remove classify_crowd_state and generate_remark as we now use RiskEngine


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
    
    # Process Risk Engine Execution
    session = db.get_session(session_id)
    session_context = session.get("context", {}) if session else {}

    risk_result = RiskEngine.calculate_risk(session_context, aggregated)

    # Append new risk evaluation variables to aggregation
    aggregated["density"] = risk_result["density"]
    aggregated["motion_score"] = risk_result["motion_score"]
    aggregated["surge_score"] = risk_result["surge_score"]
    aggregated["risk_score"] = risk_result["risk_score"]
    aggregated["risk_level"] = risk_result["risk_level"]
    aggregated["risk_flags"] = risk_result["risk_flags"]

    # Temporarily retain severity and crowd_state to satisfy existing UI compatibility
    # Mapped backwards from Risk Levels
    compatibility_map = {
        "NORMAL": "LOW",
        "BUSY": "LOW",
        "WARNING": "MEDIUM",
        "CRITICAL": "HIGH"
    }
    aggregated["severity"] = compatibility_map.get(risk_result["risk_level"], "LOW")
    aggregated["crowd_state"] = risk_result["risk_level"]

    # Snapshot Trigger (Cloudinary Upload)
    if risk_result["risk_level"] in ["WARNING", "CRITICAL"]:
        try:
            from cloudinary_utils import upload_frame_to_cloudinary
            # Get the very last frame in the window to snapshot it
            latest_frame_idx = window_frames[-1].get("frame")
            
            # Since we can't capture physical frame images from Aggregator smoothly,
            # this logic can offload a trigger to the websocket/frontend or main processor,
            # currently, we mark the DB field. Real implementation might need video_process
            # integration to upload actual frame bytes, but logically we mark it here.
            aggregated["snapshot_required"] = True
            print(f"[{session_id}] Triggered context risk snapshot at frame {latest_frame_idx}")
        except Exception:
            pass

    # Automation Alert Integration using n8n
    if risk_result["risk_level"] == "CRITICAL" and not ALERT_TRIGGERED.get(session_id, False):
        try:
            print(f"[{session_id}] CRITICAL risk detected. Triggering automation alert.")
            
            # 1. Generate mid-session heatmap snapshot
            heatmap_path = None
            if session_id in video_process.HEATMAP_BGS:
                bg_frame = video_process.HEATMAP_BGS[session_id]
                final_heatmap = bg_frame.copy()
                
                if session_id in video_process.HEATMAP_POINTS and len(video_process.HEATMAP_POINTS[session_id]) > 0:
                    map_h, map_w = bg_frame.shape[:2]
                    heatmap_matrix = np.zeros((map_h, map_w), dtype=np.float32)
                    
                    for px, py in video_process.HEATMAP_POINTS[session_id]:
                        if 0 <= py < map_h and 0 <= px < map_w:
                            heatmap_matrix[py, px] += 1
                    
                    heatmap_blur = cv2.GaussianBlur(heatmap_matrix, (0, 0), sigmaX=31, sigmaY=31)
                    heatmap_norm = cv2.normalize(heatmap_blur, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
                    heatmap_color = cv2.applyColorMap(heatmap_norm, cv2.COLORMAP_JET)
                    
                    mask = heatmap_norm > 10
                    alpha = 0.6
                    
                    for c in range(3):
                        final_heatmap[:, :, c] = np.where(
                            mask,
                            cv2.addWeighted(bg_frame[:, :, c], 1 - alpha, heatmap_color[:, :, c], alpha, 0),
                            bg_frame[:, :, c]
                        )
                
                # Save locally instead of cloud
                heatmap_path = f"alert_heatmap_{session_id}.png"
                cv2.imwrite(heatmap_path, final_heatmap)
                print(f"[{session_id}] Generated local mid-session snapshot: {heatmap_path}")
            
            # 2. Prepare Webhook Payload for Multipart
            payload = {
                "session_id": session_id,
                "session_name": session.get("filename", "Unknown") if session else "Unknown",
                "risk_level": risk_result["risk_level"],
                "people_count": aggregated["avg_human_count"],
                "timestamp": str(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            }

            # 3. Send Webhook
            try:
                if heatmap_path and os.path.exists(heatmap_path):
                    with open(heatmap_path, "rb") as f:
                        files = {"heatmap": (os.path.basename(heatmap_path), f, "image/png")}
                        # Fire and forget with short timeout
                        requests.post("http://localhost:5678/webhook/drishti-alert", data=payload, files=files, timeout=3)
                else:
                    # Send metadata only if image failed
                    requests.post("http://localhost:5678/webhook/drishti-alert", data=payload, timeout=3)
            except Exception as e:
                print(f"[{session_id}] n8n Webhook failed: {e}")
            finally:
                if heatmap_path and os.path.exists(heatmap_path):
                    try:
                        os.remove(heatmap_path)
                    except:
                        pass
            
            # 4. Mark tracking flag and UI trigger
            ALERT_TRIGGERED[session_id] = True
            
            if _remark_broadcast_callback:
                import json
                alert_msg = {
                    "file_id": session_id,
                    "type": "automation_alert_sent",
                    "risk_level": risk_result["risk_level"],
                    "session_id": session_id
                }
                _remark_broadcast_callback(json.dumps(alert_msg, default=str))

        except Exception as e:
            print(f"[{session_id}] Error in automation alert sequence: {e}")
    
    # Generate remark based on risk flags
    flags = risk_result["risk_flags"]
    if flags:
        aggregated["remark"] = "Risk factors detected: " + ", ".join([f.replace("_", " ").title() for f in flags])
    else:
        aggregated["remark"] = "Crowd behavior within normal limits"
    
    # Save aggregated window
    db.aggregate_frame_data.insert_one(aggregated)
    
    # Update last window end
    update_last_window_end(session_id, window_end)
    
    # Broadcast new remark via WebSocket (if callback is set)
    if _remark_broadcast_callback:
        try:
            import json
            
            remark_message = {
                "file_id": session_id,
                "type": "remark",
                "data": {
                    "window_start": aggregated["window_start"].isoformat() if isinstance(aggregated["window_start"], datetime) else str(aggregated["window_start"]),
                    "window_end": aggregated["window_end"].isoformat() if isinstance(aggregated["window_end"], datetime) else str(aggregated["window_end"]),
                    "remark": aggregated["remark"],
                    "crowd_state": aggregated["crowd_state"],
                    "severity": aggregated["severity"],
                    "avg_human_count": aggregated["avg_human_count"],
                    "max_human_count": aggregated["max_human_count"],
                    "avg_motion_speed": aggregated["avg_motion_speed"],
                    "avg_fast_motion_ratio": aggregated["avg_fast_motion_ratio"],
                    "crowd_growth_rate": aggregated["crowd_growth_rate"],
                    "risk_score": aggregated["risk_score"],
                    "risk_level": aggregated["risk_level"]
                }
            }
            _remark_broadcast_callback(json.dumps(remark_message, default=str))
        except Exception:
            # Error broadcasting - continue silently
            pass
    
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

