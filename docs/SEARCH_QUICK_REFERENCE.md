# CBIS Search Pipeline - Quick Reference

## Start Services
```powershell
.\start-services.ps1
```

## Service Ports
| Service | Port | Purpose |
|---------|------|---------|
| CLIP | 8000 | Image + text embedding/caption |
| Type Router V2 | 8001 | Image attribute classification |
| NIMA | 8002 | Aesthetic scoring |
| Search Pipeline | 8003 | Query optimize + route |
| Face Detection | 8005 | Face detection/recognition |
| Next.js | 3000 | Web/API layer |

## Search Examples

### Simple query
```bash
curl "http://localhost:3000/api/search?q=sunset"
```

### Query with filters
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

## Service Checks

```bash
curl http://localhost:8000/health
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health
curl http://localhost:8005/health
```

## Search Pipeline APIs

```bash
# Combined endpoint
curl -X POST http://localhost:8003/pipeline \
  -H "Content-Type: application/json" \
  -d '{"query":"sunset photos","vector":[0.1,0.2]}'

# Legacy-compatible endpoints in same service
curl -X POST http://localhost:8003/optimize -H "Content-Type: application/json" -d '{"query":"sunset photos"}'
curl -X POST http://localhost:8003/route -H "Content-Type: application/json" -d '{"query":"sunset","keywords":["sunset"],"intent":{"is_image_search":true},"vector":[0.1,0.2]}'
```

## Environment Variables

Use `apps/next-js/.env`:
```env
CLIP_SERVICE_URL=http://localhost:8000
TYPE_ROUTER_SERVICE_URL=http://localhost:8001
NIMA_SERVICE_URL=http://localhost:8002
SEARCH_PIPELINE_SERVICE_URL=http://localhost:8003
FACE_DETECTION_SERVICE_URL=http://localhost:8005
```

## Paths
- Full guide: `docs/SERVICES_GUIDE.md`
- Next.js search manager: `apps/next-js/lib/search-manager.ts`
- Next.js search API: `apps/next-js/app/api/search/route.ts`
- Search pipeline service: `services/search-pipeline/app.py`
