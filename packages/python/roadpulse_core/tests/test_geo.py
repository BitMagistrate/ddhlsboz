"""Property-based tests for the dependency-light geo helpers."""

from __future__ import annotations

import math

import pytest
from hypothesis import given
from hypothesis import strategies as st
from roadpulse_core.geo import (
    BoundingBox,
    Coordinate,
    encode_polyline,
    haversine_m,
    hex_centre,
    point_to_hex,
)

VN_LNG = st.floats(min_value=102.0, max_value=110.0, allow_nan=False, allow_infinity=False)
VN_LAT = st.floats(min_value=8.0, max_value=24.0, allow_nan=False, allow_infinity=False)


@given(VN_LNG, VN_LAT)
def test_haversine_self_distance_is_zero(lng: float, lat: float) -> None:
    point = Coordinate(lng=lng, lat=lat)
    assert haversine_m(point, point) == pytest.approx(0.0, abs=1e-6)


def test_haversine_known_pair_ho_chi_minh_to_hanoi() -> None:
    hcmc = Coordinate(lng=106.700981, lat=10.776530)
    hanoi = Coordinate(lng=105.854444, lat=21.028511)
    # Reference distance ≈ 1149 km. Allow 1% slack.
    assert haversine_m(hcmc, hanoi) == pytest.approx(1_149_000.0, rel=0.01)


@given(VN_LNG, VN_LAT, VN_LNG, VN_LAT)
def test_haversine_symmetric(lng_a: float, lat_a: float, lng_b: float, lat_b: float) -> None:
    a = Coordinate(lng=lng_a, lat=lat_a)
    b = Coordinate(lng=lng_b, lat=lat_b)
    assert haversine_m(a, b) == pytest.approx(haversine_m(b, a), rel=1e-9)


def test_polyline_round_trips_known_string() -> None:
    # Example from Google's polyline algorithm reference.
    points = [
        Coordinate(lng=-120.2, lat=38.5),
        Coordinate(lng=-120.95, lat=40.7),
        Coordinate(lng=-126.453, lat=43.252),
    ]
    encoded = encode_polyline(points)
    assert encoded == "_p~iF~ps|U_ulLnnqC_mqNvxq`@"


def test_polyline_empty_returns_empty_string() -> None:
    assert encode_polyline([]) == ""


def test_bounding_box_contains() -> None:
    bbox = BoundingBox(min_lng=106.5, min_lat=10.7, max_lng=106.9, max_lat=10.95)
    assert bbox.contains(Coordinate(lng=106.7, lat=10.78))
    assert not bbox.contains(Coordinate(lng=107.0, lat=10.78))
    assert not bbox.contains(Coordinate(lng=106.7, lat=11.0))


def test_point_to_hex_is_deterministic() -> None:
    p = Coordinate(lng=106.700981, lat=10.776530)
    assert point_to_hex(p, 9) == point_to_hex(p, 9)


def test_point_to_hex_centre_round_trip() -> None:
    p = Coordinate(lng=106.700981, lat=10.776530)
    hex_id = point_to_hex(p, 9)
    centre = hex_centre(hex_id)
    # Hex centre should be within ~250 m of the input point for resolution 9.
    assert haversine_m(centre, p) < 1_000.0
    assert math.isfinite(centre.lat)
    assert math.isfinite(centre.lng)
