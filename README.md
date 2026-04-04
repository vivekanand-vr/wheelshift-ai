# WheelShift AI Service

Python/FastAPI microservice that provides AI-powered vehicle similarity recommendations and lead scoring for WheelShift Pro. It reads from the same MySQL database as the Spring Boot backend (read-only) and caches results in the shared Redis instance.

The similarity engine uses a hybrid approach: content-based filtering (vehicle attributes) combined with collaborative filtering (client inquiry patterns), blended 60/40 in favor of content. The lead scoring engine ranks open inquiries by conversion likelihood using a six-signal weighted model.

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
│   ├── similarity.py            # Similarity endpoints
│   └── lead_scoring.py          # Lead scoring endpoints
├── models/
│   ├── vehicle_models.py        # SQLAlchemy models (read-only, mirrors backend schema)
│   └── lead_models.py           # Read-only models: Client, Sale, Reservation
├── schemas/
│   └── responses.py             # Pydantic response schemas
├── services/
│   ├── feature_engineering.py   # Feature extraction and normalization
│   ├── content_similarity.py    # Content-based cosine similarity
│   ├── collaborative_similarity.py
│   ├── hybrid_ranker.py         # Combines content + collaborative scores
│   └── lead_scoring.py          # Six-signal lead scoring engine
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
| `LS_HOT_THRESHOLD` | `70` | Minimum score for a Hot lead |
| `LS_WARM_THRESHOLD` | `40` | Minimum score for a Warm lead |
| `CACHE_TTL_LEAD_SCORE` | `900` | Lead score Redis TTL in seconds |

## API Endpoints

All endpoints require `X-API-Key` header authentication.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/ai/vehicles/similar/content` | Content-based vehicle similarity |
| `GET` | `/api/ai/vehicles/similar/collaborative` | Collaborative filtering similarity |
| `GET` | `/api/ai/vehicles/similar/hybrid` | Hybrid similarity (recommended) |
| `POST` | `/api/ai/leads/score` | Score a single inquiry (0–100 + Hot/Warm/Cold) |
| `POST` | `/api/ai/leads/score/batch` | Score up to 50 inquiries in one call |
| `GET` | `/health` | Service + dependency health check |

Interactive API docs: `http://localhost:8000/docs` (development only)

## Testing

```bash
# Requires Python 3.11+ and dependencies from requirements-dev.txt
pytest tests/ -v
```

## Documentation

| Doc | Description |
|-----|-------------|
| [docs/LEAD_SCORING.md](docs/LEAD_SCORING.md) | Lead scoring signal weights, thresholds, and configuration |
| [docs/BACKEND_INTEGRATION.md](docs/BACKEND_INTEGRATION.md) | Spring Boot integration guide — DTOs, WebClient, graceful degradation |
| [docs/CONTENT_BASED.md](docs/CONTENT_BASED.md) | Content-based similarity implementation |
| [docs/COLLABORATIVE_FILTERING.md](docs/COLLABORATIVE_FILTERING.md) | Collaborative filtering implementation |
| [docs/HYBRID_RANKING.md](docs/HYBRID_RANKING.md) | Hybrid ranking blending strategy |

## License

Proprietary — WheelShift Pro © 2026
