"""Redis cache utilities"""
import json
import logging
from typing import Any, Optional

import redis
from redis.connection import ConnectionPool

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Create connection pool
pool = ConnectionPool.from_url(
    settings.redis_url,
    max_connections=20,
    socket_timeout=5,
    socket_connect_timeout=5,
    retry_on_timeout=True,
    health_check_interval=30,
)

# Redis client
redis_client = redis.Redis(connection_pool=pool, decode_responses=True)


class CacheService:
    """Redis cache service for similarity results"""
    
    CACHE_VERSION = "v1"
    
    @staticmethod
    def _make_key(vehicle_type: str, vehicle_id: int, cache_type: str = "similarity") -> str:
        """Generate cache key"""
        return f"{cache_type}:{vehicle_type}:{vehicle_id}:{CacheService.CACHE_VERSION}"
    
    @staticmethod
    def get_similarity(vehicle_type: str, vehicle_id: int) -> Optional[dict]:
        """
        Get cached similarity results for a vehicle
        
        Args:
            vehicle_type: "car" or "motorcycle"
            vehicle_id: Vehicle ID
            
        Returns:
            Cached similarity dict or None if not found
        """
        try:
            key = CacheService._make_key(vehicle_type, vehicle_id)
            cached = redis_client.get(key)
            if cached:
                logger.debug(f"Cache HIT: {key}")
                return json.loads(cached)
            logger.debug(f"Cache MISS: {key}")
            return None
        except Exception as e:
            logger.error(f"Error getting cache for {vehicle_type}:{vehicle_id}: {e}")
            return None
    
    @staticmethod
    def set_similarity(
        vehicle_type: str,
        vehicle_id: int,
        data: dict,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Cache similarity results for a vehicle
        
        Args:
            vehicle_type: "car" or "motorcycle"
            vehicle_id: Vehicle ID
            data: Similarity results to cache
            ttl: Time to live in seconds (default: from settings)
            
        Returns:
            True if cached successfully, False otherwise
        """
        try:
            key = CacheService._make_key(vehicle_type, vehicle_id)
            ttl = ttl or settings.cache_ttl_ondemand
            redis_client.setex(key, ttl, json.dumps(data))
            logger.debug(f"Cached {key} with TTL {ttl}s")
            return True
        except Exception as e:
            logger.error(f"Error setting cache for {vehicle_type}:{vehicle_id}: {e}")
            return False
    
    @staticmethod
    def get_precomputed_similarity(vehicle_type: str, vehicle_id: int) -> Optional[dict]:
        """Get pre-computed similarity results"""
        try:
            key = f"similarity:precomputed:{vehicle_type}:{vehicle_id}:{CacheService.CACHE_VERSION}"
            cached = redis_client.get(key)
            if cached:
                logger.debug(f"Precomputed cache HIT: {key}")
                return json.loads(cached)
            return None
        except Exception as e:
            logger.error(f"Error getting precomputed cache: {e}")
            return None
    
    @staticmethod
    def set_precomputed_similarity(vehicle_type: str, vehicle_id: int, data: dict) -> bool:
        """Cache pre-computed similarity results (24h TTL)"""
        try:
            key = f"similarity:precomputed:{vehicle_type}:{vehicle_id}:{CacheService.CACHE_VERSION}"
            redis_client.setex(key, settings.cache_ttl_precomputed, json.dumps(data))
            logger.debug(f"Cached precomputed {key}")
            return True
        except Exception as e:
            logger.error(f"Error setting precomputed cache: {e}")
            return False

    @staticmethod
    def get_collaborative_similarity(vehicle_type: str, vehicle_id: int) -> Optional[dict]:
        """Get cached collaborative filtering results (24h TTL key)"""
        try:
            key = f"similarity:collaborative:{vehicle_type}:{vehicle_id}:{CacheService.CACHE_VERSION}"
            cached = redis_client.get(key)
            if cached:
                logger.debug(f"Collaborative cache HIT: {key}")
                return json.loads(cached)
            return None
        except Exception as e:
            logger.error(f"Error getting collaborative cache for {vehicle_type}:{vehicle_id}: {e}")
            return None

    @staticmethod
    def set_collaborative_similarity(vehicle_type: str, vehicle_id: int, data: dict) -> bool:
        """Cache collaborative filtering results (24h TTL — changes slowly)"""
        try:
            key = f"similarity:collaborative:{vehicle_type}:{vehicle_id}:{CacheService.CACHE_VERSION}"
            redis_client.setex(key, settings.cache_ttl_precomputed, json.dumps(data))
            logger.debug(f"Cached collaborative {key}")
            return True
        except Exception as e:
            logger.error(f"Error setting collaborative cache for {vehicle_type}:{vehicle_id}: {e}")
            return False
    
    @staticmethod
    def invalidate_similarity(vehicle_type: str, vehicle_id: int) -> bool:
        """Invalidate cached similarity for a vehicle"""
        try:
            pattern = f"similarity:*:{vehicle_type}:{vehicle_id}:{CacheService.CACHE_VERSION}"
            keys = list(redis_client.scan_iter(match=pattern))
            if keys:
                redis_client.delete(*keys)
                logger.info(f"Invalidated {len(keys)} cache keys for {vehicle_type}:{vehicle_id}")
            return True
        except Exception as e:
            logger.error(f"Error invalidating cache: {e}")
            return False
    
    @staticmethod
    def get_feature_vector(vehicle_type: str, vehicle_id: int) -> Optional[dict]:
        """Get cached feature vector for a vehicle"""
        try:
            key = f"features:{vehicle_type}:{vehicle_id}:{CacheService.CACHE_VERSION}"
            cached = redis_client.get(key)
            if cached:
                return json.loads(cached)
            return None
        except Exception as e:
            logger.error(f"Error getting feature vector cache: {e}")
            return None
    
    @staticmethod
    def set_feature_vector(vehicle_type: str, vehicle_id: int, data: dict) -> bool:
        """Cache feature vector for a vehicle (1h TTL)"""
        try:
            key = f"features:{vehicle_type}:{vehicle_id}:{CacheService.CACHE_VERSION}"
            redis_client.setex(key, settings.feature_vector_cache_ttl, json.dumps(data))
            return True
        except Exception as e:
            logger.error(f"Error setting feature vector cache: {e}")
            return False
    
    @staticmethod
    def check_connection() -> bool:
        """Check if Redis connection is healthy"""
        try:
            return redis_client.ping()
        except Exception:
            return False

    # ── Lead Scoring ────────────────────────────────────────────────────────

    LEAD_SCORE_VERSION = "v1"

    @staticmethod
    def _lead_score_key(inquiry_id: int) -> str:
        return f"lead_score:inquiry:{inquiry_id}:{CacheService.LEAD_SCORE_VERSION}"

    @staticmethod
    def get_lead_score(inquiry_id: int) -> Optional[dict]:
        """Get cached lead score for an inquiry"""
        try:
            key = CacheService._lead_score_key(inquiry_id)
            cached = redis_client.get(key)
            if cached:
                logger.debug(f"Lead score cache HIT: {key}")
                return json.loads(cached)
            logger.debug(f"Lead score cache MISS: {key}")
            return None
        except Exception as e:
            logger.error(f"Error getting lead score cache for inquiry {inquiry_id}: {e}")
            return None

    @staticmethod
    def set_lead_score(inquiry_id: int, data: dict, ttl: Optional[int] = None) -> bool:
        """Cache lead score for an inquiry"""
        try:
            key = CacheService._lead_score_key(inquiry_id)
            ttl = ttl or settings.cache_ttl_lead_score
            redis_client.setex(key, ttl, json.dumps(data))
            logger.debug(f"Cached lead score {key} with TTL {ttl}s")
            return True
        except Exception as e:
            logger.error(f"Error setting lead score cache for inquiry {inquiry_id}: {e}")
            return False

    @staticmethod
    def invalidate_lead_score(inquiry_id: int) -> bool:
        """Remove cached lead score for an inquiry (call when inquiry state changes)"""
        try:
            key = CacheService._lead_score_key(inquiry_id)
            redis_client.delete(key)
            logger.debug(f"Invalidated lead score cache: {key}")
            return True
        except Exception as e:
            logger.error(f"Error invalidating lead score cache for inquiry {inquiry_id}: {e}")
            return False

