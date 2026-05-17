"""VETC ingestion entry point.

The MVP build reads a local CSV mirror; the production wiring tails the SFTP
drop and forwards onto Redpanda. Either way every batch is k-anon-checked.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from pathlib import Path

from roadpulse_privacy.guard import KAnonGuard
from roadpulse_telemetry.logger import get_logger


def stream_buckets(csv_path: Path) -> Iterable[dict[str, object]]:
    """Yield one rollup dict per CSV row."""
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield {
                "hex_id": row["hex_id"],
                "bucket_start_ms": int(row["bucket_start_ms"]),
                "vehicle_class": row.get("vehicle_class", "MOTORBIKE"),
                "avg_speed_kmh": float(row["avg_speed_kmh"]),
                "vehicle_count": int(row["vehicle_count"]),
            }


def run(csv_path: Path, *, min_k: int = 50) -> dict[str, int]:
    """Filter the CSV through the k-anon guard and return summary counts."""
    logger = get_logger("ingestion-vetc")
    guard = KAnonGuard(min_k=min_k, source="vetc")
    accepted = 0
    rejected = 0
    for bucket in stream_buckets(csv_path):
        decision = guard.check(
            bucket=str(bucket["hex_id"]), observed_k=int(bucket["vehicle_count"])
        )
        if decision.allowed:
            accepted += 1
        else:
            rejected += 1
    logger.info("vetc.batch_done", accepted=accepted, rejected=rejected, min_k=min_k)
    return {"accepted": accepted, "rejected": rejected}


if __name__ == "__main__":
    import sys

    summary = run(Path(sys.argv[1]))
    print(summary)
