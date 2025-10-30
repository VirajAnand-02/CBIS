import torch
from doctr.io import DocumentFile
from doctr.models import ocr_predictor
import cv2
import numpy as np
import os
from PIL import Image
import time

# pip install python-doctr[torch] opencv-python
# conda install pytorch torchvision torchaudio pytorch-cuda=11.8 -c pytorch -c nvidia -y

predictor = ocr_predictor(det_arch='db_resnet50', reco_arch='master', pretrained=True)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
predictor.to(device)  # Not all parts need .to(device), but for compatibility

def preprocess_image(image_path, apply_enhancements=False):
    """
    Optional minimal preprocessing (no resizing) for noisy images.
    
    Args:
        image_path (str): Path to image.
        apply_enhancements (bool): If True, apply denoising/sharpening.
    
    Returns:
        np.ndarray: Preprocessed image array (full res).
    """
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Image not found: {image_path}")
    
    if apply_enhancements:
        # Denoising (minimal to preserve details)
        img = cv2.fastNlMeansDenoisingColored(img, h=10)
        # Sharpening
        kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
        img = cv2.filter2D(img, -1, kernel)
    
    return img

def extract_text(image_path, apply_enhancements=False):
    """
    Extract text from full-res image using docTR.
    
    Args:
        image_path (str): Path to image.
        apply_enhancements (bool): Optional enhancements for noisy images.
    
    Returns:
        Tuple[str, dict]: (Combined recognized text, timings)
    """
    t_total_start = time.perf_counter()

    # Load document
    t_doc_start = time.perf_counter()
    doc = DocumentFile.from_images([image_path])
    t_doc_end = time.perf_counter()

    # OCR inference
    if device.type == "cuda":
        torch.cuda.synchronize()
    t_inf_start = time.perf_counter()
    result = predictor(doc)
    if device.type == "cuda":
        torch.cuda.synchronize()
    t_inf_end = time.perf_counter()

    # Aggregate text
    t_agg_start = time.perf_counter()
    full_text = ""
    for page in result.pages:
        for block in page.blocks:
            for line in block.lines:
                for word in line.words:
                    full_text += word.value + " "
                full_text += "\n"
    full_text = full_text.strip() if full_text else "No text detected"
    t_agg_end = time.perf_counter()

    timings = {
        "doc_load_s": t_doc_end - t_doc_start,
        "inference_s": t_inf_end - t_inf_start,
        "aggregation_s": t_agg_end - t_agg_start,
        "total_s": time.perf_counter() - t_total_start,
    }

    return full_text, timings

def extract_features(image_path, is_document=True, apply_enhancements=False):
    """
    Modified extract_features for your project, using docTR for full-res OCR.
    
    Args:
        image_path (str): Path to image.
        is_document (bool): Kept for compatibility.
        apply_enhancements (bool): Optional for noisy images.
    
    Returns:
        dict: Features including OCR text and timings.
    """
    features = {}
    text, timings = extract_text(image_path, apply_enhancements)
    features['ocr_text'] = text
    features['ocr_timings'] = timings
    # Add other features (e.g., CLIP embeddings, BLIP captions, YOLO objects) as needed
    return features

# Example Usage: Process a folder of images
if __name__ == "__main__":
    image_folder = "images/"
    sample_images = [
        "ocrtst-2.jpg",      # Printed text sample
    ]
    
    for image_name in sample_images:
        image_path = os.path.join(image_folder, image_name)
        try:
            features = extract_features(image_path, apply_enhancements=True)
            print(f"\nImage: {image_name}")
            print("Recognized Text:", features['ocr_text'])
            t = features.get('ocr_timings', {})
            print(f"Doc load time: {t.get('doc_load_s', 0):.3f}s")
            print(f"Inference time: {t.get('inference_s', 0):.3f}s")
            print(f"Aggregation time: {t.get('aggregation_s', 0):.3f}s")
            print(f"Total time: {t.get('total_s', 0):.3f}s")
            # Log VRAM if GPU
            if torch.cuda.is_available():
                print(f"VRAM used: {torch.cuda.memory_allocated() / 1024**2:.2f} MB")
        except Exception as e:
            print(f"Error processing {image_name}: {e}")
    
    # Clean up VRAM
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

