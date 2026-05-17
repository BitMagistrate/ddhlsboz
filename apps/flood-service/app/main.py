"""FastAPI app for the flood-scoring micro-service."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel, Field
from roadpulse_ml.flood import FloodDetector, FloodObservation
from roadpulse_telemetry.logger import get_logger


class ObservationIn(BaseModel):
    hex_id: str
    speed_drop_pct: float = Field(..., ge=0.0, le=1.0)
    sar_water_prior: float = Field(..., ge=0.0, le=1.0)
    crowd_reports: int = Field(0, ge=0)
    precipitation_mm_h: float = 0.0


class ScoreOut(BaseModel):
    hex_id: str
    score: float
    confidence: float


def _bootstrap_detector() -> FloodDetector:
    obs: list[FloodObservation] = []
    # Synthetic dry hexes
    for i in range(80):
        obs.append(
            FloodObservation(
                hex_id=f"dry_{i:02d}",
                speed_drop_pct=0.05,
                sar_water_prior=0.03,
                crowd_reports=0,
                precipitation_mm_h=0.5,
            )
        )
    # Synthetic wet hexes
    for i in range(15):
        obs.append(
            FloodObservation(
                hex_id=f"wet_{i:02d}",
                speed_drop_pct=0.7,
                sar_water_prior=0.6,
                crowd_reports=3,
                precipitation_mm_h=20.0,
            )
        )
    d = FloodDetector(contamination=0.15)
    d.fit(obs)
    return d


_detector: FloodDetector | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _detector
    logger = get_logger("flood-service")
    logger.info("flood.startup")
    _detector = _bootstrap_detector()
    yield
    logger.info("flood.shutdown")


app = FastAPI(title="RoadPulse Flood Service", version="0.1.0", lifespan=lifespan)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/score", response_model=ScoreOut)
def score(body: ObservationIn) -> ScoreOut:
    assert _detector is not None
    obs = FloodObservation(**body.model_dump())
    s = _detector.score(obs)
    return ScoreOut(hex_id=body.hex_id, score=s.score, confidence=s.confidence)
