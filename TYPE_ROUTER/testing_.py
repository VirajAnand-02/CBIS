# test_model.py

import os
import argparse
import pandas as pd
import tensorflow as tf
import matplotlib.pyplot as plt
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from tensorflow.keras.preprocessing.image import ImageDataGenerator

def load_test_data(labels_csv, image_dir, target_attributes, img_size, batch_size):
    """
    Loads and prepares the test data generator from the validation split.
    """
    print("\n--- Loading Test Data ---")
    try:
        df = pd.read_csv(labels_csv)
    except FileNotFoundError:
        print(f"ERROR: Labels file not found at '{labels_csv}'.")
        return None, None

    # Replicate the exact same validation split used during training
    _, val_df = train_test_split(df, test_size=0.2, random_state=42)

    test_datagen = ImageDataGenerator(rescale=1./255)

    test_generator = test_datagen.flow_from_dataframe(
        dataframe=val_df,
        directory=image_dir,
        x_col='image_filename',
        y_col=target_attributes,
        batch_size=batch_size,
        seed=42,
        shuffle=False,  # CRUCIAL: Must be False for evaluation
        class_mode="raw",
        target_size=img_size
    )
    print(f"✅ Test generator created with {test_generator.n} images.")
    return test_generator, val_df


def evaluate_model(model, test_generator, val_df, target_attributes):
    """
    Performs quantitative evaluation and prints reports.
    """
    print("\n--- Quantitative Evaluation ---")

    # 1. Overall Performance Metrics from Keras
    print("\n--- Overall Model Performance ---")
    results = model.evaluate(test_generator, verbose=1)
    for name, value in zip(model.metrics_names, results):
        print(f"{name}: {value:.4f}")

    # 2. Per-Attribute Classification Report from Scikit-learn
    print("\n--- Per-Attribute Classification Report ---")
    y_pred_probs = model.predict(test_generator, verbose=1)
    y_pred = (y_pred_probs > 0.5).astype(int)
    y_true = val_df[target_attributes].values

    # Ensure y_true and y_pred have the same number of samples
    num_samples = min(len(y_true), len(y_pred))
    report = classification_report(
        y_true[:num_samples],
        y_pred[:num_samples],
        target_names=target_attributes,
        zero_division=0
    )
    print(report)
    return y_pred_probs


def visualize_predictions(test_generator, y_pred_probs, target_attributes, num_samples=10):
    """
    Visualizes predictions on a sample of test images.
    """
    print("\n--- Qualitative Visualization ---")
    plt.style.use('seaborn-v0_8-whitegrid')
    
    # Reset the generator and get a batch of data
    test_generator.reset()
    test_images, test_labels = next(test_generator)
    predictions_batch = y_pred_probs[:len(test_images)]

    num_to_show = min(num_samples, len(test_images))

    fig, axes = plt.subplots(num_to_show, 1, figsize=(15, 5 * num_to_show))
    if num_to_show == 1: # Matplotlib returns a single axes object if nrows=1
        axes = [axes]
    fig.suptitle('Sample Predictions vs. True Labels', fontsize=20)

    for i in range(num_to_show):
        ax = axes[i]
        ax.imshow(test_images[i])
        ax.axis('off')

        title_str = ""
        for j, attr in enumerate(target_attributes):
            pred_prob = predictions_batch[i][j]
            true_label = int(test_labels[i][j])
            pred_class = 1 if pred_prob >= 0.5 else 0
            
            match_str = "✓" if pred_class == true_label else "✗"
            title_str += f"{attr:>20}: {pred_prob:.2f} (True: {true_label}) {match_str}\n"

        # Correctly place the text annotation outside the plot area
        ax.text(1.02, 0.5, title_str.strip(),
                transform=ax.transAxes,
                fontsize=12,
                verticalalignment='center',
                fontfamily='monospace')

    plt.tight_layout(rect=[0, 0, 0.75, 0.97]) # Adjust layout to make space for text
    plt.savefig("test_predictions_report.png")
    print("\n✅ Qualitative prediction report saved to 'test_predictions_report.png'")
    plt.show()


def main(args):
    """
    Main function to orchestrate the model testing pipeline.
    """
    # --- DYNAMICALLY DISCOVER ATTRIBUTES ---
    print("\n--- Dynamically discovering attributes from CSV ---")
    try:
        df = pd.read_csv(args.labels_csv)
        attributes = [col for col in df.columns if col != 'image_filename']
        print(f"✅ Found {len(attributes)} attributes: {attributes}")
    except (FileNotFoundError, KeyError) as e:
        print(f"Error discovering attributes: {e}. Please check your CSV file.")
        return

    # --- LOAD MODEL ---
    print("\n--- Loading Trained Model ---")
    if not os.path.exists(args.model_path):
        print(f"FATAL: Model file not found at '{args.model_path}'.")
        return
    try:
        model = tf.keras.models.load_model(args.model_path)
        print("✅ Model loaded successfully.")
    except Exception as e:
        print(f"FATAL: Error loading model. The file may be corrupted. Error: {e}")
        return

    # --- LOAD DATA ---
    img_size = (args.img_size, args.img_size)
    test_generator, val_df = load_test_data(
        args.labels_csv, args.image_dir, attributes, img_size, args.batch_size
    )
    if not test_generator:
        return

    # --- EVALUATE & VISUALIZE ---
    predictions = evaluate_model(model, test_generator, val_df, attributes)
    visualize_predictions(test_generator, predictions, attributes)
    
    print("\n--- Test script finished. ---")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Test a trained multi-label image classifier.")
    parser.add_argument('--labels_csv', type=str, default='compiled_labels.csv', help='Path to the labels CSV file.')
    parser.add_argument('--image_dir', type=str, default='compiled_images', help='Path to the directory containing images.')
    parser.add_argument('--model_path', type=str, default='image_attribute_router.keras', help='Path to the trained .keras model file.')
    parser.add_argument('--img_size', type=int, default=224, help='Image size (width and height).')
    parser.add_argument('--batch_size', type=int, default=32, help='Testing batch size.')
    
    args = parser.parse_args()
    main(args)