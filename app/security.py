"""API key authentication for internal service-to-service calls"""
import logging
import secrets

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Header name expected on every protected request
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str = Security(API_KEY_HEADER)) -> str:
    """
    FastAPI dependency that validates the X-API-Key header.
    Enforced in all environments — no bypasses.

    Raises:
        401 — header is missing or empty
        403 — header present but key does not match
    """
    if not api_key:
        logger.warning("Rejected request: missing X-API-Key header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Include X-API-Key header.",
        )

    if not secrets.compare_digest(api_key, settings.api_key):
        logger.warning("Rejected request: invalid API key")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key.",
        )

    return api_key
