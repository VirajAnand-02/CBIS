import tensorflow as tf
import numpy as np
import os

# --- Configuration (Must match your training script) ---
MODEL_PATH = "image_attribute_router.keras"
IMG_SIZE = (224, 224)
# Define the attributes in the exact same order they were trained on

ATTRIBUTES = ["is_document", "has_people", "is_screenshot", "is_animal"]



def get_prediction_vector(model, image_path, img_size=(224, 224)):
    """
    Loads an image, preprocesses it, and returns the model's raw prediction vector.
    """
    try:
        img = tf.keras.utils.load_img(image_path, target_size=img_size)
        img_array = tf.keras.utils.img_to_array(img)
        img_array /= 255.0
        img_batch = np.expand_dims(img_array, axis=0)
        prediction_batch = model.predict(img_batch, verbose=0) # verbose=0 for cleaner output
        return prediction_batch[0]
    except Exception as e:
        print(f"Error processing image {image_path}: {e}")
        return None


# --- Main execution block ---
if __name__ == '__main__':
    # 1. Load the model (do this only once)
    print(f"Loading model from {MODEL_PATH}...")
    if not os.path.exists(MODEL_PATH):
        print("FATAL: Model file not found. Please run the training script first.")
        exit()
    
    # Load the trained Keras model
    trained_model = tf.keras.models.load_model(MODEL_PATH)
    print("✅ Model loaded successfully.")

    # 2. Provide the path to the image you want to test
    # IMPORTANT: Replace this with a valid path to an image on your machine!
    # For example: test_image_path = "path/to/my/test_document.png"
    test_image_path = "C:\\Users\\neelk\\Downloads\\accepted_ticket.png" # <--- CHANGE THIS

    if not os.path.exists(test_image_path):
        print(f"\nERROR: Test image not found at '{test_image_path}'.")
        print("Please update the 'test_image_path' variable with a valid file path.")
    else:
        # 3. Call the function to get the prediction vector
        print(f"\nGetting prediction for: {test_image_path}")
        prediction_vector = get_prediction_vector(trained_model, test_image_path, IMG_SIZE)

        # 4. Print and interpret the results
        if prediction_vector is not None:
            print("\n--- Raw Prediction Vector ---")
            print(prediction_vector)

            print("\n--- Interpreted Probabilities ---")
            for attribute, probability in zip(ATTRIBUTES, prediction_vector):
                print(f"{attribute:>20}: {probability:.4f}")

