# app.py
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, HttpUrl
import httpx
from io import BytesIO
from PIL import Image
import numpy as np
import tensorflow as tf
import time
import asyncio
from typing import Optional, Dict, Any

app = FastAPI(title="NIMA Scoring API")

# ---------- Request/Response models ----------
class ScoreRequest(BaseModel):
    url: HttpUrl
    model: Optional[str] = "mobilenet_v2"

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
        builder = MODEL_BUILDERS[model_id]
        model = builder(input_shape=(_model_input_size, _model_input_size, 3))
        
        # Load trained weights if available
        weights_file = MODEL_WEIGHTS.get(model_id)
        if weights_file and os.path.exists(weights_file):
            print(f"[NIMA] Loading weights from {weights_file} for model {model_id}")
            try:
                model.load_weights(weights_file, by_name=True, skip_mismatch=True)
                print(f"[NIMA] Successfully loaded weights for {model_id}")
            except Exception as e:
                print(f"[NIMA] Warning: Failed to load weights: {e}")
                print(f"[NIMA] Model will use random initialization (scores will not be meaningful)")
        else:
            print(f"[NIMA] Warning: No weights file found at {weights_file}")
            print(f"[NIMA] Model will use random initialization (scores will not be meaningful)")
        
        _model_cache[model_id] = model
    return _model_cache[model_id]

# ---------- Download image ----------
async def fetch_image_bytes(url: str, timeout: float = 10.0, max_bytes: int = 10_000_000) -> bytes:
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        r = await client.get(url)
        r.raise_for_status()
        content = r.content
        if len(content) > max_bytes:
            raise HTTPException(status_code=413, detail="Image too large")
        return content

# ---------- Run synchronous TF predict in threadpool ----------
def predict_sync(model: tf.keras.Model, input_arr: np.ndarray):
    # model.predict is synchronous and can be heavy; run in threadpool
    probs = model.predict(input_arr, verbose=0)[0]
    return probs

# ---------- Endpoint ----------
@app.post("/score", response_model=ScoreResponse)
async def score(req: ScoreRequest, request: Request):
    start_total = time.time()
    # Validate and get model
    model_id = req.model or "mobilenet_v2"
    try:
        model = get_or_create_model(model_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Fetch image
    try:
        img_bytes = await fetch_image_bytes(str(req.url))
    except httpx.HTTPError as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch image: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching image: {str(e)}")

    # Open and preprocess
    try:
        img = Image.open(BytesIO(img_bytes))
        arr = preprocess_pil_image(img, target_size=(_model_input_size, _model_input_size))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not open/process image: {str(e)}")

    # Run inference in executor
    inf_start = time.time()
    loop = asyncio.get_event_loop()
    try:
        probs = await loop.run_in_executor(None, predict_sync, model, arr)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference error: {str(e)}")
    inf_end = time.time()

    # Normalize (safety) and stats
    probs = np.asarray(probs, dtype=np.float32)
    if probs.sum() <= 0:
        # fallback uniform
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
    return response

# ---------- Basic root ----------
@app.get("/")
async def root():
    return {"info": "NIMA scoring API. POST /score with JSON {url:, model: (optional)}"}
