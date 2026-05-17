"""Tests for the ETA model."""

from __future__ import annotations

import random

import pytest
from roadpulse_core.types import EtaConfidence
from roadpulse_ml.eta import ETA_FEATURES, EtaModel, ETARecord


def _synthetic_dataset(n: int = 600, seed: int = 7) -> tuple[list[ETARecord], list[float]]:
    """A noisy linear-ish synthetic dataset that GBM can fit easily."""
    rng = random.Random(seed)
    rows: list[ETARecord] = []
    targets: list[float] = []
    for _ in range(n):
        distance = rng.uniform(500, 12_000)
        flow = rng.uniform(15, 55)
        free_flow = distance / 1_000 / flow * 3600
        hour = rng.randint(0, 167)
        weekend = 1 if hour % 24 >= 144 else 0
        precip = rng.choice([0.0, 0.0, 0.0, 1.0, 5.0, 15.0])
        rush = 1 if 16 <= (hour % 24) <= 19 else 0
        flood = rng.uniform(0.0, 0.4) if precip > 0 else 0.0
        rec = ETARecord(
            distance_m=distance,
            free_flow_seconds=free_flow,
            hour_of_week=hour,
            is_weekend=weekend,
            precipitation_mm_h=precip,
            wind_kmh=rng.uniform(0, 30),
            is_rush_hour=rush,
            lag_speed_5min=flow - rng.uniform(0, 8),
            lag_speed_15min=flow - rng.uniform(0, 6),
            lag_speed_1h=flow,
            vehicle_count_5min=rng.uniform(50, 800),
            flood_score=flood,
            road_class_index=rng.randint(0, 6),
        )
        congestion_mult = 1.0 + 0.18 * rush + 0.4 * flood + 0.06 * (precip / 25.0)
        rows.append(rec)
        targets.append(free_flow * congestion_mult + rng.uniform(-15, 15))
    return rows, targets


def test_eta_features_canonical_order_is_stable() -> None:
    assert ETA_FEATURES[0] == "distance_m"
    assert ETA_FEATURES[-1] == "road_class_index"


def test_eta_cold_start_returns_low_confidence_prediction() -> None:
    model = EtaModel()
    rec = ETARecord(
        distance_m=2_500.0,
        free_flow_seconds=420.0,
        hour_of_week=12,
        is_weekend=0,
    )
    prediction = model.predict(rec)
    assert prediction.eta_s > 0
    assert prediction.confidence == EtaConfidence.LOW
    assert prediction.eta_p10_s <= prediction.eta_s <= prediction.eta_p90_s


def test_eta_after_training_beats_free_flow_baseline_on_holdout() -> None:
    rows, targets = _synthetic_dataset(n=800)
    split = int(len(rows) * 0.8)
    model = EtaModel()
    model.fit(rows[:split], targets[:split])
    holdout = rows[split:]
    holdout_targets = targets[split:]
    predicted = [p.eta_s for p in model.predict_batch(holdout)]
    free_flow = [r.free_flow_seconds for r in holdout]
    mape_model = EtaModel.mape(holdout_targets, predicted)
    mape_baseline = EtaModel.mape(holdout_targets, free_flow)
    # The GBM should comfortably beat the free-flow OSRM baseline.
    assert mape_model < mape_baseline
    assert mape_model < 0.20


def test_eta_round_trips_via_dumps_loads() -> None:
    rows, targets = _synthetic_dataset(n=300)
    model = EtaModel()
    model.fit(rows, targets)
    payload = model.dumps()
    restored = EtaModel.loads(payload)
    assert restored.is_trained
    assert restored.version == model.version
    p1 = model.predict(rows[0])
    p2 = restored.predict(rows[0])
    assert p1.eta_s == pytest.approx(p2.eta_s, rel=1e-6)


def test_eta_model_card_renders_markdown() -> None:
    rows, targets = _synthetic_dataset(n=200)
    model = EtaModel()
    model.fit(rows, targets)
    card = model.to_model_card()
    assert card.startswith("# RoadPulse ETA Model Card")
    assert "distance_m" in card


def test_eta_fit_rejects_empty_inputs() -> None:
    model = EtaModel()
    with pytest.raises(ValueError):
        model.fit([], [])
