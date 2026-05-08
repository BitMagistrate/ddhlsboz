"""Тесты RAG-конвейера: build_route_async с mock-LLM, fallback, источники без подмены."""

from __future__ import annotations

import pytest

from app.llm import LLMError, LLMMessage, LLMProvider, LLMResponse, LLMRouter, MockProvider
from app.rag import build_route_async


class _StubProvider(LLMProvider):
    """Возвращает фиксированный текст или поднимает LLMError."""

    name = "stub"
    model = "stub-1"

    def __init__(self, text: str = "stub-ответ", fail: bool = False) -> None:
        self.text = text
        self.fail = fail
        self.calls = 0

    async def is_configured(self) -> bool:
        return True

    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.3,
        max_tokens: int = 400,
        timeout: float | None = None,
    ) -> LLMResponse:
        self.calls += 1
        if self.fail:
            raise LLMError("stub: forced failure")
        return LLMResponse(
            text=self.text,
            provider=self.name,
            model=self.model,
            prompt_tokens=1,
            completion_tokens=1,
            total_tokens=2,
            raw={"stub": True},
        )


@pytest.mark.asyncio
async def test_build_route_uses_stub_provider_for_descriptions() -> None:
    stub = _StubProvider(text="Эта неделя — про Пушкина.")
    router = LLMRouter(primary=stub, secondary=None, fallback=MockProvider())
    route = await build_route_async("пушкин онегин", weeks=2, router=router)
    assert len(route.weeks) == 2
    assert route.llm_provider == "stub"
    for w in route.weeks:
        assert w.description == "Эта неделя — про Пушкина."
        assert w.llm_provider == "stub"
        # Цитата и URL — из корпуса, не подменены LLM.
        assert w.citation
        assert w.public_domain_url
        assert w.fragment


@pytest.mark.asyncio
async def test_build_route_falls_back_to_template_when_llm_fails() -> None:
    stub = _StubProvider(fail=True)
    # И primary, и secondary падают, fallback — сам mock,
    # но в _llm_week_description исключение ловится → шаблон.
    router = LLMRouter(primary=stub, secondary=None, fallback=stub)
    route = await build_route_async("достоевский", weeks=2, router=router)
    assert len(route.weeks) == 2
    # Описание — из шаблона, не из LLM.
    for w in route.weeks:
        assert "Жанр:" in w.description
        assert w.llm_provider is None
    # Disclaimer честно говорит «mock».
    assert "Демо-режим" in route.disclaimer or "mock" in route.disclaimer


@pytest.mark.asyncio
async def test_build_route_with_mock_router_does_not_break() -> None:
    router = LLMRouter(primary=MockProvider(), secondary=None, fallback=MockProvider())
    route = await build_route_async("серебряный век", weeks=3, router=router)
    assert route.weeks
    assert route.llm_provider == "mock"
    assert route.summary
    assert route.disclaimer


@pytest.mark.asyncio
async def test_build_route_returns_empty_for_unknown_query() -> None:
    router = LLMRouter(primary=MockProvider(), secondary=None, fallback=MockProvider())
    route = await build_route_async("xyzqwerty_не_литература", weeks=2, router=router)
    assert route.weeks == []
    assert route.sources == []
    assert "нет источников" in route.summary


@pytest.mark.asyncio
async def test_build_route_fragments_are_not_invented() -> None:
    """LLM подменяет описание, но НЕ цитаты — это критично для RAG-питча."""
    stub = _StubProvider(text="""Здесь LLM пишет всё что угодно про Гоголя.""")
    router = LLMRouter(primary=stub, secondary=None, fallback=MockProvider())
    route = await build_route_async("гоголь", weeks=2, router=router)
    for w in route.weeks:
        # fragment пришёл из corpus, а не из stub.text.
        assert "LLM пишет всё что угодно" not in w.fragment
        # citation тоже из corpus.
        assert w.citation
