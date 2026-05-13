"""
ratelimit.py — лёгкий in-process rate-limit + idempotency для дорогих
LLM-эндпоинтов (`/api/curator/route`, `/api/curator/mindmap`,
`/api/curator/explain`, character/quickread).

Зачем это нужно
---------------
Каждый вызов LLM — это деньги (GigaChat ≈ 1 ₽/запрос). Без лимита
один недобросовестный пользователь может за минуту сжечь несколько
тысяч рублей квоты, плюс уронить ответственное время отклика для
остальных.

Реализация
----------
- Token bucket по ключу (user_id из тела / `X-Forwarded-For` / IP).
- Лимиты конфигурируются через env (`CHITAI_RATE_LIMIT_PER_MIN`,
  `CHITAI_RATE_LIMIT_BURST`).
- Idempotency cache: повторный POST с тем же `Idempotency-Key`
  и тем же телом отдаёт прежний ответ. TTL по умолчанию 5 минут.
- Сторадж — in-memory словарь под `asyncio.Lock`. Этого хватает
  на single-node Yandex Cloud деплой; на кластер — заменить
  на Redis-бэкенд (drop-in замена интерфейса `LimiterBackend`).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

DEFAULT_RPM = 30
DEFAULT_BURST = 6
DEFAULT_IDEMPOTENCY_TTL = 5 * 60


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return max(1, int(raw))
    except ValueError:
        return default


@dataclass
class _Bucket:
    """Token bucket: `tokens` пополняется со скоростью `rate` в минуту."""

    capacity: float
    rate_per_sec: float
    tokens: float
    last_refill: float

    def consume(self, cost: float = 1.0, now: float | None = None) -> bool:
        now = now if now is not None else time.monotonic()
        delta = max(0.0, now - self.last_refill)
        self.tokens = min(self.capacity, self.tokens + delta * self.rate_per_sec)
        self.last_refill = now
        if self.tokens >= cost:
            self.tokens -= cost
            return True
        return False


@dataclass
class _IdempotencyEntry:
    body_hash: str
    payload: object
    status: int
    created: float


@dataclass
class RateLimiter:
    """In-memory rate-limit + idempotency cache."""

    rpm: int = field(default_factory=lambda: _env_int("CHITAI_RATE_LIMIT_PER_MIN", DEFAULT_RPM))
    burst: int = field(default_factory=lambda: _env_int("CHITAI_RATE_LIMIT_BURST", DEFAULT_BURST))
    idempotency_ttl: int = field(
        default_factory=lambda: _env_int("CHITAI_IDEMPOTENCY_TTL_SECONDS", DEFAULT_IDEMPOTENCY_TTL)
    )
    _buckets: dict[str, _Bucket] = field(default_factory=dict)
    _idempotency: dict[str, _IdempotencyEntry] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    @property
    def rate_per_sec(self) -> float:
        return self.rpm / 60.0

    async def check(self, key: str, cost: float = 1.0) -> bool:
        """Возвращает True, если запрос пропускается; False — если throttled."""
        async with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = _Bucket(
                    capacity=float(self.burst),
                    rate_per_sec=self.rate_per_sec,
                    tokens=float(self.burst),
                    last_refill=time.monotonic(),
                )
                self._buckets[key] = bucket
            return bucket.consume(cost)

    @staticmethod
    def hash_body(body: object) -> str:
        canonical = json.dumps(body, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    async def get_cached(
        self, idempotency_key: str, body: object
    ) -> _IdempotencyEntry | None:
        if not idempotency_key:
            return None
        async with self._lock:
            entry = self._idempotency.get(idempotency_key)
            if entry is None:
                return None
            if time.time() - entry.created > self.idempotency_ttl:
                self._idempotency.pop(idempotency_key, None)
                return None
            if entry.body_hash != self.hash_body(body):
                return None
            return entry

    async def store(
        self,
        idempotency_key: str,
        body: object,
        payload: object,
        status: int = 200,
    ) -> None:
        if not idempotency_key:
            return
        async with self._lock:
            self._idempotency[idempotency_key] = _IdempotencyEntry(
                body_hash=self.hash_body(body),
                payload=payload,
                status=status,
                created=time.time(),
            )

    def reset(self) -> None:
        """Полный сброс — для тестов."""
        self._buckets.clear()
        self._idempotency.clear()


_LIMITER: RateLimiter | None = None


def get_limiter() -> RateLimiter:
    """Singleton. Лениво создаётся при первом вызове."""
    global _LIMITER
    if _LIMITER is None:
        _LIMITER = RateLimiter()
    return _LIMITER


def reset_limiter() -> None:
    """Полный сброс. Только для тестов — пересоздаёт инстанс из env."""
    global _LIMITER
    _LIMITER = None


def extract_client_key(request, body: object) -> str:
    """
    Ключ для bucket-а. Приоритет:
    1. `user_id` из тела запроса (для авторизованных).
    2. `X-Real-IP` / `X-Forwarded-For` (если бэкенд за обратным прокси).
    3. `request.client.host`.
    """
    if isinstance(body, dict):
        user_id = body.get("user_id")
        if isinstance(user_id, str) and user_id.strip():
            return f"user:{user_id.strip()[:64]}"
    headers = getattr(request, "headers", None)
    if headers is not None:
        for h in ("x-real-ip", "x-forwarded-for"):
            val = headers.get(h)
            if val:
                return f"ip:{val.split(',')[0].strip()[:64]}"
    client = getattr(request, "client", None)
    host = getattr(client, "host", None) if client is not None else None
    return f"ip:{host or 'unknown'}"


async def enforce(
    request,
    body: object,
    handler: Callable[[], Awaitable[dict]],
    *,
    cost: float = 1.0,
) -> dict:
    """
    Высокоуровневая обёртка: rate-limit + idempotency + вызов handler.

    Использование (FastAPI handler)::

        return await enforce(
            request,
            req.model_dump(),
            lambda: actual_handler(req),
        )
    """
    from fastapi import HTTPException  # локальный импорт — модуль агностичен

    limiter = get_limiter()
    idem_key = ""
    if hasattr(request, "headers"):
        idem_key = (request.headers.get("idempotency-key") or "").strip()

    if idem_key:
        cached = await limiter.get_cached(idem_key, body)
        if cached is not None:
            if isinstance(cached.payload, dict):
                return {**cached.payload, "_idempotency_replay": True}
            return {"value": cached.payload, "_idempotency_replay": True}

    key = extract_client_key(request, body)
    allowed = await limiter.check(key, cost=cost)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limited",
                "message": (
                    "Слишком много запросов. Попробуйте через минуту "
                    "или используйте свой `user_id` для индивидуального лимита."
                ),
                "limit_per_minute": limiter.rpm,
                "burst": limiter.burst,
            },
        )

    result = await handler()
    if idem_key:
        await limiter.store(idem_key, body, result)
    return result
