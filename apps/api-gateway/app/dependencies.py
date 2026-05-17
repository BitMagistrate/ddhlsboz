"""FastAPI dependencies.

Every router imports its services from here so we can swap implementations (real
vs. in-memory, sandbox vs. live VETC Pay) in a single place.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from roadpulse_core.types import Org
from roadpulse_features.store import InMemoryFeatureStore
from roadpulse_ml.eco import EcoModel
from roadpulse_ml.eta import EtaModel
from roadpulse_ml.flood import FloodDetector
from roadpulse_privacy.guard import KAnonGuard
from roadpulse_routing.engine import RoutingEngine
from roadpulse_telemetry.logger import get_logger

from app.config import Settings, get_settings
from app.state import AppState, get_app_state


def settings_dep() -> Settings:
    return get_settings()


def state_dep() -> AppState:
    return get_app_state()


def routing_engine_dep(state: Annotated[AppState, Depends(state_dep)]) -> RoutingEngine:
    return state.routing_engine


def eta_model_dep(state: Annotated[AppState, Depends(state_dep)]) -> EtaModel:
    return state.eta_model


def flood_detector_dep(state: Annotated[AppState, Depends(state_dep)]) -> FloodDetector:
    return state.flood_detector


def eco_model_dep(state: Annotated[AppState, Depends(state_dep)]) -> EcoModel:
    return state.eco_model


def feature_store_dep(state: Annotated[AppState, Depends(state_dep)]) -> InMemoryFeatureStore:
    return state.feature_store


def kanon_guard_dep(state: Annotated[AppState, Depends(state_dep)]) -> KAnonGuard:
    return state.kanon_guard


def logger_dep():
    return get_logger()


async def org_from_api_key(
    settings: Annotated[Settings, Depends(settings_dep)],
    state: Annotated[AppState, Depends(state_dep)],
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> Org:
    """Authenticate the caller with an API key and return their org.

    Authentication is a soft requirement at MVP scope: when ``ROADPULSE_REQUIRE_API_KEY``
    is unset (the default), unauthenticated callers receive a synthetic ``public-demo``
    org. Production turns the flag on and the seeded keys become mandatory.
    """
    if not settings.require_api_key and not x_api_key:
        return state.demo_org
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-API-Key header is required",
        )
    org = state.lookup_api_key(x_api_key)
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid API key",
        )
    return org
