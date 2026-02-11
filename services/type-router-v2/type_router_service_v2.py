# type_router_service_v2.py
# FastAPI service for Type Router V2 - classifies images using CLIP embeddings + Random Forest

import os
import numpy as np
import joblib
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ---------- CONFIG ----------
MODEL_PATH = os.environ.get("MODEL_PATH", "outputs/ovr_rf_clip_model.joblib")
DEFAULT_THRESHOLD = float(os.environ.get("THRESHOLD", "0.5"))

# TODO: Dummy mode - returns random classifications (useful for testing/development)
# Replace with actual model for production
USE_DUMMY = os.environ.get("USE_DUMMY_ROUTER", "false").lower() in ("true", "1", "yes")

# ---------- INIT FASTAPI ----------
app = FastAPI(title="CBIS Type Router V2 API", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- GLOBAL MODELS ----------
rf_model = None
label_cols = []

# ---------- LOAD MODELS ON STARTUP ----------
@app.on_event("startup")
async def load_models():
    global rf_model, label_cols
    
    if USE_DUMMY:
        print("=" * 60)
        print("⚠️  DUMMY MODE ENABLED - Using random classifications")
        print("   Set USE_DUMMY_ROUTER=false in .env file to use the actual model")
        print("=" * 60)
        # Set default labels for dummy mode
        label_cols = [
            "is_document", "is_handwritten", "has_scene_text", 
            "has_people_faces", "is_screenshot", "is_art_illustration",
            "has_machine_code", "is_natural_image", "is_nsfw", "is_low_quality"
        ]
        return

    print("=" * 60)
    print(f"Loading Type Router V2 model from {MODEL_PATH}...")
    
    # Load Random Forest model
    if not os.path.exists(MODEL_PATH):
        print(f"ERROR: Model file not found at {MODEL_PATH}")
        print("Please train the model first using train_clip_rf.py")
        print("=" * 60)
        exit(1)

    try:
        model_bundle = joblib.load(MODEL_PATH)
        if isinstance(model_bundle, dict) and "model" in model_bundle and "label_cols" in model_bundle:
            rf_model = model_bundle["model"]
            label_cols = model_bundle["label_cols"]
        else:
            # Fallback: assume joblib saved the estimator directly
            rf_model = model_bundle
            label_cols = [
                "is_document", "is_handwritten", "has_scene_text", 
                "has_people_faces", "is_screenshot", "is_art_illustration",
                "has_machine_code", "is_natural_image", "is_nsfw", "is_low_quality"
            ]
        print(f"✅ Random Forest model loaded successfully.")
        print(f"   Labels: {label_cols}")
    except Exception as e:
        print(f"ERROR: Failed to load Random Forest model: {e}")
        print("=" * 60)
        exit(1)
    
    print("=" * 60)

# ---------- HELPER FUNCTIONS ----------
def apply_threshold(probabilities: np.ndarray, threshold: float = DEFAULT_THRESHOLD) -> np.ndarray:
    """Convert probabilities to binary predictions using threshold."""
    return (probabilities >= threshold).astype(int)

# ---------- REQUEST/RESPONSE MODELS ----------
class EmbeddingRequest(BaseModel):
    embedding: List[float]
    threshold: float = DEFAULT_THRESHOLD

class TypeRouterResponse(BaseModel):
    # Dynamic fields based on label_cols
    predictions: Dict[str, bool]
    probabilities: Dict[str, float]

# ---------- ROUTES ----------
@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": "2.0",
        "model_type": "Random Forest",
        "model_path": MODEL_PATH,
        "labels": label_cols,
        "dummy_mode": USE_DUMMY
    }

@app.post("/classify", response_model=TypeRouterResponse)
def classify_from_embedding(request: EmbeddingRequest):
    """
    Accepts CLIP embedding (512-dim) and returns multi-label classification.
    This endpoint expects the embedding to already be computed by the client.
    """
    try:
        # DUMMY MODE: Return random classifications
        if USE_DUMMY:
            probabilities = {
                label: float(np.random.uniform(0.1, 0.9))
                for label in label_cols
            }
            # Force has_people_faces to always be true in dummy mode (for testing face detection)
            probabilities["has_people_faces"] = 0.95
            
            predictions = {
                label: bool(prob > request.threshold)
                for label, prob in probabilities.items()
            }
            return TypeRouterResponse(
                predictions=predictions,
                probabilities=probabilities
            )
        
        # REAL MODE: Use Random Forest model
        embedding = np.array(request.embedding).reshape(1, -1)
        
        # Validate embedding dimension
        expected_dim = 512  # CLIP ViT-B/32 embedding dimension
        if embedding.shape[1] != expected_dim:
            raise HTTPException(
                status_code=400,
                detail=f"Expected embedding dimension {expected_dim}, got {embedding.shape[1]}"
            )
        
        # Get probabilities from Random Forest
        try:
            probas = rf_model.predict_proba(embedding)[0]
        except Exception:
            # Fallback: stack per-estimator predict_proba
            probas = np.array([est.predict_proba(embedding)[0, 1] for est in rf_model.estimators_])
        
        # Apply threshold
        preds = apply_threshold(probas, request.threshold)
        
        # Build response
        probabilities = {
            label: float(prob)
            for label, prob in zip(label_cols, probas)
        }
        predictions = {
            label: bool(pred)
            for label, pred in zip(label_cols, preds)
        }
        
        return TypeRouterResponse(
            predictions=predictions,
            probabilities=probabilities
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Classification failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    print("\n🚀 Starting Type Router V2 service on http://0.0.0.0:8001")
    if USE_DUMMY:
        print("🎲 DUMMY MODE: Returning random classifications")
        print("   To disable, set USE_DUMMY_ROUTER=false in .env file")
    else:
        print(f"🤖 Using Random Forest model")
        print(f"📊 Model: {MODEL_PATH}")
        print(f"🏷️  Labels: {len(label_cols) if label_cols else 'loading...'}")
    print("\n📡 Available endpoints:")
    print("   POST /classify - Classify from CLIP embedding (512-dim)")
    print("   GET  /health - Service health check")
    print()
    uvicorn.run(app, host="0.0.0.0", port=8001)
