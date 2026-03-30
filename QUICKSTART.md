# WheelShift AI Service - Quick Start Guide

## Prerequisites

✅ **Required:**
- Python 3.11+
- **wheelshift-backend services running** (provides MySQL and Redis)
  - Navigate to wheelshift-backend and run: `docker-compose -f docker-compose-dev.yml up -d`
  - This starts MySQL (port 3307) and Redis (port 6379)

## Setup Instructions

### 1. Start Backend Services First

The AI service depends on MySQL and Redis from the backend. Make sure they're running:

```bash
cd "d:\My Projects\wheelshift-backend"
docker-compose -f docker-compose-dev.yml up -d mysql redis

# Verify services are running
docker ps | grep wheelshift
# Should see: wheelshift-mysql and wheelshift-redis
```

### 2. Create AI Service Database User

Connect to the backend's MySQL and create a read-only user for the AI service:

```bash
# Connect to MySQL (password is 'root' from docker-compose-dev.yml)
mysql -h localhost -P 3307 -u root -p

# Run these SQL commands:
CREATE USER 'wheelshift_ai'@'%' IDENTIFIED BY 'your_secure_password';
GRANT SELECT ON wheelshift_db.* TO 'wheelshift_ai'@'%';
FLUSH PRIVILEGES;
EXIT;
```

### 3. Setup Python Environment

```bash
cd "d:\My Projects\wheelshift-ai"

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
# Copy example env file
copy .env.example .env

# Edit .env and set your database password
notepad .env
```

**Key settings in `.env`:**
```env
# For local development (Python outside Docker)
DB_HOST=localhost
DB_PORT=3307  # Backend's MySQL exposed port
DB_PASSWORD=your_secure_password  # Set this to match step 2

REDIS_HOST=localhost
REDIS_PORT=6379  # Backend's Redis exposed port
REDIS_DB=1  # Use DB 1 to avoid conflicts with backend (uses DB 0)
```

### 5. Run the AI Service

**Option A: Direct Python (Recommended for Development)**
```bash
python run.py
```

**Option B: Uvicorn**
```bash
uvicorn app.main:app --reload --port 8000
```

**Option C: Docker (Joins Backend Network)**
```bash
# Build and run (automatically connects to backend's network)
docker-compose up --build
```

### 6. Verify Service is Running

```bash
# Health check
curl http://localhost:8000/health

# Should return JSON with:
# - status: "healthy"
# - database: "up"
# - redis: "up"
```

```bash
# Interactive API docs
# Open in browser: http://localhost:8000/docs
```

```bash
# Test similarity endpoint (replace 1 with actual car ID from your database)
curl "http://localhost:8000/api/ai/vehicles/similar/content?vehicleId=1&type=car&limit=5"
```

## Architecture Overview

```
┌─────────────────────────────────────────────┐
│      WheelShift Backend Services            │
│      (docker-compose-dev.yml)               │
│                                             │
│  ┌──────────┐  ┌───────────┐              │
│  │  MySQL   │  │   Redis   │              │
│  │ :3307    │  │  :6379    │              │
│  └────┬─────┘  └─────┬─────┘              │
│       │              │                     │
└───────┼──────────────┼─────────────────────┘
        │              │
        │ (shared)     │ (shared)
        │              │
┌───────▼──────────────▼─────────────────────┐
│      WheelShift AI Service                  │
│      (Python FastAPI - Port 8000)          │
│                                             │
│  • Content-based similarity                 │
│  • Feature engineering                      │
│  • Redis caching                            │
│  • Read-only DB access                      │
└─────────────────────────────────────────────┘
```

## Available API Endpoints

### Health & Documentation
- `GET /` - Service info
- `GET /health` - Health check (DB + Redis status)
- `GET /docs` - Interactive API documentation (Swagger UI)
- `GET /redoc` - ReDoc API documentation

### Similarity Endpoints
- `GET /api/ai/vehicles/similar/content`
  - **Content-based similarity** (vehicle attributes only)
  - Params: `vehicleId`, `type` (car|motorcycle), `limit`
  
- `GET /api/ai/vehicles/similar`
  - **Hybrid similarity** (currently forwards to content-based; will add collaborative in Phase 3)
  - Params: `vehicleId`, `type` (car|motorcycle), `limit`

## Troubleshooting

### ❌ "Can't connect to database"

**Check backend services are running:**
```bash
cd "d:\My Projects\wheelshift-backend"
docker-compose -f docker-compose-dev.yml ps

# Should show mysql as 'Up' and healthy
```

**Test MySQL connection:**
```bash
mysql -h localhost -P 3307 -u wheelshift_ai -p
# Enter the password you set in .env
```

**Check AI user permissions:**
```sql
SHOW GRANTS FOR 'wheelshift_ai'@'%';
# Should show SELECT on wheelshift_db.*
```

### ❌ "Can't connect to Redis"

**Check backend Redis is running:**
```bash
docker ps | grep wheelshift-redis
# Should show wheelshift-redis container running
```

**Test Redis connection:**
```bash
redis-cli -h localhost -p 6379 ping
# Should return: PONG
```

**Check Redis database availability:**
```bash
redis-cli -h localhost -p 6379
> SELECT 1  # AI service uses DB 1
> PING
> INFO keyspace  # See what keys exist
```

### ❌ "Module not found"

**Ensure virtual environment is activated:**
```bash
# You should see (venv) in your prompt
venv\Scripts\activate

# Reinstall dependencies
pip install -r requirements.txt
```

### ❌ Health check returns "degraded"

**Check the response for which service failed:**
```bash
curl http://localhost:8000/health | python -m json.tool
```

Look at the `checks` section:
- If `database.status: "down"` → See database troubleshooting above
- If `redis.status: "down"` → See Redis troubleshooting above

### ⚠️ Similarity returns empty results

**Check if you have vehicles in the database:**
```bash
mysql -h localhost -P 3307 -u wheelshift_ai -p wheelshift_db -e "SELECT COUNT(*) FROM cars;"
```

**Check status filter** (by default, SOLD vehicles are excluded):
```bash
mysql -h localhost -P 3307 -u wheelshift_ai -p wheelshift_db -e "SELECT status, COUNT(*) FROM cars GROUP BY status;"
```

**Enable debug logging** in `.env`:
```env
LOG_LEVEL=DEBUG
```
Restart the service and check logs for detailed similarity computation info.

## Development Workflow

### Hot Reload (Recommended)

When running with `python run.py` or `uvicorn --reload`, the service automatically reloads when you edit Python files.

### Running Tests

```bash
# Install test dependencies (if not already)
pip install pytest pytest-asyncio httpx

# Run all tests
pytest tests/ -v

# Run with coverage report
pytest tests/ --cov=app --cov-report=html

# Run specific test file
pytest tests/test_content_similarity.py -v
```

### Viewing Logs

**Local Python:**
- Logs print to console in JSON format (or plain text if `LOG_FORMAT=text` in .env)

**Docker:**
```bash
docker logs wheelshift-ai -f  # Follow logs
docker logs wheelshift-ai --tail 100  # Last 100 lines
```

### Monitoring Redis Cache

**Using Redis CLI:**
```bash
redis-cli -h localhost -p 6379
> SELECT 1  # AI service uses DB 1
> KEYS similarity:*  # See cached similarity results
> TTL similarity:car:1:v1  # Check TTL for specific key
> GET similarity:car:1:v1  # View cached content
```

**Using Redis Commander (from backend stack):**
- Open http://localhost:8082
- Select Database 1
- Browse keys with prefix `similarity:`, `features:`, etc.

### Invalidating Cache

**Manually clear similarity cache for a vehicle:**
```python
from app.utils.cache import CacheService
CacheService.invalidate_similarity("car", 1)
```

**Or via Redis CLI:**
```bash
redis-cli -h localhost -p 6379
> SELECT 1
> DEL similarity:car:1:v1
> DEL similarity:precomputed:car:1:v1
> DEL features:car:1:v1
```

## Next Steps

Now that the AI service is running, you can:

1. **Test with real data**: Query similarity for actual vehicles in your database
2. **Adjust feature weights**: Edit `.env` to tune similarity algorithm (e.g., `WEIGHT_PRICE=0.30`)
3. **Monitor performance**: Check `/health` and cache hit rates
4. **Continue implementation**: Move to Phase 3 (Collaborative Filtering) or Phase 5 (Spring Boot Integration)

## Docker Network Details

When running in Docker, the AI service joins the backend's `wheelshift-network`:

```yaml
# In docker-compose.yml
networks:
  wheelshift-network:
    external: true  # Joins existing network from backend
```

**Service hostnames in Docker:**
- MySQL: `mysql:3306` (internal) or `localhost:3307` (from host)
- Redis: `redis:6379` (internal) or `localhost:6379` (from host)
- AI Service: `ai-service:8000` (internal) or `localhost:8000` (from host)

## Support & Documentation

- **Implementation Plan**: `plan.md`
- **Current Status**: `STATUS.md`
- **API Specification**: `../wheelshift-backend/docs/AI_SERVICE_OVERVIEW.md`
- **Database Schema**: `../wheelshift-backend/docs/DATABASE_DESIGN.md`

---

**Version:** 0.1.0  
**Status:** Phases 1-2 Complete (Foundation + Content-Based Similarity)  
**Last Updated:** March 25, 2026
