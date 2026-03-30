"""Feature engineering service for vehicle similarity"""
import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import MinMaxScaler, StandardScaler
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.vehicle_models import Car, CarModel, Motorcycle, MotorcycleModel
from app.utils.cache import CacheService

logger = logging.getLogger(__name__)
settings = get_settings()


class FeatureEngineer:
    """Extract and normalize features for vehicle similarity"""
    
    # Categorical mappings
    FUEL_TYPE_MAP = {
        "PETROL": 0, "DIESEL": 1, "ELECTRIC": 2,
        "HYBRID": 3, "CNG": 4, "LPG": 5
    }
    
    TRANSMISSION_MAP = {
        "MANUAL": 0, "AUTOMATIC": 1, "AMT": 2,
        "CVT": 3, "DCT": 4
    }
    
    CAR_BODY_TYPE_MAP = {
        "SEDAN": 0, "SUV": 1, "HATCHBACK": 2,
        "COUPE": 3, "CONVERTIBLE": 4, "WAGON": 5,
        "VAN": 6, "TRUCK": 7
    }
    
    MOTORCYCLE_TYPE_MAP = {
        "MOTORCYCLE": 0, "SCOOTER": 1, "SPORT_BIKE": 2,
        "CRUISER": 3, "OFF_ROAD": 4, "TOURING": 5,
        "NAKED": 6, "CAFE_RACER": 7, "DIRT_BIKE": 8, "MOPED": 9
    }
    
    def __init__(self, db: Session):
        self.db = db
        self._tfidf_vectorizer: Optional[TfidfVectorizer] = None
        self._price_scaler: Optional[MinMaxScaler] = None
        self._year_scaler: Optional[StandardScaler] = None
        self._mileage_scaler: Optional[StandardScaler] = None
    
    def get_car_features(self, car_id: int) -> Optional[Dict]:
        """
        Extract and normalize features for a car
        
        Returns:
            Feature dictionary with normalized values or None if car not found
        """
        # Check cache first
        cached = CacheService.get_feature_vector("car", car_id)
        if cached:
            return cached
        
        # Fetch from database
        car = self.db.query(Car).join(CarModel).filter(Car.id == car_id).first()
        
        if not car or not car.car_model:
            logger.warning(f"Car {car_id} not found or missing model")
            return None
        
        features = self._extract_car_features(car)
        
        # Cache features
        CacheService.set_feature_vector("car", car_id, features)
        
        return features
    
    def get_motorcycle_features(self, motorcycle_id: int) -> Optional[Dict]:
        """Extract and normalize features for a motorcycle"""
        # Check cache first
        cached = CacheService.get_feature_vector("motorcycle", motorcycle_id)
        if cached:
            return cached
        
        # Fetch from database
        motorcycle = self.db.query(Motorcycle).join(MotorcycleModel).filter(
            Motorcycle.id == motorcycle_id
        ).first()
        
        if not motorcycle or not motorcycle.motorcycle_model:
            logger.warning(f"Motorcycle {motorcycle_id} not found or missing model")
            return None
        
        features = self._extract_motorcycle_features(motorcycle)
        
        # Cache features
        CacheService.set_feature_vector("motorcycle", motorcycle_id, features)
        
        return features
    
    def _extract_car_features(self, car: Car) -> Dict:
        """Extract raw and normalized features from a car"""
        model = car.car_model
        
        # Raw features
        price = float(car.selling_price) if car.selling_price else 0.0
        year = car.year or 2020
        mileage = car.mileage_km or 0
        engine_cc = car.engine_cc or 1500
        
        # Categorical encodings
        fuel_type_encoded = self.FUEL_TYPE_MAP.get(
            model.fuel_type.upper() if model.fuel_type else "PETROL", 0
        )
        transmission_encoded = self.TRANSMISSION_MAP.get(
            model.transmission_type.upper() if model.transmission_type else "MANUAL", 0
        )
        body_type_encoded = self.CAR_BODY_TYPE_MAP.get(
            model.body_type.upper() if model.body_type else "SEDAN", 0
        )
        
        # Text representation for TF-IDF
        make_model_text = f"{model.make} {model.model} {model.variant or ''}".strip().lower()
        
        # Normalize numerical features
        price_normalized = self._normalize_price(price)
        year_normalized = self._normalize_year(year)
        mileage_normalized = self._normalize_mileage(mileage)
        engine_normalized = self._normalize_engine_cc(engine_cc)
        
        return {
            "vehicle_id": car.id,
            "vehicle_type": "car",
            "raw": {
                "price": price,
                "year": year,
                "mileage_km": mileage,
                "engine_cc": engine_cc,
                "make": model.make,
                "model": model.model,
                "variant": model.variant,
                "fuel_type": model.fuel_type,
                "transmission_type": model.transmission_type,
                "body_type": model.body_type,
                "status": car.status,
            },
            "normalized": {
                "price": price_normalized,
                "year": year_normalized,
                "mileage": mileage_normalized,
                "engine_cc": engine_normalized,
                "fuel_type": fuel_type_encoded,
                "transmission": transmission_encoded,
                "body_type": body_type_encoded,
            },
            "text": make_model_text,
        }
    
    def _extract_motorcycle_features(self, motorcycle: Motorcycle) -> Dict:
        """Extract raw and normalized features from a motorcycle"""
        model = motorcycle.motorcycle_model
        
        # Raw features
        price = float(motorcycle.selling_price) if motorcycle.selling_price else 0.0
        year = motorcycle.manufacture_year or 2020
        mileage = motorcycle.mileage_km or 0
        engine_capacity = model.engine_capacity or 150
        
        # Categorical encodings
        fuel_type_encoded = self.FUEL_TYPE_MAP.get(
            model.fuel_type.upper() if model.fuel_type else "PETROL", 0
        )
        transmission_encoded = self.TRANSMISSION_MAP.get(
            model.transmission_type.upper() if model.transmission_type else "MANUAL", 0
        )
        vehicle_type_encoded = self.MOTORCYCLE_TYPE_MAP.get(
            model.vehicle_type.upper() if model.vehicle_type else "MOTORCYCLE", 0
        )
        
        # Text representation
        make_model_text = f"{model.make} {model.model} {model.variant or ''}".strip().lower()
        
        # Normalize
        price_normalized = self._normalize_price(price)
        year_normalized = self._normalize_year(year)
        mileage_normalized = self._normalize_mileage(mileage)
        engine_normalized = self._normalize_engine_cc(engine_capacity)
        
        return {
            "vehicle_id": motorcycle.id,
            "vehicle_type": "motorcycle",
            "raw": {
                "price": price,
                "year": year,
                "mileage_km": mileage,
                "engine_capacity": engine_capacity,
                "make": model.make,
                "model": model.model,
                "variant": model.variant,
                "fuel_type": model.fuel_type,
                "transmission_type": model.transmission_type,
                "vehicle_type": model.vehicle_type,
                "status": motorcycle.status,
            },
            "normalized": {
                "price": price_normalized,
                "year": year_normalized,
                "mileage": mileage_normalized,
                "engine_cc": engine_normalized,
                "fuel_type": fuel_type_encoded,
                "transmission": transmission_encoded,
                "vehicle_type": vehicle_type_encoded,
            },
            "text": make_model_text,
        }
    
    @staticmethod
    def _normalize_price(price: float) -> float:
        """Normalize price to 0-1 range (assuming max 50,000,000)"""
        return min(price / 50_000_000, 1.0)
    
    @staticmethod
    def _normalize_year(year: int) -> float:
        """Normalize year (1980-2026 range)"""
        return (year - 1980) / (2026 - 1980)
    
    @staticmethod
    def _normalize_mileage(mileage: int) -> float:
        """Normalize mileage (0-500,000 km range)"""
        return min(mileage / 500_000, 1.0)
    
    @staticmethod
    def _normalize_engine_cc(engine_cc: int) -> float:
        """Normalize engine capacity (0-6000 cc range)"""
        return min(engine_cc / 6000, 1.0)
    
    def compute_feature_vector(self, features: Dict) -> np.ndarray:
        """
        Compute weighted feature vector for similarity calculation
        
        Feature weights (from settings):
        - Price: 0.25
        - Make/Brand: 0.20 (one-hot encoded)
        - Body/Vehicle Type: 0.15
        - Year: 0.15
        - Mileage: 0.10
        - Fuel Type: 0.10
        - Text similarity: 0.05
        
        Returns:
            Weighted feature vector as numpy array
        """
        normalized = features["normalized"]
        
        # Build vector with weights applied
        vector = [
            normalized["price"] * settings.weight_price,
            normalized["year"] * settings.weight_year,
            normalized["mileage"] * settings.weight_mileage,
            normalized["fuel_type"] / 5.0 * settings.weight_fuel_type,  # Normalize to 0-1
            normalized["transmission"] / 4.0 * settings.weight_brand,  # Using as brand proxy
        ]
        
        # Add body/vehicle type
        if "body_type" in normalized:
            vector.append(normalized["body_type"] / 8.0 * settings.weight_body_type)
        elif "vehicle_type" in normalized:
            vector.append(normalized["vehicle_type"] / 10.0 * settings.weight_body_type)
        
        return np.array(vector)
