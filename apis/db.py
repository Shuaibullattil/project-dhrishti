from pymongo import MongoClient
from pymongo.server_api import ServerApi
import os
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file in project root
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME", "video_output")  # Default value if not set

if not MONGO_URI:
    raise ValueError("MONGO_URI environment variable is not set. Please check your .env file.")

class MongoDB:
    def __init__(self):
        self.client = MongoClient(MONGO_URI, server_api=ServerApi('1'))
        self.db = self.client[DB_NAME]
        self.sessions = self.db["session"]
        self.yolov = self.db["yolov"]
        self.abnormal_stats = self.db["abnormal_statistics"]

    def ping(self):
        try:
            self.client.admin.command('ping')
            return True
        except Exception as e:
            print(f"MongoDB Ping failed: {e}")
            return False

    # Session methods
    def create_session(self, session_id, filename):
        session_doc = {
            "session_id": session_id,
            "filename": filename,
            "status": "processing",
            "start_time": datetime.now(),
            "video_meta": {},
            "summary": {
                "peak_count": 0,
                "total_abnormal_frames": 0,
                "total_violations": 0
            },
            "movement_data": []
        }
        self.sessions.insert_one(session_doc)

    def update_session_meta(self, session_id, meta):
        self.sessions.update_one(
            {"session_id": session_id},
            {"$set": {"video_meta": meta}}
        )

    def complete_session(self, session_id, summary, movement_data):
        self.sessions.update_one(
            {"session_id": session_id},
            {"$set": {
                "status": "completed",
                "end_time": datetime.now(),
                "summary": summary,
                "movement_data": movement_data
            }}
        )

    def fail_session(self, session_id, error):
        self.sessions.update_one(
            {"session_id": session_id},
            {"$set": {"status": "failed", "error": error, "end_time": datetime.now()}}
        )

    # Frame data methods
    def insert_frame_data(self, session_id, frame_data):
        frame_doc = {
            "session_id": session_id,
            **frame_data,
            "timestamp": datetime.now()
        }
        self.yolov.insert_one(frame_doc)

    # Abnormal stats methods
    def insert_abnormal_stats(self, session_id, original_stats, cleaned_stats):
        doc = {
            "session_id": session_id,
            "original": original_stats,
            "cleaned": cleaned_stats,
            "created_at": datetime.now()
        }
        self.abnormal_stats.insert_one(doc)

    # Retrieval methods
    def get_all_sessions(self):
        return list(self.sessions.find({}, {"_id": 0}).sort("start_time", -1))

    def get_session(self, session_id):
        return self.sessions.find_one({"session_id": session_id}, {"_id": 0})

    def get_session_trends(self, session_id):
        return list(self.yolov.find({"session_id": session_id}, {"_id": 0}).sort("frame", 1))

    def get_abnormal_stats(self, session_id):
        return self.abnormal_stats.find_one({"session_id": session_id}, {"_id": 0})

db = MongoDB()
