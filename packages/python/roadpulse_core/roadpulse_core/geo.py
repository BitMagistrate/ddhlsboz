"""Lightweight geospatial helpers used across the routing & ML stack.

The functions in this module are deliberately dependency-free: they only use the
standard library so they can be invoked from hot paths and from edge code that may
not have access to libraries like ``shapely`` or ``h3`` (CI, ingestion validators).

Where heavier geometry support is required (polygonal isochrones, GeoJSON I/O), use
:mod:`shapely` directly in the calling code.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass

EARTH_RADIUS_M = 6_371_000.0


@dataclass(frozen=True, slots=True)
class Coordinate:
    """WGS-84 coordinate in ``[longitude, latitude]`` order (GeoJSON style).

    We follow the GeoJSON convention everywhere: tuples are always
    ``(lng, lat)``. Construct via ``Coordinate(lng, lat)`` rather than positional
    inversion.
    """

    lng: float
    lat: float

    def as_tuple(self) -> tuple[float, float]:
        return (self.lng, self.lat)


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """Axis-aligned bounding box in WGS-84 (``[min_lng, min_lat, max_lng, max_lat]``)."""

    min_lng: float
    min_lat: float
    max_lng: float
    max_lat: float

    def contains(self, point: Coordinate) -> bool:
        return (
            self.min_lng <= point.lng <= self.max_lng and self.min_lat <= point.lat <= self.max_lat
        )


def haversine_m(a: Coordinate, b: Coordinate) -> float:
    """Great-circle distance in metres between two WGS-84 points."""
    phi_a = math.radians(a.lat)
    phi_b = math.radians(b.lat)
    dphi = math.radians(b.lat - a.lat)
    dlam = math.radians(b.lng - a.lng)
    sin_dphi = math.sin(dphi / 2)
    sin_dlam = math.sin(dlam / 2)
    h = sin_dphi * sin_dphi + math.cos(phi_a) * math.cos(phi_b) * sin_dlam * sin_dlam
    return 2.0 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(h)))


def encode_polyline(points: Iterable[Coordinate], *, precision: int = 5) -> str:
    """Encode a sequence of coordinates as a Google-style polyline string.

    Matches the OSRM / Mapbox default precision of 5 (≈ 1.1 cm). For higher precision
    pass ``precision=6`` (used by Mapbox SDKs).
    """
    factor = 10**precision
    output: list[str] = []
    prev_lat = 0
    prev_lng = 0
    for point in points:
        lat = round(point.lat * factor)
        lng = round(point.lng * factor)
        output.append(_encode_signed(lat - prev_lat))
        output.append(_encode_signed(lng - prev_lng))
        prev_lat = lat
        prev_lng = lng
    return "".join(output)


def _encode_signed(value: int) -> str:
    """Encode a single signed integer the same way Google's polyline algorithm does."""
    sgn = value << 1
    if value < 0:
        sgn = ~sgn
    chunks: list[str] = []
    while sgn >= 0x20:
        chunks.append(chr((0x20 | (sgn & 0x1F)) + 63))
        sgn >>= 5
    chunks.append(chr(sgn + 63))
    return "".join(chunks)


def point_to_hex(point: Coordinate, resolution: int = 9) -> str:
    """Return the H3 cell id (string) for a point at the given resolution.

    We re-export this helper so callers don't have to keep importing ``h3`` directly
    and we can swap to a vendored implementation if needed. Falls back to a coarse,
    deterministic mock hash when the optional ``h3`` dependency is missing — useful in
    minimal test environments — but always emits a valid 15-character lowercase hex
    string suitable for use as a key.
    """
    try:
        import h3  # type: ignore[import-untyped]
    except ImportError:  # pragma: no cover - exercised in slim CI runs
        return _mock_hex(point, resolution)
    return h3.geo_to_h3(point.lat, point.lng, resolution)


def hex_centre(hex_id: str) -> Coordinate:
    """Return the centroid (lng, lat) of an H3 cell.

    Falls back to a deterministic centroid derived from the mock hex id when the
    ``h3`` dependency is unavailable.
    """
    try:
        import h3  # type: ignore[import-untyped]
    except ImportError:  # pragma: no cover
        return _mock_hex_centre(hex_id)
    lat, lng = h3.h3_to_geo(hex_id)
    return Coordinate(lng=lng, lat=lat)


# --- mock fallback --------------------------------------------------------------------


def _mock_hex(point: Coordinate, resolution: int) -> str:
    """Deterministic fallback when ``h3`` isn't installed.

    Snaps the input to a grid roughly the size of an H3 res-``resolution`` cell and
    returns a 15-character lower-hex string. Two points in the same cell yield the
    same id, which is the only contract callers rely on for k-anon bucketing.
    """
    step = 0.001 * (10 - resolution)  # ≈ 110 m at res 9, larger at coarser resolutions
    lat_bucket = round(point.lat / step)
    lng_bucket = round(point.lng / step)
    raw = (lat_bucket * 1_000_003 + lng_bucket) & 0xFFFFFFFFFFFFFFF
    return f"{raw:015x}"


def _mock_hex_centre(hex_id: str) -> Coordinate:
    raw = int(hex_id, 16)
    lat = ((raw // 1_000_003) % 90_000) / 1_000.0
    lng = ((raw % 1_000_003) % 180_000) / 1_000.0
    return Coordinate(lng=lng, lat=lat)
