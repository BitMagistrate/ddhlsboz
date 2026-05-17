"""``POST /v1/site-selection`` — O-D flow heatmap for retail site selection."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from roadpulse_core.types import Org

from app.dependencies import org_from_api_key, state_dep
from app.models import SiteSelectionCell, SiteSelectionRequest, SiteSelectionResponse
from app.state import AppState

router = APIRouter(prefix="/v1", tags=["site-selection"])


@router.post(
    "/site-selection",
    response_model=SiteSelectionResponse,
    summary="Rank hexes inside a bbox by attractiveness for retail site selection",
)
def post_site_selection(
    body: SiteSelectionRequest,
    state: Annotated[AppState, Depends(state_dep)],
    _org: Annotated[Org, Depends(org_from_api_key)],
) -> SiteSelectionResponse:
    min_lng, min_lat, max_lng, max_lat = body.bbox
    cells: list[SiteSelectionCell] = []
    total_flow = 0.0
    raw_rows: list[tuple[str, dict, float, float]] = []
    for entry in state.flood_overlay:
        hex_id: str = entry["hex_id"]  # type: ignore[assignment]
        centroid = entry["centroid"]  # type: ignore[assignment]
        if not (min_lng <= centroid.lng <= max_lng and min_lat <= centroid.lat <= max_lat):
            continue
        features = state.feature_store.get_online_features(
            "hex_speed_5min", [hex_id], ["flow_in", "flow_out", "vehicle_count"]
        )[hex_id]
        flow = float(features.get("flow_in") or 0) + float(features.get("flow_out") or 0)
        flood_penalty = float(entry["score"])  # type: ignore[arg-type]
        raw_rows.append((hex_id, centroid, flow, flood_penalty))
        total_flow += flow

    if total_flow == 0:
        # If the bbox has no seeded flow data, return all hexes in the bbox with a
        # uniform score so the dashboard isn't blank.
        for entry in state.flood_overlay:
            hex_id = entry["hex_id"]  # type: ignore[assignment]
            centroid = entry["centroid"]  # type: ignore[assignment]
            if not (min_lng <= centroid.lng <= max_lng and min_lat <= centroid.lat <= max_lat):
                continue
            cells.append(
                SiteSelectionCell(
                    hex_id=hex_id,
                    centroid=centroid,
                    score=0.5,
                    flow_share=0.0,
                    flood_penalty=float(entry["score"]),  # type: ignore[arg-type]
                    median_visit_min=4.5,
                )
            )
        return SiteSelectionResponse(
            bbox=body.bbox,
            generated_at=datetime.now(UTC),
            top_cells=cells,
        )
    audience_bonus = {"retail": 1.0, "logistics": 0.85, "hospitality": 1.15}[body.audience]
    for hex_id, centroid, flow, penalty in raw_rows:
        share = flow / total_flow
        score = max(0.0, min(1.0, share * audience_bonus - 0.6 * penalty))
        cells.append(
            SiteSelectionCell(
                hex_id=hex_id,
                centroid=centroid,
                score=round(score, 4),
                flow_share=round(share, 4),
                flood_penalty=round(penalty, 4),
                median_visit_min=4.5 if body.audience == "retail" else 9.0,
            )
        )
    cells.sort(key=lambda c: c.score, reverse=True)
    return SiteSelectionResponse(
        bbox=body.bbox,
        generated_at=datetime.now(UTC),
        top_cells=cells[:40],
    )
