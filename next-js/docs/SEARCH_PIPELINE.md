# Search Pipeline Documentation

## Overview

The CBIS Search Pipeline provides semantic search capabilities across uploaded media blobs using a multi-stage architecture inspired by the preprocessing pipeline. It combines vector similarity search, text matching, and metadata filtering to deliver relevant results.

## Architecture

```
User Query → Query Optimizer → CLIP Text Encoder → Search Router → Database Executor → Results
```

### Components

#### 1. **Query Optimizer Service** (Port 8003)
- **Location**: `query_optimizer/app.py`
- **Purpose**: Optimizes raw user queries for better search results
- **Features**:
  - Keyword extraction
  - Query intent detection (image/document/people/screenshot/aesthetic search)
  - Spell correction (planned)
  - Query expansion with synonyms (planned)
- **Dummy Mode**: Basic keyword splitting and simple intent detection

#### 2. **CLIP Text Encoder** (Port 8000)
- **Location**: `clip/app.py` - endpoint `/encode/text`
- **Purpose**: Converts text queries to 512-dimensional CLIP embeddings
- **Features**:
  - Uses same CLIP model as image encoding for semantic consistency
  - Normalized vectors for cosine similarity
  - GPU-accelerated when available

#### 3. **Search Router Service** (Port 8004)
- **Location**: `search_router/app.py`
- **Purpose**: Determines optimal search strategy based on query analysis
- **Features**:
  - Decides which tables/modalities to search
  - Sets weights for different search methods (vector/text/metadata)
  - Applies attribute filters (document/people/screenshot)
  - Configures quality filters (NIMA scores)
- **Dummy Mode**: Rule-based strategy selection

#### 4. **Search Manager** (Next.js)
- **Location**: `next-js/lib/search-manager.ts`
- **Purpose**: Orchestrates the entire search flow
- **Features**:
  - Executes vector similarity search using pgvector
  - Combines multiple search methods with weighted scoring
  - Applies filters and pagination
  - Tracks performance metrics

#### 5. **Search API Endpoint**
- **Location**: `next-js/app/api/search/route.ts`
- **Endpoints**:
  - `POST /api/search` - Full search with JSON body
  - `GET /api/search?q=query` - Simple GET search

## Search Flow

### 1. Query Optimization
```json
POST http://localhost:8003/optimize
{
  "query": "beautiful sunset photos with mountains",
  "max_keywords": 10,
  "enhance": true
}
```

**Response:**
```json
{
  "original_query": "beautiful sunset photos with mountains",
  "optimized_query": "beautiful sunset photos with mountains",
  "keywords": ["beautiful", "sunset", "photos", "mountains"],
  "intent": {
    "is_image_search": true,
    "is_document_search": false,
    "is_people_search": false,
    "is_screenshot_search": false,
    "is_aesthetic_search": true
  },
  "processing_time_s": 0.002
}
```

### 2. Text Encoding
```json
POST http://localhost:8000/encode/text
{
  "text": "beautiful sunset photos with mountains",
  "normalize": true
}
```

**Response:**
```json
{
  "embedding": [0.123, -0.456, ...], // 512 dimensions
  "text": "beautiful sunset photos with mountains",
  "device": "cuda",
  "times": {
    "encoding_s": 0.015
  }
}
```

### 3. Search Routing
```json
POST http://localhost:8004/route
{
  "query": "beautiful sunset photos",
  "keywords": ["beautiful", "sunset", "photos"],
  "intent": { "is_image_search": true, "is_aesthetic_search": true },
  "vector": [0.123, -0.456, ...],
  "filters": { "minNimaScore": 6.0 }
}
```

**Response:**
```json
{
  "strategy": {
    "use_vector_search": true,
    "use_text_search": true,
    "use_metadata_filters": false,
    "search_embeddings": true,
    "search_ocr": false,
    "search_attributes": true,
    "vector_weight": 0.7,
    "text_weight": 0.3,
    "metadata_weight": 0.0,
    "min_nima_score": 6.0,
    "attribute_filters": {}
  },
  "reasoning": "Using vector similarity search on CLIP embeddings; Aesthetic search: filtering for high NIMA scores (>6.0)",
  "processing_time_s": 0.001
}
```

### 4. Database Execution
The search manager executes a vector similarity query using pgvector:

```sql
SELECT 
  b.id,
  b.filename,
  b."originalName",
  b."mimeType",
  b.size,
  b.width,
  b.height,
  b."uploadedAt",
  e.caption,
  ba."nimaScore",
  ba."isDocument",
  ba."hasPeople",
  ba."isScreenshot",
  ba."isAnimal",
  1 - (e.vector <=> '[...]'::vector) as similarity_score
FROM "Blob" b
LEFT JOIN "Embedding" e ON e."blobId" = b.id
LEFT JOIN "BlobAttribute" ba ON ba."blobId" = b.id
WHERE e.vector IS NOT NULL
ORDER BY e.vector <=> '[...]'::vector
LIMIT 20
```

### 5. Final Response
```json
POST /api/search
{
  "query": "beautiful sunset photos",
  "limit": 20,
  "offset": 0
}
```

**Response:**
```json
{
  "query": "beautiful sunset photos",
  "results": [
    {
      "id": "uuid",
      "filename": "abc123.jpg",
      "originalName": "sunset.jpg",
      "mimeType": "image/jpeg",
      "size": 2048576,
      "width": 1920,
      "height": 1080,
      "uploadedAt": "2025-11-03T10:00:00.000Z",
      "similarity_score": 0.92,
      "combined_score": 0.644,
      "caption": "a beautiful sunset over mountains",
      "nima_score": 7.2,
      "attributes": {
        "isDocument": false,
        "hasPeople": false,
        "isScreenshot": false,
        "isAnimal": false
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
  },
  "strategy": { ... },
  "reasoning": "Using vector similarity search..."
}
```

## Setup and Configuration

### Environment Variables

Add to `next-js/.env`:
```env
# Python Service URLs - Search Pipeline
QUERY_OPTIMIZER_SERVICE_URL=http://localhost:8003
SEARCH_ROUTER_SERVICE_URL=http://localhost:8004
CLIP_SERVICE_URL=http://localhost:8000
```

Add to `query_optimizer/.env`:
```env
USE_DUMMY_QUERY_OPTIMIZER=true
```

Add to `search_router/.env`:
```env
USE_DUMMY_SEARCH_ROUTER=true
```

### Starting Services

```powershell
# Terminal 1 - CLIP Service (includes text encoding)
cd E:\programming\CBIS_Project\clip
conda activate clip-env
python -m uvicorn app:app --host 0.0.0.0 --port 8000

# Terminal 2 - Query Optimizer
cd E:\programming\CBIS_Project\query_optimizer
conda activate clip-env
python app.py

# Terminal 3 - Search Router
cd E:\programming\CBIS_Project\search_router
conda activate clip-env
python app.py

# Terminal 4 - Next.js
cd E:\programming\CBIS_Project\next-js
npm run dev
```

## Usage Examples

### Basic Search (GET)
```bash
curl "http://localhost:3000/api/search?q=sunset&limit=10"
```

### Advanced Search (POST)
```bash
curl -X POST http://localhost:3000/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "documents about technology",
    "filters": {
      "mimeType": ["image/jpeg", "image/png"],
      "minNimaScore": 5.0
    },
    "limit": 20,
    "offset": 0
  }'
```

### Search with Intent
```bash
# Search for high-quality photos with people
curl -X POST http://localhost:3000/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "beautiful portrait photos",
    "filters": {
      "minNimaScore": 7.0
    },
    "limit": 10
  }'
```

## Search Strategies

The Search Router applies different strategies based on query intent:

### Image Search (Default)
- **Vector weight**: 0.7
- **Text weight**: 0.3
- **Tables**: Embeddings + Captions

### Document Search
- **Vector weight**: 0.5
- **Text weight**: 0.5
- **Tables**: Embeddings + OCR Results
- **Filters**: `isDocument = true`

### People Search
- **Vector weight**: 0.7
- **Text weight**: 0.3
- **Tables**: Embeddings
- **Filters**: `hasPeople = true`

### Aesthetic Search
- **Vector weight**: 0.7
- **Text weight**: 0.3
- **Tables**: Embeddings + Attributes
- **Filters**: `nimaScore >= 6.0`

## Performance Metrics

Each search response includes timing breakdowns:

```json
{
  "pipeline_times": {
    "query_optimization_s": 0.002,  // Query processing
    "text_encoding_s": 0.015,        // CLIP encoding
    "routing_s": 0.001,              // Strategy selection
    "execution_s": 0.023,            // Database query
    "total_s": 0.041                 // End-to-end time
  }
}
```

## Advanced Features (Planned)

### Query Optimizer Enhancements
- [ ] Spell correction using TextBlob
- [ ] Query expansion with WordNet synonyms
- [ ] Named Entity Recognition for better keyword extraction
- [ ] Small transformer for intent classification

### Search Router Enhancements
- [ ] ML-based strategy optimization
- [ ] A/B testing of strategies
- [ ] User feedback integration
- [ ] Query performance history

### Database Optimizations
- [ ] Hybrid search (vector + full-text)
- [ ] Result caching
- [ ] Query plan analysis
- [ ] Index optimization

## Troubleshooting

### Service Not Available
If a service is down, the pipeline uses fallbacks:
- **Query Optimizer**: Basic keyword splitting
- **Search Router**: Default vector search strategy
- **CLIP**: Throws error (required service)

### Empty Results
Check:
1. Are blobs processed? (`processingStatus = 'completed'`)
2. Do blobs have embeddings? Check `Embedding` table
3. Is pgvector extension enabled? Run `CREATE EXTENSION IF NOT EXISTS vector`

### Slow Searches
Optimize:
1. Add database indexes on frequently filtered columns
2. Reduce result limit for initial queries
3. Use pagination instead of large offsets
4. Cache frequent queries

## API Reference

See `SEARCH_API.md` for complete API documentation.

## Related Documentation

- [DATABASE_SCHEMA_SUMMARY.md](DATABASE_SCHEMA_SUMMARY.md) - Database structure
- [PREPROCESSING_PIPELINE.md](PREPROCESSING_PIPELINE.md) - Image preprocessing flow
- [SERVICES_GUIDE.md](SERVICES_GUIDE.md) - All services overview
