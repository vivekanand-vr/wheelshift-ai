"""Content-based similarity engine"""
import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.vehicle_models import Car, Motorcycle
from app.services.feature_engineering import FeatureEngineer
from app.utils.cache import CacheService

logger = logging.getLogger(__name__)
settings = get_settings()


class ContentSimilarityService:
    """Compute content-based vehicle similarity"""
    
    def __init__(self, db: Session):
        self.db = db
        self.feature_engineer = FeatureEngineer(db)
    
    def find_similar_cars(
        self,
        car_id: int,
        limit: int = 10,
        exclude_statuses: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Find similar cars based on content features
        
        Args:
            car_id: Source car ID
            limit: Maximum number of similar cars to return
            exclude_statuses: Car statuses to exclude (default: ["SOLD"])
            
        Returns:
            List of similar cars with scores and reasons
        """
        if exclude_statuses is None:
            exclude_statuses = ["SOLD"]
        
        # Get source car features
        source_features = self.feature_engineer.get_car_features(car_id)
        if not source_features:
            logger.error(f"Could not extract features for car {car_id}")
            return []
        
        source_price = source_features["raw"]["price"]
        source_make = source_features["raw"]["make"]
        source_body_type = source_features["raw"]["body_type"]
        
        # Calculate price band (±15%)
        price_min = source_price * (1 - settings.price_band_percentage)
        price_max = source_price * (1 + settings.price_band_percentage)
        
        # Query candidate cars
        query = self.db.query(Car).filter(
            Car.id != car_id,
            Car.status.notin_(exclude_statuses)
        )
        
        # Apply price filter if source has a price
        if source_price > 0:
            query = query.filter(
                Car.selling_price >= price_min,
                Car.selling_price <= price_max
            )
        
        candidates = query.limit(500).all()  # Limit candidates for performance
        
        if not candidates:
            logger.info(f"No candidate cars found for {car_id}")
            return []
        
        # Compute similarities
        similarities = []
        source_vector = self.feature_engineer.compute_feature_vector(source_features)
        
        for candidate in candidates:
            candidate_features = self.feature_engineer.get_car_features(candidate.id)
            if not candidate_features:
                continue
            
            candidate_vector = self.feature_engineer.compute_feature_vector(candidate_features)
            
            # Cosine similarity
            similarity = cosine_similarity(
                source_vector.reshape(1, -1),
                candidate_vector.reshape(1, -1)
            )[0][0]
            
            # Generate reasons
            reasons = self._generate_reasons(
                source_features,
                candidate_features,
                similarity
            )
            
            similarities.append({
                "vehicleId": candidate.id,
                "score": float(similarity),
                "reason": ", ".join(reasons),
                "details": {
                    "make": candidate_features["raw"]["make"],
                    "model": candidate_features["raw"]["model"],
                    "year": candidate_features["raw"]["year"],
                    "price": candidate_features["raw"]["price"],
                }
            })
        
        # Sort by similarity score (descending) and return top N
        similarities.sort(key=lambda x: x["score"], reverse=True)
        return similarities[:limit]
    
    def find_similar_motorcycles(
        self,
        motorcycle_id: int,
        limit: int = 10,
        exclude_statuses: Optional[List[str]] = None
    ) -> List[Dict]:
        """Find similar motorcycles based on content features"""
        if exclude_statuses is None:
            exclude_statuses = ["SOLD"]
        
        # Get source motorcycle features
        source_features = self.feature_engineer.get_motorcycle_features(motorcycle_id)
        if not source_features:
            logger.error(f"Could not extract features for motorcycle {motorcycle_id}")
            return []
        
        source_price = source_features["raw"]["price"]
        
        # Calculate price band
        price_min = source_price * (1 - settings.price_band_percentage)
        price_max = source_price * (1 + settings.price_band_percentage)
        
        # Query candidates
        query = self.db.query(Motorcycle).filter(
            Motorcycle.id != motorcycle_id,
            Motorcycle.status.notin_(exclude_statuses)
        )
        
        if source_price > 0:
            query = query.filter(
                Motorcycle.selling_price >= price_min,
                Motorcycle.selling_price <= price_max
            )
        
        candidates = query.limit(500).all()
        
        if not candidates:
            logger.info(f"No candidate motorcycles found for {motorcycle_id}")
            return []
        
        # Compute similarities
        similarities = []
        source_vector = self.feature_engineer.compute_feature_vector(source_features)
        
        for candidate in candidates:
            candidate_features = self.feature_engineer.get_motorcycle_features(candidate.id)
            if not candidate_features:
                continue
            
            candidate_vector = self.feature_engineer.compute_feature_vector(candidate_features)
            
            # Cosine similarity
            similarity = cosine_similarity(
                source_vector.reshape(1, -1),
                candidate_vector.reshape(1, -1)
            )[0][0]
            
            # Generate reasons
            reasons = self._generate_reasons(
                source_features,
                candidate_features,
                similarity
            )
            
            similarities.append({
                "vehicleId": candidate.id,
                "score": float(similarity),
                "reason": ", ".join(reasons),
                "details": {
                    "make": candidate_features["raw"]["make"],
                    "model": candidate_features["raw"]["model"],
                    "year": candidate_features["raw"]["year"],
                    "price": candidate_features["raw"]["price"],
                }
            })
        
        # Sort and return top N
        similarities.sort(key=lambda x: x["score"], reverse=True)
        return similarities[:limit]
    
    def _generate_reasons(
        self,
        source_features: Dict,
        candidate_features: Dict,
        similarity_score: float
    ) -> List[str]:
        """Generate human-readable reasons for similarity"""
        reasons = []
        source_raw = source_features["raw"]
        candidate_raw = candidate_features["raw"]
        
        # Same brand/make
        if source_raw["make"].lower() == candidate_raw["make"].lower():
            reasons.append("same brand")
        
        # Similar price
        price_diff_pct = abs(
            source_raw["price"] - candidate_raw["price"]
        ) / source_raw["price"] if source_raw["price"] > 0 else 0
        
        if price_diff_pct < 0.05:
            reasons.append("similar price")
        elif price_diff_pct < 0.10:
            reasons.append("nearby price")
        
        # Same body/vehicle type
        if "body_type" in source_raw and source_raw["body_type"] == candidate_raw.get("body_type"):
            reasons.append(f"same {source_raw['body_type'].lower()} type")
        elif "vehicle_type" in source_raw and source_raw["vehicle_type"] == candidate_raw.get("vehicle_type"):
            reasons.append(f"same {source_raw['vehicle_type'].lower()} type")
        
        # Similar year
        year_diff = abs(source_raw["year"] - candidate_raw["year"])
        if year_diff <= 1:
            reasons.append("same model year")
        elif year_diff <= 3:
            reasons.append("recent model")
        
        # Same fuel type
        if source_raw["fuel_type"] == candidate_raw.get("fuel_type"):
            reasons.append(f"{source_raw['fuel_type'].lower()} fuel")
        
        # Fallback reason if none matched
        if not reasons:
            if similarity_score > 0.8:
                reasons.append("matching features")
            else:
                reasons.append("similar segment")
        
        return reasons
