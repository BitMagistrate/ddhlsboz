"""Behavioural tests for the k-anonymity guard."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from roadpulse_privacy.audit import in_memory_sink
from roadpulse_privacy.guard import KAnonGuard


def test_guard_allows_buckets_at_or_above_min_k() -> None:
    sink = in_memory_sink()
    guard = KAnonGuard(min_k=50, time_window_s=300, sink=sink, source="vetc.hex.5min")
    decision = guard.check(bucket="hex_a", observed_k=50)
    assert decision.allowed
    assert decision.observed_k == 50
    assert list(sink.recent()) == []


def test_guard_drops_thin_buckets_and_records_violations() -> None:
    sink = in_memory_sink()
    guard = KAnonGuard(min_k=50, time_window_s=300, sink=sink, source="vetc.hex.5min")
    at = datetime(2025, 9, 1, tzinfo=UTC)
    decision = guard.check(bucket="hex_b", observed_k=12, at=at)
    assert not decision.allowed
    assert decision.observed_k == 12
    assert decision.reason and "min_k=50" in decision.reason
    violations = list(sink.recent())
    assert len(violations) == 1
    assert violations[0].bucket == "hex_b"
    assert violations[0].attempted_k == 12
    assert violations[0].source == "vetc.hex.5min"
    assert violations[0].dropped_at == at


def test_guard_filter_drops_thin_buckets() -> None:
    guard = KAnonGuard(min_k=50, time_window_s=300)
    survivors = guard.filter([("hex_a", 80), ("hex_b", 5), ("hex_c", 60), ("hex_d", 49)])
    assert survivors == ["hex_a", "hex_c"]


def test_guard_rejects_invalid_construction() -> None:
    with pytest.raises(ValueError):
        KAnonGuard(min_k=1)
    with pytest.raises(ValueError):
        KAnonGuard(min_k=50, time_window_s=0)
