"""Road network graph primitives.

The graph stores nodes as ``(node_id, lng, lat)`` tuples and edges as adjacency
lists. The free-flow travel-time cost is precomputed once at construction; the
flood/congestion penalties live in :class:`EdgeAttributes` and are layered on at
query time so we can update them every five minutes without rebuilding the graph.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from roadpulse_core.geo import Coordinate, haversine_m


@dataclass(frozen=True, slots=True)
class Node:
    """A node in the road network."""

    id: int
    lng: float
    lat: float
    district: str | None = None

    def as_coordinate(self) -> Coordinate:
        return Coordinate(lng=self.lng, lat=self.lat)


@dataclass(slots=True)
class Edge:
    """An edge in the road network.

    Attributes
    ----------
    src, dst
        Endpoint node IDs.
    distance_m
        Geometric length in metres (haversine).
    free_flow_speed_kmh
        Posted/expected speed in absence of congestion.
    road_class
        OSM-style functional class used to look up profile defaults / penalties.
    tags
        Free-form bag forwarded from OSM (oneway, hgv, motor_vehicle, ...).
    """

    src: int
    dst: int
    distance_m: float
    free_flow_speed_kmh: float
    road_class: str = "residential"
    tags: dict[str, str] = field(default_factory=dict)

    @property
    def free_flow_seconds(self) -> float:
        return (self.distance_m / 1_000.0) / max(self.free_flow_speed_kmh, 1.0) * 3600.0


class Graph:
    """In-memory road graph.

    A real production graph holds 80–250K edges for HCMC + Hanoi. This class is
    designed for ≤ 1M edges held in process memory: an adjacency-list of edge
    indices keyed by node id, with all edge data in a contiguous ``list``.
    """

    def __init__(self) -> None:
        self._nodes: dict[int, Node] = {}
        self._edges: list[Edge] = []
        self._adj: dict[int, list[int]] = {}

    # --- construction -----------------------------------------------------------------

    def add_node(self, node: Node) -> None:
        if node.id in self._nodes:
            raise ValueError(f"node {node.id} already in graph")
        self._nodes[node.id] = node
        self._adj.setdefault(node.id, [])

    def add_edge(self, edge: Edge, *, bidirectional: bool = True) -> None:
        if edge.src not in self._nodes or edge.dst not in self._nodes:
            raise KeyError("both endpoints must exist before adding an edge")
        idx = len(self._edges)
        self._edges.append(edge)
        self._adj[edge.src].append(idx)
        if bidirectional:
            reverse = Edge(
                src=edge.dst,
                dst=edge.src,
                distance_m=edge.distance_m,
                free_flow_speed_kmh=edge.free_flow_speed_kmh,
                road_class=edge.road_class,
                tags=dict(edge.tags),
            )
            self._edges.append(reverse)
            self._adj[edge.dst].append(idx + 1)

    # --- access -----------------------------------------------------------------------

    @property
    def nodes(self) -> Mapping[int, Node]:
        """Return the underlying ``{node_id: Node}`` mapping (read-only view)."""
        return self._nodes

    @property
    def edges(self) -> Sequence[Edge]:
        return self._edges

    def node(self, node_id: int) -> Node:
        return self._nodes[node_id]

    def edge(self, edge_idx: int) -> Edge:
        return self._edges[edge_idx]

    def outgoing(self, node_id: int) -> list[int]:
        """Return edge indices leaving ``node_id``."""
        return self._adj.get(node_id, [])

    def __len__(self) -> int:
        return len(self._nodes)

    # --- convenience helpers ----------------------------------------------------------

    def nearest_node(
        self,
        lng_or_point: float | Coordinate | Any,
        lat: float | None = None,
        *,
        max_distance_m: float = 5_000.0,
    ) -> Node:
        """Brute-force nearest-node lookup.

        Accepts either ``(lng, lat)`` floats or a single object exposing ``.lng/.lat``
        attributes (such as :class:`Coordinate` or :class:`roadpulse_core.types.LatLon`).
        Production code uses an STR-tree built once at startup; that lives in the
        ``routing-engine`` app which depends on this package.
        """
        if lat is None:
            point_lng = float(lng_or_point.lng)
            point_lat = float(lng_or_point.lat)
        else:
            point_lng = float(lng_or_point)
            point_lat = float(lat)
        if not self._nodes:
            raise LookupError("graph has no nodes")
        target = Coordinate(lng=point_lng, lat=point_lat)
        best_node: Node | None = None
        best_d = float("inf")
        for node in self._nodes.values():
            d = haversine_m(target, node.as_coordinate())
            if d < best_d:
                best_d = d
                best_node = node
        if best_node is None or best_d > max_distance_m:
            raise LookupError(
                f"no node within {max_distance_m:.0f} m of ({point_lng}, {point_lat})"
            )
        return best_node
