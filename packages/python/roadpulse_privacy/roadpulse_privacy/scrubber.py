"""PII scrubber + safe logger.

The :data:`FORBIDDEN_FIELDS` set is the canonical list of attributes that may never
leave the privacy boundary. The scrubber is used in three places:

* Pydantic model validators on every ingestion entry-point (Kafka producer / gRPC
  receiver / REST request body) — a payload containing any forbidden field fails
  validation before it can touch downstream code.
* The ``roadpulse_telemetry.SafeLogger`` redacts forbidden keys before they reach
  stdout or any structured logger sink.
* CI runs the scrubber over generated Avro/Proto schemas to ensure no contract is
  declared with a forbidden field name.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable, Mapping, MutableMapping
from typing import Any

FORBIDDEN_FIELDS: frozenset[str] = frozenset(
    {
        "name",
        "full_name",
        "first_name",
        "last_name",
        "phone",
        "phone_number",
        "msisdn",
        "email",
        "email_address",
        "plate",
        "plate_number",
        "license_plate",
        "transponder_id",
        "vetc_id",
        "gps_track",
        "gps_trace",
        "transaction_id",
        "vin",
        "national_id",
        "passport_number",
    }
)

_SECRETISH_KEY = re.compile(r"(?i)(token|secret|api[_-]?key|password|signing|private[_-]?key)$")
REDACTED = "[REDACTED]"


class PIIScrubber:
    """Recursive scrubber for mappings and lists.

    Construct with an optional extra blocklist; the union of
    :data:`FORBIDDEN_FIELDS` and the extras is the effective deny-list. Strict mode
    (default) raises on a hit, lenient mode replaces the value with ``[REDACTED]``.
    """

    def __init__(self, extra_forbidden: Iterable[str] = (), *, strict: bool = True) -> None:
        self.forbidden = FORBIDDEN_FIELDS | {f.lower() for f in extra_forbidden}
        self.strict = strict

    def __call__(self, payload: Any) -> Any:
        return self.scrub(payload)

    def scrub(self, payload: Any) -> Any:
        """Return a new copy of ``payload`` with forbidden keys removed/redacted."""
        if isinstance(payload, Mapping):
            return {k: self._handle_pair(k, v) for k, v in payload.items() if self._allow_key(k)}
        if isinstance(payload, list):
            return [self.scrub(item) for item in payload]
        if isinstance(payload, tuple):
            return tuple(self.scrub(item) for item in payload)
        return payload

    def _allow_key(self, key: Any) -> bool:
        if not isinstance(key, str):
            return True
        lowered = key.lower()
        if lowered in self.forbidden:
            if self.strict:
                raise ValueError(f"PII field '{key}' is not allowed in payload")
            return False
        return True

    def _handle_pair(self, key: str, value: Any) -> Any:
        if isinstance(key, str) and _SECRETISH_KEY.search(key):
            return REDACTED
        return self.scrub(value)


def scrub_in_place(payload: MutableMapping[str, Any], *, strict: bool = False) -> None:
    """In-place variant for hot paths where allocation matters.

    Walks the mapping iteratively; forbidden keys are popped and secret-ish keys are
    overwritten with :data:`REDACTED`.
    """
    stack: list[MutableMapping[str, Any]] = [payload]
    while stack:
        node = stack.pop()
        for key in list(node.keys()):
            value = node[key]
            lowered = key.lower() if isinstance(key, str) else ""
            if lowered in FORBIDDEN_FIELDS:
                if strict:
                    raise ValueError(f"PII field '{key}' is not allowed in payload")
                node.pop(key)
                continue
            if _SECRETISH_KEY.search(lowered):
                node[key] = REDACTED
                continue
            if isinstance(value, MutableMapping):
                stack.append(value)


class SafeLogger:
    """Drop-in wrapper that redacts PII/secret fields before delegating to a logger."""

    def __init__(self, logger: logging.Logger, scrubber: PIIScrubber | None = None) -> None:
        self._logger = logger
        self._scrubber = scrubber or PIIScrubber(strict=False)

    def info(self, msg: str, **fields: Any) -> None:
        self._logger.info(msg, extra={"data": self._scrubber.scrub(fields)})

    def warning(self, msg: str, **fields: Any) -> None:
        self._logger.warning(msg, extra={"data": self._scrubber.scrub(fields)})

    def error(self, msg: str, **fields: Any) -> None:
        self._logger.error(msg, extra={"data": self._scrubber.scrub(fields)})

    def debug(self, msg: str, **fields: Any) -> None:
        self._logger.debug(msg, extra={"data": self._scrubber.scrub(fields)})
