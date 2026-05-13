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

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field

from .base import LLMError, LLMMessage, LLMProvider, LLMResponse
from .gigachat import GigaChatProvider
from .mock import MockProvider
from .yandex import YandexGPTProvider

logger = logging.getLogger(__name__)

DEFAULT_FAILURE_THRESHOLD = 3
DEFAULT_COOLDOWN_SECONDS = 30.0
DEFAULT_HALF_OPEN_PROBES = 1


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return max(1, int(raw))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return max(0.0, float(raw))
    except ValueError:
        return default


@dataclass
class CircuitBreaker:
    """Простой автомат closed → open → half_open ␴ closed.

    При N подряд ошибках провайдера (`failure_threshold`) брекер
    переходит в OPEN и блокирует вызовы на `cooldown` секунд. После
    cooldown — HALF_OPEN: один пробный вызов. Если успешно — closed,
    иначе — обратно в open.

    Это важно для LLM-роутера: при падении GigaChat (например,
    истёк токен) мы не бьём его всеми запросами в пыль, а быстро
    переключаемся на secondary, а через 30 с пробуем восстановиться.
    """

    failure_threshold: int = DEFAULT_FAILURE_THRESHOLD
    cooldown_seconds: float = DEFAULT_COOLDOWN_SECONDS
    half_open_probes: int = DEFAULT_HALF_OPEN_PROBES
    _state: str = "closed"  # closed | open | half_open
    _failures: int = 0
    _opened_at: float = 0.0
    _half_open_inflight: int = 0
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    @property
    def state(self) -> str:
        return self._state

    async def allow(self) -> bool:
        """Разрешить вызов? Для open — False; для closed/half_open — True (со счётчиком)."""
        async with self._lock:
            now = time.monotonic()
            if self._state == "open":
                if now - self._opened_at >= self.cooldown_seconds:
                    # Cooldown прошёл — переходим в half_open.
                    self._state = "half_open"
                    self._half_open_inflight = 0
                else:
                    return False
            if self._state == "half_open":
                if self._half_open_inflight >= self.half_open_probes:
                    return False
                self._half_open_inflight += 1
                return True
            return True

    async def record_success(self) -> None:
        async with self._lock:
            self._failures = 0
            self._half_open_inflight = 0
            self._state = "closed"

    async def record_failure(self) -> None:
        async with self._lock:
            self._failures += 1
            if self._state == "half_open":
                # Пробный вызов не удался — обратно в open.
                self._state = "open"
                self._opened_at = time.monotonic()
                self._half_open_inflight = 0
                return
            if self._failures >= self.failure_threshold:
                self._state = "open"
                self._opened_at = time.monotonic()

    async def force_open(self) -> None:
        async with self._lock:
            self._state = "open"
            self._opened_at = time.monotonic()

    async def reset(self) -> None:
        async with self._lock:
            self._state = "closed"
            self._failures = 0
            self._opened_at = 0.0
            self._half_open_inflight = 0


class LLMRouter:
    def __init__(
        self,
        primary: LLMProvider | None = None,
        secondary: LLMProvider | None = None,
        fallback: LLMProvider | None = None,
        *,
        failure_threshold: int | None = None,
        cooldown_seconds: float | None = None,
    ) -> None:
        self.primary = primary
        self.secondary = secondary
        self.fallback = fallback or MockProvider()
        failure_threshold = failure_threshold or _env_int(
            "CHITAI_LLM_FAILURE_THRESHOLD", DEFAULT_FAILURE_THRESHOLD
        )
        cooldown_seconds = cooldown_seconds if cooldown_seconds is not None else _env_float(
            "CHITAI_LLM_COOLDOWN_SECONDS", DEFAULT_COOLDOWN_SECONDS
        )
        self.breakers: dict[str, CircuitBreaker] = {}
        for slot in ("primary", "secondary"):
            self.breakers[slot] = CircuitBreaker(
                failure_threshold=failure_threshold,
                cooldown_seconds=cooldown_seconds,
            )

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
            breaker = self.breakers[slot]
            if provider is None:
                out["providers"].append(
                    {
                        "slot": slot,
                        "name": None,
                        "configured": False,
                        "breaker": breaker.state,
                    }
                )
                continue
            out["providers"].append(
                {
                    "slot": slot,
                    "name": provider.name,
                    "model": provider.model,
                    "configured": await provider.is_configured(),
                    "breaker": breaker.state,
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
        for slot, provider in (("primary", self.primary), ("secondary", self.secondary)):
            if provider is None:
                continue
            breaker = self.breakers[slot]
            if not await breaker.allow():
                attempts.append(f"{provider.name}: breaker_open")
                continue
            try:
                if not await provider.is_configured():
                    attempts.append(f"{provider.name}: not_configured")
                    # not_configured не считается сбоем — это состояние среды.
                    continue
                result = await provider.complete(
                    messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=timeout,
                )
                await breaker.record_success()
                return result
            except LLMError as exc:
                attempts.append(f"{provider.name}: {exc}")
                await breaker.record_failure()
                logger.warning(
                    "llm provider %s failed: %s (breaker=%s)",
                    provider.name,
                    exc,
                    breaker.state,
                )
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
