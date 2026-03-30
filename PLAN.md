## Plan: Similar Vehicle Suggestions Feature (Hybrid ML Approach)

**TL;DR:** Build a hybrid similarity engine combining content-based filtering (vehicle attributes) and collaborative filtering (client behavior) using sklearn. Deploy as a FastAPI service that Spring Boot calls via REST. Pre-compute similarities for top 100 vehicles, compute on-demand for others, cache results in Redis.

**Why Hybrid?**
- Content-based ensures all vehicles get suggestions (even new inventory)
- Collaborative filtering adds personalization based on what similar clients viewed/purchased
- Pure ML approach (no LLM) keeps costs zero and latency under 200ms

---

## Steps

### Phase 1: AI Service Foundation (Days 1-2)

1. **Scaffold FastAPI project** in `wheelshift-ai/`
   - Project structure: `app/`, `models/`, `services/`, `utils/`, `config/`
   - Dependencies: FastAPI, uvicorn, SQLAlchemy, pymysql, redis-py, scikit-learn, pandas, numpy
   - Docker setup: Dockerfile + add to `docker-compose-dev.yml`
   - Environment config: `.env` for DB/Redis credentials

2. **Database connection setup**
   - SQLAlchemy models for Car, CarModel, Motorcycle, MotorcycleModel, Inquiry (read-only)
   - Create MySQL user `wheelshift_ai` with SELECT-only permissions
   - Connection pool config (max 10 connections, 30s timeout)

3. **Redis caching layer**
   - Redis client with connection pooling
   - Cache key patterns: `similarity:car:{id}:v1`, `similarity:motorcycle:{id}:v1`
   - TTL: 30 minutes for on-demand, 24 hours for pre-computed

4. **Health check endpoint**
   - `GET /health` returning DB connection status, Redis status, model loaded status

### Phase 2: Content-Based Similarity Engine (Days 3-5)

5. **Feature engineering pipeline** *(parallel with step 6)*
   - Extract features from DB: price, year, mileage, make, model, bodyType/vehicleType, fuelType
   - Numerical normalization: Min-Max scaling for price (0-1), StandardScaler for year/mileage
   - Categorical encoding: One-hot for fuelType, bodyType; label encoding for make/model
   - Text features: TF-IDF vectorization on concatenated make+model+variant string
   - Feature weights: price (0.25), make/brand (0.20), bodyType (0.15), year (0.15), mileage (0.10), fuelType (0.10), text similarity (0.05)

6. **Similarity computation service** *(parallel with step 5)*
   - Cosine similarity on combined feature vectors
   - Filter logic: exclude same vehicle, same status (e.g., don't suggest SOLD cars)
   - Price band filter: ±15% of target vehicle price
   - Top-K selection: return top 10 similar vehicles with similarity scores (0-100)

7. **API endpoint: Content-based similarity**
   - `GET /api/ai/vehicles/similar/content?vehicleId=42&type=car&limit=10`
   - Response: `[{vehicleId: 18, score: 94, reasons: ["same_brand", "similar_price", "same_body_type"]}]`
   - Cache result in Redis with 30-min TTL

### Phase 3: Collaborative Filtering (Days 6-7)

8. **Client interaction data pipeline**
   - Extract from DB: Inquiries table (client_id, car_id/motorcycle_id, created_at)
   - Build user-item interaction matrix: rows=clients, cols=vehicles, values=1 (viewed/inquired)
   - Handle cold start: require minimum 50 interactions across 10+ clients before enabling collaborative

9. **Collaborative filtering model**
   - Item-item collaborative filtering using cosine similarity on interaction matrix
   - "Clients who viewed X also viewed Y" logic
   - Compute co-occurrence matrix: for each vehicle pair, count shared clients
   - Normalize by total views to get co-view probability

10. **API endpoint: Collaborative similarity**
    - `GET /api/ai/vehicles/similar/collaborative?vehicleId=42&type=car&limit=10`
    - Fallback to content-based if insufficient interaction data
    - Cache result in Redis with 24-hour TTL (changes slowly)

### Phase 4: Hybrid Ranking (Day 8)

11. **Hybrid score combiner** *(depends on steps 7 & 10)*
    - Merge content-based (0.6 weight) + collaborative (0.4 weight) scores
    - Re-rank by combined score, remove duplicates
    - Return unified top-10 list with reasons from both models

12. **Main API endpoint**
    - `GET /api/ai/vehicles/similar?vehicleId=42&type=car&limit=10`
    - Response schema (as per AI_SERVICE_OVERVIEW.md):
      ```json
      {
        "sourceVehicleId": 42,
        "suggestions": [
          {"vehicleId": 18, "score": 0.94, "reason": "Same segment, similar price + 8 co-views"},
          {"vehicleId": 55, "score": 0.87, "reason": "Same brand, newer model nearby price"}
        ]
      }
      ```

### Phase 5: Spring Boot Integration (Days 9-10)

13. **Add AIServiceClient to Spring Boot** *(parallel with step 14)*
    - Create `AIServiceClient.java` using WebClient
    - Method: `Optional<SimilarVehiclesDto> getSimilarVehicles(Long vehicleId, String type, int limit)`
    - Timeout: 3 seconds, fallback to empty list on error
    - Config: `ai.service.base-url=http://ai-service:8000`, `ai.service.enabled=true`

14. **New Spring Boot endpoints** *(parallel with step 13)*
    - `GET /api/v1/cars/{id}/similar?limit=5`
    - `GET /api/v1/motorcycles/{id}/similar?limit=5`
    - Service layer: call AIServiceClient, fetch full vehicle DTOs, return enriched response
    - Cache in Redis (shared key: `vehicles:similar:{type}:{id}`) with 30-min TTL

15. **Error handling & fallback**
    - If AI service unavailable: return empty suggestions with `"similaritiesAvailable": false` flag
    - Log AI service errors at WARN level (not ERROR/ALERT)
    - Graceful degradation: UI shows "Similar vehicles unavailable" instead of breaking

### Phase 6: Pre-computation Strategy (Days 11-12)

16. **Celery setup for background jobs**
    - Install Celery + Redis broker
    - Celery worker config: 2 workers, concurrency=4
    - Task: `precompute_top_vehicles()` runs daily at 2 AM

17. **Pre-computation job** *(depends on step 12)*
    - Identify top 100 vehicles: most viewed (from Inquiries count), most recent, AVAILABLE status
    - Compute hybrid similarities for each, store in Redis with `similarity:precomputed:{type}:{id}` key
    - TTL: 24 hours (refreshed daily)
    - API endpoint checks precomputed cache first, falls back to on-demand computation

### Phase 7: Testing & Optimization (Days 13-14)

18. **Unit tests**
    - Feature engineering correctness (normalized values, encoding)
    - Similarity score calculations (known vehicle pairs)
    - Cache hit/miss behavior
    - Fallback scenarios (AI service down)

19. **Integration tests**
    - End-to-end: Spring Boot → AI service → Redis → Response
    - Test both car and motorcycle similarity
    - Test pre-computed vs on-demand paths
    - Performance: measure P95 latency (target: < 300ms)

20. **Performance tuning**
    - Add database indexes: `inquiries(car_id, created_at)`, `inquiries(motorcycle_id, created_at)`
    - Redis connection pooling: min 5, max 20 connections
    - SQLAlchemy query optimization: eager loading, select only needed columns
    - Feature vector caching: cache normalized features per vehicle for 1 hour

---

## Relevant Files

**New Files in `wheelshift-ai/`:**
- `app/main.py` — FastAPI app initialization, middleware, routes
- `app/api/v1/similarity.py` — Similarity endpoints (steps 7, 10, 12)
- `app/services/content_similarity.py` — Content-based engine (steps 5-6)
- `app/services/collaborative_similarity.py` — Collaborative filtering (steps 8-9)
- `app/services/hybrid_ranker.py` — Score combiner (step 11)
- `app/services/feature_engineering.py` — Feature extraction and normalization (step 5)
- `app/models/vehicle_models.py` — SQLAlchemy models for Car/Motorcycle (step 2)
- `app/utils/cache.py` — Redis cache wrapper (step 3)
- `app/utils/db.py` — Database session manager (step 2)
- `app/tasks/precompute.py` — Celery background job (step 17)
- `Dockerfile` — Multi-stage build: dependencies → app
- `requirements.txt` — FastAPI, uvicorn, SQLAlchemy, pymysql, redis, scikit-learn, pandas, numpy, celery, python-dotenv
- `.env.example` — Environment variables template
- `tests/` — Unit and integration tests (steps 18-19)

**Modified Files in `wheelshift-backend/`:**
- `src/main/java/com/wheelshiftpro/config/AIServiceConfig.java` — WebClient bean, properties (step 13)
- `src/main/java/com/wheelshiftpro/client/AIServiceClient.java` — REST client for AI service (step 13)
- `src/main/java/com/wheelshiftpro/dto/ai/SimilarVehiclesDto.java` — Response DTO (step 13)
- `src/main/java/com/wheelshiftpro/controller/CarController.java` — Add `GET /{id}/similar` endpoint (step 14)
- `src/main/java/com/wheelshiftpro/controller/MotorcycleController.java` — Add `GET /{id}/similar` endpoint (step 14)
- `src/main/java/com/wheelshiftpro/service/CarService.java` — Inject AIServiceClient, implement getSimilarCars() (step 14)
- `src/main/java/com/wheelshiftpro/service/MotorcycleService.java` — Inject AIServiceClient, implement getSimilarMotorcycles() (step 14)
- `src/main/resources/application.properties` — Add `ai.service.*` properties (step 13)
- `docker-compose-dev.yml` — Add `ai-service` container (step 1)

**Database Files:**
- **No migrations needed** — read-only access, no schema changes
- **New indexes** (recommended for Inquiries table performance in step 20):
  - `CREATE INDEX idx_inquiries_car_created ON inquiries(car_id, created_at);`
  - `CREATE INDEX idx_inquiries_motorcycle_created ON inquiries(motorcycle_id, created_at);`

---

## Verification

### Automated Tests
1. **Unit tests pass**: `pytest tests/` in wheelshift-ai (50+ tests, 80%+ coverage)
2. **Integration tests pass**: `mvn test` in wheelshift-backend (SimilarityIntegrationTest)
3. **Load test**: 100 concurrent similarity requests → P95 < 500ms

### Manual Validation
1. **Content-based accuracy**: Pick 5 known similar cars (e.g., Honda City 2020 vs Honda City 2021) → verify they appear in top 3 suggestions
2. **Collaborative relevance**: For a vehicle with 20+ inquiries, check that co-viewed vehicles rank higher than pure content matches
3. **Cache effectiveness**: Hit rate > 60% after 1 hour of usage (monitor Redis `INFO stats`)
4. **Fallback behavior**: Stop AI service → Spring Boot still returns HTTP 200 with empty suggestions
5. **Cross-vehicle type isolation**: Car similarity doesn't return motorcycles, and vice versa

### Performance Benchmarks
1. **On-demand computation**: < 300ms for cache miss (measured in AI service logs)
2. **Pre-computed lookup**: < 50ms for cache hit
3. **Spring Boot endpoint**: < 400ms total (including vehicle detail enrichment)
4. **Daily pre-computation job**: Completes in < 10 minutes for 100 vehicles

---

## Decisions

### Architecture
- **Separate Python service** for ML workloads (not embedded in Spring Boot) — leverages scikit-learn ecosystem, independent scaling
- **REST over Kafka** for similarity API — synchronous response expected by frontend, simpler than async event stream
- **Redis as shared cache** between Spring Boot and AI service — reduces duplicate computation, consistent TTL management

### Similarity Algorithm
- **Hybrid approach** (60% content, 40% collaborative) — balances cold-start coverage with personalization
- **Top priority features**: Price (±15%), Make/Brand, Body/Vehicle Type, Fuel Type, Year, Mileage — matches user's business requirements
- **No LLM** for this feature — pure ML keeps response time < 300ms and zero API costs

### Caching Strategy
- **Hybrid caching**: Pre-compute top 100 vehicles (most viewed/recent), on-demand for long tail — optimizes for 80/20 rule (80% of requests hit 20% of inventory)
- **Separate TTLs**: 24h for pre-computed (stable), 30m for on-demand (fresher) — balances freshness with compute cost
- **Cache invalidation**: On vehicle status change (e.g., SOLD), clear similarity cache for that vehicle

### Data Scope
- **Read-only database access** via dedicated `wheelshift_ai` MySQL user — prevents accidental writes, follows least-privilege principle
- **Only AVAILABLE vehicles** in similarity results — don't suggest sold/maintenance vehicles unless explicitly filtering for them
- **Minimum interaction threshold**: Require 50+ inquiries across 10+ clients before enabling collaborative — avoids noisy recommendations from sparse data

---

## Further Considerations

1. **Cold Start for New Vehicles**: New inventory has no inquiry history → pure content-based until 3+ inquiries. Consider adding "Recently Added" boost in ranking. **Recommendation**: Add a `recency_score` (vehicle age in days, exponential decay) with 0.05 weight in hybrid combiner.

2. **Client Personalization (Future)**: Currently collaborative uses "all clients who viewed X". Could enhance with per-client recommendations: "Given your history of viewing SUVs, here are similar vehicles." **Recommendation**: Phase 2 feature — requires passing `clientId` to API, building user-specific embeddings.

3. **Cross-Type Suggestions (Optional)**: Should luxury cars suggest premium motorcycles for budget-conscious clients? **Recommendation**: Keep car/motorcycle separate for initial launch. Can add cross-type in UI as "Alternative: Consider a motorcycle in your price range."

---

**Estimated Effort**: 14 developer-days (2 weeks with 1 full-time engineer)
**Tech Stack**: Python 3.11, FastAPI, SQLAlchemy, scikit-learn, Redis, Celery, Docker
**Dependencies**: Requires Spring Boot backend running, MySQL accessible, Redis running
**Risk Level**: Low — read-only data access, graceful fallback if AI service unavailable
