# OCR Service

Text extraction service using docTR with GPU acceleration support.

## Features

- **GPU Acceleration**: Automatic GPU detection and FP16 precision
- **High Accuracy**: Uses db_resnet50 (detection) + master (recognition) models
- **Batch Processing**: Process multiple images in one request
- **Image Enhancement**: Optional preprocessing with denoising and sharpening
- **Performance Metrics**: Detailed timing information for each operation
- **Confidence Scores**: Word-level confidence averaging

## Installation

```powershell
pip install -r requirements.txt
```

For GPU support, ensure PyTorch with CUDA is installed:
```powershell
conda install pytorch torchvision torchaudio pytorch-cuda=12.1 -c pytorch -c nvidia -y
```

## Usage

### Start the Service

```powershell
python app.py
```

Service runs on `http://localhost:8004` by default.

### API Endpoints

#### 1. Extract Text (Single Image)

```bash
POST /extract
```

**Parameters:**
- `file`: Image file (multipart/form-data)
- `apply_enhancements`: Boolean (optional) - Apply denoising/sharpening

**Example:**
```python
import requests

with open("document.png", "rb") as f:
    response = requests.post(
        "http://localhost:8004/extract",
        files={"file": f},
        params={"apply_enhancements": True}
    )

result = response.json()
print(result["text"])
print(f"Confidence: {result['confidence']:.2%}")
print(f"Inference time: {result['timings']['inference_s']:.3f}s")
```

**Response:**
```json
{
  "text": "Extracted text content...",
  "confidence": 0.95,
  "timings": {
    "preprocessing_s": 0.123,
    "doc_load_s": 0.045,
    "inference_s": 0.234,
    "aggregation_s": 0.012,
    "total_s": 0.414
  },
  "device": "cuda",
  "words_count": 145
}
```

#### 2. Extract Text (Batch)

```bash
POST /extract_batch
```

**Parameters:**
- `files`: Multiple image files
- `apply_enhancements`: Boolean (optional)

**Example:**
```python
files = [
    ("files", open("doc1.png", "rb")),
    ("files", open("doc2.png", "rb")),
    ("files", open("doc3.png", "rb"))
]

response = requests.post(
    "http://localhost:8004/extract_batch",
    files=files
)

for result in response.json()["results"]:
    print(f"{result['filename']}: {result['text'][:100]}...")
```

#### 3. Health Check

```bash
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "device": "cuda",
  "cuda_available": true,
  "model_loaded": true
}
```

#### 4. GPU Statistics

```bash
GET /stats
```

**Response:**
```json
{
  "device": "cuda",
  "cuda_available": true,
  "gpu_name": "NVIDIA GeForce RTX 4070",
  "cuda_version": "12.1",
  "vram_total_mb": 12288.0,
  "vram_allocated_mb": 1843.25,
  "vram_reserved_mb": 2048.0
}
```

## Integration with CBIS Project

### Update `start-services.ps1`

Add OCR service to startup script:

```powershell
# Start OCR Service (port 8004)
Write-Host "Starting OCR Service..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd OCR; python app.py"
Start-Sleep -Seconds 3
```

### Environment Variables

Add to Next.js `.env.local`:
```
OCR_SERVICE_URL=http://localhost:8004
```

### Next.js Integration

Add to `lib/preprocessing-manager.ts`:

```typescript
async callOCRService(imageUrl: string, applyEnhancements = false): Promise<OCRResult> {
  const ocrServiceUrl = process.env.OCR_SERVICE_URL || 'http://localhost:8004';
  
  try {
    // Fetch image
    const imageResponse = await fetch(imageUrl);
    const imageBlob = await imageResponse.blob();
    
    // Create form data
    const formData = new FormData();
    formData.append('file', imageBlob);
    
    // Call OCR service
    const response = await fetch(
      `${ocrServiceUrl}/extract?apply_enhancements=${applyEnhancements}`,
      {
        method: 'POST',
        body: formData
      }
    );
    
    if (!response.ok) {
      throw new Error(`OCR service error: ${response.statusText}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('Error calling OCR service:', error);
    throw error;
  }
}
```

## Performance

**GPU (RTX 4070):**
- Single image: ~200-300ms
- Batch (10 images): ~1.5-2s
- VRAM usage: ~1.8GB

**CPU:**
- Single image: ~1-2s
- Batch processing slower

## Configuration

### GPU Memory Management

The service automatically:
- Detects GPU availability
- Uses FP16 precision on GPU (2x faster, 50% less VRAM)
- Synchronizes CUDA for accurate timing
- Cleans up VRAM after batch processing

### Image Enhancement

When `apply_enhancements=true`:
- **Denoising**: cv2.fastNlMeansDenoisingColored (h=10)
- **Sharpening**: 3x3 kernel enhancement

Best for:
- Noisy scanned documents
- Low-quality photos of text
- Faded or degraded documents

## Model Architecture

- **Detection**: DB-ResNet50 (text region detection)
- **Recognition**: MASTER (sequence-to-sequence text recognition)
- **Pretrained**: Yes (docTR official weights)

## Troubleshooting

### GPU Not Detected

1. Check CUDA installation: `nvidia-smi`
2. Verify PyTorch CUDA: `python -c "import torch; print(torch.cuda.is_available())"`
3. Reinstall PyTorch with CUDA support

### Low Accuracy

1. Try `apply_enhancements=true` for noisy images
2. Ensure image resolution is sufficient (min 300 DPI for scanned docs)
3. Check if text is clearly visible and not heavily distorted

### Out of Memory

1. Reduce batch size
2. Process images sequentially instead of batch
3. Clear CUDA cache: `torch.cuda.empty_cache()`

## License

Same as CBIS Project
