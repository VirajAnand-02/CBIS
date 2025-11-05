# CBIS Services Startup Guide

## Environment Setup

All services run in the `clip-env` conda environment:
```bash
conda activate clip-env
```

## Services Overview

| Service | Port | Purpose |
|---------|------|---------|
| CLIP Service | 8000 | Generate embeddings and captions |
| Type Router | 8001 | Classify image types (document, people, etc.) |
| NIMA Service | 8002 | Calculate aesthetic scores |
| Next.js App | 3000 | Frontend application |

## Starting Services

### Option 1: Using Batch Scripts (Windows)

**CLIP Service:**
```bash
cd E:\programming\CBIS_Project\clip
.\start_service.bat
```

**Type Router Service:**
```bash
cd E:\programming\CBIS_Project\TYPE_ROUTER
.\start_service.bat
```

### Option 2: Manual Commands

**CLIP Service:**
```bash
cd E:\programming\CBIS_Project\clip
conda activate clip-env
python -m uvicorn app:app --host 0.0.0.0 --port 8000
```

**Type Router Service:**
```bash
cd E:\programming\CBIS_Project\TYPE_ROUTER
conda activate clip-env
python type_router_service.py
```

**Next.js Application:**
```bash
cd E:\programming\CBIS_Project\next-js
npm run dev
```

## Configuration

### Type Router - Dummy Mode

The Type Router can run in two modes:

**Dummy Mode (Default):** Returns random classifications, useful for testing without the model file
- Edit `TYPE_ROUTER\.env` and set `USE_DUMMY_ROUTER=true`

**Real Mode:** Uses the actual trained Keras model
- Edit `TYPE_ROUTER\.env` and set `USE_DUMMY_ROUTER=false`
- Ensure `image_attribute_router.keras` is present in the TYPE_ROUTER directory

### Next.js Environment Variables

Create or edit `next-js\.env.local`:
```env
CLIP_SERVICE_URL=http://localhost:8000
TYPE_ROUTER_SERVICE_URL=http://localhost:8001
NIMA_SERVICE_URL=http://localhost:8002
```

## Testing Services

### Test CLIP Service
```bash
curl http://localhost:8000/health
```

### Test Type Router
```bash
curl http://localhost:8001/health
```

### Test with an Image
```bash
curl -X POST http://localhost:8001/classify_from_image \
  -H "Content-Type: application/json" \
  -d '{"url": "http://example.com/image.jpg"}'
```

## Troubleshooting

### PyTorch Version Error
If you see "ValueError: Due to a serious vulnerability issue in torch.load":
- Ensure PyTorch 2.6.0+ is installed: `pip show torch`
- Reinstall if needed: `pip install torch==2.6.0 torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124`

### Model Not Found
- Check that you're in the correct directory
- Verify `image_attribute_router.keras` exists in TYPE_ROUTER folder
- Or enable dummy mode by setting `USE_DUMMY_ROUTER=true` in `.env`

### Conda Activation Issues
- Ensure conda is initialized in your shell
- Try running `conda init powershell` and restart PowerShell
- Or use batch scripts which handle activation automatically

## GPU Support

All services are configured to use GPU when available:
- CUDA 12.4 support (PyTorch 2.6.0+cu124)
- Tested on NVIDIA GeForce GTX 1650 (4GB VRAM)
- Falls back to CPU if GPU unavailable
