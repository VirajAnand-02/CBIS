# Face Detection & Recognition Microservice

Asynchronous face detection and person recognition service using RetinaFace and ArcFace.

## Features

- ✅ **Asynchronous Queue Processing** - Non-blocking, instant response
- ✅ **RetinaFace Detection** - Industry-standard face detector
- ✅ **ArcFace Recognition** - State-of-the-art face recognition (512-dim embeddings)
- ✅ **Automatic Person Matching** - Identifies known persons across images
- ✅ **Auto Person Creation** - Creates new person entries for unknown faces
- ✅ **Priority Queue** - Process urgent tasks first
- ✅ **Quality Filtering** - Skips low-quality/small faces
- ✅ **PostgreSQL + pgvector** - Efficient similarity search

## Architecture

```
┌─────────────────┐
│   Next.js API   │
└────────┬────────┘
         │ POST /api/blobs/{id}/detect-faces
         ▼
┌─────────────────┐
│  Face Detection │
│    Service      │ ← Queue-based processing
│   (Port 8005)   │
└────────┬────────┘
         │
         ├─── 1. Detect faces (RetinaFace)
         ├─── 2. Crop faces
         ├─── 3. Generate embeddings (ArcFace)
         ├─── 4. Search for matching person (pgvector)
         ├─── 5. Create new person if unknown
         └─── 6. Store face instances in DB
```

## Processing Pipeline

### 1. Task Enqueueing
```
Client → POST /detect → Queue → Instant Response (task_id)
```

### 2. Background Processing
For each image:

1. **Load Image** from storage path
2. **Detect All Faces** using RetinaFace
   - Filter by confidence (> 0.6)
   - Filter by size (> 40px)
3. **For Each Face:**
   a. **Crop Face** from image
   b. **Generate Embedding** (ArcFace 512-dim)
   c. **Search Database** for similar faces
   d. **Apply Threshold** (cosine distance < 0.4)
      - If match found → Assign to existing person
      - If no match → Create new person ("Unknown Person #N")
   e. **Store Face Instance** in database

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and update:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/cbis
STORAGE_BASE_PATH=../next-js
RECOGNITION_THRESHOLD=0.4
MIN_FACE_SIZE=40
MIN_CONFIDENCE=0.6
```

### 3. Download Models

InsightFace will automatically download models on first run (~200MB).

## Usage

### Start Service

**Windows:**
```powershell
.\start_service.ps1
```

**Linux/Mac:**
```bash
python app.py
```

Service will start on `http://localhost:8005`

### API Endpoints

#### 1. Enqueue Face Detection

```bash
POST /detect
Content-Type: application/json

{
  "blob_id": "uuid-of-image",
  "file_path": "storage/blobs/filename.jpg",
  "priority": 5
}
```

**Response:**
```json
{
  "task_id": "uuid-of-task",
  "status": "queued",
  "message": "Face detection task enqueued for blob xyz",
  "queue_position": 3
}
```

#### 2. Health Check

```bash
GET /health
```

**Response:**
```json
{
  "status": "ok",
  "service": "face_detection",
  "models": {
    "detector": "retinaface",
    "recognition": "arcface"
  },
  "stats": {
    "total_processed": 145,
    "faces_detected": 327,
    "persons_created": 42,
    "faces_matched": 285,
    "queue_size": 3
  }
}
```

#### 3. Queue Statistics

```bash
GET /queue/stats
```

## Integration with Next.js

### Trigger Face Detection on Upload

```typescript
// After uploading an image
const response = await fetch(`/api/blobs/${blobId}/detect-faces`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ priority: 5 })
});

const result = await response.json();
console.log('Task ID:', result.task_id);
console.log('Queue position:', result.queue_position);
```

### Get Detection Results

```typescript
// Fetch detected faces
const response = await fetch(`/api/blobs/${blobId}/detect-faces`);
const data = await response.json();

console.log('Faces detected:', data.faces_detected);
data.faces.forEach(face => {
  console.log('Person:', face.person?.name || 'Unknown');
  console.log('Confidence:', face.confidence);
  console.log('Bounding box:', face.bounding_box);
});
```

## Configuration

### Recognition Threshold

Controls how strict person matching is:

- **0.3** - Very strict (same person, same lighting)
- **0.4** - Recommended (same person, different conditions)
- **0.5** - Loose (may have false positives)

Lower threshold = fewer false matches but more unknown persons created.

### Quality Filtering

```env
MIN_FACE_SIZE=40        # Minimum face size in pixels
MIN_CONFIDENCE=0.6      # Detection confidence (0-1)
```

### Priority Queue

Higher priority tasks are processed first:
- `1-3`: Low priority (batch processing)
- `4-6`: Normal priority (user uploads)
- `7-10`: High priority (manual requests)

## Database Schema

### Face Instances

```sql
CREATE TABLE face_instances (
  id UUID PRIMARY KEY,
  "blobId" UUID NOT NULL,
  "personId" UUID,
  "boundingBox" JSONB NOT NULL,
  embedding vector(512),
  confidence FLOAT,
  quality FLOAT,
  "detectorModel" TEXT,
  "embeddingModel" TEXT,
  "createdAt" TIMESTAMP,
  "updatedAt" TIMESTAMP
);

-- Index for similarity search
CREATE INDEX ON face_instances USING ivfflat (embedding vector_cosine_ops);
```

### Persons

```sql
CREATE TABLE persons (
  id UUID PRIMARY KEY,
  name TEXT,
  "faceCount" INTEGER,
  thumbnail TEXT,
  tags TEXT[],
  "createdAt" TIMESTAMP,
  "updatedAt" TIMESTAMP
);
```

## Performance

### Throughput
- **Detection**: ~2-5 images/second (CPU)
- **Detection**: ~10-20 images/second (GPU)
- **Recognition**: ~100 faces/second

### Resource Usage
- **Memory**: ~2GB (with models loaded)
- **Disk**: ~500MB (model files)

### Optimization Tips

1. **Use GPU** for faster processing:
   ```bash
   pip install onnxruntime-gpu
   ```

2. **Create pgvector index**:
   ```sql
   CREATE INDEX face_embedding_idx ON face_instances 
   USING ivfflat (embedding vector_cosine_ops)
   WITH (lists = 100);
   ```

3. **Batch processing** for large collections

4. **Adjust queue size** based on memory:
   ```env
   MAX_QUEUE_SIZE=1000
   ```

## Troubleshooting

### "No faces detected"
- Check image quality (blur, lighting)
- Lower `MIN_CONFIDENCE` threshold
- Check image is properly loaded

### "Too many false matches"
- Lower `RECOGNITION_THRESHOLD` (e.g., 0.3)
- Check embedding quality
- Review face crops for quality

### "Too many unknown persons"
- Increase `RECOGNITION_THRESHOLD` (e.g., 0.5)
- May need manual person merging
- Check if same person appears with different angles

### "Service out of memory"
- Reduce `MAX_QUEUE_SIZE`
- Process images in smaller batches
- Increase system RAM allocation

### "Models not loading"
- Check internet connection (first download)
- Verify `insightface` installation
- Check model cache: `~/.insightface/models/`

## Docker Deployment

```bash
# Build image
docker build -t cbis-face-detection .

# Run container
docker run -d \
  -p 8005:8005 \
  -e DATABASE_URL=postgresql://... \
  -v /path/to/storage:/storage \
  --name cbis-face-detection \
  cbis-face-detection
```

## Monitoring

### Check Service Status

```bash
curl http://localhost:8005/health
```

### View Queue

```bash
curl http://localhost:8005/queue/stats
```

### Logs

Watch processing logs:
```bash
# If running directly
python app.py

# If running in Docker
docker logs -f cbis-face-detection
```

## Person Management

### Manual Person Merging

When same person is created multiple times:

```typescript
// Merge person B into person A
await prisma.faceInstance.updateMany({
  where: { personId: 'person-b-id' },
  data: { personId: 'person-a-id' }
});

await prisma.person.update({
  where: { id: 'person-a-id' },
  data: { faceCount: { increment: personB.faceCount } }
});

await prisma.person.delete({
  where: { id: 'person-b-id' }
});
```

### Assign Names

```typescript
await prisma.person.update({
  where: { id: personId },
  data: { name: 'John Smith' }
});
```

### Search by Person

```typescript
const images = await prisma.blob.findMany({
  where: {
    faces: {
      some: { personId: 'person-id' }
    }
  }
});
```

## Future Enhancements

- [ ] Face clustering for better unknown person grouping
- [ ] Face quality enhancement (super-resolution)
- [ ] Age/gender/emotion detection
- [ ] Webhook callbacks on completion
- [ ] Redis queue for distributed processing
- [ ] Face thumbnail generation
- [ ] Batch processing API
- [ ] Person merging suggestions (similar persons)

## License

Part of CBIS (Content-Based Image Search) project.
