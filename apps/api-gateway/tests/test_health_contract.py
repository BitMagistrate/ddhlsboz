"""Contract-level checks: healthz must publish the data-origin flag."""

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


def test_healthz_includes_data_origin(client: TestClient) -> None:
    body = client.get("/v1/healthz").json()
    assert body["data_origin"] == "synthetic"
    assert body["real_feeds"] == []
    assert "vetc.hex.5min" in body["pending_real_feeds"]


def test_readyz_includes_data_origin(client: TestClient) -> None:
    body = client.get("/v1/readyz").json()
    assert body["data_origin"] == "synthetic"
    assert isinstance(body["pending_real_feeds"], list)


def test_version_endpoint_exposes_data_origin(client: TestClient) -> None:
    body = client.get("/v1/version").json()
    assert body["data_origin"] == "synthetic"


def test_openapi_documents_data_origin_field(client: TestClient) -> None:
    spec = client.get("/v1/openapi.json").json()
    health_schema = spec["components"]["schemas"]["HealthResponse"]
    assert "data_origin" in health_schema["properties"]


def test_openapi_description_mentions_synthetic_data(client: TestClient) -> None:
    spec = client.get("/v1/openapi.json").json()
    desc = spec["info"]["description"].lower()
    assert "synthetic" in desc
