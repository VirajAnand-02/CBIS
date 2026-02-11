# -*- coding: utf-8 -*-
"""
CBIS_T_Router_Full_V3.ipynb

This script downloads, compiles, and trains a multi-label image classifier
for four attributes: is_document, has_people, is_drawing_or_art, and is_screenshot.
It uses a scalable data pipeline and a robust training strategy.
"""

# ===================================================================
# STAGE 0: INSTALLATIONS & SETUP
# ===================================================================
# !pip install -q tensorflow pandas fiftyone scikit-learn kagglehub
# !pip install -q -U datasets

import os
import shutil
import pandas as pd
import tensorflow as tf
from sklearn.model_selection import train_test_split
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras.models import Model
from tensorflow.keras.layers import Dense, GlobalAveragePooling2D, Input, Dropout, BatchNormalization
from tensorflow.keras.applications import MobileNetV3Small
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.callbacks import ModelCheckpoint, EarlyStopping
from datasets import load_dataset
import fiftyone as fo
import fiftyone.zoo as foz
from fiftyone import ViewField as F
import kagglehub
import random
import glob

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
    print("No GPU found. Make sure to set Runtime → Change runtime type → GPU")

# ===================================================================
# STAGE 1: CENTRALIZED CONFIGURATION (EXPANDED)
# ===================================================================
print("\n--- CONFIGURATION ---")

# --- Attribute Definition (Single Source of Truth) ---
ATTRIBUTES = ["is_document", "has_people", "is_drawing_or_art", "is_screenshot"]
NUM_ATTRIBUTES = len(ATTRIBUTES)

# --- File & Directory Paths ---
COMPILED_IMAGES_DIR = "compiled_images"
COMPILED_LABELS_CSV = "compiled_labels.csv"
MODEL_SAVE_PATH = "image_attribute_router_v3.keras"

# --- Data Source Configuration ---
N_DOC_IMAGES = 1000
N_PEOPLE_IMAGES = 1000
N_ART_IMAGES = 1000
N_SCREENSHOT_IMAGES = 1000 # <<< NEW
N_NEGATIVE_IMAGES = 1000
N_MULTI_LABEL_SAMPLES = 200

# --- Model & Training Parameters ---
IMG_SIZE = (224, 224)
BATCH_SIZE = 32
INITIAL_EPOCHS = 5
FINE_TUNE_EPOCHS = 10
TOTAL_EPOCHS = INITIAL_EPOCHS + FINE_TUNE_EPOCHS

print(f"Attributes to predict: {ATTRIBUTES}")
print(f"Number of attributes: {NUM_ATTRIBUTES}")


# # ===================================================================
# # STAGE 2: DATA COMPILATION (WITH ALL DATA SOURCES)
# # ===================================================================
# print("\n--- STAGE 2: DATA COMPILATION ---")

# # Clean up previous runs
# if os.path.exists(COMPILED_IMAGES_DIR): shutil.rmtree(COMPILED_IMAGES_DIR)
# shutil.rmtree('is_document', ignore_errors=True)
# shutil.rmtree('has_people', ignore_errors=True)
# if os.path.exists(COMPILED_LABELS_CSV): os.remove(COMPILED_LABELS_CSV)
# os.makedirs(COMPILED_IMAGES_DIR, exist_ok=True)

# # --- Download RVL-CDIP (Documents) ---
# print("\nStreaming RVL-CDIP for 'is_document'...")
# output_dir_doc = "is_document"
# os.makedirs(output_dir_doc, exist_ok=True)
# iterator = iter(load_dataset("rvl_cdip", split="train", streaming=True))
# doc_images = [next(iterator)["image"].save(os.path.join(output_dir_doc, f"doc_{i+1}.png")) or os.path.join(output_dir_doc, f"doc_{i+1}.png") for i in range(N_DOC_IMAGES)]
# print(f"✅ Saved {len(doc_images)} document images.")

# # --- Download COCO (People & Negatives) ---
# print("\nDownloading COCO for 'has_people' and 'negative' examples...")
# export_dir_people = "has_people"
# dataset = foz.load_zoo_dataset("coco-2017", split="validation", label_types=["detections"], max_samples=3000, dataset_name="coco-demo")
# people_view = dataset.filter_labels("ground_truth", F("label") == "person").take(N_PEOPLE_IMAGES + N_NEGATIVE_IMAGES, seed=42)
# people_view.export(export_dir=export_dir_people, dataset_type=fo.types.ImageDirectory)
# all_people_images = [os.path.join(export_dir_people, f) for f in os.listdir(export_dir_people)]
# people_images = all_people_images[:N_PEOPLE_IMAGES]
# negative_images = all_people_images[N_PEOPLE_IMAGES:]
# print(f"✅ Exported {len(people_images)} images with people.")
# print(f"✅ Using {len(negative_images)} images as negative examples.")

# # --- Download WikiArt (Art) ---
# print("\nDownloading WikiArt for 'is_drawing_or_art'...")
# art_dataset_path = kagglehub.dataset_download("steubk/wikiart")
# all_art_images = glob.glob(f'{art_dataset_path}/**/*.jpg', recursive=True)
# art_images_to_use = random.sample(all_art_images, min(N_ART_IMAGES, len(all_art_images)))
# print(f"✅ Sampled {len(art_images_to_use)} art images.")

# # --- Download Mobile Screenshots ---
# print("\nDownloading Mobile Screenshots for 'is_screenshot'...")
# screenshot_dataset_path = kagglehub.dataset_download("dataclusterlabs/mobile-icon-mobile-screenshots-dataset")
# all_screenshot_images = glob.glob(f'{screenshot_dataset_path}/**/*.png', recursive=True) + glob.glob(f'{screenshot_dataset_path}/**/*.jpg', recursive=True)
# screenshot_images_to_use = random.sample(all_screenshot_images, min(N_SCREENSHOT_IMAGES, len(all_screenshot_images)))
# print(f"✅ Sampled {len(screenshot_images_to_use)} screenshot images.")


# # --- Compile All Sources into a Single DataFrame ---
# print("\nCompiling final dataset and labels...")
# records = []
# base_record = {att: 0 for att in ATTRIBUTES}

# def add_to_records(image_paths, category_name, attributes_to_set):
#     for i, img_path in enumerate(image_paths):
#         ext = os.path.splitext(img_path)[1]
#         new_fname = f"{category_name}_{i}{ext}"
#         shutil.copy2(img_path, os.path.join(COMPILED_IMAGES_DIR, new_fname))
#         record = base_record.copy()
#         record['image_filename'] = new_fname
#         for att in attributes_to_set:
#             record[att] = 1
#         records.append(record)

# add_to_records(doc_images, 'doc', ['is_document'])
# add_to_records(people_images, 'people', ['has_people'])
# add_to_records(art_images_to_use, 'art', ['is_drawing_or_art'])
# add_to_records(screenshot_images_to_use, 'screenshot', ['is_screenshot']) # <<< NEW
# add_to_records(negative_images, 'negative', [])

# # Add synthetic multi-label samples
# multi_label_docs = random.sample(doc_images, min(N_MULTI_LABEL_SAMPLES, len(doc_images)))
# add_to_records(multi_label_docs, 'multi_doc_people', ['is_document', 'has_people'])

# # --- Finalize and Save DataFrame ---
# df = pd.DataFrame(records)
# df = df.sample(frac=1, random_state=42).reset_index(drop=True)
# df.to_csv(COMPILED_LABELS_CSV, index=False)
# print(f"\n✅ Total processed images: {len(df)}")
# print("--- Final Label Distribution ---")
# print(df[ATTRIBUTES].sum())
# print("\n--- Generated CSV contents (sample) ---")
# print(df.head())


# # ===================================================================
# # STAGE 3: DATA GENERATORS (WITH ROBUST SPLIT)
# # ===================================================================
# print("\n--- STAGE 3: DATA GENERATORS ---")

# train_df, val_df = train_test_split(df, test_size=0.2, random_state=42)
# print(f"Train set size: {len(train_df)}, Validation set size: {len(val_df)}")
# train_datagen = ImageDataGenerator(rescale=1./255, rotation_range=20, width_shift_range=0.2, height_shift_range=0.2, shear_range=0.1, zoom_range=0.1, horizontal_flip=True, fill_mode='nearest')
# validation_datagen = ImageDataGenerator(rescale=1./255)
# train_generator = train_datagen.flow_from_dataframe(dataframe=train_df, directory=COMPILED_IMAGES_DIR, x_col='image_filename', y_col=ATTRIBUTES, batch_size=BATCH_SIZE, seed=42, shuffle=True, class_mode="raw", target_size=IMG_SIZE)
# validation_generator = validation_datagen.flow_from_dataframe(dataframe=val_df, directory=COMPILED_IMAGES_DIR, x_col='image_filename', y_col=ATTRIBUTES, batch_size=BATCH_SIZE, seed=42, shuffle=False, class_mode="raw", target_size=IMG_SIZE)
# print(f"✅ Generators created: {train_generator.n} training images, {validation_generator.n} validation images.")



import pandas as pd
from sklearn.model_selection import train_test_split
from tensorflow.keras.preprocessing.image import ImageDataGenerator

# Constants
COMPILED_IMAGES_DIR = "compiled_images"
COMPILED_LABELS_CSV = "compiled_labels.csv"
ATTRIBUTES = ["is_document", "has_people", "is_drawing_or_art", "is_screenshot"]
IMG_SIZE = (224, 224)
BATCH_SIZE = 32

# Load CSV
df = pd.read_csv(COMPILED_LABELS_CSV)

# Split into train and validation
train_df, val_df = train_test_split(df, test_size=0.2, random_state=42)

# Create data generators
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

# Create flow_from_dataframe generators
train_generator = train_datagen.flow_from_dataframe(
    dataframe=train_df,
    directory=COMPILED_IMAGES_DIR,
    x_col='image_filename',
    y_col=ATTRIBUTES,
    batch_size=BATCH_SIZE,
    seed=42,
    shuffle=True,
    class_mode="raw",
    target_size=IMG_SIZE
)

validation_generator = validation_datagen.flow_from_dataframe(
    dataframe=val_df,
    directory=COMPILED_IMAGES_DIR,
    x_col='image_filename',
    y_col=ATTRIBUTES,
    batch_size=BATCH_SIZE,
    seed=42,
    shuffle=False,
    class_mode="raw",
    target_size=IMG_SIZE
)

print(f"✅ Loaded {train_generator.n} training and {validation_generator.n} validation images.")


# ===================================================================
# STAGE 4: BUILD, TRAIN, AND FINE-TUNE THE MODEL
# ===================================================================
print("\n--- STAGE 4: MODEL TRAINING ---")

# --- Build Model ---
inputs = Input(shape=IMG_SIZE + (3,))
base_model = MobileNetV3Small(input_shape=IMG_SIZE + (3,), include_top=False, weights='imagenet')
base_model.trainable = False
x = base_model(inputs, training=False)
x = GlobalAveragePooling2D()(x)
x = Dense(256, activation='relu')(x)
x = BatchNormalization()(x)
x = Dropout(0.5)(x)
# The final layer now automatically has NUM_ATTRIBUTES neurons
outputs = Dense(NUM_ATTRIBUTES, activation='sigmoid', name='attributes')(x)
model = Model(inputs, outputs)
print("✅ Model built successfully.")

# --- Stage A: Train the Head ---
print("\n--- Stage A: Training the new head ---")
model.compile(
    optimizer=Adam(learning_rate=1e-3),
    loss='binary_crossentropy',
    metrics=[
        tf.keras.metrics.BinaryAccuracy(name='accuracy'),
        tf.keras.metrics.AUC(name='auc', multi_label=True, num_labels=NUM_ATTRIBUTES),
        tf.keras.metrics.AUC(name='prc', curve='PR', multi_label=True, num_labels=NUM_ATTRIBUTES)
    ]
)
print("Model Summary (Head is Trainable, Base is Frozen):")
model.summary()
history = model.fit(train_generator, validation_data=validation_generator, epochs=INITIAL_EPOCHS)

# --- Stage B: Fine-Tune the Model ---
print("\n--- Stage B: Fine-Tuning the whole model ---")
base_model.trainable = True
fine_tune_at = 100
for layer in base_model.layers[:fine_tune_at]:
    layer.trainable = False
model.compile(
    optimizer=Adam(learning_rate=1e-5),
    loss='binary_crossentropy',
    metrics=[
        tf.keras.metrics.BinaryAccuracy(name='accuracy'),
        tf.keras.metrics.AUC(name='auc', multi_label=True, num_labels=NUM_ATTRIBUTES),
        tf.keras.metrics.AUC(name='prc', curve='PR', multi_label=True, num_labels=NUM_ATTRIBUTES)
    ]
)
print("Re-compiled Model Summary (Fine-Tuning is enabled):")
model.summary()

callbacks = [
    ModelCheckpoint(filepath=MODEL_SAVE_PATH, monitor='val_prc', mode='max', save_best_only=True, verbose=1),
    EarlyStopping(monitor='val_prc', mode='max', patience=10, verbose=1, restore_best_weights=True)
]

history_fine_tune = model.fit(
    train_generator,
    validation_data=validation_generator,
    epochs=TOTAL_EPOCHS,
    initial_epoch=history.epoch[-1],
    callbacks=callbacks
)

# ===================================================================
# STAGE 5: SAVE FINAL MODEL
# ===================================================================
print("\n--- STAGE 5: SAVING FINAL MODEL ---")
print("Saving best model...")

# model.save(MODEL_SAVE_PATH) # This was the old way

# --- NEW, MORE ROBUST WAY ---
# Use the MODEL_SAVE_PATH variable that is already defined in your script's configuration.
model.save(filepath=MODEL_SAVE_PATH, save_format="keras", include_optimizer=True)

print(f"\n✅ Training and saving complete. Final model at: '{MODEL_SAVE_PATH}'")


# store results
import matplotlib.pyplot as plt

acc = history.history['accuracy']
val_acc = history.history['val_accuracy']
loss = history.history['loss']
val_loss = history.history['val_loss']


# plot results
# accuracy
plt.figure(figsize=(10, 16))
plt.rcParams['figure.figsize'] = [16, 9]
plt.rcParams['font.size'] = 14
plt.rcParams['axes.grid'] = True
plt.rcParams['figure.facecolor'] = 'white'
plt.subplot(2, 1, 1)
plt.plot(acc, label='Training Accuracy')
plt.plot(val_acc, label='Validation Accuracy')
plt.legend(loc='lower right')
plt.ylabel('Accuracy')
plt.title(f'\nTraining and Validation Accuracy. \nTrain Accuracy: {str(acc[-1])}\nValidation Accuracy: {str(val_acc[-1])}')