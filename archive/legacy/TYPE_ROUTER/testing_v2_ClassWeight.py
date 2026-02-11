# test_model.py

import os
import argparse
import pandas as pd
import tensorflow as tf
import matplotlib.pyplot as plt
import numpy as np
import time
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from tensorflow.keras.preprocessing.image import ImageDataGenerator

# --- CUSTOM LOSS FUNCTION ---
def create_weighted_binary_crossentropy(class_weights):
    def weighted_binary_crossentropy(y_true, y_pred):
        y_true = tf.cast(y_true, tf.float32)
        num_attributes = y_pred.shape[-1]
        if not class_weights:
            weights_for_1 = tf.ones(num_attributes, dtype=tf.float32)
            weights_for_0 = tf.ones(num_attributes, dtype=tf.float32)
        else:
            weights_for_1 = tf.constant([class_weights.get(i, {}).get(1, 1.0) for i in range(num_attributes)], dtype=tf.float32)
            weights_for_0 = tf.constant([class_weights.get(i, {}).get(0, 1.0) for i in range(num_attributes)], dtype=tf.float32)
        bce = tf.keras.backend.binary_crossentropy(y_true, y_pred)
        weight_mask = y_true * weights_for_1 + (1. - y_true) * weights_for_0
        weighted_bce = weight_mask * bce
        return tf.keras.backend.mean(weighted_bce)
    return weighted_binary_crossentropy


# --- load_test_data ---
def load_test_data(labels_csv, image_dir, target_attributes, img_size, batch_size):
    print("\n--- Loading Test Data ---")
    try:
        df = pd.read_csv(labels_csv)
    except FileNotFoundError:
        print(f"ERROR: Labels file not found at '{labels_csv}'.")
        return None, None
    _, val_df = train_test_split(df, test_size=0.2, random_state=42)
    test_datagen = ImageDataGenerator(rescale=1./255)
    test_generator = test_datagen.flow_from_dataframe(dataframe=val_df, directory=image_dir, x_col='image_filename', y_col=target_attributes, batch_size=batch_size, seed=42, shuffle=False, class_mode="raw", target_size=img_size)
    print(f"✅ Test generator created with {test_generator.n} images.")
    return test_generator, val_df



def evaluate_model(model, test_generator, val_df, target_attributes):
    """
    Performs quantitative evaluation, including timing, and prints reports.
    """
    print("\n--- Quantitative Evaluation ---")

    # 1. Overall Performance Metrics from Keras
    print("\n--- Overall Model Performance ---")
    results = model.evaluate(test_generator, verbose=1)
    for name, value in zip(model.metrics_names, results):
        print(f"{name}: {value:.4f}")

    # Get the raw prediction probabilities once and time it
    y_true = val_df[target_attributes].values
    num_samples = test_generator.n
    
    print("\n--- Inference Timing ---")
    start_time = time.time()
    y_pred_probs = model.predict(test_generator, verbose=1)
    end_time = time.time()
    
    total_time = end_time - start_time
    avg_time_per_image = total_time / num_samples
    
    print(f"Time to predict on {num_samples} images: {total_time:.4f} seconds")
    print(f"Average inference time per image: {avg_time_per_image * 1000:.4f} ms")


    # 2. Per-Attribute Report with default 0.5 threshold
    print("\n--- Per-Attribute Report (Default 0.5 Threshold) ---")
    y_pred_default = (y_pred_probs > 0.5).astype(int)
    report_default = classification_report(y_true[:num_samples], y_pred_default[:num_samples], target_names=target_attributes, zero_division=0)
    print(report_default)

    # 3. Per-Attribute Report with CUSTOM thresholds
    print("\n--- Per-Attribute Report (Custom Thresholds) ---")
    CUSTOM_THRESHOLDS = {'is_animal': 0.90}
    y_pred_custom = np.zeros_like(y_pred_probs)
    for i, attr in enumerate(target_attributes):
        threshold = CUSTOM_THRESHOLDS.get(attr, 0.5)
        y_pred_custom[:, i] = (y_pred_probs[:, i] > threshold).astype(int)
        print(f"Using threshold {threshold:.2f} for '{attr}'")
    report_custom = classification_report(y_true[:num_samples], y_pred_custom[:num_samples], target_names=target_attributes, zero_division=0)
    print(report_custom)

    return y_pred_probs, CUSTOM_THRESHOLDS


def visualize_predictions(test_generator, y_pred_probs, target_attributes, custom_thresholds, num_samples=10):
    # ... (function is the same as before) ...
    print("\n--- Qualitative Visualization (using Custom Thresholds) ---")
    plt.style.use('seaborn-v0_8-whitegrid')
    test_generator.reset()
    test_images, test_labels = next(test_generator)
    predictions_batch = y_pred_probs[:len(test_images)]
    num_to_show = min(num_samples, len(test_images))
    fig, axes = plt.subplots(num_to_show, 1, figsize=(15, 5 * num_to_show))
    if num_to_show == 1: axes = [axes]
    fig.suptitle('Sample Predictions vs. True Labels (Correctness based on Custom Thresholds)', fontsize=20)
    for i in range(num_to_show):
        ax = axes[i]
        ax.imshow(test_images[i])
        ax.axis('off')
        title_str = ""
        for j, attr in enumerate(target_attributes):
            pred_prob = predictions_batch[i][j]
            true_label = int(test_labels[i][j])
            threshold = custom_thresholds.get(attr, 0.5)
            pred_class = 1 if pred_prob >= threshold else 0
            match_str = "✓" if pred_class == true_label else "✗"
            title_str += f"{attr:>20}: {pred_prob:.2f} (True: {true_label}) {match_str}\n"
        ax.text(1.02, 0.5, title_str.strip(), transform=ax.transAxes, fontsize=12, verticalalignment='center', fontfamily='monospace')
    plt.tight_layout(rect=[0, 0, 0.75, 0.97])
    plt.savefig("test_predictions_report_custom_thresholds.png")
    print("\n✅ Qualitative prediction report saved to 'test_predictions_report_custom_thresholds.png'")
    plt.show()


def main(args):
    """
    Main function to orchestrate the model testing pipeline.
    """
    # --- DYNAMICALLY DISCOVER ATTRIBUTES ---
    # ... (Unchanged) ...
    print("\n--- Dynamically discovering attributes from CSV ---")
    try:
        df = pd.read_csv(args.labels_csv)
        attributes = [col for col in df.columns if col != 'image_filename']
        print(f"✅ Found {len(attributes)} attributes: {attributes}")
    except (FileNotFoundError, KeyError) as e:
        print(f"Error discovering attributes: {e}. Please check your CSV file."); return

    # --- LOAD MODEL ---
    # <<< MODIFICATION IS HERE >>>
    print("\n--- Loading Trained Model ---")
    if not os.path.exists(args.model_path):
        print(f"FATAL: Model file not found at '{args.model_path}'."); return
        
    custom_objects = {}
    if args.was_trained_with_weights:
        print("Model was trained with custom weighted loss. Preparing custom objects for loading...")
        custom_objects = {'weighted_binary_crossentropy': create_weighted_binary_crossentropy({})}
    
    start_time_load = time.time()
    try:
        model = tf.keras.models.load_model(args.model_path, custom_objects=custom_objects)
        end_time_load = time.time()
        print(f"✅ Model loaded successfully in {end_time_load - start_time_load:.4f} seconds.")
    except Exception as e:
        print(f"FATAL: Error loading model. Error: {e}"); return

    # --- LOAD DATA ---
    img_size = (args.img_size, args.img_size)
    test_generator, val_df = load_test_data(args.labels_csv, args.image_dir, attributes, img_size, args.batch_size)
    if not test_generator: return

    # --- EVALUATE & VISUALIZE ---
    predictions, custom_thresholds = evaluate_model(model, test_generator, val_df, attributes)
    visualize_predictions(test_generator, predictions, attributes, custom_thresholds, num_samples=args.num_visual_samples)
    
    print("\n--- Test script finished. ---")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Test a trained multi-label image classifier.")
    parser.add_argument('--labels_csv', type=str, default='compiled_labels.csv', help='Path to the labels CSV file.')
    parser.add_argument('--image_dir', type=str, default='compiled_images', help='Path to the directory containing images.')
    parser.add_argument('--model_path', type=str, default='image_attribute_model.keras', help='Path to the trained .keras model file.')
    parser.add_argument('--img_size', type=int, default=224, help='Image size (width and height).')
    parser.add_argument('--batch_size', type=int, default=32, help='Testing batch size.')
    parser.add_argument('--was_trained_with_weights', action='store_true', help='Flag to indicate that the model was trained with the custom weighted loss function.')
    parser.add_argument('--num_visual_samples', type=int, default=4, help='Number of sample images to visualize with their predictions.') # Added argument
    
    args = parser.parse_args()
    main(args)