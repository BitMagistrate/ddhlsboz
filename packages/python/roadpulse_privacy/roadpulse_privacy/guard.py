"""k-anonymity enforcement primitive.

A "bucket" is any aggregate that will leave the trust boundary (public API response,
Kafka topic destined for an external consumer, parquet export, etc.). Each bucket
must contain data sourced from at least ``min_k`` unique sources observed within the
time-window. Failing buckets are dropped and the violation is forwarded to a
:class:`ViolationSink` so the compliance dashboard can pick it up.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from roadpulse_privacy.audit import KAnonViolation, ViolationSink, in_memory_sink

DEFAULT_K = 50
DEFAULT_WINDOW_S = 300


@dataclass(frozen=True, slots=True)
class GuardDecision:
    """Outcome of a single guard check.

    Attributes
    ----------
    allowed
        ``True`` when the bucket meets the privacy budget and may be emitted.
    observed_k
        The number of unique sources contributing to the bucket.
    reason
        Human-readable explanation; populated when ``allowed`` is False.
    """

    allowed: bool
    observed_k: int
    reason: str | None = None


class KAnonGuard:
    """Enforces ``k`` ≥ ``min_k`` across a rolling time-window per bucket."""

    def __init__(
        self,
        *,
        min_k: int = DEFAULT_K,
        time_window_s: int = DEFAULT_WINDOW_S,
        sink: ViolationSink | None = None,
        source: str = "unknown",
    ) -> None:
        if min_k < 2:
            raise ValueError("min_k must be ≥ 2 to provide any anonymity")
        if time_window_s <= 0:
            raise ValueError("time_window_s must be positive")
        self.min_k = min_k
        self.window = timedelta(seconds=time_window_s)
        self.source = source
        self._sink = sink or in_memory_sink()

    def check(
        self,
        *,
        bucket: str,
        observed_k: int,
        at: datetime | None = None,
    ) -> GuardDecision:
        """Return a :class:`GuardDecision` and record any violation."""
        if observed_k >= self.min_k:
            return GuardDecision(allowed=True, observed_k=observed_k)
        now = at or datetime.now(UTC)
        violation = KAnonViolation(
            source=self.source,
            bucket=bucket,
            attempted_k=observed_k,
            min_k=self.min_k,
            dropped_at=now,
        )
        self._sink.record(violation)
        return GuardDecision(
            allowed=False,
            observed_k=observed_k,
            reason=f"k={observed_k} < min_k={self.min_k}",
        )

    def filter(
        self,
        items: list[tuple[str, int]],
        *,
        at: datetime | None = None,
    ) -> list[str]:
        """Filter ``[(bucket, observed_k), …]``, returning only buckets that pass."""
        return [
            bucket for bucket, k in items if self.check(bucket=bucket, observed_k=k, at=at).allowed
        ]

    @property
    def violations(self) -> list[KAnonViolation]:
        """Read-back of recent violations from the underlying sink (test helper)."""
        return list(self._sink.recent())
