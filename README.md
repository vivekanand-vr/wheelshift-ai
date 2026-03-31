# WheelShift AI Service

Python/FastAPI microservice that provides AI-powered vehicle similarity recommendations for WheelShift Pro. It reads from the same MySQL database as the Spring Boot backend (read-only) and caches results in the shared Redis instance.

The similarity engine uses a hybrid approach: content-based filtering (vehicle attributes) combined with collaborative filtering (client inquiry patterns), blended 60/40 in favor of content.

## Architecture

```
Spring Boot Backend
        |
        | HTTP (port 8000)
        v
  FastAPI AI Service
        |
   -----+-----
   |         |
 MySQL      Redis
(read-only) (DB 1, shared with backend)
```

The AI service joins the same Docker network as the backend (`wheelshift-backend_wheelshift-network`) and communicates with MySQL and Redis using their internal Docker hostnames.

## Project Structure

```
app/
├── main.py                      # FastAPI app entry point
├── config.py                    # Settings (pydantic-settings, reads from .env)
├── api/v1/
│   └── similarity.py            # Similarity endpoints
├── models/
│   └── vehicle_models.py        # SQLAlchemy models (read-only, mirrors backend schema)
├── schemas/
│   └── responses.py             # Pydantic response schemas
├── services/
│   ├── feature_engineering.py   # Feature extraction and normalization
│   ├── content_similarity.py    # Content-based cosine similarity
│   ├── collaborative_similarity.py
│   └── hybrid_ranker.py         # Combines content + collaborative scores
├── tasks/
│   └── precompute.py            # Celery background jobs
└── utils/
    ├── db.py                    # SQLAlchemy session management
    ├── cache.py                 # Redis caching helpers
    └── logger.py                # JSON logging
```

## Setup

### Prerequisites

- Docker Desktop running
- WheelShift backend stack running (`docker-compose -f docker-compose-dev.yml up -d` in the backend directory)

### 1. Create the read-only database user

```bash
docker exec -it wheelshift-mysql mysql -u root -proot
```

```sql
CREATE USER 'wheelshift_ai'@'%' IDENTIFIED BY 'ai_secure_pass_2026';
GRANT SELECT ON wheelshift_db.* TO 'wheelshift_ai'@'%';
FLUSH PRIVILEGES;
```

### 2. Configure environment

```bash
copy .env.example .env
```

The defaults in `.env.example` match the backend's Docker setup. The only value you must set is `DB_PASSWORD`.

### 3. Run

```bash
docker-compose up --build
```

The service binds to port `8000`. API docs are available at `http://localhost:8000/docs`.

## Configuration

All settings are in `.env` (see `.env.example` for the full list). Key values:

| Variable | Default | Description |
|---|---|---|
| `DB_HOST` | `localhost` | MySQL host (use `mysql` in Docker) |
| `DB_PORT` | `3307` | MySQL port |
| `DB_PASSWORD` | — | Password for `wheelshift_ai` user |
| `REDIS_DB` | `1` | Redis database index (backend uses 0) |
| `WEIGHT_PRICE` | `0.25` | Similarity feature weight |
| `CONTENT_BASED_WEIGHT` | `0.6` | Hybrid blend ratio |
| `CACHE_TTL_ONDEMAND` | `1800` | On-demand cache TTL in seconds |

## Testing

```bash
# Requires Python 3.11+ and dependencies from requirements-dev.txt
pytest tests/ -v
```

## License

Proprietary — WheelShift Pro © 2026
