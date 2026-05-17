"""Shared types, errors and geo utilities for the RoadPulse stack."""

from roadpulse_core.errors import (
    ProblemDetails,
    QuotaExceededError,
    RoadPulseError,
    ValidationProblem,
)
from roadpulse_core.geo import (
    BoundingBox,
    Coordinate,
    encode_polyline,
    haversine_m,
    hex_centre,
    point_to_hex,
)
from roadpulse_core.types import (
    EtaConfidence,
    FloodSeverity,
    RouteMode,
    VehicleClass,
)

__all__ = [
    "BoundingBox",
    "Coordinate",
    "EtaConfidence",
    "FloodSeverity",
    "ProblemDetails",
    "QuotaExceededError",
    "RoadPulseError",
    "RouteMode",
    "ValidationProblem",
    "VehicleClass",
    "encode_polyline",
    "haversine_m",
    "hex_centre",
    "point_to_hex",
]
