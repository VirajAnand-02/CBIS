# Search Pipeline Service

Combined Query Optimizer + Search Router service for CBIS.

## Overview

This service combines two previously separate services into one:
1. **Query Optimizer** - Optimizes queries, extracts keywords, determines intent
2. **Search Router** - Determines optimal search strategy based on query analysis

Port: **8003**

## Endpoints

### `/pipeline` - Complete Pipeline (Recommended)
Combined endpoint that handles both optimization and routing in one call.

```bash
POST /pipeline
{
  "query": "beautiful sunset photos",
  "vector": [0.1, 0.2, ...],  # CLIP embedding (512-dim)
  "max_keywords": 10,
  "filters": {
    "minNimaScore": 6.0
  }
}
```

**Response:**
```json
{
  "original_query": "beautiful sunset photos",
  "optimized_query": "beautiful sunset photos",
  "keywords": ["beautiful", "sunset", "photos"],
  "intent": {
    "is_image_search": true,
    "is_aesthetic_search": true,
    ...
  },
  "strategy": {
    "use_vector_search": true,
    "min_nima_score": 6.0,
    ...
  },
  "reasoning": "Using vector similarity...",
  "pipeline_times": {
    "optimize_s": 0.001,
    "route_s": 0.002,
    "total_s": 0.003
  }
}
```

### `/optimize` - Query Optimization Only (Legacy)
```bash
POST /optimize
{
  "query": "beautiful sunset photos",
  "max_keywords": 10
}
```

### `/route` - Search Routing Only (Legacy)
```bash
POST /route
{
  "query": "beautiful sunset photos",
  "keywords": ["beautiful", "sunset", "photos"],
  "intent": {...},
  "vector": [0.1, 0.2, ...],
  "filters": {...}
}
```

### `/health` - Health Check
```bash
GET /health
```

## Configuration

Edit `.env` file:

```env
# Dummy mode: Set to true to use simple keyword extraction
# Set to false to use ML models (when implemented)
USE_DUMMY_SEARCH_PIPELINE=true
```

## Running

```bash
# Install dependencies
pip install -r requirements.txt

# Run service
python app.py
```

Or use the startup script:
```powershell
.\start-services.ps1
```

## Docker

```bash
# Build
docker build -t search-pipeline .

# Run
docker run -p 8003:8003 search-pipeline
```

## Integration

### Next.js
Set environment variable in `next-js/.env`:
```env
SEARCH_PIPELINE_SERVICE_URL=http://localhost:8003
```

The search manager will automatically use the `/pipeline` endpoint.

## Migration from Separate Services

This service replaces:
- `query_optimizer` (port 8003)
- `search_router` (port 8004)

Both old services are still available as legacy endpoints (`/optimize` and `/route`) for backward compatibility.

## Future Enhancements

- [ ] ML-based query expansion with synonyms
- [ ] Spell correction using TextBlob
- [ ] Named Entity Recognition for better keyword extraction
- [ ] Small transformer for intent classification
- [ ] ML-based search strategy optimization
- [ ] A/B testing of strategies
- [ ] User feedback integration
