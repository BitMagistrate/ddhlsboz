"""Lightweight in-memory feature store.

This is used by ``apps/eta-service`` and ``apps/flood-service`` whenever the real
Feast / Redis pair is unreachable (local dev, golden e2e tests on CI). The API
deliberately mirrors :class:`feast.FeatureStore` so swapping is a one-line change.
"""

from __future__ import annotations

import threading
from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import Any


class InMemoryFeatureStore:
    """Thread-safe ``view_name → entity_key → feature_dict`` cache."""

    def __init__(self) -> None:
        self._tables: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
        self._lock = threading.RLock()

    def ingest(self, view: str, entity_key: str, row: Mapping[str, Any]) -> None:
        with self._lock:
            self._tables[view][entity_key] = dict(row)

    def ingest_many(
        self,
        view: str,
        rows: Iterable[tuple[str, Mapping[str, Any]]],
    ) -> None:
        with self._lock:
            for entity_key, row in rows:
                self._tables[view][entity_key] = dict(row)

    def get_online_features(
        self,
        view: str,
        entity_keys: Iterable[str],
        features: Iterable[str],
    ) -> dict[str, dict[str, Any]]:
        wanted = list(features)
        keys = list(entity_keys)
        with self._lock:
            view_data = self._tables.get(view, {})
            return {
                key: {feat: view_data.get(key, {}).get(feat) for feat in wanted} for key in keys
            }

    def keys(self, view: str) -> list[str]:
        with self._lock:
            return list(self._tables.get(view, {}).keys())

    def clear(self) -> None:
        with self._lock:
            self._tables.clear()
