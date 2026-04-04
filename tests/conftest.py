"""Test configuration"""
import os

import pytest

# Set required env vars before any app module is imported at collection time.
# This prevents pydantic-settings from failing on missing required fields.
os.environ.setdefault("DB_PASSWORD", "test_password")
os.environ.setdefault("API_KEY", "test_api_key")


@pytest.fixture
def mock_settings():
    """Mock settings for testing"""
    from app.config import Settings
    return Settings(
        db_password="test_password",
        api_key="test_api_key",
        env="testing",
        log_level="ERROR"
    )
