# train_model.py

import os
import argparse
import pandas as pd
import tensorflow as tf
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras.models import Model
from tensorflow.keras.layers import Dense, GlobalAveragePooling2D, Input, Dropout, BatchNormalization
from tensorflow.keras.applications import MobileNetV3Small
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.callbacks import ModelCheckpoint, EarlyStopping

def create_data_generators(labels_csv, image_dir, target_attributes, img_size, batch_size):
    """
    Loads the dataframe, splits it, and creates training and validation data generators.
    """
    print("\n--- Creating Data Generators ---")
    try:
        df = pd.read_csv(labels_csv)
    except FileNotFoundError:
        print(f"ERROR: Labels file not found at '{labels_csv}'. Please run the data preparation script first.")
        return None, None

    # Ensure all target attribute columns exist
    for col in target_attributes:
        if col not in df.columns:
            print(f"ERROR: Attribute column '{col}' not found in '{labels_csv}'.")
            return None, None

    train_df, val_df = train_test_split(df, test_size=0.2, random_state=42)
    print(f"Train set size: {len(train_df)}, Validation set size: {len(val_df)}")

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

    train_generator = train_datagen.flow_from_dataframe(
        dataframe=train_df,
        directory=image_dir,
        x_col='image_filename',
        y_col=target_attributes,
        batch_size=batch_size,
        seed=42,
        shuffle=True,
        class_mode="raw",
        target_size=img_size
    )

    validation_generator = validation_datagen.flow_from_dataframe(
        dataframe=val_df,
        directory=image_dir,
        x_col='image_filename',
        y_col=target_attributes,
        batch_size=batch_size,
        seed=42,
        shuffle=False,
        class_mode="raw",
        target_size=img_size
    )
    print(f"✅ Generators created: {train_generator.n} training images, {validation_generator.n} validation images.")
    return train_generator, validation_generator


def build_model(input_shape, num_attributes):
    """
    Builds the MobileNetV3Small-based multi-label classification model.
    """
    print("\n--- Building Model ---")
    inputs = Input(shape=input_shape)
    base_model = MobileNetV3Small(input_shape=input_shape, include_top=False, weights='imagenet')
    base_model.trainable = False  # Start with the base frozen

    x = base_model(inputs, training=False)
    x = GlobalAveragePooling2D()(x)
    x = Dense(256, activation='relu')(x)
    x = BatchNormalization()(x)
    x = Dropout(0.5)(x)
    outputs = Dense(num_attributes, activation='sigmoid', name='attributes')(x)
    model = Model(inputs, outputs)
    print("✅ Model built successfully.")
    return model, base_model


def plot_and_save_history(history_initial, history_fine, save_path="training_history.png"):
    """
    Combines two training histories and plots accuracy, loss, AUC, and PRC.
    """
    print("\n--- Generating Performance Report and Plots ---")
    # Combine history from initial training and fine-tuning
    acc = history_initial.history['accuracy'] + history_fine.history['accuracy']
    val_acc = history_initial.history['val_accuracy'] + history_fine.history['val_accuracy']
    loss = history_initial.history['loss'] + history_fine.history['loss']
    val_loss = history_initial.history['val_loss'] + history_fine.history['val_loss']
    auc = history_initial.history['auc'] + history_fine.history['auc']
    val_auc = history_initial.history['val_auc'] + history_fine.history['val_auc']
    prc = history_initial.history['prc'] + history_fine.history['prc']
    val_prc = history_initial.history['val_prc'] + history_fine.history['val_prc']

    # Find the best epoch based on validation PRC
    best_epoch = val_prc.index(max(val_prc))
    print("--- Best Epoch Performance Report ---")
    print(f"Best Epoch: {best_epoch + 1}")
    print(f"  Validation Loss:      {val_loss[best_epoch]:.4f}")
    print(f"  Validation Accuracy:  {val_acc[best_epoch]:.4f}")
    print(f"  Validation AUC:       {val_auc[best_epoch]:.4f}")
    print(f"  Validation PRC (AUC): {val_prc[best_epoch]:.4f}")

    # Plotting
    plt.style.use('seaborn-v0_8-whitegrid')
    fig, axes = plt.subplots(2, 2, figsize=(20, 15))
    fig.suptitle('Model Training History', fontsize=20)

    # Accuracy Plot
    axes[0, 0].plot(acc, label='Training Accuracy')
    axes[0, 0].plot(val_acc, label='Validation Accuracy')
    axes[0, 0].axvline(x=best_epoch, color='r', linestyle='--', label=f'Best Epoch ({best_epoch+1})')
    axes[0, 0].set_title('Training and Validation Accuracy')
    axes[0, 0].set_ylabel('Accuracy')
    axes[0, 0].set_xlabel('Epoch')
    axes[0, 0].legend(loc='lower right')

    # Loss Plot
    axes[0, 1].plot(loss, label='Training Loss')
    axes[0, 1].plot(val_loss, label='Validation Loss')
    axes[0, 1].axvline(x=best_epoch, color='r', linestyle='--')
    axes[0, 1].set_title('Training and Validation Loss')
    axes[0, 1].set_ylabel('Loss')
    axes[0, 1].set_xlabel('Epoch')
    axes[0, 1].legend(loc='upper right')

    # AUC Plot
    axes[1, 0].plot(auc, label='Training AUC')
    axes[1, 0].plot(val_auc, label='Validation AUC')
    axes[1, 0].axvline(x=best_epoch, color='r', linestyle='--')
    axes[1, 0].set_title('Training and Validation AUC (ROC)')
    axes[1, 0].set_ylabel('AUC')
    axes[1, 0].set_xlabel('Epoch')
    axes[1, 0].legend(loc='lower right')

    # PRC Plot
    axes[1, 1].plot(prc, label='Training PRC')
    axes[1, 1].plot(val_prc, label='Validation PRC (AUC)')
    axes[1, 1].axvline(x=best_epoch, color='r', linestyle='--')
    axes[1, 1].set_title('Training and Validation PRC (Precision-Recall Curve)')
    axes[1, 1].set_ylabel('Area Under Curve')
    axes[1, 1].set_xlabel('Epoch')
    axes[1, 1].legend(loc='lower right')

    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.savefig(save_path)
    print(f"\n✅ Training history plot saved to '{save_path}'")
    plt.close()


def main(args):
    """
    Main function to orchestrate the model training pipeline.
    """
    # GPU Check
    gpus = tf.config.list_physical_devices('GPU')
    if gpus:
        try:
            for gpu in gpus:
                tf.config.experimental.set_memory_growth(gpu, True)
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
    
    # Define metrics once
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
    fine_tune_at = 100
    for layer in base_model.layers[:fine_tune_at]:
        layer.trainable = False

    model.compile(optimizer=Adam(learning_rate=1e-5), loss='binary_crossentropy', metrics=metrics)
    print("Re-compiled Model Summary (Fine-Tuning is enabled):")
    model.summary()

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

    # --- STAGE C: SAVE AND REPORT ---
    # The best model is already saved by ModelCheckpoint.
    # Now we generate the final report and plots.
    plot_and_save_history(history, history_fine_tune)
    print(f"\n✅ Training complete. Best model saved to '{args.model_output_path}'")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Train a multi-label image classifier.")
    parser.add_argument('--labels_csv', type=str, default='compiled_labels.csv', help='Path to the labels CSV file.')
    parser.add_argument('--image_dir', type=str, default='compiled_images', help='Path to the directory containing images.')
    parser.add_argument('--model_output_path', type=str, default='image_attribute_router.keras', help='Path to save the final trained model.')
    parser.add_argument('--img_size', type=int, default=224, help='Image size (width and height).')
    parser.add_argument('--batch_size', type=int, default=32, help='Training batch size.')
    parser.add_argument('--initial_epochs', type=int, default=5, help='Epochs for training the head.')
    parser.add_argument('--fine_tune_epochs', type=int, default=20, help='Max epochs for fine-tuning.')
    
    args = parser.parse_args()
    main(args)