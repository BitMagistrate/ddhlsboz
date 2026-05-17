"""``POST /v1/isochrone`` — reachability polygons."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from roadpulse_core.types import LatLon, Org
from roadpulse_routing.engine import RoutingEngine

from app.dependencies import org_from_api_key, routing_engine_dep, state_dep
from app.models import IsochroneRequest, IsochroneResponse, IsochroneRing
from app.state import AppState

router = APIRouter(prefix="/v1", tags=["isochrone"])


@router.post(
    "/isochrone",
    response_model=IsochroneResponse,
    summary="Compute reachability rings for several minute thresholds",
)
def post_isochrone(
    body: IsochroneRequest,
    engine: Annotated[RoutingEngine, Depends(routing_engine_dep)],
    state: Annotated[AppState, Depends(state_dep)],
    _org: Annotated[Org, Depends(org_from_api_key)],
) -> IsochroneResponse:
    origin_node = state.nearest_node(body.origin)
    reachable = engine.reachable_within(
        origin_node.id, max_seconds=max(body.minutes) * 60, mode=body.mode
    )

    rings: list[IsochroneRing] = []
    for minute in sorted(body.minutes):
        seconds = minute * 60
        nodes = [n for n in reachable if n.cost_s <= seconds]
        if not nodes:
            polygon = [body.origin]
            rings.append(
                IsochroneRing(minutes=minute, area_km2=0.0, population_reached=0, polygon=polygon)
            )
            continue
        polygon = _convex_hull(
            [(state.graph.nodes[n.node_id].lng, state.graph.nodes[n.node_id].lat) for n in nodes]
        )
        area_km2 = _polygon_area_km2(polygon)
        # Population estimate: count distinct hexes visited × mean population per hex.
        hex_ids: set[str] = set()
        for n in nodes:
            for edge in state.seed.edges:
                if edge.src == n.node_id or edge.dst == n.node_id:
                    hid = edge.tags.get("hex_id")
                    if hid:
                        hex_ids.add(hid)
        population = sum(state.hex_population(h) for h in hex_ids)
        rings.append(
            IsochroneRing(
                minutes=minute,
                area_km2=round(area_km2, 3),
                population_reached=population,
                polygon=[LatLon(lat=lat, lng=lng) for lng, lat in polygon],
            )
        )
    return IsochroneResponse(
        origin=body.origin,
        generated_at=datetime.now(UTC),
        rings=rings,
    )


def _convex_hull(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Andrew's monotone chain. ``points`` are (lng, lat)."""
    points = sorted(set(points))
    if len(points) <= 2:
        return points

    def cross(o: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list[tuple[float, float]] = []
    for p in points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper: list[tuple[float, float]] = []
    for p in reversed(points):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def _polygon_area_km2(polygon: list[tuple[float, float]]) -> float:
    if len(polygon) < 3:
        return 0.0
    # Shoelace in m² using a local equirectangular projection.
    lat0 = sum(lat for _, lat in polygon) / len(polygon)
    cos_lat0 = math.cos(math.radians(lat0))
    coords = [
        (
            (lng - polygon[0][0]) * 111_320 * cos_lat0,
            (lat - polygon[0][1]) * 110_540,
        )
        for lng, lat in polygon
    ]
    s = 0.0
    for i in range(len(coords)):
        x1, y1 = coords[i]
        x2, y2 = coords[(i + 1) % len(coords)]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0 / 1_000_000.0


# Re-export for tests that import the helpers directly.
__all__ = ["_convex_hull", "_polygon_area_km2", "router"]
