"""Tests for the request-scoped trace/org/request id context."""

from __future__ import annotations

from roadpulse_telemetry.context import (
    bind_request_context,
    current_trace_id,
    new_trace_id,
)


def test_new_trace_id_is_26_chars_crockford() -> None:
    trace = new_trace_id()
    assert len(trace) == 26
    assert all(c in "0123456789ABCDEFGHJKMNPQRSTVWXYZ" for c in trace)


def test_two_trace_ids_differ() -> None:
    assert new_trace_id() != new_trace_id()


def test_bind_request_context_uses_supplied_trace_id() -> None:
    bind_request_context(trace_id="01HXEAGENTSAMPLE000000000A")
    assert current_trace_id() == "01HXEAGENTSAMPLE000000000A"


def test_bind_request_context_falls_back_to_headers() -> None:
    headers = {"x-trace-id": "01HX0000000000000000000000"}
    effective = bind_request_context(headers=headers)
    assert effective == "01HX0000000000000000000000"
    assert current_trace_id() == "01HX0000000000000000000000"


def test_bind_request_context_generates_when_missing() -> None:
    effective = bind_request_context()
    assert effective
    assert current_trace_id() == effective


def test_bind_request_context_supports_traceparent_header() -> None:
    headers = {"traceparent": "00-deadbeef-cafe-01"}
    effective = bind_request_context(headers=headers)
    assert effective == "00-deadbeef-cafe-01"
