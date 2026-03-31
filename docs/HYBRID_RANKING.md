# Hybrid Ranking Engine

Combines content-based and collaborative filtering scores into a single unified ranking. The primary endpoint — `GET /api/ai/vehicles/similar` — routes through this engine.

**Source:** `app/services/hybrid_ranker.py`

---

## How It Works

```
 GET /api/ai/vehicles/similar
              │
              │  1. Check precomputed Redis cache
              ├── HIT ──► return immediately (cached: true)
              │
              └── MISS ─► HybridRanker
                               │
                    ┌──────────┴──────────┐
                    │                     │
                    ▼                     ▼
           ContentSimilarity     CollaborativeSimilarity
           find_similar_*(       find_similar_*(
             id, limit=K×2)        id, limit=K×2)
                    │                     │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │    _merge()          │
                    │                     │
                    │  Union of vehicle   │
                    │  IDs from both sets │
                    │                     │
                    │  hybrid_score =     │
                    │  0.6×content_score  │
                    │ +0.4×collab_score   │
                    │                     │
                    │  Sort desc by score │
                    │  Take top-K         │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Cache (30min TTL)  │
                    │  Return response   │
                    └─────────────────────┘
```

---

## Score Merging

### Formula

```
  hybrid_score(V) = α × content_score(V) + β × collab_score(V)

  Where:
    α = CONTENT_BASED_WEIGHT  (default: 0.60)
    β = COLLABORATIVE_WEIGHT  (default: 0.40)
    α + β = 1.0

  If a vehicle appears in only one source, its missing score = 0.0:
    content_score  = 0.0  when vehicle not in content results
    collab_score   = 0.0  when vehicle not in collab results
```

### Worked Example

```
  Vehicle IDs from content engine:     [A=0.90, B=0.82, C=0.75, D=0.60]
  Vehicle IDs from collab engine:      [B=0.50, C=0.40, E=0.35]

  Union of IDs:  {A, B, C, D, E}

  Hybrid scores (α=0.6, β=0.4):
  ─────────────────────────────────────────────────────────────────
  Vehicle A:  0.6 × 0.90  +  0.4 × 0.00  =  0.540
  Vehicle B:  0.6 × 0.82  +  0.4 × 0.50  =  0.692   ← rises
  Vehicle C:  0.6 × 0.75  +  0.4 × 0.40  =  0.610
  Vehicle D:  0.6 × 0.60  +  0.4 × 0.00  =  0.360
  Vehicle E:  0.6 × 0.00  +  0.4 × 0.35  =  0.140
  ─────────────────────────────────────────────────────────────────

  Final ranked order:  B (0.692) > C (0.610) > A (0.540) > D (0.360) > E (0.140)

  Note: Vehicle B was ranked 2nd by content, but co-inquiry signal
        pushed it to 1st in the hybrid ranking.
```

---

## Degenerate Cases

When one engine produces no results, the hybrid ranker degrades gracefully without blending.

```
  content_results    collab_results    behaviour         method returned
  ───────────────────────────────────────────────────────────────────────
  non-empty          non-empty         full hybrid merge  "hybrid"
  non-empty          empty []          content only       "content"
  empty []           non-empty         collab only        "collaborative"
  empty []           empty []          empty result       "hybrid"
  ───────────────────────────────────────────────────────────────────────

  The method field in the API response always reflects
  what actually contributed, so callers know the provenance.
```

---

## Reason Combination

Each suggestion's `reason` field combines explanations from both engines.

```
  Vehicle B appears in both sources:

    content reason ──►  "same brand, similar price"
    collab  reason ──►  "3 co-inquiries by similar clients"

    combined reason ──► "same brand, similar price + 3 co-inquiries by similar clients"
                                                    ▲
                                            joined with " + "

  Vehicle A appears only in content:

    combined reason ──► "same brand, same sedan type"  (unchanged)

  Vehicle E appears only in collaborative:

    combined reason ──► "2 co-inquiries by similar clients"  (unchanged)
```

---

## Candidate Inflation

Each engine is asked for `limit × 2` candidates (not just `limit`). This ensures the union pool has enough coverage for merging to still yield `limit` final results.

```
  Caller asks for:    limit = 10

                  content engine         collab engine
                  ─────────────         ─────────────
  requested:         K×2 = 20              K×2 = 20

  worst case after union (all unique):  up to 40 candidates
  after merge + sort + take top-K:      exactly 10 returned

  Why this matters:
    Without inflation, a vehicle ranked #11 in content but #1
    in collaborative would never enter the union pool and
    would be silently excluded from the final result.
```

---

## Caching Strategy

```
  Priority 1 (fastest):
    Redis key: similarity:precomputed:{type}:{id}:v1
    TTL:       24 hours
    Written by: Celery pre-computation job (Phase 6)

  Priority 2 (on-demand):
    Redis key: similarity:{type}:{id}:v1
    TTL:       30 minutes (CACHE_TTL_ONDEMAND)
    Written by: this endpoint on first request

  Cache-aside pattern:
    ┌────────┐   check    ┌─────────────────────┐
    │ Client ├───────────►│ Precomputed cache   │ HIT → return
    └────────┘            └──────────┬──────────┘
                                     │ MISS
                          ┌──────────▼──────────┐
                          │ On-demand cache      │ HIT → return
                          └──────────┬──────────┘
                                     │ MISS
                          ┌──────────▼──────────┐
                          │ HybridRanker.compute │
                          │ → store on-demand    │
                          └─────────────────────┘
```

---

## API Endpoint

```
GET /api/ai/vehicles/similar

Query Parameters:
  vehicleId  integer   required   Source vehicle ID
  type       string    required   "car" or "motorcycle"
  limit      integer   optional   1-50, default 10

Response (full hybrid):
{
  "sourceVehicleId": 42,
  "vehicleType":     "car",
  "suggestions": [
    {
      "vehicleId": 18,
      "score":     0.692,
      "reason":    "same brand, similar price + 3 co-inquiries by similar clients",
      "details": {
        "make":  "Toyota",
        "model": "Camry",
        "year":  2022,
        "price": 485000.0
      }
    }
  ],
  "method": "hybrid",     ← "hybrid" | "content" | "collaborative"
  "cached": false
}
```

---

## Configuration

| Environment Variable       | Default | Description                              |
|----------------------------|---------|------------------------------------------|
| `CONTENT_BASED_WEIGHT`     | `0.6`   | Weight applied to content-based scores  |
| `COLLABORATIVE_WEIGHT`     | `0.4`   | Weight applied to collaborative scores  |
| `CACHE_TTL_ONDEMAND`       | `1800`  | On-demand result TTL in seconds (30min) |
| `CACHE_TTL_PRECOMPUTED`    | `86400` | Precomputed result TTL (24 hours)       |
| `ENABLE_COLLABORATIVE_FILTERING` | `true` | Disabling this forces content-only |

> Weights do **not** need to sum to 1.0 — the formula doesn't enforce normalization — but keeping them summed to 1.0 ensures hybrid scores stay in the `[0, 1]` range.

---

## Relationship to Other Engines

```
  ┌─────────────────────────────────────────────────────────────┐
  │                    Similarity Endpoints                      │
  │                                                             │
  │  /similar/content  ──────────────► ContentSimilarityService │
  │                                                             │
  │  /similar/collaborative ─────────► CollaborativeSimilarity  │
  │                     │               Service                 │
  │                     │   (fallback to content if cold start) │
  │                                                             │
  │  /similar  ──────────────────────► HybridRanker             │
  │                                     │                       │
  │                                     ├─► ContentSimilarity   │
  │                                     └─► Collaborative       │
  │                                         Similarity          │
  └─────────────────────────────────────────────────────────────┘
```

---

## Performance Profile

| Scenario                                      | Typical Latency |
|-----------------------------------------------|-----------------|
| Precomputed cache hit                         | < 10 ms         |
| On-demand cache hit                           | < 10 ms         |
| Full hybrid (both engines cold)               | 300–500 ms      |
| Content-only fallback (cold start)            | 200–300 ms      |
| After Phase 6 pre-computation (top 100 cars) | < 10 ms         |
