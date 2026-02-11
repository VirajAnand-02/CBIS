from deepface import DeepFace
import cv2
import matplotlib.pyplot as plt
import time
import torch
import tensorflow as tf

# Configure GPU for TensorFlow
def configure_gpu():
    """Configure GPU settings for TensorFlow and PyTorch"""
    print("\n=== GPU Configuration ===")
    
    # TensorFlow GPU check
    gpus = tf.config.list_physical_devices('GPU')
    if gpus:
        try:
            # Enable memory growth to prevent TF from allocating all GPU memory
            for gpu in gpus:
                tf.config.experimental.set_memory_growth(gpu, True)
            print(f"TensorFlow - GPU available: {len(gpus)} GPU(s)")
            print(f"TensorFlow - GPU devices: {[gpu.name for gpu in gpus]}")
        except RuntimeError as e:
            print(f"TensorFlow GPU configuration error: {e}")
    else:
        print("TensorFlow - No GPU detected, using CPU")
    
    # PyTorch GPU check
    if torch.cuda.is_available():
        print(f"PyTorch - CUDA available: {torch.cuda.get_device_name(0)}")
        print(f"PyTorch - CUDA version: {torch.version.cuda}")
    else:
        print("PyTorch - No CUDA detected, using CPU")
    
    print("=" * 40 + "\n")

# Call GPU configuration at startup
configure_gpu()

def verify_faces(img1_path, img2_path):
    """
    Compares two images using the ArcFace model to check if they are the same person.
    """
    print(f"Comparing {img1_path} and {img2_path}...")
    
    t_total_start = time.perf_counter()
    
    try:
        # The verify function performs face detection, alignment, and comparison
        t_verify_start = time.perf_counter()
        result = DeepFace.verify(
            img1_path=img1_path,
            img2_path=img2_path,
            model_name="ArcFace",
            detector_backend="retinaface",  # Options: 'opencv', 'retinaface', 'mtcnn', 'ssd'
            enforce_detection=False  # Set to False to handle images where face detection might fail
        )
        t_verify_end = time.perf_counter()
        
        # Display results
        print("\n--- Result ---")
        print(f"Verified: {result['verified']}")
        print(f"Distance: {result['distance']:.4f}")
        print(f"Threshold: {result['threshold']}")
        print(f"Model: {result['model']}")
        print(f"\n[Performance] Verification time: {t_verify_end - t_verify_start:.3f}s")
        print(f"[Performance] Total time: {time.perf_counter() - t_total_start:.3f}s")
        
        # GPU memory usage if available
        if torch.cuda.is_available():
            vram_used = torch.cuda.memory_allocated() / 1024**2
            print(f"[GPU] VRAM used: {vram_used:.2f} MB")
        
        # Optional: specific logic based on result
        if result['verified']:
            print("✅ These images are of the SAME person.")
        else:
            print("❌ These images are of DIFFERENT people.")
            
        return result

    except Exception as e:
        print(f"Error during verification: {e}")
        return None

def get_embedding(img_path):
    """
    Generates the 512-dimensional vector (embedding) for a face using ArcFace.
    """
    t_total_start = time.perf_counter()
    
    try:
        t_embed_start = time.perf_counter()
        embedding_objs = DeepFace.represent(
            img_path=img_path,
            model_name="ArcFace",
            detector_backend="retinaface",
            enforce_detection=False  # Set to False to handle images where face detection might fail
        )
        t_embed_end = time.perf_counter()
        
        # deepface returns a list (in case multiple faces are detected)
        embedding = embedding_objs[0]["embedding"]
        print(f"\nGenerated embedding for {img_path}:")
        print(f"Vector length: {len(embedding)}")
        print(f"First 5 values: {embedding[:5]}...")
        print(f"\n[Performance] Embedding generation time: {t_embed_end - t_embed_start:.3f}s")
        print(f"[Performance] Total time: {time.perf_counter() - t_total_start:.3f}s")
        
        # GPU memory usage if available
        if torch.cuda.is_available():
            vram_used = torch.cuda.memory_allocated() / 1024**2
            print(f"[GPU] VRAM used: {vram_used:.2f} MB")
        
        return embedding
    except Exception as e:
        print(f"Error generating embedding: {e}")
        return None

# --- Main Execution ---
if __name__ == "__main__":
    # Set paths to your actual images
    img1_path = "./photu/r1.jpg"
    img2_path = "./photu/r2.jpg"

    # 1. Run Verification
    verify_faces(img1_path, img2_path)

    # 2. Get Embeddings
    get_embedding(img1_path)
    
    # Clean up GPU memory
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        print("\n[GPU] Cache cleared")