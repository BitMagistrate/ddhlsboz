"""Eco-routing emission model.

A radically simplified Comprehensive Modal Emission Model (CMEM) suitable for
real-time edge weighting. We compute CO₂ in grams as a function of vehicle class,
posted speed, distance and a tunable per-class burn intensity. The result is a
``g_co2`` figure used by the routing engine to compute ``eco_score`` and by the
B2C app to render the eco badge ("save 0.4 kg CO₂").

In production a vehicle-specific tuning table lives in
``ml/registry/eco/version=…/coefficients.parquet``; this module ships with sane
SEA defaults so the service works end-to-end at MVP scope.
"""

from __future__ import annotations

from dataclasses import dataclass

from roadpulse_core.types import RouteMode

# Per-mode burn coefficients (g CO₂/km at posted speed). Empirical values from EEA
# COPERT v5 for Vietnamese fleet composition, normalised against a baseline car.
BASE_GCO2_PER_KM: dict[RouteMode, float] = {
    RouteMode.MOTORBIKE: 65.0,
    RouteMode.CAR: 175.0,
    RouteMode.TRUCK: 430.0,
    RouteMode.BICYCLE: 0.0,
}


# Speed-dependent multiplier (idling traffic and high-speed cruising both burn more).
def _speed_multiplier(speed_kmh: float) -> float:
    if speed_kmh <= 0:
        return 1.55
    if speed_kmh < 20:
        return 1.45 - 0.015 * speed_kmh
    if speed_kmh < 60:
        return 1.05 - 0.005 * (speed_kmh - 20)
    return 0.85 + 0.004 * (speed_kmh - 60)


@dataclass(slots=True)
class EmissionEstimate:
    """Estimated emissions and the corresponding eco score."""

    g_co2: float
    eco_score: float  # in [0, 1] — lower = greener
    fuel_l: float
    base_per_km: float
    speed_multiplier: float

    def kg_co2(self) -> float:
        return self.g_co2 / 1_000.0


class EcoModel:
    """CMEM-simplified emission model."""

    def __init__(self, fuel_density_g_l: float = 740.0, carbon_intensity: float = 2.31) -> None:
        # 1 L petrol → ~2.31 kg CO₂; diesel ~2.68. Coefficient lets you tweak fuel mix.
        self._fuel_density_g_l = fuel_density_g_l
        self._carbon_intensity = carbon_intensity

    def estimate(
        self,
        *,
        mode: RouteMode,
        distance_m: float,
        avg_speed_kmh: float,
    ) -> EmissionEstimate:
        base = BASE_GCO2_PER_KM.get(mode, 200.0)
        mult = _speed_multiplier(avg_speed_kmh)
        km = max(distance_m, 0.0) / 1_000.0
        g_co2 = base * mult * km
        # Normalise against a 50 km baseline of the same vehicle class. Zero-emission
        # modes (bicycle) get an eco_score of 0.0 to avoid a division-by-zero.
        eco_score = 0.0 if base <= 0 else min(1.0, g_co2 / (base * 50.0))
        fuel_l = g_co2 / (self._fuel_density_g_l * self._carbon_intensity)
        return EmissionEstimate(
            g_co2=round(g_co2, 2),
            eco_score=round(eco_score, 3),
            fuel_l=round(fuel_l, 3),
            base_per_km=base,
            speed_multiplier=round(mult, 3),
        )
