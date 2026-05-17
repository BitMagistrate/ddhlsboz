"""Feast feature views.

We keep the views as Pydantic models so they're trivially importable from notebooks
and unit tests, while still being one ``feast apply`` away from the actual Feast
``Entity`` + ``FeatureView`` declarations in ``services/feast/repo.py``.
"""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field


class FeatureSpec(BaseModel):
    """A single column in a feature view."""

    name: str
    dtype: str
    description: str


class FeatureView(BaseModel):
    """A named bundle of features keyed by entity."""

    name: str
    entity: str
    features: list[FeatureSpec]
    ttl_seconds: int = 3600


class HexSpeed5MinFeatures(BaseModel):
    """``hex_speed_5min`` — VETC-derived 5-minute aggregates keyed by ``hex_id``."""

    model_config = ConfigDict(extra="forbid")

    name: ClassVar[str] = "hex_speed_5min"
    entity: ClassVar[str] = "hex_id"

    bucket_start_utc: datetime
    hex_id: str
    avg_speed_kmh: float
    speed_p10: float
    speed_p50: float
    speed_p90: float
    flow_in: int = Field(ge=0)
    flow_out: int = Field(ge=0)
    vehicle_count: int = Field(ge=50)  # k-anonymity guard enforces ≥50


class FloodScoreFeatures(BaseModel):
    """``flood_score`` — current and 1/3/6-hour horizon flood probabilities per hex."""

    model_config = ConfigDict(extra="forbid")

    name: ClassVar[str] = "flood_score"
    entity: ClassVar[str] = "hex_id"

    bucket_start_utc: datetime
    hex_id: str
    score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    horizon_1h: float = Field(ge=0.0, le=1.0)
    horizon_3h: float = Field(ge=0.0, le=1.0)
    horizon_6h: float = Field(ge=0.0, le=1.0)


class WeatherFeatures(BaseModel):
    """``weather`` — hourly aggregates keyed by district id."""

    model_config = ConfigDict(extra="forbid")

    name: ClassVar[str] = "weather_district_hourly"
    entity: ClassVar[str] = "district_id"

    bucket_start_utc: datetime
    district_id: str
    temp_c: float
    precip_mm_h: float = Field(ge=0.0)
    wind_kmh: float = Field(ge=0.0)
    visibility_m: float = Field(ge=0.0)


# --- Feature view manifests used by ``services/feast/repo.py`` -----------------------

HEX_SPEED_5MIN = FeatureView(
    name="hex_speed_5min",
    entity="hex_id",
    ttl_seconds=24 * 3600,
    features=[
        FeatureSpec(
            name="avg_speed_kmh",
            dtype="float32",
            description="Average speed of vehicles in the hex over the 5-minute bucket",
        ),
        FeatureSpec(name="speed_p10", dtype="float32", description="10th percentile speed"),
        FeatureSpec(name="speed_p50", dtype="float32", description="50th percentile speed"),
        FeatureSpec(name="speed_p90", dtype="float32", description="90th percentile speed"),
        FeatureSpec(
            name="flow_in", dtype="int32", description="Vehicles entering the hex during the bucket"
        ),
        FeatureSpec(
            name="flow_out", dtype="int32", description="Vehicles leaving the hex during the bucket"
        ),
        FeatureSpec(
            name="vehicle_count",
            dtype="int32",
            description="Unique vehicles seen (k-anonymity ≥ 50)",
        ),
    ],
)

FLOOD_SCORE = FeatureView(
    name="flood_score",
    entity="hex_id",
    ttl_seconds=3600,
    features=[
        FeatureSpec(name="score", dtype="float32", description="Current flood probability"),
        FeatureSpec(name="confidence", dtype="float32", description="Detector confidence"),
        FeatureSpec(name="horizon_1h", dtype="float32", description="1-hour-ahead probability"),
        FeatureSpec(name="horizon_3h", dtype="float32", description="3-hour-ahead probability"),
        FeatureSpec(name="horizon_6h", dtype="float32", description="6-hour-ahead probability"),
    ],
)

WEATHER_HOURLY = FeatureView(
    name="weather_district_hourly",
    entity="district_id",
    ttl_seconds=2 * 3600,
    features=[
        FeatureSpec(name="temp_c", dtype="float32", description="Temperature in Celsius"),
        FeatureSpec(name="precip_mm_h", dtype="float32", description="Precipitation rate"),
        FeatureSpec(name="wind_kmh", dtype="float32", description="Wind speed"),
        FeatureSpec(name="visibility_m", dtype="float32", description="Horizontal visibility"),
    ],
)
