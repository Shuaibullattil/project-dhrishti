"""
Cloudinary utility functions for uploading images
"""
import cloudinary
import cloudinary.uploader
from cloudinary.utils import cloudinary_url
import cv2
import numpy as np
from pathlib import Path
import os
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Cloudinary configuration
# Get from environment variables or use defaults
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

# Configure Cloudinary (only if cloud_name is provided)
if CLOUDINARY_CLOUD_NAME:
    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET
    )
else:
    print("Warning: CLOUDINARY_CLOUD_NAME not set. Cloudinary uploads will be disabled.")
    print("Please add CLOUDINARY_CLOUD_NAME to your .env file.")

def upload_frame_to_cloudinary(frame, session_id, frame_number, folder="abnormal_frames"):
    """
    Upload a frame (OpenCV image) to Cloudinary.
    
    Args:
        frame: OpenCV image (numpy array)
        session_id: Session ID for organizing uploads
        frame_number: Frame number for naming
        folder: Cloudinary folder path (default: "abnormal_frames")
    
    Returns:
        str: Cloudinary URL of the uploaded image, or None if upload fails
    """
    # Check if Cloudinary is configured
    if not CLOUDINARY_CLOUD_NAME:
        print("Cloudinary not configured: CLOUDINARY_CLOUD_NAME is missing")
        return None
    
    try:
        # Encode frame as JPEG
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        
        # Convert to bytes
        frame_bytes = buffer.tobytes()
        
        # Create unique public_id for the image (without folder prefix, as folder is set separately)
        public_id = f"{session_id}/frame_{frame_number}"
        
        # Upload to Cloudinary
        upload_result = cloudinary.uploader.upload(
            frame_bytes,
            public_id=public_id,
            folder=folder,
            resource_type="image",
            overwrite=True,
            format="jpg"
        )
        
        # Return the secure URL
        return upload_result.get('secure_url') or upload_result.get('url')
        
    except Exception as e:
        print(f"Error uploading frame to Cloudinary: {e}")
        return None

def upload_base64_to_cloudinary(base64_string, session_id, frame_number, folder="abnormal_frames"):
    """
    Upload a base64 encoded image to Cloudinary.
    
    Args:
        base64_string: Base64 encoded image string
        session_id: Session ID for organizing uploads
        frame_number: Frame number for naming
        folder: Cloudinary folder path (default: "abnormal_frames")
    
    Returns:
        str: Cloudinary URL of the uploaded image, or None if upload fails
    """
    try:
        import base64
        
        # Decode base64 to bytes
        image_bytes = base64.b64decode(base64_string)
        
        # Create unique public_id for the image (without folder prefix, as folder is set separately)
        public_id = f"{session_id}/frame_{frame_number}"
        
        # Upload to Cloudinary
        upload_result = cloudinary.uploader.upload(
            image_bytes,
            public_id=public_id,
            folder=folder,
            resource_type="image",
            overwrite=True,
            format="jpg"
        )
        
        # Return the secure URL
        return upload_result.get('secure_url') or upload_result.get('url')
        
    except Exception as e:
        print(f"Error uploading base64 image to Cloudinary: {e}")
        return None

