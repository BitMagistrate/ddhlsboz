"""Детерминированный mock-провайдер для CI и оффлайн-демо."""

from __future__ import annotations

from .base import LLMMessage, LLMProvider, LLMResponse


class MockProvider(LLMProvider):
    """Возвращает короткий шаблонный ответ. Не делает сетевых вызовов."""

    name = "mock"
    model = "chitai-mock-v1"

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
        last_user = next(
            (m.content for m in reversed(messages) if m.role == "user"),
            "",
        )
        # Короткое детерминированное «псевдо-резюме» — без галлюцинаций.
        snippet = last_user.strip().splitlines()[0][:120] if last_user else ""
        text = (
            f"[demo] Маршрут собран по запросу: «{snippet}». "
            f"В демо-режиме мы используем фиксированные шаблоны и корпус public domain. "
            f"В продуктовой версии ответ генерирует YandexGPT 5 Pro или GigaChat MAX."
        )
        return LLMResponse(
            text=text,
            provider=self.name,
            model=self.model,
            prompt_tokens=sum(len(m.content) for m in messages) // 4,
            completion_tokens=len(text) // 4,
            total_tokens=(sum(len(m.content) for m in messages) + len(text)) // 4,
            raw={"mock": True},
        )
