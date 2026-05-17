"""SDK collector entry point.

Uses an in-process aggregator that buckets probes by ``hex_id`` and only emits
hexes that meet the k-anon threshold. The gRPC surface itself is defined in
``proto/ingestion/v1/sdk_collector.proto``; for the MVP we expose the same
behaviour as a HTTP/JSON endpoint so the React Native SDK can talk to it
without grpc-web.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel, Field
from roadpulse_privacy.guard import KAnonGuard
from roadpulse_telemetry.logger import get_logger


class Probe(BaseModel):
    device_hash: str = Field(..., min_length=12)
    hex_id: str = Field(..., min_length=3)
    ts_ms: int
    speed_kmh: float = Field(..., ge=0.0, le=200.0)
    heading_deg: float = Field(..., ge=0.0, lt=360.0)
    vehicle_class: str = "MOTORBIKE"
    sdk_version: str = "0.1.0"


_buckets: dict[str, set[str]] = defaultdict(set)
_guard: KAnonGuard | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _guard
    logger = get_logger("sdk-collector")
    logger.info("sdk.startup")
    _guard = KAnonGuard(min_k=50, source="sdk-collector")
    yield
    logger.info("sdk.shutdown")


app = FastAPI(title="RoadPulse SDK Collector", version="0.1.0", lifespan=lifespan)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/probes")
def submit(probe: Probe) -> dict[str, bool]:
    assert _guard is not None
    _buckets[probe.hex_id].add(probe.device_hash)
    k = len(_buckets[probe.hex_id])
    decision = _guard.check(bucket=probe.hex_id, observed_k=k)
    return {"accepted": True, "published": decision.allowed}
