"""Базовый интерфейс LLM-провайдера для ЧитАИ."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal

Role = Literal["system", "user", "assistant"]


@dataclass
class LLMMessage:
    role: Role
    content: str

    def to_yandex(self) -> dict:
        return {"role": self.role, "text": self.content}

    def to_openai(self) -> dict:
        return {"role": self.role, "content": self.content}


@dataclass
class LLMResponse:
    text: str
    provider: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    raw: dict = field(default_factory=dict)


class LLMError(Exception):
    """Любая ошибка LLM-провайдера: 4xx, 5xx, таймаут, сеть, JSON."""


class LLMProvider(ABC):
    """Минимальный контракт провайдера. async-only, идемпотентен."""

    name: str = "abstract"
    model: str = "abstract"

    @abstractmethod
    async def is_configured(self) -> bool:
        """True, если в окружении есть всё, чтобы реально позвать API."""

    @abstractmethod
    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.3,
        max_tokens: int = 400,
        timeout: float | None = None,
    ) -> LLMResponse:
        """Сгенерировать ответ. При ошибке — поднимает LLMError."""
