import argparse
import socket
import time
from typing import Tuple, Optional
import sys

try:
    import requests
except Exception:
    requests = None

import cv2
import numpy as np
from PIL import Image, ImageFilter

# --- WLED UDP Configuration ---
WLED_UDP_PORT = 21324
DRGB_HEADER = bytearray([2, 2])

# --- Color Adjustment Helper Functions (Unchanged) ---
def apply_contrast(rgb_tuple, factor):
    r, g, b = rgb_tuple
    # Avoid uint8 overflow by doing math in float
    r_f, g_f, b_f = float(r), float(g), float(b)
    r, g, b = (
        factor * (r_f - 128.0) + 128.0,
        factor * (g_f - 128.0) + 128.0,
        factor * (b_f - 128.0) + 128.0,
    )
    return int(max(0, min(255, r))), int(max(0, min(255, g))), int(max(0, min(255, b)))

def apply_saturation(rgb_tuple, factor):
    r, g, b = rgb_tuple
    r, g, b = r / 255.0, g / 255.0, b / 255.0
    h, s, v = rgb_to_hsv(r, g, b)
    s = max(0.0, min(1.0, s * factor))
    r, g, b = hsv_to_rgb(h, s, v)
    return int(r * 255), int(g * 255), int(b * 255)

def rgb_to_hsv(r, g, b):
    cmax, cmin = max(r, g, b), min(r, g, b)
    diff = cmax - cmin
    if cmax == cmin: h = 0
    elif cmax == r: h = (60 * ((g - b) / diff) + 360) % 360
    elif cmax == g: h = (60 * ((b - r) / diff) + 120) % 360
    else: h = (60 * ((r - g) / diff) + 240) % 360
    s = 0 if cmax == 0 else (diff / cmax)
    v = cmax
    return h / 360.0, s, v

def hsv_to_rgb(h, s, v):
    if s == 0.0: return v, v, v
    i = int(h * 6.0); f = (h * 6.0) - i
    p, q, t = v * (1.0 - s), v * (1.0 - s * f), v * (1.0 - s * (1.0 - f))
    i %= 6
    if i == 0: return v, t, p
    if i == 1: return q, v, p
    if i == 2: return p, v, t
    if i == 3: return p, q, v
    if i == 4: return t, p, v
    if i == 5: return v, p, q
    return 0,0,0


def apply_gamma(rgb_tuple, gamma: float):
    if gamma is None or gamma == 1.0:
        return rgb_tuple
    inv = 1.0 / gamma if gamma > 0 else 1.0
    r, g, b = rgb_tuple
    return tuple(int(((c / 255.0) ** inv) * 255 + 0.5) for c in (r, g, b))


def xy_to_index(x: int, y: int, w: int, serpentine: bool) -> int:
    if not serpentine:
        return y * w + x
    return y * w + (x if y % 2 == 0 else (w - 1 - x))


def set_brightness(wled_ip: str, bri: Optional[int]):
    if bri is None:
        return
    if requests is None:
        print("Warning: requests not installed; cannot set brightness via HTTP")
        return
    try:
        requests.post(f"http://{wled_ip}/json/state", json={"on": True, "bri": int(bri)}, timeout=2)
    except Exception as e:
        print(f"Warning: Could not set brightness: {e}")


def process_webcam_frame(
    frame_bgr: np.ndarray,
    matrix_w: int,
    matrix_h: int,
    serpentine: bool,
    wled_flipx: bool,
    wled_flipy: bool,
    contrast: float,
    saturation: float,
    blur_radius: float,
    gamma: float,
    rotate: int,
    flipx: bool,
    flipy: bool,
) -> Tuple[bytearray, np.ndarray]:
    """Return (wled_payload, preview_rgb_small)."""
    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    img = Image.fromarray(frame_rgb)

    # Optional image transforms before resize/crop
    if rotate:
        img = img.rotate(rotate, expand=True)
    if flipx:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    if flipy:
        img = img.transpose(Image.FLIP_TOP_BOTTOM)

    # Center crop + resize to matrix size (preserve aspect, crop)
    w, h = img.size
    scale = max(matrix_w / w, matrix_h / h)
    img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    left = (img.width - matrix_w) // 2
    top = (img.height - matrix_h) // 2
    img = img.crop((left, top, left + matrix_w, top + matrix_h))

    if blur_radius and blur_radius > 0:
        img = img.filter(ImageFilter.GaussianBlur(radius=blur_radius))

    small = np.array(img, dtype=np.uint8)  # RGB, HxWx3
    payload = bytearray(matrix_w * matrix_h * 3)

    for y in range(matrix_h):
        for x in range(matrix_w):
            r, g, b = small[y, x]
            if contrast != 1.0:
                r, g, b = apply_contrast((r, g, b), contrast)
            if saturation != 1.0:
                r, g, b = apply_saturation((r, g, b), saturation)
            if gamma != 1.0:
                r, g, b = apply_gamma((r, g, b), gamma)

            # Match tmp.py behavior by allowing WLED-mapping flips
            tx = (matrix_w - 1 - x) if wled_flipx else x
            ty = (matrix_h - 1 - y) if wled_flipy else y
            idx = xy_to_index(tx, ty, matrix_w, serpentine) * 3
            payload[idx:idx + 3] = bytes((int(r), int(g), int(b)))

    return payload, small


def run_webcam(cfg):
    wled_host = cfg.wled.replace("http://", "").replace("https://", "").rstrip("/")
    try:
        wled_ip = socket.gethostbyname(wled_host)
    except socket.gaierror:
        print(f"Error: could not resolve WLED host '{cfg.wled}'")
        return

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # Windows: DirectShow is often more reliable than MSMF
    if sys.platform.startswith("win") and hasattr(cv2, "CAP_DSHOW"):
        cap = cv2.VideoCapture(cfg.cam, cv2.CAP_DSHOW)
    else:
        cap = cv2.VideoCapture(cfg.cam)
    if not cap.isOpened():
        print("Error: could not open webcam")
        return

    set_brightness(wled_ip, cfg.brightness)

    frame_interval = 1.0 / cfg.hz if cfg.hz > 0 else 0.0
    next_frame = time.monotonic()

    if cfg.preview:
        cv2.namedWindow("Matrix Preview", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Matrix Preview", max(256, cfg.width * 16), max(256, cfg.height * 16))

    num_leds = cfg.width * cfg.height
    print(f"Streaming webcam -> {wled_ip}:{cfg.port} @ {cfg.hz} Hz ({cfg.width}x{cfg.height})")

    frames_sent = 0
    frames_failed = 0
    last_stats = time.monotonic()

    try:
        while True:
            now = time.monotonic()
            if frame_interval and now < next_frame:
                time.sleep(min(0.01, next_frame - now))
                continue
            if frame_interval:
                next_frame += frame_interval

            ret, frame_bgr = cap.read()
            if not ret:
                frames_failed += 1
                continue

            payload, preview_rgb = process_webcam_frame(
                frame_bgr=frame_bgr,
                matrix_w=cfg.width,
                matrix_h=cfg.height,
                serpentine=cfg.serpentine,
                wled_flipx=cfg.wled_flipx,
                wled_flipy=cfg.wled_flipy,
                contrast=cfg.contrast,
                saturation=cfg.saturation,
                blur_radius=cfg.blur,
                gamma=cfg.gamma,
                rotate=cfg.rotate,
                flipx=cfg.flipx,
                flipy=cfg.flipy,
            )

            sock.sendto(DRGB_HEADER + payload, (wled_ip, cfg.port))
            frames_sent += 1

            if cfg.preview:
                preview_bgr = cv2.cvtColor(preview_rgb, cv2.COLOR_RGB2BGR)
                scale = max(1, 256 // max(cfg.width, cfg.height))
                view = cv2.resize(
                    preview_bgr,
                    (cfg.width * scale, cfg.height * scale),
                    interpolation=cv2.INTER_NEAREST,
                )
                cv2.imshow("Matrix Preview", view)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

            time.sleep(0.001)

            # Periodic stats to help diagnose "running but not outputting"
            now_stats = time.monotonic()
            if now_stats - last_stats >= 2.0:
                fps = frames_sent / max(0.001, (now_stats - last_stats))
                print(f"sent={frames_sent} failed={frames_failed} approx_fps={fps:.1f}")
                frames_sent = 0
                frames_failed = 0
                last_stats = now_stats

    except KeyboardInterrupt:
        pass
    finally:
        try:
            sock.sendto(DRGB_HEADER + bytearray(num_leds * 3), (wled_ip, cfg.port))
        except Exception:
            pass
        sock.close()
        cap.release()
        if cfg.preview:
            cv2.destroyAllWindows()


def parse_args():
    p = argparse.ArgumentParser(description="Webcam -> WLED matrix streamer (DRGB)")
    p.add_argument("--wled", required=True, help="WLED hostname or IP (no protocol required)")
    p.add_argument("--width", type=int, default=16, help="Matrix width")
    p.add_argument("--height", type=int, default=16, help="Matrix height")
    p.add_argument("--serpentine", action="store_true", help="Serpentine wiring")
    p.add_argument("--rotate", type=int, choices=[0, 90, 180, 270], default=0, help="Rotate input image")
    p.add_argument("--flipx", action="store_true", help="Flip input image horizontally")
    p.add_argument("--flipy", action="store_true", help="Flip input image vertically")

    # Default to tmp.py mapping (both axes flipped) since it is known-good in this setup.
    p.add_argument("--no-wled-flipx", dest="wled_flipx", action="store_false", help="Disable WLED mapping X flip")
    p.add_argument("--no-wled-flipy", dest="wled_flipy", action="store_false", help="Disable WLED mapping Y flip")

    p.add_argument("--cam", type=int, default=0, help="Webcam device index")
    p.add_argument("--brightness", type=int, default=None, help="Set WLED brightness via HTTP (0-255)")
    p.add_argument("--contrast", type=float, default=1.0)
    p.add_argument("--saturation", type=float, default=1.0)
    p.add_argument("--blur", type=float, default=0.0, help="Gaussian blur radius")
    p.add_argument("--gamma", type=float, default=1.0)
    p.add_argument("--hz", type=float, default=30.0, help="Update rate")
    p.add_argument("--port", type=int, default=WLED_UDP_PORT, help="WLED UDP port")
    p.add_argument("--no-preview", dest="preview", action="store_false")
    p.set_defaults(preview=True, wled_flipx=True, wled_flipy=True)
    return p.parse_args()


if __name__ == '__main__':
    cfg = parse_args()
    run_webcam(cfg)