"""FastAPI entrypoint.

This file is intentionally tiny: it wires the routers, middleware and OpenAPI
metadata. Business logic lives under ``app.routers.*``.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from roadpulse_telemetry.context import bind_request_context
from roadpulse_telemetry.logger import configure_logging, get_logger

from app import __version__
from app.config import get_settings
from app.data_origin import data_origin, pending_real_feeds, real_feeds
from app.routers import (
    eta_batch,
    fleet_match,
    flood_risk,
    health,
    isochrone,
    route,
    site_selection,
    trigger_feed,
)
from app.state import get_app_state


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = get_logger("api-gateway")
    state = get_app_state()
    logger.info(
        "api_gateway.started",
        version=__version__,
        environment=settings.environment,
        nodes=len(state.graph.nodes),
        edges=len(state.graph.edges),
        flood_hexes=len(state.flood_overlay),
        orgs=len(state.seed.orgs),
        mode="synthetic-fixtures",
        data_origin=data_origin(),
        real_feeds=real_feeds(),
        pending_real_feeds=pending_real_feeds(),
    )
    yield
    logger.info("api_gateway.stopped")


app = FastAPI(
    title="RoadPulse Public API",
    version=__version__,
    description=(
        "RoadPulse is a flood-aware mobility intelligence layer for Vietnam. This OpenAPI "
        "document covers the public ``/v1/*`` surface — three-route planning, batch ETA, "
        "isochrones, flood risk, site selection, fleet matching and the parametric "
        "insurance trigger feed. See ``docs/api/`` for SDK snippets.\n\n"
        "**Data origin:** this build is served from synthetic VETC-shaped fixtures. "
        "`/v1/healthz` exposes `data_origin` and the list of pending real feeds — see "
        "the README \"What's real vs synthetic\" matrix for the full mapping."
    ),
    lifespan=lifespan,
    openapi_url="/v1/openapi.json",
    docs_url="/v1/docs",
    redoc_url="/v1/redoc",
)


@app.middleware("http")
async def trace_middleware(request: Request, call_next):
    started = time.perf_counter()
    trace_id = bind_request_context(headers=request.headers)
    response: Response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started) * 1000
    response.headers["x-trace-id"] = trace_id
    response.headers["x-response-time-ms"] = f"{elapsed_ms:.2f}"
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, exc: Exception):
    logger = get_logger("api-gateway")
    logger.error("unhandled_exception", error=str(exc), error_type=exc.__class__.__name__)
    return JSONResponse(
        status_code=500,
        content={
            "code": "internal_error",
            "message": "internal server error",
        },
    )


settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["x-trace-id", "x-response-time-ms"],
)


# Routers — every ``/v1/*`` surface lives under its own module.
app.include_router(health.router)
app.include_router(route.router)
app.include_router(eta_batch.router)
app.include_router(isochrone.router)
app.include_router(flood_risk.router)
app.include_router(site_selection.router)
app.include_router(fleet_match.router)
app.include_router(trigger_feed.router)
