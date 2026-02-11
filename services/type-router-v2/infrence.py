#!/usr/bin/env python3
"""
inference_clip_rf.py

Simple inference script for the One-vs-Rest RandomForest trained on CLIP image embeddings.

Usage examples:
    # Predict from a directory (all images inside)
    python inference_clip_rf.py \
      --model-file outputs/ovr_rf_clip_model.joblib \
      --images-dir /path/to/images \
      --out-csv outputs/inference_results.csv

    # Predict from a CSV with 'filename' column (relative/absolute paths)
    python inference_clip_rf.py \
      --model-file outputs/ovr_rf_clip_model.joblib \
      --input-csv new_images.csv \
      --images-dir /path/to/images \
      --out-csv outputs/inference_results.csv

    # Use per-label thresholds:
    python inference_clip_rf.py \
      --model-file outputs/ovr_rf_clip_model.joblib \
      --images-dir /path/to/images \
      --thresholds thresholds.json \
      --out-csv outputs/inference_results.csv
"""

import os
import argparse
import json
from pathlib import Path
from tqdm import tqdm

import numpy as np
import pandas as pd
import joblib
from PIL import Image

import torch
from transformers import CLIPProcessor, CLIPModel

def compute_clip_embeddings(model, processor, image_paths, batch_size=32, device="cpu"):
    """Compute normalized CLIP embeddings for given image paths. Returns (embeddings, kept_idx)."""
    model.eval()
    emb_list = []
    kept_idx = []
    with torch.no_grad():
        for i in tqdm(range(0, len(image_paths), batch_size), desc="CLIP batches"):
            batch = image_paths[i:i+batch_size]
            images = []
            valid_indices = []
            for j, p in enumerate(batch):
                try:
                    img = Image.open(p).convert("RGB")
                    images.append(img)
                    valid_indices.append(i + j)
                except Exception as e:
                    print(f"Warning: failed to open {p}: {e}")
            if not images:
                continue
            inputs = processor(images=images, return_tensors="pt")
            inputs = {k: v.to(device) for k, v in inputs.items()}
            if device == "cuda":
                torch.cuda.synchronize()
            feats = model.get_image_features(**inputs)
            # L2 normalize per-vector
            feats = feats / feats.norm(dim=-1, keepdim=True)
            feats = feats.cpu().numpy()
            emb_list.append(feats)
            kept_idx.extend(valid_indices)
    if len(emb_list) == 0:
        return np.zeros((0, model.config.projection_dim if hasattr(model.config, "projection_dim") else 512)), []
    return np.vstack(emb_list), kept_idx

def load_image_list(images_dir=None, input_csv=None):
    """
    Return list of file paths and a DataFrame with metadata (if csv provided).
    If input_csv provided, expect 'filename' column. Filenames may be relative to images_dir.
    Otherwise, list all files under images_dir (non-recursive).
    """
    if input_csv:
        df = pd.read_csv(input_csv)
        if "filename" not in df.columns:
            raise ValueError("Input CSV must have 'filename' column.")
        paths = []
        for fn in df["filename"].tolist():
            p = Path(fn)
            if not p.is_absolute() and images_dir:
                p = Path(images_dir) / p
            paths.append(str(p))
        return paths, df
    else:
        # images_dir required
        if images_dir is None:
            raise ValueError("Either --input-csv or --images-dir must be provided.")
        p = Path(images_dir)
        files = [str(x) for x in p.iterdir() if x.is_file()]
        df = pd.DataFrame({"filename": [Path(f).name for f in files]})
        return files, df

def apply_thresholds(probas, label_cols, thresholds=None):
    """Convert probabilities (N, L) to binary preds (N, L) using thresholds dict or scalar."""
    if thresholds is None:
        thr = 0.5
        return (probas >= thr).astype(int)
    # thresholds can be a dict mapping label->float, or a single numeric value
    if isinstance(thresholds, (int, float)):
        return (probas >= float(thresholds)).astype(int)
    # thresholds expected dict
    thr_array = np.array([thresholds.get(lbl, 0.5) for lbl in label_cols], dtype=float)
    return (probas >= thr_array).astype(int)

def main(args):
    # Load model (joblib file saved by training script)
    model_bundle = joblib.load(args.model_file)
    if isinstance(model_bundle, dict) and "model" in model_bundle and "label_cols" in model_bundle:
        ovr = model_bundle["model"]
        label_cols = model_bundle["label_cols"]
    else:
        # fallback: assume joblib saved the estimator directly and user provided labels via CLI
        ovr = model_bundle
        if args.labels:
            label_cols = args.labels.split(",")
        else:
            raise ValueError("Model file doesn't contain label names; provide --labels comma-separated.")

    # Load CLIP model & processor
    device = "cuda" if torch.cuda.is_available() and not args.force_cpu else "cpu"
    print("Using device:", device)
    clip_model = CLIPModel.from_pretrained(args.clip_model).to(device)
    clip_processor = CLIPProcessor.from_pretrained(args.clip_model)

    # Build image list
    image_paths, meta_df = load_image_list(args.images_dir, args.input_csv)
    print(f"Found {len(image_paths)} image paths (note: some may be unreadable and will be skipped).")

    # Compute embeddings
    embeddings, kept_idx = compute_clip_embeddings(clip_model, clip_processor, image_paths,
                                                   batch_size=args.batch_size, device=device)
    if embeddings.shape[0] == 0:
        raise RuntimeError("No embeddings computed. Exiting.")

    # Keep only metadata rows for successfully processed images (if meta_df present)
    meta_kept = meta_df.iloc[kept_idx].reset_index(drop=True)

    # Predict probabilities
    try:
        probas = ovr.predict_proba(embeddings)
    except Exception:
        # fallback: stack per-estimator predict_proba
        probas = np.vstack([est.predict_proba(embeddings)[:, 1] for est in ovr.estimators_]).T

    # Apply thresholds
    thresholds = None
    if args.thresholds:
        with open(args.thresholds, "r") as f:
            thr_obj = json.load(f)
        # thr_obj may be dict {label: num} or scalar
        if isinstance(thr_obj, dict):
            thresholds = thr_obj
        elif isinstance(thr_obj, (int, float)):
            thresholds = float(thr_obj)
        else:
            raise ValueError("thresholds JSON should be either a dict or a numeric scalar.")
    preds = apply_thresholds(probas, label_cols, thresholds)

    # Build output DataFrame
    proba_df = pd.DataFrame(probas, columns=[f"proba_{c}" for c in label_cols])
    pred_df = pd.DataFrame(preds, columns=[f"pred_{c}" for c in label_cols])
    out_df = pd.concat([meta_kept.reset_index(drop=True), proba_df.reset_index(drop=True), pred_df.reset_index(drop=True)], axis=1)

    out_csv = args.out_csv if args.out_csv else "inference_results.csv"
    out_df.to_csv(out_csv, index=False)
    print(f"Saved inference CSV to: {out_csv}")
    print("Done.")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--model-file", required=True, help="joblib file saved by training (contains {'model', 'label_cols'})")
    p.add_argument("--clip-model", default="openai/clip-vit-base-patch32", help="CLIP model name")
    p.add_argument("--images-dir", default=None, help="Directory with images (or base for filenames in input CSV)")
    p.add_argument("--input-csv", default=None, help="CSV with 'filename' column (optional)")
    p.add_argument("--out-csv", default="inference_results.csv", help="Where to save results")
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--force-cpu", action="store_true", help="Don't use CUDA even if available")
    p.add_argument("--labels", default=None, help="Comma-separated label names (only needed if model file lacks them)")
    p.add_argument("--thresholds", default=None, help="JSON file with per-label thresholds (e.g. {'is_nsfw':0.4, 'is_document':0.6}) or scalar")
    args = p.parse_args()
    main(args)
