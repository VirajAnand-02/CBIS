# app.py - Query Optimizer Service
"""
Query Optimizer and Keyword Extraction Service

This service takes raw user search queries and:
1. Optimizes/expands the query for better search results
2. Extracts relevant keywords
3. Suggests query corrections/enhancements
4. Determines search intent (image, document, people, etc.)

Port: 8003
"""

import os
import re
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# Check if we should use dummy mode
USE_DUMMY = os.environ.get("USE_DUMMY_QUERY_OPTIMIZER", "false").lower() in ("true", "1", "yes")

app = FastAPI(title="Query Optimizer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Request/Response Models ----------
class OptimizeQueryRequest(BaseModel):
    query: str
    max_keywords: int = 10
    enhance: bool = True  # Whether to expand/enhance the query

class OptimizeQueryResponse(BaseModel):
    original_query: str
    optimized_query: str
    keywords: List[str]
    intent: Dict[str, Any]  # Search intent signals
    suggestions: Optional[List[str]] = None
    processing_time_s: float

# ---------- Dummy Implementation ----------
def dummy_optimize(query: str, max_keywords: int = 10) -> OptimizeQueryResponse:
    """
    Dummy implementation that does basic keyword extraction.
    """
    import time
    start = time.time()
    
    # Basic keyword extraction: split on spaces, remove short words
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
        optimized_query=query,  # No optimization in dummy mode
        keywords=keywords,
        intent=intent,
        suggestions=None,
        processing_time_s=processing_time
    )

# ---------- Advanced Implementation (TODO: Add NLP models) ----------
def advanced_optimize(query: str, max_keywords: int = 10) -> OptimizeQueryResponse:
    """
    Advanced implementation using NLP for:
    - Spell correction
    - Query expansion with synonyms
    - Better keyword extraction (using TF-IDF, NER, etc.)
    - Intent classification
    
    TODO: Implement with spaCy, transformers, or similar
    """
    import time
    start = time.time()
    
    # For now, use dummy implementation
    # In the future, add:
    # - spaCy for NER and POS tagging
    # - TextBlob for spell correction
    # - WordNet for synonym expansion
    # - A small transformer for intent classification
    
    result = dummy_optimize(query, max_keywords)
    result.processing_time_s = time.time() - start
    
    return result

# ---------- Routes ----------
@app.post("/optimize", response_model=OptimizeQueryResponse)
async def optimize_query(request: OptimizeQueryRequest):
    """
    Optimize a search query and extract keywords.
    
    Example:
    POST /optimize
    {
        "query": "beautiful sunset photos with mountains",
        "max_keywords": 10,
        "enhance": true
    }
    
    Returns:
    {
        "original_query": "beautiful sunset photos with mountains",
        "optimized_query": "beautiful sunset photos with mountains",
        "keywords": ["beautiful", "sunset", "photos", "mountains"],
        "intent": {
            "is_image_search": true,
            "is_aesthetic_search": true,
            ...
        },
        "suggestions": null,
        "processing_time_s": 0.001
    }
    """
    try:
        if not request.query or not request.query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")
        
        if USE_DUMMY:
            result = dummy_optimize(request.query, request.max_keywords)
        else:
            result = advanced_optimize(request.query, request.max_keywords)
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query optimization failed: {str(e)}")

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
    print("Query Optimizer Service")
    print(f"Mode: {'DUMMY' if USE_DUMMY else 'ADVANCED'}")
    print("Port: 8003")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8003)
