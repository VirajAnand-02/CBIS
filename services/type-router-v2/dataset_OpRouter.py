#!/usr/bin/env python3
"""
generate multilabel dataset for images using LLM

openrouter_multi_label_resizing.py

Multi-label image classification using OpenRouter (chat completions).
Images are inline-encoded (data:<mime>;base64,...) in the user message.
Resizes/encodes images if they exceed the inline size limit.

Outputs CSV with columns:
filename,is_document,has_people_faces,is_screenshot,raw_response,error

Usage:
    python openrouter_multi_label_resizing.py /path/to/images_folder [output.csv]

Requirements:
    pip install aiohttp Pillow
Notes:
    - Configure API keys via OPENROUTER_API_KEYS (comma separated) or OPENROUTER_API_KEY.
    - Set OPENROUTER_API_BASE to change base URL (default: https://openrouter.ai/api/v1).
    - Choose a multimodal model that accepts embedded data URIs (on OpenRouter).
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
# CONFIG: Put your API keys here or use env vars
# -----------------------------
API_KEYS: List[str] = []  # or leave empty to read from env

# Allow single-key env var or comma separated
if not API_KEYS:
    env_keys = os.getenv("OPENROUTER_API_KEYS") or os.getenv("OPENROUTER_API_KEY")
    if env_keys:
        API_KEYS = [k.strip() for k in env_keys.split(",") if k.strip()]

if not API_KEYS:
    raise SystemExit("No OpenRouter API keys found. Set OPENROUTER_API_KEYS or OPENROUTER_API_KEY env var.")

# Model to use (must be available on your OpenRouter account and support image input)
MODEL = os.getenv("OPENROUTER_MODEL", "gpt-4o")  # change to a multimodal model if available

# Rate limit per key (requests per window)
RATE_LIMIT = int(os.getenv("OPENROUTER_RATE_LIMIT", "10"))
RATE_PERIOD = float(os.getenv("OPENROUTER_RATE_PERIOD", "60.0"))  # seconds

# Concurrency throttling (total concurrent requests)
GLOBAL_CONCURRENCY = int(os.getenv("OPENROUTER_GLOBAL_CONCURRENCY", "12"))

# Max inline upload bytes (practical safety margin; many endpoints struggle > 15-20MB)
MAX_INLINE_BYTES = int(os.getenv("OPENROUTER_MAX_INLINE_BYTES", str(18 * 1024 * 1024)))  # 18 MB

# OpenRouter base URL (adjust if you use a different host/route)
OPENROUTER_API_BASE = os.getenv("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1")
ENDPOINT = f"{OPENROUTER_API_BASE}/chat/completions"

# -----------------------------
# Helper classes & functions
# -----------------------------
class RateLimiter:
    """Simple sliding-window rate limiter for N requests per window seconds."""
    def __init__(self, limit: int, window_s: float):
        self.limit = limit
        self.window = window_s
        self.timestamps = deque()

    async def acquire(self):
        while True:
            now = time.monotonic()
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
        "Classify the provided image and output a single JSON object ONLY (no extra text). "
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
    Make image bytes fit under max_bytes. Returns (image_bytes, mime_type).
    Strategy: reduce dimensions and/or jpeg quality, convert to JPEG if necessary.
    """
    orig_size = os.path.getsize(path)
    orig_mime = detect_mime_type_from_path(path)

    with open(path, "rb") as f:
        orig_bytes = f.read()
    if len(orig_bytes) <= max_bytes:
        return orig_bytes, orig_mime

    im = Image.open(path)
    im_format = (im.format or "JPEG").upper()

    scales = [0.95, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.15, 0.1]
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
            img = img.convert("RGB")
            save_kwargs["format"] = "JPEG"
            if quality is not None:
                save_kwargs["quality"] = quality
            save_kwargs["optimize"] = True
        img.save(bio, **save_kwargs)
        return bio.getvalue()

    for scale in scales:
        new_w = max(1, int(im.width * scale))
        new_h = max(1, int(im.height * scale))
        resized = im.resize((new_w, new_h), Image.Resampling.LANCZOS)
        if im_format in ("JPEG", "JPG"):
            for q in qualities:
                data = save_image_to_bytes(resized, "JPEG", quality=q)
                if len(data) <= max_bytes:
                    return data, "image/jpeg"
        else:
            try:
                data = save_image_to_bytes(resized, im_format)
                if len(data) <= max_bytes:
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
            for q in qualities:
                conv = resized.convert("RGB")
                data = save_image_to_bytes(conv, "JPEG", quality=q)
                if len(data) <= max_bytes:
                    return data, "image/jpeg"

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

    raise ValueError(f"Unable to reduce image {path} under {max_bytes} bytes (original {orig_size} bytes)")

# -----------------------------
# Main async processing
# -----------------------------
async def classify_image(session: aiohttp.ClientSession, image_path: str, api_key: str, rate_limiter: RateLimiter) -> Dict[str, Any]:
    """
    Send a single image to OpenRouter chat completions endpoint with inline data URI.
    Returns parsed labels and raw response/errors.
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
        data_uri = f"data:{mime_type};base64,{b64}"

        # Build messages. Many multimodal models accept an inline data URI inside the message content.
        messages = [
            {"role": "system", "content": "You are a helpful multimodal assistant that receives an image embedded as a data URI and must output a JSON object only."},
            {"role": "user", "content": make_prompt()},
            # The actual image is included as a separate user message. Models that support multimodal inputs should accept this.
            {"role": "user", "content": f"[IMAGE_DATA_URI_START]\n{data_uri}\n[IMAGE_DATA_URI_END]"},
        ]

        payload = {
            "model": MODEL,
            "messages": messages,
            # "max_tokens": 512,  # optional
            # If OpenRouter supports streaming or extra fields, you can place them here.
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        await rate_limiter.acquire()

        timeout = aiohttp.ClientTimeout(total=120)
        async with session.post(ENDPOINT, json=payload, headers=headers, timeout=timeout) as resp:
            text = await resp.text()
            result["raw_response"] = text
            if resp.status != 200:
                result["error"] = f"HTTP {resp.status}: {text[:500]}"
                return result

            try:
                j = json.loads(text)
            except Exception:
                j = None

            parsed = None
            if j:
                # try typical OpenAI-like response shape
                choices = j.get("choices") or j.get("items") or []
                if isinstance(choices, list) and choices:
                    # try to aggregate text fields
                    candidate_texts = []
                    for c in choices:
                        # typical: c["message"]["content"]
                        if isinstance(c, dict):
                            cont = c.get("message") or c.get("content") or c.get("delta") or {}
                            if isinstance(cont, dict):
                                txt = cont.get("content") or cont.get("text")
                                if isinstance(txt, str):
                                    candidate_texts.append(txt)
                            elif isinstance(cont, str):
                                candidate_texts.append(cont)
                    combined = "\n".join(candidate_texts) if candidate_texts else None
                    if combined:
                        parsed, _ = extract_json_from_text(combined)

            # If still not parsed, attempt to extract JSON from raw text directly
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
        print("Usage: python openrouter_multi_label_resizing.py /path/to/images_folder [output.csv]")
        sys.exit(1)
    folder = sys.argv[1]
    out_csv = sys.argv[2] if len(sys.argv) >= 3 else "openrouter_image_classification.csv"
    asyncio.run(main_async(folder, out_csv))
    print("Done. Results saved to", out_csv)


if __name__ == "__main__":
    main()
