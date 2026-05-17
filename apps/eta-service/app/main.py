"""FastAPI app for the ETA micro-service."""

from __future__ import annotations

import random
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel, Field
from roadpulse_ml.eta import EtaModel, ETARecord
from roadpulse_telemetry.logger import get_logger


class PredictRequest(BaseModel):
    """Body of `POST /predict` — mirrors :class:`ETARecord`."""

    distance_m: float = Field(..., ge=0.0)
    free_flow_seconds: float = Field(..., ge=0.0)
    hour_of_week: int = Field(0, ge=0, le=167)
    is_weekend: int = Field(0, ge=0, le=1)
    precipitation_mm_h: float = 0.0
    wind_kmh: float = 0.0
    is_rush_hour: int = 0
    lag_speed_5min: float = 0.0
    lag_speed_15min: float = 0.0
    lag_speed_1h: float = 0.0
    vehicle_count_5min: float = 0.0
    flood_score: float = 0.0
    road_class_index: int = 0


class PredictResponse(BaseModel):
    eta_s: float
    eta_p10_s: float
    eta_p90_s: float
    confidence: str


def _bootstrap_model() -> EtaModel:
    rng = random.Random(7)
    rows: list[ETARecord] = []
    targets: list[float] = []
    for _ in range(600):
        distance = rng.uniform(500, 12_000)
        flow = rng.uniform(15, 50)
        ff = distance / 1000 / flow * 3600
        rush = rng.choice([0, 0, 1])
        flood = rng.uniform(0, 0.6) if rush else 0.0
        rec = ETARecord(
            distance_m=distance,
            free_flow_seconds=ff,
            hour_of_week=rng.randint(0, 167),
            is_weekend=rng.choice([0, 1]),
            precipitation_mm_h=rng.uniform(0, 18),
            wind_kmh=rng.uniform(0, 25),
            is_rush_hour=rush,
            lag_speed_5min=flow - rng.uniform(0, 5),
            lag_speed_15min=flow - rng.uniform(0, 5),
            lag_speed_1h=flow,
            vehicle_count_5min=rng.uniform(80, 800),
            flood_score=flood,
            road_class_index=rng.randint(0, 6),
        )
        mult = 1 + 0.2 * rush + 0.5 * flood
        rows.append(rec)
        targets.append(ff * mult + rng.uniform(-10, 10))
    m = EtaModel()
    m.fit(rows, targets)
    return m


_model: EtaModel | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _model
    logger = get_logger("eta-service")
    logger.info("eta.startup")
    _model = _bootstrap_model()
    yield
    logger.info("eta.shutdown")


app = FastAPI(title="RoadPulse ETA Service", version="0.1.0", lifespan=lifespan)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/predict", response_model=PredictResponse)
def predict(body: PredictRequest) -> PredictResponse:
    assert _model is not None
    record = ETARecord(**body.model_dump())
    pred = _model.predict(record)
    return PredictResponse(
        eta_s=pred.eta_s,
        eta_p10_s=pred.eta_p10_s,
        eta_p90_s=pred.eta_p90_s,
        confidence=pred.confidence.value,
    )
