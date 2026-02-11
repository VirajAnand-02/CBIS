# app.py - Combined Search Pipeline Service
"""
Combined Search Pipeline Service

This service handles both query optimization and search routing in a single pipeline:
1. Query Optimization: Optimizes queries, extracts keywords, determines intent
2. Search Routing: Determines optimal search strategy based on query analysis

Port: 8003
"""

import os
import re
import time
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# Check if we should use dummy mode
USE_DUMMY = os.environ.get("USE_DUMMY_SEARCH_PIPELINE", "true").lower() in ("true", "1", "yes")

app = FastAPI(title="Search Pipeline API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== QUERY OPTIMIZER ====================

class OptimizeQueryRequest(BaseModel):
    query: str
    max_keywords: int = 10
    enhance: bool = True

class OptimizeQueryResponse(BaseModel):
    original_query: str
    optimized_query: str
    keywords: List[str]
    intent: Dict[str, Any]
    suggestions: Optional[List[str]] = None
    processing_time_s: float

def optimize_query_impl(query: str, max_keywords: int = 10) -> OptimizeQueryResponse:
    """
    TODO: Dummy implementation - replace with trained NLP model.
    """
    start = time.time()
    
    # Basic keyword extraction
    words = re.findall(r'\b\w+\b', query.lower())
    keywords = [w for w in words if len(w) > 2][:max_keywords]
    
    # Basic intent detection
    intent = {
        "is_image_search": any(word in query.lower() for word in ["photo", "image", "picture", "pic"]),
        "is_document_search": any(word in query.lower() for word in ["document", "doc", "pdf", "text"]),
        "is_people_search": any(word in query.lower() for word in ["person", "people", "face", "portrait"]),
        "is_screenshot_search": any(word in query.lower() for word in ["screenshot", "screen", "capture"]),
        "is_aesthetic_search": any(word in query.lower() for word in ["beautiful", "quality", "aesthetic", "good"]),
    }
    
    processing_time = time.time() - start
    
    return OptimizeQueryResponse(
        original_query=query,
        optimized_query=query,
        keywords=keywords,
        intent=intent,
        suggestions=None,
        processing_time_s=processing_time
    )

# ==================== SEARCH ROUTER ====================

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
    vector: List[float]
    filters: Optional[Dict[str, Any]] = None

class SearchStrategy(BaseModel):
    use_vector_search: bool
    use_text_search: bool
    use_metadata_filters: bool
    search_embeddings: bool
    search_ocr: bool
    search_attributes: bool
    vector_weight: float = 0.7
    text_weight: float = 0.2
    metadata_weight: float = 0.1
    mime_type_filter: Optional[List[str]] = None
    attribute_filters: Dict[str, bool] = {}
    min_nima_score: Optional[float] = None
    max_nima_score: Optional[float] = None

class RouteSearchResponse(BaseModel):
    strategy: SearchStrategy
    reasoning: str
    processing_time_s: float

def route_search_impl(request: RouteSearchRequest) -> RouteSearchResponse:
    """
    TODO: Dummy router - replace with trained ML model.
    """
    start = time.time()
    
    intent = request.intent
    
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
        strategy.min_nima_score = 6.0
        reasoning_parts.append("Aesthetic search: filtering for high NIMA scores (>6.0)")
    
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

# ==================== COMBINED PIPELINE ====================

class SearchPipelineRequest(BaseModel):
    query: str
    vector: List[float]  # CLIP embedding
    max_keywords: int = 10
    filters: Optional[Dict[str, Any]] = None

class SearchPipelineResponse(BaseModel):
    # Query optimization results
    original_query: str
    optimized_query: str
    keywords: List[str]
    intent: Dict[str, Any]
    
    # Search routing results
    strategy: SearchStrategy
    reasoning: str
    
    # Timing info
    pipeline_times: Dict[str, float]

@app.post("/pipeline", response_model=SearchPipelineResponse)
async def search_pipeline(request: SearchPipelineRequest):
    """
    Complete search pipeline: optimize query and determine search strategy.
    
    Example:
    POST /pipeline
    {
        "query": "beautiful sunset photos",
        "vector": [0.1, 0.2, ...],
        "max_keywords": 10,
        "filters": {
            "minNimaScore": 6.0
        }
    }
    """
    try:
        if not request.query or not request.query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")
        
        if not request.vector or len(request.vector) == 0:
            raise HTTPException(status_code=400, detail="Search vector cannot be empty")
        
        start_total = time.time()
        
        # Step 1: Optimize query
        opt_result = optimize_query_impl(request.query, request.max_keywords)
        
        # Step 2: Route search
        route_request = RouteSearchRequest(
            query=opt_result.optimized_query,
            keywords=opt_result.keywords,
            intent=SearchIntent(**opt_result.intent),
            vector=request.vector,
            filters=request.filters
        )
        route_result = route_search_impl(route_request)
        
        total_time = time.time() - start_total
        
        return SearchPipelineResponse(
            original_query=opt_result.original_query,
            optimized_query=opt_result.optimized_query,
            keywords=opt_result.keywords,
            intent=opt_result.intent,
            strategy=route_result.strategy,
            reasoning=route_result.reasoning,
            pipeline_times={
                "optimize_s": opt_result.processing_time_s,
                "route_s": route_result.processing_time_s,
                "total_s": total_time
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {str(e)}")

# ==================== LEGACY ENDPOINTS ====================

@app.post("/optimize", response_model=OptimizeQueryResponse)
async def optimize_query(request: OptimizeQueryRequest):
    """Legacy endpoint for query optimization only."""
    try:
        if not request.query or not request.query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")
        
        return optimize_query_impl(request.query, request.max_keywords)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query optimization failed: {str(e)}")

@app.post("/route", response_model=RouteSearchResponse)
async def route_search(request: RouteSearchRequest):
    """Legacy endpoint for search routing only."""
    try:
        if not request.query or not request.query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")
        
        if not request.vector or len(request.vector) == 0:
            raise HTTPException(status_code=400, detail="Search vector cannot be empty")
        
        return route_search_impl(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search routing failed: {str(e)}")

# ==================== HEALTH ====================

@app.get("/health")
def health():
    return {
        "status": "ok",
        "mode": "dummy" if USE_DUMMY else "advanced",
        "version": "2.0.0",
        "endpoints": ["/pipeline", "/optimize", "/route"]
    }

@app.get("/")
async def root():
    return {
        "service": "Search Pipeline API",
        "version": "2.0.0",
        "endpoints": {
            "pipeline": "POST /pipeline - Complete search pipeline",
            "optimize": "POST /optimize - Query optimization only",
            "route": "POST /route - Search routing only",
            "health": "GET /health - Service health"
        }
    }

if __name__ == "__main__":
    import uvicorn
    print("=" * 60)
    print("Search Pipeline Service (Query Optimizer + Search Router)")
    print(f"Mode: {'DUMMY' if USE_DUMMY else 'ADVANCED'}")
    print("Port: 8003")
    print("Endpoints: /pipeline, /optimize, /route")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8003)
