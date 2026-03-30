"""Basic tests for content-based similarity"""
import pytest
from unittest.mock import Mock, patch

from app.services.feature_engineering import FeatureEngineer


def test_feature_engineer_normalize_price():
    """Test price normalization"""
    assert FeatureEngineer._normalize_price(0) == 0.0
    assert FeatureEngineer._normalize_price(25_000_000) == 0.5
    assert FeatureEngineer._normalize_price(50_000_000) == 1.0
    assert FeatureEngineer._normalize_price(100_000_000) == 1.0  # Capped at 1.0


def test_feature_engineer_normalize_year():
    """Test year normalization"""
    assert FeatureEngineer._normalize_year(1980) == 0.0
    assert FeatureEngineer._normalize_year(2003) == 0.5
    assert FeatureEngineer._normalize_year(2026) == 1.0


def test_feature_engineer_normalize_mileage():
    """Test mileage normalization"""
    assert FeatureEngineer._normalize_mileage(0) == 0.0
    assert FeatureEngineer._normalize_mileage(250_000) == 0.5
    assert FeatureEngineer._normalize_mileage(500_000) == 1.0
    assert FeatureEngineer._normalize_mileage(1_000_000) == 1.0  # Capped


def test_feature_engineer_normalize_engine_cc():
    """Test engine capacity normalization"""
    assert FeatureEngineer._normalize_engine_cc(0) == 0.0
    assert FeatureEngineer._normalize_engine_cc(3000) == 0.5
    assert FeatureEngineer._normalize_engine_cc(6000) == 1.0


def test_fuel_type_encoding():
    """Test fuel type categorical encoding"""
    assert FeatureEngineer.FUEL_TYPE_MAP["PETROL"] == 0
    assert FeatureEngineer.FUEL_TYPE_MAP["DIESEL"] == 1
    assert FeatureEngineer.FUEL_TYPE_MAP["ELECTRIC"] == 2
    assert FeatureEngineer.FUEL_TYPE_MAP["HYBRID"] == 3


def test_transmission_encoding():
    """Test transmission type categorical encoding"""
    assert FeatureEngineer.TRANSMISSION_MAP["MANUAL"] == 0
    assert FeatureEngineer.TRANSMISSION_MAP["AUTOMATIC"] == 1
    assert FeatureEngineer.TRANSMISSION_MAP["CVT"] == 3


# Integration test would require database setup
# @pytest.mark.integration
# def test_content_similarity_service(db_session):
#     """Test content similarity service with real database"""
#     service = ContentSimilarityService(db_session)
#     results = service.find_similar_cars(1, limit=5)
#     assert len(results) <= 5
#     assert all("vehicleId" in r for r in results)
#     assert all("score" in r for r in results)
