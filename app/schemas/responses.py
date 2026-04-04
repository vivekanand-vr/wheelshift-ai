"""Response schemas"""
from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class VehicleDetailSchema(BaseModel):
    """Vehicle detail information in similarity response"""
    make: str
    model: str
    year: int
    price: float


class SimilarVehicleSchema(BaseModel):
    """Single similar vehicle result"""
    vehicleId: int = Field(..., description="Vehicle ID")
    score: float = Field(..., ge=0, le=1, description="Similarity score (0-1)")
    reason: str = Field(..., description="Human-readable similarity reason")
    details: Optional[VehicleDetailSchema] = None


class SimilarityResponseSchema(BaseModel):
    """Response for similarity API"""
    sourceVehicleId: int
    vehicleType: str = Field(..., pattern="^(car|motorcycle)$")
    suggestions: List[SimilarVehicleSchema]
    method: str = Field(..., description="Similarity method used: content, collaborative, or hybrid")
    cached: bool = Field(default=False, description="Whether result was served from cache")


class HealthCheckSchema(BaseModel):
    """Health check response"""
    status: str
    service: str
    version: str
    environment: str
    checks: Dict


# ── Lead Scoring ────────────────────────────────────────────────────────────

class SignalBreakdownSchema(BaseModel):
    """Per-signal point contributions for a lead score"""
    purchasing_history: int = Field(..., ge=0, le=30)
    inquiry_type: int = Field(..., ge=0, le=20)
    reservation_status: int = Field(..., ge=0, le=15)
    inquiry_frequency: int = Field(..., ge=0, le=15)
    response_engagement: int = Field(..., ge=0, le=10)
    vehicle_price_band: int = Field(..., ge=0, le=10)


class LeadScoreSchema(BaseModel):
    """Score result for a single inquiry"""
    inquiryId: int
    clientId: int
    score: int = Field(..., ge=0, le=100, description="Conversion likelihood score 0–100")
    priority: str = Field(..., pattern="^(Hot|Warm|Cold)$", description="Hot ≥70 / Warm 40–69 / Cold <40")
    breakdown: SignalBreakdownSchema
    cached: bool = False
    scoredAt: datetime


class LeadScoreBatchResponseSchema(BaseModel):
    """Batch scoring response"""
    results: List[LeadScoreSchema]
    totalScored: int
    failedIds: List[int] = Field(default_factory=list, description="Inquiry IDs not found in DB")

