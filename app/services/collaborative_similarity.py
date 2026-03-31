"""Collaborative filtering similarity engine (item-item, inquiry-based)"""
import logging
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.vehicle_models import Car, CarModel, Inquiry, Motorcycle, MotorcycleModel

logger = logging.getLogger(__name__)
settings = get_settings()


class CollaborativeSimilarityService:
    """
    Item-item collaborative filtering based on client inquiry history.

    Logic: "Clients who inquired about vehicle X also inquired about vehicle Y."
    Scores use a Jaccard-like normalization to avoid popularity bias:
        score(X, Y) = co_inquiries / (clients_of_X + total_inquiries_of_Y - co_inquiries)
    """

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def find_similar_cars(
        self,
        car_id: int,
        limit: int = 10,
        exclude_statuses: Optional[List[str]] = None,
    ) -> List[Dict]:
        """
        Find similar cars via item-item collaborative filtering.

        Returns:
            List of similar cars with normalized scores and reasons,
            or empty list when insufficient interaction data exists.
        """
        if exclude_statuses is None:
            exclude_statuses = ["SOLD"]

        if not self._has_sufficient_data("car"):
            logger.info("Insufficient car interaction data for collaborative filtering")
            return []

        # Clients who inquired about the source car
        client_ids = self._get_clients_for_car(car_id)
        if not client_ids:
            logger.info(f"No clients found who inquired about car {car_id}")
            return []

        # Other cars those same clients inquired about
        co_inquired = self._get_co_inquired_cars(car_id, client_ids)
        if not co_inquired:
            logger.info(f"No co-inquired cars found for car {car_id}")
            return []

        scored = self._compute_scores(co_inquired, len(client_ids), "car")
        return self._build_car_results(scored, limit, exclude_statuses)

    def find_similar_motorcycles(
        self,
        motorcycle_id: int,
        limit: int = 10,
        exclude_statuses: Optional[List[str]] = None,
    ) -> List[Dict]:
        """
        Find similar motorcycles via item-item collaborative filtering.

        Returns:
            List of similar motorcycles with normalized scores and reasons,
            or empty list when insufficient interaction data exists.
        """
        if exclude_statuses is None:
            exclude_statuses = ["SOLD"]

        if not self._has_sufficient_data("motorcycle"):
            logger.info("Insufficient motorcycle interaction data for collaborative filtering")
            return []

        client_ids = self._get_clients_for_motorcycle(motorcycle_id)
        if not client_ids:
            logger.info(f"No clients found who inquired about motorcycle {motorcycle_id}")
            return []

        co_inquired = self._get_co_inquired_motorcycles(motorcycle_id, client_ids)
        if not co_inquired:
            logger.info(f"No co-inquired motorcycles found for motorcycle {motorcycle_id}")
            return []

        scored = self._compute_scores(co_inquired, len(client_ids), "motorcycle")
        return self._build_motorcycle_results(scored, limit, exclude_statuses)

    # ------------------------------------------------------------------
    # Threshold check
    # ------------------------------------------------------------------

    def _has_sufficient_data(self, vehicle_type: str) -> bool:
        """Return True only if interaction data meets minimum thresholds."""
        if not settings.enable_collaborative_filtering:
            return False

        if vehicle_type == "car":
            total = (
                self.db.query(func.count(Inquiry.id))
                .filter(Inquiry.car_id.isnot(None))
                .scalar()
            ) or 0
            unique_clients = (
                self.db.query(func.count(Inquiry.client_id.distinct()))
                .filter(Inquiry.car_id.isnot(None))
                .scalar()
            ) or 0
        else:
            total = (
                self.db.query(func.count(Inquiry.id))
                .filter(Inquiry.motorcycle_id.isnot(None))
                .scalar()
            ) or 0
            unique_clients = (
                self.db.query(func.count(Inquiry.client_id.distinct()))
                .filter(Inquiry.motorcycle_id.isnot(None))
                .scalar()
            ) or 0

        has_enough = (
            total >= settings.min_interactions_threshold
            and unique_clients >= settings.min_clients_threshold
        )
        if not has_enough:
            logger.debug(
                f"Insufficient {vehicle_type} data: {total} interactions across "
                f"{unique_clients} clients (need {settings.min_interactions_threshold}+ "
                f"interactions, {settings.min_clients_threshold}+ clients)"
            )
        return has_enough

    # ------------------------------------------------------------------
    # Data retrieval helpers
    # ------------------------------------------------------------------

    def _get_clients_for_car(self, car_id: int) -> List[int]:
        rows = (
            self.db.query(Inquiry.client_id)
            .filter(Inquiry.car_id == car_id)
            .distinct()
            .all()
        )
        return [r[0] for r in rows]

    def _get_clients_for_motorcycle(self, motorcycle_id: int) -> List[int]:
        rows = (
            self.db.query(Inquiry.client_id)
            .filter(Inquiry.motorcycle_id == motorcycle_id)
            .distinct()
            .all()
        )
        return [r[0] for r in rows]

    def _get_co_inquired_cars(
        self, car_id: int, client_ids: List[int]
    ) -> List[Tuple[int, int]]:
        """Return [(other_car_id, co_inquiry_count)] for clients who also viewed car_id."""
        rows = (
            self.db.query(
                Inquiry.car_id,
                func.count(Inquiry.client_id.distinct()).label("co_views"),
            )
            .filter(
                Inquiry.client_id.in_(client_ids),
                Inquiry.car_id != car_id,
                Inquiry.car_id.isnot(None),
            )
            .group_by(Inquiry.car_id)
            .all()
        )
        return [(r[0], r[1]) for r in rows]

    def _get_co_inquired_motorcycles(
        self, motorcycle_id: int, client_ids: List[int]
    ) -> List[Tuple[int, int]]:
        """Return [(other_motorcycle_id, co_inquiry_count)]."""
        rows = (
            self.db.query(
                Inquiry.motorcycle_id,
                func.count(Inquiry.client_id.distinct()).label("co_views"),
            )
            .filter(
                Inquiry.client_id.in_(client_ids),
                Inquiry.motorcycle_id != motorcycle_id,
                Inquiry.motorcycle_id.isnot(None),
            )
            .group_by(Inquiry.motorcycle_id)
            .all()
        )
        return [(r[0], r[1]) for r in rows]

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _compute_scores(
        self,
        co_inquired: List[Tuple[int, int]],
        n_source_clients: int,
        vehicle_type: str,
    ) -> List[Tuple[int, float, int]]:
        """
        Compute Jaccard-like normalized scores for co-inquired vehicles.

        score = co_views / (n_source_clients + total_views_of_candidate - co_views)

        Returns list of (vehicle_id, score, co_views) sorted descending by score.
        """
        vehicle_ids = [vid for vid, _ in co_inquired]

        # Total inquiry counts per candidate vehicle for normalization
        if vehicle_type == "car":
            total_rows = (
                self.db.query(
                    Inquiry.car_id,
                    func.count(Inquiry.id).label("total"),
                )
                .filter(Inquiry.car_id.in_(vehicle_ids))
                .group_by(Inquiry.car_id)
                .all()
            )
        else:
            total_rows = (
                self.db.query(
                    Inquiry.motorcycle_id,
                    func.count(Inquiry.id).label("total"),
                )
                .filter(Inquiry.motorcycle_id.in_(vehicle_ids))
                .group_by(Inquiry.motorcycle_id)
                .all()
            )

        total_map = {r[0]: r[1] for r in total_rows}

        scored = []
        for vid, co_views in co_inquired:
            total = total_map.get(vid, co_views)
            denominator = n_source_clients + total - co_views
            score = co_views / denominator if denominator > 0 else 0.0
            scored.append((vid, round(float(score), 4), co_views))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    # ------------------------------------------------------------------
    # Result builders
    # ------------------------------------------------------------------

    def _build_car_results(
        self,
        scored: List[Tuple[int, float, int]],
        limit: int,
        exclude_statuses: List[str],
    ) -> List[Dict]:
        top_ids = [vid for vid, _, _ in scored[: limit * 2]]

        cars = (
            self.db.query(Car)
            .join(CarModel, Car.car_model_id == CarModel.id)
            .filter(
                Car.id.in_(top_ids),
                Car.status.notin_(exclude_statuses),
            )
            .all()
        )
        car_map = {c.id: c for c in cars}

        results = []
        for vid, score, co_views in scored:
            car = car_map.get(vid)
            if not car or not car.car_model:
                continue
            label = "inquiry" if co_views == 1 else "inquiries"
            results.append(
                {
                    "vehicleId": car.id,
                    "score": score,
                    "reason": f"{co_views} co-{label} by similar clients",
                    "details": {
                        "make": car.car_model.make,
                        "model": car.car_model.model,
                        "year": car.year,
                        "price": float(car.selling_price) if car.selling_price else 0.0,
                    },
                }
            )
            if len(results) >= limit:
                break

        logger.info(f"Collaborative: {len(results)} similar cars found")
        return results

    def _build_motorcycle_results(
        self,
        scored: List[Tuple[int, float, int]],
        limit: int,
        exclude_statuses: List[str],
    ) -> List[Dict]:
        top_ids = [vid for vid, _, _ in scored[: limit * 2]]

        motorcycles = (
            self.db.query(Motorcycle)
            .join(MotorcycleModel, Motorcycle.motorcycle_model_id == MotorcycleModel.id)
            .filter(
                Motorcycle.id.in_(top_ids),
                Motorcycle.status.notin_(exclude_statuses),
            )
            .all()
        )
        moto_map = {m.id: m for m in motorcycles}

        results = []
        for vid, score, co_views in scored:
            moto = moto_map.get(vid)
            if not moto or not moto.motorcycle_model:
                continue
            label = "inquiry" if co_views == 1 else "inquiries"
            results.append(
                {
                    "vehicleId": moto.id,
                    "score": score,
                    "reason": f"{co_views} co-{label} by similar clients",
                    "details": {
                        "make": moto.motorcycle_model.make,
                        "model": moto.motorcycle_model.model,
                        "year": moto.manufacture_year,
                        "price": float(moto.selling_price) if moto.selling_price else 0.0,
                    },
                }
            )
            if len(results) >= limit:
                break

        logger.info(f"Collaborative: {len(results)} similar motorcycles found")
        return results
