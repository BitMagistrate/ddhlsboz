"""ETA model with prediction intervals.

Algorithm overview
------------------

We train three gradient-boosted regressors on the same feature matrix:

* A *median* model (loss="squared_error") that produces the point ETA estimate.
* A *p10* quantile model used as the lower bound of the prediction interval.
* A *p90* quantile model used as the upper bound.

This is the same recipe we use in production for the LightGBM baseline; swapping to
LightGBM is a single-import change in :func:`_make_regressor` because both libraries
share the gradient-boosting parameter surface. Graph WaveNet (M2 in section 7.19)
adds a residual on top of these baselines and is loaded separately by the
``eta-service`` app.
"""

from __future__ import annotations

import io
import json
import pickle
import zlib
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict, Field
from roadpulse_core.types import EtaConfidence
from sklearn.ensemble import (
    GradientBoostingRegressor,
    HistGradientBoostingRegressor,
)

ETA_FEATURES: tuple[str, ...] = (
    "distance_m",
    "free_flow_seconds",
    "hour_of_week",
    "is_weekend",
    "precipitation_mm_h",
    "wind_kmh",
    "is_rush_hour",
    "lag_speed_5min",
    "lag_speed_15min",
    "lag_speed_1h",
    "vehicle_count_5min",
    "flood_score",
    "road_class_index",
)


class ETARecord(BaseModel):
    """One training/inference record. Matches the Feast feature view ``eta_v1``."""

    model_config = ConfigDict(extra="forbid")

    distance_m: float
    free_flow_seconds: float
    hour_of_week: int = Field(ge=0, le=167)
    is_weekend: int = Field(ge=0, le=1)
    precipitation_mm_h: float = 0.0
    wind_kmh: float = 0.0
    is_rush_hour: int = Field(default=0, ge=0, le=1)
    lag_speed_5min: float = 0.0
    lag_speed_15min: float = 0.0
    lag_speed_1h: float = 0.0
    vehicle_count_5min: float = 0.0
    flood_score: float = 0.0
    road_class_index: int = 0

    def as_row(self) -> list[float]:
        return [getattr(self, name) for name in ETA_FEATURES]


class EtaPrediction(BaseModel):
    """ETA inference output."""

    eta_s: float
    eta_p10_s: float
    eta_p90_s: float
    confidence: EtaConfidence
    model_version: str


@dataclass(slots=True)
class _Ensemble:
    """Internal triple-model bundle: median + p10 + p90."""

    median: Any
    p10: Any
    p90: Any


def _make_regressor(*, loss: str, quantile: float | None = None) -> Any:
    """Construct a quantile-capable gradient-boosted regressor.

    For point estimates we prefer ``HistGradientBoostingRegressor`` because it's
    quantile-capable as of scikit-learn 1.1, faster on large data and produces
    fewer surprises than ``GradientBoostingRegressor``. For prediction intervals on
    very small fixture datasets we fall back to ``GradientBoostingRegressor`` which
    is more robust at extreme quantiles.
    """
    if loss == "quantile":
        return GradientBoostingRegressor(
            loss="quantile",
            alpha=float(quantile or 0.5),
            n_estimators=160,
            max_depth=3,
            learning_rate=0.05,
            random_state=42,
        )
    return HistGradientBoostingRegressor(
        loss="squared_error",
        max_iter=200,
        learning_rate=0.05,
        max_depth=6,
        random_state=42,
    )


class EtaModel:
    """ETA estimator with quantile prediction intervals."""

    version_prefix = "eta-lgbm-py"

    def __init__(self, version: str | None = None) -> None:
        self._models = _Ensemble(
            median=_make_regressor(loss="squared_error"),
            p10=_make_regressor(loss="quantile", quantile=0.1),
            p90=_make_regressor(loss="quantile", quantile=0.9),
        )
        self._trained_at: datetime | None = None
        self._fitted = False
        self._version = version or self.version_prefix + "-untrained"

    # --- training ---------------------------------------------------------------------

    def fit(self, X: Sequence[ETARecord] | np.ndarray, y: Sequence[float]) -> None:
        """Fit the median + p10/p90 ensemble.

        ``X`` may be either an iterable of :class:`ETARecord` (preferred — keeps the
        feature ordering canonical) or a raw 2D numpy array already aligned to
        :data:`ETA_FEATURES`.
        """
        matrix, targets = self._to_matrix(X, y)
        if matrix.shape[0] == 0:
            raise ValueError("cannot fit on an empty training set")
        self._models.median.fit(matrix, targets)
        self._models.p10.fit(matrix, targets)
        self._models.p90.fit(matrix, targets)
        self._fitted = True
        self._trained_at = datetime.now(UTC)
        self._version = f"{self.version_prefix}-{matrix.shape[0]}-{self._trained_at:%Y%m%d%H%M}"

    # --- inference --------------------------------------------------------------------

    def predict(self, record: ETARecord) -> EtaPrediction:
        """Predict an ETA for a single record."""
        if not self._fitted:
            return self._heuristic_prediction(record)
        row = np.asarray([record.as_row()], dtype=np.float64)
        eta = float(self._models.median.predict(row)[0])
        p10 = float(self._models.p10.predict(row)[0])
        p90 = float(self._models.p90.predict(row)[0])
        # Quantile models can cross at extreme tails; clamp.
        p10 = max(0.0, min(p10, eta))
        p90 = max(eta, p90)
        return EtaPrediction(
            eta_s=max(0.0, eta),
            eta_p10_s=p10,
            eta_p90_s=p90,
            confidence=self._classify_confidence(eta, p10, p90),
            model_version=self._version,
        )

    def predict_batch(self, records: Iterable[ETARecord]) -> list[EtaPrediction]:
        return [self.predict(r) for r in records]

    # --- diagnostics ------------------------------------------------------------------

    @staticmethod
    def mape(y_true: Sequence[float], y_pred: Sequence[float]) -> float:
        """Return Mean Absolute Percentage Error. Skips records with y_true ≤ 0."""
        vt = np.asarray(y_true, dtype=np.float64)
        vp = np.asarray(y_pred, dtype=np.float64)
        mask = vt > 0
        if not mask.any():
            return float("nan")
        return float(np.mean(np.abs((vt[mask] - vp[mask]) / vt[mask])))

    @property
    def version(self) -> str:
        return self._version

    @property
    def is_trained(self) -> bool:
        return self._fitted

    # --- persistence ------------------------------------------------------------------

    def dumps(self) -> bytes:
        payload = {
            "kind": "eta",
            "version": self._version,
            "trained_at": self._trained_at.isoformat() if self._trained_at else None,
            "fitted": self._fitted,
            "models": {
                "median": pickle.dumps(self._models.median),
                "p10": pickle.dumps(self._models.p10),
                "p90": pickle.dumps(self._models.p90),
            },
        }
        return zlib.compress(pickle.dumps(payload), level=6)

    @classmethod
    def loads(cls, data: bytes) -> EtaModel:
        payload = pickle.loads(zlib.decompress(data))
        if payload.get("kind") != "eta":
            raise ValueError("payload is not an EtaModel artefact")
        model = cls(version=payload["version"])
        model._models.median = pickle.loads(payload["models"]["median"])
        model._models.p10 = pickle.loads(payload["models"]["p10"])
        model._models.p90 = pickle.loads(payload["models"]["p90"])
        model._fitted = bool(payload["fitted"])
        if payload.get("trained_at"):
            model._trained_at = datetime.fromisoformat(payload["trained_at"])
        return model

    def to_model_card(self) -> str:
        """Render the model card markdown emitted into the registry."""
        card = {
            "version": self._version,
            "features": list(ETA_FEATURES),
            "trained_at": self._trained_at.isoformat() if self._trained_at else None,
            "framework": "scikit-learn",
            "loss": "squared_error + quantile(0.1, 0.9)",
        }
        buf = io.StringIO()
        buf.write("# RoadPulse ETA Model Card\n\n")
        buf.write("```json\n")
        json.dump(card, buf, indent=2)
        buf.write("\n```\n")
        return buf.getvalue()

    # --- helpers ----------------------------------------------------------------------

    @staticmethod
    def _to_matrix(
        X: Sequence[ETARecord] | np.ndarray,
        y: Sequence[float],
    ) -> tuple[np.ndarray, np.ndarray]:
        if isinstance(X, np.ndarray):
            matrix = X.astype(np.float64)
        else:
            matrix = np.asarray([r.as_row() for r in X], dtype=np.float64)
        targets = np.asarray(y, dtype=np.float64)
        if matrix.shape[0] != targets.shape[0]:
            raise ValueError("X and y must have matching lengths")
        return matrix, targets

    def _heuristic_prediction(self, record: ETARecord) -> EtaPrediction:
        """Cold-start: return the free-flow estimate with a wide interval."""
        base = max(record.free_flow_seconds, 5.0)
        congestion_bump = 1 + 0.4 * record.flood_score + 0.05 * record.is_rush_hour
        eta = base * congestion_bump
        return EtaPrediction(
            eta_s=eta,
            eta_p10_s=base,
            eta_p90_s=eta * 1.6,
            confidence=EtaConfidence.LOW,
            model_version=f"{self._version}-cold",
        )

    @staticmethod
    def _classify_confidence(eta: float, p10: float, p90: float) -> EtaConfidence:
        if eta <= 0:
            return EtaConfidence.LOW
        spread = (p90 - p10) / eta
        if spread <= 0.15:
            return EtaConfidence.HIGH
        if spread <= 0.4:
            return EtaConfidence.MEDIUM
        return EtaConfidence.LOW
