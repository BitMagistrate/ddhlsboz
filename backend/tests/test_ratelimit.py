"""Тесты rate-limit middleware и idempotency cache."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.ratelimit import RateLimiter, get_limiter, reset_limiter


@pytest.fixture(autouse=True)
def _reset_limiter():
    """Перед каждым тестом — чистый стейт."""
    reset_limiter()
    yield
    reset_limiter()


def test_bucket_consume_allows_until_empty():
    limiter = RateLimiter(rpm=60, burst=3)
    # 3 запроса проходят (burst=3), 4-й — нет.
    assert asyncio.run(limiter.check("user:x"))
    assert asyncio.run(limiter.check("user:x"))
    assert asyncio.run(limiter.check("user:x"))
    assert not asyncio.run(limiter.check("user:x"))


def test_bucket_refills_over_time(monkeypatch):
    limiter = RateLimiter(rpm=60, burst=2)
    # rpm=60 → 1 токен/сек
    # Опустошаем bucket
    assert asyncio.run(limiter.check("user:y"))
    assert asyncio.run(limiter.check("user:y"))
    assert not asyncio.run(limiter.check("user:y"))

    # Подменяем `time.monotonic` чтобы ускорить тест
    bucket = limiter._buckets["user:y"]
    bucket.last_refill -= 5  # 5 секунд назад
    assert asyncio.run(limiter.check("user:y"))


def test_different_keys_have_independent_buckets():
    limiter = RateLimiter(rpm=60, burst=1)
    assert asyncio.run(limiter.check("user:a"))
    assert not asyncio.run(limiter.check("user:a"))
    assert asyncio.run(limiter.check("user:b"))


def test_idempotency_replay_matches_body():
    limiter = RateLimiter(rpm=60, burst=10)
    body = {"query": "hello", "weeks": 4}
    asyncio.run(limiter.store("key-1", body, {"payload": "first"}))
    cached = asyncio.run(limiter.get_cached("key-1", body))
    assert cached is not None
    assert cached.payload == {"payload": "first"}


def test_idempotency_misses_when_body_differs():
    limiter = RateLimiter(rpm=60, burst=10)
    asyncio.run(limiter.store("key-2", {"q": "a"}, {"x": 1}))
    cached = asyncio.run(limiter.get_cached("key-2", {"q": "b"}))
    assert cached is None


def test_idempotency_expires_after_ttl():
    limiter = RateLimiter(rpm=60, burst=10, idempotency_ttl=1)
    asyncio.run(limiter.store("key-3", {"q": "a"}, {"x": 1}))
    entry = limiter._idempotency["key-3"]
    entry.created -= 60  # «прошла минута»
    cached = asyncio.run(limiter.get_cached("key-3", {"q": "a"}))
    assert cached is None


def test_curator_route_returns_429_when_exceeded(monkeypatch):
    """API уровень: после burst-а отдаёт 429 с понятным телом."""
    monkeypatch.setenv("CHITAI_RATE_LIMIT_PER_MIN", "1")
    monkeypatch.setenv("CHITAI_RATE_LIMIT_BURST", "1")
    # Пересоздаём лимитер с новой конфигой
    import app.ratelimit as rl

    rl._LIMITER = None  # noqa: SLF001
    client = TestClient(app)
    payload = {"query": "Пушкин и тема чести", "weeks": 2}
    r1 = client.post("/api/curator/route", json=payload)
    assert r1.status_code == 200
    r2 = client.post("/api/curator/route", json=payload)
    assert r2.status_code == 429
    body = r2.json()["detail"]
    assert body["error"] == "rate_limited"
    assert "limit_per_minute" in body


def test_idempotency_key_replays_response():
    """Тот же `Idempotency-Key` + тело → тот же ответ, _idempotency_replay=True."""
    client = TestClient(app)
    payload = {"query": "Пушкин и тема чести", "weeks": 2}
    headers = {"Idempotency-Key": "test-replay-1"}
    r1 = client.post("/api/curator/route", json=payload, headers=headers)
    assert r1.status_code == 200
    r2 = client.post("/api/curator/route", json=payload, headers=headers)
    assert r2.status_code == 200
    assert r2.json().get("_idempotency_replay") is True


def test_idempotency_key_with_different_body_does_not_replay():
    client = TestClient(app)
    headers = {"Idempotency-Key": "test-different-body"}
    r1 = client.post(
        "/api/curator/route",
        json={"query": "Пушкин и тема чести", "weeks": 2},
        headers=headers,
    )
    assert r1.status_code == 200
    r2 = client.post(
        "/api/curator/route",
        json={"query": "Толстой и эпопея", "weeks": 2},
        headers=headers,
    )
    assert r2.status_code == 200
    # Тело другое → не replay
    assert r2.json().get("_idempotency_replay") is not True


def test_mindmap_also_rate_limited(monkeypatch):
    monkeypatch.setenv("CHITAI_RATE_LIMIT_PER_MIN", "1")
    monkeypatch.setenv("CHITAI_RATE_LIMIT_BURST", "1")
    import app.ratelimit as rl

    rl._LIMITER = None  # noqa: SLF001
    client = TestClient(app)
    payload = {"query": "Пушкин и тема чести", "limit": 4}
    r1 = client.post("/api/curator/mindmap", json=payload)
    assert r1.status_code == 200
    r2 = client.post("/api/curator/mindmap", json=payload)
    assert r2.status_code == 429


def test_user_id_in_body_is_used_as_key():
    """Два разных user_id — независимые лимиты."""
    limiter = get_limiter()
    from app.ratelimit import extract_client_key

    class _Req:
        headers: dict[str, str] = {}
        client = None

    assert extract_client_key(_Req(), {"user_id": "alice"}) == "user:alice"
    assert extract_client_key(_Req(), {"user_id": "bob"}) == "user:bob"
    assert extract_client_key(_Req(), {"user_id": "  "}).startswith("ip:")
    # Lock уважается
    assert limiter is get_limiter()
