"""
nima_score.py

Compute a NIMA (Neural Image Assessment) score for an image using a MobileNet backbone.
- Outputs: predicted distribution (10 bins), mean score, stddev.
- Optionally load pretrained weights (local .h5 file).
Requirements:
    pip install tensorflow pillow numpy
Usage:
    python nima_score.py /path/to/image.jpg --weights path/to/nima_mobilenet_weights.h5
If no weights file is provided, the model will be creatpythoned but untrained (useful if you want to load your own weights).
"""

import argparse
import numpy as np
from PIL import Image
import tensorflow as tf

# ----------------------------
# Model builder (MobileNet base)
# ----------------------------
def build_nima_mobilenet(input_shape=(224, 224, 3)):
    """
    Build a NIMA-like model using MobileNet as backbone.
    Output: softmax over 10 classes (scores 1..10).
    """
    base = tf.keras.applications.MobileNet(
        input_shape=input_shape, include_top=False, weights=None  # weights=None by default
    )
    x = base.output
    x = tf.keras.layers.GlobalAveragePooling2D()(x)
    x = tf.keras.layers.Dense(1024, activation="relu")(x)
    x = tf.keras.layers.Dropout(0.5)(x)
    # final layer: 10 outputs (score 1..10), softmax gives predicted distribution
    outputs = tf.keras.layers.Dense(10, activation="softmax", name="nima_scores")(x)
    model = tf.keras.Model(inputs=base.input, outputs=outputs)
    return model

# ----------------------------
# Image preprocessing
# ----------------------------
def load_and_preprocess_image(path, target_size=(224, 224)):
    img = Image.open(path).convert("RGB")
    img = img.resize(target_size, Image.BILINEAR)
    arr = np.asarray(img).astype("float32")
    # MobileNet preprocessing: scale [-1,1]
    arr = tf.keras.applications.mobilenet.preprocess_input(arr)
    # model expects batch dimension
    arr = np.expand_dims(arr, axis=0)
    return arr

# ----------------------------
# Score computation utilities
# ----------------------------
def distribution_to_stats(dist):
    """
    dist: numpy array shape (10,) probabilities for scores 1..10
    Returns: mean, std
    mean = sum(i * p_i) with i in [1..10]
    std = sqrt(E[X^2] - E[X]^2)
    """
    bins = np.arange(1, 11).astype(np.float32)  # 1..10
    mean = float(np.sum(bins * dist))
    mean_sq = float(np.sum((bins ** 2) * dist))
    std = float(np.sqrt(max(0.0, mean_sq - mean ** 2)))
    return mean, std

# ----------------------------
# Main CLI
# ----------------------------
def main():
    parser = argparse.ArgumentParser(description="Compute NIMA score for an image (MobileNet backbone).")
    parser.add_argument("image", help="Path to image file")
    parser.add_argument("--weights", default=None, help="Path to Keras .h5 weights for NIMA MobileNet (optional)")
    parser.add_argument("--size", type=int, default=224, help="Input size (default 224 for MobileNet)")
    args = parser.parse_args()

    model = build_nima_mobilenet(input_shape=(args.size, args.size, 3))
    if args.weights:
        print(f"Loading weights from {args.weights} ...")
        # Replace your current load_weights call with this:
        model.load_weights(args.weights, by_name=True, skip_mismatch=True)

    else:
        print("No weights provided: model is randomly initialized. Provide pretrained weights for meaningful scores.")

    x = load_and_preprocess_image(args.image, target_size=(args.size, args.size))
    probs = model.predict(x, verbose=0)[0]  # shape (10,)
    mean, std = distribution_to_stats(probs)

    # Present results
    np.set_printoptions(precision=4, suppress=True)
    print("\nPredicted distribution (scores 1..10):")
    print(probs)
    print(f"\nNIMA mean score: {mean:.4f}")
    print(f"NIMA stddev: {std:.4f}")

if __name__ == "__main__":
    main()
