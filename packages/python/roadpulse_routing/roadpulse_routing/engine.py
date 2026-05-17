"""Routing engine.

A small Dijkstra implementation that consumes :class:`~roadpulse_routing.graph.Graph`
and a per-mode :class:`~roadpulse_routing.profiles.Profile`. Edge penalties (flood,
congestion, eco) are pulled out of a swappable :class:`EdgePenaltyLookup` so callers
can plug Redis, an in-memory dict, or a feature-store client.

The implementation deliberately mirrors how the production OSRM Lua profile blends
weights, so unit tests that exercise the Python path also validate the formula
applied by the native engine.
"""

from __future__ import annotations

import heapq
import math
from collections.abc import Iterable
from dataclasses import dataclass, field
from math import isfinite
from typing import Protocol

from roadpulse_core.geo import Coordinate, haversine_m
from roadpulse_core.types import RouteMode

from roadpulse_routing.graph import Edge, Graph
from roadpulse_routing.profiles import PROFILES, Profile


class EdgePenaltyLookup(Protocol):
    """Read-only view onto current edge penalty signals.

    Returns values in ``[0, 1]`` where 0 = no contribution and 1 = maximal slowdown.
    """

    def congestion(self, edge: Edge) -> float: ...
    def flood(self, edge: Edge) -> float: ...
    def eco(self, edge: Edge) -> float: ...


class ZeroPenalty:
    """No-op penalty lookup used in tests and offline backtests."""

    def congestion(self, edge: Edge) -> float:
        return 0.0

    def flood(self, edge: Edge) -> float:
        return 0.0

    def eco(self, edge: Edge) -> float:
        return 0.0


@dataclass(slots=True)
class StaticPenalty:
    """Static dict-backed penalty lookup keyed by H3 hex id stored on the edge tags."""

    congestion_by_hex: dict[str, float] = field(default_factory=dict)
    flood_by_hex: dict[str, float] = field(default_factory=dict)
    eco_by_class: dict[str, float] = field(default_factory=dict)

    def congestion(self, edge: Edge) -> float:
        return self.congestion_by_hex.get(edge.tags.get("hex_id", ""), 0.0)

    def flood(self, edge: Edge) -> float:
        return self.flood_by_hex.get(edge.tags.get("hex_id", ""), 0.0)

    def eco(self, edge: Edge) -> float:
        return self.eco_by_class.get(edge.road_class, 0.0)


# --- Result types ----------------------------------------------------------------------


@dataclass(slots=True)
class Step:
    """A single step in a route response.

    The geometry is expressed as a list of ``(lng, lat)`` tuples so the public
    OpenAPI envelope can wrap them into :class:`LatLon` instances on the way out.
    """

    edge_idx: int
    distance_m: float
    duration_s: float
    road_class: str
    instruction: str
    bearing_deg: float
    geometry: list[tuple[float, float]]
    flood_score: float = 0.0
    congestion_score: float = 0.0


@dataclass(slots=True)
class Route:
    """A single computed route candidate."""

    name: str
    distance_m: float
    duration_s: float
    free_flow_seconds: float
    flood_score: float
    congestion_score: float
    eco_score: float
    toll_estimate_vnd: int
    geometry: list[tuple[float, float]]
    steps: list[Step] = field(default_factory=list)
    hex_path: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ReachableNode:
    """A node reachable from the origin within a time budget."""

    node_id: int
    cost_s: float


# --- Engine ---------------------------------------------------------------------------


class RoutingEngine:
    """Dijkstra-based routing engine with custom penalty blending."""

    def __init__(self, graph: Graph, penalties: EdgePenaltyLookup | None = None) -> None:
        self._graph = graph
        self._penalties = penalties or ZeroPenalty()

    @property
    def graph(self) -> Graph:
        return self._graph

    @property
    def penalties(self) -> EdgePenaltyLookup:
        return self._penalties

    # --- public API ------------------------------------------------------------------

    def shortest(
        self,
        origin_id: int,
        destination_id: int,
        *,
        profile: Profile,
        flood_aware: bool = True,
        eco: bool = False,
    ) -> Route:
        """Run Dijkstra with the blended-cost edge function."""
        prev = self._dijkstra(
            origin_id,
            destination_id,
            profile=profile,
            flood_aware=flood_aware,
            eco=eco,
        )
        if origin_id == destination_id:
            origin = self._graph.node(origin_id)
            return Route(
                name="route",
                distance_m=0.0,
                duration_s=0.0,
                free_flow_seconds=0.0,
                flood_score=0.0,
                congestion_score=0.0,
                eco_score=0.0,
                toll_estimate_vnd=0,
                geometry=[(origin.lng, origin.lat)],
            )
        if destination_id not in prev:
            raise LookupError("destination is unreachable from origin under this profile")
        return self._reconstruct(origin_id, destination_id, prev, profile)

    def three_candidates(
        self,
        origin_id: int,
        destination_id: int,
        *,
        mode: RouteMode = RouteMode.MOTORBIKE,
    ) -> list[Route]:
        """Return the ``fast`` / ``safe`` / ``eco`` candidates side-by-side."""
        profile = PROFILES[mode]
        fast = self.shortest(
            origin_id,
            destination_id,
            profile=profile,
            flood_aware=False,
            eco=False,
        )
        fast.name = "fast"
        safe = self.shortest(
            origin_id,
            destination_id,
            profile=profile,
            flood_aware=True,
            eco=False,
        )
        safe.name = "safe"
        eco_route = self.shortest(
            origin_id,
            destination_id,
            profile=profile,
            flood_aware=True,
            eco=True,
        )
        eco_route.name = "eco"
        return [fast, safe, eco_route]

    def reachable_within(
        self,
        origin_id: int,
        *,
        max_seconds: float,
        mode: RouteMode = RouteMode.MOTORBIKE,
    ) -> list[ReachableNode]:
        """Multi-source-shortest-path: return every node reachable in ``max_seconds``."""
        profile = PROFILES[mode]
        dist: dict[int, float] = {origin_id: 0.0}
        pq: list[tuple[float, int]] = [(0.0, origin_id)]
        visited: set[int] = set()
        beta = profile.beta_flood
        alpha = profile.alpha_congestion
        while pq:
            cost, node_id = heapq.heappop(pq)
            if node_id in visited:
                continue
            if cost > max_seconds:
                continue
            visited.add(node_id)
            for edge_idx in self._graph.outgoing(node_id):
                edge = self._graph.edge(edge_idx)
                if not profile.is_usable(edge.road_class, edge.tags):
                    continue
                base = edge.free_flow_seconds
                if not isfinite(base) or base <= 0:
                    continue
                penalty = (
                    1.0
                    + alpha * self._penalties.congestion(edge)
                    + beta * self._penalties.flood(edge)
                )
                new_cost = cost + base * penalty
                if new_cost > max_seconds:
                    continue
                if new_cost < dist.get(edge.dst, float("inf")):
                    dist[edge.dst] = new_cost
                    heapq.heappush(pq, (new_cost, edge.dst))
        return [ReachableNode(node_id=nid, cost_s=c) for nid, c in dist.items()]

    # --- helpers ---------------------------------------------------------------------

    def _dijkstra(
        self,
        origin_id: int,
        destination_id: int,
        *,
        profile: Profile,
        flood_aware: bool,
        eco: bool,
    ) -> dict[int, tuple[int, int]]:
        dist: dict[int, float] = {origin_id: 0.0}
        prev: dict[int, tuple[int, int]] = {}
        pq: list[tuple[float, int]] = [(0.0, origin_id)]
        visited: set[int] = set()
        beta = profile.beta_flood if flood_aware else 0.0
        gamma = profile.gamma_eco if eco else 0.0
        alpha = profile.alpha_congestion
        while pq:
            cost, node_id = heapq.heappop(pq)
            if node_id in visited:
                continue
            visited.add(node_id)
            if node_id == destination_id:
                break
            for edge_idx in self._graph.outgoing(node_id):
                edge = self._graph.edge(edge_idx)
                if not profile.is_usable(edge.road_class, edge.tags):
                    continue
                base = edge.free_flow_seconds
                if not isfinite(base) or base <= 0:
                    continue
                penalty = (
                    1.0
                    + alpha * self._penalties.congestion(edge)
                    + beta * self._penalties.flood(edge)
                    + gamma * self._penalties.eco(edge)
                )
                new_cost = cost + base * penalty
                if new_cost < dist.get(edge.dst, float("inf")):
                    dist[edge.dst] = new_cost
                    prev[edge.dst] = (node_id, edge_idx)
                    heapq.heappush(pq, (new_cost, edge.dst))
        return prev

    def _reconstruct(
        self,
        origin_id: int,
        destination_id: int,
        prev: dict[int, tuple[int, int]],
        profile: Profile,
    ) -> Route:
        # Walk back from destination → origin to recover the edge sequence.
        edge_sequence: list[int] = []
        node_id = destination_id
        path_nodes: list[int] = [destination_id]
        while node_id != origin_id:
            prev_node, edge_idx = prev[node_id]
            edge_sequence.append(edge_idx)
            path_nodes.append(prev_node)
            node_id = prev_node
        edge_sequence.reverse()
        path_nodes.reverse()

        steps: list[Step] = []
        geometry: list[tuple[float, float]] = []
        hex_path: list[str] = []
        total_distance = 0.0
        total_duration = 0.0
        total_free_flow = 0.0
        total_flood = 0.0
        total_congestion = 0.0
        toll_vnd = 0
        last_hex = ""

        origin_node = self._graph.node(origin_id)
        geometry.append((origin_node.lng, origin_node.lat))

        for src_node_id, edge_idx in zip(path_nodes[:-1], edge_sequence, strict=True):
            edge = self._graph.edge(edge_idx)
            src = self._graph.node(src_node_id)
            dst = self._graph.node(edge.dst)
            flood = self._penalties.flood(edge)
            cong = self._penalties.congestion(edge)
            step_duration = edge.free_flow_seconds * (
                1.0 + profile.alpha_congestion * cong + profile.beta_flood * flood
            )
            bearing = _bearing(src.lng, src.lat, dst.lng, dst.lat)
            road_name = edge.tags.get("name") or _class_label(edge.road_class)
            instruction = _build_instruction(road_name, edge.distance_m, edge.road_class)
            step_geometry = [(src.lng, src.lat), (dst.lng, dst.lat)]
            steps.append(
                Step(
                    edge_idx=edge_idx,
                    distance_m=edge.distance_m,
                    duration_s=step_duration,
                    road_class=edge.road_class,
                    instruction=instruction,
                    bearing_deg=round(bearing, 1),
                    geometry=step_geometry,
                    flood_score=round(flood, 3),
                    congestion_score=round(cong, 3),
                )
            )
            geometry.append((dst.lng, dst.lat))
            total_distance += edge.distance_m
            total_duration += step_duration
            total_free_flow += edge.free_flow_seconds
            total_flood = max(total_flood, flood)
            total_congestion = max(total_congestion, cong)
            try:
                toll_vnd += int(edge.tags.get("toll_vnd", "0") or "0")
            except (TypeError, ValueError):
                pass
            hid = edge.tags.get("hex_id") or ""
            if hid and hid != last_hex:
                hex_path.append(hid)
                last_hex = hid

        eco_score = (total_distance / 1_000.0) * profile.eco_factor
        return Route(
            name="route",
            distance_m=round(total_distance, 2),
            duration_s=round(total_duration, 2),
            free_flow_seconds=round(total_free_flow, 2),
            flood_score=round(total_flood, 3),
            congestion_score=round(total_congestion, 3),
            eco_score=round(eco_score, 3),
            toll_estimate_vnd=toll_vnd,
            geometry=geometry,
            steps=steps,
            hex_path=hex_path,
        )


# --- helpers ----------------------------------------------------------------------


def _bearing(lng1: float, lat1: float, lng2: float, lat2: float) -> float:
    """Initial great-circle bearing from (lng1,lat1) to (lng2,lat2) in degrees."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dlon = math.radians(lng2 - lng1)
    x = math.sin(dlon) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlon)
    brng = math.degrees(math.atan2(x, y))
    return (brng + 360.0) % 360.0


_ROAD_CLASS_LABELS = {
    "motorway": "highway",
    "trunk": "boulevard",
    "primary": "avenue",
    "secondary": "road",
    "tertiary": "street",
    "residential": "street",
    "living_street": "lane",
    "service": "service road",
    "hem": "hẻm alley",
    "unclassified": "road",
    "track": "track",
}


def _class_label(road_class: str) -> str:
    return _ROAD_CLASS_LABELS.get(road_class, "road")


def _build_instruction(road_name: str, distance_m: float, road_class: str) -> str:
    """Human-readable instruction in English (the demo locale)."""
    label = road_name if road_name else _class_label(road_class)
    if distance_m >= 1_000:
        dist_str = f"{distance_m / 1_000:.1f} km"
    else:
        dist_str = f"{int(round(distance_m))} m"
    return f"Continue on {label} for {dist_str}"


def total_geometry_length(coords: Iterable[Coordinate]) -> float:
    """Sum great-circle distances over a polyline; useful for backtests."""
    coords = list(coords)
    total = 0.0
    for a, b in zip(coords, coords[1:], strict=False):
        total += haversine_m(a, b)
    return total
