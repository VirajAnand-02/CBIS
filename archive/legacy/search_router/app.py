# app.py - Search Router Service
"""
Search Router Service

This service determines which database tables/modalities to search based on:
1. Query intent from Query Optimizer
2. Search vector from CLIP
3. Keywords and filters

It returns a search strategy that the executor (Next.js) will use.

Port: 8004
"""

import os
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# Check if we should use dummy mode
USE_DUMMY = os.environ.get("USE_DUMMY_SEARCH_ROUTER", "false").lower() in ("true", "1", "yes")

app = FastAPI(title="Search Router API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Request/Response Models ----------
class SearchIntent(BaseModel):
    is_image_search: bool = False
    is_document_search: bool = False
    is_people_search: bool = False
    is_screenshot_search: bool = False
    is_aesthetic_search: bool = False

class RouteSearchRequest(BaseModel):
    query: str
    keywords: List[str]
    intent: SearchIntent
    vector: List[float]  # CLIP embedding
    filters: Optional[Dict[str, Any]] = None

class SearchStrategy(BaseModel):
    """
    Defines which tables/modalities to search and how to weight them
    """
    use_vector_search: bool
    use_text_search: bool
    use_metadata_filters: bool
    
    # Which tables to query
    search_embeddings: bool
    search_ocr: bool
    search_attributes: bool
    
    # Weights for result ranking
    vector_weight: float = 0.7
    text_weight: float = 0.2
    metadata_weight: float = 0.1
    
    # Filters to apply
    mime_type_filter: Optional[List[str]] = None
    attribute_filters: Dict[str, bool] = {}
    
    # Quality/aesthetic filters
    min_nima_score: Optional[float] = None
    max_nima_score: Optional[float] = None

class RouteSearchResponse(BaseModel):
    strategy: SearchStrategy
    reasoning: str  # Explanation of routing decision
    processing_time_s: float

# ---------- TODO: Dummy Implementation (Replace with ML model) ----------
def dummy_route(request: RouteSearchRequest) -> RouteSearchResponse:
    """
    TODO: Dummy router that makes simple decisions based on intent.
    This should be replaced with a trained ML model for production.
    """
    import time
    start = time.time()
    
    intent = request.intent
    
    # Default strategy: vector search on embeddings
    strategy = SearchStrategy(
        use_vector_search=True,
        use_text_search=True,
        use_metadata_filters=False,
        search_embeddings=True,
        search_ocr=False,
        search_attributes=False,
        vector_weight=0.7,
        text_weight=0.3,
        metadata_weight=0.0
    )
    
    reasoning_parts = ["Using vector similarity search on CLIP embeddings"]
    
    # Adjust based on intent
    if intent.is_document_search:
        strategy.search_ocr = True
        strategy.text_weight = 0.5
        strategy.vector_weight = 0.5
        strategy.attribute_filters["isDocument"] = True
        strategy.use_metadata_filters = True
        reasoning_parts.append("Document search: enabled OCR search and document filter")
    
    if intent.is_people_search:
        strategy.attribute_filters["hasPeople"] = True
        strategy.use_metadata_filters = True
        reasoning_parts.append("People search: filtering for images with people")
    
    if intent.is_screenshot_search:
        strategy.attribute_filters["isScreenshot"] = True
        strategy.use_metadata_filters = True
        reasoning_parts.append("Screenshot search: filtering for screenshots")
    
    if intent.is_aesthetic_search:
        strategy.search_attributes = True
        strategy.min_nima_score = 6.0  # Only high-quality images
        reasoning_parts.append("Aesthetic search: filtering for high NIMA scores (>6.0)")
    
    # Apply any user-provided filters
    if request.filters:
        if "mimeType" in request.filters:
            strategy.mime_type_filter = request.filters["mimeType"]
            reasoning_parts.append(f"MIME type filter: {request.filters['mimeType']}")
        
        if "minNimaScore" in request.filters:
            strategy.min_nima_score = request.filters["minNimaScore"]
        
        if "maxNimaScore" in request.filters:
            strategy.max_nima_score = request.filters["maxNimaScore"]
    
    processing_time = time.time() - start
    reasoning = "; ".join(reasoning_parts)
    
    return RouteSearchResponse(
        strategy=strategy,
        reasoning=reasoning,
        processing_time_s=processing_time
    )

# ---------- Advanced Implementation ----------
def advanced_route(request: RouteSearchRequest) -> RouteSearchResponse:
    """
    Advanced router that could use ML models to optimize search strategy.
    
    TODO: Implement with:
    - Query performance history
    - User feedback signals
    - A/B testing of strategies
    - ML model to predict best strategy
    """
    import time
    start = time.time()
    
    # TODO: For now, use dummy implementation - replace with ML model
    result = dummy_route(request)
    result.processing_time_s = time.time() - start
    
    return result

# ---------- Routes ----------
@app.post("/route", response_model=RouteSearchResponse)
async def route_search(request: RouteSearchRequest):
    """
    Determine the optimal search strategy based on query analysis.
    
    Example:
    POST /route
    {
        "query": "beautiful sunset photos",
        "keywords": ["beautiful", "sunset", "photos"],
        "intent": {
            "is_image_search": true,
            "is_aesthetic_search": true
        },
        "vector": [0.1, 0.2, ...],  // CLIP embedding
        "filters": {
            "minNimaScore": 6.0
        }
    }
    
    Returns:
    {
        "strategy": {
            "use_vector_search": true,
            "search_embeddings": true,
            "min_nima_score": 6.0,
            ...
        },
        "reasoning": "Using vector similarity...",
        "processing_time_s": 0.002
    }
    """
    try:
        if not request.query or not request.query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")
        
        if not request.vector or len(request.vector) == 0:
            raise HTTPException(status_code=400, detail="Search vector cannot be empty")
        
        if USE_DUMMY:
            result = dummy_route(request)
        else:
            result = advanced_route(request)
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search routing failed: {str(e)}")

@app.get("/health")
def health():
    return {
        "status": "ok",
        "mode": "dummy" if USE_DUMMY else "advanced",
        "version": "1.0.0"
    }

if __name__ == "__main__":
    import uvicorn
    print("=" * 60)
    print("Search Router Service")
    print(f"Mode: {'DUMMY' if USE_DUMMY else 'ADVANCED'}")
    print("Port: 8004")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8004)
