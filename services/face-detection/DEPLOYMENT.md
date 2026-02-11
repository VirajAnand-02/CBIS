# Face Detection Service - Deployment Checklist

## Pre-Deployment

### 1. Database Migration
```powershell
cd e:\programming\CBIS_Project\next-js
npx prisma migrate dev --name add_face_recognition
```

This will create:
- `FaceInstance` table with vector embeddings
- `Person` table for face grouping
- Proper relations between tables

### 2. Install pgvector Extension
Connect to your PostgreSQL database and run:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### 3. Create Indexes (Optional but Recommended)
For better performance on large datasets:
```sql
-- Index for fast similarity search
CREATE INDEX ON "FaceInstance" USING ivfflat (embedding vector_cosine_ops);

-- Index for person lookup
CREATE INDEX ON "FaceInstance" (person_id);

-- Index for blob lookup
CREATE INDEX ON "FaceInstance" (blob_id);
```

## Service Setup

### 4. Configure Environment
```powershell
cd e:\programming\CBIS_Project\FACE_DETECTION
cp .env.example .env
```

Edit `.env` and set:
```env
DATABASE_URL=postgresql://user:password@localhost:5432/cbis
RECOGNITION_THRESHOLD=0.4
MIN_CONFIDENCE=0.6
MIN_FACE_SIZE=40
```

### 5. Install Dependencies
```powershell
pip install -r requirements.txt
```

This will install:
- `insightface` (face detection & recognition)
- `fastapi` (web framework)
- `opencv-python` (image processing)
- `psycopg2-binary` (PostgreSQL driver)
- `asyncpg` (async PostgreSQL)
- Other dependencies

### 6. Download Models (Automatic on First Run)
Models will be downloaded to `~/.insightface/models/` on first use:
- `buffalo_l` (RetinaFace + ArcFace)
- ~700MB total

## Deployment

### 7. Start Service
```powershell
# Option 1: Direct Python
cd FACE_DETECTION
python app.py

# Option 2: PowerShell script
.\start_service.ps1

# Option 3: Docker (after building)
docker-compose up face-detection
```

Service will start on **http://localhost:8005**

### 8. Verify Service
```powershell
# Test health endpoint
curl http://localhost:8005/health

# Run test suite
python test_service.py
```

### 9. Check API Documentation
Open in browser: **http://localhost:8005/docs**

## Integration

### 10. Update Next.js Environment
In `next-js/.env.local`:
```env
FACE_DETECTION_URL=http://localhost:8005
```

### 11. Test Face Detection API
```powershell
# From Next.js app
curl -X POST http://localhost:3000/api/blobs/{blob_id}/detect-faces
```

## Post-Deployment

### 12. Monitor Service
- Check logs for errors
- Monitor queue stats: `GET /queue/stats`
- Watch processing performance
- Check database for created persons

### 13. Tune Parameters (if needed)
Adjust in `.env`:
- `RECOGNITION_THRESHOLD`: Lower = stricter matching (0.3-0.5 recommended)
- `MIN_CONFIDENCE`: Higher = fewer false positives (0.5-0.7 recommended)
- `MIN_FACE_SIZE`: Larger = ignore small faces (30-50 recommended)

## Production Considerations

### 14. Enable Process Manager
For production, use a process manager:

**PM2:**
```powershell
npm install -g pm2
pm2 start app.py --interpreter python --name face-detection
```

**Supervisor:**
```ini
[program:face-detection]
command=python app.py
directory=E:\programming\CBIS_Project\FACE_DETECTION
autostart=true
autorestart=true
```

### 15. Set Up Logging
Configure logging to file:
```python
# In app.py, add:
import logging
logging.basicConfig(
    filename='face_detection.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
```

### 16. Configure Reverse Proxy (Optional)
If using Nginx:
```nginx
location /face-detection/ {
    proxy_pass http://localhost:8005/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

## Troubleshooting

### Service won't start
1. Check Python version: `python --version` (need 3.8+)
2. Verify dependencies: `pip list | findstr fastapi`
3. Check port availability: `netstat -ano | findstr :8005`
4. Review error logs

### Models not downloading
1. Check internet connection
2. Ensure write permissions to `~/.insightface/`
3. Manually download from: https://github.com/deepinsight/insightface

### Database connection fails
1. Verify PostgreSQL is running
2. Check DATABASE_URL format
3. Ensure pgvector extension is installed
4. Test connection: `psql $DATABASE_URL`

### Face detection not working
1. Check image format (JPEG/PNG)
2. Verify image path exists
3. Check image contains faces
4. Review MIN_CONFIDENCE threshold
5. Check service logs for errors

## Success Criteria
- ✓ Service responds to /health
- ✓ Can enqueue detection tasks
- ✓ Faces are detected and stored
- ✓ Persons are created/matched
- ✓ Embeddings are saved to database
- ✓ Queue processes continuously
- ✓ No memory leaks over time

## Next Steps
After successful deployment:
1. Test with real user uploads
2. Build person management UI
3. Add face detection to upload pipeline
4. Implement person naming/merging
5. Create face search functionality
6. Add face clustering for unknowns
