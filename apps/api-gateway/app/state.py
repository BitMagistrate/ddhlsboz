"""Process-wide singletons (routing engine, ML models, feature store, demo data).

We deliberately keep this isolated so unit tests can instantiate a fresh
:class:`AppState` per test without touching shared state.
"""

from __future__ import annotations

import json
import math
import random
import time
from dataclasses import dataclass, field
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from roadpulse_core.types import LatLon, Org
from roadpulse_features.store import InMemoryFeatureStore
from roadpulse_ml.eco import EcoModel
from roadpulse_ml.eta import EtaModel, ETARecord
from roadpulse_ml.flood import FloodDetector, FloodObservation
from roadpulse_privacy.guard import KAnonGuard
from roadpulse_routing.engine import RoutingEngine, StaticPenalty
from roadpulse_routing.graph import Edge, Graph, Node

# --- Seed loader ---------------------------------------------------------------------


@dataclass(slots=True)
class SeedBundle:
    nodes: list[Node]
    edges: list[Edge]
    flood_hexes: dict[str, dict[str, float]]
    api_keys: dict[str, str]
    orgs: dict[str, Org]
    fleets: list[dict[str, object]]
    policies: list[dict[str, object]]
    demographics: dict[str, int] = field(default_factory=dict)


def _load_json(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))


def load_seed_bundle(seed_dir: Path) -> SeedBundle:
    """Load the HCMC seed graph + supporting fixture data.

    The seed files live under ``data/seed/`` and are committed verbatim. The graph
    is a hand-curated 81-node / 220-edge corridor running from Tân Sơn Nhất Airport
    through District 3 and District 1 to Phú Mỹ Hưng — enough hexes to demo flood-
    aware routing without bringing in a 4 GB OSM extract.
    """
    if not seed_dir.exists():
        return _fallback_seed()

    nodes_raw = _load_json(seed_dir / "graph_nodes.json")
    edges_raw = _load_json(seed_dir / "graph_edges.json")
    floods = _load_json(seed_dir / "flood_markers.json")
    orgs_raw = _load_json(seed_dir / "orgs.json")
    fleets_raw = _load_json(seed_dir / "fleets.json")
    policies_raw = _load_json(seed_dir / "policies.json")
    demo_raw = _load_json(seed_dir / "demographics.json")

    assert isinstance(nodes_raw, list)
    assert isinstance(edges_raw, list)
    assert isinstance(orgs_raw, list)
    assert isinstance(fleets_raw, list)
    assert isinstance(policies_raw, list)
    assert isinstance(floods, dict)
    assert isinstance(demo_raw, dict)

    nodes = [
        Node(id=int(n["id"]), lng=float(n["lng"]), lat=float(n["lat"]), district=n.get("district"))
        for n in nodes_raw
    ]
    edges = [
        Edge(
            src=int(e["src"]),
            dst=int(e["dst"]),
            distance_m=float(e["distance_m"]),
            free_flow_speed_kmh=float(e["free_flow_speed_kmh"]),
            road_class=str(e["road_class"]),
            tags={
                "hex_id": str(e.get("hex_id", "")),
                "name": str(e.get("name", "")),
                "toll_vnd": str(e.get("toll_vnd", 0)),
            },
        )
        for e in edges_raw
    ]
    orgs: dict[str, Org] = {}
    api_keys: dict[str, str] = {}
    for raw in orgs_raw:
        org = Org(
            id=str(raw["id"]),
            name=str(raw["name"]),
            tier=str(raw["tier"]),
            country=str(raw.get("country", "VN")),
        )
        orgs[org.id] = org
        for key in raw.get("api_keys", []):
            api_keys[str(key)] = org.id
    floods_typed: dict[str, dict[str, float]] = {}
    for hex_id, payload in floods.items():
        if not isinstance(payload, dict):
            continue
        numeric: dict[str, float] = {}
        for kk, vv in payload.items():
            try:
                numeric[kk] = float(vv)
            except (TypeError, ValueError):
                # Skip non-numeric fields like a textual `note` annotation.
                continue
        floods_typed[hex_id] = numeric
    demographics = {str(k): int(v) for k, v in demo_raw.items()}
    return SeedBundle(
        nodes=nodes,
        edges=edges,
        flood_hexes=floods_typed,
        api_keys=api_keys,
        orgs=orgs,
        fleets=fleets_raw,
        policies=policies_raw,
        demographics=demographics,
    )


def _fallback_seed() -> SeedBundle:
    """Tiny synthetic graph used when ``data/seed`` is missing (CI-only)."""
    nodes = [
        Node(id=i, lng=106.700 + 0.005 * (i % 5), lat=10.770 + 0.005 * (i // 5)) for i in range(20)
    ]
    edges: list[Edge] = []
    for n in nodes:
        for m in nodes:
            if n.id >= m.id:
                continue
            dist = math.hypot(n.lng - m.lng, n.lat - m.lat) * 111_320
            if dist == 0 or dist > 800:
                continue
            edges.append(
                Edge(
                    src=n.id,
                    dst=m.id,
                    distance_m=dist,
                    free_flow_speed_kmh=30,
                    road_class="primary",
                    tags={"hex_id": f"hex_{n.id % 4:02d}"},
                )
            )
    demo_org = Org(id="org_demo", name="Demo Org", tier="b2c", country="VN")
    return SeedBundle(
        nodes=nodes,
        edges=edges,
        flood_hexes={"hex_02": {"score": 0.8}},
        api_keys={"rp_demo_key": "org_demo"},
        orgs={"org_demo": demo_org},
        fleets=[],
        policies=[],
        demographics={f"hex_{i:02d}": 1500 for i in range(4)},
    )


# --- App state ------------------------------------------------------------------------


class AppState:
    """Singleton bag of services for the FastAPI app."""

    def __init__(self, seed_dir: Path | None = None) -> None:
        self._started_at = time.time()
        self.seed = load_seed_bundle(
            seed_dir or Path(__file__).resolve().parents[3] / "data" / "seed"
        )
        self._graph = Graph()
        for node in self.seed.nodes:
            self._graph.add_node(node)
        for edge in self.seed.edges:
            self._graph.add_edge(edge)

        flood_by_hex = {
            hid: float(payload["score"]) for hid, payload in self.seed.flood_hexes.items()
        }
        self.penalty = StaticPenalty(flood_by_hex=flood_by_hex)
        self.routing_engine = RoutingEngine(self._graph, self.penalty)

        self.feature_store = InMemoryFeatureStore()
        self._materialise_feature_store(flood_by_hex)

        self.eta_model = self._train_eta_model()
        self.flood_detector = self._train_flood_detector(flood_by_hex)
        self.eco_model = EcoModel()
        self.kanon_guard = KAnonGuard(min_k=50, source="api-gateway")

        self.signing_key = Ed25519PrivateKey.generate()
        self.public_key_pem = (
            self.signing_key.public_key()
            .public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            .decode("ascii")
        )

        demo_org = self.seed.orgs.get("org_demo") or Org(
            id="org_demo",
            name="Demo Org",
            tier="b2c",
            country="VN",
        )
        self.demo_org = demo_org
        self._api_keys = self.seed.api_keys

        # Pre-computed flood overlay used by /v1/route and /v1/flood-risk.
        self.flood_overlay = self._build_flood_overlay()

    # --- lifecycle -------------------------------------------------------------------

    @property
    def uptime_s(self) -> float:
        return time.time() - self._started_at

    # --- lookups ---------------------------------------------------------------------

    def lookup_api_key(self, key: str) -> Org | None:
        org_id = self._api_keys.get(key)
        if not org_id:
            return None
        return self.seed.orgs.get(org_id)

    @property
    def graph(self) -> Graph:
        return self._graph

    @property
    def fleets(self) -> list[dict[str, object]]:
        return self.seed.fleets

    @property
    def policies(self) -> list[dict[str, object]]:
        return self.seed.policies

    # --- helpers ---------------------------------------------------------------------

    def hex_centroid(self, hex_id: str) -> LatLon | None:
        # Compute by averaging the endpoints of edges tagged with the hex id.
        coords: list[tuple[float, float]] = []
        for edge in self.seed.edges:
            if edge.tags.get("hex_id") == hex_id:
                src = self._graph.nodes[edge.src]
                dst = self._graph.nodes[edge.dst]
                coords.append(((src.lng + dst.lng) / 2.0, (src.lat + dst.lat) / 2.0))
        if not coords:
            return None
        lng = sum(c[0] for c in coords) / len(coords)
        lat = sum(c[1] for c in coords) / len(coords)
        return LatLon(lat=lat, lng=lng)

    def hex_population(self, hex_id: str) -> int:
        return self.seed.demographics.get(hex_id, 2_000)

    def nearest_node(self, point: LatLon) -> Node:
        return self._graph.nearest_node(point.lng, point.lat)

    # --- internals -------------------------------------------------------------------

    def _build_flood_overlay(self) -> list[dict[str, object]]:
        overlay: list[dict[str, object]] = []
        for hex_id, info in self.seed.flood_hexes.items():
            centroid = self.hex_centroid(hex_id)
            if centroid is None:
                continue
            overlay.append(
                {
                    "hex_id": hex_id,
                    "centroid": centroid,
                    "score": float(info["score"]),
                    "horizon": "now",
                }
            )
        return overlay

    def _materialise_feature_store(self, flood_by_hex: dict[str, float]) -> None:
        seen: set[str] = set()
        for edge in self.seed.edges:
            hid = edge.tags.get("hex_id")
            if not hid or hid in seen:
                continue
            seen.add(hid)
            self.feature_store.ingest(
                "hex_speed_5min",
                hid,
                {
                    "avg_speed_kmh": edge.free_flow_speed_kmh * 0.78,
                    "speed_p10": edge.free_flow_speed_kmh * 0.45,
                    "speed_p50": edge.free_flow_speed_kmh * 0.78,
                    "speed_p90": edge.free_flow_speed_kmh,
                    "flow_in": 400,
                    "flow_out": 380,
                    "vehicle_count": 240,
                },
            )
            self.feature_store.ingest(
                "flood_score",
                hid,
                {
                    "score": flood_by_hex.get(hid, 0.05),
                    "confidence": 0.75,
                    "horizon_1h": min(1.0, flood_by_hex.get(hid, 0.05) * 1.1),
                    "horizon_3h": min(1.0, flood_by_hex.get(hid, 0.05) * 0.9),
                    "horizon_6h": min(1.0, flood_by_hex.get(hid, 0.05) * 0.7),
                },
            )

    def _train_eta_model(self) -> EtaModel:
        """Bootstrap the ETA model with synthetic-but-realistic training data."""
        rng = random.Random(99)
        rows: list[ETARecord] = []
        targets: list[float] = []
        for _ in range(900):
            distance = rng.uniform(500, 14_000)
            flow = rng.uniform(15, 50)
            free_flow = distance / 1_000 / flow * 3600
            hour = rng.randint(0, 167)
            weekend = 1 if hour % 24 >= 144 else 0
            precip = rng.choice([0.0, 0.0, 0.5, 2.5, 8.0, 18.0])
            rush = 1 if 16 <= (hour % 24) <= 19 else 0
            flood = rng.uniform(0.0, 0.6) if precip > 0 else 0.0
            row = ETARecord(
                distance_m=distance,
                free_flow_seconds=free_flow,
                hour_of_week=hour,
                is_weekend=weekend,
                precipitation_mm_h=precip,
                wind_kmh=rng.uniform(0, 35),
                is_rush_hour=rush,
                lag_speed_5min=flow - rng.uniform(0, 8),
                lag_speed_15min=flow - rng.uniform(0, 6),
                lag_speed_1h=flow,
                vehicle_count_5min=rng.uniform(60, 900),
                flood_score=flood,
                road_class_index=rng.randint(0, 6),
            )
            mult = 1.0 + 0.18 * rush + 0.5 * flood + 0.08 * (precip / 25.0)
            rows.append(row)
            targets.append(free_flow * mult + rng.uniform(-12, 12))
        model = EtaModel()
        model.fit(rows, targets)
        return model

    def _train_flood_detector(self, flood_by_hex: dict[str, float]) -> FloodDetector:
        observations: list[FloodObservation] = []
        for hex_id, score in flood_by_hex.items():
            observations.append(
                FloodObservation(
                    hex_id=hex_id,
                    speed_drop_pct=min(0.95, max(0.05, score)),
                    sar_water_prior=min(0.95, max(0.04, score * 0.9)),
                    crowd_reports=2 if score > 0.5 else 0,
                    precipitation_mm_h=18.0 if score > 0.5 else 1.0,
                )
            )
        # Pad with synthetic dry hexes so IsolationForest has variation.
        for i in range(80):
            observations.append(
                FloodObservation(
                    hex_id=f"hex_dry_{i:02d}",
                    speed_drop_pct=0.05,
                    sar_water_prior=0.02,
                    crowd_reports=0,
                    precipitation_mm_h=0.5,
                )
            )
        detector = FloodDetector(contamination=0.15)
        detector.fit(observations)
        return detector


# --- Global accessor ---------------------------------------------------------------


_state: AppState | None = None


def get_app_state() -> AppState:
    global _state
    if _state is None:
        _state = AppState()
    return _state


def reset_app_state() -> None:
    global _state
    _state = None
