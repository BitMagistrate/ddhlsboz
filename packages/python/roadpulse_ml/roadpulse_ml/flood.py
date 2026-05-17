"""Flood detection.

Two-stage fusion:

1. ``IsolationForest`` flags hexes where the current speed distribution looks
   unusual relative to the historical median for the same hour-of-week. The output
   is an anomaly score ``∈ [0, 1]`` after a sigmoid squash.
2. A Bayesian update folds in the Sentinel-1 SAR water-mask prior — when SAR shows
   standing water in the same hex, the posterior probability gets a strong boost;
   when SAR says the hex is dry, we down-weight the speed anomaly.

The output ``hex_flood_score`` is published every 5 minutes on the
``flood.hex.score`` Kafka topic and read by the routing engine to compute the
``β·flood_score`` edge penalty.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np
from pydantic import BaseModel, ConfigDict, Field
from sklearn.ensemble import IsolationForest

DEFAULT_PRIOR_FLOOD_RATE = 0.04  # 4% of HCMC hexes in a typical wet-season hour


class FloodObservation(BaseModel):
    """One 5-minute observation for the detector."""

    model_config = ConfigDict(extra="forbid")

    hex_id: str
    speed_drop_pct: float = Field(ge=0.0, le=1.0)
    sar_water_prior: float = Field(default=DEFAULT_PRIOR_FLOOD_RATE, ge=0.0, le=1.0)
    crowd_reports: int = 0
    precipitation_mm_h: float = 0.0


class FloodScore(BaseModel):
    """Published score for a single hex bucket."""

    hex_id: str
    score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    sources: list[str]


@dataclass(slots=True)
class _ScoreInputs:
    matrix: np.ndarray
    hex_ids: list[str]
    priors: np.ndarray
    crowd: np.ndarray
    precip: np.ndarray


class FloodDetector:
    """Isolation Forest + Bayesian SAR fusion."""

    def __init__(self, contamination: float = 0.05) -> None:
        self._model = IsolationForest(
            n_estimators=128,
            contamination=contamination,
            random_state=42,
        )
        self._fitted = False

    def fit(self, observations: Iterable[FloodObservation]) -> None:
        """Train the anomaly detector on historical fixture data."""
        bundle = self._prepare(observations)
        if bundle.matrix.shape[0] == 0:
            raise ValueError("cannot fit on empty observations")
        self._model.fit(bundle.matrix)
        self._fitted = True

    def score(self, observations: Iterable[FloodObservation]) -> list[FloodScore]:
        bundle = self._prepare(observations)
        if not self._fitted:
            return [self._heuristic(o) for o in self._regenerate(bundle)]
        # IsolationForest.decision_function: higher = more normal. Flip the sign so
        # larger anomaly => higher score, then squash to [0, 1].
        raw = -self._model.decision_function(bundle.matrix)
        anomaly = 1.0 / (1.0 + np.exp(-3.5 * raw))  # sigmoid-like squash
        # Bayesian fusion: posterior given speed-anomaly p(flood|x) ∝ p(x|flood)·prior
        posterior = self._fuse(anomaly, bundle.priors, bundle.precip)
        # Crowd reports linearly bump score up to +0.2.
        crowd_bump = np.clip(bundle.crowd / 5.0, 0.0, 1.0) * 0.2
        score = np.clip(posterior + crowd_bump, 0.0, 1.0)
        confidence = self._confidence(anomaly, bundle.priors, bundle.crowd)
        return [
            FloodScore(
                hex_id=hex_id,
                score=float(round(s, 4)),
                confidence=float(round(c, 4)),
                sources=self._sources(prior, reports),
            )
            for hex_id, s, c, prior, reports in zip(
                bundle.hex_ids,
                score,
                confidence,
                bundle.priors,
                bundle.crowd,
                strict=True,
            )
        ]

    @property
    def is_trained(self) -> bool:
        return self._fitted

    # --- helpers ----------------------------------------------------------------------

    @staticmethod
    def _prepare(observations: Iterable[FloodObservation]) -> _ScoreInputs:
        recs = list(observations)
        if not recs:
            return _ScoreInputs(
                matrix=np.empty((0, 2), dtype=np.float64),
                hex_ids=[],
                priors=np.empty(0, dtype=np.float64),
                crowd=np.empty(0, dtype=np.float64),
                precip=np.empty(0, dtype=np.float64),
            )
        matrix = np.asarray(
            [[r.speed_drop_pct, r.precipitation_mm_h] for r in recs], dtype=np.float64
        )
        return _ScoreInputs(
            matrix=matrix,
            hex_ids=[r.hex_id for r in recs],
            priors=np.asarray([r.sar_water_prior for r in recs], dtype=np.float64),
            crowd=np.asarray([r.crowd_reports for r in recs], dtype=np.float64),
            precip=matrix[:, 1],
        )

    @staticmethod
    def _regenerate(bundle: _ScoreInputs) -> list[FloodObservation]:
        return [
            FloodObservation(
                hex_id=hid,
                speed_drop_pct=float(bundle.matrix[i, 0]),
                sar_water_prior=float(bundle.priors[i]),
                crowd_reports=int(bundle.crowd[i]),
                precipitation_mm_h=float(bundle.precip[i]),
            )
            for i, hid in enumerate(bundle.hex_ids)
        ]

    @staticmethod
    def _heuristic(observation: FloodObservation) -> FloodScore:
        # Cold start: speed drop and precipitation alone, no anomaly model yet.
        raw = 0.55 * observation.speed_drop_pct + 0.45 * min(
            observation.precipitation_mm_h / 25.0, 1.0
        )
        prior = observation.sar_water_prior
        # Naive Bayes with a Bernoulli prior on SAR.
        posterior = (raw * prior) / max(raw * prior + (1 - raw) * (1 - prior), 1e-9)
        score = min(1.0, posterior + min(observation.crowd_reports / 5.0, 1.0) * 0.2)
        return FloodScore(
            hex_id=observation.hex_id,
            score=round(score, 4),
            confidence=0.35,
            sources=FloodDetector._sources(prior, observation.crowd_reports),
        )

    @staticmethod
    def _fuse(anomaly: np.ndarray, prior: np.ndarray, precip: np.ndarray) -> np.ndarray:
        # Bayes: p(flood|x) = p(x|flood)·p(flood) / [p(x|flood)·p(flood) + p(x|¬flood)·(1-p(flood))]
        likelihood = anomaly * (0.6 + 0.4 * np.tanh(precip / 12.0))
        baseline = 1.0 - likelihood
        numerator = likelihood * prior
        denominator = numerator + baseline * (1.0 - prior)
        out = np.zeros_like(numerator)
        np.divide(numerator, denominator, where=denominator > 0, out=out)
        return out

    @staticmethod
    def _confidence(anomaly: np.ndarray, prior: np.ndarray, crowd: np.ndarray) -> np.ndarray:
        # Confidence is highest when SAR agrees and we have multiple crowd reports.
        agreement = 1.0 - np.abs(anomaly - prior)
        crowd_bonus = np.clip(crowd / 10.0, 0.0, 0.3)
        return np.clip(0.4 * agreement + 0.4 + crowd_bonus, 0.0, 1.0)

    @staticmethod
    def _sources(prior: float, crowd: float | int) -> list[str]:
        sources = ["speed"]
        if prior > 0.1:
            sources.append("sar")
        if crowd:
            sources.append("crowd")
        return sources

    @staticmethod
    def _sigmoid(x: float) -> float:
        return 1.0 / (1.0 + math.exp(-x))
