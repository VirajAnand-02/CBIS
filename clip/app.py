# app.py
import os
import time
import io
import requests
import torch
from PIL import Image
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from transformers import (
    CLIPProcessor, CLIPModel,
    BlipProcessor, BlipForConditionalGeneration
)

# ---------- CONFIG ----------
CLIP_MODEL_NAME = "openai/clip-vit-base-patch32"
BLIP_MODEL_NAME = "Salesforce/blip-image-captioning-base"

# choose device
device = "cuda" if torch.cuda.is_available() else "cpu"

# ---------- INIT FASTAPI ----------
app = FastAPI(title="Image -> (embedding, caption) API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tune for production
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- LOAD MODELS ON STARTUP ----------
print("=" * 60)
print("Loading models... (this may take a while)")
print(f"Device: {device}")
if device == "cuda":
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")
print("=" * 60)

clip_model = CLIPModel.from_pretrained(CLIP_MODEL_NAME).to(device)
clip_processor = CLIPProcessor.from_pretrained(CLIP_MODEL_NAME)

blip_model = BlipForConditionalGeneration.from_pretrained(BLIP_MODEL_NAME).to(device)
blip_processor = BlipProcessor.from_pretrained(BLIP_MODEL_NAME)

print("✅ Models loaded successfully!")
print(f"   - CLIP Model: {CLIP_MODEL_NAME}")
print(f"   - BLIP Model: {BLIP_MODEL_NAME}")
print(f"   - Running on: {device.upper()}")
if device == "cuda":
    print(f"   - GPU Memory Allocated: {torch.cuda.memory_allocated(0) / 1024**3:.2f} GB")
print("=" * 60)


# ---------- HELPERS ----------
def load_image_from_bytes(b: bytes) -> Image.Image:
    try:
        img = Image.open(io.BytesIO(b)).convert("RGB")
        return img
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image: {e}")


def process_pil_image(img: Image.Image):
    """
    Runs CLIP embedding and BLIP caption on the given PIL image.
    Returns dict with embedding (list), caption (str), device (str), times.
    """
    # CLIP embedding
    clip_inputs = clip_processor(images=img, return_tensors="pt").to(device)
    if device == "cuda":
        torch.cuda.synchronize()
    t0 = time.perf_counter()
    with torch.no_grad():
        image_features = clip_model.get_image_features(**clip_inputs)
    if device == "cuda":
        torch.cuda.synchronize()
    embed_time_s = time.perf_counter() - t0

    # normalize
    image_features = image_features / image_features.norm(dim=-1, keepdim=True)
    embedding = image_features[0].cpu().tolist()

    # BLIP caption
    blip_inputs = blip_processor(images=img, return_tensors="pt").to(device)
    if device == "cuda":
        torch.cuda.synchronize()
    t1 = time.perf_counter()
    with torch.no_grad():
        output_ids = blip_model.generate(**blip_inputs, max_length=30)
    if device == "cuda":
        torch.cuda.synchronize()
    caption_time_s = time.perf_counter() - t1

    caption = blip_processor.decode(output_ids[0], skip_special_tokens=True)

    return {
        "embedding": embedding,
        "caption": caption,
        "device": device,
        "times": {
            "embedding_s": embed_time_s,
            "caption_s": caption_time_s
        }
    }


# ---------- ROUTES ----------
class URLBody(BaseModel):
    url: str

@app.post("/process/upload")
async def process_upload(file: UploadFile = File(...)):
    """
    Accepts multipart/form-data file upload.
    """
    content = await file.read()
    img = load_image_from_bytes(content)
    result = process_pil_image(img)
    # include some metadata about original filename
    result["filename"] = file.filename
    return result


@app.post("/process/url")
def process_url(body: URLBody):
    """
    Accepts JSON { "url": "https://.../image.png" }.
    Downloads the image and processes it.
    """
    try:
        resp = requests.get(body.url, timeout=15)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not fetch URL: {e}")

    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="Failed to fetch image")

    content_type = resp.headers.get("content-type", "")
    if not content_type.startswith("image/"):
        # still allow (some blob servers don't set content-type), but warn
        # We'll attempt to parse anyway
        pass

    img = load_image_from_bytes(resp.content)
    result = process_pil_image(img)
    result["source_url"] = body.url
    return result


@app.get("/health")
def health():
    return {"status": "ok", "device": device}


# ---------- TEXT ENCODING FOR SEARCH ----------
class TextEncodeBody(BaseModel):
    text: str
    normalize: bool = True

@app.post("/encode/text")
def encode_text(body: TextEncodeBody):
    """
    Encodes text query into CLIP embedding vector for similarity search.
    
    Request JSON:
    {
        "text": "a cat sitting on a couch",
        "normalize": true
    }
    
    Response JSON:
    {
        "embedding": [...],
        "text": "a cat sitting on a couch",
        "device": "cuda",
        "times": { "encoding_s": 0.012 }
    }
    """
    try:
        # Process text through CLIP
        clip_inputs = clip_processor(text=body.text, return_tensors="pt", padding=True).to(device)
        
        if device == "cuda":
            torch.cuda.synchronize()
        t0 = time.perf_counter()
        
        with torch.no_grad():
            text_features = clip_model.get_text_features(**clip_inputs)
        
        if device == "cuda":
            torch.cuda.synchronize()
        encode_time_s = time.perf_counter() - t0
        
        # Normalize if requested (recommended for similarity search)
        if body.normalize:
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)
        
        embedding = text_features[0].cpu().tolist()
        
        return {
            "embedding": embedding,
            "text": body.text,
            "device": device,
            "times": {
                "encoding_s": encode_time_s
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Text encoding failed: {e}")
