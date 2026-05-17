"""Single source of truth for the "real vs synthetic" data origin flag.

The MVP build runs entirely on synthetic-but-realistic fixtures committed under
``data/seed/``. Every public endpoint surfaces this fact through
``HealthResponse.data_origin`` and every service entry-point logs it at startup
so jury & operators can never confuse a demo with a real-feed deployment.

To flip a feed to real, add its identifier to ``REAL_FEEDS`` (from env via
``ROADPULSE_REAL_FEEDS``, comma-separated) and remove it from
``PENDING_REAL_FEEDS``.
"""

from __future__ import annotations

import os
from typing import Final, Literal

DataOrigin = Literal["synthetic", "real"]

# Default feeds that we know we eventually need to plug in. Tracked for the
# pitch: each one corresponds to one MoU / data-share negotiation in flight.
PENDING_REAL_FEEDS: Final[tuple[str, ...]] = (
    "vetc.hex.5min",
    "sentinel1.sar.water_mask",
    "vnms.weather.hourly",
    "fleet_sdk.probes",
)


def real_feeds() -> list[str]:
    """Return the list of feeds that are currently wired to real data."""
    raw = os.getenv("ROADPULSE_REAL_FEEDS", "").strip()
    if not raw:
        return []
    return [piece.strip() for piece in raw.split(",") if piece.strip()]


def data_origin() -> DataOrigin:
    """Aggregate flag: ``synthetic`` until at least one real feed is wired."""
    return "real" if real_feeds() else "synthetic"


def pending_real_feeds() -> list[str]:
    """Return feeds that are still synthetic-only."""
    wired = set(real_feeds())
    return [feed for feed in PENDING_REAL_FEEDS if feed not in wired]
