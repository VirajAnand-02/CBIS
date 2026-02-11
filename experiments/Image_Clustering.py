# streamlit_cluster_app.py
# python -m streamlit run .\Image_Clustering.py

import streamlit as st
from pathlib import Path
from PIL import Image
import numpy as np
import pandas as pd
import os
import shutil
import math
from io import BytesIO

import torch
from transformers import CLIPProcessor, CLIPModel

import hdbscan
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.manifold import TSNE
import umap

import matplotlib.pyplot as plt

st.set_page_config(layout="wide", page_title="CLIP HDBSCAN Explorer")

# -------------------------
# Utility & cached helpers
# -------------------------
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}


def find_images(folder: Path):
    imgs = []
    for p in folder.rglob("*"):
        if p.suffix.lower() in IMAGE_EXTS and p.is_file():
            imgs.append(p)
    imgs.sort()
    return imgs


@st.cache_resource(show_spinner=False)
def load_clip_models(model_name: str = "openai/clip-vit-base-patch32", use_safetensors: bool = True):
    """
    Cached model + processor loader (keeps them in memory across runs).
    """
    model = CLIPModel.from_pretrained(model_name, use_safetensors=use_safetensors)
    processor = CLIPProcessor.from_pretrained(model_name, use_fast=True)
    return model, processor


@st.cache_data(show_spinner=False)
def compute_embeddings_cached(image_paths_tuple, model_name, batch_size: int, normalize: bool, device_str: str):
    """
    Compute CLIP embeddings for a list of image paths. Cached by the tuple of paths + model_name.
    Returns list(filenames), np.ndarray embeddings (n x d).
    """
    # Convert tuple back to list
    image_paths = list(image_paths_tuple)
    device = torch.device(device_str)
    model, processor = load_clip_models(model_name=model_name)
    model = model.to(device)
    model.eval()
    all_feats = []
    filenames = []

    # process in batches
    for i in range(0, len(image_paths), batch_size):
        batch_paths = image_paths[i : i + batch_size]
        images = []
        for p in batch_paths:
            try:
                img = Image.open(p).convert("RGB")
                images.append(img)
                filenames.append(str(p))
            except Exception as e:
                st.warning(f"Failed to open {p}: {e}")

        if not images:
            continue

        inputs = processor(images=images, return_tensors="pt").to(device)
        with torch.no_grad():
            feats = model.get_image_features(**inputs)
        feats = feats.cpu().numpy()
        if normalize:
            norms = np.linalg.norm(feats, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            feats = feats / norms
        all_feats.append(feats)

    if all_feats:
        embeddings = np.vstack(all_feats)
    else:
        embeddings = np.zeros((0, 512), dtype=np.float32)

    return filenames, embeddings


def reduce_pca(embeddings, n_components):
    if n_components is None or n_components <= 0 or n_components >= embeddings.shape[1]:
        return embeddings, None
    pca = PCA(n_components=n_components, random_state=42)
    reduced = pca.fit_transform(embeddings)
    return reduced, pca


def compute_hdbscan(embeddings, min_cluster_size, min_samples, metric="euclidean"):
    """
    HDBSCAN clustering. 
    Note: If embeddings are normalized, euclidean distance approximates cosine distance.
    Alternatively, use metric='precomputed' with a cosine distance matrix.
    """
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=int(min_cluster_size),
        min_samples=int(min_samples),
        metric=metric,
        core_dist_n_jobs=-1
    )
    labels = clusterer.fit_predict(embeddings)
    return labels, clusterer


def plot_2d_projection(embeddings_2d, labels, width=700, height=500, title="2D projection"):
    """Return matplotlib figure for embedding 2D plot colored by labels"""
    unique_labels = sorted(set(labels))
    fig, ax = plt.subplots(figsize=(8, 6))
    for lbl in unique_labels:
        mask = np.array(labels) == lbl
        if lbl == -1:
            name = "noise"
            alpha = 0.4
            s = 10
        else:
            name = f"cluster {lbl}"
            alpha = 0.8
            s = 20
        ax.scatter(embeddings_2d[mask, 0], embeddings_2d[mask, 1], label=name, s=s, alpha=alpha)
    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left")
    ax.set_title(title)
    return fig


def make_thumbnail(path, size=(160, 160)):
    try:
        img = Image.open(path)
        img.thumbnail(size)
        bio = BytesIO()
        img.save(bio, format="PNG")
        bio.seek(0)
        return bio
    except Exception:
        return None


# -------------------------
# Sidebar: controls
# -------------------------
st.sidebar.title("Data & Embeddings")
image_dir = st.sidebar.text_input("Image folder (path)", value="images")
image_dir_path = Path(image_dir)

use_precomputed = st.sidebar.checkbox("Load embeddings from .npy file (skip CLIP compute)")
precomputed_path = None
if use_precomputed:
    precomputed_path = st.sidebar.text_input("Embeddings .npy file path (contains numpy array)", value="embeddings.npy")
    filenames_csv = st.sidebar.text_input("Filenames CSV path (optional, maps index -> filename)", value="filenames.csv")

st.sidebar.markdown("---")
st.sidebar.title("CLIP / compute settings")
model_name = st.sidebar.text_input("CLIP model name", value="openai/clip-vit-base-patch32")
device_default = "cuda" if torch.cuda.is_available() else "cpu"
device = st.sidebar.selectbox("Device", options=[device_default, "cpu"], index=0)
batch_size = st.sidebar.number_input("Batch size (embedding)", min_value=1, max_value=128, value=32, step=1)
normalize = st.sidebar.checkbox("Normalize embeddings", value=True)
st.sidebar.markdown("---")
st.sidebar.title("Dimensionality & clustering")

pca_components = st.sidebar.slider("PCA components (0 = skip)", min_value=0, max_value=512, value=64, step=1)
umap_components = st.sidebar.checkbox("Use UMAP for 2D visualization (else PCA/TSNE)", value=True)

min_cluster_size = st.sidebar.slider("HDBSCAN min_cluster_size", min_value=2, max_value=100, value=5, step=1)
min_samples = st.sidebar.slider("HDBSCAN min_samples", min_value=1, max_value=50, value=5, step=1)

st.sidebar.markdown("---")
if st.sidebar.button("(Re)compute CLIP embeddings"):
    # trigger recompute by clearing cache for compute_embeddings_cached
    compute_embeddings_cached.clear()

st.sidebar.caption("Tip: For interactive sliders, compute embeddings first (can be slow on first run).")

# -------------------------
# Main UI
# -------------------------
st.title("CLIP + HDBSCAN interactive explorer")
col_left, col_right = st.columns([1, 3])

with col_left:
    st.header("Dataset")
    if not image_dir_path.exists():
        st.error(f"Path not found: {image_dir_path}")
        st.stop()

    image_paths = find_images(image_dir_path)
    st.write(f"Found {len(image_paths)} images in `{image_dir_path}`")
    if len(image_paths) == 0:
        st.stop()

    if use_precomputed and precomputed_path and Path(precomputed_path).exists():
        st.success("Loading precomputed embeddings")
        embeddings = np.load(precomputed_path)
        # load filenames if provided by CSV or CSV path
        if filenames_csv and Path(filenames_csv).exists():
            df_names = pd.read_csv(filenames_csv, header=None)
            filenames = df_names.iloc[:, 0].astype(str).tolist()
        else:
            # assume same ordering as images found on disk
            filenames = [str(p) for p in image_paths]
    else:
        # Compute CLIP embeddings (cached)
        with st.spinner("Computing CLIP embeddings (this runs once and is cached)..."):
            # convert Path objects to tuple of strings for caching key
            paths_tuple = tuple(str(p) for p in image_paths)
            filenames, embeddings = compute_embeddings_cached(paths_tuple, model_name, batch_size, normalize, device)

        st.success(f"Computed embeddings shape: {embeddings.shape}")

    # optional save embeddings
    if st.button("Save embeddings to embeddings.npy"):
        np.save("embeddings.npy", embeddings)
        pd.DataFrame(filenames).to_csv("filenames.csv", index=False, header=False)
        st.success("Saved embeddings.npy and filenames.csv in current folder")

with col_right:
    st.header("Clustering controls & results")

    # reduce dimensions for clustering
    embeddings_for_clustering, pca_obj = reduce_pca(embeddings, None if pca_components == 0 else pca_components)

    st.markdown(f"**Embeddings used for clustering:** {embeddings_for_clustering.shape[1]} dims (PCA={pca_components})")
    # run HDBSCAN on current min_cluster_size/min_samples
    # Using euclidean metric on normalized embeddings (approximates cosine distance)
    labels, clusterer = compute_hdbscan(embeddings_for_clustering, min_cluster_size=min_cluster_size, min_samples=min_samples, metric="euclidean")

    # Compute counts
    label_counts = pd.Series(labels).value_counts().sort_index()
    n_clusters = len([l for l in set(labels) if l != -1])
    st.metric("Number of clusters (excluding noise)", n_clusters)
    st.write("Cluster counts (label:count):")
    st.write(label_counts.to_frame("count"))

    # show silhouette score if meaningful
    try:
        if len(set(labels)) > 1 and -1 not in set(labels):
            sil = silhouette_score(embeddings_for_clustering, labels, metric="cosine")
            st.write(f"Silhouette score: {sil:.4f}")
        else:
            st.write("Silhouette score: N/A (need >=2 clusters without only noise)")
    except Exception as e:
        st.write("Silhouette score: error:", e)

    # 2D projection (UMAP or PCA)
    st.subheader("2D projection")
    # compute or reuse 2D projection cached in session state for speed
    if "proj_2d" not in st.session_state or st.session_state.get("proj_shape") != embeddings_for_clustering.shape:
        with st.spinner("Computing 2D projection..."):
            try:
                if umap_components:
                    reducer = umap.UMAP(n_components=2, random_state=42)
                    proj2d = reducer.fit_transform(embeddings_for_clustering)
                else:
                    pca2 = PCA(n_components=2, random_state=42)
                    proj2d = pca2.fit_transform(embeddings_for_clustering)
            except Exception:
                # fallback to TSNE for small datasets
                proj2d = TSNE(n_components=2, init="pca", random_state=42).fit_transform(embeddings_for_clustering)
        st.session_state["proj_2d"] = proj2d
        st.session_state["proj_shape"] = embeddings_for_clustering.shape
    else:
        proj2d = st.session_state["proj_2d"]

    fig = plot_2d_projection(proj2d, labels)
    st.pyplot(fig)

    # allow picking a cluster to view thumbnails
    st.subheader("Browse cluster images")
    cluster_choices = ["noise (-1)"] + [f"{c}" for c in sorted(set(labels) - {-1})]
    # default select -1 if noise present, else first cluster
    default_sel = 0 if -1 in set(labels) else (1 if len(cluster_choices) > 1 else 0)
    selected = st.selectbox("Choose cluster", cluster_choices, index=default_sel)

    if selected == "noise (-1)":
        sel_label = -1
    else:
        sel_label = int(selected)

    sel_idx = [i for i, lbl in enumerate(labels) if lbl == sel_label]
    st.write(f"Images in selected cluster: {len(sel_idx)}")

    # show up to 80 thumbnails, paginated
    per_page = st.slider("Thumbnails per page", min_value=8, max_value=80, value=24, step=8)
    page = st.number_input("Page", min_value=1, max_value=max(1, math.ceil(len(sel_idx) / per_page)), value=1, step=1)
    start = (page - 1) * per_page
    end = start + per_page
    sel_idx_page = sel_idx[start:end]

    # display thumbnails in a grid
    cols = st.columns(6)
    for i, idx in enumerate(sel_idx_page):
        try:
            thumb_buf = make_thumbnail(filenames[idx])
            col = cols[i % 6]
            if thumb_buf:
                col.image(thumb_buf, use_container_width=True)
            else:
                col.write("Failed to load")
            col.caption(Path(filenames[idx]).name)
        except Exception as e:
            st.write("Error loading thumbnail:", e)

    # allow exporting current cluster assignment to CSV and copying files into cluster folders
    if st.button("Export cluster CSV"):
        df = pd.DataFrame({"filename": filenames, "label": labels})
        df.to_csv("clusters_streamlit.csv", index=False)
        st.success("Saved clusters_streamlit.csv")

    if st.button("Copy cluster files into 'clustered_streamlit' folder (copy)"):
        out_base = Path("clustered_streamlit")
        if out_base.exists():
            # avoid accidental overwrite - ask user to remove first
            st.warning("'clustered_streamlit' already exists. Please remove it first or rename.")
        else:
            for fname, lbl in zip(filenames, labels):
                src = Path(fname)
                if lbl == -1:
                    sub = out_base / "cluster_noise"
                else:
                    sub = out_base / f"cluster_{lbl}"
                sub.mkdir(parents=True, exist_ok=True)
                dst = sub / src.name
                try:
                    shutil.copy2(src, dst)
                except Exception as e:
                    st.warning(f"Failed to copy {src} -> {dst}: {e}")
            st.success("Copied files to 'clustered_streamlit'")

st.sidebar.markdown("---")
st.sidebar.write("Made with ❤️ — drag the sliders to change min_cluster_size/min_samples and explore clusters live.")
