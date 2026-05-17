"""Weather ingestion entry point (MVP stub)."""

from __future__ import annotations

import time
from dataclasses import dataclass

from roadpulse_telemetry.logger import get_logger


@dataclass(slots=True)
class WeatherRollup:
    district_code: str
    hour_start_ms: int
    precipitation_mm_h: float
    wind_kmh: float
    temperature_c: float


def poll_nmhs() -> list[WeatherRollup]:
    """Return today's hourly rollups for HCMC districts.

    In production this hits `https://nmhs.gov.vn/api/forecast`. The MVP returns
    a synthetic dry-monsoon distribution so the demo is reproducible without an
    external dependency.
    """
    now_ms = int(time.time() * 1_000)
    return [
        WeatherRollup(
            district_code=f"79{700 + i:03d}",
            hour_start_ms=now_ms,
            precipitation_mm_h=0.0 if i % 4 else 8.0,
            wind_kmh=12.0,
            temperature_c=29.0,
        )
        for i in range(24)
    ]


def main() -> None:
    log = get_logger("ingestion-weather")
    log.info(
        "weather.startup",
        mode="synthetic-fixtures",
        data_origin="synthetic",
        pending_real_feed="vnms.weather.hourly",
    )
    for row in poll_nmhs():
        log.info("weather.row", district=row.district_code, precip=row.precipitation_mm_h)


if __name__ == "__main__":
    main()
