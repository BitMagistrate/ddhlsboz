"""Routing profiles per vehicle class.

Profiles correspond 1:1 to the Lua scripts in ``services/osrm/profiles``. Keep this
table and the Lua side in sync — both expect the same tunable weights and the same
set of forbidden road classes.
"""

from __future__ import annotations

from dataclasses import dataclass

from roadpulse_core.types import RouteMode

# Sensible per-road-class default speeds in km/h. Each profile may override.
DEFAULT_SPEEDS_KMH: dict[str, float] = {
    "motorway": 90.0,
    "trunk": 70.0,
    "primary": 55.0,
    "secondary": 45.0,
    "tertiary": 35.0,
    "residential": 25.0,
    "living_street": 15.0,
    "service": 18.0,
    "unclassified": 30.0,
    "hem": 12.0,  # narrow alleys, unique to VN motorbike profile
    "track": 15.0,
}


@dataclass(frozen=True, slots=True)
class Profile:
    """Edge-evaluation profile for a single vehicle class."""

    mode: RouteMode
    name: str
    speeds_kmh: dict[str, float]
    forbidden_classes: frozenset[str]
    alpha_congestion: float
    beta_flood: float
    gamma_eco: float
    eco_factor: float  # multiplier from base fuel-burn intensity (1.0 = baseline car)

    def is_usable(self, road_class: str, tags: dict[str, str]) -> bool:
        if road_class in self.forbidden_classes:
            return False
        # Truck-specific tags
        if "hgv" in tags and tags["hgv"] in {"no", "destination"} and self.mode is RouteMode.TRUCK:
            return False
        if (
            "motor_vehicle" in tags
            and tags["motor_vehicle"] == "no"
            and self.mode
            in {
                RouteMode.CAR,
                RouteMode.TRUCK,
            }
        ):
            return False
        return True

    def free_flow_speed(self, road_class: str) -> float:
        return self.speeds_kmh.get(road_class, DEFAULT_SPEEDS_KMH.get(road_class, 25.0))


motorbike_vn = Profile(
    mode=RouteMode.MOTORBIKE,
    name="motorbike-vn",
    speeds_kmh={
        "motorway": 0.0,  # motorbikes are typically forbidden on the few VN highways
        "trunk": 50.0,
        "primary": 45.0,
        "secondary": 38.0,
        "tertiary": 32.0,
        "residential": 28.0,
        "living_street": 18.0,
        "service": 22.0,
        "unclassified": 30.0,
        "hem": 14.0,
        "track": 18.0,
    },
    forbidden_classes=frozenset({"motorway"}),
    alpha_congestion=0.6,
    beta_flood=2.5,
    gamma_eco=0.05,
    eco_factor=0.4,
)

car_vn = Profile(
    mode=RouteMode.CAR,
    name="car-vn",
    speeds_kmh=DEFAULT_SPEEDS_KMH,
    forbidden_classes=frozenset({"hem", "track", "living_street"}),
    alpha_congestion=0.9,
    beta_flood=1.5,
    gamma_eco=0.10,
    eco_factor=1.0,
)

truck_vn = Profile(
    mode=RouteMode.TRUCK,
    name="truck-vn",
    speeds_kmh={
        **DEFAULT_SPEEDS_KMH,
        "residential": 18.0,
        "tertiary": 28.0,
        "secondary": 35.0,
    },
    forbidden_classes=frozenset({"hem", "track", "living_street", "service"}),
    alpha_congestion=1.0,
    beta_flood=1.2,
    gamma_eco=0.18,
    eco_factor=2.4,
)

bicycle_vn = Profile(
    mode=RouteMode.BICYCLE,
    name="bicycle-vn",
    speeds_kmh={
        "motorway": 0.0,
        "trunk": 0.0,
        "primary": 16.0,
        "secondary": 16.0,
        "tertiary": 16.0,
        "residential": 16.0,
        "living_street": 12.0,
        "service": 14.0,
        "unclassified": 16.0,
        "hem": 12.0,
        "track": 12.0,
    },
    forbidden_classes=frozenset({"motorway", "trunk"}),
    alpha_congestion=0.3,
    beta_flood=2.0,
    gamma_eco=0.0,
    eco_factor=0.0,
)


PROFILES: dict[RouteMode, Profile] = {
    RouteMode.MOTORBIKE: motorbike_vn,
    RouteMode.CAR: car_vn,
    RouteMode.TRUCK: truck_vn,
    RouteMode.BICYCLE: bicycle_vn,
}
