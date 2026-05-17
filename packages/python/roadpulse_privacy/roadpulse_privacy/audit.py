"""Audit envelopes for the privacy guard.

Violations are emitted on the ``audit.kanon.violations`` Kafka topic in production.
In tests and ad-hoc tooling we use an in-memory ring buffer so unit tests can assert
on what was dropped without spinning up Redpanda.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class KAnonViolation:
    source: str
    bucket: str
    attempted_k: int
    min_k: int
    dropped_at: datetime


class ViolationSink(Protocol):
    def record(self, violation: KAnonViolation) -> None: ...

    def recent(self) -> Iterable[KAnonViolation]: ...


class _InMemorySink:
    """Bounded ring buffer used in tests and local dev."""

    def __init__(self, capacity: int = 1024) -> None:
        self._buf: deque[KAnonViolation] = deque(maxlen=capacity)

    def record(self, violation: KAnonViolation) -> None:
        self._buf.append(violation)

    def recent(self) -> Iterable[KAnonViolation]:
        return list(self._buf)


def in_memory_sink(capacity: int = 1024) -> ViolationSink:
    """Factory for the default in-memory violation sink."""
    return _InMemorySink(capacity=capacity)
