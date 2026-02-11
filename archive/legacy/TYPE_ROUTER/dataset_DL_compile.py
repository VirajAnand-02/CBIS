#!/usr/bin/env python3
# build_image_dataset.py

import os
import shutil
import pandas as pd
from datasets import load_dataset
from tqdm import tqdm
import random
import glob

# ===================================================================
# STAGE 1: CENTRALIZED CONFIGURATION
# ===================================================================
print("\n--- CONFIGURATION ---")

# --- Attribute Definition (Single Source of Truth) ---
ATTRIBUTES = ["is_document", "has_people", "is_screenshot", "is_animal"]

# --- File & Directory Paths ---
COMPILED_IMAGES_DIR = "compiled_images"
COMPILED_LABELS_CSV = "compiled_labels.csv"

# --- Data Source Configuration (Definitive Counts) ---
N_SAMPLES_PER_CATEGORY = 3000

print(f"Attributes: {ATTRIBUTES}")
print(f"Will definitively download {N_SAMPLES_PER_CATEGORY} samples for each category.")

# ===================================================================
# STAGE 2: DATA COMPILATION (ROBUST METHOD)
# ===================================================================
print("\n--- STAGE 2: DATA COMPILATION ---")

# --- Cleanup from any previous run ---
print("Cleaning up from previous runs...")
if os.path.exists(COMPILED_IMAGES_DIR):
    shutil.rmtree(COMPILED_IMAGES_DIR)
os.makedirs(COMPILED_IMAGES_DIR, exist_ok=True)
if os.path.exists(COMPILED_LABELS_CSV):
    os.remove(COMPILED_LABELS_CSV)

# --- Helper function for Hugging Face Datasets ---
def get_images_from_hf_dataset(dataset_name, split, num_images, category_name):
    """
    Streams a Hugging Face dataset and saves exactly num_images.
    """
    print(f"\n---> Processing '{category_name}' from Hugging Face '{dataset_name}'...")
    image_paths = []
    tmp_dir = f"tmp_{category_name}"
    if os.path.exists(tmp_dir): shutil.rmtree(tmp_dir)
    os.makedirs(tmp_dir, exist_ok=True)

    iterator = iter(load_dataset(dataset_name, split=split, streaming=True))
    
    with tqdm(total=num_images, desc=f"Finding {category_name} images") as pbar:
        while len(image_paths) < num_images:
            try:
                example = next(iterator)
                if "image" in example and example["image"] is not None:
                    image = example["image"]
                    if image.mode != "RGB":
                        image = image.convert("RGB")
                    
                    idx = len(image_paths) + 1
                    fname = os.path.join(tmp_dir, f"{category_name}_{idx}.jpg")
                    image.save(fname)
                    image_paths.append(fname)
                    pbar.update(1)
                else:
                    continue
            except StopIteration:
                print(f"\nWarning: Reached end of dataset for '{category_name}' before finding {num_images}.")
                break
            except Exception as e:
                print(f"\nSkipping an image due to an unexpected error: {e}")

    print(f"  ✓ Obtained {len(image_paths)} images for '{category_name}'.")
    return image_paths

# --- 1) Documents from RVL-CDIP (Hugging Face) ---
doc_paths = get_images_from_hf_dataset(
    dataset_name="rvl_cdip",
    split="train",
    num_images=N_SAMPLES_PER_CATEGORY,
    category_name="document",
)

# --- 2) People from Human Faces (Kaggle) ---
print("\n---> Processing 'people' from Kaggle dataset 'ashwingupta3012/human-faces'...")
people_paths = []
tmp_people_dir = "tmp_people_kaggle"
try:
    from kaggle.api.kaggle_api_extended import KaggleApi
    api = KaggleApi()
    api.authenticate()

    if os.path.exists(tmp_people_dir): shutil.rmtree(tmp_people_dir)
    print("  Downloading and unzipping 'human-faces' dataset...")
    api.dataset_download_files("ashwingupta3012/human-faces", path=tmp_people_dir, unzip=True, quiet=True)

    all_people_images = glob.glob(os.path.join(tmp_people_dir, "Humans", "*.jpg"), recursive=True)
    if len(all_people_images) < N_SAMPLES_PER_CATEGORY:
        print(f"  Warning: Found only {len(all_people_images)} people images, less than the requested {N_SAMPLES_PER_CATEGORY}.")
        people_paths = all_people_images
    else:
        people_paths = random.sample(all_people_images, N_SAMPLES_PER_CATEGORY)
    
    print(f"  ✓ Sampled {len(people_paths)} images for 'people'.")

except Exception as e:
    print(f"\n  ✗ ERROR: Could not download 'people' from Kaggle. Please ensure 'kaggle.json' is set up.")
    print(f"    Details: {e}")
    print("    Skipping 'people' category.")


# --- 3) Animals from 'animals10' (Kaggle) ---
print("\n---> Processing 'animal' from Kaggle dataset 'alessiocorrado99/animals10'...")
animal_paths = []
tmp_animal_dir = "tmp_animals_kaggle"
try:
    from kaggle.api.kaggle_api_extended import KaggleApi
    api = KaggleApi()
    api.authenticate()

    if os.path.exists(tmp_animal_dir): shutil.rmtree(tmp_animal_dir)
    print("  Downloading and unzipping 'animals10' dataset...")
    api.dataset_download_files("alessiocorrado99/animals10", path=tmp_animal_dir, unzip=True, quiet=True)

    all_animal_images = glob.glob(os.path.join(tmp_animal_dir, "raw-img", "**", "*.jpeg"), recursive=True)
    if len(all_animal_images) < N_SAMPLES_PER_CATEGORY:
        print(f"  Warning: Found only {len(all_animal_images)} animal images, less than the requested {N_SAMPLES_PER_CATEGORY}.")
        animal_paths = all_animal_images
    else:
        animal_paths = random.sample(all_animal_images, N_SAMPLES_PER_CATEGORY)
    
    print(f"  ✓ Sampled {len(animal_paths)} images for 'animal'.")

except Exception as e:
    print(f"\n  ✗ ERROR: Could not download 'animals' from Kaggle. Please ensure 'kaggle.json' is set up.")
    print(f"    Details: {e}")
    print("    Skipping 'animal' category.")

# --- 4) Screenshots from a dedicated dataset (Hugging Face) ---
screenshot_paths = get_images_from_hf_dataset(
    dataset_name="naorm/website-screenshots-blip-large",
    split="train",
    num_images=N_SAMPLES_PER_CATEGORY,
    category_name="screenshot",
)

# --- Final Compilation ---
print("\nCompiling into one dataset...")
all_records = []
base_record = {att: 0 for att in ATTRIBUTES}

def add_to_records(src_paths, category_name, active_attr):
    if not src_paths:
        print(f"Skipping compilation for '{category_name}' as no paths were provided.")
        return
        
    for idx, src_path in enumerate(src_paths):
        ext = os.path.splitext(src_path)[1].lower() or ".jpg"
        dest_name = f"{category_name}_{idx+1}{ext}"
        dest_path = os.path.join(COMPILED_IMAGES_DIR, dest_name)
        shutil.copy2(src_path, dest_path)
        
        rec = base_record.copy()
        rec["image_filename"] = dest_name
        rec[active_attr] = 1
        all_records.append(rec)

add_to_records(doc_paths, "document", "is_document")
add_to_records(people_paths, "people", "has_people")
add_to_records(animal_paths, "animal", "is_animal")
add_to_records(screenshot_paths, "screenshot", "is_screenshot")

if all_records:
    df = pd.DataFrame(all_records)
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)
    df.to_csv(COMPILED_LABELS_CSV, index=False)
    print(f"\n✅ Total images compiled: {len(df)}")
    print(f"✅ Labels CSV saved to '{COMPILED_LABELS_CSV}'")
    print("\n--- Final Label Distribution ---")
    print(df[ATTRIBUTES].sum(numeric_only=True))
    print("\n--- CSV Head ---")
    print(df.head())
else:
    print("\n⚠️ No data was compiled. Something went wrong.")

# --- Final Cleanup ---
print("\nCleaning up temporary download directories...")
shutil.rmtree("tmp_document", ignore_errors=True)
shutil.rmtree("tmp_people_kaggle", ignore_errors=True)
shutil.rmtree("tmp_animals_kaggle", ignore_errors=True)
shutil.rmtree("tmp_screenshot", ignore_errors=True)

print("\n🚀 Dataset build complete!")