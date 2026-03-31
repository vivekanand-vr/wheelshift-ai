# Collaborative Filtering Engine

Recommends vehicles based on shared client inquiry behaviour. "Clients who inquired about vehicle X also inquired about vehicle Y."

**Source:** `app/services/collaborative_similarity.py`

---

## How It Works

```
 API Request
     │
     ▼
┌──────────────────────────────────────────────────────────┐
│  CollaborativeSimilarityService.find_similar_cars()      │
└──────────────────────────────┬───────────────────────────┘
                               │
               ┌───────────────▼────────────────┐
               │  1. Threshold check             │
               │     ≥ 50 total inquiries?       │
               │     ≥ 10 unique clients?        │
               └──────────┬──────────┬──────────┘
                          │NO        │YES
                          ▼          ▼
                      return []   continue
                     (fallback    │
                    to content)   │
               ┌──────────────────▼──────────────┐
               │  2. Who inquired about source?  │
               │     SELECT DISTINCT client_id   │
               │     FROM inquiries              │
               │     WHERE car_id = :id          │
               └──────────────────┬──────────────┘
                                  │
               ┌──────────────────▼──────────────┐
               │  3. What else did they view?    │
               │     SELECT car_id,              │
               │       COUNT(DISTINCT client_id) │
               │     FROM inquiries              │
               │     WHERE client_id IN (...)    │
               │       AND car_id != :source     │
               │     GROUP BY car_id             │
               └──────────────────┬──────────────┘
                                  │
               ┌──────────────────▼──────────────┐
               │  4. Compute Jaccard scores       │
               │     (see formula below)          │
               └──────────────────┬──────────────┘
                                  │
               ┌──────────────────▼──────────────┐
               │  5. Sort by score desc           │
               │     Fetch vehicle details        │
               │     Apply status filter          │
               │     Return top-K results         │
               └──────────────────┬──────────────┘
                                  │
               ┌──────────────────▼──────────────┐
               │  6. Cache result (24h TTL)       │
               └──────────────────────────────────┘
```

---

## Interaction Matrix (Conceptual)

```
          Vehicle A  Vehicle B  Vehicle C  Vehicle D  Vehicle E
          ─────────────────────────────────────────────────────
Client 1 │    ✓                    ✓                     ✓
Client 2 │    ✓          ✓         ✓
Client 3 │               ✓                    ✓
Client 4 │    ✓                               ✓
Client 5 │    ✓          ✓
          ─────────────────────────────────────────────────────

  Source: Vehicle A  ─── 4 clients inquired (1, 2, 4, 5)

  Co-inquired vehicles from those 4 clients:
    Vehicle B: clients 2, 5 → co_views = 2
    Vehicle C: clients 1, 2 → co_views = 2
    Vehicle D: client 4     → co_views = 1
    Vehicle E: client 1     → co_views = 1
```

---

## Scoring Formula

Jaccard-like normalization prevents popular vehicles from dominating the rankings.

```
                          co_views(X, Y)
  score(X, Y)  =  ─────────────────────────────────────────────
                   clients(X) + total_inquiries(Y) - co_views(X, Y)


  Where:
    co_views(X, Y)       = # unique clients who inquired about BOTH X and Y
    clients(X)           = # unique clients who inquired about source X
    total_inquiries(Y)   = total inquiry count for candidate Y (not deduplicated)

  Result range: (0.0, 1.0]
  1.0 = every client of X also inquired about Y, and Y has no other inquiries
  0.0 = no shared clients at all (excluded from results)
```

### Worked Example

```
  Source (Vehicle A): 4 unique clients
  Candidate (Vehicle B): co_views = 2, total inquiries = 5

  score = 2 / (4 + 5 - 2)
        = 2 / 7
        = 0.2857

  Candidate (Vehicle C): co_views = 2, total inquiries = 2

  score = 2 / (4 + 2 - 2)
        = 2 / 4
        = 0.5000   ← higher score despite same co_views
                      because C is less "popular"
```

---

## Cold Start Handling

Collaborative filtering is only activated when there is enough interaction data to produce meaningful signals.

```
  settings.enable_collaborative_filtering = True?
                │
          NO ───┤
                │           YES
                │            │
                │    total car inquiries >= 50?
                │            │
                │      NO ───┤
                │            │       YES
                │            │        │
                │            │  unique clients >= 10?
                │            │        │
                │      NO ───┘        │ YES
                │                     │
                ▼                     ▼
           return []            run algorithm
          (engine will          (sufficient data)
          fall back to
          content-based)

  Thresholds: MIN_INTERACTIONS_THRESHOLD = 50 (default)
              MIN_CLIENTS_THRESHOLD      = 10 (default)
  Configurable via environment variables.
```

---

## Database Queries

### Query 1 — Source clients
```sql
SELECT DISTINCT client_id
FROM inquiries
WHERE car_id = :source_id
```

### Query 2 — Co-inquired vehicles
```sql
SELECT car_id,
       COUNT(DISTINCT client_id) AS co_views
FROM inquiries
WHERE client_id IN (:client_ids)
  AND car_id     != :source_id
  AND car_id     IS NOT NULL
GROUP BY car_id
```

### Query 3 — Total inquiries for normalization
```sql
SELECT car_id,
       COUNT(*) AS total
FROM inquiries
WHERE car_id IN (:candidate_ids)
GROUP BY car_id
```

### Query 4 — Enrich results (joined fetch)
```sql
SELECT cars.*, car_models.*
FROM cars
JOIN car_models ON cars.car_model_id = car_models.id
WHERE cars.id IN (:top_ids)
  AND cars.status NOT IN ('SOLD')
```

> Motorcycles use the identical pattern with `motorcycle_id` and the `motorcycles` / `motorcycle_models` tables.

---

## Result Shape

```
{
  "vehicleId": 55,
  "score":     0.50,
  "reason":    "4 co-inquiries by similar clients",
  "details": {
    "make":  "Honda",
    "model": "City",
    "year":  2021,
    "price": 420000.0
  }
}
```

The `reason` field uses the count of co-inquiries and correct pluralization:
- `"1 co-inquiry by similar clients"`
- `"3 co-inquiries by similar clients"`

---

## Caching Strategy

Collaborative results change slowly (inquiry patterns evolve day-by-day, not minute-by-minute), so they share the same 24-hour TTL as precomputed results.

```
  Request
     │
     ├── HIT ──► Redis key: similarity:collaborative:{type}:{id}:v1
     │                       TTL: 24 hours (CACHE_TTL_PRECOMPUTED)
     │                       Return cached response immediately
     │
     └── MISS ─► Run algorithm → store result
                 Key: similarity:collaborative:{type}:{id}:v1
                 TTL: 24 hours
```

The key follows the same `similarity:*:{type}:{id}:v1` pattern used across all similarity types, so the existing `invalidate_similarity()` glob wipe clears collaborative results too when a vehicle's status changes.

---

## API Endpoint

```
GET /api/ai/vehicles/similar/collaborative

Query Parameters:
  vehicleId  integer   required   Source vehicle ID
  type       string    required   "car" or "motorcycle"
  limit      integer   optional   1-50, default 10

Response (sufficient data):
{
  "sourceVehicleId": 42,
  "vehicleType":     "car",
  "suggestions": [...],
  "method":  "collaborative",
  "cached":  false
}

Response (insufficient data — automatic fallback):
{
  "sourceVehicleId": 42,
  "vehicleType":     "car",
  "suggestions": [...],
  "method":  "content",    ← note: method reflects actual source
  "cached":  false
}
```

---

## Limitations & Considerations

| Concern | Behaviour |
|---------|-----------|
| New vehicle (0 inquiries) | Returns `[]`, endpoint falls back to content-based |
| New deployment (< 50 total inquiries) | Entire engine disabled; all requests fall back |
| Heavily popular vehicle | Jaccard normalization reduces its dominance |
| Client inquiries same vehicle twice | `DISTINCT client_id` — counted as one interaction |
| SOLD candidates | Excluded in the final JOIN query |
| Cross-type suggestions | Not supported — car engine never queries motorcycles |
