"""Tests for the synthetic-vs-real data origin flag exposed by api-gateway."""

from __future__ import annotations

import importlib

import pytest
from app.data_origin import (
    PENDING_REAL_FEEDS,
    data_origin,
    pending_real_feeds,
    real_feeds,
)


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ROADPULSE_REAL_FEEDS", raising=False)


def test_defaults_to_synthetic() -> None:
    assert data_origin() == "synthetic"
    assert real_feeds() == []
    assert pending_real_feeds() == list(PENDING_REAL_FEEDS)


def test_env_with_single_feed_flips_to_real(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROADPULSE_REAL_FEEDS", "vetc.hex.5min")
    assert data_origin() == "real"
    assert real_feeds() == ["vetc.hex.5min"]
    pending = pending_real_feeds()
    assert "vetc.hex.5min" not in pending
    assert "sentinel1.sar.water_mask" in pending


def test_env_strips_whitespace_and_skips_blanks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "ROADPULSE_REAL_FEEDS",
        "  vetc.hex.5min ,, sentinel1.sar.water_mask ,",
    )
    feeds = real_feeds()
    assert feeds == ["vetc.hex.5min", "sentinel1.sar.water_mask"]


def test_pending_list_matches_canonical_default(monkeypatch: pytest.MonkeyPatch) -> None:
    # Reimport to ensure the constant didn't drift across hot reloads.
    monkeypatch.delenv("ROADPULSE_REAL_FEEDS", raising=False)
    mod = importlib.reload(importlib.import_module("app.data_origin"))
    assert set(mod.PENDING_REAL_FEEDS) == {
        "vetc.hex.5min",
        "sentinel1.sar.water_mask",
        "vnms.weather.hourly",
        "fleet_sdk.probes",
    }
