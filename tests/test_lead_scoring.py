"""Unit tests for the lead scoring service"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.services.lead_scoring import (
    LeadScoringService,
    SignalBreakdown,
    _INQUIRY_TYPE_POINTS,
    _RESERVATION_STATUS_POINTS,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────


def _make_client(purchase_count: int = 0):
    client = MagicMock()
    client.id = 1
    client.total_purchases = purchase_count  # matches actual DB column name
    return client


def _make_inquiry(
    inquiry_id: int = 10,
    client_id: int = 1,
    inquiry_type: str = "GENERAL_INFO",
    status: str = "OPEN",
    vehicle_type: str = "CAR",
    car_id: int = 5,
    motorcycle_id=None,
    created_at=None,
    response_date=None,
):
    inq = MagicMock()
    inq.id = inquiry_id
    inq.client_id = client_id
    inq.inquiry_type = inquiry_type
    inq.status = status
    inq.vehicle_type = vehicle_type
    inq.car_id = car_id
    inq.motorcycle_id = motorcycle_id
    inq.created_at = created_at or datetime(2026, 1, 1, 10, 0, 0)
    inq.response_date = response_date
    return inq


def _make_service(db=None):
    if db is None:
        db = MagicMock()
    return LeadScoringService(db)


# ── Signal 1: Purchase history ────────────────────────────────────────────────


def test_signal_purchase_history_zero():
    svc = _make_service()
    assert svc._signal_purchase_history(_make_client(0)) == 0


def test_signal_purchase_history_one():
    svc = _make_service()
    assert svc._signal_purchase_history(_make_client(1)) == 15


def test_signal_purchase_history_two():
    svc = _make_service()
    assert svc._signal_purchase_history(_make_client(2)) == 22


def test_signal_purchase_history_three_or_more():
    svc = _make_service()
    assert svc._signal_purchase_history(_make_client(3)) == 30
    assert svc._signal_purchase_history(_make_client(10)) == 30


def test_signal_purchase_history_none_treated_as_zero():
    client = _make_client(0)
    client.total_purchases = None
    svc = _make_service()
    assert svc._signal_purchase_history(client) == 0


# ── Signal 2: Inquiry type ────────────────────────────────────────────────────


def test_signal_inquiry_type_test_drive():
    svc = _make_service()
    assert svc._signal_inquiry_type(_make_inquiry(inquiry_type="TEST_DRIVE")) == 20


def test_signal_inquiry_type_purchase_inquiry():
    svc = _make_service()
    assert svc._signal_inquiry_type(_make_inquiry(inquiry_type="PURCHASE_INQUIRY")) == 18


def test_signal_inquiry_type_price_negotiation():
    svc = _make_service()
    assert svc._signal_inquiry_type(_make_inquiry(inquiry_type="PRICE_NEGOTIATION")) == 18


def test_signal_inquiry_type_financing():
    svc = _make_service()
    assert svc._signal_inquiry_type(_make_inquiry(inquiry_type="FINANCING")) == 15


def test_signal_inquiry_type_visit():
    svc = _make_service()
    assert svc._signal_inquiry_type(_make_inquiry(inquiry_type="VISIT")) == 12


def test_signal_inquiry_type_general_info():
    svc = _make_service()
    assert svc._signal_inquiry_type(_make_inquiry(inquiry_type="GENERAL_INFO")) == 5


def test_signal_inquiry_type_unknown_falls_back_to_minimum():
    svc = _make_service()
    assert svc._signal_inquiry_type(_make_inquiry(inquiry_type="SOMETHING_RANDOM")) == 3


def test_signal_inquiry_type_none_falls_back_to_minimum():
    svc = _make_service()
    assert svc._signal_inquiry_type(_make_inquiry(inquiry_type=None)) == 3


def test_signal_inquiry_type_case_insensitive():
    svc = _make_service()
    assert svc._signal_inquiry_type(_make_inquiry(inquiry_type="test_drive")) == 20


# ── Signal 3: Reservation status ─────────────────────────────────────────────


def _db_with_reservations(statuses):
    db = MagicMock()
    query_mock = db.query.return_value
    filter_mock = query_mock.filter.return_value
    filter_mock.all.return_value = [(s,) for s in statuses]
    return db


def test_signal_reservation_confirmed():
    db = _db_with_reservations(["CONFIRMED"])
    svc = _make_service(db)
    assert svc._signal_reservation(client_id=1) == 15


def test_signal_reservation_active():
    db = _db_with_reservations(["ACTIVE"])
    svc = _make_service(db)
    assert svc._signal_reservation(client_id=1) == 15


def test_signal_reservation_pending():
    db = _db_with_reservations(["PENDING"])
    svc = _make_service(db)
    assert svc._signal_reservation(client_id=1) == 10


def test_signal_reservation_expired():
    db = _db_with_reservations(["EXPIRED"])
    svc = _make_service(db)
    assert svc._signal_reservation(client_id=1) == 6


def test_signal_reservation_cancelled():
    db = _db_with_reservations(["CANCELLED"])
    svc = _make_service(db)
    assert svc._signal_reservation(client_id=1) == 6


def test_signal_reservation_no_history():
    db = _db_with_reservations([])
    svc = _make_service(db)
    assert svc._signal_reservation(client_id=1) == 0


def test_signal_reservation_picks_highest_status():
    """When a client has multiple reservations, the best score wins."""
    db = _db_with_reservations(["EXPIRED", "CONFIRMED", "CANCELLED"])
    svc = _make_service(db)
    assert svc._signal_reservation(client_id=1) == 15


# ── Signal 4: Inquiry frequency ───────────────────────────────────────────────


def _db_with_inquiry_count(count: int):
    db = MagicMock()
    query_mock = db.query.return_value
    filter_mock = query_mock.filter.return_value
    filter_mock.scalar.return_value = count
    return db


def test_signal_inquiry_frequency_five_or_more():
    svc = _make_service(_db_with_inquiry_count(5))
    assert svc._signal_inquiry_frequency(client_id=1) == 15


def test_signal_inquiry_frequency_six():
    svc = _make_service(_db_with_inquiry_count(6))
    assert svc._signal_inquiry_frequency(client_id=1) == 15


def test_signal_inquiry_frequency_four():
    svc = _make_service(_db_with_inquiry_count(4))
    assert svc._signal_inquiry_frequency(client_id=1) == 10


def test_signal_inquiry_frequency_three():
    svc = _make_service(_db_with_inquiry_count(3))
    assert svc._signal_inquiry_frequency(client_id=1) == 10


def test_signal_inquiry_frequency_two():
    svc = _make_service(_db_with_inquiry_count(2))
    assert svc._signal_inquiry_frequency(client_id=1) == 6


def test_signal_inquiry_frequency_one():
    svc = _make_service(_db_with_inquiry_count(1))
    assert svc._signal_inquiry_frequency(client_id=1) == 3


def test_signal_inquiry_frequency_zero_treated_as_one():
    svc = _make_service(_db_with_inquiry_count(0))
    assert svc._signal_inquiry_frequency(client_id=1) == 3


# ── Signal 5: Response engagement ────────────────────────────────────────────


def test_signal_response_engagement_responded_and_fast():
    now = datetime(2026, 1, 1, 10, 0, 0)
    inq = _make_inquiry(
        status="RESPONDED",
        created_at=now,
        response_date=now + timedelta(hours=1),
    )
    svc = _make_service()
    assert svc._signal_response_engagement(inq) == 10


def test_signal_response_engagement_responded_and_medium():
    now = datetime(2026, 1, 1, 10, 0, 0)
    inq = _make_inquiry(
        status="RESPONDED",
        created_at=now,
        response_date=now + timedelta(hours=12),
    )
    svc = _make_service()
    assert svc._signal_response_engagement(inq) == 8  # 5 (status) + 3 (2-24h)


def test_signal_response_engagement_responded_slow():
    now = datetime(2026, 1, 1, 10, 0, 0)
    inq = _make_inquiry(
        status="RESPONDED",
        created_at=now,
        response_date=now + timedelta(hours=30),
    )
    svc = _make_service()
    assert svc._signal_response_engagement(inq) == 5  # 5 (status) + 0 (>24h)


def test_signal_response_engagement_in_progress_no_response():
    inq = _make_inquiry(status="IN_PROGRESS", response_date=None)
    svc = _make_service()
    assert svc._signal_response_engagement(inq) == 5  # status only


def test_signal_response_engagement_open_no_response():
    inq = _make_inquiry(status="OPEN", response_date=None)
    svc = _make_service()
    assert svc._signal_response_engagement(inq) == 0


def test_signal_response_engagement_capped_at_ten():
    """Sanity: score never exceeds 10."""
    now = datetime(2026, 1, 1, 10, 0, 0)
    inq = _make_inquiry(
        status="RESPONDED",
        created_at=now,
        response_date=now + timedelta(minutes=30),
    )
    svc = _make_service()
    assert svc._signal_response_engagement(inq) <= 10


# ── Signal 6: Vehicle price band ─────────────────────────────────────────────


def test_signal_price_band_premium():
    svc = _make_service()
    assert svc._signal_price_band(2_000_000) == 10


def test_signal_price_band_upper_mid():
    svc = _make_service()
    assert svc._signal_price_band(1_200_000) == 7


def test_signal_price_band_mid():
    svc = _make_service()
    assert svc._signal_price_band(600_000) == 5


def test_signal_price_band_budget():
    svc = _make_service()
    assert svc._signal_price_band(300_000) == 3


def test_signal_price_band_none():
    svc = _make_service()
    assert svc._signal_price_band(None) == 2


def test_signal_price_band_exact_boundary_800k():
    svc = _make_service()
    assert svc._signal_price_band(800_000) == 7


def test_signal_price_band_exact_boundary_400k():
    svc = _make_service()
    assert svc._signal_price_band(400_000) == 5


# ── Label computation ─────────────────────────────────────────────────────────


def test_label_hot():
    assert LeadScoringService._label(70) == "Hot"
    assert LeadScoringService._label(100) == "Hot"
    assert LeadScoringService._label(85) == "Hot"


def test_label_warm():
    assert LeadScoringService._label(40) == "Warm"
    assert LeadScoringService._label(69) == "Warm"


def test_label_cold():
    assert LeadScoringService._label(0) == "Cold"
    assert LeadScoringService._label(39) == "Cold"


def test_label_boundary_hot_warm():
    assert LeadScoringService._label(70) == "Hot"
    assert LeadScoringService._label(69) == "Warm"


def test_label_boundary_warm_cold():
    assert LeadScoringService._label(40) == "Warm"
    assert LeadScoringService._label(39) == "Cold"


# ── score_inquiry integration tests (mock DB) ─────────────────────────────────


def _build_db_for_full_score(
    inquiry,
    client,
    reservation_statuses=None,
    recent_inquiry_count=1,
    car_selling_price=None,
):
    """Build a mock DB that returns consistent data for all service queries."""
    db = MagicMock()

    def query_side_effect(model):
        from app.models.vehicle_models import Car, Inquiry, Motorcycle
        from app.models.lead_models import Client, Reservation

        mock_q = MagicMock()
        if model is Inquiry:
            filter_mock = MagicMock()
            filter_mock.first.return_value = inquiry
            # frequency count path
            filter_mock2 = MagicMock()
            filter_mock2.scalar.return_value = recent_inquiry_count
            mock_q.filter.side_effect = [filter_mock, filter_mock2]
        elif model is Client:
            filter_mock = MagicMock()
            filter_mock.first.return_value = client
            mock_q.filter.return_value = filter_mock
        elif model is Reservation:
            rows = [(s,) for s in (reservation_statuses or [])]
            filter_mock = MagicMock()
            filter_mock.all.return_value = rows
            mock_q.filter.return_value = filter_mock
        elif model is Car:
            row = (car_selling_price,) if car_selling_price is not None else None
            filter_mock = MagicMock()
            filter_mock.first.return_value = row
            mock_q.filter.return_value = filter_mock
        elif model is Motorcycle:
            filter_mock = MagicMock()
            filter_mock.first.return_value = None
            mock_q.filter.return_value = filter_mock
        else:
            mock_q.filter.return_value = MagicMock()
        return mock_q

    db.query.side_effect = query_side_effect
    return db


def test_score_inquiry_not_found_returns_none():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    svc = _make_service(db)
    assert svc.score_inquiry(999) is None


def test_score_inquiry_score_is_within_bounds():
    """
    Full end-to-end score_inquiry call (signals patched individually so the
    test does not have to replicate SQLAlchemy query dispatch internals).
    Max possible score is 100; result must honour that contract.
    """
    inq = _make_inquiry(
        inquiry_type="TEST_DRIVE",
        status="RESPONDED",
        created_at=datetime(2026, 1, 1, 10, 0),
        response_date=datetime(2026, 1, 1, 10, 30),
        vehicle_type="CAR",
        car_id=5,
    )
    client = _make_client(purchase_count=3)

    db = MagicMock()
    # score_inquiry fetches inquiry then client via .filter().first()
    db.query.return_value.filter.return_value.first.side_effect = [inq, client]

    svc = _make_service(db)

    # Patch all DB-dependent signals so the test is self-contained
    with (
        patch.object(svc, "_signal_reservation", return_value=15),
        patch.object(svc, "_signal_inquiry_frequency", return_value=15),
        patch.object(svc, "_get_vehicle_price", return_value=2_000_000),
    ):
        result = svc.score_inquiry(inq.id)

    assert result is not None
    assert 0 <= result.score <= 100
    assert result.priority in ("Hot", "Warm", "Cold")
    # With all signals at max this should be Hot
    assert result.priority == "Hot"


def test_score_batch_empty_returns_empty():
    svc = _make_service()
    results, failed = svc.score_batch([])
    assert results == []
    assert failed == []


def test_score_batch_missing_ids_tracked():
    db = MagicMock()
    # Return empty list from bulk inquiry query
    db.query.return_value.filter.return_value.all.return_value = []
    svc = _make_service(db)
    results, failed = svc.score_batch([101, 102])
    assert results == []
    assert set(failed) == {101, 102}
