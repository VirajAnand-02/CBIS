#!/usr/bin/env python3
"""
gemini_multi_label_resizing_v2.py

Multi-label image classification using Google Gemini generateContent REST API.

Outputs CSV with columns:
filename,is_document,is_handwritten,has_scene_text,has_people_faces,is_screenshot,is_art_illustration,has_machine_code,is_natural_image,is_nsfw,is_low_quality,error

Usage:
    python gemini_multi_label_resizing_v2.py /path/to/images_folder [output.csv]

Requirements:
    pip install aiohttp Pillow

Configuration:
    - Set GEMINI_API_KEYS environment variable (comma-separated) OR populate API_KEYS list below.
    - Set MODEL to a Gemini multimodal model available to your project (e.g. "models/gemini-1.5-mini" or your account's multimodal model).
    - Adjust RATE_LIMIT, RATE_PERIOD, GLOBAL_CONCURRENCY, MAX_INLINE_BYTES as needed.
"""

import asyncio
import aiohttp
import base64
import csv
import json
import os
import sys
import time
import itertools
from collections import deque
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image
import mimetypes
from io import BytesIO
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# -----------------------------
# CONFIG: Put your API keys here or use env var
# -----------------------------
API_KEYS: List[str] = []  # or leave empty to read GEMINI_API_KEYS env var

if not API_KEYS:
    env_keys = os.getenv("GEMINI_API_KEYS")
    if env_keys:
        API_KEYS = [k.strip() for k in env_keys.split(",") if k.strip()]

if not API_KEYS:
    raise SystemExit("No Gemini API keys found. Set GEMINI_API_KEYS environment variable or fill API_KEYS list.")

# Gemini model to use (ensure it's multimodal / supports image input for your project)
MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")  # or "models/gemini-1.5-mini" etc.

# Rate limiting / concurrency
RATE_LIMIT = int(os.getenv("GEMINI_RATE_LIMIT", "10"))  # requests per period per key
RATE_PERIOD = float(os.getenv("GEMINI_RATE_PERIOD", "60.0"))  # seconds
GLOBAL_CONCURRENCY = int(os.getenv("GEMINI_GLOBAL_CONCURRENCY", "12"))

# Max inline upload bytes (safety margin for inline base64 uploads)
MAX_INLINE_BYTES = int(os.getenv("GEMINI_MAX_INLINE_BYTES", str(18 * 1024 * 1024)))  # 18MB

# Gemini endpoint template
ENDPOINT_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# -----------------------------
# Helper classes & functions
# -----------------------------
class RateLimiter:
    """Sliding-window rate limiter for N requests per window seconds."""
    def __init__(self, limit: int, window_s: float):
        self.limit = limit
        self.window = window_s
        self.timestamps = deque()
        self.timeout_until = None  # Track 429 timeout

    async def acquire(self):
        while True:
            now = time.monotonic()
            
            # Check if we're in a 429 timeout period
            if self.timeout_until is not None:
                if now < self.timeout_until:
                    wait = self.timeout_until - now
                    await asyncio.sleep(wait + 0.1)
                    continue
                else:
                    # Timeout expired, clear it
                    self.timeout_until = None
            
            # drop old entries
            while self.timestamps and (now - self.timestamps[0]) > self.window:
                self.timestamps.popleft()
            if len(self.timestamps) < self.limit:
                self.timestamps.append(now)
                return
            earliest = self.timestamps[0]
            wait = (earliest + self.window) - now
            if wait <= 0:
                continue
            await asyncio.sleep(wait + 0.01)
    
    def set_timeout(self, duration_s: float):
        """Set a timeout for this rate limiter (e.g., after 429 error)."""
        self.timeout_until = time.monotonic() + duration_s


def detect_mime_type_from_path(path: str) -> str:
    mt, _ = mimetypes.guess_type(path)
    if mt and mt.startswith("image/"):
        return mt
    try:
        with Image.open(path) as im:
            fmt = (im.format or "JPEG").upper()
            return {
                "JPEG": "image/jpeg",
                "PNG": "image/png",
                "WEBP": "image/webp",
                "HEIC": "image/heic",
                "HEIF": "image/heif",
            }.get(fmt, "image/jpeg")
    except Exception:
        return "image/jpeg"


def make_prompt() -> str:
    return (
        "Classify the supplied image and output a single JSON object ONLY (no extra text or markdown). "
        "Analyze the image and determine which categories it belongs to (can be multiple) and relevant tags.\n\n"
        "### Fundamental Types (select ALL that apply):\n"
        "- is_document: Printed documents, PDFs, forms, invoices, receipts\n"
        "- is_handwritten: Handwritten notes, sketches, scans of handwritten content\n"
        "- has_scene_text: Text in natural scenes (signs, billboards, storefronts, text-in-the-wild)\n"
        "- has_people_faces: Images containing people or visible faces\n"
        "- is_screenshot: Screenshots from phones, computers, apps, websites\n"
        "- is_art_illustration: Artwork, drawings, illustrations, paintings, digital art\n"
        "- has_machine_code: Barcodes, QR codes, machine-readable codes\n"
        "- is_natural_image: Natural photographs, landscapes, objects\n\n"
        "### Tags:\n"
        "- is_nsfw: Contains NSFW/adult content (true/false)\n"
        "- is_low_quality: Blurry, dark, noisy, heavily compressed, or poor quality (true/false)\n\n"
        "Output JSON format (all fields required, use true/false for each):\n"
        "{\n"
        "  \"is_document\": true or false,\n"
        "  \"is_handwritten\": true or false,\n"
        "  \"has_scene_text\": true or false,\n"
        "  \"has_people_faces\": true or false,\n"
        "  \"is_screenshot\": true or false,\n"
        "  \"is_art_illustration\": true or false,\n"
        "  \"has_machine_code\": true or false,\n"
        "  \"is_natural_image\": true or false,\n"
        "  \"is_nsfw\": true or false,\n"
        "  \"is_low_quality\": true or false\n"
        "}\n\n"
        "Example: {\"is_document\": false, \"is_handwritten\": false, \"has_scene_text\": true, \"has_people_faces\": true, \"is_screenshot\": false, \"is_art_illustration\": false, \"has_machine_code\": false, \"is_natural_image\": true, \"is_nsfw\": false, \"is_low_quality\": false}"
    )


def extract_json_from_text(text: str) -> Tuple[Optional[Dict[str, Any]], str]:
    if not text:
        return None, text
    text = text.strip()
    try:
        obj = json.loads(text)
        return obj, text
    except Exception:
        pass
    # fallback: find first {...} block
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start:end+1]
        try:
            obj = json.loads(candidate)
            return obj, text
        except Exception:
            try:
                obj = json.loads(candidate.replace("'", '"'))
                return obj, text
            except Exception:
                pass
    return None, text


def prepare_image_bytes(path: str, max_bytes: int = MAX_INLINE_BYTES) -> Tuple[bytes, str]:
    """
    Prepare image bytes to be under max_bytes. Return (bytes, mime_type).
    Strategy: scale down dimensions and reduce JPEG quality, convert to JPEG if required.
    """
    orig_size = os.path.getsize(path)
    mime = detect_mime_type_from_path(path)
    with open(path, "rb") as f:
        raw = f.read()
    if len(raw) <= max_bytes:
        return raw, mime

    im = Image.open(path)
    im_format = (im.format or "JPEG").upper()

    scales = [0.95, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.15, 0.1]
    qualities = [95, 85, 75, 65, 50, 40]

    def save_img(img: Image.Image, fmt: str, quality: Optional[int] = None) -> bytes:
        bio = BytesIO()
        save_kwargs = {}
        if fmt in ("JPEG", "JPG"):
            save_kwargs["format"] = "JPEG"
            if quality is not None:
                save_kwargs["quality"] = quality
            save_kwargs["optimize"] = True
        elif fmt == "PNG":
            save_kwargs["format"] = "PNG"
            save_kwargs["optimize"] = True
        elif fmt == "WEBP":
            save_kwargs["format"] = "WEBP"
            if quality is not None:
                save_kwargs["quality"] = quality
        else:
            img = img.convert("RGB")
            save_kwargs["format"] = "JPEG"
            if quality is not None:
                save_kwargs["quality"] = quality
            save_kwargs["optimize"] = True
        img.save(bio, **save_kwargs)
        return bio.getvalue()

    # Try reducing size while preserving format where possible
    for scale in scales:
        w = max(1, int(im.width * scale))
        h = max(1, int(im.height * scale))
        resized = im.resize((w, h), Image.Resampling.LANCZOS)
        if im_format in ("JPEG", "JPG"):
            for q in qualities:
                data = save_img(resized, "JPEG", quality=q)
                if len(data) <= max_bytes:
                    return data, "image/jpeg"
        else:
            try:
                data = save_img(resized, im_format)
                if len(data) <= max_bytes:
                    fmt_to_mime = {"PNG": "image/png", "WEBP": "image/webp"}
                    return data, fmt_to_mime.get(im_format, "image/jpeg")
            except Exception:
                pass
            for q in qualities:
                data = save_img(resized.convert("RGB"), "JPEG", quality=q)
                if len(data) <= max_bytes:
                    return data, "image/jpeg"

    # Aggressive fallback
    tiny_scales = [0.08, 0.06, 0.04, 0.02]
    for scale in tiny_scales:
        w = max(1, int(im.width * scale))
        h = max(1, int(im.height * scale))
        resized = im.resize((w, h), Image.Resampling.LANCZOS)
        for q in [40, 30, 20]:
            data = save_img(resized.convert("RGB"), "JPEG", quality=q)
            if len(data) <= max_bytes:
                return data, "image/jpeg"

    raise ValueError(f"Unable to reduce image {path} under {max_bytes} bytes (original {orig_size})")

# -----------------------------
# Main async processing (uses prepare_image_bytes)
# -----------------------------
async def classify_image(session: aiohttp.ClientSession, image_path: str, api_key: str, rate_limiter: RateLimiter) -> Dict[str, Any]:
    """
    Send a single image to Gemini generateContent using inline base64 image bytes.
    Returns a dict with parsed labels and raw response/error.
    """
    result = {
        "filename": os.path.basename(image_path),
        "is_document": None,
        "is_handwritten": None,
        "has_scene_text": None,
        "has_people_faces": None,
        "is_screenshot": None,
        "is_art_illustration": None,
        "has_machine_code": None,
        "is_natural_image": None,
        "is_nsfw": None,
        "is_low_quality": None,
        "error": None,
    }

    try:
        try:
            img_bytes, mime_type = prepare_image_bytes(image_path, MAX_INLINE_BYTES)
        except Exception as e:
            result["error"] = f"Prepare image error: {e}"
            return result

        b64 = base64.b64encode(img_bytes).decode("ascii")

        # Gemini generateContent API payload structure
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": make_prompt()
                        },
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": b64
                            }
                        }
                    ]
                }
            ]
        }

        # Some Gemini deployments use x-goog-api-key header; others rely on oauth tokens.
        # We'll use x-goog-api-key per your original reference.
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key
        }

        # Respect per-key rate limit
        await rate_limiter.acquire()

        url = ENDPOINT_TEMPLATE.format(model=MODEL)
        timeout = aiohttp.ClientTimeout(total=120)
        async with session.post(url, json=payload, headers=headers, timeout=timeout) as resp:
            text = await resp.text()
            if resp.status != 200:
                # Check for 429 (quota exhausted)
                if resp.status == 429:
                    result["error"] = f"HTTP 429: Rate limit/quota exhausted"
                    result["retry"] = True  # Mark for retry
                    # Set 60 second timeout on this rate limiter
                    rate_limiter.set_timeout(60.0)
                else:
                    result["error"] = f"HTTP {resp.status}: {text[:500]}"
                return result

            # Parse JSON if possible
            try:
                j = json.loads(text)
            except Exception:
                j = None

            parsed = None
            # Extract model's produced text(s) - shape depends on API responses (candidates/candidates[*].content.parts etc.)
            if j:
                # Known shapes: { "candidates": [ { "content": { "parts": [ {"text": "..."} ] } } ] }
                try:
                    candidates = j.get("candidates") or []
                    if isinstance(candidates, list) and candidates:
                        parts_texts = []
                        for c in candidates:
                            cont = c.get("content") or {}
                            parts = cont.get("parts") or []
                            for p in parts:
                                if "text" in p:
                                    parts_texts.append(p["text"])
                        if parts_texts:
                            combined = "\n".join(parts_texts)
                            parsed, _ = extract_json_from_text(combined)
                except Exception:
                    parsed = None

            if parsed is None:
                parsed, _ = extract_json_from_text(text)

            if parsed:
                def conv_bool(v):
                    if isinstance(v, bool):
                        return v
                    if isinstance(v, (int, float)):
                        return bool(v)
                    if isinstance(v, str):
                        s = v.strip().lower()
                        if s in ("true", "yes", "1"):
                            return True
                        if s in ("false", "no", "0"):
                            return False
                    return None

                # Extract all classification fields
                result["is_document"] = conv_bool(parsed.get("is_document"))
                result["is_handwritten"] = conv_bool(parsed.get("is_handwritten"))
                result["has_scene_text"] = conv_bool(parsed.get("has_scene_text"))
                result["has_people_faces"] = conv_bool(parsed.get("has_people_faces"))
                result["is_screenshot"] = conv_bool(parsed.get("is_screenshot"))
                result["is_art_illustration"] = conv_bool(parsed.get("is_art_illustration"))
                result["has_machine_code"] = conv_bool(parsed.get("has_machine_code"))
                result["is_natural_image"] = conv_bool(parsed.get("is_natural_image"))
                result["is_nsfw"] = conv_bool(parsed.get("is_nsfw"))
                result["is_low_quality"] = conv_bool(parsed.get("is_low_quality"))
            else:
                result["error"] = result.get("error") or "Could not parse JSON from model response."

            return result

    except Exception as e:
        result["error"] = f"Exception: {repr(e)}"
        return result


async def worker_task(image_queue: asyncio.Queue, session: aiohttp.ClientSession, key_cycle, rate_limiters, out_queue: asyncio.Queue, retry_queue: asyncio.Queue):
    while True:
        try:
            image_path = await image_queue.get()
            if image_path is None:
                image_queue.task_done()
                break
            key_idx = next(key_cycle)
            api_key = API_KEYS[key_idx]
            rate_limiter = rate_limiters[key_idx]
            res = await classify_image(session, image_path, api_key, rate_limiter)
            
            # If it's a retry-able error (429), put back in retry queue
            if res.get("retry"):
                await retry_queue.put(image_path)
            else:
                # Only add successful results to output
                await out_queue.put(res)
        finally:
            image_queue.task_done()


async def main_async(folder: str, out_csv: str):
    allowed_ext = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
    images = []
    for root, _, files in os.walk(folder):
        for fn in files:
            ext = os.path.splitext(fn)[1].lower()
            if ext in allowed_ext:
                images.append(os.path.join(root, fn))
    if not images:
        print("No images found in folder.")
        return

    rate_limiters = [RateLimiter(RATE_LIMIT, RATE_PERIOD) for _ in API_KEYS]
    key_indices = list(range(len(API_KEYS)))
    key_cycle = itertools.cycle(key_indices)

    image_queue = asyncio.Queue()
    out_queue = asyncio.Queue()
    retry_queue = asyncio.Queue()

    for p in images:
        await image_queue.put(p)
    num_workers = min(GLOBAL_CONCURRENCY, max(1, len(images)))
    for _ in range(num_workers):
        await image_queue.put(None)

    timeout = aiohttp.ClientTimeout(total=180)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        workers = [
            asyncio.create_task(worker_task(image_queue, session, key_cycle, rate_limiters, out_queue, retry_queue))
            for _ in range(num_workers)
        ]

        fieldnames = ["filename", "is_document", "is_handwritten", "has_scene_text", "has_people_faces", 
                      "is_screenshot", "is_art_illustration", "has_machine_code", "is_natural_image",
                      "is_nsfw", "is_low_quality"]
        with open(out_csv, "w", newline="", encoding="utf-8") as csvf:
            writer = csv.DictWriter(csvf, fieldnames=fieldnames)
            writer.writeheader()

            processed = 0
            successful = 0
            total = len(images)
            while processed < total:
                res = await out_queue.get()
                
                # Only write to CSV if no error
                if not res.get("error"):
                    row = {
                        "filename": res.get("filename"),
                        "is_document": "" if res.get("is_document") is None else str(bool(res.get("is_document"))),
                        "is_handwritten": "" if res.get("is_handwritten") is None else str(bool(res.get("is_handwritten"))),
                        "has_scene_text": "" if res.get("has_scene_text") is None else str(bool(res.get("has_scene_text"))),
                        "has_people_faces": "" if res.get("has_people_faces") is None else str(bool(res.get("has_people_faces"))),
                        "is_screenshot": "" if res.get("is_screenshot") is None else str(bool(res.get("is_screenshot"))),
                        "is_art_illustration": "" if res.get("is_art_illustration") is None else str(bool(res.get("is_art_illustration"))),
                        "has_machine_code": "" if res.get("has_machine_code") is None else str(bool(res.get("has_machine_code"))),
                        "is_natural_image": "" if res.get("is_natural_image") is None else str(bool(res.get("is_natural_image"))),
                        "is_nsfw": "" if res.get("is_nsfw") is None else str(bool(res.get("is_nsfw"))),
                        "is_low_quality": "" if res.get("is_low_quality") is None else str(bool(res.get("is_low_quality")))
                    }
                    writer.writerow(row)
                    csvf.flush()
                    successful += 1
                    
                    # Build a compact display of active labels
                    labels = []
                    if res.get("is_document"): labels.append("doc")
                    if res.get("is_handwritten"): labels.append("handwritten")
                    if res.get("has_scene_text"): labels.append("scene_text")
                    if res.get("has_people_faces"): labels.append("people")
                    if res.get("is_screenshot"): labels.append("screenshot")
                    if res.get("is_art_illustration"): labels.append("art")
                    if res.get("has_machine_code"): labels.append("code")
                    if res.get("is_natural_image"): labels.append("natural")
                    if res.get("is_nsfw"): labels.append("NSFW")
                    if res.get("is_low_quality"): labels.append("low_qual")
                    labels_str = ",".join(labels) if labels else "none"
                    print(f"[{successful}/{total}] {row['filename']} -> [{labels_str}]")
                else:
                    # Log error but don't write to CSV
                    print(f"[ERR] {res.get('filename')} -> {res.get('error')}")
                
                processed += 1
                out_queue.task_done()

        await asyncio.gather(*workers)
        
        # Check retry queue and report failed images
        retry_count = retry_queue.qsize()
        if retry_count > 0:
            print(f"\n⚠️  {retry_count} images failed due to quota/rate limits and were not processed")
            print(f"✅ Successfully processed: {successful}/{total} images")


def main():
    if len(sys.argv) < 2:
        print("Usage: python gemini_multi_label_resizing_v2.py /path/to/images_folder [output.csv]")
        sys.exit(1)
    folder = sys.argv[1]
    out_csv = sys.argv[2] if len(sys.argv) >= 3 else "gemini_image_classification_v2.csv"
    asyncio.run(main_async(folder, out_csv))
    print("Done. Results saved to", out_csv)


if __name__ == "__main__":
    main()
