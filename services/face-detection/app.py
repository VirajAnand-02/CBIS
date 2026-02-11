# Face Detection Microservice
# Asynchronous face detection, recognition, and person management

import os
import asyncio
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import numpy as np
from io import BytesIO
import base64

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Face detection and recognition
import cv2
from PIL import Image
from deepface import DeepFace
import warnings
import logging
import requests

# Suppress DeepFace warnings
logging.getLogger().setLevel(logging.ERROR)
warnings.filterwarnings('ignore')

# Queue
from collections import deque
from threading import Lock

load_dotenv()

# ---------- CONFIG ----------
NEXTJS_API_URL = os.environ.get("NEXTJS_API_URL", "http://localhost:3000")
FACE_DETECTION_MODEL = os.environ.get("FACE_DETECTION_MODEL", "retinaface")
FACE_RECOGNITION_MODEL = os.environ.get("FACE_RECOGNITION_MODEL", "arcface")
MIN_FACE_SIZE = int(os.environ.get("MIN_FACE_SIZE", "40"))
MIN_CONFIDENCE = float(os.environ.get("MIN_CONFIDENCE", "0.6"))
RECOGNITION_THRESHOLD = float(os.environ.get("RECOGNITION_THRESHOLD", "0.4"))
MAX_QUEUE_SIZE = int(os.environ.get("MAX_QUEUE_SIZE", "1000"))

# Face crop storage
FACE_CROPS_DIR = Path("face_crops")
FACE_CROPS_DIR.mkdir(exist_ok=True)

# ---------- GLOBAL STATE ----------
processing_queue = deque()
queue_lock = Lock()
processing_active = False
gpu_configured = False

# Stats
stats = {
    "total_processed": 0,
    "faces_detected": 0,
    "persons_created": 0,
    "faces_matched": 0,
    "errors": 0,
    "queue_size": 0
}

# ---------- FASTAPI ----------
app = FastAPI(title="Face Detection & Recognition Service", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- MODELS ----------
class FaceDetectionRequest(BaseModel):
    blob_id: str
    priority: int = 5  # 1-10, higher = more urgent

class FaceDetectionResponse(BaseModel):
    task_id: str
    status: str
    message: str
    queue_position: int

class TaskStatusResponse(BaseModel):
    task_id: str
    status: str  # queued, processing, completed, failed
    blob_id: str
    faces_detected: Optional[int]
    persons_identified: Optional[int]
    error: Optional[str]
    completed_at: Optional[str]

# ---------- NEXT.JS API HELPERS ----------
async def call_nextjs_api(endpoint: str, method: str = "GET", json_data: Dict = None) -> Dict:
    """Call Next.js API endpoint"""
    url = f"{NEXTJS_API_URL}/api/{endpoint}"
    
    try:
        if method == "GET":
            response = requests.get(url, timeout=10)
        elif method == "POST":
            response = requests.post(url, json=json_data, timeout=10)
        elif method == "PUT":
            response = requests.put(url, json=json_data, timeout=10)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        response.raise_for_status()
        return response.json()
    
    except Exception as e:
        print(f"Next.js API call failed ({method} {endpoint}): {e}")
        raise

async def get_blob_url(blob_id: str) -> str:
    """Get blob file URL from Next.js"""
    return f"{NEXTJS_API_URL}/api/blobs/{blob_id}"

async def find_matching_person(embedding: np.ndarray, threshold: float) -> Optional[Tuple[str, float]]:
    """
    Find closest matching person using Next.js face search API
    Returns (person_id, similarity_score) or None
    """
    try:
        # Call Next.js face search endpoint
        result = await call_nextjs_api(
            "faces/search",
            method="POST",
            json_data={
                "embedding": embedding.tolist(),
                "threshold": 1 - threshold,  # Convert to distance threshold
                "limit": 1
            }
        )
        
        if result and len(result.get("matches", [])) > 0:
            match = result["matches"][0]
            return (match["personId"], match["similarity"])
        
        return None
        
    except Exception as e:
        print(f"Face search failed: {e}")
        return None

async def create_person(name: str, thumbnail: str = None) -> str:
    """Create a new person via Next.js API"""
    try:
        data = {"name": name}
        if thumbnail:
            data["thumbnail"] = thumbnail
            
        result = await call_nextjs_api(
            "persons",
            method="POST",
            json_data=data
        )
        
        stats["persons_created"] += 1
        return result["id"]
        
    except Exception as e:
        print(f"Failed to create person: {e}")
        raise

async def update_person_thumbnail(person_id: str, thumbnail: str) -> None:
    """Update person thumbnail via Next.js API"""
    try:
        await call_nextjs_api(
            f"persons/{person_id}",
            method="PATCH",
            json_data={"thumbnail": thumbnail}
        )
        print(f"Updated thumbnail for person {person_id}")
        
    except Exception as e:
        print(f"Failed to update person thumbnail: {e}")
        # Don't raise - thumbnail update is not critical

async def create_face_instance(
    blob_id: str,
    person_id: str,
    bounding_box: Dict,
    embedding: np.ndarray,
    confidence: float,
    quality: float
) -> str:
    """Create face instance via Next.js API"""
    try:
        result = await call_nextjs_api(
            "faces",
            method="POST",
            json_data={
                "blobId": blob_id,
                "personId": person_id,
                "boundingBox": bounding_box,
                "embedding": embedding.tolist(),
                "confidence": confidence,
                "quality": quality,
                "detectorModel": FACE_DETECTION_MODEL,
                "embeddingModel": FACE_RECOGNITION_MODEL
            }
        )
        
        return result["id"]
        
    except Exception as e:
        print(f"Failed to create face instance: {e}")
        raise

# ---------- GPU CONFIGURATION ----------
def configure_gpu():
    """Configure GPU settings for TensorFlow"""
    global gpu_configured
    
    if gpu_configured:
        return
    
    try:
        import tensorflow as tf
        import torch
        
        print("\n=== GPU Configuration ===")
        
        # TensorFlow GPU check
        gpus = tf.config.list_physical_devices('GPU')
        if gpus:
            try:
                # Enable memory growth to prevent TF from allocating all GPU memory
                for gpu in gpus:
                    tf.config.experimental.set_memory_growth(gpu, True)
                print(f"TensorFlow - GPU available: {len(gpus)} GPU(s)")
                print(f"TensorFlow - GPU devices: {[gpu.name for gpu in gpus]}")
            except RuntimeError as e:
                print(f"TensorFlow GPU configuration error: {e}")
        else:
            print("TensorFlow - No GPU detected, using CPU")
        
        # PyTorch GPU check
        if torch.cuda.is_available():
            print(f"PyTorch - CUDA available: {torch.cuda.get_device_name(0)}")
            print(f"PyTorch - CUDA version: {torch.version.cuda}")
        else:
            print("PyTorch - No CUDA detected, using CPU")
        
        print("=" * 40 + "\n")
        gpu_configured = True
        
    except Exception as e:
        print(f"GPU configuration warning: {e}")
        gpu_configured = True

# ---------- FACE DETECTION & RECOGNITION ----------
def calculate_face_quality(bounding_box: Dict, img_width: int, img_height: int, confidence: float) -> float:
    """
    Calculate face quality score based on:
    - Size (larger = better)
    - Detection confidence
    - Position (centered = better)
    """
    # Size quality (normalized)
    face_area = bounding_box['width'] * bounding_box['height']
    size_quality = min(1.0, face_area * 4)  # Assume 25% of image is optimal
    
    # Position quality (centered faces are better)
    center_x = bounding_box['x'] + bounding_box['width'] / 2
    center_y = bounding_box['y'] + bounding_box['height'] / 2
    dist_from_center = np.sqrt((center_x - 0.5)**2 + (center_y - 0.5)**2)
    position_quality = 1.0 - min(1.0, dist_from_center * 2)
    
    # Combine metrics
    return (size_quality * 0.4 + confidence * 0.4 + position_quality * 0.2)

def save_face_crop(image: np.ndarray, bbox: np.ndarray, face_id: str) -> str:
    """Save cropped face image"""
    x1, y1, x2, y2 = bbox.astype(int)
    
    # Add padding (10%)
    h, w = image.shape[:2]
    padding = int(min(x2 - x1, y2 - y1) * 0.1)
    x1 = max(0, x1 - padding)
    y1 = max(0, y1 - padding)
    x2 = min(w, x2 + padding)
    y2 = min(h, y2 + padding)
    
    # Crop face
    face_crop = image[y1:y2, x1:x2]
    
    # Save
    crop_path = FACE_CROPS_DIR / f"{face_id}.jpg"
    cv2.imwrite(str(crop_path), cv2.cvtColor(face_crop, cv2.COLOR_RGB2BGR))
    
    return str(crop_path)

def generate_thumbnail_base64(image: np.ndarray, bbox: Dict, size: int = 128) -> str:
    """Generate base64 encoded thumbnail from face crop"""
    # Extract bounding box coordinates (already in pixel values)
    x = int(bbox['x'])
    y = int(bbox['y'])
    w = int(bbox['w'])
    h = int(bbox['h'])
    
    # Add padding (10%)
    img_h, img_w = image.shape[:2]
    padding = int(min(w, h) * 0.1)
    x1 = max(0, x - padding)
    y1 = max(0, y - padding)
    x2 = min(img_w, x + w + padding)
    y2 = min(img_h, y + h + padding)
    
    # Crop face
    face_crop = image[y1:y2, x1:x2]
    
    # Convert to PIL Image
    face_pil = Image.fromarray(cv2.cvtColor(face_crop, cv2.COLOR_BGR2RGB))
    
    # Resize to thumbnail size
    face_pil.thumbnail((size, size), Image.Resampling.LANCZOS)
    
    # Convert to base64
    buffer = BytesIO()
    face_pil.save(buffer, format='JPEG', quality=85)
    thumbnail_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    return f"data:image/jpeg;base64,{thumbnail_base64}"

async def download_blob_image(blob_id: str) -> str:
    """Download blob image from Next.js and save temporarily"""
    try:
        # Get blob URL
        blob_url = await get_blob_url(blob_id)
        
        # Download image
        response = requests.get(blob_url, timeout=30)
        response.raise_for_status()
        
        # Save temporarily
        temp_dir = Path("temp_images")
        temp_dir.mkdir(exist_ok=True)
        
        temp_path = temp_dir / f"{blob_id}.jpg"
        with open(temp_path, 'wb') as f:
            f.write(response.content)
        
        return str(temp_path)
        
    except Exception as e:
        print(f"Failed to download blob {blob_id}: {e}")
        raise

async def process_image(blob_id: str) -> Dict:
    """
    Main face detection and recognition pipeline using DeepFace
    """
    result = {
        "blob_id": blob_id,
        "faces_detected": 0,
        "faces_processed": 0,
        "persons_matched": 0,
        "persons_created": 0,
        "errors": []
    }
    
    t_total_start = time.perf_counter()
    temp_image_path = None
    
    try:
        # 1. Download image from Next.js
        print(f"[{blob_id}] Downloading image from Next.js...")
        temp_image_path = await download_blob_image(blob_id)
        
        print(f"[{blob_id}] Detecting faces with DeepFace (RetinaFace + ArcFace)...")
        
        # 2. Detect and extract faces using DeepFace
        t_detect_start = time.perf_counter()
        try:
            # DeepFace.represent returns list of face embeddings
            face_objs = DeepFace.represent(
                img_path=temp_image_path,
                model_name="ArcFace",
                detector_backend="retinaface",
                enforce_detection=False,
                align=True
            )
        except Exception as e:
            print(f"[{blob_id}] DeepFace detection failed: {e}")
            return result
        
        t_detect_end = time.perf_counter()
        
        if not face_objs:
            print(f"[{blob_id}] No faces detected")
            return result
        
        result["faces_detected"] = len(face_objs)
        print(f"[{blob_id}] Found {len(face_objs)} face(s) in {t_detect_end - t_detect_start:.3f}s")
        
        # Get image dimensions for normalization
        img = cv2.imread(temp_image_path)
        img_height, img_width = img.shape[:2]
        
        # 3. Process each detected face
        for idx, face_obj in enumerate(face_objs):
            try:
                # Extract data from DeepFace result
                embedding = np.array(face_obj["embedding"])
                facial_area = face_obj.get("facial_area", {})
                
                # Get bounding box
                x = facial_area.get("x", 0)
                y = facial_area.get("y", 0)
                w = facial_area.get("w", 0)
                h = facial_area.get("h", 0)
                
                # Filter by size
                if w < MIN_FACE_SIZE or h < MIN_FACE_SIZE:
                    print(f"[{blob_id}] Face {idx+1}: Too small ({w}x{h}), skipping")
                    continue
                
                # Normalize bounding box (0-1)
                normalized_bbox = {
                    "x": float(x) / img_width,
                    "y": float(y) / img_height,
                    "width": float(w) / img_width,
                    "height": float(h) / img_height
                }
                
                # Estimate confidence (DeepFace doesn't return this directly)
                confidence = face_obj.get("confidence", 0.9)
                
                # Calculate quality
                quality = calculate_face_quality(normalized_bbox, img_width, img_height, confidence)
                
                print(f"[{blob_id}] Face {idx+1}: Embedding extracted (dim: {len(embedding)}), quality: {quality:.2f}")
                
                # 4. Find matching person
                print(f"[{blob_id}] Face {idx+1}: Searching for matching person...")
                t_match_start = time.perf_counter()
                match = await find_matching_person(embedding, RECOGNITION_THRESHOLD)
                t_match_end = time.perf_counter()
                
                # Generate thumbnail for this face
                thumbnail_base64 = None
                try:
                    thumbnail_base64 = generate_thumbnail_base64(img, facial_area)
                except Exception as e:
                    print(f"[{blob_id}] Face {idx+1}: Failed to generate thumbnail: {e}")
                
                person_id = None
                if match:
                    person_id, similarity = match
                    print(f"[{blob_id}] Face {idx+1}: Matched to person {person_id} (similarity: {similarity:.3f}) in {t_match_end - t_match_start:.3f}s")
                    result["persons_matched"] += 1
                    stats["faces_matched"] += 1
                    
                    # Update thumbnail if person doesn't have one
                    if thumbnail_base64:
                        try:
                            # Check if person has thumbnail
                            person_data = await call_nextjs_api(f"persons/{person_id}", method="GET")
                            if not person_data.get("thumbnail"):
                                await update_person_thumbnail(person_id, thumbnail_base64)
                        except Exception as e:
                            print(f"[{blob_id}] Face {idx+1}: Failed to check/update thumbnail: {e}")
                else:
                    # Create new person with thumbnail
                    unknown_count = stats["persons_created"] + 1
                    person_name = f"Unknown Person #{unknown_count}"
                    person_id = await create_person(person_name, thumbnail_base64)
                    print(f"[{blob_id}] Face {idx+1}: Created new person {person_id} ({person_name})")
                    result["persons_created"] += 1
                
                # 5. Create face instance in database
                face_instance_id = await create_face_instance(
                    blob_id=blob_id,
                    person_id=person_id,
                    bounding_box=normalized_bbox,
                    embedding=embedding,
                    confidence=confidence,
                    quality=quality
                )
                
                result["faces_processed"] += 1
                stats["faces_detected"] += 1
                
                print(f"[{blob_id}] Face {idx+1}: Processed successfully (face_id: {face_instance_id})")
                
            except Exception as e:
                error_msg = f"Face {idx+1} processing error: {str(e)}"
                print(f"[{blob_id}] {error_msg}")
                result["errors"].append(error_msg)
        
        t_total_end = time.perf_counter()
        print(f"[{blob_id}] Completed: {result['faces_processed']}/{result['faces_detected']} faces processed in {t_total_end - t_total_start:.3f}s")
        
    except Exception as e:
        error_msg = f"Image processing error: {str(e)}"
        print(f"[{blob_id}] {error_msg}")
        result["errors"].append(error_msg)
        stats["errors"] += 1
    
    finally:
        # Clean up temporary image
        if temp_image_path and Path(temp_image_path).exists():
            try:
                Path(temp_image_path).unlink()
            except:
                pass
    
    return result

# ---------- QUEUE MANAGEMENT ----------
async def process_queue_worker():
    """Background worker to process queue"""
    global processing_active
    
    print("Queue worker started")
    
    while processing_active:
        task = None
        
        with queue_lock:
            if processing_queue:
                task = processing_queue.popleft()
                stats["queue_size"] = len(processing_queue)
        
        if task:
            task_id, blob_id, priority, enqueued_at = task
            
            print(f"\n[Task {task_id}] Processing blob {blob_id}")
            print(f"[Task {task_id}] Wait time: {time.time() - enqueued_at:.1f}s")
            
            try:
                result = await process_image(blob_id)
                stats["total_processed"] += 1
                
                print(f"[Task {task_id}] Completed successfully")
                print(f"[Task {task_id}] Result: {result}")
                
            except Exception as e:
                print(f"[Task {task_id}] Failed: {str(e)}")
                stats["errors"] += 1
        else:
            # Queue empty, wait a bit
            await asyncio.sleep(0.5)

def start_queue_worker():
    """Start background queue worker"""
    global processing_active
    processing_active = True
    asyncio.create_task(process_queue_worker())

def stop_queue_worker():
    """Stop background queue worker"""
    global processing_active
    processing_active = False

# ---------- STARTUP/SHUTDOWN ----------
@app.on_event("startup")
async def startup_event():
    print("=" * 60)
    print("Face Detection & Recognition Service Starting...")
    print("=" * 60)
    
    # Configure GPU
    configure_gpu()
    
    # Pre-load DeepFace models to avoid delays on first request
    print("Pre-loading DeepFace models (RetinaFace + ArcFace)...")
    try:
        import tempfile
        import numpy as np
        
        # Create a dummy image to trigger model loading
        dummy_img = np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8)
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            cv2.imwrite(tmp.name, dummy_img)
            temp_path = tmp.name
        
        try:
            # This will download and cache the models
            DeepFace.represent(
                img_path=temp_path,
                model_name="ArcFace",
                detector_backend="retinaface",
                enforce_detection=False
            )
            print("✓ Models loaded successfully")
        finally:
            # Clean up temp file
            Path(temp_path).unlink(missing_ok=True)
            
    except Exception as e:
        print(f"⚠ Warning: Failed to pre-load models: {e}")
        print("  Models will be downloaded on first request")
    
    print(f"✓ Service configured")
    print(f"  Detection backend: {FACE_DETECTION_MODEL} (RetinaFace)")
    print(f"  Recognition model: {FACE_RECOGNITION_MODEL} (ArcFace - 512D)")
    print(f"  Recognition threshold: {RECOGNITION_THRESHOLD}")
    print(f"  Min face size: {MIN_FACE_SIZE}px")
    print(f"  Min confidence: {MIN_CONFIDENCE}")
    
    # Start queue worker
    start_queue_worker()
    print("✓ Queue worker started")
    
    print("=" * 60)
    print("Service ready on http://0.0.0.0:8005")
    print("=" * 60)

@app.on_event("shutdown")
async def shutdown_event():
    print("\nShutting down...")
    stop_queue_worker()
    print("✓ Queue worker stopped")

# ---------- API ROUTES ----------
@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "face_detection",
        "version": "1.0",
        "models": {
            "detector": FACE_DETECTION_MODEL,
            "recognition": FACE_RECOGNITION_MODEL
        },
        "config": {
            "threshold": RECOGNITION_THRESHOLD,
            "min_face_size": MIN_FACE_SIZE,
            "min_confidence": MIN_CONFIDENCE
        },
        "stats": stats
    }

@app.post("/detect", response_model=FaceDetectionResponse)
async def enqueue_face_detection(request: FaceDetectionRequest):
    """
    Enqueue face detection task
    Returns immediately with task ID
    """
    # Check queue size
    if len(processing_queue) >= MAX_QUEUE_SIZE:
        raise HTTPException(status_code=503, detail="Queue is full, try again later")
    
    # Generate task ID
    task_id = str(uuid.uuid4())
    
    # Add to queue
    task = (task_id, request.blob_id, request.priority, time.time())
    
    with queue_lock:
        # Insert based on priority (higher priority first)
        inserted = False
        for i, existing_task in enumerate(processing_queue):
            if request.priority > existing_task[2]:  # priority is now index 2
                processing_queue.insert(i, task)
                inserted = True
                break
        
        if not inserted:
            processing_queue.append(task)
        
        queue_position = list(processing_queue).index(task) + 1
        stats["queue_size"] = len(processing_queue)
    
    print(f"\n[Task {task_id}] Enqueued blob {request.blob_id}")
    print(f"[Task {task_id}] Queue position: {queue_position}")
    print(f"[Task {task_id}] Priority: {request.priority}")
    
    return FaceDetectionResponse(
        task_id=task_id,
        status="queued",
        message=f"Face detection task enqueued for blob {request.blob_id}",
        queue_position=queue_position
    )

@app.get("/queue/stats")
def get_queue_stats():
    """Get queue statistics"""
    return {
        "queue_size": len(processing_queue),
        "processing": processing_active,
        "stats": stats
    }

@app.get("/queue/clear")
def clear_queue():
    """Clear all pending tasks (admin endpoint)"""
    with queue_lock:
        cleared = len(processing_queue)
        processing_queue.clear()
        stats["queue_size"] = 0
    
    return {
        "cleared": cleared,
        "message": f"Cleared {cleared} pending tasks"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
