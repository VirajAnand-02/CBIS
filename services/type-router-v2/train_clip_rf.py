#!/usr/bin/env python3
"""
train_clip_rf_multilabel.py

Usage:
    python train_clip_rf_multilabel.py \
      --csv metadata.csv \
      --images-dir /path/to/images \
      --out-dir outputs \
      --clip-model openai/clip-vit-base-patch32 \
      --batch-size 32 \
      --n-estimators 200
"""

import os
import argparse
import time
import math
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
from tqdm import tqdm
import joblib

import torch
from transformers import CLIPProcessor, CLIPModel

from sklearn.ensemble import RandomForestClassifier
from sklearn.multiclass import OneVsRestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    f1_score, jaccard_score, hamming_loss, classification_report
)

# -------------------------
# Helpers
# -------------------------
def robust_bool_to_int(series):
    """Convert a pandas Series of booleans/strings/numbers to 0/1 ints robustly."""
    s = series.copy()
    # If already boolean or numeric
    if pd.api.types.is_bool_dtype(s):
        return s.astype(int)
    if pd.api.types.is_integer_dtype(s) or pd.api.types.is_float_dtype(s):
        return s.fillna(0).astype(int).clip(0, 1)
    # Otherwise convert strings
    s2 = s.astype(str).str.strip().str.lower().fillna("false")
    mapping = {"true": 1, "t": 1, "yes": 1, "y": 1, "1": 1,
               "false": 0, "f": 0, "no": 0, "n": 0, "0": 0}
    return s2.map(mapping).fillna(0).astype(int)

def compute_clip_embeddings(model, processor, image_paths, batch_size=32, device="cpu"):
    """Compute CLIP embeddings for a list of image paths. Returns embeddings array (N, D) and kept_index_map."""
    model.eval()
    embeddings = []
    kept_idx = []  # indices of image_paths that were successfully processed
    total = len(image_paths)
    with torch.no_grad():
        for i in tqdm(range(0, total, batch_size), desc="CLIP batches"):
            batch_paths = image_paths[i:i+batch_size]
            images = []
            valid_indices = []
            for j, p in enumerate(batch_paths):
                try:
                    img = Image.open(p).convert("RGB")
                    images.append(img)
                    valid_indices.append(i + j)
                except Exception as e:
                    # skip corrupted/missing image
                    print(f"Warning: couldn't open image {p}: {e}")
            if not images:
                continue
            # Prepare inputs
            clip_inputs = processor(images=images, return_tensors="pt")
            clip_inputs = {k: v.to(device) for k, v in clip_inputs.items()}
            if device == "cuda":
                torch.cuda.synchronize()
            t0 = time.perf_counter()
            image_features = model.get_image_features(**clip_inputs)
            if device == "cuda":
                torch.cuda.synchronize()
            t_elapsed = time.perf_counter() - t0
            # Normalize each vector
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            image_features = image_features.cpu().numpy()
            embeddings.append(image_features)
            kept_idx.extend(valid_indices)
    if embeddings:
        embeddings = np.vstack(embeddings)
    else:
        embeddings = np.zeros((0, model.config.projection_dim if hasattr(model.config, "projection_dim") else 512))
    return embeddings, kept_idx

# -------------------------
# Main flow
# -------------------------
def main(args):
    os.makedirs(args.out_dir, exist_ok=True)

    # Read CSV
    df = pd.read_csv(args.csv)
    if "filename" not in df.columns:
        raise ValueError("CSV must have a 'filename' column with image filenames/paths.")

    # Labels: use all columns except 'filename' as label columns
    label_cols = [c for c in df.columns if c != "filename"]
    if len(label_cols) == 0:
        raise ValueError("CSV contains no label columns (only 'filename' found).")

    print("Label columns detected:", label_cols)

    # Convert label columns to binary 0/1 ints
    for c in label_cols:
        df[c] = robust_bool_to_int(df[c])

    # Build absolute image paths (if filename is already absolute, keep it)
    image_paths = []
    for fname in df["filename"].tolist():
        p = Path(fname)
        if not p.is_absolute():
            p = Path(args.images_dir) / p
        image_paths.append(str(p))

    # Load CLIP
    device = "cuda" if torch.cuda.is_available() and not args.force_cpu else "cpu"
    print("Using device:", device)
    print("Loading CLIP model:", args.clip_model)
    clip_model = CLIPModel.from_pretrained(args.clip_model).to(device)
    clip_processor = CLIPProcessor.from_pretrained(args.clip_model)

    # Compute embeddings
    print("Computing CLIP embeddings for images...")
    embeddings, kept_idx = compute_clip_embeddings(
        clip_model, clip_processor,
        image_paths,
        batch_size=args.batch_size,
        device=device
    )

    if embeddings.shape[0] == 0:
        raise RuntimeError("No embeddings were computed. Check your image paths and files.")

    print(f"Computed embeddings for {embeddings.shape[0]} images (skipped {len(image_paths) - len(kept_idx)}).")
    # Keep corresponding rows in df
    df_kept = df.iloc[kept_idx].reset_index(drop=True)
    assert embeddings.shape[0] == len(df_kept)

    # Save embeddings to .npy and csv (optional)
    emb_npy_path = os.path.join(args.out_dir, "clip_embeddings.npy")
    np.save(emb_npy_path, embeddings)
    print("Saved embeddings to", emb_npy_path)

    emb_csv_path = os.path.join(args.out_dir, "clip_embeddings_with_meta.csv")
    emb_meta_df = pd.DataFrame(embeddings)
    emb_out = pd.concat([df_kept.reset_index(drop=True), emb_meta_df.reset_index(drop=True)], axis=1)
    emb_out.to_csv(emb_csv_path, index=False)
    print("Saved embeddings+meta CSV to", emb_csv_path)

    # Prepare X, Y
    X = embeddings  # shape (n_samples, dim)
    Y = df_kept[label_cols].values  # shape (n_samples, n_labels)

    # Train / test split
    X_train, X_test, y_train, y_test, meta_train, meta_test = train_test_split(
        X, Y, df_kept, test_size=args.test_size, random_state=42
    )

    print(f"Train samples: {X_train.shape[0]}  Test samples: {X_test.shape[0]}")

    # Build and train One-vs-Rest RandomForest
    rf = RandomForestClassifier(
        n_estimators=args.n_estimators,
        max_depth=args.max_depth,
        n_jobs=args.n_jobs,
        random_state=42,
        class_weight="balanced" if args.class_weight_balanced else None
    )
    ovr = OneVsRestClassifier(rf, n_jobs=args.n_jobs)

    print("Training One-vs-Rest RandomForest...")
    t0 = time.perf_counter()
    ovr.fit(X_train, y_train)
    t_train = time.perf_counter() - t0
    print(f"Training done in {t_train:.1f}s")

    # Predict & probabilities
    print("Predicting on test set...")
    y_pred = ovr.predict(X_test)
    try:
        y_proba = ovr.predict_proba(X_test)
    except Exception:
        # fallback: stack individual estimator predict_proba
        y_proba = np.vstack([est.predict_proba(X_test)[:, 1] for est in ovr.estimators_]).T

    # Evaluation
    print("Micro F1:", f1_score(y_test, y_pred, average="micro"))
    print("Macro F1:", f1_score(y_test, y_pred, average="macro"))
    try:
        jacc = jaccard_score(y_test, y_pred, average="samples")
    except Exception:
        jacc = jaccard_score(y_test, y_pred, average="samples", zero_division=0)
    print("Jaccard (samples avg):", jacc)
    print("Hamming loss:", hamming_loss(y_test, y_pred))

    # Per-label report
    print("\nPer-label classification reports:")
    for i, lbl in enumerate(label_cols):
        print(f"--- {lbl} ---")
        print(classification_report(y_test[:, i], y_pred[:, i], zero_division=0))

    # Save predictions and probabilities with meta
    preds_df = pd.DataFrame(y_pred, columns=[f"pred_{c}" for c in label_cols])
    proba_df = pd.DataFrame(y_proba, columns=[f"proba_{c}" for c in label_cols])
    true_df = pd.DataFrame(y_test, columns=[f"true_{c}" for c in label_cols])

    results_df = pd.concat([meta_test.reset_index(drop=True),
                            true_df.reset_index(drop=True),
                            preds_df.reset_index(drop=True),
                            proba_df.reset_index(drop=True)], axis=1)
    results_csv = os.path.join(args.out_dir, "test_predictions.csv")
    results_df.to_csv(results_csv, index=False)
    print("Saved test predictions to", results_csv)

    # Save model + label columns
    model_path = os.path.join(args.out_dir, "ovr_rf_clip_model.joblib")
    joblib.dump({"model": ovr, "label_cols": label_cols}, model_path)
    print("Saved model to", model_path)

    # Save feature importances (per-label)
    try:
        fi = {}
        skipped_labels = []
        for lbl, est in zip(label_cols, ovr.estimators_):
            # Check if the estimator has feature_importances_ (skip constant predictors)
            if hasattr(est, 'feature_importances_'):
                fi[lbl] = est.feature_importances_
            else:
                # Constant predictor (only one class in training data)
                fi[lbl] = np.zeros(X_train.shape[1])  # all zeros
                skipped_labels.append(lbl)
        
        if fi:
            fi_df = pd.DataFrame(fi)
            fi_df.index = [f"dim_{i}" for i in range(fi_df.shape[0])]
            fi_path = os.path.join(args.out_dir, "feature_importances_per_label.csv")
            fi_df.to_csv(fi_path)
            print("Saved feature importances to", fi_path)
            if skipped_labels:
                print(f"  Note: Labels with constant predictions (set to zeros): {skipped_labels}")
    except Exception as e:
        print("Could not save per-label feature importances:", e)

    print("ALL DONE.")

# -------------------------
# CLI
# -------------------------
if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--csv", required=True, help="CSV with 'filename' and label columns")
    p.add_argument("--images-dir", required=True, help="Directory root for images (if filenames are relative)")
    p.add_argument("--out-dir", required=True, help="Output directory to save embeddings, models, CSVs")
    p.add_argument("--clip-model", default="openai/clip-vit-base-patch32", help="CLIP model name")
    p.add_argument("--batch-size", type=int, default=32, help="CLIP batch size")
    p.add_argument("--n-estimators", type=int, default=200, help="RandomForest n_estimators")
    p.add_argument("--max-depth", type=int, default=None, help="RandomForest max_depth")
    p.add_argument("--n-jobs", type=int, default=-1, help="n_jobs for RF / One-vs-Rest")
    p.add_argument("--test-size", type=float, default=0.2, help="Fraction used for test set")
    p.add_argument("--force-cpu", action="store_true", help="Don't use CUDA even if available")
    p.add_argument("--class-weight-balanced", action="store_true", help="Use class_weight='balanced' for RF")
    args = p.parse_args()
    main(args)
