"""Lead scoring API endpoints"""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.schemas.responses import (
    LeadScoreBatchResponseSchema,
    LeadScoreSchema,
    SignalBreakdownSchema,
)
from app.services.lead_scoring import LeadScoreResult, LeadScoringService
from app.utils.cache import CacheService
from app.utils.db import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Request bodies ────────────────────────────────────────────────────────────

class ScoreRequest(BaseModel):
    inquiryId: int = Field(..., description="Inquiry ID to score")


class BatchScoreRequest(BaseModel):
    inquiryIds: List[int] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="List of inquiry IDs to score (max 50)",
    )


# ── Helper ────────────────────────────────────────────────────────────────────

def _to_schema(result: LeadScoreResult, cached: bool = False) -> LeadScoreSchema:
    return LeadScoreSchema(
        inquiryId=result.inquiry_id,
        clientId=result.client_id,
        score=result.score,
        priority=result.priority,
        breakdown=SignalBreakdownSchema(
            purchasing_history=result.breakdown.purchasing_history,
            inquiry_type=result.breakdown.inquiry_type,
            reservation_status=result.breakdown.reservation_status,
            inquiry_frequency=result.breakdown.inquiry_frequency,
            response_engagement=result.breakdown.response_engagement,
            vehicle_price_band=result.breakdown.vehicle_price_band,
        ),
        cached=cached,
        scoredAt=result.scored_at,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/leads/score",
    response_model=LeadScoreSchema,
    summary="Score a single inquiry",
    description=(
        "Returns a 0–100 conversion-likelihood score and a Hot/Warm/Cold priority label "
        "for one inquiry, along with a per-signal breakdown."
    ),
)
async def score_single(body: ScoreRequest, db: Session = Depends(get_db)):
    logger.info(f"Lead score request: inquiry_id={body.inquiryId}")

    cached = CacheService.get_lead_score(body.inquiryId)
    if cached:
        logger.info(f"Returning cached lead score for inquiry {body.inquiryId}")
        cached["cached"] = True
        return cached

    service = LeadScoringService(db)
    result = service.score_inquiry(body.inquiryId)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Inquiry {body.inquiryId} not found.",
        )

    schema = _to_schema(result)
    CacheService.set_lead_score(body.inquiryId, schema.model_dump(mode="json"))

    logger.info(
        f"Scored inquiry {body.inquiryId}: score={result.score} priority={result.priority}"
    )
    return schema


@router.post(
    "/leads/score/batch",
    response_model=LeadScoreBatchResponseSchema,
    summary="Score a batch of inquiries",
    description=(
        "Score up to 50 inquiries in one call. "
        "Cache hits are served immediately; misses are scored together to avoid N+1 DB queries. "
        "Inquiry IDs not found in the database are listed in failedIds."
    ),
)
async def score_batch(body: BatchScoreRequest, db: Session = Depends(get_db)):
    logger.info(f"Batch lead score request: {len(body.inquiryIds)} inquiries")

    # Split IDs into cache hits and misses
    cached_results: List[LeadScoreSchema] = []
    miss_ids: List[int] = []

    for iid in body.inquiryIds:
        hit = CacheService.get_lead_score(iid)
        if hit:
            hit["cached"] = True
            cached_results.append(LeadScoreSchema(**hit))
        else:
            miss_ids.append(iid)

    # Score the misses in one service call
    fresh_results: List[LeadScoreSchema] = []
    failed_ids: List[int] = []

    if miss_ids:
        service = LeadScoringService(db)
        computed, failed_ids = service.score_batch(miss_ids)
        for result in computed:
            schema = _to_schema(result)
            CacheService.set_lead_score(result.inquiry_id, schema.model_dump(mode="json"))
            fresh_results.append(schema)

    all_results = cached_results + fresh_results

    logger.info(
        f"Batch complete: {len(all_results)} scored "
        f"({len(cached_results)} cached, {len(fresh_results)} fresh), "
        f"{len(failed_ids)} failed"
    )

    return LeadScoreBatchResponseSchema(
        results=all_results,
        totalScored=len(all_results),
        failedIds=failed_ids,
    )
