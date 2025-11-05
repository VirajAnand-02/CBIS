#!/usr/bin/env python3
"""
gemini_multi_label_resizing.py

Classify images (multi-label) using Gemini REST generateContent API.

Now with automatic resizing/format conversion if images exceed the inline size limit.

Outputs CSV with columns:
filename,is_document,has_people_faces,is_screenshot,raw_response,error

Usage:
    python gemini_multi_label_resizing.py /path/to/images_folder [output.csv]

Requirements:
    pip install aiohttp Pillow
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

# -----------------------------
# CONFIG: Put your API keys here
# -----------------------------
API_KEYS: List[str] = [
    "AIzaSyCTywawZnqACjYj1ZvWTqdw-NvtuGan53E",
    "AIzaSyDLc2a_cN4Cxgt_bFntL19UVrp4VBs3BVo"
]

if not API_KEYS:
    env_keys = os.getenv("GEMINI_API_KEYS")
    if env_keys:
        API_KEYS = [k.strip() for k in env_keys.split(",") if k.strip()]

if not API_KEYS:
    raise SystemExit("No Gemini API keys found. Add keys to API_KEYS or set GEMINI_API_KEYS env var.")

# Gemini model to use
MODEL = "gemini-flash-lite-latest" # models/gemini-flash-lite-latest

# Rate limit per key (10 requests per 60 seconds as requested)
RATE_LIMIT = 10
RATE_PERIOD = 60.0  # seconds

# Concurrency throttling (total concurrent requests)
GLOBAL_CONCURRENCY = 12

# Max inline upload bytes (practical safety margin <20MB). We'll resize to fit under this.
MAX_INLINE_BYTES = 18 * 1024 * 1024  # 18 MB

# Gemini endpoint
ENDPOINT_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# -----------------------------
# Helper classes & functions
# -----------------------------
class RateLimiter:
    """Simple sliding-window rate limiter for N requests per window seconds."""
    def __init__(self, limit: int, window_s: float):
        self.limit = limit
        self.window = window_s
        self.timestamps = deque()  # store float timestamps

    async def acquire(self):
        """Wait until allowed, then record a new timestamp."""
        while True:
            now = time.monotonic()
            # pop old timestamps
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


def detect_mime_type_from_path(path: str) -> str:
    mt, _ = mimetypes.guess_type(path)
    if mt and mt.startswith("image/"):
        return mt
    try:
        with Image.open(path) as im:
            fmt = im.format or "JPEG"
            return {
                "JPEG": "image/jpeg",
                "PNG": "image/png",
                "WEBP": "image/webp",
                "HEIC": "image/heic",
                "HEIF": "image/heif",
            }.get(fmt.upper(), "image/jpeg")
    except Exception:
        return "image/jpeg"


def make_prompt() -> str:
    return (
        "Classify this image and output a single JSON object ONLY (no extra text). "
        "The JSON must contain three keys: "
        "\"is_document\" (true/false), "
        "\"has_people_faces\" (true/false), "
        "\"is_screenshot\" (true/false). "
        "Optionally include an \"explanation\" string describing why. "
        "Example output: {\"is_document\": true, \"has_people_faces\": false, \"is_screenshot\": false, \"explanation\":\"...\"}"
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
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start:end+1]
        try:
            obj = json.loads(candidate)
            return obj, text
        except Exception:
            try:
                cand2 = candidate.replace("'", '"')
                obj = json.loads(cand2)
                return obj, text
            except Exception:
                pass
    return None, text


def prepare_image_bytes(path: str, max_bytes: int = MAX_INLINE_BYTES) -> Tuple[bytes, str]:
    """
    Prepare the image bytes to be under max_bytes.
    Returns (image_bytes, mime_type).
    Strategy:
      - If already under limit, return original bytes and detected mime.
      - Otherwise open with PIL and iteratively downscale (reduce dimensions),
        lower JPEG quality, and if needed convert to JPEG (flatten alpha) and continue.
    """
    orig_size = os.path.getsize(path)
    orig_mime = detect_mime_type_from_path(path)

    with open(path, "rb") as f:
        orig_bytes = f.read()
    if len(orig_bytes) <= max_bytes:
        return orig_bytes, orig_mime

    # Open PIL image
    im = Image.open(path)
    im_format = (im.format or "JPEG").upper()

    # Prepare scale and quality candidates
    # We'll iterate scales from 0.95 down to 0.1 (bigger jumps for big images)
    scales = [0.95, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.15, 0.1]
    # JPEG quality options (start high then lower)
    qualities = [95, 85, 75, 65, 50, 40]

    def save_image_to_bytes(img: Image.Image, fmt: str, quality: Optional[int] = None) -> bytes:
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
            # fallback to JPEG
            img = img.convert("RGB")
            save_kwargs["format"] = "JPEG"
            if quality is not None:
                save_kwargs["quality"] = quality
            save_kwargs["optimize"] = True
        img.save(bio, **save_kwargs)
        return bio.getvalue()

    # Try couple of strategies:
    # 1) reduce dimensions but keep format
    for scale in scales:
        new_w = max(1, int(im.width * scale))
        new_h = max(1, int(im.height * scale))
        resized = im.resize((new_w, new_h), Image.Resampling.LANCZOS)
        # If original was JPEG-like, try JPEG quality reductions
        if im_format in ("JPEG", "JPG"):
            for q in qualities:
                data = save_image_to_bytes(resized, "JPEG", quality=q)
                if len(data) <= max_bytes:
                    return data, "image/jpeg"
        else:
            # Try saving in same format first (PNG/WEBP)
            try:
                data = save_image_to_bytes(resized, im_format)
                if len(data) <= max_bytes:
                    # determine mime from format
                    mime = {
                        "PNG": "image/png",
                        "WEBP": "image/webp",
                        "HEIC": "image/heic",
                        "HEIF": "image/heif"
                    }.get(im_format, None)
                    if mime:
                        return data, mime
            except Exception:
                pass
            # If still too big, convert to JPEG and try quality reductions
            for q in qualities:
                conv = resized.convert("RGB")
                data = save_image_to_bytes(conv, "JPEG", quality=q)
                if len(data) <= max_bytes:
                    return data, "image/jpeg"

    # 2) As a last resort, aggressively reduce quality and dimensions further
    # Try few very small target sizes
    tiny_scales = [0.08, 0.06, 0.04, 0.02]
    for scale in tiny_scales:
        new_w = max(1, int(im.width * scale))
        new_h = max(1, int(im.height * scale))
        resized = im.resize((new_w, new_h), Image.Resampling.LANCZOS)
        for q in [40, 30, 20]:
            conv = resized.convert("RGB")
            data = save_image_to_bytes(conv, "JPEG", quality=q)
            if len(data) <= max_bytes:
                return data, "image/jpeg"

    # If we reach here, we were unable to make it small enough
    raise ValueError(f"Unable to reduce image {path} under {max_bytes} bytes (final size {len(orig_bytes)})")

# -----------------------------
# Main async processing (classify_image uses prepare_image_bytes)
# -----------------------------
async def classify_image(session: aiohttp.ClientSession, image_path: str, api_key: str, rate_limiter: RateLimiter) -> Dict[str, Any]:
    """
    Send a single image to Gemini generateContent using inline base64 image bytes.
    """
    result = {
        "filename": os.path.basename(image_path),
        "is_document": None,
        "has_people_faces": None,
        "is_screenshot": None,
        "raw_response": None,
        "error": None,
    }

    try:
        try:
            img_bytes, mime_type = prepare_image_bytes(image_path, MAX_INLINE_BYTES)
        except Exception as e:
            result["error"] = f"Prepare image error: {e}"
            return result

        b64 = base64.b64encode(img_bytes).decode("ascii")

        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": b64
                            }
                        },
                        {"text": make_prompt()}
                    ]
                }
            ]
        }

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key
        }

        # respect per-key rate limit
        await rate_limiter.acquire()

        url = ENDPOINT_TEMPLATE.format(model=MODEL)
        timeout = aiohttp.ClientTimeout(total=120)
        async with session.post(url, json=payload, headers=headers, timeout=timeout) as resp:
            text = await resp.text()
            result["raw_response"] = text
            if resp.status != 200:
                result["error"] = f"HTTP {resp.status}: {text[:500]}"
                return result

            # parse JSON from response
            parsed = None
            try:
                j = json.loads(text)
            except Exception:
                j = None

            if j:
                try:
                    candidates = j.get("candidates") or []
                    if isinstance(candidates, list) and candidates:
                        parts_texts = []
                        for c in candidates:
                            cont = c.get("content", {})
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

                result["is_document"] = conv_bool(parsed.get("is_document"))
                result["has_people_faces"] = conv_bool(parsed.get("has_people_faces"))
                result["is_screenshot"] = conv_bool(parsed.get("is_screenshot"))
            else:
                result["error"] = result.get("error") or "Could not parse JSON from model response."

            return result

    except Exception as e:
        result["error"] = f"Exception: {repr(e)}"
        return result


async def worker_task(image_queue: asyncio.Queue, session: aiohttp.ClientSession, key_cycle, rate_limiters, out_queue: asyncio.Queue):
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

    for p in images:
        await image_queue.put(p)
    num_workers = min(GLOBAL_CONCURRENCY, max(1, len(images)))
    for _ in range(num_workers):
        await image_queue.put(None)

    timeout = aiohttp.ClientTimeout(total=180)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        workers = [
            asyncio.create_task(worker_task(image_queue, session, key_cycle, rate_limiters, out_queue))
            for _ in range(num_workers)
        ]

        fieldnames = ["filename", "is_document", "has_people_faces", "is_screenshot", "raw_response", "error"]
        with open(out_csv, "w", newline="", encoding="utf-8") as csvf:
            writer = csv.DictWriter(csvf, fieldnames=fieldnames)
            writer.writeheader()

            processed = 0
            total = len(images)
            while processed < total:
                res = await out_queue.get()
                row = {
                    "filename": res.get("filename"),
                    "is_document": "" if res.get("is_document") is None else str(bool(res.get("is_document"))),
                    "has_people_faces": "" if res.get("has_people_faces") is None else str(bool(res.get("has_people_faces"))),
                    "is_screenshot": "" if res.get("is_screenshot") is None else str(bool(res.get("is_screenshot"))),
                    "raw_response": (res.get("raw_response") or "")[:10000],
                    "error": res.get("error") or ""
                }
                writer.writerow(row)
                csvf.flush()
                processed += 1
                print(f"[{processed}/{total}] {row['filename']} -> doc={row['is_document']} faces={row['has_people_faces']} screenshot={row['is_screenshot']} err={row['error']}")
                out_queue.task_done()

        await asyncio.gather(*workers)


def main():
    if len(sys.argv) < 2:
        print("Usage: python gemini_multi_label_resizing.py /path/to/images_folder [output.csv]")
        sys.exit(1)
    folder = sys.argv[1]
    out_csv = sys.argv[2] if len(sys.argv) >= 3 else "gemini_image_classification.csv"
    asyncio.run(main_async(folder, out_csv))
    print("Done. Results saved to", out_csv)


if __name__ == "__main__":
    main()
