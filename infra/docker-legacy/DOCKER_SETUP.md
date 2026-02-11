# CBIS Docker Setup Guide

This guide covers the Docker setup for all Python microservices in the CBIS (Content-Based Image Search) project.

## Architecture

The CBIS system consists of the following microservices:

| Service | Port | Description |
|---------|------|-------------|
| **CLIP** | 8000 | Image embeddings (512-dim) and caption generation |
| **Type Router V2** | 8001 | Multi-label image classification (CLIP + Random Forest) |
| **NIMA** | 8002 | Image quality assessment (aesthetic scoring) |
| **Query Optimizer** | 8003 | Search query enhancement and intent detection |
| **Search Router** | 8004 | Search strategy determination and routing |
| **Face Detection** | 8005 | Face detection and recognition using InsightFace |
| **Type Router V1** | 8006 | Legacy image classification (optional) |

## Prerequisites

- Docker Desktop (Windows/Mac) or Docker Engine (Linux)
- Docker Compose v2.0+
- At least 8GB RAM available for Docker
- 10GB free disk space

## Quick Start

### 1. Build All Services

```bash
# Build all services (without starting)
docker-compose build

# Or build individual services
docker-compose build clip
docker-compose build type-router-v2
docker-compose build nima
docker-compose build query-optimizer
docker-compose build search-router
```

### 2. Start All Services

```bash
# Start all services in detached mode
docker-compose up -d

# Or start specific services
docker-compose up -d clip nima

# View logs
docker-compose logs -f

# View logs for specific service
docker-compose logs -f clip
```

### 3. Check Service Health

```bash
# Check all running containers
docker-compose ps

# Test individual services
curl http://localhost:8000/health  # CLIP
curl http://localhost:8001/health  # Type Router V2
curl http://localhost:8002/health  # NIMA
curl http://localhost:8003/health  # Query Optimizer
curl http://localhost:8004/health  # Search Router
curl http://localhost:8005/health  # Face Detection
```

### 4. Stop Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes
docker-compose down -v

# Stop specific services
docker-compose stop clip nima
```

## Individual Service Build

You can also build and run services individually:

### CLIP Service

```bash
cd CLIP
docker build -t cbis-clip .
docker run -d -p 8000:8000 --name cbis-clip cbis-clip
```

### Type Router V2

```bash
cd TYPE_ROUTER_V2
docker build -t cbis-type-router-v2 .
docker run -d -p 8001:8001 --name cbis-type-router-v2 cbis-type-router-v2
```

### NIMA Service

```bash
cd NIMA
docker build -t cbis-nima .
docker run -d -p 8002:8002 --name cbis-nima cbis-nima
```

## Environment Configuration

Each service can be configured via environment variables in the `docker-compose.yml` file:

### CLIP Service
```yaml
environment:
  - CLIP_MODEL_NAME=openai/clip-vit-base-patch32
  - BLIP_MODEL_NAME=Salesforce/blip-image-captioning-base
```

### Type Router V2
```yaml
environment:
  - USE_DUMMY_ROUTER=false
  - MODEL_PATH=outputs/ovr_rf_clip_model.joblib
  - CLIP_MODEL=openai/clip-vit-base-patch32
  - THRESHOLD=0.5
```

### NIMA Service
```yaml
# No specific environment variables needed
# Model loaded from mobilenet_nima.h5
```

### Query Optimizer
```yaml
environment:
  - USE_DUMMY_QUERY_OPTIMIZER=false
```

### Search Router
```yaml
environment:
  - USE_DUMMY_SEARCH_ROUTER=false
```

## Volume Mounting

The docker-compose setup uses volumes for:

1. **Model Caching**: HuggingFace models are cached to avoid re-downloading
   - `clip-cache`: CLIP and BLIP models
   - `type-router-v2-cache`: Type Router V2 CLIP model

2. **Model Files**: Read-only mounts for trained models
   - `./NIMA/mobilenet_nima.h5`: NIMA quality assessment model
   - `./TYPE_ROUTER_V2/outputs`: Random Forest models for Type Router V2

## Networking

All services are connected via the `cbis-network` bridge network, allowing inter-service communication:

```yaml
networks:
  cbis-network:
    driver: bridge
```

Services can communicate using container names:
- `http://clip:8000`
- `http://type-router-v2:8001`
- `http://nima:8002`

## GPU Support (Optional)

To enable GPU acceleration for CLIP and Type Router V2:

1. Install [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)

2. Update `docker-compose.yml`:

```yaml
clip:
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
```

3. Use GPU-enabled base image in Dockerfile:

```dockerfile
FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04
```

## Troubleshooting

### Service fails to start

```bash
# Check logs
docker-compose logs <service-name>

# Common issues:
# 1. Model file missing - check volume mounts
# 2. Port conflict - change port in docker-compose.yml
# 3. Memory limit - increase Docker memory allocation
```

### Model download takes too long

First-time startup downloads large models (CLIP: ~600MB, BLIP: ~1GB). Subsequent starts use cached models.

```bash
# Check volume size
docker volume ls
docker volume inspect cbis_clip-cache
```

### Container health check fails

```bash
# Manually test health endpoint
docker exec cbis-clip python -c "import requests; print(requests.get('http://localhost:8000/health').json())"
```

### Out of memory errors

```bash
# Increase Docker memory in Docker Desktop settings
# Or set memory limits in docker-compose.yml:

services:
  clip:
    mem_limit: 4g
    memswap_limit: 4g
```

## Development Workflow

### Rebuild after code changes

```bash
# Rebuild specific service
docker-compose build clip
docker-compose up -d clip

# Or rebuild and restart in one command
docker-compose up -d --build clip
```

### Access container shell

```bash
# Interactive shell
docker exec -it cbis-clip /bin/bash

# Run Python REPL
docker exec -it cbis-clip python
```

### View real-time logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f clip type-router-v2
```

## Production Deployment

For production, consider:

1. **Use specific image tags** instead of `latest`
2. **Set resource limits** (CPU, memory)
3. **Enable health checks** (already configured)
4. **Use secrets** for sensitive data (API keys)
5. **Configure logging drivers** (e.g., json-file with rotation)
6. **Set restart policies** (already set to `unless-stopped`)

Example production configuration:

```yaml
clip:
  image: cbis-clip:1.0.0
  deploy:
    resources:
      limits:
        cpus: '2'
        memory: 4G
      reservations:
        cpus: '1'
        memory: 2G
  logging:
    driver: "json-file"
    options:
      max-size: "10m"
      max-file: "3"
```

## Integration with Next.js

The Next.js app should communicate with these services via their exposed ports:

```typescript
// Example: Call CLIP service
const response = await fetch('http://localhost:8000/embed', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ url: imageUrl })
});

const { embedding, caption } = await response.json();
```

For production, use Docker Compose to run all services together, or deploy to Kubernetes.

## Maintenance

### Update dependencies

```bash
# Update requirements.txt in each service
# Then rebuild:
docker-compose build --no-cache <service-name>
```

### Clean up

```bash
# Remove stopped containers
docker-compose rm

# Remove unused images
docker image prune -a

# Remove unused volumes
docker volume prune
```

### Backup models

```bash
# Backup volumes
docker run --rm -v cbis_clip-cache:/data -v $(pwd):/backup alpine tar czf /backup/clip-cache-backup.tar.gz /data

# Restore volumes
docker run --rm -v cbis_clip-cache:/data -v $(pwd):/backup alpine tar xzf /backup/clip-cache-backup.tar.gz -C /
```

## CI/CD Integration

Example GitHub Actions workflow:

```yaml
name: Build and Push Docker Images

on:
  push:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Build CLIP service
        run: docker build -t ghcr.io/${{ github.repository }}/cbis-clip:latest ./CLIP
      
      - name: Push to registry
        run: docker push ghcr.io/${{ github.repository }}/cbis-clip:latest
```

## Monitoring

Consider adding monitoring tools:

- **Prometheus** for metrics collection
- **Grafana** for visualization
- **Loki** for log aggregation

Example Prometheus integration:

```python
# Add to each service's app.py
from prometheus_client import make_asgi_app, Counter, Histogram

REQUEST_COUNT = Counter('requests_total', 'Total requests')
REQUEST_LATENCY = Histogram('request_latency_seconds', 'Request latency')

# Mount metrics endpoint
app.mount("/metrics", make_asgi_app())
```

## Support

For issues or questions:
- Check service logs: `docker-compose logs <service>`
- Test endpoints: `curl http://localhost:<port>/health`
- Review API documentation: `http://localhost:<port>/docs` (FastAPI auto-docs)
