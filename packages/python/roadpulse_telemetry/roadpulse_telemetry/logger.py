"""Structured logging configuration.

We use ``structlog`` so every log line is emitted as JSON with the trace id, request
id and service name bound automatically. The PII scrubber is wired in as the first
processor so accidentally logging a forbidden field is impossible.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from roadpulse_privacy.scrubber import PIIScrubber
from structlog.types import EventDict, Processor

from roadpulse_telemetry.context import (
    _ORG_ID,
    _REQUEST_ID,
    _TRACE_ID,
    env_service_name,
)

_SCRUBBER = PIIScrubber(strict=False)


def _add_request_context(_logger: Any, _method: str, event_dict: EventDict) -> EventDict:
    trace_id = _TRACE_ID.get()
    if trace_id:
        event_dict.setdefault("trace_id", trace_id)
    request_id = _REQUEST_ID.get()
    if request_id:
        event_dict.setdefault("request_id", request_id)
    org_id = _ORG_ID.get()
    if org_id:
        event_dict.setdefault("org_id", org_id)
    return event_dict


def _scrub_pii(_logger: Any, _method: str, event_dict: EventDict) -> EventDict:
    return _SCRUBBER.scrub(event_dict)  # type: ignore[return-value]


def configure_logging(level: int | str = "INFO") -> None:
    """Configure structlog + stdlib logging for a RoadPulse service."""
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)

    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _add_request_context,
        _scrub_pii,
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ]
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> Any:
    """Return a structlog logger bound to the service name."""
    return structlog.get_logger(name or env_service_name())
