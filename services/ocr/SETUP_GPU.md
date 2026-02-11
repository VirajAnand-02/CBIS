# GPU Setup for OCR Service

## Problem
PyTorch is installed as CPU-only version (`2.9.1+cpu`), preventing GPU acceleration.

## Solution

### 1. Uninstall CPU-only PyTorch

```powershell
conda activate ocr
pip uninstall torch torchvision torchaudio
```

### 2. Install PyTorch with CUDA Support

For **CUDA 12.1** (recommended for RTX 4070):
```powershell
conda install pytorch torchvision torchaudio pytorch-cuda=12.1 -c pytorch -c nvidia -y
```

For **CUDA 11.8** (if CUDA 12.1 doesn't work):
```powershell
conda install pytorch torchvision torchaudio pytorch-cuda=11.8 -c pytorch -c nvidia -y
```

### 3. Verify Installation

```powershell
python -c "import torch; print('CUDA available:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None')"
```

Expected output:
```
CUDA available: True
GPU: NVIDIA GeForce RTX 4070
```

### 4. Check CUDA Version

First, check your NVIDIA driver CUDA version:
```powershell
nvidia-smi
```

Look for the CUDA Version in the top right (e.g., `CUDA Version: 12.9`).

Then install the corresponding PyTorch version. For CUDA 12.x, use `pytorch-cuda=12.1`.

## Font Issue Fix (Synthesis)

The synthesis failure is due to missing fonts. Install fonts:

### Option 1: Install Matplotlib Fonts
```powershell
pip install matplotlib
```

### Option 2: Use System Fonts
The updated `tst_docTR.py` now tries multiple fonts:
1. Arial (Windows default)
2. Times New Roman (Windows default)
3. System default

This should resolve the "cannot open resource" error.

## Performance Comparison

**CPU (current):**
- Model loading: ~3.9s
- OCR inference: ~4.8s
- Total: ~14.9s

**GPU (expected after fix):**
- Model loading: ~1.5s (with FP16)
- OCR inference: ~0.2-0.3s
- Total: ~2-3s

**Speed improvement: ~5-7x faster**

## Troubleshooting

### Still Using CPU After Install?

1. Restart PowerShell/Terminal
2. Reactivate conda environment: `conda activate ocr`
3. Verify: `python -c "import torch; print(torch.cuda.is_available())"`

### CUDA Out of Memory?

The code already uses FP16 precision to reduce memory usage. If you still get OOM:
```python
# In tst_docTR.py, comment out the .half() line
# model.half()  # Comment this out
```

### Wrong CUDA Version?

If PyTorch CUDA version doesn't match your driver:
- Check: `nvidia-smi` (shows max supported CUDA)
- Install matching PyTorch CUDA version
- PyTorch CUDA version can be <= driver CUDA version
