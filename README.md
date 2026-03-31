# WheelShift AI Service

AI-powered vehicle similarity and recommendation engine for WheelShift Pro using hybrid ML approach (content-based + collaborative filtering).

## 🎯 Current Status: 42% Complete

**Phases 1 & 2 are complete and fully operational!** The service currently provides:
- ✅ Content-based similarity engine (live and tested)
- ✅ Health monitoring with DB + Redis checks
- ✅ Feature engineering pipeline with weighted scoring
- ✅ Redis caching (30min TTL for on-demand, 1h for feature vectors)
- ✅ FastAPI service with OpenAPI docs
- ⏳ Collaborative filtering (pending)
- ⏳ Hybrid ranking (pending)
- ⏳ Spring Boot integration (pending)

## Features

### ✅ Implemented
- **Content-Based Similarity**: Vehicle recommendations based on attributes (price, brand, year, body type, fuel type, mileage)
- **Feature Engineering**: Normalized numerical features + categorical encoding with configurable weights
- **Smart Caching**: Redis-based caching with separate TTLs for different data types
- **Health Monitoring**: Comprehensive health checks for database and cache connectivity
- **RESTful API**: FastAPI with automatic OpenAPI documentation

### 🚧 Coming Soon
- **Collaborative Filtering**: Client behavior-based recommendations ("clients who viewed X also viewed Y")
- **Hybrid Ranking**: Combined approach (60% content + 40% collaborative)
- **Pre-computation**: Daily background jobs for top 100 vehicles
- **Spring Boot Integration**: REST client for seamless backend integration

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- **WheelShift Backend running** (provides MySQL on port 3307 and Redis on port 6379)
- Docker & Docker Compose (optional)

### Setup in 5 Minutes

```bash
# 1. Ensure backend services are running
cd ../wheelshift-backend
docker-compose -f docker-compose-dev.yml up -d mysql redis

# 2. Setup AI service
cd ../wheelshift-ai
python -m venv venv
venv\Scripts\activate  # Windows | source venv/bin/activate (Linux/Mac)
pip install -r requirements.txt

# 3. Configure environment
copy .env.example .env
# Edit .env with your database credentials

# 4. Create database user (connect to MySQL on port 3307)
mysql -h localhost -P 3307 -u root -p
```

```sql
CREATE USER 'wheelshift_ai'@'%' IDENTIFIED BY 'your_secure_password';
GRANT SELECT ON wheelshift_db.* TO 'wheelshift_ai'@'%';
FLUSH PRIVILEGES;
```

```bash
# 5. Run the service
python run.py
# Or: uvicorn app.main:app --reload --port 8000

# 6. Test it
curl http://localhost:8000/health
```

### Docker Deployment

```bash
# Start backend services first
cd ../wheelshift-backend
docker-compose -f docker-compose-dev.yml up -d mysql redis

# Build and run AI service (automatically joins backend's network)
cd ../wheelshift-ai
docker-compose up --build
```

## 📡 API Endpoints

### Health & Documentation
- `GET /` - Service information
- `GET /health` - Health check (database + Redis status)
- `GET /docs` - Interactive API documentation (Swagger UI)
- `GET /redoc` - Alternative API documentation

### Similarity Endpoints ✅ Live
```bash
# Content-based similarity (fully operational)
GET /api/ai/vehicles/similar/content?vehicleId=42&type=car&limit=10

# Hybrid similarity (currently forwards to content-based)
GET /api/ai/vehicles/similar?vehicleId=42&type=car&limit=10
```

**Query Parameters:**
- `vehicleId` (required): ID of the source vehicle
- `type` (required): `car` or `motorcycle`
- `limit` (optional): Number of suggestions to return (default: 10)

**Response Example:**
```json
{
  "sourceVehicleId": 42,
  "vehicleType": "car",
  "suggestions": [
    {
      "vehicleId": 18,
      "score": 0.94,
      "reason": "same brand, similar price, same sedan type",
      "details": {
        "make": "Toyota",
        "model": "Camry",
        "year": 2022,
        "price": 485000.0
      }
    }
  ],
  "method": "content",
  "cached": false
}
```

### 🔜 Coming Soon
```bash
# Collaborative filtering (Phase 3)
GET /api/ai/vehicles/similar/collaborative?vehicleId=42&type=car&limit=10
```

## 🏗️ Project Structure

```
wheelshift-ai/
├── app/
│   ├── main.py                          # FastAPI app with lifespan, CORS, error handling
│   ├── config.py                        # Pydantic settings with caching
│   ├── api/
│   │   └── v1/
│   │       └── similarity.py            # ✅ Similarity endpoints (content-based live)
│   ├── models/
│   │   └── vehicle_models.py            # SQLAlchemy models (Car, Motorcycle, Inquiry)
│   ├── schemas/
│   │   └── responses.py                 # Pydantic response schemas
│   ├── services/
│   │   ├── feature_engineering.py       # ✅ Feature extraction (350 lines)
│   │   ├── content_similarity.py        # ✅ Content-based engine (250 lines)
│   │   ├── collaborative_similarity.py  # 🚧 Pending (Phase 3)
│   │   └── hybrid_ranker.py             # 🚧 Pending (Phase 4)
│   └── utils/
│       ├── db.py                        # Database session management
│       ├── cache.py                     # Redis caching service
│       └── logger.py                    # JSON logging setup
├── tests/
│   ├── conftest.py                      # Test configuration
│   └── test_content_similarity.py       # Unit tests for feature engineering
├── requirements.txt                     # 25 dependencies
├── .env.example                         # Environment template
├── Dockerfile                           # Multi-stage build
├── docker-compose.yml                   # Service orchestration
└── run.py                               # Development runner
```

## 🎨 Architecture

```
┌─────────────────┐
│  Spring Boot    │ ──HTTP──┐
│  Backend        │         │
│  (Phase 5)      │         │
└─────────────────┘         │
                            ▼
                    ┌────────────────┐
                    │   FastAPI      │
                    │  AI Service    │
                    │  Port 8000     │
                    └────────┬───────┘
                             │
                ┌────────────┼────────────┐
                ▼            ▼            ▼
           ┌────────┐   ┌────────┐   ┌────────┐
           │ MySQL  │   │ Redis  │   │ Celery │
           │ (3307) │   │ (6379) │   │ (Phase │
           │ Read   │   │ Cache  │   │   6)   │
           │ Only   │   │        │   │        │
           └────────┘   └────────┘   └────────┘
```

### Data Flow (Current - Phase 2)
1. Client requests similar vehicles via API
2. Service checks Redis cache for existing result
3. On cache miss: extracts features → computes similarity → ranks results
4. Caches result (30min TTL) and returns to client
5. Feature vectors cached separately (1h TTL) for reuse

### Data Flow (Future - Phase 6)
1. Daily Celery job pre-computes top 100 vehicles (most viewed + recent + available)
2. Results stored in Redis with 24h TTL
3. API checks precomputed cache first, falls back to on-demand computation

## ⚙️ Configuration

Key environment variables (see `.env.example`):

```env
# Database (connects to backend's MySQL)
DB_HOST=localhost
DB_PORT=3307
DB_USER=wheelshift_ai
DB_PASSWORD=your_secure_password
DB_NAME=wheelshift_db

# Redis Cache (connects to backend's Redis, uses DB 1)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=1

# Feature Weights (content-based similarity)
WEIGHT_PRICE=0.25
WEIGHT_BRAND=0.20
WEIGHT_BODY_TYPE=0.15
WEIGHT_YEAR=0.15
WEIGHT_MILEAGE=0.10
WEIGHT_FUEL_TYPE=0.10
WEIGHT_TEXT=0.05

# Caching Strategy
CACHE_TTL_ONDEMAND=1800       # 30 minutes
CACHE_TTL_PRECOMPUTED=86400   # 24 hours
CACHE_TTL_FEATURES=3600       # 1 hour

# Hybrid Ranking (Phase 4)
CONTENT_BASED_WEIGHT=0.6
COLLABORATIVE_WEIGHT=0.4
ENABLE_COLLABORATIVE_FILTERING=false
```

## 🗺️ Development Roadmap

### ✅ Phase 1: Foundation (Complete)
- FastAPI project scaffold with Docker
- SQLAlchemy models (read-only access)
- Redis caching layer with connection pooling
- Health check endpoint

### ✅ Phase 2: Content-Based Engine (Complete)
- Feature engineering pipeline (numerical + categorical + text)
- Cosine similarity computation
- Price band filtering (±15%)
- Top-K ranking with human-readable reasons
- API endpoints with caching

### 🔜 Phase 3: Collaborative Filtering (Next - 2 days)
- Build user-item interaction matrix from `inquiries` table
- Item-item collaborative filtering ("clients who viewed X also viewed Y")
- Co-occurrence matrix computation
- `/api/ai/vehicles/similar/collaborative` endpoint
- Cold start handling (minimum 50 interactions threshold)

### 🔜 Phase 4: Hybrid Ranking (1 day)
- Merge content (60%) + collaborative (40%) scores
- Deduplication and unified ranking
- Update main `/api/ai/vehicles/similar` endpoint

### 🔜 Phase 5: Spring Boot Integration (2 days)
- Create `AIServiceClient.java` with WebClient
- Add `/api/v1/cars/{id}/similar` endpoint
- Add `/api/v1/motorcycles/{id}/similar` endpoint
- Timeout handling (3s with fallback)
- Graceful degradation on AI service unavailability

### 🔜 Phase 6: Pre-computation (2 days)
- Celery + Redis broker setup
- Daily job: pre-compute top 100 vehicles
- Store in Redis with 24h TTL
- API-first precomputed cache lookup

### 🔜 Phase 7: Testing & Optimization (2 days)
- Unit tests (target: 80%+ coverage)
- Integration tests (Spring Boot ↔ AI service)
- Database indexes on `inquiries` table
- Performance tuning (target: P95 < 500ms)

**Progress: 6 of 14 days complete (42%)**

## 🧪 Testing

```bash
# Run unit tests
pytest tests/ -v

# Run with coverage report
pytest tests/ --cov=app --cov-report=html

# Run specific test file
pytest tests/test_content_similarity.py -v
```

### Current Test Coverage
- ✅ Feature engineering (normalization, encoding)
- ✅ Similarity score calculations
- ⏳ API endpoints (pending)
- ⏳ Cache behavior (pending)
- ⏳ Integration tests (pending)

## 🐛 Troubleshooting

### "Can't connect to database"
**Problem:** Service fails to connect to MySQL

**Solutions:**
1. Ensure backend MySQL is running: `docker ps | grep wheelshift-mysql`
2. Check MySQL is on port 3307: `mysql -h localhost -P 3307 -u wheelshift_ai -p`
3. Verify credentials in `.env` match database user
4. Confirm `wheelshift_ai` user has SELECT permissions:
   ```sql
   SHOW GRANTS FOR 'wheelshift_ai'@'%';
   ```

### "Can't connect to Redis"
**Problem:** Service fails to connect to Redis

**Solutions:**
1. **Start backend services first**: `cd ../wheelshift-backend && docker-compose -f docker-compose-dev.yml up -d`
2. Check Redis is running: `docker ps | grep wheelshift-redis`
3. Test connection: `redis-cli -h localhost -p 6379 ping` (should return `PONG`)
4. Verify `REDIS_HOST` and `REDIS_PORT` in `.env`

### "ModuleNotFoundError"
**Problem:** Python can't find installed packages

**Solutions:**
1. Activate virtual environment: `venv\Scripts\activate` (Windows) or `source venv/bin/activate` (Linux/Mac)
2. Reinstall dependencies: `pip install -r requirements.txt`
3. Check Python version: `python --version` (should be 3.11+)

### "No similar vehicles found"
**Problem:** API returns empty suggestions

**Solutions:**
1. Verify `vehicleId` exists in database: Check `cars` or `motorcycles` table
2. Ensure vehicle status is not `SOLD` (excluded by default)
3. Check logs for errors: `tail -f logs/app.log`
4. Try increasing `limit` parameter: `?limit=20`

## 📊 Performance Targets

| Metric | Current | Target |
|--------|---------|--------|
| Health check | ✅ <50ms | <50ms |
| Content similarity (cache hit) | ✅ <50ms | <50ms |
| Content similarity (cache miss) | 🎯 200-300ms | <300ms |
| Hybrid similarity | ⏳ TBD | <400ms |
| Precomputed lookup | ⏳ TBD | <50ms |
| P95 under load (100 concurrent) | ⏳ TBD | <500ms |

## 🔑 Key Decisions

### Architecture
- **Separate Python service** for ML workloads (not embedded in Spring Boot) → leverages scikit-learn ecosystem, independent scaling
- **REST over message queue** for similarity API → synchronous response expected by frontend
- **Redis as shared cache** between services → reduces compute, consistent TTL management

### Algorithm
- **Hybrid approach** (60% content + 40% collaborative) → balances cold-start coverage with personalization
- **Feature priorities**: Price (±15%), Brand, Body Type, Year, Fuel Type, Mileage
- **No LLM** for this feature → keeps latency <300ms and zero API costs

### Caching Strategy
- **Two-tier caching**: Pre-computed (top 100, 24h TTL) + on-demand (long tail, 30min TTL)
- **Separate feature vector cache** (1h TTL) → reused across multiple similarity computations
- **Cache invalidation**: Manual clear on vehicle status change to SOLD

## 📚 Documentation

- **API Docs**: http://localhost:8000/docs (Swagger UI)
- **Implementation Plan**: See `PLAN.md` for full 14-day roadmap
- **Current Status**: See `STATUS.md` for detailed progress tracking
- **Database Design**: See `../wheelshift-backend/docs/DATABASE_DESIGN.md`

## 📄 License

Proprietary - WheelShift Pro © 2026

---

**Version:** 0.2.0 (Phases 1-2 Complete)  
**Last Updated:** March 31, 2026  
**Next Milestone:** Phase 3 - Collaborative Filtering
