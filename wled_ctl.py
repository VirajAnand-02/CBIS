import os
import json
import time
import socket
import threading
from tkinter import (
    Tk, Frame, Label, Entry, Button, Radiobutton, Scale, Canvas, Listbox, Scrollbar,
    StringVar, IntVar, DoubleVar, BooleanVar, Toplevel, filedialog, colorchooser, messagebox
)
from tkinter import ttk

import cv2
import mss
import numpy as np
import requests
from PIL import Image, ImageTk, ImageFilter

# --- Helper Functions (Color, etc.) - Unchanged ---
def apply_contrast(rgb_tuple, factor):
    r, g, b = rgb_tuple
    r, g, b = factor * (r - 128) + 128, factor * (g - 128) + 128, factor * (b - 128) + 128
    return int(max(0, min(255, r))), int(max(0, min(255, g))), int(max(0, min(255, b)))

def apply_saturation(rgb_tuple, factor):
    r, g, b = rgb_tuple
    r /= 255.0; g /= 255.0; b /= 255.0
    cmax, cmin = max(r, g, b), min(r, g, b)
    diff = cmax - cmin
    if cmax == 0: s = 0
    else: s = diff / cmax
    s = max(0.0, min(1.0, s * factor))
    h = 0
    if diff != 0:
        if cmax == r: h = (60 * ((g - b) / diff) + 360) % 360
        elif cmax == g: h = (60 * ((b - r) / diff) + 120) % 360
        else: h = (60 * ((r - g) / diff) + 240) % 360
    h /= 360.0
    v = cmax
    if s == 0.0: r,g,b = v,v,v
    else:
        i = int(h * 6.0); f = (h * 6.0) - i
        p, q, t = v * (1.0 - s), v * (1.0 - s * f), v * (1.0 - s * (1.0 - f))
        i %= 6
        if i == 0: r,g,b = v, t, p
        elif i == 1: r,g,b = q, v, p
        elif i == 2: r,g,b = p, v, t
        elif i == 3: r,g,b = p, q, v
        elif i == 4: r,g,b = t, p, v
        else: r,g,b = v, p, q
    return int(r * 255), int(g * 255), int(b * 255)

# --- Backend Controller Class ---
class WledController:
    def __init__(self, gui_callback):
        self.gui_callback = gui_callback
        self.config = {
            'ip': '',
            'segments': [], # New segment-based config
            'media_type': 'color', 'media_path': '', 'color_value': (0, 0, 255),
            'brightness': 128, 'contrast': 1.0, 'saturation': 1.0, 'blur': 0.0,
            'screen_x': 100, 'screen_y': 100, 'screen_w': 320, 'screen_h': 240
        }
        self.is_streaming = False
        self.stream_thread = None
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.wled_ip_resolved = None
        self.video_capture = None
        self.mss_instance = None
        self.DRGB_HEADER = bytearray([2, 2])

    def update_config(self, key, value):
        self.config[key] = value
        if key == 'ip': self.resolve_ip()

    def resolve_ip(self):
        try:
            self.wled_ip_resolved = socket.gethostbyname(self.config['ip'])
            return True
        except socket.gaierror:
            self.wled_ip_resolved = None
            return False

    def start_stream(self):
        if not self.wled_ip_resolved:
            self.gui_callback('status', "Error: Invalid WLED IP.")
            return False
        if not self.config['segments']:
            self.gui_callback('status', "Error: No segments configured.")
            return False
        if self.is_streaming: return True

        self.is_streaming = True
        self.stream_thread = threading.Thread(target=self._streaming_loop, daemon=True)
        self.stream_thread.start()
        self.gui_callback('status', f"Streaming to {self.wled_ip_resolved}")
        self.set_wled_brightness()
        return True

    def stop_stream(self):
        if not self.is_streaming: return
        self.is_streaming = False
        if self.stream_thread: self.stream_thread.join()
        self._send_blackout()
        self.gui_callback('status', "Stream stopped. LEDs off.")
        if self.video_capture:
            self.video_capture.release()
            self.video_capture = None
        if self.mss_instance: self.mss_instance = None

    def set_wled_brightness(self):
        if not self.wled_ip_resolved: return
        try:
            requests.post(f"http://{self.wled_ip_resolved}/json/state", json={"on": True, "bri": self.config['brightness']}, timeout=2)
        except requests.RequestException as e:
            self.gui_callback('status', f"Error setting brightness: {e}")

    def _get_total_leds(self):
        if not self.config['segments']: return 0
        return max(seg['end'] for seg in self.config['segments']) + 1

    def _send_blackout(self):
        if not self.wled_ip_resolved: return
        num_leds = self._get_total_leds()
        if num_leds > 0:
            blackout_packet = self.DRGB_HEADER + bytearray(num_leds * 3)
            self.sock.sendto(blackout_packet, (self.wled_ip_resolved, 21324))

    def _streaming_loop(self):
        target_fps = 30
        frame_duration = 1.0 / target_fps
        if self.config['media_type'] == 'video':
            if os.path.exists(self.config['media_path']):
                self.video_capture = cv2.VideoCapture(self.config['media_path'])
        elif self.config['media_type'] == 'screen':
            self.mss_instance = mss.mss()

        while self.is_streaming:
            loop_start_time = time.monotonic()
            frame_np = self._get_frame_from_source()
            if frame_np is None:
                time.sleep(0.1)
                continue
            
            wled_data, preview_img = self._process_frame_for_segments(frame_np)
            
            packet = self.DRGB_HEADER + wled_data
            self.sock.sendto(packet, (self.wled_ip_resolved, 21324))
            self.gui_callback('preview', preview_img)

            elapsed = time.monotonic() - loop_start_time
            if (sleep_time := frame_duration - elapsed) > 0:
                time.sleep(sleep_time)
    
    def _get_frame_from_source(self) -> np.ndarray | None:
        media_type = self.config['media_type']
        
        if media_type == 'color':
            return np.full((16, 16, 3), self.config['color_value'], dtype=np.uint8)
        
        if media_type == 'image':
            try: return np.array(Image.open(self.config['media_path']).convert('RGB'))
            except Exception: return None

        if media_type == 'video' and self.video_capture:
            ret, frame = self.video_capture.read()
            if not ret:
                self.video_capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self.video_capture.read()
            if ret: return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        if media_type == 'screen' and self.mss_instance:
            monitor = {"top": self.config['screen_y'], "left": self.config['screen_x'], 
                       "width": self.config['screen_w'], "height": self.config['screen_h']}
            sct_img = self.mss_instance.grab(monitor)
            return np.array(Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX"))
            
        return None

    def _process_frame_for_segments(self, frame_np: np.ndarray) -> tuple[bytearray, Image.Image]:
        total_leds = self._get_total_leds()
        wled_data = bytearray(total_leds * 3)
        
        composite_preview = Image.new('RGB', (len(self.config['segments']) * 68, 64), (20, 20, 20))
        preview_x_offset = 2

        source_img = Image.fromarray(frame_np)

        for segment in self.config['segments']:
            # 1. Determine segment dimensions
            if segment['type'] == 'matrix':
                target_w, target_h = segment['width'], segment['height']
            else: # strip
                target_w, target_h = (segment['end'] - segment['start'] + 1), 1
            
            # 2. Resize source image to segment dimensions
            img_w, img_h = source_img.size
            scale = max(target_w / img_w, target_h / img_h)
            resized = source_img.resize((int(img_w * scale), int(img_h * scale)), Image.LANCZOS)
            left, top = (resized.width - target_w) / 2, (resized.height - target_h) / 2
            segment_img = resized.crop((left, top, left + target_w, top + target_h))

            # 3. Apply segment-specific transformations
            if segment.get('rotation', 0) != 0:
                segment_img = segment_img.rotate(segment['rotation'], expand=True)
                # After rotation, dimensions might change, so re-crop to target
                left, top = (segment_img.width - target_w) / 2, (segment_img.height - target_h) / 2
                segment_img = segment_img.crop((left, top, left + target_w, top + target_h))

            if self.config['blur'] > 0:
                segment_img = segment_img.filter(ImageFilter.GaussianBlur(radius=self.config['blur']))

            # 4. Extract pixel data
            preview_np = np.zeros((target_h, target_w, 3), dtype=np.uint8)
            for y in range(target_h):
                for x in range(target_w):
                    r, g, b = segment_img.getpixel((x, y))
                    
                    if self.config['contrast'] != 1.0: r, g, b = apply_contrast((r,g,b), self.config['contrast'])
                    if self.config['saturation'] != 1.0: r, g, b = apply_saturation((r,g,b), self.config['saturation'])
                    
                    preview_np[y, x] = [r, g, b]
                    
                    # Map to WLED index
                    if segment['type'] == 'matrix':
                        # Serpentine layout
                        if segment.get('serpentine', False) and (y % 2) != 0:
                            wled_x = (target_w - 1) - x
                        else: # Normal layout
                            wled_x = x
                        local_index = y * target_w + wled_x
                    else: # Strip
                        local_index = x
                    
                    global_index = segment['start'] + local_index
                    if global_index < total_leds:
                        wled_data[global_index*3 : global_index*3+3] = r, g, b

            # 5. Create and add to composite preview
            segment_preview = Image.fromarray(preview_np).resize((64, 64), Image.NEAREST)
            composite_preview.paste(segment_preview, (preview_x_offset, 0))
            preview_x_offset += 68

        return wled_data, composite_preview

# --- GUI Dialog for Segment Configuration ---
class SegmentDialog(Toplevel):
    def __init__(self, parent, segment=None):
        super().__init__(parent)
        self.transient(parent)
        self.title("Add/Edit Segment")
        self.parent = parent
        self.result = None
        
        # --- Variables ---
        self.name_var = StringVar()
        self.start_var = IntVar()
        self.end_var = IntVar()
        self.type_var = StringVar(value='matrix')
        self.width_var = IntVar()
        self.height_var = IntVar()
        self.rotation_var = IntVar(value=0)
        self.serpentine_var = BooleanVar(value=True)

        if segment: # Populate with existing data if editing
            self.name_var.set(segment.get('name', ''))
            self.start_var.set(segment.get('start', 0))
            self.end_var.set(segment.get('end', 255))
            self.type_var.set(segment.get('type', 'matrix'))
            self.width_var.set(segment.get('width', 16))
            self.height_var.set(segment.get('height', 16))
            self.rotation_var.set(segment.get('rotation', 0))
            self.serpentine_var.set(segment.get('serpentine', True))

        # --- Widgets ---
        frame = ttk.Frame(self, padding="10")
        frame.pack(expand=True, fill='both')

        # Grid layout
        ttk.Label(frame, text="Name:").grid(row=0, column=0, sticky='w', pady=2)
        ttk.Entry(frame, textvariable=self.name_var).grid(row=0, column=1, sticky='ew')
        
        ttk.Label(frame, text="Start LED:").grid(row=1, column=0, sticky='w', pady=2)
        ttk.Entry(frame, textvariable=self.start_var).grid(row=1, column=1, sticky='ew')
        
        ttk.Label(frame, text="End LED:").grid(row=2, column=0, sticky='w', pady=2)
        ttk.Entry(frame, textvariable=self.end_var).grid(row=2, column=1, sticky='ew')

        ttk.Separator(frame, orient='horizontal').grid(row=3, columnspan=2, sticky='ew', pady=10)

        # Type selection
        type_frame = ttk.Frame(frame)
        type_frame.grid(row=4, columnspan=2, sticky='w')
        ttk.Radiobutton(type_frame, text="Matrix", variable=self.type_var, value='matrix', command=self.update_ui_state).pack(side='left', padx=5)
        ttk.Radiobutton(type_frame, text="Strip", variable=self.type_var, value='strip', command=self.update_ui_state).pack(side='left', padx=5)
        
        # Matrix-specific settings
        self.matrix_frame = ttk.LabelFrame(frame, text="Matrix Options", padding=10)
        self.matrix_frame.grid(row=5, columnspan=2, sticky='ew', pady=5)
        
        ttk.Label(self.matrix_frame, text="Width:").grid(row=0, column=0, sticky='w')
        ttk.Entry(self.matrix_frame, textvariable=self.width_var, width=5).grid(row=0, column=1)
        ttk.Label(self.matrix_frame, text="Height:").grid(row=1, column=0, sticky='w')
        ttk.Entry(self.matrix_frame, textvariable=self.height_var, width=5).grid(row=1, column=1)
        
        ttk.Label(self.matrix_frame, text="Rotation:").grid(row=2, column=0, sticky='w')
        ttk.Combobox(self.matrix_frame, textvariable=self.rotation_var, values=[0, 90, 180, 270], width=4, state='readonly').grid(row=2, column=1)
        
        ttk.Checkbutton(self.matrix_frame, text="Serpentine Layout", variable=self.serpentine_var).grid(row=3, columnspan=2, sticky='w', pady=5)

        # Buttons
        button_frame = ttk.Frame(frame)
        button_frame.grid(row=6, columnspan=2, pady=10)
        ttk.Button(button_frame, text="OK", command=self.on_ok).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.destroy).pack(side='left', padx=5)

        self.update_ui_state()
        self.grab_set() # Modal
        self.wait_window(self)

    def update_ui_state(self, *_):
        is_matrix = self.type_var.get() == 'matrix'
        for widget in self.matrix_frame.winfo_children():
            widget.configure(state='normal' if is_matrix else 'disabled')

    def on_ok(self):
        start, end = self.start_var.get(), self.end_var.get()
        if start > end:
            messagebox.showerror("Validation Error", "Start LED must not be greater than End LED.", parent=self)
            return

        self.result = {
            "name": self.name_var.get(), "start": start, "end": end,
            "type": self.type_var.get()
        }
        if self.result['type'] == 'matrix':
            w, h = self.width_var.get(), self.height_var.get()
            if w * h != (end - start + 1):
                messagebox.showerror("Validation Error", "Width x Height must equal the total number of LEDs in the segment.", parent=self)
                return
            self.result.update({
                "width": w, "height": h, "rotation": self.rotation_var.get(),
                "serpentine": self.serpentine_var.get()
            })
        self.destroy()

# --- Main GUI Application Class ---
class WledControlApp:
    CONFIG_FILE = "wled_config.json"
    
    def __init__(self, root):
        # ... (rest of the __init__ is very similar to previous version) ...
        self.root = root
        self.root.title("WLED Universal Controller v2")
        self.controller = WledController(self._gui_callback)
        self.load_config()

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        style = ttk.Style()
        style.configure("TNotebook.Tab", padding=[10, 5], font=('Segoe UI', 10))
        
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(expand=True, fill='both', padx=10, pady=10)

        self.home_frame = ttk.Frame(self.notebook, padding=10)
        self.settings_frame = ttk.Frame(self.notebook, padding=10)
        
        self.notebook.add(self.home_frame, text='Home')
        self.notebook.add(self.settings_frame, text='Settings')
        
        self._init_vars()
        self._create_home_widgets()
        self._create_settings_widgets()
        
        self.screen_capture_overlay = None
        self.populate_ui_from_config()
        self.update_media_ui_state()

    def _init_vars(self):
        self.ip_var = StringVar()
        self.media_type_var = StringVar()
        self.media_path_var = StringVar()
        self.color_var_rgb = (0, 0, 255)
        self.brightness_var = IntVar()
        self.contrast_var = DoubleVar()
        self.saturation_var = DoubleVar()
        self.blur_var = DoubleVar()

    def _create_home_widgets(self):
        # This function is largely unchanged from the previous version
        left_frame = ttk.Frame(self.home_frame)
        left_frame.pack(side='left', fill='y', padx=(0, 10))
        
        control_frame = ttk.LabelFrame(left_frame, text="Controls", padding=10)
        control_frame.pack(fill='x', pady=5)
        self.start_button = ttk.Button(control_frame, text="Start Streaming", command=self.toggle_stream)
        self.start_button.pack(fill='x', pady=2)
        self.status_label = ttk.Label(control_frame, text="Disconnected", wraplength=180, justify='center')
        self.status_label.pack(fill='x', pady=5)
        
        media_frame = ttk.LabelFrame(left_frame, text="Media Source", padding=10)
        media_frame.pack(fill='x', pady=5)
        for text, val in [("Color", "color"), ("Image", "image"), ("Video", "video"), ("Screen", "screen")]:
            ttk.Radiobutton(media_frame, text=text, variable=self.media_type_var, value=val, command=self.update_media_ui_state).pack(anchor='w')
        self.color_button = ttk.Button(media_frame, text="Select Color", command=self.select_color)
        self.color_button.pack(fill='x', pady=(5,0))
        self.file_button = ttk.Button(media_frame, text="Select File...", command=self.select_file)
        self.file_button.pack(fill='x')
        self.screen_button = ttk.Button(media_frame, text="Position Screen Area", command=self.select_screen_area)
        self.screen_button.pack(fill='x')
        
        adj_frame = ttk.LabelFrame(left_frame, text="Adjustments", padding=10)
        adj_frame.pack(fill='x', pady=5)
        ttk.Label(adj_frame, text="Brightness").pack()
        Scale(adj_frame, from_=0, to=255, orient='horizontal', variable=self.brightness_var, command=lambda v: self.on_brightness_change()).pack(fill='x')
        ttk.Label(adj_frame, text="Contrast").pack()
        Scale(adj_frame, from_=0.1, to=3.0, resolution=0.1, orient='horizontal', variable=self.contrast_var, command=lambda v: self.on_adjustment_change()).pack(fill='x')
        ttk.Label(adj_frame, text="Saturation").pack()
        Scale(adj_frame, from_=0.0, to=3.0, resolution=0.1, orient='horizontal', variable=self.saturation_var, command=lambda v: self.on_adjustment_change()).pack(fill='x')
        ttk.Label(adj_frame, text="Blur").pack()
        Scale(adj_frame, from_=0.0, to=5.0, resolution=0.1, orient='horizontal', variable=self.blur_var, command=lambda v: self.on_adjustment_change()).pack(fill='x')

        right_frame = ttk.Frame(self.home_frame)
        right_frame.pack(side='right', expand=True, fill='both')
        preview_frame = ttk.LabelFrame(right_frame, text="Live Preview", padding=5)
        preview_frame.pack(expand=True, fill='both')
        self.preview_canvas = Canvas(preview_frame, bg='black', height=80)
        self.preview_canvas.pack(expand=True, fill='x')
        self.preview_image = None

    def _create_settings_widgets(self):
        # Completely new UI for settings
        conn_frame = ttk.LabelFrame(self.settings_frame, text="WLED Connection", padding=10)
        conn_frame.pack(fill='x', pady=5)
        ttk.Label(conn_frame, text="WLED IP/Hostname:").pack(anchor='w')
        ttk.Entry(conn_frame, textvariable=self.ip_var).pack(fill='x')

        seg_frame = ttk.LabelFrame(self.settings_frame, text="LED Segments", padding=10)
        seg_frame.pack(fill='both', expand=True, pady=5)

        # Listbox for segments
        list_frame = ttk.Frame(seg_frame)
        list_frame.pack(fill='both', expand=True)
        self.seg_listbox = Listbox(list_frame, height=6)
        self.seg_listbox.pack(side='left', fill='both', expand=True)
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.seg_listbox.yview)
        scrollbar.pack(side='right', fill='y')
        self.seg_listbox.config(yscrollcommand=scrollbar.set)

        # Buttons for segment management
        btn_frame = ttk.Frame(seg_frame)
        btn_frame.pack(fill='x', pady=(5,0))
        ttk.Button(btn_frame, text="Add", command=self.add_segment).pack(side='left')
        ttk.Button(btn_frame, text="Edit", command=self.edit_segment).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Remove", command=self.remove_segment).pack(side='left')

        ttk.Button(self.settings_frame, text="Save All Settings", command=self.save_and_apply_config).pack(pady=20)
    
    # --- UI Logic (mostly new for segments) ---
    def add_segment(self):
        dialog = SegmentDialog(self.root)
        if dialog.result:
            self.controller.config['segments'].append(dialog.result)
            self.update_segment_listbox()
    
    def edit_segment(self):
        selected = self.seg_listbox.curselection()
        if not selected: return
        idx = selected[0]
        
        dialog = SegmentDialog(self.root, self.controller.config['segments'][idx])
        if dialog.result:
            self.controller.config['segments'][idx] = dialog.result
            self.update_segment_listbox()

    def remove_segment(self):
        selected = self.seg_listbox.curselection()
        if not selected: return
        if messagebox.askyesno("Confirm", "Are you sure you want to remove the selected segment?"):
            # Iterate in reverse to safely delete from list
            for idx in sorted(selected, reverse=True):
                del self.controller.config['segments'][idx]
            self.update_segment_listbox()

    def update_segment_listbox(self):
        self.seg_listbox.delete(0, 'end')
        for i, seg in enumerate(self.controller.config.get('segments', [])):
            info = f"[{seg['start']}-{seg['end']}]"
            self.seg_listbox.insert('end', f"{i:02d}: {seg['name']} {info}")

    def select_screen_area(self):
        # Simplified screen area selection
        if self.screen_capture_overlay and self.screen_capture_overlay.winfo_exists():
            self.screen_capture_overlay.lift()
            return
        
        self.screen_capture_overlay = Toplevel(self.root)
        cfg = self.controller.config
        w, h, x, y = cfg['screen_w'], cfg['screen_h'], cfg['screen_x'], cfg['screen_y']
        
        self.screen_capture_overlay.geometry(f"{w}x{h}+{x}+{y}")
        self.screen_capture_overlay.attributes('-alpha', 0.5)
        self.screen_capture_overlay.attributes('-topmost', True)
        self.screen_capture_overlay.overrideredirect(True)
        
        label = Label(self.screen_capture_overlay, text="Drag to Move\nRight-click to Close", bg="blue", fg="white")
        label.pack(expand=True, fill='both')
        label.bind("<B1-Motion>", self._drag_overlay)
        label.bind("<Button-3>", lambda e: self.screen_capture_overlay.destroy())

    def _drag_overlay(self, event):
        overlay = self.screen_capture_overlay
        new_x = overlay.winfo_x() + event.x - (overlay.winfo_width() // 2)
        new_y = overlay.winfo_y() + event.y - (overlay.winfo_height() // 2)
        self.controller.update_config('screen_x', new_x)
        self.controller.update_config('screen_y', new_y)
        overlay.geometry(f"+{new_x}+{new_y}") # Move without resizing

    # --- Config Management (Updated for Segments) ---
    def save_and_apply_config(self):
        # ... (update controller from other vars)
        self.controller.update_config('ip', self.ip_var.get())
        self.controller.update_config('media_type', self.media_type_var.get())
        self.controller.update_config('media_path', self.media_path_var.get())
        self.controller.update_config('color_value', self.color_var_rgb)
        self.controller.update_config('brightness', self.brightness_var.get())
        self.controller.update_config('contrast', self.contrast_var.get())
        self.controller.update_config('saturation', self.saturation_var.get())
        self.controller.update_config('blur', self.blur_var.get())
        # Segments are already updated in the controller's config via the dialogs
        
        if self.controller.resolve_ip():
            self.status_label.config(text=f"Config saved. WLED at {self.controller.wled_ip_resolved}")
        else:
            self.status_label.config(text="Error: Could not resolve hostname.")
        self.save_config()

    def populate_ui_from_config(self):
        cfg = self.controller.config
        self.ip_var.set(cfg.get('ip', ''))
        self.media_type_var.set(cfg.get('media_type', 'color'))
        self.media_path_var.set(cfg.get('media_path', ''))
        self.color_var_rgb = tuple(cfg.get('color_value', (0,0,255)))
        self.brightness_var.set(cfg.get('brightness', 128))
        self.contrast_var.set(cfg.get('contrast', 1.0))
        self.saturation_var.set(cfg.get('saturation', 1.0))
        self.blur_var.set(cfg.get('blur', 0.0))
        self.update_segment_listbox() # Populate the listbox

    # --- All other methods are largely the same as previous version ---
    # (toggle_stream, on_brightness_change, on_adjustment_change, update_media_ui_state,
    #  select_color, select_file, save_config, load_config, on_closing, _gui_callback,
    # _update_preview_canvas, _update_status_label)
    
    # ... Pasting the remaining unchanged methods for completeness ...

    def toggle_stream(self):
        if self.controller.is_streaming:
            self.controller.stop_stream()
            self.start_button.config(text="Start Streaming")
        else:
            self.save_and_apply_config()
            if self.controller.start_stream():
                self.start_button.config(text="Stop Streaming")
    
    def on_brightness_change(self):
        self.controller.update_config('brightness', self.brightness_var.get())
        if self.controller.is_streaming:
            self.controller.set_wled_brightness()
    
    def on_adjustment_change(self):
        self.controller.update_config('contrast', self.contrast_var.get())
        self.controller.update_config('saturation', self.saturation_var.get())
        self.controller.update_config('blur', self.blur_var.get())

    def update_media_ui_state(self):
        media_type = self.media_type_var.get()
        self.color_button.config(state='normal' if media_type == 'color' else 'disabled')
        self.file_button.config(state='normal' if media_type in ['image', 'video'] else 'disabled')
        self.screen_button.config(state='normal' if media_type == 'screen' else 'disabled')

    def select_color(self):
        color_code = colorchooser.askcolor(title="Choose color")
        if color_code and color_code[0]: self.color_var_rgb = tuple(int(c) for c in color_code[0])

    def select_file(self):
        media_type = self.media_type_var.get()
        filetypes = [("Image files", "*.jpg *.jpeg *.png *.bmp"), ("All files", "*.*")] if media_type == 'image' else [("Video files", "*.mp4 *.avi *.mov"), ("All files", "*.*")]
        filepath = filedialog.askopenfilename(title=f"Select {media_type.capitalize()} File", filetypes=filetypes)
        if filepath:
            self.media_path_var.set(filepath)
            self.status_label.config(text=f"Ready: {os.path.basename(filepath)}")

    def save_config(self):
        with open(self.CONFIG_FILE, 'w') as f:
            json.dump(self.controller.config, f, indent=4)
            
    def load_config(self):
        try:
            with open(self.CONFIG_FILE, 'r') as f:
                self.controller.config.update(json.load(f))
        except (FileNotFoundError, json.JSONDecodeError): pass

    def on_closing(self):
        self.save_and_apply_config() # Save on close
        self.controller.stop_stream()
        self.root.destroy()

    def _gui_callback(self, type, data):
        if type == 'preview': self.root.after(0, self._update_preview_canvas, data)
        elif type == 'status': self.root.after(0, self._update_status_label, data)

    def _update_preview_canvas(self, pil_image: Image.Image):
        if not self.preview_canvas.winfo_exists(): return
        canvas_w = self.preview_canvas.winfo_width()
        canvas_h = self.preview_canvas.winfo_height()
        # Resize maintaining aspect ratio to fit canvas
        pil_image.thumbnail((canvas_w, canvas_h), Image.LANCZOS)
        self.preview_image = ImageTk.PhotoImage(pil_image)
        # Clear previous image and draw new one centered
        self.preview_canvas.delete("all")
        self.preview_canvas.create_image(canvas_w // 2, canvas_h // 2, anchor='center', image=self.preview_image)
        
    def _update_status_label(self, text: str):
        if not self.status_label.winfo_exists(): return
        self.status_label.config(text=text)


if __name__ == '__main__':
    root = Tk()
    app = WledControlApp(root)
    root.mainloop()