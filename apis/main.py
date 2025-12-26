import os
import shutil
import uuid
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict

# Import existing logic (need to adjust paths)
import sys
CROWD_ANALYSIS_PATH = os.path.abspath("../crowd_analysis")
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

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Downloads folder path
DOWNLOADS_DIR = os.path.join(os.path.expanduser("~"), "Downloads", "Dhrishti_Outputs")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

# Static serving for images in Downloads (so UI can see them)
app.mount("/outputs", StaticFiles(directory=DOWNLOADS_DIR), name="outputs")

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
        sync_broadcast(json.dumps({"file_id": file_id, "type": "realtime", "data": data}))

    try:
        # Run in executor to avoid blocking
        results_dir = await loop.run_in_executor(executor, run_processing, file_path, file_id, on_progress)
        
        # Get final analysis results
        analysis = get_analysis_results(results_dir)
        
        # Move results to Downloads
        final_dest = os.path.join(DOWNLOADS_DIR, file_id)
        if os.path.exists(results_dir):
            shutil.move(results_dir, final_dest)
            
            active_processing[file_id]["status"] = "completed"
            active_processing[file_id]["analysis"] = analysis
            active_processing[file_id]["output_url_base"] = f"/outputs/{file_id}"
            
            # Update session in MongoDB with final analysis
            db.complete_session(file_id, analysis["summary"], analysis.get("movement_data", []))
            
            sync_broadcast(json.dumps({
                "file_id": file_id, 
                "status": "completed", 
                "analysis": analysis,
                "output_url_base": f"/outputs/{file_id}"
            }))
        else:
            raise Exception("Results directory not found")
            
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
    session = db.get_session(session_id)
    if not session:
        return {"error": "Session not found"}
    
    trends = db.get_session_trends(session_id)
    abnormal_stats = db.get_abnormal_stats(session_id)
    
    return {
        "session": session,
        "trends": trends,
        "abnormal_stats": abnormal_stats
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
