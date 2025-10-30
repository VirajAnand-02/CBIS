#!/usr/bin/env python
# train_model.py

import os
import argparse
import pandas as pd
import numpy as np
import tensorflow as tf
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from tensorflow.keras.preprocessing.image import ImageDataGenerator, load_img, img_to_array
from tensorflow.keras.models import Model, load_model
from tensorflow.keras.layers import Dense, GlobalAveragePooling2D, Input, Dropout, BatchNormalization
from tensorflow.keras.applications import MobileNetV3Small
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.callbacks import ModelCheckpoint, EarlyStopping

# --- DATA PREPARATION ---

def create_data_generators(labels_csv, image_dir, target_attributes, img_size, batch_size):
    """
    Loads the dataframe, splits it, and creates training and validation data generators.
    """
    print("\n--- Creating Data Generators ---")
    try:
        df = pd.read_csv(labels_csv)
    except FileNotFoundError:
        print(f"ERROR: Labels file not found at '{labels_csv}'.")
        return None, None

    # Ensure all target attribute columns exist
    for col in target_attributes:
        if col not in df.columns:
            print(f"ERROR: Attribute column '{col}' not found in '{labels_csv}'.")
            return None, None

    train_df, val_df = train_test_split(df, test_size=0.2, random_state=42)
    print(f"Train set size: {len(train_df)}, Validation set size: {len(val_df)}")

    # Data augmentation for the training set, only rescaling for the validation set
    train_datagen = ImageDataGenerator(
        rescale=1./255,
        rotation_range=20,
        width_shift_range=0.2,
        height_shift_range=0.2,
        shear_range=0.1,
        zoom_range=0.1,
        horizontal_flip=True,
        fill_mode='nearest'
    )
    validation_datagen = ImageDataGenerator(rescale=1./255)

    # flow_from_dataframe is memory-efficient for large datasets
    train_generator = train_datagen.flow_from_dataframe(
        dataframe=train_df,
        directory=image_dir,
        x_col='image_filename',
        y_col=target_attributes,
        batch_size=batch_size,
        seed=42,
        shuffle=True,
        class_mode="raw", # 'raw' for multi-label regression/classification
        target_size=img_size
    )

    validation_generator = validation_datagen.flow_from_dataframe(
        dataframe=val_df,
        directory=image_dir,
        x_col='image_filename',
        y_col=target_attributes,
        batch_size=batch_size,
        seed=42,
        shuffle=False, # No need to shuffle validation data
        class_mode="raw",
        target_size=img_size
    )
    print(f"✅ Generators created: {train_generator.n} training images, {validation_generator.n} validation images.")
    return train_generator, validation_generator

# --- MODEL ARCHITECTURE ---

def build_model(input_shape, num_attributes):
    """
    Builds the MobileNetV3Small-based multi-label classification model.
    """
    print("\n--- Building Model ---")
    inputs = Input(shape=input_shape)
    
    # Use a pre-trained base model for transfer learning
    base_model = MobileNetV3Small(input_shape=input_shape, include_top=False, weights='imagenet')
    base_model.trainable = False  # Start with the base frozen to train only the new head

    # Add custom classification head
    x = base_model(inputs, training=False)
    x = GlobalAveragePooling2D()(x)
    x = Dense(256, activation='relu')(x)
    x = BatchNormalization()(x)
    x = Dropout(0.5)(x)
    # Output layer with 'sigmoid' for multi-label classification
    outputs = Dense(num_attributes, activation='sigmoid', name='attributes')(x)
    
    model = Model(inputs, outputs)
    print("✅ Model built successfully.")
    return model, base_model

# --- REPORTING & PLOTTING ---

def _plot_metric(ax, history_data, val_history_data, metric_name, best_epoch):
    """Helper function to plot a single metric."""
    ax.plot(history_data, label=f'Training {metric_name}')
    ax.plot(val_history_data, label=f'Validation {metric_name}')
    ax.axvline(x=best_epoch, color='r', linestyle='--', label=f'Best Epoch ({best_epoch+1})')
    ax.set_title(f'Training and Validation {metric_name}')
    ax.set_ylabel(metric_name)
    ax.set_xlabel('Epoch')
    ax.legend(loc='best')

def plot_and_save_history(history_initial, history_fine, save_path="training_history.png"):
    """
    Combines two training histories and plots key metrics.
    """
    print("\n--- Generating Performance Report and Plots ---")
    # Combine history from initial training and fine-tuning
    history = {key: history_initial.history[key] + history_fine.history[key] for key in history_initial.history.keys()}

    # Find the best epoch based on validation PRC (Precision-Recall Curve AUC)
    val_prc = history['val_prc']
    best_epoch = np.argmax(val_prc)
    
    print("--- Best Epoch Performance Report ---")
    print(f"Best Epoch: {best_epoch + 1}")
    print(f"  Validation Loss:      {history['val_loss'][best_epoch]:.4f}")
    print(f"  Validation Accuracy:  {history['val_accuracy'][best_epoch]:.4f}")
    print(f"  Validation AUC:       {history['val_auc'][best_epoch]:.4f}")
    print(f"  Validation PRC (AUC): {history['val_prc'][best_epoch]:.4f}")

    # Plotting
    plt.style.use('seaborn-v0_8-whitegrid')
    fig, axes = plt.subplots(2, 2, figsize=(20, 15))
    fig.suptitle('Model Training History', fontsize=20)

    _plot_metric(axes[0, 0], history['accuracy'], history['val_accuracy'], 'Accuracy', best_epoch)
    _plot_metric(axes[0, 1], history['loss'], history['val_loss'], 'Loss', best_epoch)
    _plot_metric(axes[1, 0], history['auc'], history['val_auc'], 'AUC (ROC)', best_epoch)
    _plot_metric(axes[1, 1], history['prc'], history['val_prc'], 'PRC (AUC)', best_epoch)

    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.savefig(save_path)
    print(f"\n✅ Training history plot saved to '{save_path}'")
    plt.close()

# --- MAIN WORKFLOWS: TRAIN & PREDICT ---

def train_pipeline(args):
    """
    Main function to orchestrate the model training pipeline.
    """
    # GPU Check
    gpus = tf.config.list_physical_devices('GPU')
    if gpus:
        try:
            for gpu in gpus: tf.config.experimental.set_memory_growth(gpu, True)
            print(f"GPUs detected and memory growth enabled: {gpus}")
        except RuntimeError as e:
            print(e)
    else:
        print("No GPU found. Training on CPU.")

    # --- DYNAMICALLY DISCOVER ATTRIBUTES ---
    print("\n--- Dynamically discovering attributes from CSV ---")
    try:
        df = pd.read_csv(args.labels_csv)
        attributes = [col for col in df.columns if col != 'image_filename']
        num_attributes = len(attributes)
        print(f"✅ Found {num_attributes} attributes: {attributes}")
    except (FileNotFoundError, KeyError) as e:
        print(f"Error discovering attributes: {e}. Please check your CSV file.")
        return

    # --- DATA PREPARATION ---
    img_size = (args.img_size, args.img_size)
    train_generator, validation_generator = create_data_generators(
        args.labels_csv, args.image_dir, attributes, img_size, args.batch_size
    )
    if not train_generator:
        return # Exit if generators failed to create

    # --- MODEL BUILDING ---
    model, base_model = build_model(input_shape=img_size + (3,), num_attributes=num_attributes)
    
    # Define metrics once. PRC is great for imbalanced multi-label problems.
    metrics = [
        tf.keras.metrics.BinaryAccuracy(name='accuracy'),
        tf.keras.metrics.AUC(name='auc', multi_label=True, num_labels=num_attributes),
        tf.keras.metrics.AUC(name='prc', curve='PR', multi_label=True, num_labels=num_attributes)
    ]

    # --- STAGE A: TRAIN THE HEAD ---
    print("\n--- Stage A: Training the new head ---")
    model.compile(optimizer=Adam(learning_rate=1e-3), loss='binary_crossentropy', metrics=metrics)
    model.summary()
    history = model.fit(
        train_generator,
        validation_data=validation_generator,
        epochs=args.initial_epochs
    )

    # --- STAGE B: FINE-TUNE THE MODEL ---
    print("\n--- Stage B: Fine-Tuning the whole model ---")
    base_model.trainable = True
    # Unfreeze from a certain layer onward. Let's unfreeze the top ~50% of the layers.
    fine_tune_at = len(base_model.layers) // 2 
    print(f"Unfreezing layers from index {fine_tune_at} onwards.")
    for layer in base_model.layers[:fine_tune_at]:
        layer.trainable = False

    # Re-compile with a much lower learning rate for fine-tuning
    model.compile(optimizer=Adam(learning_rate=1e-5), loss='binary_crossentropy', metrics=metrics)
    print("Re-compiled Model Summary (Fine-Tuning is enabled):")
    model.summary()

    # Callbacks to save the best model and stop early if no improvement
    callbacks = [
        ModelCheckpoint(filepath=args.model_output_path, monitor='val_prc', mode='max', save_best_only=True, verbose=1),
        EarlyStopping(monitor='val_prc', mode='max', patience=10, verbose=1, restore_best_weights=True)
    ]

    total_epochs = args.initial_epochs + args.fine_tune_epochs
    history_fine_tune = model.fit(
        train_generator,
        validation_data=validation_generator,
        epochs=total_epochs,
        initial_epoch=history.epoch[-1],
        callbacks=callbacks
    )

    # --- STAGE C: FINAL REPORT & SAVE ---
    plot_and_save_history(history, history_fine_tune, args.history_plot_path)

    print("\n--- Final Evaluation on Validation Set ---")
    # Load the best model saved by the checkpoint
    best_model = load_model(args.model_output_path)
    results = best_model.evaluate(validation_generator, verbose=1)
    print("Performance of the best model on the validation set:")
    for name, value in zip(best_model.metrics_names, results):
        print(f"  {name}: {value:.4f}")

    print(f"\n✅ Training complete. Best model saved to '{args.model_output_path}'")


def predict_on_image(args):
    """
    Loads a trained model and predicts attributes for a single image.
    Inspired by the prediction block in the reference script.
    """
    print("\n--- Predicting on a single image ---")
    try:
        # Load the attribute names from the CSV
        df = pd.read_csv(args.labels_csv)
        attributes = [col for col in df.columns if col != 'image_filename']
        print(f"Loaded {len(attributes)} attribute labels.")
        
        # Load the trained model
        model = load_model(args.model_path)
        print(f"Model '{args.model_path}' loaded successfully.")
    except Exception as e:
        print(f"ERROR: Failed to load model or labels. {e}")
        return

    # Load and preprocess the image
    img_size = (args.img_size, args.img_size)
    try:
        img = load_img(args.image_path, target_size=img_size)
        img_array = img_to_array(img)
        img_array = img_array / 255.0  # Rescale
        img_batch = np.expand_dims(img_array, axis=0) # Create a batch
    except Exception as e:
        print(f"ERROR: Failed to load or process image '{args.image_path}'. {e}")
        return
    
    # Make prediction
    proba = model.predict(img_batch)[0] # Get probabilities for the first (and only) image in the batch

    # Get top N predictions
    sorted_indices = np.argsort(proba)[::-1] # Sort in descending order

    print(f"\nTop {args.top_n} predicted attributes for '{os.path.basename(args.image_path)}':")
    for i in range(args.top_n):
        idx = sorted_indices[i]
        label = attributes[idx]
        confidence = proba[idx]
        print(f"  - {label}: {confidence:.2%}")
        
    # Display the image
    plt.imshow(img)
    plt.title(f"Predictions for {os.path.basename(args.image_path)}")
    plt.axis('off')
    plt.show()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Train or use a multi-label image classifier.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    subparsers = parser.add_subparsers(dest='mode', required=True, help='Select mode: "train" or "predict"')

    # --- Parser for the 'train' mode ---
    train_parser = subparsers.add_parser('train', help='Train a new model from scratch.')
    train_parser.add_argument('--labels_csv', type=str, default='compiled_labels.csv', help='Path to the labels CSV file.')
    train_parser.add_argument('--image_dir', type=str, default='compiled_images', help='Path to the directory containing images.')
    train_parser.add_argument('--model_output_path', type=str, default='image_attribute_model.keras', help='Path to save the final trained model.')
    train_parser.add_argument('--history_plot_path', type=str, default='training_history.png', help='Path to save the training history plot.')
    train_parser.add_argument('--img_size', type=int, default=224, help='Image size (width and height).')
    train_parser.add_argument('--batch_size', type=int, default=32, help='Training batch size.')
    train_parser.add_argument('--initial_epochs', type=int, default=5, help='Epochs for training the head.')
    train_parser.add_argument('--fine_tune_epochs', type=int, default=20, help='Max epochs for fine-tuning.')
    
    # --- Parser for the 'predict' mode ---
    predict_parser = subparsers.add_parser('predict', help='Predict attributes for a single image using a trained model.')
    predict_parser.add_argument('--image_path', type=str, required=True, help='Path to the input image for prediction.')
    predict_parser.add_argument('--model_path', type=str, default='image_attribute_model.keras', help='Path to the trained Keras model file.')
    predict_parser.add_argument('--labels_csv', type=str, default='compiled_labels.csv', help='Path to the CSV to retrieve attribute names.')
    predict_parser.add_argument('--img_size', type=int, default=224, help='Image size the model was trained on.')
    predict_parser.add_argument('--top_n', type=int, default=5, help='Number of top predictions to display.')

    args = parser.parse_args()
    
    if args.mode == 'train':
        train_pipeline(args)
    elif args.mode == 'predict':
        predict_on_image(args)