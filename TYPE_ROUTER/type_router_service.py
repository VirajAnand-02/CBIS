# type_router_service.py
# FastAPI service for Type Router - classifies images based on CLIP embeddings

import os
import numpy as np
import tensorflow as tf
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ---------- CONFIG ----------
MODEL_PATH = "image_attribute_router.keras"
IMG_SIZE = (224, 224)

# Define attributes (must match training order)
ATTRIBUTES = ["is_document", "has_people", "is_screenshot", "is_animal"]

# Classification thresholds
THRESHOLD = 0.5  # Adjust based on your model performance

# Dummy mode - returns random classifications (useful for testing/development)
USE_DUMMY = os.environ.get("USE_DUMMY_ROUTER", "false").lower() in ("true", "1", "yes")

# ---------- INIT FASTAPI ----------
app = FastAPI(title="CBIS Type Router API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- LOAD MODEL ON STARTUP ----------
model = None

if USE_DUMMY:
    print("=" * 60)
    print("⚠️  DUMMY MODE ENABLED - Using random classifications")
    print("   Set USE_DUMMY_ROUTER=false in .env file to use the actual model")
    print("=" * 60)
else:
    print("=" * 60)
    print(f"Loading Type Router model from {MODEL_PATH}...")
    if not os.path.exists(MODEL_PATH):
        print(f"ERROR: Model file not found at {MODEL_PATH}")
        print("Please ensure the model file is in the same directory as this script.")
        print("=" * 60)
        exit(1)

    try:
        model = tf.keras.models.load_model(MODEL_PATH)
        print("✅ Type Router model loaded successfully.")
        print(f"   Model expects input shape: {model.input_shape}")
        print(f"   Output attributes: {ATTRIBUTES}")
        print("=" * 60)
    except Exception as e:
        print(f"ERROR: Failed to load model: {e}")
        print("=" * 60)
        exit(1)

# ---------- REQUEST/RESPONSE MODELS ----------
class EmbeddingRequest(BaseModel):
    embedding: List[float]

class TypeRouterResponse(BaseModel):
    is_document: bool
    has_people: bool
    is_screenshot: bool
    is_animal: bool
    probabilities: dict

# ---------- ROUTES ----------
@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL_PATH, "attributes": ATTRIBUTES}


@app.post("/classify", response_model=TypeRouterResponse)
def classify_from_embedding(request: EmbeddingRequest):
    """
    Accepts CLIP embedding and returns image type classification.
    
    NOTE: This is a placeholder implementation that needs to be updated
    to properly convert CLIP embeddings to the format your model expects.
    """
    try:
        # TODO: Currently this won't work correctly because:
        # 1. Your model expects image pixels (224x224x3), not CLIP embeddings (512-dim)
        # 2. You need to either:
        #    a) Retrain the Type Router to accept CLIP embeddings as input
        #    b) Use a different approach (e.g., similarity matching, linear probe)
        #    c) Pass the actual image and process it here
        
        # For now, return random predictions based on embedding statistics
        embedding = np.array(request.embedding)
        
        # Placeholder logic - replace with actual model inference
        # This is just to make the pipeline work for now
        predictions = {
            "is_document": bool(np.mean(embedding[:128]) > 0),
            "has_people": bool(np.mean(embedding[128:256]) > 0),
            "is_screenshot": bool(np.mean(embedding[256:384]) > 0),
            "is_animal": bool(np.mean(embedding[384:]) > 0),
        }
        
        probabilities = {
            "is_document": float(np.abs(np.mean(embedding[:128]))),
            "has_people": float(np.abs(np.mean(embedding[128:256]))),
            "is_screenshot": float(np.abs(np.mean(embedding[256:384]))),
            "is_animal": float(np.abs(np.mean(embedding[384:]))),
        }
        
        return TypeRouterResponse(
            **predictions,
            probabilities=probabilities
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Classification failed: {str(e)}")


@app.post("/classify_from_image")
async def classify_from_image_url(body: dict):
    """
    Alternative endpoint that accepts image URL and processes it directly.
    This uses the actual trained model (or dummy mode if USE_DUMMY=true).
    """
    import requests
    from PIL import Image
    import io
    
    try:
        url = body.get("url")
        if not url:
            raise HTTPException(status_code=400, detail="Missing 'url' field")
        
        # DUMMY MODE: Return random classifications
        if USE_DUMMY:
            probabilities = {
                attr: float(np.random.uniform(0.1, 0.9))
                for attr in ATTRIBUTES
            }
            predictions = {
                attr: bool(prob > THRESHOLD)
                for attr, prob in probabilities.items()
            }
            return TypeRouterResponse(
                **predictions,
                probabilities=probabilities
            )
        
        # REAL MODE: Use actual model
        # Download image
        response = requests.get(url, timeout=15)
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch image")
        
        # Load and preprocess image
        img = Image.open(io.BytesIO(response.content)).convert("RGB")
        img = img.resize(IMG_SIZE)
        img_array = tf.keras.utils.img_to_array(img)
        img_array /= 255.0
        img_batch = np.expand_dims(img_array, axis=0)
        
        # Get predictions
        prediction_vector = model.predict(img_batch, verbose=0)[0]
        
        # Convert to boolean classifications
        predictions = {
            attr: bool(prob > THRESHOLD)
            for attr, prob in zip(ATTRIBUTES, prediction_vector)
        }
        
        probabilities = {
            attr: float(prob)
            for attr, prob in zip(ATTRIBUTES, prediction_vector)
        }
        
        return TypeRouterResponse(
            **predictions,
            probabilities=probabilities
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Classification failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    print("\n🚀 Starting Type Router service on http://0.0.0.0:8001")
    if USE_DUMMY:
        print("🎲 DUMMY MODE: Returning random classifications")
        print("   To disable, set USE_DUMMY_ROUTER=false or remove the env variable")
    else:
        print("📝 Use /classify_from_image endpoint with image URLs")
        print("⚠️  /classify endpoint needs model retraining to accept CLIP embeddings")
    print()
    uvicorn.run(app, host="0.0.0.0", port=8001)

