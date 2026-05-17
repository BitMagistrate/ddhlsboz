"""ETA, flood-detection and eco-score models.

Two production model families live here:

* :class:`EtaModel` — a per-hex Gradient Boosted Trees regressor that returns ETA and
  a P10/P90 prediction interval. At Build Week scope we use scikit-learn's
  ``HistGradientBoostingRegressor`` (a LightGBM-compatible API). The interface is
  intentionally identical to the production LightGBM/Graph WaveNet pipeline so we
  can swap implementations without changing service code.
* :class:`FloodDetector` — Isolation Forest on speed-drop residuals fused with a
  Bayesian update from the Sentinel-1 SAR water mask.

Both export and load themselves with the same ``dumps``/``loads`` API so the model
registry doesn't need to know which family it's serving.
"""

from roadpulse_ml.eco import EcoModel, EmissionEstimate
from roadpulse_ml.eta import ETA_FEATURES, EtaModel, EtaPrediction, ETARecord
from roadpulse_ml.flood import FloodDetector, FloodObservation, FloodScore

__all__ = [
    "ETA_FEATURES",
    "ETARecord",
    "EcoModel",
    "EmissionEstimate",
    "EtaModel",
    "EtaPrediction",
    "FloodDetector",
    "FloodObservation",
    "FloodScore",
]
