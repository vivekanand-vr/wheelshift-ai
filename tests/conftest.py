"""Test configuration"""
import pytest


@pytest.fixture
def mock_settings():
    """Mock settings for testing"""
    from app.config import Settings
    return Settings(
        db_password="test_password",
        env="testing",
        log_level="ERROR"
    )
