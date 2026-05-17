"""Tests for the in-memory feature store used as the Feast fallback."""

from __future__ import annotations

import threading

from roadpulse_features.store import InMemoryFeatureStore


def test_ingest_and_get_returns_features() -> None:
    store = InMemoryFeatureStore()
    store.ingest("hex_speed_5min", "hex_a", {"avg_speed_kmh": 24.0, "vehicle_count": 200})
    out = store.get_online_features(
        "hex_speed_5min", ["hex_a"], ["avg_speed_kmh", "vehicle_count"]
    )
    assert out == {"hex_a": {"avg_speed_kmh": 24.0, "vehicle_count": 200}}


def test_unknown_entity_returns_none_filled_dict() -> None:
    store = InMemoryFeatureStore()
    out = store.get_online_features(
        "hex_speed_5min", ["missing"], ["avg_speed_kmh", "vehicle_count"]
    )
    assert out == {"missing": {"avg_speed_kmh": None, "vehicle_count": None}}


def test_ingest_many_overwrites_per_key() -> None:
    store = InMemoryFeatureStore()
    rows = [
        ("hex_a", {"avg_speed_kmh": 20.0, "vehicle_count": 60}),
        ("hex_b", {"avg_speed_kmh": 35.0, "vehicle_count": 120}),
    ]
    store.ingest_many("hex_speed_5min", rows)
    store.ingest("hex_a", "hex_a", {"x": 1})  # different view, must not collide
    store.ingest("hex_speed_5min", "hex_a", {"avg_speed_kmh": 11.0, "vehicle_count": 200})
    out = store.get_online_features(
        "hex_speed_5min", ["hex_a", "hex_b"], ["avg_speed_kmh", "vehicle_count"]
    )
    assert out["hex_a"]["avg_speed_kmh"] == 11.0
    assert out["hex_b"]["avg_speed_kmh"] == 35.0


def test_keys_lists_view_entries() -> None:
    store = InMemoryFeatureStore()
    store.ingest("v", "k1", {"x": 1})
    store.ingest("v", "k2", {"x": 2})
    assert sorted(store.keys("v")) == ["k1", "k2"]
    assert store.keys("missing_view") == []


def test_clear_wipes_all_views() -> None:
    store = InMemoryFeatureStore()
    store.ingest("v1", "k", {"x": 1})
    store.ingest("v2", "k", {"x": 2})
    store.clear()
    assert store.keys("v1") == []
    assert store.keys("v2") == []


def test_store_is_thread_safe_against_concurrent_writers() -> None:
    """Sanity check that the RLock prevents lost writes under contention."""
    store = InMemoryFeatureStore()

    def writer(prefix: str) -> None:
        for i in range(200):
            store.ingest("hex_speed_5min", f"{prefix}_{i}", {"avg_speed_kmh": float(i)})

    threads = [threading.Thread(target=writer, args=(p,)) for p in ("a", "b", "c")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    keys = store.keys("hex_speed_5min")
    assert len(keys) == 600
