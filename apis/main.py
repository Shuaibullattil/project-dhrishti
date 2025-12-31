import os
import shutil
import uuid
import json
import asyncio
import datetime
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict, Any
from contextlib import asynccontextmanager

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    raise TypeError ("Type %s not serializable" % type(obj))

# Import existing logic (need to adjust paths)
import sys
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Root of the project
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
CROWD_ANALYSIS_PATH = os.path.join(PROJECT_ROOT, "crowd_analysis")
sys.path.append(CROWD_ANALYSIS_PATH)

from main_api import run_processing, get_analysis_results
from db import db
from aggregator import run_window_aggregator
from contextlib import asynccontextmanager

# Background task control
aggregation_task = None
aggregation_running = False

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - start and stop background tasks."""
    global aggregation_task, aggregation_running
    
    # Start background aggregation task
    aggregation_running = True
    aggregation_task = asyncio.create_task(background_aggregation_loop())
    
    yield
    
    # Stop background aggregation task
    aggregation_running = False
    if aggregation_task:
        aggregation_task.cancel()
        try:
            await aggregation_task
        except asyncio.CancelledError:
            pass

app = FastAPI(title="Project Dhrishti API", lifespan=lifespan)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = os.path.join(SCRIPT_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Shared state for real-time updates
active_processing: Dict[str, Dict] = {}

# Shared state for real-time updates
active_processing: Dict[str, Dict] = {}

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                pass

manager = ConnectionManager()
executor = ThreadPoolExecutor(max_workers=4)
loop = asyncio.get_event_loop()

def sync_broadcast(message: str):
    """Thread-safe wrapper to broadcast from a synchronous context."""
    asyncio.run_coroutine_threadsafe(manager.broadcast(message), loop)

async def background_aggregation_loop():
    """Background task that runs aggregation every 5 seconds for active sessions."""
    global aggregation_running
    
    while aggregation_running:
        try:
            # Run aggregation in executor to avoid blocking
            await loop.run_in_executor(executor, run_window_aggregator)
            # Wait 5 seconds before next iteration
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"Error in background aggregation: {e}")
            await asyncio.sleep(5)  # Wait before retrying

@app.post("/upload")
async def upload_video(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    file_id = str(uuid.uuid4())
    file_path = os.path.abspath(os.path.join(UPLOAD_DIR, f"{file_id}_{file.filename}"))
    
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    active_processing[file_id] = {"status": "queued", "progress": 0, "count": 0}
    
    # Initialize session in MongoDB
    db.create_session(file_id, file.filename)
    
    # Start background processing
    background_tasks.add_task(process_video_task, file_id, file_path)
    
    return {"file_id": file_id, "filename": file.filename}

async def process_video_task(file_id: str, file_path: str):
    active_processing[file_id]["status"] = "processing"
    
    def on_progress(data):
        active_processing[file_id].update(data)
        sync_broadcast(json.dumps({"file_id": file_id, "type": "realtime", "data": data}, default=json_serial))

    try:
        # Run in executor to avoid blocking
        await loop.run_in_executor(executor, run_processing, file_path, file_id, on_progress)
        
        # Get final analysis results from MongoDB
        analysis = get_analysis_results(file_id)
        
        active_processing[file_id]["status"] = "completed"
        active_processing[file_id]["analysis"] = analysis
        
        # Update session in MongoDB with final analysis
        db.complete_session(file_id, analysis["summary"], analysis.get("movement_data", []))
        
        # Run aggregation for completed session
        try:
            from aggregator import run_window_aggregator_for_session
            run_window_aggregator_for_session(file_id)
        except Exception as e:
            print(f"Error running aggregation for session {file_id}: {e}")
        
        sync_broadcast(json.dumps({
            "file_id": file_id, 
            "status": "completed", 
            "analysis": analysis
        }, default=json_serial))
        
        # Cleanup uploaded video file
        if os.path.exists(file_path):
            os.remove(file_path)
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        active_processing[file_id]["status"] = "failed"
        active_processing[file_id]["error"] = str(e)
        sync_broadcast(json.dumps({"file_id": file_id, "status": "failed", "error": str(e)}))

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/status/{file_id}")
async def get_status(file_id: str):
    return active_processing.get(file_id, {"status": "not_found"})

@app.get("/sessions")
async def get_sessions():
    return db.get_all_sessions()

@app.get("/sessions/{session_id}")
async def get_session_details(session_id: str):
    analysis = get_analysis_results(session_id)
    if "error" in analysis:
        return analysis
    
    abnormal_stats = db.get_abnormal_stats(session_id)
    abnormal_frames = db.get_abnormal_frames(session_id)
    
    return {
        "session": {
            "session_id": session_id,
            "video_meta": analysis["meta"],
            "summary": analysis["summary"]
        },
        "trends": analysis["trends"],
        "abnormal_stats": abnormal_stats,
        "abnormal_frames": abnormal_frames
    }

@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    # Delete from MongoDB
    success = db.delete_session(session_id)
    
    if success:
        return {"message": f"Session {session_id} deleted successfully"}
    else:
        return {"error": "Failed to delete session"}

@app.post("/aggregate/run")
async def run_aggregation():
    """Run window aggregation for all active sessions."""
    from aggregator import run_window_aggregator
    try:
        processed_count = run_window_aggregator()
        return {
            "message": "Aggregation completed",
            "windows_processed": processed_count
        }
    except Exception as e:
        return {"error": str(e)}

@app.post("/aggregate/session/{session_id}")
async def run_aggregation_for_session(session_id: str):
    """Run window aggregation for a specific session."""
    from aggregator import run_window_aggregator_for_session
    try:
        processed_count = run_window_aggregator_for_session(session_id)
        return {
            "message": f"Aggregation completed for session {session_id}",
            "windows_processed": processed_count
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/sessions/{session_id}/aggregated")
async def get_aggregated_windows(session_id: str):
    """Get all aggregated windows for a session."""
    windows = db.get_aggregated_windows(session_id)
    return windows

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
