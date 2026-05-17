"""Liveness/readiness/version probes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app import __version__
from app.dependencies import state_dep
from app.models import HealthResponse
from app.state import AppState

router = APIRouter(prefix="/v1", tags=["health"])


@router.get("/healthz", response_model=HealthResponse, summary="Liveness probe")
def healthz(state: Annotated[AppState, Depends(state_dep)]) -> HealthResponse:
    return HealthResponse(
        status="ok",
        version=__version__,
        uptime_s=state.uptime_s,
        services={
            "routing": "ok",
            "eta": "ok" if state.eta_model.is_trained else "degraded",
            "flood": "ok" if state.flood_detector.is_trained else "degraded",
        },
    )


@router.get("/readyz", response_model=HealthResponse, summary="Readiness probe")
def readyz(state: Annotated[AppState, Depends(state_dep)]) -> HealthResponse:
    ready = state.eta_model.is_trained and state.flood_detector.is_trained
    return HealthResponse(
        status="ok" if ready else "degraded",
        version=__version__,
        uptime_s=state.uptime_s,
        services={
            "graph_nodes": str(len(state.graph.nodes)),
            "graph_edges": str(len(state.graph.edges)),
            "flood_hexes": str(len(state.flood_overlay)),
        },
    )


@router.get("/version", summary="Build metadata")
def version() -> dict[str, str]:
    return {"version": __version__, "service": "api-gateway"}
