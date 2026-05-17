"""Profile tunable / forbidden-class regression tests."""

from __future__ import annotations

from roadpulse_core.types import RouteMode
from roadpulse_routing.profiles import (
    DEFAULT_SPEEDS_KMH,
    PROFILES,
    bicycle_vn,
    car_vn,
    motorbike_vn,
    truck_vn,
)


def test_every_mode_has_a_profile() -> None:
    assert set(PROFILES) == set(RouteMode)


def test_motorbike_is_forbidden_on_motorway() -> None:
    assert not motorbike_vn.is_usable("motorway", {})


def test_truck_skips_hem_alleys_and_service_roads() -> None:
    for cls in ("hem", "service", "track", "living_street"):
        assert not truck_vn.is_usable(cls, {})


def test_car_is_blocked_when_motor_vehicle_no_tag() -> None:
    assert not car_vn.is_usable("residential", {"motor_vehicle": "no"})


def test_bicycle_speed_is_capped() -> None:
    # No bicycle road class should exceed 16 km/h in our profile.
    assert max(bicycle_vn.speeds_kmh.values()) <= 16.0


def test_truck_hgv_destination_tag_blocks_routing() -> None:
    assert not truck_vn.is_usable("primary", {"hgv": "destination"})


def test_free_flow_speed_falls_back_to_default() -> None:
    # Unknown class should hit the per-profile dict miss → DEFAULT_SPEEDS_KMH miss → 25.0.
    speed = motorbike_vn.free_flow_speed("nonexistent_class")
    assert speed == DEFAULT_SPEEDS_KMH.get("nonexistent_class", 25.0)


def test_flood_penalty_higher_for_motorbike_than_truck() -> None:
    """Motorbikes are most vulnerable to flooding — beta must reflect that."""
    assert motorbike_vn.beta_flood > truck_vn.beta_flood
    assert motorbike_vn.beta_flood > car_vn.beta_flood


def test_eco_factor_increases_with_vehicle_size() -> None:
    assert truck_vn.eco_factor > car_vn.eco_factor > motorbike_vn.eco_factor
