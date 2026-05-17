"""Tests for the eco / CO₂-per-km emissions estimator."""

from __future__ import annotations

import pytest
from roadpulse_core.types import RouteMode
from roadpulse_ml.eco import EcoModel


@pytest.fixture()
def model() -> EcoModel:
    return EcoModel()


def test_bicycle_emits_zero_co2(model: EcoModel) -> None:
    est = model.estimate(mode=RouteMode.BICYCLE, distance_m=10_000, avg_speed_kmh=18.0)
    assert est.g_co2 == 0.0
    assert est.eco_score == 0.0


def test_truck_burns_more_than_car(model: EcoModel) -> None:
    car = model.estimate(mode=RouteMode.CAR, distance_m=10_000, avg_speed_kmh=40.0)
    truck = model.estimate(mode=RouteMode.TRUCK, distance_m=10_000, avg_speed_kmh=40.0)
    assert truck.g_co2 > car.g_co2 * 2  # baseline truck coeff is 430 vs 175


def test_idling_traffic_is_dirtier(model: EcoModel) -> None:
    moving = model.estimate(mode=RouteMode.CAR, distance_m=10_000, avg_speed_kmh=40.0)
    crawling = model.estimate(mode=RouteMode.CAR, distance_m=10_000, avg_speed_kmh=5.0)
    assert crawling.g_co2 > moving.g_co2


def test_high_speed_cruise_is_dirtier_than_optimal(model: EcoModel) -> None:
    optimal = model.estimate(mode=RouteMode.CAR, distance_m=10_000, avg_speed_kmh=60.0)
    speeding = model.estimate(mode=RouteMode.CAR, distance_m=10_000, avg_speed_kmh=100.0)
    assert speeding.g_co2 > optimal.g_co2


def test_kg_co2_is_grams_over_thousand(model: EcoModel) -> None:
    est = model.estimate(mode=RouteMode.CAR, distance_m=20_000, avg_speed_kmh=45.0)
    assert est.kg_co2() == pytest.approx(est.g_co2 / 1000.0)


def test_zero_distance_returns_zero(model: EcoModel) -> None:
    est = model.estimate(mode=RouteMode.CAR, distance_m=0, avg_speed_kmh=40.0)
    assert est.g_co2 == 0.0
    assert est.fuel_l == 0.0


def test_negative_distance_clamps_to_zero(model: EcoModel) -> None:
    est = model.estimate(mode=RouteMode.CAR, distance_m=-500, avg_speed_kmh=40.0)
    assert est.g_co2 == 0.0
