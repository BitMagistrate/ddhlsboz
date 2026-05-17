"""``GET /v1/flood-risk`` — current and forecast flood scores per hex."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from roadpulse_core.types import LatLon, Org

from app.dependencies import org_from_api_key, state_dep
from app.models import FloodOverlayPoint, FloodRiskResponse
from app.state import AppState

router = APIRouter(prefix="/v1", tags=["flood"])

_HORIZONS = ("now", "1h", "3h", "6h")
_FORECAST_DECAY = {
    "now": 1.0,
    "1h": 1.05,
    "3h": 0.85,
    "6h": 0.65,
}


@router.get(
    "/flood-risk",
    response_model=FloodRiskResponse,
    summary="Return current/forecast flood scores for a set of hexes or bbox",
)
def get_flood_risk(
    state: Annotated[AppState, Depends(state_dep)],
    _org: Annotated[Org, Depends(org_from_api_key)],
    hex_ids: Annotated[list[str] | None, Query()] = None,
    bbox: Annotated[
        tuple[float, float, float, float] | None,
        Query(
            description="minLng,minLat,maxLng,maxLat",
        ),
    ] = None,
    horizon: Annotated[Literal["now", "1h", "3h", "6h"], Query()] = "now",
) -> FloodRiskResponse:
    decay = _FORECAST_DECAY[horizon]
    rows: list[FloodOverlayPoint] = []
    for entry in state.flood_overlay:
        hex_id: str = entry["hex_id"]  # type: ignore[assignment]
        centroid: LatLon = entry["centroid"]  # type: ignore[assignment]
        score: float = float(entry["score"]) * decay  # type: ignore[arg-type]
        if hex_ids is not None and hex_id not in hex_ids:
            continue
        if bbox is not None and not _in_bbox(centroid, bbox):
            continue
        rows.append(
            FloodOverlayPoint(
                hex_id=hex_id,
                centroid=centroid,
                score=min(1.0, max(0.0, round(score, 4))),
                horizon=horizon,
            )
        )
    return FloodRiskResponse(
        horizon=horizon,
        generated_at=datetime.now(UTC),
        hexes=rows,
    )


def _in_bbox(point: LatLon, bbox: tuple[float, float, float, float]) -> bool:
    min_lng, min_lat, max_lng, max_lat = bbox
    return (min_lng <= point.lng <= max_lng) and (min_lat <= point.lat <= max_lat)
