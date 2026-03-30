"""Similarity API endpoints"""
import logging
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.schemas.responses import SimilarityResponseSchema
from app.services.content_similarity import ContentSimilarityService
from app.utils.cache import CacheService
from app.utils.db import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/vehicles/similar/content",
    response_model=SimilarityResponseSchema,
    summary="Content-based similarity",
    description="Find similar vehicles based on attributes (make, model, price, year, etc.)"
)
async def get_content_based_similarity(
    vehicleId: int = Query(..., description="Source vehicle ID"),
    type: Literal["car", "motorcycle"] = Query(..., description="Vehicle type"),
    limit: int = Query(10, ge=1, le=50, description="Maximum results"),
    db: Session = Depends(get_db)
):
    """Get content-based similar vehicles"""
    logger.info(f"Content similarity request: {type} ID={vehicleId}, limit={limit}")
    
    try:
        # Check cache first
        cached_result = CacheService.get_similarity(type, vehicleId)
        if cached_result and cached_result.get("method") == "content":
            logger.info(f"Returning cached content similarity for {type}:{vehicleId}")
            return {**cached_result, "cached": True}
        
        # Compute similarity
        service = ContentSimilarityService(db)
        
        if type == "car":
            suggestions = service.find_similar_cars(vehicleId, limit=limit)
        else:
            suggestions = service.find_similar_motorcycles(vehicleId, limit=limit)
        
        response = {
            "sourceVehicleId": vehicleId,
            "vehicleType": type,
            "suggestions": suggestions,
            "method": "content",
            "cached": False
        }
        
        # Cache result
        CacheService.set_similarity(type, vehicleId, response)
        
        logger.info(f"Computed {len(suggestions)} content-based suggestions for {type}:{vehicleId}")
        return response
        
    except Exception as e:
        logger.error(f"Error computing content similarity for {type}:{vehicleId}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error computing similarity: {str(e)}"
        )


@router.get(
    "/vehicles/similar",
    response_model=SimilarityResponseSchema,
    summary="Vehicle similarity (hybrid)",
    description="Find similar vehicles using hybrid approach (content + collaborative)"
)
async def get_similar_vehicles(
    vehicleId: int = Query(..., description="Source vehicle ID"),
    type: Literal["car", "motorcycle"] = Query(..., description="Vehicle type"),
    limit: int = Query(10, ge=1, le=50, description="Maximum results"),
    db: Session = Depends(get_db)
):
    """
    Get similar vehicles using hybrid approach
    
    For now, this endpoints forwards to content-based similarity.
    Collaborative filtering and hybrid ranking will be added in later phases.
    """
    logger.info(f"Hybrid similarity request (content-only for now): {type} ID={vehicleId}")
    
    # Check precomputed cache first
    precomputed = CacheService.get_precomputed_similarity(type, vehicleId)
    if precomputed:
        logger.info(f"Returning precomputed similarity for {type}:{vehicleId}")
        return {**precomputed, "cached": True}
    
    # Fall back to content-based for now
    return await get_content_based_similarity(vehicleId, type, limit, db)
