# Face Detection Service - Quick Reference

## 🚀 Quick Start

```powershell
# One-command deployment
cd E:\programming\CBIS_Project\FACE_DETECTION
.\deploy.ps1 -Step all

# Manual steps
.\deploy.ps1 -Step db      # Run database migration
.\deploy.ps1 -Step deps    # Install dependencies
.\deploy.ps1 -Step start   # Start service
```

## 📡 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/detect` | POST | Enqueue face detection task |
| `/health` | GET | Service health & stats |
| `/queue/stats` | GET | Queue status |
| `/queue/clear` | GET | Clear queue |
| `/docs` | GET | Interactive API documentation |

## 💻 Usage Examples

### Detect Faces
```bash
curl -X POST http://localhost:8005/detect \
  -H "Content-Type: application/json" \
  -d '{
    "blob_id": "cm6abc123",
    "file_path": "storage/blobs/photo.jpg",
    "priority": 7
  }'
```

**Response:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "queue_position": 1,
  "blob_id": "cm6abc123"
}
```

### Check Health
```bash
curl http://localhost:8005/health
```

**Response:**
```json
{
  "status": "healthy",
  "models": {
    "detection": "loaded",
    "recognition": "loaded"
  },
  "stats": {
    "total_processed": 42,
    "faces_detected": 156,
    "persons_created": 23
  }
}
```

### Next.js Integration
```typescript
// Trigger detection
const response = await fetch(`/api/blobs/${blobId}/detect-faces`, {
  method: 'POST'
});
const { taskId, queuePosition } = await response.json();

// Get results
const faces = await fetch(`/api/blobs/${blobId}/detect-faces`);
const { faceInstances } = await faces.json();
```

## ⚙️ Configuration

**Environment Variables (.env):**
```env
DATABASE_URL=postgresql://user:password@localhost:5432/cbis
RECOGNITION_THRESHOLD=0.4    # Person matching threshold (0.3-0.5)
MIN_CONFIDENCE=0.6           # Min face detection confidence
MIN_FACE_SIZE=40             # Min face size in pixels
```

**Tuning Guide:**
- **RECOGNITION_THRESHOLD**: Lower = stricter matching, more unknown persons
  - `0.3`: Very strict (siblings might be different persons)
  - `0.4`: Recommended (good balance)
  - `0.5`: Lenient (might merge similar faces)

- **MIN_CONFIDENCE**: Higher = fewer false positives
  - `0.5`: Detect more faces (some false positives)
  - `0.6`: Recommended (balanced)
  - `0.7`: Only high-quality detections

## 🗄️ Database Schema

### FaceInstance
```sql
CREATE TABLE "FaceInstance" (
  id           TEXT PRIMARY KEY,
  blob_id      TEXT NOT NULL,
  person_id    TEXT,
  bounding_box JSONB,           -- {x, y, width, height}
  embedding    vector(512),     -- ArcFace embedding
  confidence   FLOAT,
  quality      FLOAT,
  detected_at  TIMESTAMP DEFAULT NOW()
);
```

### Person
```sql
CREATE TABLE "Person" (
  id          TEXT PRIMARY KEY,
  name        TEXT,              -- "John Doe" or "Unknown Person #42"
  tags        TEXT[],
  face_count  INT DEFAULT 0,
  created_at  TIMESTAMP DEFAULT NOW()
);
```

## 🔍 Troubleshooting

| Issue | Solution |
|-------|----------|
| Models not downloading | Check internet, ensure `~/.insightface/` writable |
| Database connection fails | Verify `DATABASE_URL`, check PostgreSQL running |
| No faces detected | Check `MIN_CONFIDENCE`, verify image has faces |
| Too many unknown persons | Increase `RECOGNITION_THRESHOLD` to 0.5 |
| Service crashes | Check logs, ensure enough RAM (2GB+ recommended) |

## 📊 Monitoring

**Queue Stats:**
```bash
curl http://localhost:8005/queue/stats
```

**Response:**
```json
{
  "queue_size": 3,
  "processing": true,
  "stats": {
    "total_processed": 156,
    "faces_detected": 623,
    "persons_created": 87,
    "uptime_seconds": 3600
  }
}
```

**Logs:**
```powershell
# If running directly
python app.py

# If in Docker
docker logs cbis-face-detection -f

# If using PM2
pm2 logs face-detection
```

## 🐳 Docker Commands

```powershell
# Build image
docker build -t cbis-face-detection ./FACE_DETECTION

# Run standalone
docker run -p 8005:8005 --env-file .env cbis-face-detection

# Run with compose
docker-compose -f docker-compose.full.yml up -d face-detection

# View logs
docker logs cbis-face-detection -f

# Stop service
docker-compose -f docker-compose.full.yml stop face-detection
```

## 🎯 Performance Tips

1. **Batch Processing**: Queue multiple images before processing
2. **Image Size**: Resize large images to ~1024px before detection
3. **Priority**: Use priority field (1-10) for urgent tasks
4. **Caching**: InsightFace models cached in `~/.insightface/`
5. **Database**: Create indexes for faster similarity search

## 🔗 Related Services

| Service | Port | Purpose |
|---------|------|---------|
| Next.js App | 3000 | Frontend & API |
| CLIP | 8000 | Image embeddings |
| Type Router V2 | 8001 | Image classification |
| NIMA | 8002 | Quality assessment |
| Query Optimizer | 8003 | Search optimization |
| Search Router | 8004 | Search orchestration |
| **Face Detection** | **8005** | **Face recognition** |

## 📚 Documentation

- **Full Docs**: `README.md`
- **Deployment**: `DEPLOYMENT.md`
- **API Docs**: http://localhost:8005/docs (when running)
- **Prisma Schema**: `../next-js/prisma/schema.prisma`

## 🆘 Support

**Common Commands:**
```powershell
# Full deployment
.\deploy.ps1 -Step all

# Start service
.\deploy.ps1 -Step start

# Run tests
python test_service.py

# Check service
curl http://localhost:8005/health

# View API docs
start http://localhost:8005/docs
```

**Service URL:** http://localhost:8005  
**API Documentation:** http://localhost:8005/docs  
**Project Root:** `E:\programming\CBIS_Project\FACE_DETECTION`
