"""Main FastAPI application"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.utils.cache import CacheService
from app.utils.db import check_db_connection
from app.utils.logger import setup_logging

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting WheelShift AI Service...")
    logger.info(f"Environment: {settings.env}")
    logger.info(f"Database: {settings.db_host}:{settings.db_port}/{settings.db_name}")
    logger.info(f"Redis: {settings.redis_host}:{settings.redis_port}/{settings.redis_db}")
    
    # Check connections
    db_healthy = check_db_connection()
    redis_healthy = CacheService.check_connection()
    
    if not db_healthy:
        logger.warning("Database connection check failed at startup")
    else:
        logger.info("✓ Database connection healthy")
    
    if not redis_healthy:
        logger.warning("Redis connection check failed at startup")
    else:
        logger.info("✓ Redis connection healthy")
    
    yield
    
    # Shutdown
    logger.info("Shutting down WheelShift AI Service...")


# Create FastAPI app
app = FastAPI(
    title="WheelShift AI Service",
    description="AI-powered vehicle similarity and recommendation engine",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.env == "development" else None,
    redoc_url="/redoc" if settings.env == "development" else None,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.env == "development" else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint"""
    return {
        "service": "WheelShift AI Service",
        "version": "0.1.0",
        "status": "operational",
        "environment": settings.env,
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint
    
    Returns:
        Health status of the service including database and Redis connectivity
    """
    db_healthy = check_db_connection()
    redis_healthy = CacheService.check_connection()
    
    overall_healthy = db_healthy and redis_healthy
    
    health_data = {
        "status": "healthy" if overall_healthy else "degraded",
        "service": "wheelshift-ai",
        "version": "0.1.0",
        "environment": settings.env,
        "checks": {
            "database": {
                "status": "up" if db_healthy else "down",
                "host": settings.db_host,
                "port": settings.db_port,
            },
            "redis": {
                "status": "up" if redis_healthy else "down",
                "host": settings.redis_host,
                "port": settings.redis_port,
            },
            "collaborative_filtering": {
                "status": "enabled" if settings.enable_collaborative_filtering else "disabled"
            }
        }
    }
    
    status_code = 200 if overall_healthy else 503
    
    if not overall_healthy:
        logger.warning(f"Health check failed: DB={db_healthy}, Redis={redis_healthy}")
    
    return JSONResponse(content=health_data, status_code=status_code)


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if settings.env == "development" else "An error occurred"
        }
    )


# Import and include routers
from app.api.v1 import similarity, lead_scoring
from app.security import verify_api_key
from fastapi import Depends

app.include_router(
    similarity.router,
    prefix="/api/ai",
    tags=["Similarity"],
    dependencies=[Depends(verify_api_key)],
)

app.include_router(
    lead_scoring.router,
    prefix="/api/ai",
    tags=["Lead Scoring"],
    dependencies=[Depends(verify_api_key)],
)
