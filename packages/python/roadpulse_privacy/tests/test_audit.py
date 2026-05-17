"""Tests for the audit ring buffer + violation envelope."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from roadpulse_privacy.audit import KAnonViolation, _InMemorySink, in_memory_sink


def _make_violation(bucket: str = "demo", *, attempted_k: int = 12) -> KAnonViolation:
    return KAnonViolation(
        source="vetc.hex.5min",
        bucket=bucket,
        attempted_k=attempted_k,
        min_k=50,
        dropped_at=datetime(2025, 5, 17, tzinfo=UTC),
    )


def test_in_memory_sink_records_and_returns_recent() -> None:
    sink = in_memory_sink()
    sink.record(_make_violation())
    sink.record(_make_violation(bucket="other", attempted_k=4))
    recent = list(sink.recent())
    assert len(recent) == 2
    assert {v.bucket for v in recent} == {"demo", "other"}


def test_in_memory_sink_respects_capacity() -> None:
    sink = _InMemorySink(capacity=3)
    for i in range(10):
        sink.record(_make_violation(bucket=f"bucket_{i}", attempted_k=i))
    recent = list(sink.recent())
    assert len(recent) == 3
    # Ring buffer keeps the *latest* writes, not the oldest.
    assert [v.bucket for v in recent] == ["bucket_7", "bucket_8", "bucket_9"]


def test_violation_is_frozen() -> None:
    v = _make_violation()
    import dataclasses

    assert dataclasses.is_dataclass(v)
    # Frozen dataclass should refuse mutation.
    try:
        v.attempted_k = 99  # type: ignore[misc]
    except dataclasses.FrozenInstanceError:
        return
    raise AssertionError("KAnonViolation should be immutable")


def test_recent_is_snapshot_not_live_view() -> None:
    sink = in_memory_sink()
    sink.record(_make_violation())
    snapshot = list(sink.recent())
    sink.record(_make_violation(bucket="later"))
    assert len(snapshot) == 1  # snapshot is independent


def test_violation_carries_dropped_at_timezone() -> None:
    v = _make_violation()
    assert v.dropped_at.tzinfo is not None
    assert datetime.now(UTC) - v.dropped_at >= timedelta(days=0)
