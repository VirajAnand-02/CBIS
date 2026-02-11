# app.py
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, HttpUrl, ValidationError
import httpx
from io import BytesIO
from PIL import Image
import numpy as np
import tensorflow as tf
import time
import asyncio
from typing import Optional, Dict, Any
import logging
import traceback
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("NIMA")

# Configure TensorFlow GPU settings
def configure_gpu():
    """Configure TensorFlow to use GPU if available."""
    gpus = tf.config.list_physical_devices('GPU')
    
    if gpus:
        try:
            # Enable memory growth to avoid allocating all GPU memory at once
            for gpu in gpus:
                tf.config.experimental.set_memory_growth(gpu, True)
            
            logger.info(f"✅ GPU detected: {len(gpus)} device(s)")
            for i, gpu in enumerate(gpus):
                logger.info(f"   GPU {i}: {gpu.name}")
            
            # Log GPU details
            gpu_details = tf.config.experimental.get_device_details(gpus[0])
            if gpu_details:
                logger.info(f"   Compute Capability: {gpu_details.get('compute_capability', 'unknown')}")
            
            return "GPU"
        except RuntimeError as e:
            logger.error(f"GPU configuration error: {e}")
            return "CPU"
    else:
        logger.info("⚠️  No GPU detected, using CPU")
        return "CPU"

# Configure GPU on startup
device_type = configure_gpu()

app = FastAPI(title="NIMA Scoring API")

# ---------- Middleware for request logging ----------
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Incoming {request.method} {request.url.path}")
    try:
        # Try to read body for logging (only for non-GET)
        if request.method in ["POST", "PUT", "PATCH"]:
            body = await request.body()
            logger.debug(f"Request body: {body.decode('utf-8', errors='ignore')[:500]}")
            # Reset body for actual handler
            async def receive():
                return {"type": "http.request", "body": body}
            request._receive = receive
        
        response = await call_next(request)
        logger.info(f"Response status: {response.status_code}")
        return response
    except Exception as e:
        logger.error(f"Request processing error: {str(e)}")
        logger.error(traceback.format_exc())
        raise

# ---------- Exception handlers ----------
@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    logger.error(f"Validation error on request to {request.url.path}")
    logger.error(f"Request body: {await request.body()}")
    logger.error(f"Validation errors: {exc.errors()}")
    return HTTPException(
        status_code=400,
        detail={
            "message": "Invalid request data",
            "errors": exc.errors(),
            "body": str(await request.body())
        }
    )

# ---------- Request/Response models ----------
class ScoreRequest(BaseModel):
    url: str  # Changed from HttpUrl to str for more flexibility
    model: Optional[str] = "mobilenet_v2"
    
    class Config:
        # Allow extra fields
        extra = "allow"

class ScoreResponse(BaseModel):
    score: float
    distributions: Optional[list]
    model: Optional[str]
    times: Optional[dict]
    # additional fields allowed (pydantic by default will allow extra if not strict)

# ---------- Utilities from your original script ----------
def build_nima_mobilenet(input_shape=(224, 224, 3)):
    base = tf.keras.applications.MobileNet(
        input_shape=input_shape, include_top=False, weights=None
    )
    x = base.output
    x = tf.keras.layers.GlobalAveragePooling2D()(x)
    x = tf.keras.layers.Dense(1024, activation="relu")(x)
    x = tf.keras.layers.Dropout(0.5)(x)
    outputs = tf.keras.layers.Dense(10, activation="softmax", name="nima_scores")(x)
    model = tf.keras.Model(inputs=base.input, outputs=outputs)
    return model

def build_nima_mobilenet_v2(input_shape=(224, 224, 3)):
    base = tf.keras.applications.MobileNetV2(
        input_shape=input_shape, include_top=False, weights=None
    )
    x = base.output
    x = tf.keras.layers.GlobalAveragePooling2D()(x)
    x = tf.keras.layers.Dense(1024, activation="relu")(x)
    x = tf.keras.layers.Dropout(0.5)(x)
    outputs = tf.keras.layers.Dense(10, activation="softmax", name="nima_scores")(x)
    model = tf.keras.Model(inputs=base.input, outputs=outputs)
    return model

def distribution_to_stats(dist: np.ndarray):
    bins = np.arange(1, 11).astype(np.float32)  # 1..10
    mean = float(np.sum(bins * dist))
    mean_sq = float(np.sum((bins ** 2) * dist))
    std = float(np.sqrt(max(0.0, mean_sq - mean ** 2)))
    return mean, std

def preprocess_pil_image(img: Image.Image, target_size=(224, 224)):
    img = img.convert("RGB")
    img = img.resize(target_size, Image.BILINEAR)
    arr = np.asarray(img).astype("float32")
    arr = tf.keras.applications.mobilenet.preprocess_input(arr)  # works for MobileNet / MobileNetV2
    arr = np.expand_dims(arr, axis=0)
    return arr

# ---------- Model cache ----------
MODEL_BUILDERS = {
    "mobilenet": build_nima_mobilenet,
    "mobilenet_v2": build_nima_mobilenet_v2,
}

# Map model IDs to their weight files
MODEL_WEIGHTS = {
    "mobilenet": "mobilenet_nima.h5",
    "mobilenet_v2": "mobilenet_nima.h5",  # Using same weights for both (mobilenet architecture)
}

_model_cache: Dict[str, tf.keras.Model] = {}
_model_input_size = 224  # default

# Load a model (lazy)
def get_or_create_model(model_id: str):
    import os
    model_id = model_id.lower()
    if model_id not in MODEL_BUILDERS:
        raise ValueError(f"Unknown model '{model_id}'. Supported: {list(MODEL_BUILDERS.keys())}")
    if model_id not in _model_cache:
        # Build and cache
        logger.info(f"Building model: {model_id}")
        builder = MODEL_BUILDERS[model_id]
        
        # Build model with GPU support if available
        with tf.device('/GPU:0' if device_type == "GPU" else '/CPU:0'):
            model = builder(input_shape=(_model_input_size, _model_input_size, 3))
        
        # Load trained weights if available
        weights_file = MODEL_WEIGHTS.get(model_id)
        if weights_file and os.path.exists(weights_file):
            logger.info(f"Loading weights from {weights_file} for model {model_id}")
            try:
                model.load_weights(weights_file, by_name=True, skip_mismatch=True)
                logger.info(f"✅ Successfully loaded weights for {model_id}")
            except Exception as e:
                logger.warning(f"Failed to load weights: {e}")
                logger.warning(f"Model will use random initialization (scores will not be meaningful)")
        else:
            logger.warning(f"No weights file found at {weights_file}")
            logger.warning(f"Model will use random initialization (scores will not be meaningful)")
        
        logger.info(f"Model {model_id} loaded on {device_type}")
        _model_cache[model_id] = model
    return _model_cache[model_id]

# ---------- Download image ----------
async def fetch_image_bytes(url: str, timeout: float = 10.0, max_bytes: int = 10_000_000) -> bytes:
    try:
        logger.debug(f"Creating HTTP client for URL: {url}")
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            logger.debug(f"Sending GET request...")
            r = await client.get(url)
            r.raise_for_status()
            content = r.content
            logger.debug(f"Response received: {len(content)} bytes, content-type: {r.headers.get('content-type')}")
            
            if len(content) > max_bytes:
                logger.error(f"Image too large: {len(content)} bytes (max: {max_bytes})")
                raise HTTPException(status_code=413, detail=f"Image too large: {len(content)} bytes")
            
            return content
    except httpx.TimeoutException as e:
        logger.error(f"Timeout fetching image from {url}: {str(e)}")
        raise
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error {e.response.status_code} fetching {url}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error fetching image: {str(e)}")
        logger.error(traceback.format_exc())
        raise

# ---------- Run synchronous TF predict in threadpool ----------
def predict_sync(model: tf.keras.Model, input_arr: np.ndarray):
    # model.predict is synchronous and can be heavy; run in threadpool
    probs = model.predict(input_arr, verbose=0)[0]
    return probs

# ---------- Endpoint ----------
@app.post("/score", response_model=ScoreResponse)
async def score(req: ScoreRequest, request: Request):
    start_total = time.time()
    
    # Log incoming request
    logger.info(f"=== NIMA Score Request ===")
    logger.info(f"Client: {request.client.host if request.client else 'unknown'}")
    logger.info(f"URL: {req.url}")
    logger.info(f"Model: {req.model}")
    
    # Validate URL format
    if not req.url or not isinstance(req.url, str):
        logger.error(f"Invalid URL type: {type(req.url)}")
        raise HTTPException(status_code=400, detail="URL must be a non-empty string")
    
    url_str = str(req.url).strip()
    if not url_str.startswith(('http://', 'https://')):
        logger.error(f"Invalid URL scheme: {url_str}")
        raise HTTPException(
            status_code=400, 
            detail=f"URL must start with http:// or https://, got: {url_str[:100]}"
        )
    
    logger.info(f"Validated URL: {url_str}")
    
    # Validate and get model
    model_id = req.model or "mobilenet_v2"
    try:
        logger.info(f"Loading model: {model_id}")
        model = get_or_create_model(model_id)
    except ValueError as e:
        logger.error(f"Invalid model requested: {model_id} - {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

    # Fetch image
    try:
        logger.info(f"Fetching image from URL: {url_str}")
        img_bytes = await fetch_image_bytes(url_str)
        logger.info(f"Successfully fetched image: {len(img_bytes)} bytes")
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error fetching image: {e.response.status_code} - {str(e)}")
        raise HTTPException(
            status_code=400, 
            detail=f"Failed to fetch image (HTTP {e.response.status_code}): {str(e)}"
        )
    except httpx.RequestError as e:
        logger.error(f"Request error fetching image: {str(e)}")
        raise HTTPException(
            status_code=400, 
            detail=f"Failed to fetch image (network error): {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error fetching image: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500, 
            detail=f"Error fetching image: {str(e)}"
        )

    # Open and preprocess
    try:
        logger.info("Opening and preprocessing image")
        img = Image.open(BytesIO(img_bytes))
        logger.info(f"Image opened: size={img.size}, mode={img.mode}, format={img.format}")
        arr = preprocess_pil_image(img, target_size=(_model_input_size, _model_input_size))
        logger.info(f"Preprocessed array shape: {arr.shape}")
    except Exception as e:
        logger.error(f"Error processing image: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=400, 
            detail=f"Could not open/process image: {str(e)}"
        )

    # Run inference in executor
    inf_start = time.time()
    loop = asyncio.get_event_loop()
    try:
        logger.info("Running inference...")
        probs = await loop.run_in_executor(None, predict_sync, model, arr)
        logger.info(f"Inference complete: {probs.shape}")
    except Exception as e:
        logger.error(f"Inference error: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500, 
            detail=f"Inference error: {str(e)}"
        )
    inf_end = time.time()

    # Normalize (safety) and stats
    probs = np.asarray(probs, dtype=np.float32)
    if probs.sum() <= 0:
        # fallback uniform
        logger.warning("Probability sum <= 0, using uniform distribution")
        probs = np.ones_like(probs) / probs.size
    else:
        probs = probs / float(probs.sum())

    mean, std = distribution_to_stats(probs)

    total_end = time.time()
    inference_s = inf_end - inf_start
    total_s = total_end - start_total

    # Format response
    response = {
        "score": round(mean, 4),               # mean in [1..10]
        "distributions": [float(round(float(x), 6)) for x in probs.tolist()],  # probabilities for bins 1..10
        "model": model_id,
        "times": {"inference_s": float(round(inference_s, 6)), "total_s": float(round(total_s, 6))},
    }
    
    logger.info(f"Score: {response['score']}, Total time: {total_s:.3f}s")
    logger.info("=== Request Complete ===\n")
    
    return response

# ---------- Basic root ----------
@app.get("/")
async def root():
    return {
        "info": "NIMA scoring API. POST /score with JSON {url:, model: (optional)}",
        "device": device_type,
        "gpu_available": len(tf.config.list_physical_devices('GPU')) > 0,
    }

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "device": device_type,
        "models": list(MODEL_BUILDERS.keys()),
        "gpu_available": len(tf.config.list_physical_devices('GPU')) > 0,
    }
