"""Lead scoring service — ranks inquiries by conversion likelihood"""
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.lead_models import Client, Reservation
from app.models.vehicle_models import Car, Inquiry, Motorcycle

logger = logging.getLogger(__name__)
settings = get_settings()

# ── Lookup tables ────────────────────────────────────────────────────────────

_INQUIRY_TYPE_POINTS: Dict[str, int] = {
    "TEST_DRIVE": 20,
    "PURCHASE_INQUIRY": 18,
    "PRICE_NEGOTIATION": 18,
    "FINANCING": 15,
    "VISIT": 12,
    "GENERAL_INFO": 5,
}

_RESERVATION_STATUS_POINTS: Dict[str, int] = {
    "ACTIVE": 15,
    "CONFIRMED": 15,
    "PENDING": 10,
    "EXPIRED": 6,
    "CANCELLED": 6,
}


# ── Result data classes ──────────────────────────────────────────────────────

@dataclass
class SignalBreakdown:
    purchasing_history: int
    inquiry_type: int
    reservation_status: int
    inquiry_frequency: int
    response_engagement: int
    vehicle_price_band: int


@dataclass
class LeadScoreResult:
    inquiry_id: int
    client_id: int
    score: int
    priority: str
    breakdown: SignalBreakdown
    scored_at: datetime


# ── Service ──────────────────────────────────────────────────────────────────

class LeadScoringService:
    """
    Scores inquiries on a 0–100 scale using a weighted sum of six signals.

    Thresholds (configurable via settings):
        Hot  ≥ ls_hot_threshold  (default 70)
        Warm ≥ ls_warm_threshold (default 40)
        Cold < ls_warm_threshold
    """

    def __init__(self, db: Session):
        self.db = db

    # ── Public API ────────────────────────────────────────────────────────────

    def score_inquiry(self, inquiry_id: int) -> Optional[LeadScoreResult]:
        """
        Score a single inquiry.

        Returns:
            LeadScoreResult, or None if the inquiry or its client is not found.
        """
        inquiry = self.db.query(Inquiry).filter(Inquiry.id == inquiry_id).first()
        if inquiry is None:
            logger.warning(f"Inquiry {inquiry_id} not found")
            return None

        client = self.db.query(Client).filter(Client.id == inquiry.client_id).first()
        if client is None:
            logger.warning(f"Client {inquiry.client_id} not found for inquiry {inquiry_id}")
            return None

        return self._compute(inquiry, client)

    def score_batch(
        self, inquiry_ids: List[int]
    ) -> Tuple[List[LeadScoreResult], List[int]]:
        """
        Score a list of inquiries efficiently (no N+1 queries for the main loads).

        Returns:
            (results, failed_ids)
            failed_ids — inquiry IDs that could not be scored (not found).
        """
        if not inquiry_ids:
            return [], []

        # Bulk load inquiries
        inquiries = (
            self.db.query(Inquiry)
            .filter(Inquiry.id.in_(inquiry_ids))
            .all()
        )
        inquiry_map: Dict[int, Inquiry] = {i.id: i for i in inquiries}
        failed_ids = [iid for iid in inquiry_ids if iid not in inquiry_map]

        if not inquiry_map:
            return [], failed_ids

        # Bulk load clients for found inquiries
        unique_client_ids = list({i.client_id for i in inquiry_map.values() if i.client_id})
        clients = (
            self.db.query(Client)
            .filter(Client.id.in_(unique_client_ids))
            .all()
        )
        client_map: Dict[int, Client] = {c.id: c for c in clients}

        results: List[LeadScoreResult] = []
        for iid, inquiry in inquiry_map.items():
            client = client_map.get(inquiry.client_id)
            if client is None:
                logger.warning(f"Client {inquiry.client_id} missing for inquiry {iid}")
                failed_ids.append(iid)
                continue
            results.append(self._compute(inquiry, client))

        return results, failed_ids

    # ── Core computation ──────────────────────────────────────────────────────

    def _compute(self, inquiry: Inquiry, client: Client) -> LeadScoreResult:
        vehicle_price = self._get_vehicle_price(inquiry)

        breakdown = SignalBreakdown(
            purchasing_history=self._signal_purchase_history(client),
            inquiry_type=self._signal_inquiry_type(inquiry),
            reservation_status=self._signal_reservation(inquiry.client_id),
            inquiry_frequency=self._signal_inquiry_frequency(inquiry.client_id),
            response_engagement=self._signal_response_engagement(inquiry),
            vehicle_price_band=self._signal_price_band(vehicle_price),
        )

        raw_total = (
            breakdown.purchasing_history
            + breakdown.inquiry_type
            + breakdown.reservation_status
            + breakdown.inquiry_frequency
            + breakdown.response_engagement
            + breakdown.vehicle_price_band
        )
        score = min(max(raw_total, 0), 100)

        return LeadScoreResult(
            inquiry_id=inquiry.id,
            client_id=inquiry.client_id,
            score=score,
            priority=self._label(score),
            breakdown=breakdown,
            scored_at=datetime.now(tz=timezone.utc),
        )

    # ── Signal calculators ────────────────────────────────────────────────────

    def _signal_purchase_history(self, client: Client) -> int:
        """
        Signal 1 — Prior purchase history (max 30 pts).
        Uses client.total_purchases maintained by the backend on each sale.
        """
        count = client.total_purchases or 0
        if count >= 3:
            return settings.ls_weight_purchase_history  # 30
        if count == 2:
            return 22
        if count == 1:
            return 15
        return 0

    def _signal_inquiry_type(self, inquiry: Inquiry) -> int:
        """
        Signal 2 — Inquiry type intent (max 20 pts).
        Maps inquiry_type string to a fixed point value.
        """
        return _INQUIRY_TYPE_POINTS.get(
            (inquiry.inquiry_type or "").upper(), 3
        )

    def _signal_reservation(self, client_id: int) -> int:
        """
        Signal 3 — Reservation status (max 15 pts).
        Takes the highest points from all reservations the client has ever had.
        """
        rows = (
            self.db.query(Reservation.status)
            .filter(Reservation.client_id == client_id)
            .all()
        )
        if not rows:
            return 0
        best = 0
        for (status,) in rows:
            pts = _RESERVATION_STATUS_POINTS.get((status or "").upper(), 0)
            if pts > best:
                best = pts
        return best

    def _signal_inquiry_frequency(self, client_id: int) -> int:
        """
        Signal 4 — Recent inquiry frequency (max 15 pts).
        Counts all inquiries the client made in the trailing window.
        """
        window_start = datetime.now(tz=timezone.utc) - timedelta(
            days=settings.ls_frequency_window_days
        )
        count = (
            self.db.query(func.count(Inquiry.id))
            .filter(
                Inquiry.client_id == client_id,
                Inquiry.created_at >= window_start,
            )
            .scalar()
        ) or 0

        if count >= 5:
            return settings.ls_weight_inquiry_frequency  # 15
        if count >= 3:
            return 10
        if count == 2:
            return 6
        return 3  # at least 1 (the current inquiry counts)

    def _signal_response_engagement(self, inquiry: Inquiry) -> int:
        """
        Signal 5 — Staff response engagement (max 10 pts).
        Combines inquiry status flag (+5) and first-response latency (+5 / +3 / 0).
        """
        pts = 0
        status = (inquiry.status or "").upper()
        if status in ("RESPONDED", "IN_PROGRESS"):
            pts += 5

        if inquiry.response_date and inquiry.created_at:
            response_dt = inquiry.response_date
            created_dt = inquiry.created_at
            # Normalise to naive for arithmetic (MySQL timestamps are naive)
            if getattr(response_dt, "tzinfo", None):
                response_dt = response_dt.replace(tzinfo=None)
            if getattr(created_dt, "tzinfo", None):
                created_dt = created_dt.replace(tzinfo=None)
            hours_elapsed = (response_dt - created_dt).total_seconds() / 3600
            if 0 <= hours_elapsed < 2:
                pts += 5
            elif hours_elapsed < 24:
                pts += 3

        return min(pts, 10)

    def _signal_price_band(self, selling_price: Optional[float]) -> int:
        """
        Signal 6 — Vehicle price band (max 10 pts).
        Premium vehicles attract deliberate, high-intent buyers.
        Prices are in INR.
        """
        if selling_price is None:
            return 2
        price = float(selling_price)
        if price > 1_500_000:
            return settings.ls_weight_price_band  # 10
        if price >= 800_000:
            return 7
        if price >= 400_000:
            return 5
        return 3

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_vehicle_price(self, inquiry: Inquiry) -> Optional[float]:
        """Return selling_price of the vehicle linked to the inquiry, or None."""
        vtype = (inquiry.vehicle_type or "").upper()
        if vtype == "CAR" and inquiry.car_id:
            row = (
                self.db.query(Car.selling_price)
                .filter(Car.id == inquiry.car_id)
                .first()
            )
            return float(row[0]) if row and row[0] is not None else None
        if vtype == "MOTORCYCLE" and inquiry.motorcycle_id:
            row = (
                self.db.query(Motorcycle.selling_price)
                .filter(Motorcycle.id == inquiry.motorcycle_id)
                .first()
            )
            return float(row[0]) if row and row[0] is not None else None
        return None

    @staticmethod
    def _label(score: int) -> str:
        if score >= settings.ls_hot_threshold:
            return "Hot"
        if score >= settings.ls_warm_threshold:
            return "Warm"
        return "Cold"
