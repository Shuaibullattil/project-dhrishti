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

app = FastAPI(title="Project Dhrishti API")

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
    
    return {
        "session": {
            "session_id": session_id,
            "video_meta": analysis["meta"],
            "summary": analysis["summary"]
        },
        "trends": analysis["trends"],
        "abnormal_stats": abnormal_stats
    }

@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    # Delete from MongoDB
    success = db.delete_session(session_id)
    
    if success:
        return {"message": f"Session {session_id} deleted successfully"}
    else:
        return {"error": "Failed to delete session"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
