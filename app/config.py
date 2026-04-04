"""Application configuration management"""
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Environment
    env: str = "development"
    
    # Database Configuration
    db_host: str = "localhost"
    db_port: int = 3307
    db_user: str = "wheelshift_ai"
    db_password: str
    db_name: str = "wheelshift_db"
    
    # Redis Configuration
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 1
    redis_password: Optional[str] = None
    
    # Feature Flags
    enable_collaborative_filtering: bool = True
    min_interactions_threshold: int = 50
    min_clients_threshold: int = 10
    
    # Caching Configuration
    cache_ttl_ondemand: int = 1800  # 30 minutes
    cache_ttl_precomputed: int = 86400  # 24 hours
    feature_vector_cache_ttl: int = 3600  # 1 hour
    
    # Similarity Configuration
    default_similarity_limit: int = 10
    price_band_percentage: float = 0.15
    top_vehicles_precompute: int = 100
    
    # Feature Weights
    weight_price: float = 0.25
    weight_brand: float = 0.20
    weight_body_type: float = 0.15
    weight_year: float = 0.15
    weight_mileage: float = 0.10
    weight_fuel_type: float = 0.10
    weight_text_similarity: float = 0.05
    
    # Hybrid Model Weights
    content_based_weight: float = 0.6
    collaborative_weight: float = 0.4

    # Lead Scoring — signal weights (points, must sum to 100)
    ls_weight_purchase_history: int = 30
    ls_weight_inquiry_type: int = 20
    ls_weight_reservation: int = 15
    ls_weight_inquiry_frequency: int = 15
    ls_weight_response_engage: int = 10
    ls_weight_price_band: int = 10

    # Lead Scoring — label thresholds
    ls_hot_threshold: int = 70
    ls_warm_threshold: int = 40

    # Lead Scoring — frequency signal window
    ls_frequency_window_days: int = 90

    # Lead Scoring — cache TTL (short: inquiry state changes often)
    cache_ttl_lead_score: int = 900  # 15 minutes

    # Internal service-to-service authentication
    # Required in production. If unset in development, auth is skipped with a warning.
    api_key: str

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"
    
    # Celery Configuration
    celery_broker_url: str = "redis://localhost:6379/2"
    celery_result_backend: str = "redis://localhost:6379/2"
    celery_task_track_started: bool = True
    celery_task_time_limit: int = 1800
    
    @property
    def database_url(self) -> str:
        """Construct database URL for SQLAlchemy"""
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
            f"?charset=utf8mb4"
        )
    
    @property
    def redis_url(self) -> str:
        """Construct Redis URL"""
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
