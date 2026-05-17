"""Common types, enums and small value objects used across the RoadPulse stack."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------- enums --


class RouteMode(str, Enum):
    """Mode of transport supported by the routing engine."""

    MOTORBIKE = "motorbike"
    CAR = "car"
    TRUCK = "truck"
    BICYCLE = "bicycle"


class VehicleClass(str, Enum):
    """K-anonymised vehicle class bucket used in VETC aggregates."""

    MOTOR = "motor"
    CAR = "car"
    TRUCK = "truck"


class FloodSeverity(str, Enum):
    """Trigger severity used by the parametric insurance trigger feed."""

    LOW = "low"
    MED = "med"
    HIGH = "high"


class EtaConfidence(str, Enum):
    """Categorical confidence label attached to ETA predictions."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TimeOfDay(str, Enum):
    """Departure time bucket. ``NOW`` means the request is for an immediate trip."""

    NOW = "now"
    MORNING = "morning"
    NOON = "noon"
    EVENING = "evening"
    NIGHT = "night"


OrgTier = Literal["internal", "b2c", "b2b", "b2b2c", "research"]


# ----------------------------------------------------------------------- value objects


class LatLon(BaseModel):
    """A geographic coordinate (WGS-84). Latitude first, longitude second."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    lat: float = Field(ge=-90.0, le=90.0)
    lng: float = Field(ge=-180.0, le=180.0)


class Org(BaseModel):
    """Tenant / org metadata. Loaded from the seed bundle on startup."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    id: str
    name: str
    tier: str
    country: str = "VN"
    created_at: datetime | None = None


__all__ = [
    "EtaConfidence",
    "FloodSeverity",
    "LatLon",
    "Org",
    "OrgTier",
    "RouteMode",
    "TimeOfDay",
    "VehicleClass",
]
