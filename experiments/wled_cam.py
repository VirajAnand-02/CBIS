#!/usr/bin/env python3
"""
wled_cam_stream.py  (updated)
Live Raspberry Pi camera OR video -> WLED matrix streamer over UDP (DRGB).

Features:
 - Camera capture (with optional libcamera GStreamer pipeline fallback)
 - Video file or YouTube URL streaming (yt_dlp + moviepy) when --video is provided
 - Matrix size config (WxH)
 - Serpentine / linear wiring
 - Rotation & flip
 - Contrast, saturation, blur, gamma
 - Brightness via WLED HTTP API
 - Stable update-rate limiting (default 30 Hz)
 - Optional OpenCV preview
"""

import argparse
import socket
import time
import os
import sys
from typing import Tuple, Optional

try:
    import requests
except Exception:
    requests = None

try:
    import yt_dlp as youtube_dl
except Exception:
    youtube_dl = None

try:
    # MoviePy 2.x prefers: from moviepy import VideoFileClip
    from moviepy import VideoFileClip
except Exception:
    try:
        # MoviePy 1.x legacy import
        from moviepy.editor import VideoFileClip
    except Exception:
        VideoFileClip = None

try:
    import pygame
except Exception:
    pygame = None

import cv2
import numpy as np
from PIL import Image, ImageFilter

# ---------------- WLED UDP ----------------
WLED_UDP_PORT = 21324
DRGB_HEADER = bytearray([2, 2])  # DRGB protocol

# ---------------- Color helpers (improved) ----------------
def rgb_to_hsv(r, g, b):
    cmax, cmin = max(r, g, b), min(r, g, b)
    diff = cmax - cmin
    if diff == 0:
        h = 0
    elif cmax == r:
        h = (60 * ((g - b) / diff) + 360) % 360
    elif cmax == g:
        h = (60 * ((b - r) / diff) + 120) % 360
    else:
        h = (60 * ((r - g) / diff) + 240) % 360
    s = 0 if cmax == 0 else diff / cmax
    v = cmax
    return h / 360.0, s, v

def hsv_to_rgb(h, s, v):
    if s == 0:
        return v, v, v
    i = int(h * 6)
    f = h * 6 - i
    p = v * (1 - s)
    q = v * (1 - s * f)
    t = v * (1 - s * (1 - f))
    i %= 6
    return [(v,t,p),(q,v,p),(p,v,t),(p,q,v),(t,p,v),(v,p,q)][i]

def apply_contrast(rgb_tuple, factor):
    r, g, b = rgb_tuple
    r_f, g_f, b_f = float(r), float(g), float(b)
    r, g, b = (
        factor * (r_f - 128.0) + 128.0,
        factor * (g_f - 128.0) + 128.0,
        factor * (b_f - 128.0) + 128.0,
    )
    return int(max(0, min(255, r))), int(max(0, min(255, g))), int(max(0, min(255, b)))

def apply_saturation(rgb_tuple, factor):
    r, g, b = rgb_tuple
    r_f, g_f, b_f = r / 255.0, g / 255.0, b / 255.0
    h, s, v = rgb_to_hsv(r_f, g_f, b_f)
    s = max(0.0, min(1.0, s * factor))
    r2, g2, b2 = hsv_to_rgb(h, s, v)
    return int(r2 * 255), int(g2 * 255), int(b2 * 255)

def apply_gamma(rgb_tuple, gamma):
    inv = 1.0 / gamma if gamma > 0 else 1.0
    r, g, b = rgb_tuple
    return tuple(int(((c / 255.0) ** inv) * 255 + 0.5) for c in (r, g, b))

# ---------------- Optional audio playback (video mode) ----------------
def play_audio_from_clip(clip, audio_path: str) -> bool:
    """Extracts clip audio to a wav and plays it via pygame mixer."""
    if pygame is None:
        print("Warning: pygame not installed; cannot play audio")
        return False
    if getattr(clip, "audio", None) is None:
        print("Warning: No audio track found; continuing without audio")
        return False
    try:
        # Requires ffmpeg on PATH (MoviePy uses it under the hood)
        clip.audio.write_audiofile(audio_path, fps=44100, logger=None)
        pygame.mixer.init()
        pygame.mixer.music.load(audio_path)
        pygame.mixer.music.play()
        return True
    except Exception as e:
        print(f"Warning: Could not play audio: {e}")
        return False

# ---------------- Mapping ----------------
def xy_to_index(x, y, w, serpentine):
    if not serpentine:
        return y * w + x
    return y * w + (x if y % 2 == 0 else (w - 1 - x))

# ---------------- Utility: set brightness ----------------
def set_brightness(ip: str, bri: Optional[int]):
    if bri is None:
        return
    if requests is None:
        print("Warning: requests not installed; cannot set brightness via HTTP")
        return
    try:
        requests.post(f"http://{ip}/json/state", json={"on": True, "bri": bri}, timeout=2)
    except Exception as e:
        print(f"Warning: Could not set brightness: {e}")

# ---------------- Video download (optional) ----------------
def download_video(youtube_url: str, output_path: str = "tmp_video.mp4") -> Optional[str]:
    if youtube_dl is None:
        print("yt_dlp not installed; cannot download YouTube video.")
        return None
    ydl_opts = {
        'format': 'bestvideo[height<=720]+bestaudio/best[height<=720]/best',
        'outtmpl': output_path,
        'quiet': True,
        'merge_output_format': 'mp4'
    }
    try:
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            ydl.download([youtube_url])
        return output_path
    except Exception as e:
        print(f"Error downloading video: {e}")
        return None

# ---------------- Frame processing ----------------
def process_frame_pil(frame_rgb: np.ndarray, cfg) -> Tuple[bytearray, np.ndarray]:
    """
    frame_rgb : HxWx3 numpy array in RGB order
    Returns: (drgb_payload, preview_bgr)
    """
    img = Image.fromarray(frame_rgb)

    # rotate / flips (apply before resize)
    if cfg.rotate:
        img = img.rotate(cfg.rotate, expand=True)
    if cfg.flip_x:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    if cfg.flip_y:
        img = img.transpose(Image.FLIP_TOP_BOTTOM)

    # center crop + resize to matrix size (preserve aspect, crop)
    w, h = img.size
    scale = max(cfg.matrix_w / w, cfg.matrix_h / h)
    img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    left = (img.width - cfg.matrix_w) // 2
    top = (img.height - cfg.matrix_h) // 2
    img = img.crop((left, top, left + cfg.matrix_w, top + cfg.matrix_h))

    # blur
    if cfg.blur_radius and cfg.blur_radius > 0:
        img = img.filter(ImageFilter.GaussianBlur(cfg.blur_radius))

    preview_np = np.array(img, dtype=np.uint8)  # RGB

    # Prepare payload
    total = cfg.matrix_w * cfg.matrix_h * 3
    data = bytearray(total)

    # For small matrices (e.g., 16x16) a python loop is acceptable and keeps HSV conversions simple
    for y in range(cfg.matrix_h):
        for x in range(cfg.matrix_w):
            r, g, b = preview_np[y, x]
            if cfg.contrast != 1.0:
                r, g, b = apply_contrast((r, g, b), cfg.contrast)
            if cfg.saturation != 1.0:
                r, g, b = apply_saturation((r, g, b), cfg.saturation)
            if cfg.gamma != 1.0:
                r, g, b = apply_gamma((r, g, b), cfg.gamma)

            idx = xy_to_index(x, y, cfg.matrix_w, cfg.serpentine) * 3
            data[idx:idx+3] = bytes((int(r), int(g), int(b)))

    preview_bgr = cv2.cvtColor(preview_np, cv2.COLOR_RGB2BGR)
    return data, preview_bgr

# ---------------- Capture helpers ----------------
def make_libcamera_capture(width=640, height=480, framerate=30):
    # GStreamer pipeline for libcamera (Raspberry Pi)
    pipeline = (
        f"libcamerasrc ! video/x-raw,width={width},height={height},framerate={framerate}/1 "
        "! videoconvert ! appsink"
    )
    return cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)

# ---------------- Main loop ----------------
def run(cfg):
    # resolve wled ip/host
    wled_host = cfg.wled_ip.replace("http://", "").replace("https://", "").rstrip("/")
    try:
        wled_ip = socket.gethostbyname(wled_host)
    except socket.gaierror:
        print(f"Error: could not resolve WLED host '{cfg.wled_ip}'")
        return

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # If --video provided, stream video through moviepy (supports local files or downloaded youtube)
    clip = None
    audio_playing = False
    audio_tmp_path = "wled_tmp_audio.wav"
    if cfg.video:
        video_source = cfg.video
        if video_source.startswith("http") and ("youtube.com" in video_source or "youtu.be" in video_source):
            downloaded = download_video(video_source, "wled_tmp_video.mp4")
            if downloaded is None:
                print("Failed to download video; quitting.")
                return
            video_source = downloaded
        if VideoFileClip is None:
            print("moviepy is not installed; cannot play video files.")
            return
        try:
            clip = VideoFileClip(video_source)
            print(f"Opened video clip: duration {clip.duration:.2f}s")
        except Exception as e:
            print(f"Error opening video file: {e}")
            return

    else:
        # Camera mode
        # Try standard integer index, but provide libcamera fallback if it fails
        try:
            cap = cv2.VideoCapture(cfg.cam_index)
            if not cap.isOpened():
                print("cv2.VideoCapture failed to open default device; trying libcamera pipeline...")
                cap = make_libcamera_capture()
            if not cap.isOpened():
                print("Camera open failed.")
                return
        except Exception as e:
            print(f"Exception opening camera: {e}")
            return

    # brightness
    set_brightness(wled_ip, cfg.brightness_http)

    # Use a monotonic clock for pacing (more stable; also matches video playback timing)
    frame_interval = 1.0 / cfg.update_hz if cfg.update_hz > 0 else 0.0
    next_frame = time.monotonic()

    print(f"Streaming to {wled_ip}:{cfg.udp_port} @ {cfg.update_hz} Hz")
    if cfg.preview:
        cv2.namedWindow("Matrix Preview", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Matrix Preview", max(256, cfg.matrix_w * 16), max(256, cfg.matrix_h * 16))

    try:
        # Video mode: drive frames from playback time (monotonic), optionally with audio.
        if clip and cfg.audio:
            audio_playing = play_audio_from_clip(clip, audio_tmp_path)

        start_playback = time.monotonic()
        while True:
            now = time.monotonic()
            if frame_interval and now < next_frame:
                time.sleep(min(0.01, next_frame - now))
                continue
            if frame_interval:
                next_frame += frame_interval

            # get frame (RGB)
            if clip:
                # video mode - use clip.get_frame with elapsed playback time
                playback_t = time.monotonic() - start_playback
                if playback_t > clip.duration:
                    print("Video finished.")
                    break
                frame_rgb = clip.get_frame(playback_t)  # moviepy returns RGB
                # ensure uint8
                if frame_rgb.dtype != np.uint8:
                    frame_rgb = (frame_rgb * 255).astype(np.uint8)
            else:
                ret, frame_bgr = cap.read()
                if not ret:
                    # read failed, skip
                    continue
                # convert to RGB
                frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

            payload, preview = process_frame_pil(frame_rgb, cfg)

            # send to WLED
            sock.sendto(DRGB_HEADER + payload, (wled_ip, cfg.udp_port))

            if cfg.preview:
                # upscale preview for visibility
                scale = max(1, 256 // max(cfg.matrix_w, cfg.matrix_h))
                view = cv2.resize(preview, (cfg.matrix_w * scale, cfg.matrix_h * scale), interpolation=cv2.INTER_NEAREST)
                cv2.imshow("Matrix Preview", view)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    print("Preview quit requested.")
                    break

            # Prevent a tight loop from pegging CPU if update_hz is high or disabled.
            time.sleep(0.001)

    except KeyboardInterrupt:
        print("Interrupted by user.")
    finally:
        # blackout
        num_leds = cfg.matrix_w * cfg.matrix_h
        sock.sendto(DRGB_HEADER + bytearray(num_leds * 3), (wled_ip, cfg.udp_port))
        sock.close()
        if cfg.preview:
            cv2.destroyAllWindows()
        if not clip:
            try:
                cap.release()
            except Exception:
                pass
        else:
            try:
                clip.close()
            except Exception:
                pass

        if audio_playing and pygame is not None:
            try:
                pygame.mixer.music.stop()
                pygame.mixer.quit()
            except Exception:
                pass
        if audio_playing and os.path.exists(audio_tmp_path):
            try:
                os.remove(audio_tmp_path)
            except Exception:
                pass
        # cleanup downloaded video
        if cfg.video and cfg.video.startswith("http") and os.path.exists("wled_tmp_video.mp4"):
            try:
                os.remove("wled_tmp_video.mp4")
            except Exception:
                pass

# ---------------- CLI ----------------
def parse_args():
    p = argparse.ArgumentParser(description="Live camera or video -> WLED matrix streamer (DRGB)")
    p.add_argument("--wled", required=True, help="WLED hostname or IP (no protocol required)")
    p.add_argument("--width", type=int, default=16)
    p.add_argument("--height", type=int, default=16)
    p.add_argument("--serpentine", action="store_true")
    p.add_argument("--rotate", type=int, choices=[0,90,180,270], default=0)
    p.add_argument("--flipx", action="store_true")
    p.add_argument("--flipy", action="store_true")
    p.add_argument("--contrast", type=float, default=1.0)
    p.add_argument("--saturation", type=float, default=1.0)
    p.add_argument("--blur", type=float, default=0.0)
    p.add_argument("--gamma", type=float, default=1.0)
    p.add_argument("--cam", type=int, default=0, dest="cam_index")
    p.add_argument("--brightness", type=int, dest="brightness_http")
    p.add_argument("--hz", type=float, default=30.0, dest="update_hz")
    p.add_argument("--no-preview", dest="preview", action="store_false")
    p.add_argument("--port", type=int, default=WLED_UDP_PORT, dest="udp_port")
    p.add_argument("--video", type=str, default=None, help="Path to video file or YouTube URL (optional)")
    p.add_argument("--audio", action="store_true", help="In --video mode, play extracted audio via pygame")
    p.set_defaults(preview=True)

    a = p.parse_args()
    # Simple cfg object
    class Cfg:
        pass
    cfg = Cfg()
    cfg.wled_ip = a.wled
    cfg.matrix_w = a.width
    cfg.matrix_h = a.height
    cfg.serpentine = a.serpentine
    cfg.rotate = a.rotate
    cfg.flip_x = a.flipx
    cfg.flip_y = a.flipy
    cfg.contrast = a.contrast
    cfg.saturation = a.saturation
    cfg.blur_radius = a.blur
    cfg.gamma = a.gamma
    cfg.cam_index = a.cam_index
    cfg.preview = a.preview
    cfg.brightness_http = a.brightness_http
    cfg.udp_port = a.udp_port
    cfg.update_hz = a.update_hz
    cfg.video = a.video
    cfg.audio = a.audio
    return cfg

if __name__ == "__main__":
    cfg = parse_args()
    run(cfg)
