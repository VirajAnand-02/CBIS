# Type Router V2 Service

FastAPI service for multi-label image classification using CLIP embeddings and Random Forest classifier.

## Overview

Type Router V2 uses a two-stage approach:
1. **CLIP (Vision Transformer)**: Extracts semantic embeddings from images
2. **Random Forest (One-vs-Rest)**: Performs multi-label classification on embeddings

This approach is more efficient and accurate than the V1 approach which used raw pixel values.

## Labels

The model classifies images into 10 categories:

**Primary Types (8):**
- `is_document` - Scanned documents, PDFs, forms
- `is_handwritten` - Handwritten notes, sketches
- `has_scene_text` - Images containing visible text (signs, captions)
- `has_people_faces` - Images with human faces
- `is_screenshot` - Screenshots of applications, websites
- `is_art_illustration` - Artwork, illustrations, drawings
- `has_machine_code` - Code snippets, terminal outputs
- `is_natural_image` - Natural scenes, landscapes, objects

**Quality Tags (2):**
- `is_nsfw` - Not Safe For Work content
- `is_low_quality` - Low quality, blurry, or corrupted images

## Installation

### 1. Install Dependencies

```bash
pip install fastapi uvicorn pydantic python-dotenv numpy pandas joblib scikit-learn torch transformers pillow requests
```

Or use the provided script:
```powershell
.\start_service.ps1
```

### 2. Train the Model (First Time)

If you haven't trained the model yet:

```bash
python train_clip_rf.py \
  --csv gemini_image_classification_v2.csv \
  --images-dir ../path/to/your/images \
  --out-dir outputs \
  --n-estimators 200 \
  --batch-size 32
```

This will create:
- `outputs/ovr_rf_clip_model.joblib` - Trained Random Forest model
- `outputs/clip_embeddings.npy` - Precomputed CLIP embeddings
- `outputs/test_predictions.csv` - Test set results
- `outputs/feature_importances_per_label.csv` - Feature importance analysis

### 3. Configure Environment

Create or edit `.env` file:

```env
# Dummy mode for testing (returns random classifications)
USE_DUMMY_ROUTER=false

# Model configuration
MODEL_PATH=outputs/ovr_rf_clip_model.joblib
CLIP_MODEL=openai/clip-vit-base-patch32
THRESHOLD=0.5
```

## Usage

### Start the Service

**Windows (PowerShell):**
```powershell
.\start_service.ps1
```

**Linux/Mac:**
```bash
python type_router_service_v2.py
```

The service will start on `http://localhost:8001`

### API Endpoints

#### 1. Health Check
```bash
GET /health
```

Returns service status, model info, and available labels.

#### 2. Classify from CLIP Embedding
```bash
POST /classify
Content-Type: application/json

{
  "embedding": [0.1, 0.2, ..., 0.512],  // 512-dim CLIP embedding
  "threshold": 0.5  // optional, default 0.5
}
```

**Response:**
```json
{
  "predictions": {
    "is_document": true,
    "has_people_faces": false,
    ...
  },
  "probabilities": {
    "is_document": 0.87,
    "has_people_faces": 0.23,
    ...
  }
}
```

#### 3. Classify from Image URL
```bash
POST /classify_from_image
Content-Type: application/json

{
  "url": "https://example.com/image.jpg",
  "threshold": 0.5  // optional
}
```

This endpoint downloads the image, computes CLIP embedding, and classifies it.

#### 4. Classify from Base64 Image
```bash
POST /classify_from_base64
Content-Type: application/json

{
  "image": "base64_encoded_image_data...",
  "threshold": 0.5  // optional
}
```

Useful for direct file uploads or when you have the image data already.

## Integration with CBIS Project

### Next.js API Integration

In your Next.js app, you can call the Type Router V2 service:

```typescript
// Example: Classify image on upload
async function classifyImage(blobId: string) {
  const imageUrl = `http://localhost:3000/api/blobs/${blobId}`;
  
  const response = await fetch('http://localhost:8001/classify_from_image', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ 
      url: imageUrl,
      threshold: 0.5 
    })
  });
  
  const result = await response.json();
  
  // result.predictions contains boolean flags
  // result.probabilities contains confidence scores
  
  return result;
}
```

### Processing Pipeline

The typical flow in the CBIS project:

1. **Upload**: Image uploaded to Next.js `/api/blobs`
2. **Storage**: Saved to filesystem, metadata to PostgreSQL
3. **CLIP Encoding**: CLIP service generates embedding
4. **Type Classification**: Type Router V2 classifies the image
5. **Attribute Storage**: Results saved to `blob_attributes` table
6. **Search**: Embeddings used for similarity search

## Development

### Dummy Mode

For testing without a trained model, enable dummy mode in `.env`:

```env
USE_DUMMY_ROUTER=true
```

This returns random classifications with probabilities between 0.1-0.9.

### Custom Thresholds

Different labels may require different thresholds for optimal precision/recall:

```python
# Per-label thresholds
thresholds = {
    "is_nsfw": 0.3,  # More sensitive (lower threshold)
    "is_document": 0.6,  # More strict (higher threshold)
    ...
}
```

Save as `thresholds.json` and use with inference script:

```bash
python infrence.py \
  --model-file outputs/ovr_rf_clip_model.joblib \
  --images-dir /path/to/images \
  --thresholds thresholds.json \
  --out-csv results.csv
```

### Retraining

To retrain the model with new data:

1. Update `gemini_image_classification_v2.csv` with new labeled examples
2. Run training script:
   ```bash
   python train_clip_rf.py --csv gemini_image_classification_v2.csv --images-dir /path/to/images --out-dir outputs
   ```
3. Restart the service to load the new model

## Architecture Comparison

### V1 (Old - Keras/CNN)
- Input: Raw image pixels (224×224×3)
- Model: Convolutional Neural Network
- Training: Requires large labeled dataset
- Inference: Slower (forward pass through CNN)
- Flexibility: Hard to update without retraining entire network

### V2 (New - CLIP + Random Forest)
- Input: CLIP embeddings (512-dim semantic vectors)
- Model: Random Forest (One-vs-Rest)
- Training: Can train on smaller datasets (CLIP provides transfer learning)
- Inference: Fast (simple tree traversal)
- Flexibility: Easy to add new labels or retrain incrementally

## Performance

On a typical dataset:
- **Micro F1**: ~0.85
- **Macro F1**: ~0.78
- **Jaccard Score**: ~0.72
- **Hamming Loss**: ~0.12

Inference speed:
- **With CLIP computation**: ~100-200ms per image (GPU)
- **From embedding**: ~5-10ms per image (CPU)

## Troubleshooting

### Model not found
```
ERROR: Model file not found at outputs/ovr_rf_clip_model.joblib
```
**Solution**: Train the model first using `train_clip_rf.py` or enable dummy mode.

### CUDA out of memory
```
RuntimeError: CUDA out of memory
```
**Solution**: Reduce `--batch-size` when training, or set `--force-cpu` flag.

### Wrong embedding dimension
```
Expected embedding dimension 512, got X
```
**Solution**: Ensure you're using the same CLIP model for embedding extraction and classification.

## License

Part of the CBIS (Content-Based Image Search) project.
