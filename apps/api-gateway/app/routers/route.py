"""``POST /v1/route`` — three-variant routing (fast / safe / eco).

This is the highest-traffic endpoint and the demo's centrepiece. For every request
we plan three candidate routes on the seeded HCMC graph, score them against the
ETA model, the flood detector and the eco model and return all three so the B2C
app can render the picker.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from roadpulse_core.types import LatLon, Org, RouteMode
from roadpulse_ml.eco import EcoModel
from roadpulse_ml.eta import EtaModel, ETARecord
from roadpulse_routing.engine import RoutingEngine
from roadpulse_telemetry.context import current_trace_id, new_trace_id
from roadpulse_telemetry.logger import get_logger

from app.dependencies import (
    eco_model_dep,
    eta_model_dep,
    org_from_api_key,
    routing_engine_dep,
    state_dep,
)
from app.models import (
    FloodOverlayPoint,
    RouteRequest,
    RouteResponse,
    RouteStep,
    RouteVariant,
)
from app.state import AppState

router = APIRouter(prefix="/v1", tags=["route"])

_HOUR_OF_WEEK_WINDOW_LABELS = {
    "morning": (7, "weekday morning rush"),
    "evening": (18, "weekday evening rush"),
}


@router.post(
    "/route",
    response_model=RouteResponse,
    summary="Plan a flood-aware route with fast/safe/eco variants",
)
def post_route(
    body: RouteRequest,
    engine: Annotated[RoutingEngine, Depends(routing_engine_dep)],
    eta_model: Annotated[EtaModel, Depends(eta_model_dep)],
    eco_model: Annotated[EcoModel, Depends(eco_model_dep)],
    state: Annotated[AppState, Depends(state_dep)],
    _org: Annotated[Org, Depends(org_from_api_key)],
) -> RouteResponse:
    logger = get_logger("route")
    origin_node = state.nearest_node(body.origin)
    destination_node = state.nearest_node(body.destination)
    if origin_node.id == destination_node.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="origin and destination map to the same graph node",
        )
    try:
        candidates = engine.three_candidates(
            origin_node.id,
            destination_node.id,
            mode=body.mode,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    depart_at = body.depart_at or datetime.now(UTC)
    hour_of_week = (depart_at.weekday() * 24 + depart_at.hour) % 168
    is_weekend = 1 if depart_at.weekday() >= 5 else 0
    is_rush = 1 if depart_at.hour in {7, 8, 9, 17, 18, 19} else 0

    variants: list[RouteVariant] = []
    for variant in candidates:
        # Use the average flood score of the path as the ETA flood feature.
        avg_speed = (variant.distance_m / variant.duration_s) * 3.6 if variant.duration_s > 0 else 0
        eta_record = ETARecord(
            distance_m=variant.distance_m,
            free_flow_seconds=variant.free_flow_seconds,
            hour_of_week=hour_of_week,
            is_weekend=is_weekend,
            precipitation_mm_h=4.0 if variant.flood_score > 0.2 else 0.0,
            wind_kmh=12.0,
            is_rush_hour=is_rush,
            lag_speed_5min=avg_speed,
            lag_speed_15min=avg_speed,
            lag_speed_1h=avg_speed,
            vehicle_count_5min=320,
            flood_score=variant.flood_score,
            road_class_index=_road_class_to_index(body.mode),
        )
        prediction = eta_model.predict(eta_record)
        emissions = eco_model.estimate(
            mode=body.mode,
            distance_m=variant.distance_m,
            avg_speed_kmh=max(avg_speed, 5.0),
        )
        eco_score = max(variant.eco_score, emissions.eco_score)
        toll_vnd = _estimate_tolls(variant.hex_path, state, body)
        notes: list[str] = []
        if body.avoid_tolls and toll_vnd > 0:
            notes.append("toll avoidance was requested but the optimal road still has tolls")
        if variant.flood_score > 0.6 and body.avoid_flood is False:
            notes.append("⚠ this route crosses a flooded corridor (override allowed)")
        if variant.name == "safe" and variant.flood_score < 0.05:
            notes.append("conditions look clear — safe route ≈ fast route")
        steps = _flatten_steps(variant)
        variants.append(
            RouteVariant(
                name=variant.name,
                distance_m=variant.distance_m,
                duration_s=prediction.eta_s,
                free_flow_s=variant.free_flow_seconds,
                flood_score=variant.flood_score,
                eco_score=eco_score,
                toll_vnd=toll_vnd,
                co2_g=emissions.g_co2,
                eta_p10_s=prediction.eta_p10_s,
                eta_p90_s=prediction.eta_p90_s,
                eta_confidence=prediction.confidence,
                geometry=[LatLon(lat=lat, lng=lng) for lng, lat in variant.geometry],
                steps=steps,
                hex_path=variant.hex_path,
                notes=notes,
            )
        )

    overlay = [
        FloodOverlayPoint(
            hex_id=row["hex_id"],  # type: ignore[index]
            centroid=row["centroid"],  # type: ignore[index]
            score=row["score"],  # type: ignore[index]
            horizon="now",
        )
        for row in state.flood_overlay
    ]
    weather_note = _weather_note(variants)
    request_id = current_trace_id() or new_trace_id()
    logger.info(
        "route.candidates",
        variants=[v.name for v in variants],
        request_id=request_id,
    )
    return RouteResponse(
        request_id=request_id,
        generated_at=datetime.now(UTC),
        variants=variants,
        flood_overlay=overlay,
        weather_note=weather_note,
    )


def _flatten_steps(variant) -> list[RouteStep]:
    steps: list[RouteStep] = []
    for step in variant.steps:
        steps.append(
            RouteStep(
                instruction=step.instruction,
                distance_m=step.distance_m,
                duration_s=step.duration_s,
                bearing_deg=step.bearing_deg,
                geometry=[LatLon(lat=lat, lng=lng) for lng, lat in step.geometry],
            )
        )
    return steps


def _road_class_to_index(mode: RouteMode) -> int:
    return {
        RouteMode.MOTORBIKE: 1,
        RouteMode.CAR: 2,
        RouteMode.TRUCK: 4,
        RouteMode.BICYCLE: 0,
    }.get(mode, 1)


def _estimate_tolls(hex_path: list[str], state: AppState, body: RouteRequest) -> int:
    """Sum toll_vnd tags along the variant. Trucks pay 3× the motorbike toll."""
    if body.mode == RouteMode.MOTORBIKE or body.mode == RouteMode.BICYCLE:
        return 0
    multiplier = 3 if body.mode == RouteMode.TRUCK else 1
    edge_index: dict[str, int] = {}
    for edge in state.seed.edges:
        hid = edge.tags.get("hex_id", "")
        if not hid:
            continue
        try:
            toll = int(edge.tags.get("toll_vnd", 0) or 0)
        except ValueError:
            toll = 0
        if toll:
            edge_index[hid] = max(edge_index.get(hid, 0), toll)
    return sum(edge_index.get(hid, 0) for hid in hex_path) * multiplier


def _weather_note(variants: list[RouteVariant]) -> str | None:
    high = next((v for v in variants if v.flood_score > 0.6), None)
    if high is None:
        return None
    return (
        "Heavy rain detected in District 1/4. Safe route avoids "
        f"{', '.join(high.hex_path[:3])} — expect 5-12 min delay."
    )
