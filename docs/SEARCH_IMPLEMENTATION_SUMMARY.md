# CBIS Search Pipeline - Implementation Summary

## Current Architecture

The search stack is now consolidated into one Python service plus Next.js orchestration.

1. `services/clip/app.py` (Port 8000)
- Image embedding/caption
- Text embedding endpoint: `POST /encode/text`

2. `services/search-pipeline/app.py` (Port 8003)
- Combined query optimization + routing endpoint: `POST /pipeline`
- Backward-compatible endpoints: `POST /optimize`, `POST /route`

3. `apps/next-js/lib/search-manager.ts`
- Calls CLIP text encoding
- Calls Search Pipeline
- Executes pgvector search via Prisma/raw SQL helpers

4. `apps/next-js/app/api/search/route.ts`
- Public search API (`GET` and `POST`)

## Active Search Flow

```text
User Query
  -> CLIP /encode/text (8000)
  -> Search Pipeline /pipeline (8003)
  -> DB vector search (pgvector)
  -> Ranked results
```

## Key Files

- `services/clip/app.py`
- `services/search-pipeline/app.py`
- `apps/next-js/lib/search-manager.ts`
- `apps/next-js/app/api/search/route.ts`
- `apps/next-js/lib/db.ts`

## Environment Variables (current)

```env
CLIP_SERVICE_URL=http://localhost:8000
SEARCH_PIPELINE_SERVICE_URL=http://localhost:8003
TYPE_ROUTER_SERVICE_URL=http://localhost:8001
NIMA_SERVICE_URL=http://localhost:8002
FACE_DETECTION_SERVICE_URL=http://localhost:8005
```

## Startup

Use:
```powershell
.\start-services.ps1
```

This starts:
- CLIP (8000)
- Type Router V2 (8001)
- NIMA (8002)
- Search Pipeline (8003)
- Face Detection (8005)
- Next.js (3000)

## Notes

- Legacy standalone `query_optimizer` and `search_router` are archived under `archive/legacy/`.
- Docker assets are archived under `infra/docker-legacy/`.
