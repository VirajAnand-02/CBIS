# Docker Updates for FACE_DETECTION Service

## Summary

All Docker-related files have been updated to include the FACE_DETECTION service (port 8005).

## Files Updated

### 1. `docker-compose.yml` ✅
**Changes:**
- Added `face-detection` service definition
- Port: 8005
- Container name: `cbis-face-detection`
- Added environment variables: DATABASE_URL, RECOGNITION_THRESHOLD, MIN_CONFIDENCE, MIN_FACE_SIZE
- Added volumes:
  - `./next-js/storage:/app/storage:ro` (read-only access to uploaded images)
  - `insightface-models:/root/.insightface` (model cache)
  - `./FACE_DETECTION/face_crops:/app/face_crops` (face crop storage)
- Health check with 60s start period (allows time for model loading)
- Updated Type Router V1 (Legacy) port from 8005 to 8006

### 2. `docker-build-all.ps1` ✅
**Changes:**
- Added Face Detection to the services array
- Tag: `cbis-face-detection:latest`
- Path: `.\FACE_DETECTION`

### 3. `docker-start.ps1` ✅
**Changes:**
- Added `cbis-face-detection` to required images check
- Added Face Detection URL to service URLs display: `http://localhost:8005/docs`

### 4. `docker-health-check.ps1` ✅
**Changes:**
- Added Face Detection to health check services array
- URL: `http://localhost:8005/health`
- Port: 8005

### 5. `DOCKER_QUICKSTART.md` ✅
**Changes:**
- Updated Services Overview table with Face Detection
- Added Face Detection to API Endpoints section
- Added Face Detection to manual health check commands
- Updated directory structure to include FACE_DETECTION/

### 6. `DOCKER_SETUP.md` ✅
**Changes:**
- Updated Architecture table with Face Detection
- Changed Type Router V1 port from 8005 to 8006
- Added Face Detection health check command

### 7. `docs/SERVICES_GUIDE.md` ✅
**Changes:**
- Updated Services Overview table
- Added Face Detection service (port 8005)
- Added Query Optimizer and Search Router (previously missing)

### 8. `.env.example` ✅ (NEW FILE)
**Created at project root with:**
- DATABASE_URL for Face Detection service
- PostgreSQL credentials for docker-compose.full.yml
- Face Detection configuration
- Inter-service URLs for all microservices

## Service Configuration

### Face Detection Service Details

**Port:** 8005  
**Container:** cbis-face-detection  
**Dependencies:**
- Database: PostgreSQL (requires DATABASE_URL env var)
- Storage: Read-only access to `next-js/storage/`

**Environment Variables:**
```env
DATABASE_URL=postgresql://user:password@host:5432/database
RECOGNITION_THRESHOLD=0.4
MIN_CONFIDENCE=0.6
MIN_FACE_SIZE=40
STORAGE_BASE_PATH=/app/storage
```

**Volumes:**
- `./next-js/storage:/app/storage:ro` - Access uploaded images
- `insightface-models:/root/.insightface` - Cache InsightFace models (~1GB)
- `./FACE_DETECTION/face_crops:/app/face_crops` - Store detected face crops

**Health Check:**
- Test: `python -c "import requests; requests.get('http://localhost:8005/health')"`
- Interval: 30s
- Timeout: 10s
- Retries: 3
- Start period: 60s (longer due to model loading)

## Complete Service List

| Service | Port | Container Name | Status |
|---------|------|----------------|--------|
| CLIP | 8000 | cbis-clip | ✅ Active |
| Type Router V2 | 8001 | cbis-type-router-v2 | ✅ Active |
| NIMA | 8002 | cbis-nima | ✅ Active |
| Query Optimizer | 8003 | cbis-query-optimizer | ✅ Active |
| Search Router | 8004 | cbis-search-router | ✅ Active |
| **Face Detection** | **8005** | **cbis-face-detection** | **✅ NEW** |
| Type Router V1 | 8006 | cbis-type-router-v1 | ⚠️ Legacy (commented) |

## Usage

### Setup Environment

1. Copy the example environment file:
```powershell
cp .env.example .env
```

2. Edit `.env` and update DATABASE_URL with your Supabase connection string:
```env
DATABASE_URL=postgresql://user:password@aws-1-ap-south-1.pooler.supabase.com:5432/postgres
```

### Build and Start

```powershell
# Build all services including Face Detection
.\docker-build-all.ps1

# Start all services
.\docker-start.ps1

# Check health (should show 6 services)
.\docker-health-check.ps1
```

### Verify Face Detection

```powershell
# Check health
curl http://localhost:8005/health

# View API documentation
# Open: http://localhost:8005/docs

# Test face detection endpoint
curl -X POST http://localhost:8005/detect `
  -H "Content-Type: application/json" `
  -d '{"blob_id": "your-blob-id-here"}'
```

## Docker Compose Commands

```bash
# Start only Face Detection
docker-compose up -d face-detection

# View Face Detection logs
docker-compose logs -f face-detection

# Restart Face Detection
docker-compose restart face-detection

# Stop Face Detection
docker-compose stop face-detection

# Rebuild Face Detection
docker-compose build --no-cache face-detection
docker-compose up -d face-detection
```

## Troubleshooting

### Face Detection won't start

**Check logs:**
```bash
docker-compose logs face-detection
```

**Common issues:**
1. **DATABASE_URL not set**: Edit `.env` file with correct connection string
2. **Storage mount error**: Ensure `next-js/storage/` directory exists
3. **Model download**: First startup downloads ~1GB InsightFace models (takes 5-10 min)
4. **Memory**: Face Detection needs ~2-4GB RAM for model inference

### Health check fails

Face Detection has a 60s start period because:
- InsightFace models need to be downloaded (first run)
- Models need to be loaded into memory (~1-2GB)
- GPU initialization (if available)

Wait 1-2 minutes after starting before checking health.

### Database connection issues

Ensure your DATABASE_URL in `.env` is correct:
```env
# Supabase format
DATABASE_URL=postgresql://postgres.xxxxx:password@aws-0-region.pooler.supabase.com:5432/postgres

# Local PostgreSQL
DATABASE_URL=postgresql://user:password@localhost:5432/cbis
```

## Next Steps

1. ✅ Updated all Docker files
2. ⏳ Create `.env` file from `.env.example`
3. ⏳ Run SQL migration (see `FACE_MIGRATION_GUIDE.md`)
4. ⏳ Build and start services
5. ⏳ Test Face Detection endpoint
6. ⏳ Integrate with Next.js frontend

## Integration with Next.js

Once Face Detection is running, update `next-js/.env.local`:

```env
FACE_DETECTION_SERVICE_URL=http://localhost:8005
```

The service will be available at:
- API: `http://localhost:8005`
- Docs: `http://localhost:8005/docs`
- Health: `http://localhost:8005/health`

## Notes

- Face Detection requires database access (persons and face_instances tables)
- First startup will be slower due to model downloads
- InsightFace models are cached in Docker volume: `insightface-models`
- Face crops are stored locally in `FACE_DETECTION/face_crops/`
- Service runs on CPU by default (GPU support can be enabled with nvidia-docker)
