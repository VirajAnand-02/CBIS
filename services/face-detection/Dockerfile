# Face Detection Service Dockerfile with GPU Support
FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

# Set working directory
WORKDIR /app
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies (Python, pip, OpenCV libs, and build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-venv python3-pip \
    build-essential ca-certificates wget git \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip first (older pip doesn't support --break-system-packages)
RUN python3 -m pip install --upgrade pip

# Bypass externally-managed-environment restriction
RUN python3 -m pip install --break-system-packages --upgrade setuptools wheel

# Copy requirements and app
COPY requirements.txt /app/requirements.txt
COPY app.py /app/app.py

# Install Python dependencies with GPU-enabled TensorFlow
RUN set -eux; \
    # Remove tensorflow and torch lines if present to install GPU versions
    grep -vE '^(tensorflow|torch)([<>=].*)?$' /app/requirements.txt > /tmp/reqs_no_gpu.txt || cp /app/requirements.txt /tmp/reqs_no_gpu.txt; \
    pip install --break-system-packages --no-cache-dir -r /tmp/reqs_no_gpu.txt; \
    # Install GPU-compatible TensorFlow
    pip install --break-system-packages --no-cache-dir "tensorflow[and-cuda]>=2.15.0"; \
    # Install GPU-compatible PyTorch (CUDA 12.4)
    pip install --break-system-packages --no-cache-dir "torch>=2.0.0" --index-url https://download.pytorch.org/whl/cu124

# Create directories
RUN mkdir -p face_crops temp_images

# Expose port
EXPOSE 8005

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python3 -c "import requests; r = requests.get('http://localhost:8005/health'); exit(0 if r.status_code==200 else 1)" || exit 1

# Run the application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8005", "--reload"]

# docker build -t face-dec-img .
# docker run --name face-detection --gpus all -p 8005:8005 -v ${PWD}:/app face-dec-img

# -e NEXTJS_API_URL=http://host.docker.internal:3000
