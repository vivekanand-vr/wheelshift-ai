# Lead Scoring

Ranks open inquiries by conversion likelihood so sales staff can prioritise the hottest leads.

---

## Scoring Model

A **weighted sum** of six signals produces an integer score in `[0, 100]`.

| # | Signal | Max pts | Source columns |
|---|--------|---------|----------------|
| 1 | Prior purchase history | 30 | `clients.total_purchases` |
| 2 | Inquiry type intent | 20 | `inquiries.inquiry_type` |
| 3 | Reservation status | 15 | `reservations.status` |
| 4 | Recent inquiry frequency | 15 | `inquiries.created_at` (90-day window) |
| 5 | Staff response engagement | 10 | `inquiries.status`, `inquiries.response_date` |
| 6 | Vehicle price band | 10 | `cars.selling_price` / `motorcycles.selling_price` |

### Priority labels

| Label | Range |
|-------|-------|
| **Hot** | ≥ 70 |
| **Warm** | 40 – 69 |
| **Cold** | < 40 |

---

## Signal Details

### 1 — Purchase History (30 pts)

| `total_purchases` | Points |
|-------------------|--------|
| 0 | 0 |
| 1 | 15 |
| 2 | 22 |
| ≥ 3 | 30 |

### 2 — Inquiry Type (20 pts)

| `inquiry_type` | Points |
|---------------|--------|
| `TEST_DRIVE` | 20 |
| `PURCHASE_INQUIRY` | 18 |
| `PRICE_NEGOTIATION` | 18 |
| `FINANCING` | 15 |
| `VISIT` | 12 |
| `GENERAL_INFO` | 5 |
| anything else / null | 3 |

### 3 — Reservation Status (15 pts)

Checks all reservations ever linked to the client and takes the highest-point status.

| Best status found | Points |
|-------------------|--------|
| `ACTIVE` / `CONFIRMED` | 15 |
| `PENDING` | 10 |
| `EXPIRED` / `CANCELLED` | 6 |
| none | 0 |

### 4 — Inquiry Frequency (15 pts)

Count of the client's inquiries in the last 90 days (window configurable via `LS_FREQUENCY_WINDOW_DAYS`).

| Count | Points |
|-------|--------|
| ≥ 5 | 15 |
| 3 – 4 | 10 |
| 2 | 6 |
| ≤ 1 | 3 |

### 5 — Response Engagement (10 pts, additive)

| Condition | Points |
|-----------|--------|
| `status` is `RESPONDED` or `IN_PROGRESS` | +5 |
| Response latency < 2 h | +5 |
| Response latency 2 – 24 h | +3 |
| No response / > 24 h | +0 |

### 6 — Vehicle Price Band (10 pts)

Based on the `selling_price` (INR) of the car or motorcycle on the inquiry.

| Price | Points |
|-------|--------|
| > ₹15,00,000 | 10 |
| ₹8,00,000 – ₹15,00,000 | 7 |
| ₹4,00,000 – ₹8,00,000 | 5 |
| < ₹4,00,000 | 3 |
| No vehicle / price unknown | 2 |

---

## Caching

Results are cached in Redis DB 1 with a **15-minute TTL**.

```
Key:  lead_score:inquiry:{id}:v1
TTL:  900 s (configurable via CACHE_TTL_LEAD_SCORE)
```

The short TTL keeps scores fresh as inquiry status changes. No active invalidation is required for MVP.

---

## Configuration

All signal weights and thresholds are tunable via environment variables (defaults in `.env.example`).

| Variable | Default | Description |
|----------|---------|-------------|
| `LS_WEIGHT_PURCHASE_HISTORY` | 30 | Max pts for signal 1 |
| `LS_WEIGHT_INQUIRY_TYPE` | 20 | Max pts for signal 2 |
| `LS_WEIGHT_RESERVATION` | 15 | Max pts for signal 3 |
| `LS_WEIGHT_INQUIRY_FREQUENCY` | 15 | Max pts for signal 4 |
| `LS_WEIGHT_RESPONSE_ENGAGE` | 10 | Max pts for signal 5 |
| `LS_WEIGHT_PRICE_BAND` | 10 | Max pts for signal 6 |
| `LS_HOT_THRESHOLD` | 70 | Minimum score for Hot |
| `LS_WARM_THRESHOLD` | 40 | Minimum score for Warm |
| `LS_FREQUENCY_WINDOW_DAYS` | 90 | Lookback window for signal 4 |
| `CACHE_TTL_LEAD_SCORE` | 900 | Redis TTL in seconds |

---

## Source files

| File | Role |
|------|------|
| `app/models/lead_models.py` | Read-only SQLAlchemy models: `Client`, `Sale`, `Reservation` |
| `app/services/lead_scoring.py` | `LeadScoringService` — all six signal methods + batch loader |
| `app/api/v1/lead_scoring.py` | FastAPI router: `POST /api/ai/leads/score` and `/batch` |
| `app/schemas/responses.py` | `LeadScoreSchema`, `SignalBreakdownSchema`, `LeadScoreBatchResponseSchema` |
| `app/utils/cache.py` | `get/set/invalidate_lead_score` helpers |
| `tests/test_lead_scoring.py` | 50 unit tests (all signals + label boundaries + batch edge cases) |
