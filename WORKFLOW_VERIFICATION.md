# Aggregation Workflow Verification

## Complete Workflow Trace

### 1. New Session Starts
**Location:** `apis/main.py` → `POST /upload`

1. User uploads video
2. Session created: `db.create_session(file_id, file.filename)`
   - Stored in `sessions` collection
3. Video processing starts: `process_video_task(file_id, file_path)`
4. **Frames stored in `yolov` collection:**
   - `crowd_analysis/video_process.py` line 389: `db.insert_frame_data(session_id, frame_data)`
   - `apis/db.py` line 149-155: Stores frame with `session_id`, `timestamp`, and all metrics
   - Each frame document includes:
     - `session_id`
     - `frame`, `human_count`, `violate_count`, etc.
     - `avg_bbox_area`, `crowd_density_score`, `avg_motion_speed`, etc.
     - `timestamp` (automatically added)

### 2. Background Aggregation (Every 5 Seconds)
**Location:** `apis/main.py` → `background_aggregation_loop()`

1. **Background task starts on app startup:**
   - `lifespan()` context manager starts the task (line 45)
   - Task runs continuously every 5 seconds (line 113)

2. **Every 5 seconds, the loop:**
   - Calls `run_window_aggregator()` (line 111)
   - Gets active sessions with unprocessed frames
   - Processes one window per session

### 3. Aggregation Process
**Location:** `apis/aggregator.py` → `process_session_window()`

For each active session:

1. **Get last processed timestamp:**
   - `get_last_window_end(session_id)` (line 222)
   - Reads from `last_aggregate_frame` collection
   - Returns `None` if first time (no previous aggregation)

2. **Fetch unprocessed frames from `yolov` collection:**
   - `get_unprocessed_frames(session_id, last_window_end)` (line 225)
   - Query: `{"session_id": session_id, "timestamp": {"$gt": last_window_end}}`
   - Returns frames sorted by timestamp (ASCENDING)
   - If `last_window_end` is `None`, gets all frames for the session

3. **Create 5-second window:**
   - If first window: starts from first frame's timestamp (line 235-236)
   - If subsequent: starts from `last_window_end` (line 232)
   - Window end: `window_start + 5 seconds` (line 238)

4. **Filter frames within window:**
   - Only includes frames where: `window_start <= frame_time < window_end` (line 245)

5. **Aggregate window:**
   - Calculates all metrics (avg, max, etc.) (line 254)
   - Calculates `crowd_growth_rate` (line 260)
   - Classifies `crowd_state` and `severity` (line 264-272)
   - Generates `remark` (line 275)

6. **Store aggregated data:**
   - **Saves to `aggregate_frame_data` collection:** (line 278)
     ```python
     db.aggregate_frame_data.insert_one(aggregated)
     ```
   - Document includes:
     - `session_id`, `window_start`, `window_end`
     - All aggregated metrics
     - `crowd_state`, `severity`, `remark`
     - `timestamp` (set to `window_end`)

7. **Update last processed timestamp:**
   - **Updates `last_aggregate_frame` collection:** (line 281)
     ```python
     update_last_window_end(session_id, window_end)
     ```
   - Stores: `{"session_id": session_id, "last_window_end": window_end}`
   - Uses `upsert=True` to create if doesn't exist

## Data Flow Summary

```
New Session → Video Processing
    ↓
Frames stored in `yolov` collection
    ↓
Background Task (every 5 seconds)
    ↓
Read from `yolov` collection (unprocessed frames)
    ↓
Aggregate into 5-second windows
    ↓
Store in `aggregate_frame_data` collection
    ↓
Update `last_aggregate_frame` collection (timestamp)
```

## Collections Used

1. **`yolov`** - Source collection
   - Stores individual frame data
   - Query: `{"session_id": session_id, "timestamp": {"$gt": last_window_end}}`

2. **`aggregate_frame_data`** - Destination collection
   - Stores aggregated window data
   - One document per 5-second window

3. **`last_aggregate_frame`** - Tracking collection
   - Stores last processed window end timestamp per session
   - Used to prevent re-aggregation

## Verification Checklist

✅ Frames stored in `yolov` when session starts  
✅ Background task runs every 5 seconds  
✅ Reads from `yolov` collection  
✅ Filters by `session_id` and `timestamp > last_window_end`  
✅ Creates 5-second windows  
✅ Aggregates frame data  
✅ Stores in `aggregate_frame_data` collection  
✅ Updates `last_aggregate_frame` with timestamp  
✅ Prevents re-aggregation of processed frames  

