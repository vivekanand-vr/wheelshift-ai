# WheelShift AI Service

AI-powered vehicle similarity and recommendation engine for WheelShift Pro.

## Features

- **Content-Based Similarity**: Vehicle attribute-based recommendations
- **Collaborative Filtering**: Client behavior-based recommendations
- **Hybrid Ranking**: Combined approach for optimal suggestions
- **Pre-computation**: Daily background jobs for top vehicles
- **Caching**: Redis-based caching for fast responses

## Quick Start

### Prerequisites

- Python 3.11+
- **wheelshift-backend running** (provides MySQL and Redis via docker-compose-dev.yml)
- Docker & Docker Compose (optional)

### Local Development

1. **Clone and setup**:
   ```bash
   cd wheelshift-ai
   cp .env.example .env
   # Edit .env with your database credentials
   ```

2. **Create virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Create database user**:
   ```sql
   -- Connect to backend's MySQL on port 3307
   mysql -h localhost -P 3307 -u root -p
   
   CREATE USER 'wheelshift_ai'@'%' IDENTIFIED BY 'your_secure_password';
   GRANT SELECT ON wheelshift_db.* TO 'wheelshift_ai'@'%';
   FLUSH PRIVILEGES;
   ```

4. **Run the service**:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

5. **Check health**:
   ```bash
   curl http://localhost:8000/health
   ```

### Docker Deployment

```bash
# 1. Start backend services first (from wheelshift-backend directory)
cd ../wheelshift-backend
docker-compose -f docker-compose-dev.yml up -d mysql redis

# 2. Build and run AI service (joins backend's docker network)
cd ../wheelshift-ai
docker-compose up --build
```

## API Endpoints

### Health Check
```
GET /health
```

### Similarity (Coming Soon)
```
GET /api/ai/vehicles/similar?vehicleId=42&type=car&limit=10
GET /api/ai/vehicles/similar/content?vehicleId=42&type=car&limit=10
GET /api/ai/vehicles/similar/collaborative?vehicleId=42&type=car&limit=10
```

## Architecture

```
app/
├── main.py                 # FastAPI application
├── config.py               # Configuration management
├── api/
│   └── v1/
│       └── similarity.py   # Similarity endpoints
├── services/
│   ├── content_similarity.py      # Content-based engine
│   ├── collaborative_similarity.py # Collaborative filtering
│   └── hybrid_ranker.py           # Hybrid combiner
├── models/
│   └── vehicle_models.py   # SQLAlchemy models
├── utils/
│   ├── db.py              # Database utilities
│   ├── cache.py           # Redis caching
│   └── logger.py          # Logging setup
└── tasks/
    └── precompute.py      # Celery background jobs
```

## Configuration

Key environment variables (see `.env.example`):

- `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`: Database config (connects to backend's MySQL)
- `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`: Redis config (connects to backend's Redis, uses DB 1)
- `ENABLE_COLLABORATIVE_FILTERING`: Enable/disable collaborative filtering
- `CACHE_TTL_ONDEMAND`: Cache TTL for on-demand computations (default: 1800s)
- `CACHE_TTL_PRECOMPUTED`: Cache TTL for pre-computed results (default: 86400s)
- `CONTENT_BASED_WEIGHT`: Weight for content-based score (default: 0.6)
- `COLLABORATIVE_WEIGHT`: Weight for collaborative score (default: 0.4)

## Testing

```bash
# Run unit tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html
```

## Development Status

- [x] Phase 1: Project scaffold & infrastructure
- [ ] Phase 2: Content-based similarity engine
- [ ] Phase 3: Collaborative filtering
- [ ] Phase 4: Hybrid ranking
- [ ] Phase 5: Spring Boot integration
- [ ] Phase 6: Pre-computation strategy
- [ ] Phase 7: Testing & optimization

## License

Proprietary - WheelShift Pro © 2026
