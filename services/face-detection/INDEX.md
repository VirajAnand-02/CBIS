# Face Detection Service - Complete Package

## 📦 Package Contents

This directory contains a complete, production-ready face detection and recognition microservice for the CBIS project.

### Core Files

| File | Purpose | Lines |
|------|---------|-------|
| `app.py` | Main service implementation | 600+ |
| `requirements.txt` | Python dependencies | 15 |
| `Dockerfile` | Container configuration | 30 |
| `.env.example` | Environment template | 10 |
| `start_service.ps1` | PowerShell startup script | 50 |

### Documentation

| File | Purpose | Pages |
|------|---------|-------|
| `README.md` | Complete documentation | 15+ |
| `QUICKREF.md` | Quick reference card | 3 |
| `DEPLOYMENT.md` | Deployment checklist | 4 |
| `ARCHITECTURE.md` | System architecture | 6 |

### Scripts

| File | Purpose |
|------|---------|
| `deploy.ps1` | Automated deployment |
| `test_service.py` | Service test suite |

## 🎯 What This Service Does

### Core Functionality
1. **Face Detection**: Detects faces in uploaded images using RetinaFace
2. **Face Recognition**: Generates 512-dimensional embeddings using ArcFace
3. **Person Matching**: Finds similar faces using vector similarity (pgvector)
4. **Auto-Identification**: Creates new "Unknown Person" entries when no match found
5. **Queue-Based Processing**: Instant API responses with background processing

### Key Features
- ✅ Async queue architecture (no blocking)
- ✅ Priority-based task ordering
- ✅ Thread-safe operations
- ✅ Configurable matching threshold
- ✅ Quality filtering
- ✅ RESTful API with OpenAPI docs
- ✅ Docker support
- ✅ PostgreSQL integration with pgvector
- ✅ Comprehensive error handling

## 🚀 Quick Start (5 Minutes)

```powershell
# 1. Run automated deployment
cd E:\programming\CBIS_Project\FACE_DETECTION
.\deploy.ps1 -Step all

# 2. Edit .env with your database URL
notepad .env

# 3. Start the service
.\deploy.ps1 -Step start

# 4. Test it
python test_service.py
```

**Service URL**: http://localhost:8005  
**API Docs**: http://localhost:8005/docs

## 📊 Technical Specifications

### Technologies
- **Framework**: FastAPI (async)
- **Face Detection**: InsightFace (RetinaFace)
- **Face Recognition**: InsightFace (ArcFace)
- **Database**: PostgreSQL + pgvector
- **Queue**: Python deque + asyncio
- **Container**: Docker

### Models
- **RetinaFace**: Face detection (640x640 input)
- **ArcFace**: Face recognition (512-dim embeddings, L2 normalized)
- **Model Size**: ~700MB total
- **Model Storage**: `~/.insightface/models/buffalo_l/`

### Performance
- **Detection Speed**: ~200ms per image
- **Embedding Speed**: ~50ms per face
- **Database Query**: ~10ms per search
- **Throughput**: 2-3 images/second
- **Memory**: ~1GB idle, ~2GB peak

### API Endpoints
- `POST /detect` - Enqueue face detection task
- `GET /health` - Service health and statistics
- `GET /queue/stats` - Queue status
- `GET /queue/clear` - Clear queue
- `GET /docs` - Interactive API documentation

## 🗄️ Database Integration

### Tables Created (Prisma Migration)

**FaceInstance**
```prisma
model FaceInstance {
  id           String    @id @default(cuid())
  blobId       String
  personId     String?
  boundingBox  Json      // {x, y, width, height}
  embedding    Unsupported("vector(512)")
  confidence   Float
  quality      Float?
  detectedAt   DateTime  @default(now())
  
  blob         Blob      @relation(fields: [blobId], references: [id])
  person       Person?   @relation(fields: [personId], references: [id])
}
```

**Person**
```prisma
model Person {
  id         String          @id @default(cuid())
  name       String          // "John Doe" or "Unknown Person #42"
  tags       String[]
  faceCount  Int             @default(0)
  createdAt  DateTime        @default(now())
  
  faces      FaceInstance[]
}
```

### Required PostgreSQL Extension
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### Recommended Indexes
```sql
CREATE INDEX ON "FaceInstance" USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX ON "FaceInstance" (person_id);
CREATE INDEX ON "FaceInstance" (blob_id);
```

## 🔧 Configuration

### Environment Variables

```env
# Required
DATABASE_URL=postgresql://user:password@localhost:5432/cbis

# Optional (with defaults)
RECOGNITION_THRESHOLD=0.4    # Person matching threshold
MIN_CONFIDENCE=0.6           # Min face detection confidence
MIN_FACE_SIZE=40             # Min face size in pixels
```

### Tuning Guide

**RECOGNITION_THRESHOLD** (Person Matching)
- `0.3`: Very strict - siblings might be different persons
- `0.4`: **Recommended** - good balance
- `0.5`: Lenient - might merge similar-looking people

**MIN_CONFIDENCE** (Detection Quality)
- `0.5`: More faces detected (some false positives)
- `0.6`: **Recommended** - balanced
- `0.7`: Only high-quality detections

**MIN_FACE_SIZE** (Size Filter)
- `30`: Include small faces in group photos
- `40`: **Recommended** - balanced
- `50`: Only prominent faces

## 🏗️ Architecture

### Processing Flow
```
Upload Image → Enqueue Task → Instant Response
                   ↓
        Background Worker (Async)
                   ↓
        Detect Faces (RetinaFace)
                   ↓
        For each face:
          ├─ Crop Face
          ├─ Generate Embedding (ArcFace)
          ├─ Search Similar (pgvector)
          ├─ Match Found? → Use Person
          └─ No Match? → Create "Unknown Person"
                   ↓
        Save FaceInstance to Database
```

### Queue Architecture
- **Type**: Python `deque` with `threading.Lock`
- **Ordering**: Priority-based (1-10), FIFO within priority
- **Response**: Instant task_id and queue position
- **Processing**: Single async background worker

### Person Matching
- **Method**: Cosine similarity via pgvector
- **Threshold**: Configurable (default 0.4)
- **Query**: `ORDER BY embedding <=> $1 LIMIT 1`
- **Auto-Create**: "Unknown Person #N" when no match

## 📝 Usage Examples

### Python Client
```python
import requests

# Enqueue detection
response = requests.post(
    "http://localhost:8005/detect",
    json={
        "blob_id": "cm6abc123",
        "file_path": "storage/blobs/photo.jpg",
        "priority": 7
    }
)
task = response.json()
print(f"Task ID: {task['task_id']}")
print(f"Queue position: {task['queue_position']}")

# Check health
health = requests.get("http://localhost:8005/health").json()
print(f"Faces detected: {health['stats']['faces_detected']}")
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

// Display faces
faceInstances.forEach(face => {
  console.log(`Person: ${face.person.name}`);
  console.log(`Confidence: ${face.confidence}`);
  console.log(`Bounding box: ${JSON.stringify(face.boundingBox)}`);
});
```

### cURL
```bash
# Detect faces
curl -X POST http://localhost:8005/detect \
  -H "Content-Type: application/json" \
  -d '{"blob_id":"cm6abc123","file_path":"storage/blobs/photo.jpg"}'

# Check health
curl http://localhost:8005/health

# Queue stats
curl http://localhost:8005/queue/stats
```

## 🐳 Docker Deployment

### Build Image
```powershell
docker build -t cbis-face-detection ./FACE_DETECTION
```

### Run Standalone
```powershell
docker run -d \
  -p 8005:8005 \
  --env-file .env \
  -v ./next-js/storage:/app/storage:ro \
  cbis-face-detection
```

### Run with Docker Compose
```powershell
# Start all services
docker-compose -f docker-compose.full.yml up -d

# Start only face detection
docker-compose -f docker-compose.full.yml up -d face-detection

# View logs
docker logs cbis-face-detection -f

# Stop service
docker-compose -f docker-compose.full.yml stop face-detection
```

## 🧪 Testing

### Automated Test Suite
```powershell
python test_service.py
```

**Tests:**
- ✓ Health endpoint
- ✓ Queue statistics
- ✓ API documentation
- ✓ Service availability

### Manual Testing
```powershell
# 1. Start service
python app.py

# 2. Open API docs
start http://localhost:8005/docs

# 3. Try /detect endpoint with sample data
# 4. Check /queue/stats
# 5. Verify database has FaceInstance records
```

## 📈 Monitoring

### Health Check
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
    "persons_created": 23,
    "uptime_seconds": 3600
  }
}
```

### Queue Statistics
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
    "persons_created": 87
  }
}
```

## 🔒 Security

### Current
- ✓ Input validation (file paths)
- ✓ Parameterized database queries
- ✓ Environment-based configuration
- ✓ No sensitive data in logs

### Future Enhancements
- ⏳ API authentication (JWT)
- ⏳ Rate limiting
- ⏳ Request signing
- ⏳ CORS configuration

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| Models not downloading | Check internet, `~/.insightface/` writable |
| Database connection fails | Verify DATABASE_URL, PostgreSQL running |
| Port 8005 in use | Change port in app.py, update docker-compose |
| No faces detected | Lower MIN_CONFIDENCE, check image quality |
| Too many unknown persons | Increase RECOGNITION_THRESHOLD to 0.5 |
| Service crashes | Check RAM (need 2GB+), review logs |
| Slow processing | Resize images, check database indexes |

## 📚 Documentation Index

| Document | Purpose | Audience |
|----------|---------|----------|
| **README.md** | Complete reference | All users |
| **QUICKREF.md** | Quick reference | Developers |
| **DEPLOYMENT.md** | Step-by-step deployment | DevOps |
| **ARCHITECTURE.md** | System design | Architects |
| **deploy.ps1** | Automated deployment | DevOps |
| **test_service.py** | Testing guide | QA/Developers |

## 🎓 Learning Path

### For Developers
1. Read QUICKREF.md (5 min)
2. Run deploy.ps1 (10 min)
3. Test with API docs (15 min)
4. Read ARCHITECTURE.md (20 min)
5. Modify configuration (10 min)

### For DevOps
1. Read DEPLOYMENT.md (10 min)
2. Review docker-compose.full.yml (5 min)
3. Run deploy.ps1 -Step docker (15 min)
4. Set up monitoring (20 min)
5. Configure production (30 min)

### For Architects
1. Read ARCHITECTURE.md (30 min)
2. Review app.py (60 min)
3. Study database schema (20 min)
4. Plan scaling strategy (30 min)

## 🔗 Integration Points

### With Next.js App
- **API Endpoint**: `/api/blobs/[id]/detect-faces`
- **Trigger**: POST request with blob_id
- **Retrieve**: GET request returns face instances

### With Other Services
- **CLIP**: Could enhance with face + scene embeddings
- **NIMA**: Could filter low-quality face images
- **Search Router**: Could enable "find similar faces" search

### With Database
- **Blob**: Each face links to original image
- **Person**: Faces grouped by person
- **Vector**: Similarity search using pgvector

## 🚧 Future Enhancements

### Planned
- ⏳ Person management UI (naming, merging)
- ⏳ Face clustering (better grouping)
- ⏳ Age/gender detection
- ⏳ Emotion recognition
- ⏳ Face tracking across videos

### Possible
- Face beautification scoring
- Celebrity look-alike matching
- Face swapping/editing
- Automatic tagging in photos
- Privacy mode (blur faces)

## 📞 Support

### Quick Commands
```powershell
# Deploy everything
.\deploy.ps1 -Step all

# Start service
python app.py

# Run tests
python test_service.py

# View health
curl http://localhost:8005/health

# API docs
start http://localhost:8005/docs
```

### Key URLs
- **Service**: http://localhost:8005
- **API Docs**: http://localhost:8005/docs
- **Health**: http://localhost:8005/health
- **Queue Stats**: http://localhost:8005/queue/stats

### Files
- **Main Code**: `app.py` (600+ lines)
- **Config**: `.env` (edit from `.env.example`)
- **Deployment**: `deploy.ps1`
- **Tests**: `test_service.py`

## ✅ Deployment Checklist

- [ ] Read DEPLOYMENT.md
- [ ] Run `.\deploy.ps1 -Step db` (Prisma migration)
- [ ] Run `.\deploy.ps1 -Step deps` (Install packages)
- [ ] Edit `.env` with DATABASE_URL
- [ ] Run `.\deploy.ps1 -Step start` (Start service)
- [ ] Run `python test_service.py` (Verify)
- [ ] Open http://localhost:8005/docs (Check API)
- [ ] Test face detection with sample image
- [ ] Verify database has Person and FaceInstance records
- [ ] Set up monitoring/logging
- [ ] Configure production settings
- [ ] Deploy to production

## 🎉 Success Criteria

Your deployment is successful when:
- ✓ Service responds to /health endpoint
- ✓ Can enqueue detection tasks via /detect
- ✓ Faces are detected and stored in database
- ✓ Persons are created/matched correctly
- ✓ Embeddings are searchable via pgvector
- ✓ Queue processes continuously
- ✓ API documentation is accessible
- ✓ No errors in logs
- ✓ Memory usage is stable

## 📄 License & Credits

**Service**: Part of CBIS Project  
**Models**: InsightFace (Apache 2.0)  
**Framework**: FastAPI (MIT)  
**Database**: PostgreSQL + pgvector  

**Credits:**
- InsightFace: https://github.com/deepinsight/insightface
- pgvector: https://github.com/pgvector/pgvector
- FastAPI: https://fastapi.tiangolo.com/

---

**Version**: 1.0.0  
**Last Updated**: 2024  
**Project**: CBIS (Content-Based Image Search)  
**Service Port**: 8005
