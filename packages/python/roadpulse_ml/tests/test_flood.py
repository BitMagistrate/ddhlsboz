"""Tests for the flood detector."""

from __future__ import annotations

import random

from roadpulse_core.types import RouteMode
from roadpulse_ml.eco import EcoModel
from roadpulse_ml.flood import FloodDetector, FloodObservation


def _historical(n: int = 400, seed: int = 11) -> list[FloodObservation]:
    rng = random.Random(seed)
    obs: list[FloodObservation] = []
    for i in range(n):
        normal = i % 3 != 0
        obs.append(
            FloodObservation(
                hex_id=f"hex_{i:04x}",
                speed_drop_pct=rng.uniform(0.0, 0.2) if normal else rng.uniform(0.7, 0.95),
                sar_water_prior=rng.uniform(0.01, 0.06) if normal else rng.uniform(0.7, 0.95),
                crowd_reports=0 if normal else rng.randint(1, 5),
                precipitation_mm_h=rng.uniform(0, 4) if normal else rng.uniform(10, 30),
            )
        )
    return obs


def test_flood_detector_ranks_flooded_hexes_higher() -> None:
    obs = _historical()
    detector = FloodDetector(contamination=0.2)
    detector.fit(obs)
    scores = detector.score(obs)
    flooded = [s.score for s, o in zip(scores, obs, strict=True) if o.speed_drop_pct > 0.5]
    dry = [s.score for s, o in zip(scores, obs, strict=True) if o.speed_drop_pct <= 0.2]
    # Average flooded score should be clearly higher than the dry average.
    assert sum(flooded) / max(len(flooded), 1) > sum(dry) / max(len(dry), 1) + 0.2


def test_flood_detector_cold_start_uses_heuristic() -> None:
    detector = FloodDetector()
    scores = detector.score(
        [
            FloodObservation(
                hex_id="hex_x",
                speed_drop_pct=0.9,
                sar_water_prior=0.8,
                crowd_reports=3,
                precipitation_mm_h=18.0,
            )
        ]
    )
    assert len(scores) == 1
    assert scores[0].score > 0.5
    assert "sar" in scores[0].sources
    assert "crowd" in scores[0].sources


def test_flood_detector_empty_input_returns_empty_list() -> None:
    detector = FloodDetector()
    assert detector.score([]) == []


def test_eco_model_known_values_match_table() -> None:
    eco = EcoModel()
    estimate = eco.estimate(mode=RouteMode.MOTORBIKE, distance_m=5_000, avg_speed_kmh=30)
    assert estimate.g_co2 > 0
    assert 0.0 <= estimate.eco_score <= 1.0
    truck = eco.estimate(mode=RouteMode.TRUCK, distance_m=5_000, avg_speed_kmh=30)
    assert truck.g_co2 > estimate.g_co2
    assert truck.kg_co2() > estimate.kg_co2()


def test_eco_model_bicycle_emits_zero() -> None:
    eco = EcoModel()
    bike = eco.estimate(mode=RouteMode.BICYCLE, distance_m=10_000, avg_speed_kmh=16)
    assert bike.g_co2 == 0.0
    assert bike.eco_score == 0.0
