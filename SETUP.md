# WheelShift AI Service - Setup Instructions

## Phase 1 & 2 Complete! ✅

You've successfully completed:
- ✅ Project scaffolding with FastAPI
- ✅ Database connection (SQLAlchemy + MySQL)
- ✅ Redis caching layer
- ✅ Health check endpoint
- ✅ Feature engineering pipeline
- ✅ Content-based similarity engine
- ✅ API endpoints for similarity

## Quick Start

### 1. Setup Environment

```bash
cd d:\My Projects\wheelshift-ai

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Copy environment config
copy .env.example .env
```

### 2. Configure .env File

Edit `.env` and set:
```env
DB_HOST=localhost
DB_PORT=3307
DB_USER=wheelshift_ai
DB_PASSWORD=your_password_here
DB_NAME=wheelshift_db

REDIS_HOST=localhost
REDIS_PORT=6379
```

### 3. Create Database User

Connect to MySQL and run:
```sql
CREATE USER 'wheelshift_ai'@'%' IDENTIFIED BY 'your_password_here';
GRANT SELECT ON wheelshift_db.* TO 'wheelshift_ai'@'%';
FLUSH PRIVILEGES;
```

### 4. Run the Service

**Option A: Direct Python**
```bash
python run.py
```

**Option B: Uvicorn**
```bash
uvicorn app.main:app --reload --port 8000
```

**Option C: Docker Compose**
```bash
# First, ensure backend services are running
cd "../wheelshift-backend"
docker-compose -f docker-compose-dev.yml up -d mysql redis

# Then start AI service (it will join the backend's network)
cd "../wheelshift-ai"
docker-compose up --build
```

### 5. Test the Service

```bash
# Health check
curl http://localhost:8000/health

# API docs
# Open in browser: http://localhost:8000/docs

# Test similarity (replace 1 with an actual car ID)
curl "http://localhost:8000/api/ai/vehicles/similar/content?vehicleId=1&type=car&limit=5"
```

## Available Endpoints

### Health & Info
- `GET /` - Service info
- `GET /health` - Health check (DB + Redis status)
- `GET /docs` - Interactive API documentation (Swagger UI)

### Similarity
- `GET /api/ai/vehicles/similar/content` - Content-based similarity
  - Query params: `vehicleId`, `type` (car|motorcycle), `limit`
- `GET /api/ai/vehicles/similar` - Hybrid similarity (uses content for now)
  - Query params: `vehicleId`, `type` (car|motorcycle), `limit`

## Run Tests

```bash
# Install test dependencies (if not already installed)
pip install pytest pytest-asyncio httpx

# Run tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=app --cov-report=html
```

## Next Steps

### Phase 3: Collaborative Filtering (Pending)
- Build user-item interaction matrix from `inquiries` table
- Implement item-item collaborative filtering
- Create collaborative similarity endpoint

### Phase 4: Hybrid Ranking (Pending)
- Combine content (60%) + collaborative (40%) scores
- Update main `/similar` endpoint with hybrid logic

### Phase 5: Spring Boot Integration (Pending)
- Create `AIServiceClient.java` in Spring Boot
- Add `/api/v1/cars/{id}/similar` endpoint
- Add `/api/v1/motorcycles/{id}/similar` endpoint

### Phase 6: Pre-computation (Pending)
- Setup Celery workers
- Implement daily batch job for top 100 vehicles
- Store precomputed results in Redis

### Phase 7: Optimization (Pending)
- Add database indexes on `inquiries` table
- Load testing and performance tuning
- Integration testing

## Troubleshooting

### "Can't connect to database"
- Check MySQL is running on port 3307
- Verify `wheelshift_ai` user exists and has SELECT permissions
- Test connection: `mysql -h localhost -P 3307 -u wheelshift_ai -p`

### "Can't connect to Redis"
- **Ensure wheelshift-backend is running** (`docker-compose -f docker-compose-dev.yml up -d` in backend directory)
- Check Redis is accessible: `redis-cli -p 6379 ping`
- Verify the `wheelshift-redis` container is up: `docker ps | grep wheelshift-redis`

### "Module not found"
- Activate virtual environment: `venv\Scripts\activate`
- Reinstall dependencies: `pip install -r requirements.txt`

## Project Structure

```
wheelshift-ai/
├── app/
│   ├── main.py                 # FastAPI application
│   ├── config.py               # Settings management
│   ├── api/
│   │   └── v1/
│   │       └── similarity.py   # Similarity endpoints
│   ├── models/
│   │   └── vehicle_models.py   # SQLAlchemy models
│   ├── schemas/
│   │   └── responses.py        # Pydantic response schemas
│   ├── services/
│   │   ├── feature_engineering.py      # Feature extraction
│   │   └── content_similarity.py       # Content-based engine
│   └── utils/
│       ├── db.py              # Database utilities
│       ├── cache.py           # Redis caching
│       └── logger.py          # Logging setup
├── tests/
│   ├── conftest.py            # Test configuration
│   └── test_content_similarity.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
├── README.md
└── run.py                     # Development runner
```

## Architecture

```
┌─────────────┐
│ Spring Boot │ ──HTTP──> ┌──────────────┐
│  Backend    │           │  FastAPI     │
└─────────────┘           │  AI Service  │
                          │  (Port 8000) │
                          └───────┬──────┘
                                  │
                     ┌────────────┼────────────┐
                     ▼            ▼            ▼
                ┌─────────┐  ┌────────┐  ┌────────┐
                │  MySQL  │  │ Redis  │  │ Celery │
                │ (Read)  │  │ Cache  │  │ Worker │
                └─────────┘  └────────┘  └────────┘
```

## Performance Targets

- ✅ Health check: < 50ms
- ✅ Content similarity (cache hit): < 50ms
- 🎯 Content similarity (cache miss): < 300ms
- 🎯 Hybrid similarity: < 400ms

## Support

For issues or questions, refer to:
- Implementation plan: `plan.md`
- AI service spec: `../wheelshift-backend/docs/AI_SERVICE_OVERVIEW.md`
- Database design: `../wheelshift-backend/docs/DATABASE_DESIGN.md`

---

**Status:** Phase 1 & 2 Complete | Phase 3-7 Pending
**Version:** 0.1.0
**Last Updated:** March 24, 2026
