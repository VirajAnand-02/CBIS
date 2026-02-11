# Face Detection Service - Architecture Overview

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         CBIS System                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐         ┌─────────────────────────────┐      │
│  │   Next.js    │────────▶│  Face Detection Service     │      │
│  │  (Frontend)  │         │       (Port 8005)           │      │
│  │              │         │                             │      │
│  │ - Upload UI  │         │  ┌───────────────────────┐  │      │
│  │ - View Faces │         │  │   FastAPI Server      │  │      │
│  │ - Manage     │         │  │   - /detect (POST)    │  │      │
│  │   Persons    │         │  │   - /health (GET)     │  │      │
│  └──────┬───────┘         │  │   - /queue/stats      │  │      │
│         │                 │  └───────────┬───────────┘  │      │
│         │                 │              │              │      │
│         │                 │  ┌───────────▼───────────┐  │      │
│         │                 │  │   Async Queue         │  │      │
│         │                 │  │   - Priority Queue    │  │      │
│         │                 │  │   - Thread-safe       │  │      │
│         │                 │  │   - Instant Response  │  │      │
│         │                 │  └───────────┬───────────┘  │      │
│         │                 │              │              │      │
│         │                 │  ┌───────────▼───────────┐  │      │
│         │                 │  │  Background Worker    │  │      │
│         │                 │  │  - Async Processing   │  │      │
│         │                 │  │  - Continuous Loop    │  │      │
│         │                 │  └───────────┬───────────┘  │      │
│         │                 │              │              │      │
│         │                 │  ┌───────────▼───────────┐  │      │
│         │                 │  │  InsightFace Models   │  │      │
│         │                 │  │  - RetinaFace (Detect)│  │      │
│         │                 │  │  - ArcFace (Embed)    │  │      │
│         │                 │  └───────────┬───────────┘  │      │
│         │                 └──────────────┼──────────────┘      │
│         │                                │                     │
│         │                 ┌──────────────▼──────────────┐      │
│         └────────────────▶│     PostgreSQL + pgvector   │      │
│                           │                             │      │
│                           │  Tables:                    │      │
│                           │  - FaceInstance             │      │
│                           │    * embedding (vector)     │      │
│                           │    * bounding_box (json)    │      │
│                           │    * person_id (fk)         │      │
│                           │  - Person                   │      │
│                           │    * name                   │      │
│                           │    * face_count             │      │
│                           └─────────────────────────────┘      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Processing Flow

```
┌─────────────────┐
│  1. User Upload │
│     Image       │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│  2. Next.js API: POST /api/blobs/[id]/      │
│     detect-faces                            │
└────────┬────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│  3. Face Detection: POST /detect            │
│     {                                       │
│       "blob_id": "cm6abc123",              │
│       "file_path": "storage/blobs/...",    │
│       "priority": 7                        │
│     }                                       │
└────────┬────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│  4. Enqueue Task                            │
│     - Generate task_id (UUID)              │
│     - Add to priority queue                │
│     - Return immediately                    │
└────────┬────────────────────────────────────┘
         │
         │ ┌────────────────────────────────┐
         │ │  Response (instant):           │
         │ │  {                             │
         │ │    "task_id": "550e8400...",  │
         │ │    "status": "queued",        │
         │ │    "queue_position": 1        │
         │ │  }                            │
         │ └────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│  5. Background Worker (Async)               │
│     - Fetch task from queue                │
│     - Load image from storage              │
└────────┬────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│  6. Face Detection (RetinaFace)            │
│     - Detect faces in image                │
│     - Get bounding boxes                   │
│     - Filter by MIN_CONFIDENCE (0.6)       │
│     - Filter by MIN_FACE_SIZE (40px)       │
└────────┬────────────────────────────────────┘
         │
         │ For each detected face:
         │
         ▼
┌─────────────────────────────────────────────┐
│  7. Crop Face                               │
│     - Extract face region                  │
│     - Resize to 112x112                    │
└────────┬────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│  8. Generate Embedding (ArcFace)           │
│     - 512-dimensional vector               │
│     - L2 normalized                        │
└────────┬────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│  9. Find Matching Person                   │
│     - Query: SELECT * FROM Person          │
│       JOIN FaceInstance                    │
│       ORDER BY embedding <=> $1            │
│       LIMIT 1                              │
│     - Check distance < THRESHOLD (0.4)     │
└────────┬────────────────────────────────────┘
         │
         ├─── Match Found ───┐
         │                   │
         │                   ▼
         │         ┌──────────────────────┐
         │         │ 10a. Use Person      │
         │         │      - person_id     │
         │         │      - Update count  │
         │         └──────────┬───────────┘
         │                    │
         ├─── No Match ───┐  │
         │                │  │
         │                ▼  │
         │      ┌──────────────────────┐  │
         │      │ 10b. Create Person   │  │
         │      │      - "Unknown #N"  │  │
         │      │      - Generate ID   │  │
         │      └──────────┬───────────┘  │
         │                 │              │
         │                 └──────┬───────┘
         │                        │
         ▼                        ▼
┌─────────────────────────────────────────────┐
│  11. Save FaceInstance                      │
│      INSERT INTO FaceInstance               │
│      - id (UUID)                            │
│      - blob_id                              │
│      - person_id                            │
│      - bounding_box (JSON)                  │
│      - embedding (vector)                   │
│      - confidence                           │
│      - quality                              │
└────────┬────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│  12. Update Statistics                      │
│      - total_processed++                   │
│      - faces_detected++                    │
│      - persons_created++ (if new)          │
└─────────────────────────────────────────────┘
```

## Data Flow

```
Image File
    │
    ├──▶ RetinaFace ──▶ Bounding Boxes [x, y, w, h]
    │
    └──▶ Crop Faces ──▶ Face Images (112x112)
              │
              └──▶ ArcFace ──▶ Embeddings (512-dim)
                        │
                        ├──▶ pgvector ──▶ Similar Person?
                        │         │
                        │         ├─ Yes ──▶ person_id
                        │         │
                        │         └─ No ──▶ Create New Person
                        │
                        └──▶ Database ──▶ FaceInstance Record
```

## Person Matching Algorithm

```python
def find_matching_person(embedding: np.ndarray):
    # 1. Search all existing face embeddings
    query = """
        SELECT p.id, p.name, 
               fi.embedding <=> $1 as distance
        FROM Person p
        JOIN FaceInstance fi ON fi.person_id = p.id
        ORDER BY distance
        LIMIT 1
    """
    
    result = execute_query(query, [embedding])
    
    # 2. Check if match is close enough
    if result and result['distance'] < RECOGNITION_THRESHOLD:
        return result['id']  # Match found
    else:
        return None  # No match, create new person
```

## Component Responsibilities

### FastAPI Server
- ✓ Accept HTTP requests
- ✓ Validate input
- ✓ Manage async queue
- ✓ Return instant responses
- ✓ Serve health checks

### Async Queue
- ✓ Thread-safe operations
- ✓ Priority-based ordering
- ✓ FIFO within priority
- ✓ Task tracking

### Background Worker
- ✓ Continuous processing
- ✓ Async/await pattern
- ✓ Error handling
- ✓ Statistics tracking

### InsightFace Models
- ✓ Face detection (RetinaFace)
- ✓ Face recognition (ArcFace)
- ✓ Quality assessment
- ✓ Embedding generation

### Database Layer
- ✓ Store face instances
- ✓ Manage persons
- ✓ Vector similarity search
- ✓ Relationship tracking

## Configuration Hierarchy

```
.env
 ├── DATABASE_URL ──────────▶ PostgreSQL Connection
 ├── RECOGNITION_THRESHOLD ─▶ Person Matching Strictness
 ├── MIN_CONFIDENCE ────────▶ Detection Quality Filter
 └── MIN_FACE_SIZE ─────────▶ Size Filter (pixels)
```

## Deployment Options

```
┌─────────────────────────────────────────────────────┐
│  Option 1: Direct Python                            │
│  ┌────────────────────────────────────────────┐    │
│  │  python app.py                             │    │
│  │  - Port 8005                               │    │
│  │  - Local development                       │    │
│  └────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│  Option 2: Docker Standalone                        │
│  ┌────────────────────────────────────────────┐    │
│  │  docker run -p 8005:8005 \                 │    │
│  │    --env-file .env \                       │    │
│  │    cbis-face-detection                     │    │
│  └────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│  Option 3: Docker Compose (Full Stack)              │
│  ┌────────────────────────────────────────────┐    │
│  │  docker-compose up face-detection          │    │
│  │  - All services orchestrated               │    │
│  │  - Network configured                      │    │
│  │  - Volumes managed                         │    │
│  └────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│  Option 4: Process Manager (Production)             │
│  ┌────────────────────────────────────────────┐    │
│  │  pm2 start app.py \                        │    │
│  │    --interpreter python \                  │    │
│  │    --name face-detection                   │    │
│  │  - Auto-restart                            │    │
│  │  - Log management                          │    │
│  └────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

## Performance Considerations

### Memory Usage
```
Base Service:        ~200MB
InsightFace Models:  ~700MB
Per Image:          ~50MB (temporary)
Total (idle):       ~1GB
Peak (processing):  ~2GB
```

### Processing Speed
```
Face Detection:     ~200ms per image
Embedding:         ~50ms per face
Database Query:    ~10ms per search
Total:            ~300-500ms per image (1-3 faces)
```

### Scalability
```
Queue Size:        Unlimited (memory limited)
Concurrent Tasks:  1 (background worker)
Throughput:        ~2-3 images/second
Scaling:          Horizontal (multiple instances)
```

## Error Handling

```
Request ──▶ Validation ──▶ Enqueue ──▶ Response
                │
                ├─ Invalid Input ──▶ 400 Bad Request
                └─ Valid ──▶ Continue

Processing ──▶ Face Detection ──▶ Embedding ──▶ Database
                     │                │            │
                     ├─ No Faces ──▶ Log & Skip   │
                     │                             │
                     ├─ Detection Error ──▶ Retry  │
                     │                             │
                     └─ Database Error ──▶ Log & Alert
```

## Monitoring Points

1. **Health Endpoint**: Service status, model status
2. **Queue Stats**: Size, processing state, throughput
3. **Database**: Connection pool, query performance
4. **Memory**: Usage patterns, leak detection
5. **Logs**: Errors, warnings, processing times

## Security Considerations

- ✓ Input validation (file paths)
- ✓ Database parameterized queries
- ✓ Environment-based secrets
- ✓ No sensitive data in logs
- ✓ Rate limiting (future)
- ✓ Authentication (future)
