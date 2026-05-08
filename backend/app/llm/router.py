"""LLM-роутер: выбирает primary, при ошибке падает в secondary, потом в mock.

Стратегия:
  1. Берём primary из ENV `LLM_PRIMARY` (yandex|gigachat). Дефолт — `yandex`.
  2. Если primary не сконфигурирован — пропускаем, идём к secondary.
  3. Если primary упал по сети/4xx/5xx — логируем и идём к secondary.
  4. Если оба упали или не сконфигурированы — возвращаем MockProvider, чтобы
     CI/демо не ломались. В лог пишем причину.

Это даёт:
  - честный live-ответ, когда ключи в порядке;
  - устойчивый CI и демо-стенд без ключей;
  - возможность развернуть без YandexGPT (пока ждём роль), используя только GigaChat.
"""

from __future__ import annotations

import logging
import os

from .base import LLMError, LLMMessage, LLMProvider, LLMResponse
from .gigachat import GigaChatProvider
from .mock import MockProvider
from .yandex import YandexGPTProvider

logger = logging.getLogger(__name__)


class LLMRouter:
    def __init__(
        self,
        primary: LLMProvider | None = None,
        secondary: LLMProvider | None = None,
        fallback: LLMProvider | None = None,
    ) -> None:
        self.primary = primary
        self.secondary = secondary
        self.fallback = fallback or MockProvider()

    @classmethod
    def from_env(cls) -> LLMRouter:
        choice = (os.getenv("LLM_PRIMARY") or "yandex").strip().lower()
        yandex = YandexGPTProvider()
        gigachat = GigaChatProvider()
        if choice == "gigachat":
            return cls(primary=gigachat, secondary=yandex)
        return cls(primary=yandex, secondary=gigachat)

    async def status(self) -> dict:
        """Сводка по конфигурации для /api/llm/status (без секретов)."""
        out: dict = {"providers": []}
        for slot, provider in (("primary", self.primary), ("secondary", self.secondary)):
            if provider is None:
                out["providers"].append({"slot": slot, "name": None, "configured": False})
                continue
            out["providers"].append(
                {
                    "slot": slot,
                    "name": provider.name,
                    "model": provider.model,
                    "configured": await provider.is_configured(),
                }
            )
        out["fallback"] = {"name": self.fallback.name, "model": self.fallback.model}
        out["primary_choice"] = (os.getenv("LLM_PRIMARY") or "yandex").strip().lower()
        return out

    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.3,
        max_tokens: int = 400,
        timeout: float | None = None,
    ) -> LLMResponse:
        attempts: list[str] = []
        for provider in (self.primary, self.secondary):
            if provider is None:
                continue
            try:
                if not await provider.is_configured():
                    attempts.append(f"{provider.name}: not_configured")
                    continue
                return await provider.complete(
                    messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=timeout,
                )
            except LLMError as exc:
                attempts.append(f"{provider.name}: {exc}")
                logger.warning("llm provider %s failed: %s", provider.name, exc)
        # Финальный fallback — mock, чтобы продакшен не падал.
        logger.warning("llm router: falling back to mock; reasons=%s", attempts)
        result = await self.fallback.complete(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        # Прозрачно сообщаем потребителю, что мы в fallback и почему.
        result.raw = {**result.raw, "fallback_reasons": attempts}
        return result


_router: LLMRouter | None = None


def get_router() -> LLMRouter:
    global _router
    if _router is None:
        _router = LLMRouter.from_env()
    return _router


def reset_router() -> None:
    """Используется в тестах для переинициализации после правки env."""
    global _router
    _router = None
