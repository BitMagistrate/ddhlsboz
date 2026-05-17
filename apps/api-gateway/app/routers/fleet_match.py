"""``POST /v1/fleet-match`` — load matching marketplace.

The matcher consults the seeded fleet catalog and returns the candidates whose
capacity envelope and current location best fit the shipper's request. ETA is
estimated using the routing engine + flood penalty.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from roadpulse_core.geo import haversine_m
from roadpulse_core.types import LatLon, Org
from roadpulse_routing.engine import RoutingEngine
from roadpulse_telemetry.context import current_trace_id, new_trace_id

from app.dependencies import org_from_api_key, routing_engine_dep, state_dep
from app.models import FleetMatchCandidate, FleetMatchRequest, FleetMatchResponse
from app.state import AppState

router = APIRouter(prefix="/v1", tags=["fleet-match"])


@router.post(
    "/fleet-match",
    response_model=FleetMatchResponse,
    summary="Match a shipper request against the carrier marketplace",
)
def post_fleet_match(
    body: FleetMatchRequest,
    state: Annotated[AppState, Depends(state_dep)],
    engine: Annotated[RoutingEngine, Depends(routing_engine_dep)],
    _org: Annotated[Org, Depends(org_from_api_key)],
) -> FleetMatchResponse:
    request_id = current_trace_id() or new_trace_id()
    pickup_node = state.nearest_node(body.pickup).id
    candidates: list[FleetMatchCandidate] = []
    for fleet in state.fleets:
        fleet_id = str(fleet["id"])
        depot = LatLon(lat=float(fleet["depot_lat"]), lng=float(fleet["depot_lng"]))  # type: ignore[index]
        capacity_kg = float(fleet["capacity_kg"])  # type: ignore[index]
        capacity_m3 = float(fleet["capacity_m3"])  # type: ignore[index]
        if capacity_kg < body.weight_kg or capacity_m3 < body.volume_m3:
            continue
        try:
            variant = engine.three_candidates(
                state.nearest_node(depot).id, pickup_node, mode=body.mode
            )[0]
        except LookupError:
            straight_m = haversine_m(depot.lat, depot.lng, body.pickup.lat, body.pickup.lng)
            variant_distance = straight_m * 1.4
            variant_duration = variant_distance / 1000 / 30 * 3600
            variant_flood = 0.05
        else:
            variant_distance = variant.distance_m
            variant_duration = variant.duration_s
            variant_flood = variant.flood_score
        rate_per_km = float(fleet["rate_per_km_vnd"])  # type: ignore[index]
        quote = int(round(variant_distance / 1000 * rate_per_km + 80_000))
        candidates.append(
            FleetMatchCandidate(
                fleet_id=fleet_id,
                fleet_name=str(fleet["name"]),  # type: ignore[index]
                vehicle_class=str(fleet["vehicle_class"]),  # type: ignore[index]
                capacity_kg=capacity_kg,
                capacity_m3=capacity_m3,
                pickup_eta_min=round(variant_duration / 60.0, 1),
                quote_vnd=quote,
                flood_risk=round(variant_flood, 4),
                rating=float(fleet.get("rating", 4.5)),  # type: ignore[arg-type]
            )
        )
    candidates.sort(key=lambda c: (c.pickup_eta_min, c.quote_vnd))
    return FleetMatchResponse(
        request_id=request_id,
        generated_at=datetime.now(UTC),
        candidates=candidates[:10],
    )
