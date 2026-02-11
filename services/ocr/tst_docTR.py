#!/usr/bin/env python3
"""
test_doctr_reconstruct.py
Usage:
    python test_doctr_reconstruct.py path/to/image.jpg
Outputs:
 - prints plain OCR text
 - saves structured JSON (ocr_output.json)
 - shows overlay visualization (words/blocks)
 - saves reconstructed page images reconstructed_page_0.png, ...
"""

import sys
import json
import time
import matplotlib.pyplot as plt
import torch
import logging
import warnings

from doctr.io import DocumentFile
from doctr.models import ocr_predictor

# Suppress font warnings from docTR
logging.getLogger().setLevel(logging.ERROR)
warnings.filterwarnings('ignore')

def main(img_path: str, save_json: str = "ocr_output.json"):
    t_total_start = time.perf_counter()
    
    # Detect device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[Device] Using: {device.type.upper()}")
    if device.type == "cuda":
        print(f"[Device] GPU: {torch.cuda.get_device_name(0)}")
        print(f"[Device] CUDA Version: {torch.version.cuda}")
    
    # 1) load model
    t_model_start = time.perf_counter()
    model = ocr_predictor(pretrained=True, assume_straight_pages=False)   # detection + recognition
    
    # Only move to GPU, don't use .half() as it can cause detection issues
    if device.type == "cuda":
        model.to(device)
        print(f"[Device] Model loaded on GPU (FP32)")
    t_model_end = time.perf_counter()
    print(f"[Performance] Model loading: {t_model_end - t_model_start:.3f}s")

    # 2) load input image (single image or list)
    t_doc_start = time.perf_counter()
    doc_in = DocumentFile.from_images(img_path)
    t_doc_end = time.perf_counter()
    print(f"[Performance] Document loading: {t_doc_end - t_doc_start:.3f}s")

    # 3) run inference -> Document-like result
    if device.type == "cuda":
        torch.cuda.synchronize()
    t_inf_start = time.perf_counter()
    result = model(doc_in)
    if device.type == "cuda":
        torch.cuda.synchronize()
    t_inf_end = time.perf_counter()
    print(f"[Performance] OCR inference: {t_inf_end - t_inf_start:.3f}s")
    
    # Log GPU memory if available
    if torch.cuda.is_available():
        vram_used = torch.cuda.memory_allocated() / 1024**2
        print(f"[Device] VRAM used: {vram_used:.2f} MB")

    # 4) plain text
    t_render_start = time.perf_counter()
    plain_text = result.render()
    t_render_end = time.perf_counter()
    print(f"[Performance] Text rendering: {t_render_end - t_render_start:.3f}s")
    
    print("\n=== Plain text output ===\n")
    print(plain_text)

    # 5) structured JSON export
    t_json_start = time.perf_counter()
    json_out = result.export()
    t_json_end = time.perf_counter()
    print(f"[Performance] JSON export: {t_json_end - t_json_start:.3f}s")
    
    # Convert numpy arrays to lists for JSON serialization
    try:
        def convert_to_serializable(obj):
            if isinstance(obj, dict):
                return {k: convert_to_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_to_serializable(item) for item in obj]
            elif hasattr(obj, 'tolist'):  # numpy array
                return obj.tolist()
            else:
                return obj
        
        json_out_serializable = convert_to_serializable(json_out)
        
        with open(save_json, "w", encoding="utf-8") as f:
            json.dump(json_out_serializable, f, ensure_ascii=False, indent=2)
        print(f"\nStructured JSON saved to: {save_json}")
    except Exception as e:
        print(f"Warning: Could not save JSON: {e}")

    # 6) overlay visualization (boxes). This will open an interactive matplotlib window
    #    requires matplotlib & mplcursors (installed with "python-doctr[viz]").
    try:
        result.show(interactive=False)   # set interactive=True for interactive cursor
    except Exception as e:
        print("Warning: couldn't call result.show();", e)

    # 7) synthesize / reconstruct pages from predictions
    try:
        t_synth_start = time.perf_counter()
        synthesized_pages = result.synthesize()
        t_synth_end = time.perf_counter()
        print(f"[Performance] Page synthesis: {t_synth_end - t_synth_start:.3f}s")
        
        # Display synthesized pages
        for i, synth in enumerate(synthesized_pages):
            plt.imshow(synth)
            plt.axis('off')
            plt.title(f"Synthesized Page {i}")
            
            # Save the synthesized page
            out_name = f"reconstructed_page_{i}.png"
            plt.savefig(out_name, bbox_inches="tight", dpi=150)
            print(f"Saved synthesized page -> {out_name}")
            plt.show()
    except Exception as e:
        print(f"Synthesis failed: {e}")
    
    # Clean up GPU memory
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    
    t_total_end = time.perf_counter()
    print(f"\n[Performance] Total execution time: {t_total_end - t_total_start:.3f}s")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_doctr_reconstruct.py path/to/image.jpg")
        sys.exit(1)
    main(sys.argv[1])
