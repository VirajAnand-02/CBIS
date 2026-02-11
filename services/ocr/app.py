"""
OCR Service using docTR
Provides text extraction from images via REST API
"""

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import torch
from doctr.io import DocumentFile
from doctr.models import ocr_predictor
import cv2
import numpy as np
from PIL import Image
import io
import time
import logging
import warnings
import os
from typing import Optional, Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Suppress font warnings from docTR
logging.getLogger('root').setLevel(logging.ERROR)
warnings.filterwarnings('ignore')

# Initialize FastAPI app
app = FastAPI(
    title="OCR Service",
    description="Text extraction service using docTR with GPU support",
    version="1.0.0"
)

# Global variables for model and device
predictor = None
device = None

class OCRResponse(BaseModel):
    """Response model for OCR extraction"""
    text: str
    confidence: Optional[float] = None
    timings: Dict[str, float]
    device: str
    words_count: int

class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    device: str
    cuda_available: bool
    model_loaded: bool

def configure_gpu():
    """Configure GPU settings for PyTorch"""
    global device
    
    if torch.cuda.is_available():
        device = torch.device("cuda")
        logger.info(f"GPU detected: {torch.cuda.get_device_name(0)}")
        logger.info(f"CUDA Version: {torch.version.cuda}")
        logger.info(f"Available VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")
    else:
        device = torch.device("cpu")
        logger.warning("No GPU detected, using CPU")
    
    return device

def load_model():
    """Load docTR OCR model"""
    global predictor, device
    
    try:
        logger.info("Loading docTR OCR model...")
        predictor = ocr_predictor(pretrained=True, assume_straight_pages=False)
        
        # Move to device - don't use .half() as it can cause detection issues
        if device.type == "cuda":
            predictor.to(device)
            logger.info("Model loaded on GPU (FP32)")
        else:
            logger.info("Model loaded on CPU")
        
        return True
    except Exception as e:
        logger.error(f"Error loading model: {e}")
        return False

def preprocess_image(image_bytes: bytes, apply_enhancements: bool = False) -> np.ndarray:
    """
    Preprocess image from bytes
    
    Args:
        image_bytes: Raw image bytes
        apply_enhancements: Apply denoising and sharpening
    
    Returns:
        Preprocessed image array
    """
    # Convert bytes to numpy array
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    if img is None:
        raise ValueError("Failed to decode image")
    
    if apply_enhancements:
        # Denoising (minimal to preserve details)
        img = cv2.fastNlMeansDenoisingColored(img, h=10)
        # Sharpening
        kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
        img = cv2.filter2D(img, -1, kernel)
    
    return img

def extract_text_from_bytes(image_bytes: bytes, apply_enhancements: bool = False) -> Dict[str, Any]:
    """
    Extract text from image bytes
    
    Args:
        image_bytes: Raw image bytes
        apply_enhancements: Apply preprocessing enhancements
    
    Returns:
        Dictionary with text, timings, and metadata
    """
    t_total_start = time.perf_counter()
    
    # Preprocess if needed
    if apply_enhancements:
        t_prep_start = time.perf_counter()
        img = preprocess_image(image_bytes, apply_enhancements=True)
        # Convert back to bytes
        _, buffer = cv2.imencode('.png', img)
        image_bytes = buffer.tobytes()
        t_prep_end = time.perf_counter()
        prep_time = t_prep_end - t_prep_start
    else:
        prep_time = 0.0
    
    # Load document from bytes
    t_doc_start = time.perf_counter()
    pil_image = Image.open(io.BytesIO(image_bytes))
    doc = DocumentFile.from_images([pil_image])
    t_doc_end = time.perf_counter()
    
    # OCR inference
    if device.type == "cuda":
        torch.cuda.synchronize()
    t_inf_start = time.perf_counter()
    result = predictor(doc)
    if device.type == "cuda":
        torch.cuda.synchronize()
    t_inf_end = time.perf_counter()
    
    # Aggregate text using render() method and calculate average confidence
    t_agg_start = time.perf_counter()
    full_text = result.render()
    
    # Calculate average confidence from word-level data
    total_confidence = 0.0
    word_count = 0
    
    for page in result.pages:
        for block in page.blocks:
            for line in block.lines:
                for word in line.words:
                    total_confidence += word.confidence
                    word_count += 1
    
    avg_confidence = total_confidence / word_count if word_count > 0 else 0.0
    t_agg_end = time.perf_counter()
    
    timings = {
        "preprocessing_s": prep_time,
        "doc_load_s": t_doc_end - t_doc_start,
        "inference_s": t_inf_end - t_inf_start,
        "aggregation_s": t_agg_end - t_agg_start,
        "total_s": time.perf_counter() - t_total_start,
    }
    
    return {
        "text": full_text,
        "confidence": avg_confidence,
        "timings": timings,
        "words_count": word_count
    }

@app.on_event("startup")
async def startup_event():
    """Initialize model on startup"""
    configure_gpu()
    success = load_model()
    if not success:
        logger.error("Failed to load model on startup")
    else:
        logger.info("OCR service ready")

@app.get("/", response_model=HealthResponse)
async def root():
    """Root endpoint with service info"""
    return {
        "status": "running",
        "device": device.type if device else "unknown",
        "cuda_available": torch.cuda.is_available(),
        "model_loaded": predictor is not None
    }

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy" if predictor is not None else "unhealthy",
        "device": device.type if device else "unknown",
        "cuda_available": torch.cuda.is_available(),
        "model_loaded": predictor is not None
    }

@app.post("/extract", response_model=OCRResponse)
async def extract_ocr(
    file: UploadFile = File(...),
    apply_enhancements: bool = False
):
    """
    Extract text from uploaded image
    
    Args:
        file: Uploaded image file
        apply_enhancements: Apply preprocessing (denoising, sharpening)
    
    Returns:
        OCR results with text, confidence, and timings
    """
    if predictor is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    # Validate file type
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    try:
        # Read file bytes
        image_bytes = await file.read()
        
        # Extract text
        result = extract_text_from_bytes(image_bytes, apply_enhancements)
        
        # Log GPU memory if available
        if torch.cuda.is_available():
            vram_used = torch.cuda.memory_allocated() / 1024**2
            logger.info(f"VRAM used: {vram_used:.2f} MB")
        
        return OCRResponse(
            text=result["text"],
            confidence=result["confidence"],
            timings=result["timings"],
            device=device.type,
            words_count=result["words_count"]
        )
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing image: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing image: {str(e)}")

@app.post("/extract_batch")
async def extract_batch(files: list[UploadFile] = File(...), apply_enhancements: bool = False):
    """
    Extract text from multiple images
    
    Args:
        files: List of uploaded image files
        apply_enhancements: Apply preprocessing to all images
    
    Returns:
        List of OCR results
    """
    if predictor is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    results = []
    
    for file in files:
        if not file.content_type.startswith("image/"):
            results.append({
                "filename": file.filename,
                "error": "Not an image file"
            })
            continue
        
        try:
            image_bytes = await file.read()
            result = extract_text_from_bytes(image_bytes, apply_enhancements)
            results.append({
                "filename": file.filename,
                "text": result["text"],
                "confidence": result["confidence"],
                "timings": result["timings"],
                "words_count": result["words_count"]
            })
        except Exception as e:
            logger.error(f"Error processing {file.filename}: {e}")
            results.append({
                "filename": file.filename,
                "error": str(e)
            })
    
    # Clean up GPU memory
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    
    return {"results": results, "device": device.type}

@app.get("/stats")
async def get_stats():
    """Get GPU/CPU statistics"""
    stats = {
        "device": device.type if device else "unknown",
        "cuda_available": torch.cuda.is_available()
    }
    
    if torch.cuda.is_available():
        stats.update({
            "gpu_name": torch.cuda.get_device_name(0),
            "cuda_version": torch.version.cuda,
            "vram_total_mb": torch.cuda.get_device_properties(0).total_memory / 1024**2,
            "vram_allocated_mb": torch.cuda.memory_allocated() / 1024**2,
            "vram_reserved_mb": torch.cuda.memory_reserved() / 1024**2
        })
    
    return stats

if __name__ == "__main__":
    import uvicorn
    
    # Get port from environment or use default
    port = int(os.getenv("OCR_SERVICE_PORT", "8004"))
    
    logger.info(f"Starting OCR service on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
