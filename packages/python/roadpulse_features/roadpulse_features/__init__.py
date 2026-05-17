"""Feast feature view definitions + a lightweight in-memory feature store.

Production deployments use Feast on Redis (online) + Parquet on MinIO (offline). For
local development and unit testing the :class:`InMemoryFeatureStore` provides the
same ``get_online_features`` / ``materialise`` API without spinning up infra.
"""

from roadpulse_features.feature_views import (
    FeatureSpec,
    FeatureView,
    FloodScoreFeatures,
    HexSpeed5MinFeatures,
    WeatherFeatures,
)
from roadpulse_features.store import InMemoryFeatureStore

__all__ = [
    "FeatureSpec",
    "FeatureView",
    "FloodScoreFeatures",
    "HexSpeed5MinFeatures",
    "InMemoryFeatureStore",
    "WeatherFeatures",
]
