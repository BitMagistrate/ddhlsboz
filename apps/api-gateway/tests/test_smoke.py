"""End-to-end smoke tests for every public router.

These are exercised against the FastAPI ``TestClient`` so they cover middleware,
dependency injection, the seeded HCMC graph and the ML models in one go.
"""

from __future__ import annotations

import pytest
from app.main import app
from app.state import reset_app_state
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client() -> TestClient:
    reset_app_state()
    with TestClient(app) as tc:
        yield tc
    reset_app_state()


def test_healthz_returns_ok(client: TestClient) -> None:
    resp = client.get("/v1/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in {"ok", "degraded"}
    assert body["version"]
    assert "x-trace-id" in resp.headers


def test_version_endpoint(client: TestClient) -> None:
    resp = client.get("/v1/version")
    assert resp.status_code == 200
    assert resp.json()["service"] == "api-gateway"


def test_route_returns_three_variants(client: TestClient) -> None:
    payload = {
        # Tan Son Nhat airport area → Phu My Hung
        "origin": {"lat": 10.820, "lng": 106.645},
        "destination": {"lat": 10.754, "lng": 106.733},
        "mode": "motorbike",
        "avoid_flood": True,
    }
    resp = client.post("/v1/route", json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert {v["name"] for v in body["variants"]} == {"fast", "safe", "eco"}
    for variant in body["variants"]:
        assert variant["distance_m"] > 0
        assert variant["duration_s"] > 0
        assert variant["geometry"]
        assert variant["steps"]
        assert 0.0 <= variant["flood_score"] <= 1.0
        assert variant["co2_g"] >= 0.0
    assert body["flood_overlay"]


def test_route_rejects_same_origin_destination(client: TestClient) -> None:
    payload = {
        "origin": {"lat": 10.820, "lng": 106.645},
        "destination": {"lat": 10.820, "lng": 106.645},
    }
    resp = client.post("/v1/route", json=payload)
    assert resp.status_code == 400


def test_eta_batch_returns_predictions(client: TestClient) -> None:
    payload = {
        "batch_id": "batch_demo_001",
        "items": [
            {
                "order_id": f"ord_{i:03d}",
                "origin": {"lat": 10.820, "lng": 106.645},
                "destination": {"lat": 10.754, "lng": 106.733},
            }
            for i in range(5)
        ],
    }
    resp = client.post("/v1/eta-batch", json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["batch_id"] == "batch_demo_001"
    assert len(body["predictions"]) == 5
    assert body["summary"]["n_orders"] == 5


def test_isochrone_returns_rings(client: TestClient) -> None:
    payload = {
        "origin": {"lat": 10.780, "lng": 106.700},
        "minutes": [5, 10, 15],
    }
    resp = client.post("/v1/isochrone", json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [r["minutes"] for r in body["rings"]] == [5, 10, 15]


def test_flood_risk_returns_overlay(client: TestClient) -> None:
    resp = client.get("/v1/flood-risk")
    assert resp.status_code == 200
    body = resp.json()
    assert body["horizon"] == "now"
    assert body["hexes"]


def test_flood_risk_filters_by_horizon(client: TestClient) -> None:
    resp = client.get("/v1/flood-risk?horizon=6h")
    assert resp.status_code == 200
    assert resp.json()["horizon"] == "6h"


def test_site_selection_ranks_cells(client: TestClient) -> None:
    payload = {
        "bbox": [106.64, 10.73, 106.78, 10.83],
        "audience": "retail",
    }
    resp = client.post("/v1/site-selection", json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["top_cells"]
    scores = [c["score"] for c in body["top_cells"]]
    assert scores == sorted(scores, reverse=True)


def test_fleet_match_returns_candidates(client: TestClient) -> None:
    payload = {
        "pickup": {"lat": 10.780, "lng": 106.700},
        "dropoff": {"lat": 10.754, "lng": 106.733},
        "weight_kg": 800.0,
        "volume_m3": 5.0,
        "mode": "truck",
    }
    resp = client.post("/v1/fleet-match", json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["candidates"]
    # Sorted by ETA ascending.
    etas = [c["pickup_eta_min"] for c in body["candidates"]]
    assert etas == sorted(etas)


def test_trigger_feed_returns_signed_events(client: TestClient) -> None:
    resp = client.get("/v1/trigger-feed/policy_pti_d1_flood_2024")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["policy_id"] == "policy_pti_d1_flood_2024"
    if body["events"]:
        first = body["events"][0]
        assert first["payload_alg"] == "Ed25519"
        assert first["payload_signature"]


def test_trigger_feed_404_for_unknown_policy(client: TestClient) -> None:
    resp = client.get("/v1/trigger-feed/policy_does_not_exist")
    assert resp.status_code == 404


def test_trigger_feed_pubkey_is_pem(client: TestClient) -> None:
    resp = client.get("/v1/trigger-feed/policy_pti_d1_flood_2024/pubkey")
    assert resp.status_code == 200
    assert "BEGIN PUBLIC KEY" in resp.text


def test_openapi_document_is_served(client: TestClient) -> None:
    resp = client.get("/v1/openapi.json")
    assert resp.status_code == 200
    spec = resp.json()
    assert spec["info"]["title"] == "RoadPulse Public API"
    assert "/v1/route" in spec["paths"]
