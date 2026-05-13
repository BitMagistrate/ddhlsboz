"""Тесты circuit breaker в LLM-роутере."""

from __future__ import annotations

import asyncio

import pytest

from app.llm.base import LLMError, LLMMessage, LLMResponse
from app.llm.router import CircuitBreaker, LLMRouter


class _FlakyProvider:
    name = "flaky"
    model = "flaky-1"

    def __init__(self, *, fail_n: int = 0, configured: bool = True) -> None:
        self._left = fail_n
        self._configured = configured
        self.calls = 0

    async def is_configured(self) -> bool:
        return self._configured

    async def complete(self, messages, *, temperature=0.3, max_tokens=400, timeout=None) -> LLMResponse:
        self.calls += 1
        if self._left > 0:
            self._left -= 1
            raise LLMError("simulated boom")
        return LLMResponse(provider=self.name, model=self.model, text="ok", raw={})


def test_breaker_starts_closed():
    br = CircuitBreaker()
    assert br.state == "closed"
    assert asyncio.run(br.allow())


def test_breaker_opens_after_threshold():
    br = CircuitBreaker(failure_threshold=2, cooldown_seconds=60)
    asyncio.run(br.record_failure())
    assert br.state == "closed"
    asyncio.run(br.record_failure())
    assert br.state == "open"
    assert asyncio.run(br.allow()) is False


def test_breaker_half_open_after_cooldown():
    br = CircuitBreaker(failure_threshold=1, cooldown_seconds=1)
    asyncio.run(br.record_failure())
    assert br.state == "open"
    br._opened_at -= 60  # «прошёл cooldown»
    allowed = asyncio.run(br.allow())
    assert allowed is True
    assert br.state == "half_open"
    # Второй probe в half_open запрещён.
    assert asyncio.run(br.allow()) is False


def test_half_open_success_closes_breaker():
    br = CircuitBreaker(failure_threshold=1, cooldown_seconds=1)
    asyncio.run(br.record_failure())
    br._opened_at -= 60
    asyncio.run(br.allow())  # half_open
    asyncio.run(br.record_success())
    assert br.state == "closed"


def test_half_open_failure_reopens():
    br = CircuitBreaker(failure_threshold=1, cooldown_seconds=1)
    asyncio.run(br.record_failure())
    br._opened_at -= 60
    asyncio.run(br.allow())  # half_open
    asyncio.run(br.record_failure())
    assert br.state == "open"


@pytest.mark.asyncio
async def test_router_uses_secondary_when_primary_breaker_open():
    primary = _FlakyProvider(fail_n=5)
    secondary = _FlakyProvider(fail_n=0)
    router = LLMRouter(primary=primary, secondary=secondary, failure_threshold=2, cooldown_seconds=60)
    msgs = [LLMMessage(role="user", content="hi")]
    # Первая попытка: primary падает, secondary отвечает.
    r1 = await router.complete(msgs)
    assert r1.provider == "flaky"  # secondary
    # Второй провал primary → breaker opens, дальше primary не вызывается.
    primary_calls_before = primary.calls
    r2 = await router.complete(msgs)
    assert r2.provider == "flaky"  # secondary
    # breaker для primary опен → primary calls больше не растут
    primary.calls_after = primary.calls
    assert router.breakers["primary"].state == "open"
    # Дополнительный вызов: primary не должен вызываться (breaker open).
    primary._left = 5  # потенциально мог бы упасть, но breaker не пустит
    await router.complete(msgs)
    assert primary.calls == primary_calls_before + 1  # не вырос дальше


@pytest.mark.asyncio
async def test_router_status_includes_breaker_state():
    primary = _FlakyProvider(fail_n=0)
    secondary = _FlakyProvider(fail_n=0)
    router = LLMRouter(primary=primary, secondary=secondary, failure_threshold=2, cooldown_seconds=60)
    status = await router.status()
    slots = [p["slot"] for p in status["providers"]]
    assert slots == ["primary", "secondary"]
    for p in status["providers"]:
        assert p["breaker"] in ("closed", "open", "half_open")


@pytest.mark.asyncio
async def test_not_configured_does_not_open_breaker():
    """`is_configured() == False` — это «нет ключей», не сбой. Не считаем за failure."""
    primary = _FlakyProvider(configured=False)
    secondary = _FlakyProvider(fail_n=0)
    router = LLMRouter(primary=primary, secondary=secondary, failure_threshold=1, cooldown_seconds=60)
    msgs = [LLMMessage(role="user", content="hi")]
    await router.complete(msgs)
    await router.complete(msgs)
    assert router.breakers["primary"].state == "closed"
