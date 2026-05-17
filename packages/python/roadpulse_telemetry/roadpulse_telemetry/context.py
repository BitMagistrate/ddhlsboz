"""Request-scoped trace context propagation.

Each inbound request gets a ULID-shaped ``trace_id`` (we use ULIDs because they sort
lexicographically, which is gold when reading raw logs). Downstream services pull
the active trace id off the ``Authorization`` chain and continue using it.
"""

from __future__ import annotations

import os
import secrets
import time
from collections.abc import Mapping
from contextvars import ContextVar

_TRACE_ID: ContextVar[str | None] = ContextVar("roadpulse_trace_id", default=None)
_ORG_ID: ContextVar[str | None] = ContextVar("roadpulse_org_id", default=None)
_REQUEST_ID: ContextVar[str | None] = ContextVar("roadpulse_request_id", default=None)

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def new_trace_id() -> str:
    """Generate a 26-character ULID-ish trace id (timestamp + 80 bits of entropy)."""
    ts_ms = int(time.time() * 1000)
    timestamp = _encode_b32(ts_ms, length=10)
    entropy = _encode_b32(int.from_bytes(secrets.token_bytes(10), "big"), length=16)
    return timestamp + entropy


def current_trace_id() -> str | None:
    return _TRACE_ID.get()


def bind_request_context(
    *,
    trace_id: str | None = None,
    request_id: str | None = None,
    org_id: str | None = None,
    headers: Mapping[str, str] | None = None,
) -> str:
    """Set the trace context for the current task.

    Returns the effective trace_id so callers can stash it into response headers.
    """
    if headers is not None:
        trace_id = trace_id or headers.get("x-trace-id") or headers.get("traceparent")
        request_id = request_id or headers.get("x-request-id")
        org_id = org_id or headers.get("x-roadpulse-org-id")
    effective = trace_id or new_trace_id()
    _TRACE_ID.set(effective)
    _REQUEST_ID.set(request_id or effective)
    _ORG_ID.set(org_id)
    return effective


def env_service_name() -> str:
    return os.environ.get("ROADPULSE_SERVICE", "unknown")


def _encode_b32(value: int, *, length: int) -> str:
    if value < 0:
        raise ValueError("cannot encode negative value")
    if length <= 0:
        raise ValueError("length must be positive")
    chars: list[str] = []
    for _ in range(length):
        chars.append(_CROCKFORD[value & 0x1F])
        value >>= 5
    return "".join(reversed(chars))
