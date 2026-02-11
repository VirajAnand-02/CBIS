import tensorflow as tf
import numpy as np
from PIL import Image

# --- Configuration ---
KERAS_MODEL_PATH = "image_attribute_router.keras"
IMG_SIZE = (224, 224)
PREDICTION_THRESHOLD = 0.5  # Confidence threshold for an attribute being "present"

# --- Load the Keras model and its metadata ---
print(f"Loading model from {KERAS_MODEL_PATH}...")
model = tf.keras.models.load_model(KERAS_MODEL_PATH)

# Try to load attributes from the model file itself for better portability
try:
    ATTRIBUTES = model.config.attributes
    print("Successfully loaded attributes from model file.")
except AttributeError:
    print("Warning: Could not load attributes from model file.")
    print("Falling back to separate import. Ensure 'dataset_DL.cfg_file' is available.")
    # This is the fallback if the model was saved without the attribute list
    from dataset_DL.cfg_file import ATTRIBUTES


def preprocess_image(image_path: str) -> np.ndarray:
    """Load an image file into a normalized batch tensor."""
    img = Image.open(image_path).convert('RGB')
    img = img.resize(IMG_SIZE)
    arr = np.asarray(img, dtype=np.float32) / 255.0
    return np.expand_dims(arr, axis=0)  # Shape: (1, H, W, 3)

def classify_image_attributes(image_path: str) -> dict:
    """
    Runs a forward pass on the model and returns a dictionary mapping
    attribute names to booleans.
    """
    batch = preprocess_image(image_path)
    # model.predict returns a batch of predictions, we take the first and only one.
    preds = model.predict(batch)[0]  # Shape: (NUM_ATTRIBUTES,)

    return {
        attr: (preds[i] > PREDICTION_THRESHOLD)
        for i, attr in enumerate(ATTRIBUTES)
    }

# --- Example Usage ---
if __name__ == "__main__":
    # Update this path to an image you want to test
    image_to_test = "dataset_DL\\has_people\\000000065736.jpg" 
    
    try:
        attrs = classify_image_attributes(image_to_test)

        print(f"\nAttributes for {image_to_test}:")
        for k, v in attrs.items():
            print(f"  - {k}: {'✓ Present' if v else '✗ Absent'}")

        # Example of simple routing logic based on predictions
        print("\nRouting logic:")
        if attrs.get('is_document'):
            print("  -> Routing to Document Processing Module...")
        elif attrs.get('has_faces'):
            print("  -> Routing to Face Recognition Module...")
        else:
            print("  -> Routing to General Processing Module...")

    except FileNotFoundError:
        print(f"Error: The image file was not found at '{image_to_test}'")
    except Exception as e:
        print(f"An error occurred: {e}")