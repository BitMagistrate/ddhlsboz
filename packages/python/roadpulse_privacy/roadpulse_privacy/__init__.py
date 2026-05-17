"""K-anonymity guards, PII scrubbers and field-level redactors.

This package is the single point of truth for privacy enforcement. Every public API
endpoint, every Kafka producer and every export job MUST funnel its outputs through
:class:`KAnonGuard` and :class:`PIIScrubber`. CI enforces that no service can declare
a Kafka topic schema containing forbidden fields without going through these helpers.
"""

from roadpulse_privacy.audit import KAnonViolation, ViolationSink, in_memory_sink
from roadpulse_privacy.guard import KAnonGuard
from roadpulse_privacy.scrubber import (
    FORBIDDEN_FIELDS,
    PIIScrubber,
    SafeLogger,
    scrub_in_place,
)

__all__ = [
    "FORBIDDEN_FIELDS",
    "KAnonGuard",
    "KAnonViolation",
    "PIIScrubber",
    "SafeLogger",
    "ViolationSink",
    "in_memory_sink",
    "scrub_in_place",
]
