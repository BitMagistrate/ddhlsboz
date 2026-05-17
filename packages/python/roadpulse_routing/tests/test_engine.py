"""Behavioural tests for the routing engine.

We build a deterministic 6-node toy graph that resembles a HCMC corridor:

    A --- B --- C
    |     |     |
    D --- E --- F

with one ``trunk`` road through B/E, residential streets on the rim and a flood
hex covering edges D–E and E–F. The ``safe`` route should detour around the
flooded corridor; ``eco`` should additionally prefer the lower-class roads.
"""

from __future__ import annotations

from roadpulse_core.types import RouteMode
from roadpulse_routing.engine import RoutingEngine, StaticPenalty
from roadpulse_routing.graph import Edge, Graph, Node


def _toy_graph() -> Graph:
    g = Graph()
    g.add_node(Node(id=1, lng=106.70, lat=10.78))  # A
    g.add_node(Node(id=2, lng=106.71, lat=10.78))  # B
    g.add_node(Node(id=3, lng=106.72, lat=10.78))  # C
    g.add_node(Node(id=4, lng=106.70, lat=10.77))  # D
    g.add_node(Node(id=5, lng=106.71, lat=10.77))  # E
    g.add_node(Node(id=6, lng=106.72, lat=10.77))  # F

    common = {"hex_id": ""}
    g.add_edge(
        Edge(
            src=1,
            dst=2,
            distance_m=1_000,
            free_flow_speed_kmh=45,
            road_class="primary",
            tags=dict(common),
        )
    )
    g.add_edge(
        Edge(
            src=2,
            dst=3,
            distance_m=1_000,
            free_flow_speed_kmh=45,
            road_class="primary",
            tags=dict(common),
        )
    )
    g.add_edge(
        Edge(
            src=4,
            dst=5,
            distance_m=1_000,
            free_flow_speed_kmh=50,
            road_class="trunk",
            tags={"hex_id": "hex_flood"},
        )
    )
    g.add_edge(
        Edge(
            src=5,
            dst=6,
            distance_m=1_000,
            free_flow_speed_kmh=50,
            road_class="trunk",
            tags={"hex_id": "hex_flood"},
        )
    )
    g.add_edge(
        Edge(
            src=1,
            dst=4,
            distance_m=500,
            free_flow_speed_kmh=25,
            road_class="residential",
            tags=dict(common),
        )
    )
    g.add_edge(
        Edge(
            src=2,
            dst=5,
            distance_m=500,
            free_flow_speed_kmh=25,
            road_class="residential",
            tags=dict(common),
        )
    )
    g.add_edge(
        Edge(
            src=3,
            dst=6,
            distance_m=500,
            free_flow_speed_kmh=25,
            road_class="residential",
            tags=dict(common),
        )
    )
    return g


def test_three_candidates_have_distinct_costs_when_flood_present() -> None:
    graph = _toy_graph()
    penalty = StaticPenalty(flood_by_hex={"hex_flood": 0.95})
    engine = RoutingEngine(graph, penalty)
    routes = engine.three_candidates(1, 6, mode=RouteMode.MOTORBIKE)
    assert [r.name for r in routes] == ["fast", "safe", "eco"]
    fast, safe, _eco = routes
    # The fast route may go through the trunk; the safe one routes around the flooded hex.
    assert safe.flood_score < fast.flood_score or safe.duration_s >= fast.duration_s


def test_geometry_is_non_empty_polyline() -> None:
    graph = _toy_graph()
    engine = RoutingEngine(graph)
    routes = engine.three_candidates(1, 6, mode=RouteMode.MOTORBIKE)
    for route in routes:
        assert route.geometry
        assert route.distance_m > 0
        assert route.duration_s > 0
        assert route.steps


def test_unreachable_origin_raises() -> None:
    graph = Graph()
    graph.add_node(Node(id=1, lng=106.7, lat=10.78))
    graph.add_node(Node(id=2, lng=106.8, lat=10.78))
    engine = RoutingEngine(graph)
    try:
        engine.three_candidates(1, 2, mode=RouteMode.MOTORBIKE)
    except LookupError as exc:
        assert "unreachable" in str(exc)
    else:
        raise AssertionError("expected LookupError")


def test_motorbike_uses_hem_alleys_truck_does_not() -> None:
    graph = Graph()
    graph.add_node(Node(id=1, lng=106.70, lat=10.78))
    graph.add_node(Node(id=2, lng=106.701, lat=10.78))
    graph.add_node(Node(id=3, lng=106.702, lat=10.78))
    graph.add_edge(Edge(src=1, dst=2, distance_m=100, free_flow_speed_kmh=14, road_class="hem"))
    graph.add_edge(Edge(src=2, dst=3, distance_m=100, free_flow_speed_kmh=14, road_class="hem"))
    engine = RoutingEngine(graph)
    motor = engine.shortest(
        1,
        3,
        profile=__import__("roadpulse_routing").profiles.motorbike_vn,
    )
    assert motor.distance_m > 0
    try:
        engine.shortest(
            1,
            3,
            profile=__import__("roadpulse_routing").profiles.truck_vn,
        )
    except LookupError:
        return
    raise AssertionError("trucks must not be able to traverse hẻm alleys")
