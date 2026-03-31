"""Similarity API endpoints"""
import logging
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.schemas.responses import SimilarityResponseSchema
from app.services.collaborative_similarity import CollaborativeSimilarityService
from app.services.content_similarity import ContentSimilarityService
from app.services.hybrid_ranker import HybridRanker
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
    "/vehicles/similar/collaborative",
    response_model=SimilarityResponseSchema,
    summary="Collaborative filtering similarity",
    description="Find similar vehicles based on shared client inquiry history"
)
async def get_collaborative_similarity(
    vehicleId: int = Query(..., description="Source vehicle ID"),
    type: Literal["car", "motorcycle"] = Query(..., description="Vehicle type"),
    limit: int = Query(10, ge=1, le=50, description="Maximum results"),
    db: Session = Depends(get_db)
):
    """Get collaborative-filtering similar vehicles.

    Falls back to content-based similarity when interaction data is insufficient
    (fewer than MIN_INTERACTIONS_THRESHOLD inquiries or MIN_CLIENTS_THRESHOLD clients).
    """
    logger.info(f"Collaborative similarity request: {type} ID={vehicleId}, limit={limit}")

    try:
        # Check collaborative cache first (24h TTL)
        cached_result = CacheService.get_collaborative_similarity(type, vehicleId)
        if cached_result:
            logger.info(f"Returning cached collaborative similarity for {type}:{vehicleId}")
            return {**cached_result, "cached": True}

        service = CollaborativeSimilarityService(db)

        if type == "car":
            suggestions = service.find_similar_cars(vehicleId, limit=limit)
        else:
            suggestions = service.find_similar_motorcycles(vehicleId, limit=limit)

        # Fall back to content-based when insufficient interaction data
        if not suggestions:
            logger.info(
                f"Collaborative fallback to content-based for {type}:{vehicleId} "
                "(insufficient interaction data)"
            )
            return await get_content_based_similarity(vehicleId, type, limit, db)

        response = {
            "sourceVehicleId": vehicleId,
            "vehicleType": type,
            "suggestions": suggestions,
            "method": "collaborative",
            "cached": False,
        }

        CacheService.set_collaborative_similarity(type, vehicleId, response)
        logger.info(
            f"Computed {len(suggestions)} collaborative suggestions for {type}:{vehicleId}"
        )
        return response

    except Exception as e:
        logger.error(
            f"Error computing collaborative similarity for {type}:{vehicleId}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Error computing collaborative similarity: {str(e)}",
        )


@router.get(
    "/vehicles/similar",
    response_model=SimilarityResponseSchema,
    summary="Vehicle similarity (hybrid)",
    description="Find similar vehicles using hybrid approach (60% content + 40% collaborative)"
)
async def get_similar_vehicles(
    vehicleId: int = Query(..., description="Source vehicle ID"),
    type: Literal["car", "motorcycle"] = Query(..., description="Vehicle type"),
    limit: int = Query(10, ge=1, le=50, description="Maximum results"),
    db: Session = Depends(get_db)
):
    """Get similar vehicles using hybrid ranking (content-based + collaborative filtering)."""
    logger.info(f"Hybrid similarity request: {type} ID={vehicleId}, limit={limit}")

    try:
        # Check precomputed cache first
        precomputed = CacheService.get_precomputed_similarity(type, vehicleId)
        if precomputed:
            logger.info(f"Returning precomputed similarity for {type}:{vehicleId}")
            return {**precomputed, "cached": True}

        ranker = HybridRanker(db)

        if type == "car":
            suggestions, method = ranker.find_similar_cars(vehicleId, limit=limit)
        else:
            suggestions, method = ranker.find_similar_motorcycles(vehicleId, limit=limit)

        response = {
            "sourceVehicleId": vehicleId,
            "vehicleType": type,
            "suggestions": suggestions,
            "method": method,
            "cached": False,
        }

        # Cache on-demand hybrid results
        CacheService.set_similarity(type, vehicleId, response)
        logger.info(
            f"Computed {len(suggestions)} hybrid suggestions for {type}:{vehicleId} "
            f"via '{method}'"
        )
        return response

    except Exception as e:
        logger.error(
            f"Error computing hybrid similarity for {type}:{vehicleId}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Error computing similarity: {str(e)}",
        )
