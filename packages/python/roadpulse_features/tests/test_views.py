"""Schema-level tests for the published Feast feature views."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from roadpulse_features.feature_views import (
    FLOOD_SCORE,
    HEX_SPEED_5MIN,
    WEATHER_HOURLY,
    FloodScoreFeatures,
    HexSpeed5MinFeatures,
    WeatherFeatures,
)


def test_hex_speed_view_enforces_k_anon_floor() -> None:
    """``vehicle_count`` must be ≥ 50 (the global k-anonymity floor)."""
    with pytest.raises(ValidationError):
        HexSpeed5MinFeatures(
            bucket_start_utc=datetime(2025, 5, 17, tzinfo=UTC),
            hex_id="hex_demo",
            avg_speed_kmh=22.0,
            speed_p10=12.0,
            speed_p50=22.0,
            speed_p90=33.0,
            flow_in=10,
            flow_out=8,
            vehicle_count=12,  # below 50 -> must fail
        )


def test_hex_speed_view_accepts_compliant_row() -> None:
    row = HexSpeed5MinFeatures(
        bucket_start_utc=datetime(2025, 5, 17, tzinfo=UTC),
        hex_id="hex_demo",
        avg_speed_kmh=22.0,
        speed_p10=12.0,
        speed_p50=22.0,
        speed_p90=33.0,
        flow_in=120,
        flow_out=140,
        vehicle_count=210,
    )
    assert row.vehicle_count == 210


def test_flood_score_rejects_out_of_range_score() -> None:
    with pytest.raises(ValidationError):
        FloodScoreFeatures(
            bucket_start_utc=datetime(2025, 5, 17, tzinfo=UTC),
            hex_id="hex_demo",
            score=1.4,
            confidence=0.8,
            horizon_1h=0.7,
            horizon_3h=0.6,
            horizon_6h=0.4,
        )


def test_weather_view_rejects_negative_precipitation() -> None:
    with pytest.raises(ValidationError):
        WeatherFeatures(
            bucket_start_utc=datetime(2025, 5, 17, tzinfo=UTC),
            district_id="d1",
            temp_c=29.0,
            precip_mm_h=-1.0,
            wind_kmh=10.0,
            visibility_m=8000.0,
        )


def test_manifests_are_internally_consistent() -> None:
    """Each FeatureView's ``features`` list must use canonical names."""
    for fv in [HEX_SPEED_5MIN, FLOOD_SCORE, WEATHER_HOURLY]:
        assert fv.name
        assert fv.entity
        assert fv.features, f"{fv.name} should list at least one feature"
        names = [f.name for f in fv.features]
        # No duplicates
        assert len(names) == len(set(names)), f"{fv.name} has duplicate feature names"


def test_extra_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        FloodScoreFeatures(
            bucket_start_utc=datetime(2025, 5, 17, tzinfo=UTC),
            hex_id="hex_demo",
            score=0.5,
            confidence=0.6,
            horizon_1h=0.4,
            horizon_3h=0.3,
            horizon_6h=0.2,
            secret_field="leak",  # type: ignore[call-arg]
        )
