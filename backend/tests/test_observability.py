"""Тесты observability: метрики, request_id, prom-сериализация."""

from __future__ import annotations

import logging

from app import observability as obs


def test_counter_and_inc_alias() -> None:
    metrics = obs.Metrics()
    metrics.counter("requests_total", 1.0, {"path": "/x"})
    metrics.inc("requests_total", {"path": "/x"})
    text = metrics.render_prometheus()
    assert "requests_total" in text
    assert 'requests_total{path="/x"} 2' in text


def test_histogram_observed_in_prometheus_format() -> None:
    metrics = obs.Metrics()
    for v in (0.04, 0.2, 1.5, 11.0):
        metrics.observe("latency_seconds", v, {"path": "/y"})
    text = metrics.render_prometheus()
    assert "latency_seconds_bucket" in text
    assert 'le="0.05"' in text
    assert 'le="+Inf"' in text
    assert 'latency_seconds_count{path="/y"} 4' in text


def test_request_id_set_and_get() -> None:
    rid = obs.new_request_id()
    assert obs.get_request_id() == rid
    obs.set_request_id("forced-id")
    assert obs.get_request_id() == "forced-id"


def test_configure_logging_idempotent() -> None:
    obs.configure_logging(level=logging.WARNING, json=False)
    handlers_before = len(logging.getLogger().handlers)
    obs.configure_logging(level=logging.WARNING, json=False)
    handlers_after = len(logging.getLogger().handlers)
    assert handlers_after == handlers_before == 1


def test_metrics_reset_clears_all() -> None:
    metrics = obs.Metrics()
    metrics.counter("x", 1.0)
    metrics.observe("y", 1.0)
    metrics.set_gauge("z", 5.0)
    metrics.reset()
    assert metrics.render_prometheus().strip() == ""


def test_label_escape() -> None:
    metrics = obs.Metrics()
    metrics.counter("requests", 1.0, {"path": 'a"b\nc'})
    text = metrics.render_prometheus()
    assert '\\"' in text
    assert "\\n" in text
