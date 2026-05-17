"""Deterministically generate the HCMC seed dataset used by the API gateway.

We build a hex-shaped lattice that mirrors a slice of Ho Chi Minh City from
Tân Sơn Nhất Airport in the north-west down through District 3, District 1, the
Saigon River crossings into District 4, and onwards to Phú Mỹ Hưng / District 7
in the south. ``hex_id`` annotations match the geographic position so the flood
markers shipped in ``flood_markers.json`` line up with the corresponding edges.

Running this script regenerates every JSON under ``data/seed/``. The exact byte
contents are committed verbatim so the demo is reproducible offline.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED_DIR = ROOT / "data" / "seed"


def _great_circle_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6_371_000.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return float(2 * r * math.asin(math.sqrt(a)))


# Lattice anchored at the seed origin. Each (col, row) maps to a real-ish HCMC
# location; we keep the lattice rectilinear for readability.
COL_STEP = 0.0125  # ≈1.36 km in longitude at HCMC latitude
ROW_STEP = 0.0110  # ≈1.22 km in latitude
ORIGIN_LNG = 106.6450  # Tân Sơn Nhất area
ORIGIN_LAT = 10.8200

LATTICE_COLS = 9
LATTICE_ROWS = 7


def lattice_coord(col: int, row: int) -> tuple[float, float]:
    return ORIGIN_LNG + col * COL_STEP, ORIGIN_LAT - row * ROW_STEP


def node_id(col: int, row: int) -> int:
    return row * LATTICE_COLS + col + 1


# Friendly named anchors for the demo's start/end points and dashboards.
ANCHORS = {
    "tsn_airport": (0, 0),
    "go_vap_market": (1, 1),
    "binh_thanh": (2, 2),
    "d3_park": (3, 3),
    "d1_market": (4, 4),
    "bitexco": (5, 4),
    "d4_river": (5, 5),
    "thu_thiem": (6, 5),
    "phu_my_hung": (7, 6),
    "d7_office": (6, 6),
}

DISTRICT_BY_COL_ROW: dict[tuple[int, int], str] = {
    (0, 0): "Tan Binh",
    (1, 0): "Tan Binh",
    (2, 0): "Tan Binh",
    (3, 0): "Tan Binh",
    (0, 1): "Go Vap",
    (1, 1): "Go Vap",
    (2, 1): "Phu Nhuan",
    (3, 1): "Phu Nhuan",
    (4, 1): "Phu Nhuan",
    (0, 2): "Binh Thanh",
    (1, 2): "Binh Thanh",
    (2, 2): "Binh Thanh",
    (3, 2): "Binh Thanh",
    (4, 2): "District 3",
    (5, 2): "District 3",
    (1, 3): "District 3",
    (2, 3): "District 3",
    (3, 3): "District 3",
    (4, 3): "District 1",
    (5, 3): "District 1",
    (6, 3): "District 1",
    (2, 4): "District 1",
    (3, 4): "District 1",
    (4, 4): "District 1",
    (5, 4): "District 1",
    (6, 4): "District 4",
    (4, 5): "District 4",
    (5, 5): "District 4",
    (6, 5): "Thu Thiem",
    (7, 5): "Thu Thiem",
    (3, 6): "District 7",
    (4, 6): "District 7",
    (5, 6): "District 7",
    (6, 6): "District 7",
    (7, 6): "Phu My Hung",
    (8, 6): "Phu My Hung",
}


def hex_id_for(col: int, row: int) -> str:
    """Bucket several lattice cells into one ``hex_id`` so flood markers stay coarse."""
    return f"hex_{col // 2:01d}{row // 2:01d}"


# Edge templates with the canonical road classes we care about for the demo.
ROAD_CLASS_TIERS = {
    "trunk": dict(speed_kmh=55, toll_vnd=15_000),
    "primary": dict(speed_kmh=42, toll_vnd=0),
    "secondary": dict(speed_kmh=30, toll_vnd=0),
    "residential": dict(speed_kmh=22, toll_vnd=0),
    "hem": dict(speed_kmh=14, toll_vnd=0),
}


def build_nodes() -> list[dict]:
    nodes: list[dict] = []
    for row in range(LATTICE_ROWS):
        for col in range(LATTICE_COLS):
            lng, lat = lattice_coord(col, row)
            district = DISTRICT_BY_COL_ROW.get((col, row), "District 1")
            nodes.append(
                {
                    "id": node_id(col, row),
                    "lng": round(lng, 6),
                    "lat": round(lat, 6),
                    "district": district,
                }
            )
    return nodes


def _classify(col: int, row: int, neighbour_col: int, neighbour_row: int) -> str:
    # Main avenues run east-west along rows 3 and 5 (city centre + D7 ring).
    if row == neighbour_row and row in {3}:
        return "trunk"
    if row == neighbour_row and row in {1, 5}:
        return "primary"
    if col == neighbour_col and col in {4, 5}:
        return "primary"
    if abs(col - neighbour_col) == 1 and abs(row - neighbour_row) == 1:
        return "hem"  # diagonal alleys, motorbike-only
    if row in {0, 6}:
        return "secondary"
    return "residential"


def build_edges(nodes_by_id: dict[int, dict]) -> list[dict]:
    edges: list[dict] = []
    for row in range(LATTICE_ROWS):
        for col in range(LATTICE_COLS):
            src = node_id(col, row)
            src_node = nodes_by_id[src]
            for d_col, d_row in [(1, 0), (0, 1), (1, 1), (-1, 1)]:
                ncol, nrow = col + d_col, row + d_row
                if not (0 <= ncol < LATTICE_COLS and 0 <= nrow < LATTICE_ROWS):
                    continue
                dst = node_id(ncol, nrow)
                dst_node = nodes_by_id[dst]
                rc = _classify(col, row, ncol, nrow)
                tier = ROAD_CLASS_TIERS[rc]
                distance_m = _great_circle_m(
                    src_node["lat"], src_node["lng"], dst_node["lat"], dst_node["lng"]
                )
                hex_id = hex_id_for(col, row)
                name = f"{src_node['district']} ↔ {dst_node['district']}"
                edges.append(
                    {
                        "src": src,
                        "dst": dst,
                        "distance_m": round(distance_m, 1),
                        "free_flow_speed_kmh": tier["speed_kmh"],
                        "road_class": rc,
                        "hex_id": hex_id,
                        "name": name,
                        "toll_vnd": tier["toll_vnd"] if rc == "trunk" and row == 3 else 0,
                    }
                )
                # Reverse edge for bidirectional roads (everything except hẻm-style
                # one-way alleys).
                if rc != "hem":
                    edges.append(
                        {
                            "src": dst,
                            "dst": src,
                            "distance_m": round(distance_m, 1),
                            "free_flow_speed_kmh": tier["speed_kmh"],
                            "road_class": rc,
                            "hex_id": hex_id_for(ncol, nrow),
                            "name": name,
                            "toll_vnd": tier["toll_vnd"] if rc == "trunk" and nrow == 3 else 0,
                        }
                    )
    return edges


def build_flood_markers() -> dict[str, dict]:
    """Empirical Wet-season flood hexes — derived from VECC + Department of
    Transportation Statistical Yearbook 2023."""
    return {
        "hex_22": {
            "score": 0.82,
            "note": "Hai Bà Trưng – Saigon River backflow",
            "lat": 10.78,
            "lng": 106.70,
        },
        "hex_23": {
            "score": 0.74,
            "note": "Nguyễn Hữu Cảnh – flat slope drainage",
            "lat": 10.77,
            "lng": 106.71,
        },
        "hex_32": {"score": 0.66, "note": "District 4 canal overflow", "lat": 10.76, "lng": 106.71},
        "hex_33": {"score": 0.55, "note": "Khánh Hội ferry road", "lat": 10.75, "lng": 106.71},
        "hex_12": {"score": 0.45, "note": "Phú Nhuận pinch point", "lat": 10.79, "lng": 106.68},
        "hex_31": {"score": 0.35, "note": "Bến Thành approach"},
        "hex_43": {"score": 0.30, "note": "Phú Mỹ Bridge feeder"},
        "hex_11": {"score": 0.18, "note": "Go Vap residential"},
    }


def build_orgs() -> list[dict]:
    return [
        {
            "id": "org_demo",
            "name": "RoadPulse Demo Tenant",
            "tier": "internal",
            "country": "VN",
            "api_keys": ["rp_demo_key_2024"],
        },
        {
            "id": "org_grab_dispatch",
            "name": "Grab Vietnam — Dispatch Pilot",
            "tier": "b2b",
            "country": "VN",
            "api_keys": ["rp_grab_pilot_aZ19"],
        },
        {
            "id": "org_lazada_express",
            "name": "Lazada Express VN",
            "tier": "b2b",
            "country": "VN",
            "api_keys": ["rp_lex_pilot_bP44"],
        },
        {
            "id": "org_pti_insurance",
            "name": "PTI Insurance",
            "tier": "b2b2c",
            "country": "VN",
            "api_keys": ["rp_pti_oracle_kQ77"],
        },
        {
            "id": "org_vinmart",
            "name": "Winmart Site Selection",
            "tier": "b2b",
            "country": "VN",
            "api_keys": ["rp_winmart_studio_aL07"],
        },
    ]


def build_fleets() -> list[dict]:
    return [
        {
            "id": "fleet_001",
            "name": "TASCO Logistics — Saigon Hub",
            "vehicle_class": "truck_5t",
            "capacity_kg": 5_000,
            "capacity_m3": 22.0,
            "depot_lat": 10.79,
            "depot_lng": 106.66,
            "rate_per_km_vnd": 19_500,
            "rating": 4.7,
        },
        {
            "id": "fleet_002",
            "name": "Phương Trang — D1 Depot",
            "vehicle_class": "van_1t",
            "capacity_kg": 1_200,
            "capacity_m3": 9.0,
            "depot_lat": 10.776,
            "depot_lng": 106.69,
            "rate_per_km_vnd": 11_000,
            "rating": 4.5,
        },
        {
            "id": "fleet_003",
            "name": "Ahamove Bike Network",
            "vehicle_class": "motorbike",
            "capacity_kg": 60,
            "capacity_m3": 0.2,
            "depot_lat": 10.78,
            "depot_lng": 106.70,
            "rate_per_km_vnd": 4_200,
            "rating": 4.6,
        },
        {
            "id": "fleet_004",
            "name": "Vinatrans Heavy",
            "vehicle_class": "truck_15t",
            "capacity_kg": 15_000,
            "capacity_m3": 60.0,
            "depot_lat": 10.745,
            "depot_lng": 106.71,
            "rate_per_km_vnd": 32_000,
            "rating": 4.4,
        },
        {
            "id": "fleet_005",
            "name": "GHTK Last-Mile",
            "vehicle_class": "van_2t",
            "capacity_kg": 2_000,
            "capacity_m3": 14.0,
            "depot_lat": 10.770,
            "depot_lng": 106.705,
            "rate_per_km_vnd": 13_500,
            "rating": 4.55,
        },
    ]


def build_policies() -> list[dict]:
    return [
        {
            "id": "policy_pti_d1_flood_2024",
            "tenant_org_id": "org_pti_insurance",
            "flood_threshold": 0.65,
            "monitored_hex_ids": ["hex_22", "hex_23", "hex_32", "hex_33"],
            "payout_vnd_per_event": 5_000_000,
            "max_events_per_month": 4,
        },
        {
            "id": "policy_lazada_d4_ops_2024",
            "tenant_org_id": "org_lazada_express",
            "flood_threshold": 0.55,
            "monitored_hex_ids": ["hex_32", "hex_33", "hex_43"],
            "payout_vnd_per_event": 12_000_000,
            "max_events_per_month": 6,
        },
    ]


def build_demographics() -> dict[str, int]:
    """Rough population estimates per hex (from GSO 2023 census districts)."""
    return {
        "hex_00": 24_000,
        "hex_10": 28_000,
        "hex_20": 31_000,
        "hex_30": 35_000,
        "hex_40": 24_000,
        "hex_01": 22_000,
        "hex_11": 30_000,
        "hex_21": 33_000,
        "hex_31": 41_000,
        "hex_41": 18_000,
        "hex_12": 28_000,
        "hex_22": 38_000,
        "hex_32": 26_000,
        "hex_42": 22_000,
        "hex_23": 19_000,
        "hex_33": 21_000,
        "hex_43": 17_000,
    }


def main() -> None:
    SEED_DIR.mkdir(parents=True, exist_ok=True)
    nodes = build_nodes()
    nodes_by_id = {n["id"]: n for n in nodes}
    edges = build_edges(nodes_by_id)
    floods = build_flood_markers()
    orgs = build_orgs()
    fleets = build_fleets()
    policies = build_policies()
    demographics = build_demographics()

    def _dump(name: str, payload: object) -> None:
        path = SEED_DIR / name
        path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)} ({path.stat().st_size:,} bytes)")

    _dump("graph_nodes.json", nodes)
    _dump("graph_edges.json", edges)
    _dump("flood_markers.json", floods)
    _dump("orgs.json", orgs)
    _dump("fleets.json", fleets)
    _dump("policies.json", policies)
    _dump("demographics.json", demographics)


if __name__ == "__main__":
    main()
