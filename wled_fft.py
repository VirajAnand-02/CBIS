import time
import socket
import numpy as np
import cv2
import soundcard as sc
import requests
import json
import mss
from colorgram import extract
from PIL import Image
import threading

# --- Configuration ---
CONFIG_FILE = "wled_vu_config.json"
WLED_IP = 'wled-tube.local'
WLED_UDP_PORT = 21324
DRGB_HEADER = bytearray([2, 2])
MATRIX_WIDTH, MATRIX_HEIGHT = 16, 16
FPS = 30
MIN_DB, MAX_DB = -60, 0
SAMPLE_RATE, NUM_SAMPLES = 44100, 1024
COLOR_TRANSITION_DURATION = 0.5

# --- Controls Definition ---
CONTROL_MAP = {
    'squish': ("Freq Squish", 300),
    'log_mix': ("Log/Lin Mix", 100),
    'sensitivity': ("Sensitivity", 200),
    'decay': ("Decay (Smooth)", 99),
    # --- CHANGED: Expanded slider range for a wider offset ---
    'threshold': ("Level Threshold", MATRIX_HEIGHT * 2),
    'min_freq': ("Min Freq (Hz)", 500),
    'max_freq': ("Max Freq (Hz)", 22000),
    'brightness': ("Brightness", 255)
}

# --- Shared State for Threading ---
g_target_palette = {'grad_start': (0,255,0), 'grad_end': (255,0,0)}
palette_lock = threading.Lock()
stop_thread_flag = False

# --- Color Helper Functions ---
def rgb_to_hsv(r, g, b):
    cmax, cmin = max(r, g, b), min(r, g, b); diff = cmax - cmin
    if cmax == cmin: h = 0
    elif cmax == r: h = (60 * ((g - b) / diff) + 360) % 360
    elif cmax == g: h = (60 * ((b - r) / diff) + 120) % 360
    else: h = (60 * ((r - g) / diff) + 240) % 360
    s = 0 if cmax == 0 else (diff / cmax); v = cmax
    return h / 360.0, s, v

def hsv_to_rgb(h, s, v):
    if s == 0.0: return v, v, v
    i = int(h * 6.0); f = (h * 6.0) - i
    p, q, t = v * (1.0 - s), v * (1.0 - s * f), v * (1.0 - s * (1.0 - f))
    i %= 6
    if i == 0: return v, t, p;
    if i == 1: return q, v, p;
    if i == 2: return p, v, t
    if i == 3: return p, q, v;
    if i == 4: return t, p, v;
    if i == 5: return v, p, q
    return 0,0,0

def force_saturate(rgb_tuple: tuple, saturation_level: float = 1.0) -> tuple:
    if rgb_tuple is None: return 255, 0, 0
    r, g, b = (c / 255.0 for c in rgb_tuple)
    h, s, v = rgb_to_hsv(r, g, b)
    s = min(1.0, max(0.0, saturation_level))  # Ensure saturation is between 0 and 1
    r, g, b = hsv_to_rgb(h, s, v)
    return int(r * 255), int(g * 255), int(b * 255)

def lerp_color(start_color, end_color, alpha):
    r = int(start_color[0] + (end_color[0] - start_color[0]) * alpha)
    g = int(start_color[1] + (end_color[1] - start_color[1]) * alpha)
    b = int(start_color[2] + (end_color[2] - start_color[2]) * alpha)
    return (r, g, b)

# --- Color Sampler Thread ---
def color_sampler_thread_func():
    print("Color sampler thread started.")
    while not stop_thread_flag:
        try:
            with mss.mss() as sct:
                img = Image.frombytes("RGB", sct.grab(sct.monitors[1]).size, sct.grab(sct.monitors[1]).bgra, "raw", "BGRX")
                img.thumbnail((200, 200))
                colors = extract(img, 6)
                if len(colors) >= 3:
                    colors.sort(key=lambda c: (0.2126*c.rgb.r + 0.7152*c.rgb.g + 0.0722*c.rgb.b))
                    start_color_raw = (colors[1].rgb.r, colors[1].rgb.g, colors[1].rgb.b)
                    end_color_raw = (colors[-1].rgb.r, colors[-1].rgb.g, colors[-1].rgb.b)
                    with palette_lock:
                        g_target_palette['grad_start'] = force_saturate(start_color_raw)
                        g_target_palette['grad_end'] = force_saturate(end_color_raw)
        except Exception: pass
        time.sleep(1.0 / 5.0)
    print("Color sampler thread stopped.")

# --- Config, UI, Matrix, and Networking Functions ---
def save_config(controls: dict):
    try:
        with open(CONFIG_FILE, 'w') as f: json.dump(controls, f, indent=4)
        print(f"Configuration saved to {CONFIG_FILE}")
    except Exception as e: print(f"Error saving config: {e}")

def load_config(defaults: dict) -> dict:
    try:
        with open(CONFIG_FILE, 'r') as f: loaded = json.load(f)
        print(f"Configuration loaded from {CONFIG_FILE}")
        for key in defaults:
            if key not in loaded: loaded[key] = defaults[key]
        return loaded
    except Exception:
        print("No config file found or error loading, using defaults."); return defaults

def setup_ui_controls(controls: dict):
    cv2.namedWindow("Controls", cv2.WINDOW_NORMAL); cv2.resizeWindow("Controls", 400, 450)
    def nothing(x): pass
    for key, (display_name, max_val) in CONTROL_MAP.items():
        cv2.createTrackbar(display_name, "Controls", controls.get(key, 0), max_val, nothing)

def get_control_values() -> dict:
    values_raw = {key: cv2.getTrackbarPos(name, "Controls") for key, (name, _) in CONTROL_MAP.items()}
    values_raw['squish_factor'] = values_raw['squish'] / 100.0
    values_raw['log_mix_factor'] = values_raw['log_mix'] / 100.0
    values_raw['sensitivity_factor'] = values_raw['sensitivity'] / 20.0
    values_raw['decay_factor'] = 0.8 + (values_raw['decay'] / 500.0)
    # Slider (0-32) is mapped to an offset from -16 to +16. Neutral is 16.
    values_raw['threshold_offset'] = values_raw['threshold'] - MATRIX_HEIGHT
    values_raw['min_freq'] = max(1, values_raw['min_freq'])
    values_raw['max_freq'] = max(values_raw['min_freq'] + 100, values_raw['max_freq'])
    return values_raw

def update_ui_from_config(config: dict):
    for key, value in config.items():
        if key in CONTROL_MAP: cv2.setTrackbarPos(CONTROL_MAP[key][0], "Controls", value)

def get_gradient_color(value: float, palette: dict) -> tuple:
    value = max(0.0, min(1.0, value))
    return lerp_color(palette['grad_start'], palette['grad_end'], value)

def create_vu_matrix(fft_magnitudes, fft_freqs, peak_levels, controls, palette) -> tuple:
    output_matrix = np.zeros((MATRIX_HEIGHT, MATRIX_WIDTH, 3), dtype=np.uint8)
    min_f, max_f = controls['min_freq'], controls['max_freq']
    linear_bins = np.linspace(min_f, max_f, num=MATRIX_WIDTH + 1)
    log_bins = np.logspace(np.log10(min_f), np.log10(max_f), num=MATRIX_WIDTH + 1)
    final_bins = (1 - controls['squish_factor']) * linear_bins + controls['squish_factor'] * log_bins
    band_magnitudes = np.zeros(MATRIX_WIDTH)
    for i in range(MATRIX_WIDTH):
        mask = (fft_freqs >= final_bins[i]) & (fft_freqs < final_bins[i+1])
        if np.any(mask): band_magnitudes[i] = np.mean(fft_magnitudes[mask])
    epsilon = np.finfo(float).eps
    linear_heights = band_magnitudes * controls['sensitivity_factor'] * 0.1
    db_magnitudes = 20 * np.log10(band_magnitudes + epsilon)
    normalized_db = np.clip((db_magnitudes - MIN_DB) / (MAX_DB - MIN_DB), 0, 1)
    decibel_heights = normalized_db * MATRIX_HEIGHT
    mixed_heights = ((1 - controls['log_mix_factor']) * linear_heights + controls['log_mix_factor'] * decibel_heights)
    bar_heights = np.int32(mixed_heights * (1 + controls['sensitivity_factor']))
    bar_heights += controls['threshold_offset']
    bar_heights = np.clip(bar_heights, 0, MATRIX_HEIGHT)
    new_peaks = np.maximum(bar_heights, peak_levels * controls['decay_factor'])
    for x in range(MATRIX_WIDTH):
        height = int(new_peaks[x])
        for y in range(height):
            output_matrix[MATRIX_HEIGHT - 1 - y, x] = get_gradient_color(y / (MATRIX_HEIGHT - 1) if MATRIX_HEIGHT > 1 else 1.0, palette)
    return new_peaks, output_matrix

def matrix_to_wled_data(matrix_np: np.ndarray) -> bytearray:
    h, w, _ = matrix_np.shape; wled_data = bytearray(w * h * 3)
    for y in range(h):
        for x in range(w):
            idx = ((h - 1 - y) * w + (w - 1 - x)) * 3
            wled_data[idx:idx+3] = tuple(matrix_np[y, x])
    return wled_data

# --- Main Application ---
def run_vu_meter():
    global stop_thread_flag
    print("Initializing...")
    try:
        wled_ip_resolved = socket.gethostbyname(WLED_IP); sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    except socket.gaierror: print(f"Error: Could not resolve hostname '{WLED_IP}'."); return

    default_controls = {
        'squish': 100, 'log_mix': 50, 'sensitivity': 80, 'decay': 92,
        # --- CHANGED: Set default slider position to the new neutral middle (16) ---
        'threshold': MATRIX_HEIGHT,
        'min_freq': 60, 'max_freq': 12000, 'brightness': 128
    }
    initial_controls = load_config(default_controls)
    setup_ui_controls(initial_controls)
    
    cv2.namedWindow("VU Meter Preview", cv2.WINDOW_NORMAL); cv2.resizeWindow("VU Meter Preview", 256, 256)
    
    peak_levels = np.zeros(MATRIX_WIDTH); last_brightness = -1
    display_palette = g_target_palette.copy()
    previous_palette = g_target_palette.copy()
    current_target_palette = g_target_palette.copy()
    transition_start_time = 0

    color_thread = threading.Thread(target=color_sampler_thread_func, daemon=True); color_thread.start()

    try:
        default_speaker = sc.default_speaker()
        all_mics = sc.all_microphones(include_loopback=True)
        loopback_mic = next((m for m in all_mics if m.isloopback and default_speaker.name in m.name), None)
        if loopback_mic is None: print("Error: Could not find a loopback device."); return

        print(f"\n--- INSTRUCTIONS ---\nStreaming to {wled_ip_resolved}\nPress 's' to Save\nPress 'l' to Load\nPress 'q' to Quit\n--------------------\n")
        
        with loopback_mic.recorder(samplerate=SAMPLE_RATE, blocksize=NUM_SAMPLES) as recorder:
            while True:
                current_time = time.monotonic()
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'): break
                elif key == ord('s'): save_config(get_control_values())
                elif key == ord('l'): update_ui_from_config(load_config(default_controls))

                with palette_lock: newly_sampled_palette = g_target_palette.copy()
                if newly_sampled_palette != current_target_palette:
                    previous_palette = display_palette.copy()
                    current_target_palette = newly_sampled_palette.copy()
                    transition_start_time = current_time

                progress = min(1.0, (current_time - transition_start_time) / COLOR_TRANSITION_DURATION)
                display_palette['grad_start'] = lerp_color(previous_palette['grad_start'], current_target_palette['grad_start'], progress)
                display_palette['grad_end'] = lerp_color(previous_palette['grad_end'], current_target_palette['grad_end'], progress)

                controls = get_control_values()
                if controls['brightness'] != last_brightness:
                    try: requests.post(f"http://{wled_ip_resolved}/json/state", json={"bri": controls['brightness']}, timeout=0.5)
                    except requests.RequestException: pass
                    last_brightness = controls['brightness']

                audio_data = recorder.record(numframes=NUM_SAMPLES)
                if audio_data is None or audio_data.size == 0: continue
                
                mono_audio = np.mean(audio_data, axis=1) if audio_data.ndim > 1 else audio_data
                fft_magnitudes = np.abs(np.fft.rfft(mono_audio))
                fft_freqs = np.fft.rfftfreq(n=len(mono_audio), d=1.0/SAMPLE_RATE)

                peak_levels, preview_matrix_np = create_vu_matrix(fft_magnitudes, fft_freqs, peak_levels, controls, display_palette)
                sock.sendto(DRGB_HEADER + matrix_to_wled_data(preview_matrix_np), (wled_ip_resolved, WLED_UDP_PORT))
                
                cv2.imshow("VU Meter Preview", cv2.cvtColor(preview_matrix_np, cv2.COLOR_RGB2BGR))
                
                if (sleep_time := (1.0 / FPS) - (time.monotonic() - current_time)) > 0: time.sleep(sleep_time)

    except KeyboardInterrupt: print("\nStopping stream.")
    except Exception as e: print(f"\nAn unexpected error occurred: {e}"); import traceback; traceback.print_exc()
    finally:
        print("Signaling color sampler thread to stop...")
        stop_thread_flag = True
        color_thread.join(timeout=1.0)
        print("Turning off LEDs and closing resources.")
        sock.sendto(DRGB_HEADER + bytearray(MATRIX_WIDTH * MATRIX_HEIGHT * 3), (wled_ip_resolved, WLED_UDP_PORT))
        sock.close()
        cv2.destroyAllWindows()

if __name__ == '__main__':
    run_vu_meter()