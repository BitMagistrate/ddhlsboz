"""FastAPI wrapper around :class:`roadpulse_routing.engine.RoutingEngine`."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from roadpulse_core.types import RouteMode
from roadpulse_routing.engine import RoutingEngine, StaticPenalty
from roadpulse_routing.graph import Edge, Graph, Node
from roadpulse_telemetry.logger import get_logger


class LatLon(BaseModel):
    lat: float = Field(..., ge=-90.0, le=90.0)
    lng: float = Field(..., ge=-180.0, le=180.0)


class RouteIn(BaseModel):
    origin: LatLon
    destination: LatLon
    mode: RouteMode = RouteMode.MOTORBIKE


class RouteOut(BaseModel):
    name: str
    distance_m: float
    duration_s: float
    free_flow_s: float
    flood_score: float
    hex_path: list[str]


_engine: RoutingEngine | None = None
_graph: Graph | None = None


def _load_graph() -> tuple[Graph, dict[str, float]]:
    seed_dir = Path(__file__).resolve().parents[3] / "data" / "seed"
    nodes = json.loads((seed_dir / "graph_nodes.json").read_text())
    edges = json.loads((seed_dir / "graph_edges.json").read_text())
    floods = json.loads((seed_dir / "flood_markers.json").read_text())
    g = Graph()
    for n in nodes:
        g.add_node(Node(id=int(n["id"]), lng=float(n["lng"]), lat=float(n["lat"])))
    for e in edges:
        g.add_edge(
            Edge(
                src=int(e["src"]),
                dst=int(e["dst"]),
                distance_m=float(e["distance_m"]),
                free_flow_speed_kmh=float(e["free_flow_speed_kmh"]),
                road_class=str(e["road_class"]),
                tags={"hex_id": str(e.get("hex_id", ""))},
            ),
            bidirectional=False,
        )
    flood_by_hex = {
        hid: float(info.get("score", 0.0)) for hid, info in floods.items() if isinstance(info, dict)
    }
    return g, flood_by_hex


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _engine, _graph
    logger = get_logger("routing-engine")
    logger.info("routing.startup")
    g, flood = _load_graph()
    _graph = g
    _engine = RoutingEngine(g, StaticPenalty(flood_by_hex=flood))
    yield
    logger.info("routing.shutdown")


app = FastAPI(title="RoadPulse Routing Engine", version="0.1.0", lifespan=lifespan)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/route", response_model=list[RouteOut])
def route(body: RouteIn) -> list[RouteOut]:
    assert _engine is not None and _graph is not None
    o = _graph.nearest_node(body.origin.lng, body.origin.lat)
    d = _graph.nearest_node(body.destination.lng, body.destination.lat)
    if o.id == d.id:
        raise HTTPException(400, "origin and destination collapse to the same node")
    try:
        variants = _engine.three_candidates(o.id, d.id, mode=body.mode)
    except LookupError as exc:
        raise HTTPException(422, str(exc)) from exc
    return [
        RouteOut(
            name=v.name,
            distance_m=v.distance_m,
            duration_s=v.duration_s,
            free_flow_s=v.free_flow_seconds,
            flood_score=v.flood_score,
            hex_path=v.hex_path,
        )
        for v in variants
    ]
