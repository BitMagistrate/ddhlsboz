"""Sentinel-1 SAR ingestion stub.

Production uses ``snap-engine`` + ``rasterio`` to classify each tile and roll
the result up to H3. For the MVP build we ship a deterministic stub so the
notebook & demo work offline; the real pipeline lives in
``ml/pipelines/sar_water_classifier`` and is invoked from Airflow nightly.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from roadpulse_telemetry.logger import get_logger


@dataclass(slots=True)
class SARTileScore:
    hex_id: str
    water_fraction: float


def classify_synthetic(hex_ids: list[str]) -> list[SARTileScore]:
    out: list[SARTileScore] = []
    for hex_id in hex_ids:
        seed = sum(ord(c) for c in hex_id)
        out.append(
            SARTileScore(
                hex_id=hex_id,
                water_fraction=0.5 + 0.45 * math.sin(seed * 0.41),
            )
        )
    return out


if __name__ == "__main__":
    log = get_logger("ingestion-sar")
    log.info(
        "sar.startup",
        mode="synthetic-fixtures",
        data_origin="synthetic",
        pending_real_feed="sentinel1.sar.water_mask",
    )
    for tile in classify_synthetic(["hex_22", "hex_23", "hex_32", "hex_42"]):
        log.info("sar.tile", hex_id=tile.hex_id, water=round(tile.water_fraction, 3))
