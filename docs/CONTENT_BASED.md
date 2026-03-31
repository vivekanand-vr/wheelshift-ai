# Content-Based Similarity Engine

Recommends vehicles by comparing their attributes. No historical user data required — works on day one with zero inquiries.

**Source:** `app/services/content_similarity.py`, `app/services/feature_engineering.py`

---

## How It Works

```
 API Request
     │
     ▼
┌────────────────────────────────────────────────┐
│  ContentSimilarityService.find_similar_cars()  │
└────────────────────────────┬───────────────────┘
                             │
             ┌───────────────▼───────────────┐
             │   1. Extract source features   │
             │      (DB + Redis cache)         │
             └───────────────┬───────────────┘
                             │
             ┌───────────────▼───────────────┐
             │   2. Price band filter ±15%    │
             │      Query candidate vehicles   │
             │      (max 500 candidates)       │
             └───────────────┬───────────────┘
                             │
             ┌───────────────▼───────────────┐
             │   3. For each candidate:       │
             │      - Extract features        │
             │      - Build feature vector    │
             │      - Cosine similarity       │
             └───────────────┬───────────────┘
                             │
             ┌───────────────▼───────────────┐
             │   4. Sort by score desc        │
             │      Return top-K results      │
             └───────────────┬───────────────┘
                             │
             ┌───────────────▼───────────────┐
             │   5. Generate reasons          │
             │   6. Cache result (30min TTL)  │
             └───────────────────────────────┘
```

---

## Feature Engineering Pipeline

### Step 1 — Raw Value Extraction

```
      cars / car_models tables
              │
    ┌─────────▼─────────┐
    │   Raw Extraction   │
    │                   │
    │  price            │  ─── selling_price (Numeric)
    │  year             │  ─── year (Integer)
    │  mileage_km       │  ─── mileage_km (Integer)
    │  engine_cc        │  ─── engine_cc (Integer)
    │  make             │  ─── car_models.make
    │  model            │  ─── car_models.model
    │  fuel_type        │  ─── car_models.fuel_type
    │  transmission     │  ─── car_models.transmission_type
    │  body_type        │  ─── car_models.body_type
    └───────────────────┘
```

### Step 2 — Normalization

```
  NUMERICAL FEATURES
  ──────────────────────────────────────────────────────────────
  price       Min-Max     0 ─────────────────────────── 50 000 000
                          │  price / 50_000_000 → [0, 1]  │

  year        Linear      1980 ──────────────────────────── 2026
                          │  (year - 1980) / 46 → [0, 1]  │

  mileage_km  Min-Max     0 ──────────────────────────── 500 000 km
                          │  mileage / 500_000 → [0, 1]   │

  engine_cc   Min-Max     0 ─────────────────────────────── 6 000 cc
                          │  cc / 6_000 → [0, 1]           │

  CATEGORICAL FEATURES
  ──────────────────────────────────────────────────────────────
  fuel_type   Label       PETROL=0  DIESEL=1  ELECTRIC=2
                          HYBRID=3  CNG=4     LPG=5
                          → divided by 5 to reach [0, 1]

  transmission Label      MANUAL=0  AUTOMATIC=1  AMT=2
                          CVT=3     DCT=4
                          → divided by 4 to reach [0, 1]

  body_type   Label       SEDAN=0   SUV=1    HATCHBACK=2   COUPE=3
  (car)                   CONVERT=4 WAGON=5  VAN=6         TRUCK=7
                          → divided by 8 to reach [0, 1]

  vehicle_type Label      MOTORCYCLE=0  SCOOTER=1  SPORT_BIKE=2
  (motorcycle)            CRUISER=3     OFF_ROAD=4  TOURING=5
                          NAKED=6  CAFE_RACER=7  DIRT_BIKE=8  MOPED=9
                          → divided by 10 to reach [0, 1]
```

### Step 3 — Weighted Feature Vector

Each dimension is scaled by a configurable weight before cosine similarity is computed.

```
  Index  Feature           Weight    Formula
  ─────────────────────────────────────────────────────────────────
    0    price             0.25      norm_price  × 0.25
    1    year              0.15      norm_year   × 0.15
    2    mileage           0.10      norm_mileage × 0.10
    3    fuel_type         0.10      norm_fuel   × 0.10
    4    transmission*     0.20      norm_trans  × 0.20
    5    body/vehicle type 0.15      norm_type   × 0.15
  ─────────────────────────────────────────────────────────────────
  * transmission is currently used as a brand proxy

  Resulting vector: [w0, w1, w2, w3, w4, w5]
                     ▲
                     used for cosine similarity
```

> Weights are fully configurable via environment variables: `WEIGHT_PRICE`, `WEIGHT_BRAND`, etc.

---

## Cosine Similarity

```
  Source vector:    A = [a0, a1, a2, a3, a4, a5]
  Candidate vector: B = [b0, b1, b2, b3, b4, b5]

                    A · B
  similarity(A, B) = ──────────────
                    ‖A‖ × ‖B‖

  Score range: [0.0, 1.0]
  1.0 = identical feature vectors
  0.0 = completely orthogonal (maximum dissimilarity)
```

---

## Price Band Filter

Before computing any similarity, candidates outside the ±15% price window are discarded. This prevents a £5k car from ever ranking highly against a £50k car regardless of other matching attributes.

```
  Source price: P

  ┌─────────────────────────────────────────────────┐
  │                                                 │
  │  P × 0.85 ◄──────── ±15% band ────────► P × 1.15  │
  │                                                 │
  │          All candidates inside band             │
  │          are scored via cosine similarity       │
  │                                                 │
  │          Candidates outside band → discarded    │
  │                                                 │
  └─────────────────────────────────────────────────┘

  Configurable via: PRICE_BAND_PERCENTAGE (default: 0.15)
  Disabled automatically if source vehicle has no price (price = 0)
```

---

## Similarity Reason Generation

After scoring, each result gets a plain-English explanation:

```
  Condition                                Reason label
  ─────────────────────────────────────────────────────────────────
  source.make == candidate.make            "same brand"
  |price_diff| / source_price < 5%        "similar price"
  |price_diff| / source_price < 10%       "nearby price"
  source.body_type == candidate.body_type  "same {body_type} type"
  |year_diff| <= 1                         "same model year"
  |year_diff| <= 3                         "recent model"
  source.fuel_type == candidate.fuel_type  "{fuel_type} fuel"
  score > 0.8 (no other reasons matched)  "matching features"
  score <= 0.8 (no other reasons matched) "similar segment"
```

Multiple conditions can match, producing combined reasons like:
> `"same brand, similar price, same sedan type"`

---

## Caching Strategy

```
  Request
     │
     ├── HIT ──► Redis key: similarity:car:{id}:v1
     │                       TTL: 30 min (CACHE_TTL_ONDEMAND)
     │                       Return cached response immediately
     │
     └── MISS ─► Compute similarity
                     │
                     ├── Feature vectors cached separately
                     │   Key: features:car:{id}:v1
                     │   TTL: 1 hour (FEATURE_VECTOR_CACHE_TTL)
                     │   Reused across multiple similarity calls
                     │
                     └── Final result cached
                         Key: similarity:car:{id}:v1
                         TTL: 30 min
```

---

## API Endpoint

```
GET /api/ai/vehicles/similar/content

Query Parameters:
  vehicleId  integer   required   Source vehicle ID
  type       string    required   "car" or "motorcycle"
  limit      integer   optional   1-50, default 10

Response:
{
  "sourceVehicleId": 42,
  "vehicleType":     "car",
  "suggestions": [
    {
      "vehicleId": 18,
      "score":     0.94,
      "reason":    "same brand, similar price, same sedan type",
      "details": {
        "make":  "Toyota",
        "model": "Camry",
        "year":  2022,
        "price": 485000.0
      }
    }
  ],
  "method": "content",
  "cached": false
}
```

---

## Status Filtering

Vehicles with status `SOLD` are excluded from all results by default. This prevents suggesting vehicles the client cannot purchase. The `exclude_statuses` parameter allows callers to customise this behaviour (e.g., include `MAINTENANCE` vehicles in internal tools).

---

## Performance Profile

| Path                       | Typical Latency |
|----------------------------|-----------------|
| Redis cache hit            | < 10 ms         |
| Feature vector cache hit   | ~50–100 ms      |
| Full computation (no cache)| 200–300 ms      |
| Candidate pool limit       | 500 vehicles    |
