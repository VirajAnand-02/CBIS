import torch
import time
from PIL import Image
from transformers import (
    CLIPProcessor, CLIPModel,
    BlipProcessor, BlipForConditionalGeneration
)

# ---------- SETTINGS ----------
clip_model_name = "openai/clip-vit-base-patch32"
blip_model_name = "Salesforce/blip-image-captioning-base"
# Use absolute path or path relative to script location
import os
script_dir = os.path.dirname(os.path.abspath(__file__))
image_path = os.path.join(script_dir, "cal.png")

device = "cuda" if torch.cuda.is_available() else "cpu"

# ---------- LOAD MODELS ----------
# CLIP for embeddings
clip_model = CLIPModel.from_pretrained(clip_model_name).to(device)
clip_processor = CLIPProcessor.from_pretrained(clip_model_name)

# BLIP for captions
blip_model = BlipForConditionalGeneration.from_pretrained(blip_model_name).to(device)
blip_processor = BlipProcessor.from_pretrained(blip_model_name)

# ---------- LOAD IMAGE ----------
image = Image.open(image_path).convert("RGB")

# ---------- GET CLIP EMBEDDING ----------
clip_inputs = clip_processor(images=image, return_tensors="pt").to(device)
if device == "cuda":
    torch.cuda.synchronize()
t0 = time.perf_counter()
with torch.no_grad():
    image_features = clip_model.get_image_features(**clip_inputs)
if device == "cuda":
    torch.cuda.synchronize()
embed_time_s = time.perf_counter() - t0

# Normalize (optional)
image_features = image_features / image_features.norm(dim=-1, keepdim=True)

embedding_list = image_features[0].cpu().tolist()

# ---------- GET BLIP CAPTION ----------
blip_inputs = blip_processor(images=image, return_tensors="pt").to(device)
if device == "cuda":
    torch.cuda.synchronize()
t1 = time.perf_counter()
with torch.no_grad():
    output_ids = blip_model.generate(**blip_inputs, max_length=30)
if device == "cuda":
    torch.cuda.synchronize()
caption_time_s = time.perf_counter() - t1

caption = blip_processor.decode(output_ids[0], skip_special_tokens=True)

# ---------- RESULTS ----------
print("DEVICE: ", device)
print(f"CLIP Embedding Length: {len(embedding_list)}")
print("First 10 embedding values:", embedding_list[:10])
print("Caption:", caption)
print(f"Embedding compute time: {embed_time_s:.3f}s")
print(f"Caption generation time: {caption_time_s:.3f}s")
