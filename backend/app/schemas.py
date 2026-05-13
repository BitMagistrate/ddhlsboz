"""Контрактные JSON-схемы ответов ЧитАИ.

Через Pydantic v2 фиксируем форму ответов критичных эндпоинтов: фронт и бот
полагаются на стабильную схему, и любой дрейф формы (отсутствие поля,
лишний None, неверный тип) ловится ещё до отправки клиенту. Это критерий A1
из master TODO («контракт ответа /api/curator/route — JSON Schema»).

Лишние поля (`safety` и пр.) разрешены явно, чтобы можно было постепенно
расширять ответ без поломки контракта.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CuratorRouteWeek(BaseModel):
    model_config = ConfigDict(extra="allow")

    week: int = Field(..., ge=1, le=12)
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, max_length=2000)
    book: str = Field(..., min_length=1, max_length=300)
    book_id: str = Field(..., min_length=1, max_length=100)
    fragment: str = Field(..., min_length=1, max_length=4000)
    citation: str = Field(..., min_length=1, max_length=300)
    public_domain_url: str = Field(..., min_length=1, max_length=500)
    actions: list[str] = Field(default_factory=list, max_length=12)
    pushkin_card_event: str | None = None
    llm_provider: str | None = None


class CuratorSource(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    title: str
    author: str
    year: int | None = None
    genre: str | None = None
    school_grade: int | str | None = None
    ege_topics: list[str] = Field(default_factory=list)
    fragment: str
    citation: str
    public_domain_url: str
    pushkin_card: bool = False


class CuratorRouteResponse(BaseModel):
    """JSON-Schema контракт для /api/curator/route."""

    model_config = ConfigDict(extra="allow")

    query: str = Field(..., min_length=1, max_length=300)
    summary: str = Field(..., min_length=1)
    weeks: list[CuratorRouteWeek] = Field(default_factory=list, max_length=12)
    sources: list[CuratorSource] = Field(default_factory=list)
    disclaimer: str = Field(..., min_length=1)
    llm_provider: str = Field(..., min_length=1, max_length=80)
    llm_model: str = Field(..., min_length=1, max_length=120)


def validate_curator_route(payload: dict) -> dict:
    """Прогоняем dict через Pydantic-модель и возвращаем нормализованный dict.

    Pydantic v2 при ошибке поднимет ValidationError; FastAPI превратит её в
    500 — это правильное поведение, потому что значит, что мы где-то нарушили
    контракт изнутри.
    """
    return CuratorRouteResponse.model_validate(payload).model_dump(mode="json")
