"""Smoke-тесты HTTP-эндпоинтов через FastAPI TestClient.

В CI ключи не выставлены → роутер должен честно отдавать mock-ответы,
эндпоинты работать, и источники — браться из корпуса без подмены.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.llm.router import reset_router
from app.main import app


@pytest.fixture(autouse=True)
def _no_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """Сбрасываем все LLM-ключи и переинициализируем роутер.

    Это гарантирует, что в CI мы не уйдём в живые сети, даже если у разработчика
    случайно загрузился .env через dotenv.
    """
    for var in (
        "YANDEX_GPT_API_KEY",
        "YANDEX_GPT_FOLDER_ID",
        "GIGACHAT_AUTHORIZATION_KEY",
        "GIGACHAT_SCOPE",
    ):
        monkeypatch.delenv(var, raising=False)
    reset_router()


def test_healthz() -> None:
    with TestClient(app) as client:
        r = client.get("/healthz")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


def test_info_lists_russian_stack_only() -> None:
    with TestClient(app) as client:
        body = client.get("/api/info").json()
        stack = " ".join(body["stack"])
        assert "YandexGPT" in stack
        assert "GigaChat" in stack
        assert "OpenAI" not in stack
        assert "Claude" not in stack


def test_corpus_search() -> None:
    with TestClient(app) as client:
        r = client.get("/api/corpus/search", params={"q": "Пушкин", "limit": 3})
        assert r.status_code == 200
        body = r.json()
        assert body["count"] >= 1
        assert all("title" in s for s in body["items"])


def test_curator_route_returns_route_with_citations() -> None:
    with TestClient(app) as client:
        r = client.post("/api/curator/route", json={"query": "пушкин онегин", "weeks": 2})
        assert r.status_code == 200
        body = r.json()
        assert body["weeks"]
        assert body["llm_provider"] == "mock"  # без ключей → mock
        for w in body["weeks"]:
            assert w["fragment"]
            assert w["citation"]
            assert w["public_domain_url"]


def test_llm_status_no_secrets() -> None:
    with TestClient(app) as client:
        r = client.get("/api/llm/status")
        assert r.status_code == 200
        body = r.json()
        names = [p["name"] for p in body["providers"]]
        assert set(names) >= {"yandex", "gigachat"}
        # Ни одно поле не содержит фактических ключей.
        blob = r.text
        assert "Api-Key" not in blob
        assert "Bearer" not in blob


def test_trainer_quiz_returns_questions_without_answers() -> None:
    with TestClient(app) as client:
        r = client.get("/api/trainer/quiz", params={"subject": "Литература", "limit": 3})
        assert r.status_code == 200
        body = r.json()
        assert body["items"]
        for q in body["items"]:
            assert "answer" not in q  # ответ скрыт
