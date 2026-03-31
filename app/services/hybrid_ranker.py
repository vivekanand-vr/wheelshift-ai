"""Hybrid ranker: combines content-based and collaborative filtering scores"""
import logging
from typing import Dict, List, Tuple

from sqlalchemy.orm import Session

from app.config import get_settings
from app.services.collaborative_similarity import CollaborativeSimilarityService
from app.services.content_similarity import ContentSimilarityService

logger = logging.getLogger(__name__)
settings = get_settings()


class HybridRanker:
    """
    Merge content-based and collaborative scores into a unified ranking.

    Weights are controlled by settings:
        content_based_weight  (default 0.6)
        collaborative_weight  (default 0.4)

    If one source returns no results the other fills the full result.
    The returned method string reflects which sources actually contributed:
        "hybrid"         — both sources contributed
        "content"        — only content-based results available
        "collaborative"  — only collaborative results available
    """

    def __init__(self, db: Session):
        self.db = db
        self.content_service = ContentSimilarityService(db)
        self.collaborative_service = CollaborativeSimilarityService(db)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def find_similar_cars(
        self, car_id: int, limit: int = 10
    ) -> Tuple[List[Dict], str]:
        """
        Return (suggestions, method) for cars.

        Fetches limit*2 results from each engine so merging produces
        enough candidates before pruning to `limit`.
        """
        content = self.content_service.find_similar_cars(car_id, limit=limit * 2)
        collaborative = self.collaborative_service.find_similar_cars(
            car_id, limit=limit * 2
        )
        suggestions, method = self._merge(content, collaborative, limit)
        logger.info(
            f"Hybrid ranking for car {car_id}: {len(suggestions)} results via '{method}'"
        )
        return suggestions, method

    def find_similar_motorcycles(
        self, motorcycle_id: int, limit: int = 10
    ) -> Tuple[List[Dict], str]:
        """Return (suggestions, method) for motorcycles."""
        content = self.content_service.find_similar_motorcycles(
            motorcycle_id, limit=limit * 2
        )
        collaborative = self.collaborative_service.find_similar_motorcycles(
            motorcycle_id, limit=limit * 2
        )
        suggestions, method = self._merge(content, collaborative, limit)
        logger.info(
            f"Hybrid ranking for motorcycle {motorcycle_id}: "
            f"{len(suggestions)} results via '{method}'"
        )
        return suggestions, method

    # ------------------------------------------------------------------
    # Merging logic
    # ------------------------------------------------------------------

    def _merge(
        self,
        content_results: List[Dict],
        collaborative_results: List[Dict],
        limit: int,
    ) -> Tuple[List[Dict], str]:
        """
        Merge and re-rank results from both engines.

        hybrid_score = content_weight * content_score
                     + collaborative_weight * collaborative_score

        Reasons from both sources are joined with " + " so callers can
        display a combined explanation.
        """
        has_content = bool(content_results)
        has_collab = bool(collaborative_results)

        # Degenerate cases — no merging needed
        if not has_content and not has_collab:
            return [], "hybrid"
        if not has_collab:
            return content_results[:limit], "content"
        if not has_content:
            return collaborative_results[:limit], "collaborative"

        content_weight = settings.content_based_weight
        collab_weight = settings.collaborative_weight

        content_map: Dict[int, Dict] = {r["vehicleId"]: r for r in content_results}
        collab_map: Dict[int, Dict] = {r["vehicleId"]: r for r in collaborative_results}

        merged: List[Dict] = []
        for vid in set(content_map) | set(collab_map):
            c_item = content_map.get(vid)
            k_item = collab_map.get(vid)

            c_score = c_item["score"] if c_item else 0.0
            k_score = k_item["score"] if k_item else 0.0
            hybrid_score = round(content_weight * c_score + collab_weight * k_score, 4)

            # Combine reasons from both sources (skip empty strings)
            reason_parts = []
            if c_item and c_item.get("reason"):
                reason_parts.append(c_item["reason"])
            if k_item and k_item.get("reason"):
                reason_parts.append(k_item["reason"])
            reason = " + ".join(reason_parts) if reason_parts else "hybrid match"

            # Prefer content details (richer); fall back to collaborative
            details = (c_item or k_item).get("details", {})

            merged.append(
                {
                    "vehicleId": vid,
                    "score": hybrid_score,
                    "reason": reason,
                    "details": details,
                }
            )

        merged.sort(key=lambda x: x["score"], reverse=True)
        return merged[:limit], "hybrid"
