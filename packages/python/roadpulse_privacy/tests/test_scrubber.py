"""Tests for the PII scrubber and SafeLogger."""

from __future__ import annotations

import logging

import pytest
from roadpulse_privacy.scrubber import (
    REDACTED,
    PIIScrubber,
    SafeLogger,
    scrub_in_place,
)


def test_scrubber_strict_raises_on_pii() -> None:
    scrubber = PIIScrubber(strict=True)
    with pytest.raises(ValueError, match="phone"):
        scrubber.scrub({"phone": "+84-901-123-456", "speed": 32.4})


def test_scrubber_lenient_drops_keys() -> None:
    scrubber = PIIScrubber(strict=False)
    cleaned = scrubber.scrub({"email": "foo@bar", "speed": 32.4})
    assert cleaned == {"speed": 32.4}


def test_scrubber_redacts_nested_secrets() -> None:
    scrubber = PIIScrubber(strict=False)
    payload = {
        "service": "trigger-feed",
        "config": {"signing_private_key": "abc123", "endpoint": "https://api"},
        "values": [{"transponder_id": "x"}],
    }
    cleaned = scrubber.scrub(payload)
    assert cleaned["config"]["signing_private_key"] == REDACTED
    assert cleaned["config"]["endpoint"] == "https://api"
    assert cleaned["values"] == [{}]


def test_scrub_in_place_strips_and_redacts() -> None:
    payload = {
        "phone": "+84",
        "service": "x",
        "config": {"api_key": "k", "ok": 1},
    }
    scrub_in_place(payload)
    assert "phone" not in payload
    assert payload["service"] == "x"
    assert payload["config"]["api_key"] == REDACTED
    assert payload["config"]["ok"] == 1


def test_safe_logger_redacts_log_fields(caplog: pytest.LogCaptureFixture) -> None:
    base_logger = logging.getLogger("rp.test")
    base_logger.setLevel(logging.INFO)
    safe = SafeLogger(base_logger)
    with caplog.at_level(logging.INFO, logger="rp.test"):
        safe.info("issue", phone="+84-1", route_id="r-1", api_token="t")
    record = caplog.records[-1]
    data = record.__dict__["data"]
    assert "phone" not in data
    assert data["route_id"] == "r-1"
    assert data["api_token"] == REDACTED
