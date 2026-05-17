"""Smoke tests for the structlog wiring + PII scrubbing processor."""

from __future__ import annotations

import json
import sys
from io import StringIO

import structlog
from roadpulse_telemetry.context import bind_request_context
from roadpulse_telemetry.logger import configure_logging, get_logger


def _emit_capture(emit) -> str:
    """Call ``emit(logger)`` while redirecting structlog's stdout to a buffer."""
    sink = StringIO()
    saved = sys.stdout
    sys.stdout = sink
    try:
        configure_logging(level="INFO")
        logger = get_logger("test")
        emit(logger)
    finally:
        sys.stdout = saved
        structlog.reset_defaults()
    lines = [line for line in sink.getvalue().splitlines() if line.strip()]
    assert lines, "expected at least one log line, got nothing"
    return lines[-1]


def test_configure_logging_uses_json_renderer() -> None:
    bind_request_context(trace_id="01HX0000000000000000000000")
    payload = json.loads(_emit_capture(lambda log: log.info("hello", value=1)))
    assert payload["event"] == "hello"
    assert payload["value"] == 1
    assert payload["trace_id"] == "01HX0000000000000000000000"


def test_logger_scrubs_pii_fields() -> None:
    payload = json.loads(
        _emit_capture(
            lambda log: log.info(
                "login", phone="0901234567", email="x@example.com", note="ok"
            )
        )
    )
    assert "phone" not in payload
    assert "email" not in payload
    assert payload["note"] == "ok"


def test_logger_redacts_secretish_keys() -> None:
    """Keys matching the ``secretish`` regex are replaced with ``[REDACTED]``."""
    payload = json.loads(
        _emit_capture(
            lambda log: log.info(
                "op",
                api_key="sk_demo_123",
                bearer_token="xyz",
                user_password="pw",
                details={"signing": "abc", "private_key": "p"},
            )
        )
    )
    assert payload["api_key"] == "[REDACTED]"
    assert payload["bearer_token"] == "[REDACTED]"
    assert payload["user_password"] == "[REDACTED]"
    assert payload["details"]["signing"] == "[REDACTED]"
    assert payload["details"]["private_key"] == "[REDACTED]"
