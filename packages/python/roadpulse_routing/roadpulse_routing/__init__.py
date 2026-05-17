"""Routing engine primitives — graph, profiles, custom edge weights, Dijkstra/A*.

This package is a deliberately small, fully-typed re-implementation of the subset of
OSRM we use at MVP scale. In production the heavy lifting is delegated to OSRM
contraction hierarchies built nightly in ``services/osrm``; this Python implementation
is what the API gateway falls back to when OSRM is being rebuilt and what the unit
tests run against without spinning up the native engine.

The contract that matters here:

* Edges have a baseline cost (free-flow travel time) and a stack of penalty
  contributors (``congestion_score``, ``flood_score``, ``eco_score``). The blended
  cost is ``base × (1 + α·cong + β·flood + γ·eco)`` — exactly the formula the OSRM
  Lua profile applies via ``edge_function``.
* Profiles control which edges are usable (motorbike can use ``hẻm`` alleys, trucks
  can't), default speed by road class, and tunable weights ``α/β/γ``.
"""

from roadpulse_routing.engine import (
    EdgePenaltyLookup,
    ReachableNode,
    Route,
    RoutingEngine,
    StaticPenalty,
    Step,
    ZeroPenalty,
)
from roadpulse_routing.graph import Edge, Graph, Node
from roadpulse_routing.profiles import (
    PROFILES,
    Profile,
    bicycle_vn,
    car_vn,
    motorbike_vn,
    truck_vn,
)

__all__ = [
    "PROFILES",
    "Edge",
    "EdgePenaltyLookup",
    "Graph",
    "Node",
    "Profile",
    "ReachableNode",
    "Route",
    "RoutingEngine",
    "StaticPenalty",
    "Step",
    "ZeroPenalty",
    "bicycle_vn",
    "car_vn",
    "motorbike_vn",
    "truck_vn",
]
