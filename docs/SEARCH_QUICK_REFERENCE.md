# CBIS Search Pipeline - Quick Reference

## 🚀 Start All Services
```powershell
.\start-services.ps1
```

## 📡 Service Ports
| Service | Port | Purpose |
|---------|------|---------|
| CLIP | 8000 | Image & Text Encoding |
| Type Router | 8001 | Image Classification |
| NIMA | 8002 | Aesthetic Scoring |
| **Query Optimizer** | **8003** | **Query Processing** |
| **Search Router** | **8004** | **Search Strategy** |
| Next.js | 3000 | Web Interface |

## 🔍 Quick Search Examples

### Simple Text Search
```bash
curl "http://localhost:3000/api/search?q=sunset"
```

### Search with Limit
```bash
curl "http://localhost:3000/api/search?q=sunset&limit=10"
```

### High Quality Images
```bash
curl "http://localhost:3000/api/search?q=beautiful+photos&minNimaScore=7.0"
```

### Advanced POST Search
```bash
curl -X POST http://localhost:3000/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "sunset over mountains",
    "filters": {
      "mimeType": ["image/jpeg"],
      "minNimaScore": 6.0
    },
    "limit": 20
  }'
```

## 🧪 Test Individual Services

### CLIP Text Encoding
```bash
curl -X POST http://localhost:8000/encode/text \
  -H "Content-Type: application/json" \
  -d '{"text": "beautiful sunset", "normalize": true}'
```

### Query Optimizer
```bash
curl -X POST http://localhost:8003/optimize \
  -H "Content-Type: application/json" \
  -d '{"query": "sunset photos with mountains"}'
```

### Search Router
```bash
curl -X POST http://localhost:8004/route \
  -H "Content-Type: application/json" \
  -d '{
    "query": "sunset",
    "keywords": ["sunset"],
    "intent": {"is_image_search": true},
    "vector": [0.1, 0.2],
    "filters": {}
  }'
```

### Health Checks
```bash
curl http://localhost:8000/health
curl http://localhost:8003/health
curl http://localhost:8004/health
```

## 🎯 Search Strategies

| Query Type | Example | Auto-Applied Filters |
|------------|---------|---------------------|
| General | "sunset photos" | Vector search, caption matching |
| Documents | "technical documents" | `isDocument=true`, OCR search |
| People | "portrait photos" | `hasPeople=true` |
| High Quality | "beautiful images" | `nimaScore >= 6.0` |
| Screenshots | "app screenshots" | `isScreenshot=true` |

## ⚙️ Configuration

### Enable/Disable Dummy Mode

**Query Optimizer** (`query_optimizer/.env`):
```env
USE_DUMMY_QUERY_OPTIMIZER=true
```

**Search Router** (`search_router/.env`):
```env
USE_DUMMY_SEARCH_ROUTER=true
```

**Next.js** (`next-js/.env`):
```env
QUERY_OPTIMIZER_SERVICE_URL=http://localhost:8003
SEARCH_ROUTER_SERVICE_URL=http://localhost:8004
CLIP_SERVICE_URL=http://localhost:8000
```

## 📊 Response Format
```json
{
  "query": "sunset",
  "results": [
    {
      "id": "uuid",
      "filename": "image.jpg",
      "originalName": "sunset.jpg",
      "mimeType": "image/jpeg",
      "similarity_score": 0.92,
      "combined_score": 0.644,
      "caption": "a beautiful sunset",
      "nima_score": 7.2,
      "attributes": {
        "isDocument": false,
        "hasPeople": false
      }
    }
  ],
  "total_count": 45,
  "pipeline_times": {
    "query_optimization_s": 0.002,
    "text_encoding_s": 0.015,
    "routing_s": 0.001,
    "execution_s": 0.023,
    "total_s": 0.041
  }
}
```

## 🐛 Troubleshooting

### Service Won't Start
```bash
# Check if port is in use
netstat -ano | findstr :<PORT>

# Kill process if needed
taskkill /PID <PID> /F
```

### No Search Results
1. Check if blobs are processed: `processingStatus = 'completed'`
2. Check if embeddings exist in database
3. Verify pgvector extension is enabled

### Slow Searches
- Reduce `limit` parameter
- Add indexes on frequently filtered columns
- Check database query plan

## 📚 Documentation

- **Full Guide**: `next-js/SEARCH_PIPELINE.md`
- **Implementation Summary**: `SEARCH_IMPLEMENTATION_SUMMARY.md`
- **Database Schema**: `next-js/DATABASE_SCHEMA_SUMMARY.md`
- **Services Guide**: `next-js/SERVICES_GUIDE.md`

## 🔗 API Endpoints

### Search
- `POST /api/search` - Full-featured search with filters
- `GET /api/search?q=query` - Simple query string search

### Individual Services
- `POST http://localhost:8000/encode/text` - Text encoding
- `POST http://localhost:8003/optimize` - Query optimization
- `POST http://localhost:8004/route` - Search routing

## 💡 Tips

1. **Use Dummy Mode** for testing without ML models
2. **Filter by NIMA score** for high-quality results
3. **Combine filters** for precise searches
4. **Check pipeline_times** to identify bottlenecks
5. **Use GET endpoint** for simple searches from browser

## 🎓 Example Use Cases

### Find High-Quality Photos
```bash
curl "http://localhost:3000/api/search?q=photos&minNimaScore=7.5&limit=10"
```

### Search Documents
```bash
curl -X POST http://localhost:3000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "invoice document", "filters": {}}'
```

### Find Images with People
```bash
curl "http://localhost:3000/api/search?q=portraits"
```

### Search by Semantic Meaning
```bash
curl "http://localhost:3000/api/search?q=serenity+and+peace"
```

---

**Note**: All Python services use dummy mode by default for testing without ML models. Set `USE_DUMMY_*=false` in `.env` files to enable advanced features.
