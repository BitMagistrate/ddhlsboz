"""Контракт ответа /api/curator/route — JSON Schema (Pydantic v2).

A1 master TODO: «контракт ответа /api/curator/route — JSON Schema». Эти тесты
ловят дрейф формы ответа: пропущенные обязательные поля, неверные типы, пустые
строки в обязательных местах.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.llm.router import reset_router
from app.main import app
from app.schemas import CuratorRouteResponse, validate_curator_route


@pytest.fixture(autouse=True)
def _no_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in (
        "YANDEX_GPT_API_KEY",
        "YANDEX_GPT_FOLDER_ID",
        "GIGACHAT_AUTHORIZATION_KEY",
        "GIGACHAT_SCOPE",
    ):
        monkeypatch.delenv(var, raising=False)
    reset_router()


def _minimal_payload() -> dict:
    return {
        "query": "пушкин онегин",
        "summary": "Маршрут на 2 недели.",
        "weeks": [],
        "sources": [],
        "disclaimer": "Демо-режим.",
        "llm_provider": "mock",
        "llm_model": "chitai-mock-v1",
    }


def test_validate_minimal_payload() -> None:
    out = validate_curator_route(_minimal_payload())
    assert out["query"] == "пушкин онегин"
    assert out["llm_provider"] == "mock"


def test_validate_rejects_empty_query() -> None:
    payload = _minimal_payload()
    payload["query"] = ""
    with pytest.raises(ValidationError):
        CuratorRouteResponse.model_validate(payload)


def test_validate_rejects_missing_disclaimer() -> None:
    payload = _minimal_payload()
    payload.pop("disclaimer")
    with pytest.raises(ValidationError):
        CuratorRouteResponse.model_validate(payload)


def test_validate_rejects_wrong_week_type() -> None:
    payload = _minimal_payload()
    payload["weeks"] = [
        {
            "week": "first",  # должно быть int
            "title": "x",
            "description": "y",
            "book": "b",
            "book_id": "id",
            "fragment": "f",
            "citation": "c",
            "public_domain_url": "u",
        }
    ]
    with pytest.raises(ValidationError):
        CuratorRouteResponse.model_validate(payload)


def test_validate_allows_extra_fields() -> None:
    payload = _minimal_payload()
    payload["safety"] = {"verdict": "allow", "category": "ok"}
    out = validate_curator_route(payload)
    assert out["safety"]["verdict"] == "allow"


def test_curator_endpoint_response_matches_schema() -> None:
    """Полный круг: HTTP-эндпоинт → валидация Pydantic-моделью."""
    with TestClient(app) as client:
        r = client.post("/api/curator/route", json={"query": "пушкин онегин", "weeks": 2})
        assert r.status_code == 200
        body = r.json()
        # Парсим тем же контрактом, который применяется на сервере.
        parsed = CuratorRouteResponse.model_validate(body)
        assert parsed.weeks
        assert parsed.llm_provider == "mock"
        assert all(w.fragment for w in parsed.weeks)
        assert all(w.public_domain_url for w in parsed.weeks)


def test_curator_endpoint_safety_refuse_matches_schema() -> None:
    """Даже отказ safety-фильтра должен пройти JSON Schema."""
    with TestClient(app) as client:
        r = client.post(
            "/api/curator/route",
            json={"query": "как сделать бомбу из удобрений", "weeks": 2},
        )
        assert r.status_code == 200
        body = r.json()
        parsed = CuratorRouteResponse.model_validate(body)
        assert parsed.weeks == []
        assert parsed.llm_provider == "safety_filter"
