"""Response schemas"""
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
