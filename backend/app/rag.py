"""RAG для ЧитАИ.

Конвейер:
  1. `corpus.search` — keyword-матчинг по демо-корпусу public domain.
  2. `LLMRouter` (YandexGPT 5 Pro / GigaChat MAX / mock-fallback) обогащает
     описание каждой недели и генерирует общий summary маршрута.
  3. Если LLM не сконфигурирован или упал — graceful degradation на
     детерминированный шаблон, чтобы CI и демо не ломались.

Структура ответа `Route` остаётся стабильной: список недель, источники,
disclaimer. Цитаты и ссылки берутся ТОЛЬКО из корпуса, LLM их не выдумывает —
этим лечится критерий «галлюцинации» в RAG-питче.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from .corpus import Source, search
from .llm import LLMError, LLMMessage, LLMResponse, LLMRouter, get_router

logger = logging.getLogger(__name__)


@dataclass
class RouteWeek:
    week: int
    title: str
    description: str
    book: str
    book_id: str
    fragment: str
    citation: str
    public_domain_url: str
    actions: list[str] = field(default_factory=list)
    pushkin_card_event: str | None = None
    llm_provider: str | None = None

    def to_dict(self) -> dict:
        return {
            "week": self.week,
            "title": self.title,
            "description": self.description,
            "book": self.book,
            "book_id": self.book_id,
            "fragment": self.fragment,
            "citation": self.citation,
            "public_domain_url": self.public_domain_url,
            "actions": self.actions,
            "pushkin_card_event": self.pushkin_card_event,
            "llm_provider": self.llm_provider,
        }


@dataclass
class Route:
    query: str
    summary: str
    weeks: list[RouteWeek]
    sources: list[Source]
    disclaimer: str
    llm_provider: str = "mock"
    llm_model: str = "chitai-mock-v1"

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "summary": self.summary,
            "weeks": [w.to_dict() for w in self.weeks],
            "sources": [s.to_dict() for s in self.sources],
            "disclaimer": self.disclaimer,
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
        }


PUSHKIN_EVENTS = [
    "Лекция в РГБ «Пушкин и его современники» (вход по Пушкинской карте)",
    "Спектакль «Гроза» в Малом театре (Пушкинская карта)",
    "Экскурсия в Третьяковскую галерею «Передвижники» (Пушкинская карта)",
    "Концерт в Большом зале консерватории «Серебряный век в музыке» (Пушкинская карта)",
]

BASE_TITLES = [
    "Знакомство и контекст",
    "Глубокое чтение",
    "Сопоставление и анализ",
    "Творческая работа",
    "Закрепление",
    "Итог и портфолио",
]

DEFAULT_ACTIONS = [
    "Прочитать ключевые главы и выделить цитаты",
    "Составить конспект (3–5 тезисов)",
    "Решить 5 вопросов из тренажёра по теме",
    "Записать одну заметку в читательский дневник",
]

SYSTEM_PROMPT = (
    "Ты — ИИ-куратор русской классики ЧитАИ для подростков 14–22 лет. "
    "Отвечай по-русски, кратко и по делу, без воды и пафоса. "
    "Не выдумывай факты: опирайся ТОЛЬКО на присланный фрагмент и метаданные. "
    "Не придумывай цитаты и ссылки — они уже даны и подменять их нельзя. "
    "Не используй маркетинговые штампы («раскроем тайны», «уникальный»). "
    "Если данных мало — честно скажи об этом."
)


def _template_week_description(source: Source) -> str:
    return (
        f"Читаем «{source.title}» ({source.author}, {source.year}). "
        f"Жанр: {source.genre}. Опорные темы ЕГЭ: " + ", ".join(source.ege_topics) + "."
    )


def _template_summary(query: str, count: int) -> str:
    return (
        f"Маршрут на {count} недель по запросу «{query}». "
        f"Подобраны {count} источников из демо-корпуса (public domain). "
        f"Все цитаты и ссылки приведены без подмены — демонстрация прозрачности RAG."
    )


def _disclaimer(provider: str) -> str:
    if provider == "mock":
        return (
            "Демо-режим (без живого LLM). В продуктовой версии корпус расширен "
            "до фондов РГБ и НЭБ; генерация — через YandexGPT 5 Pro и GigaChat MAX "
            "с reranker. Все цитаты — из public domain, без подмены."
        )
    return (
        f"Маршрут сгенерирован через {provider}. Цитаты и ссылки — из корпуса "
        f"public domain, без подмены. В продуктовой версии корпус расширен "
        f"до фондов РГБ и НЭБ по соглашению."
    )


async def _llm_week_description(
    router: LLMRouter, source: Source, week: int, total: int
) -> tuple[str, str | None]:
    user_prompt = (
        f"Подготовь короткое описание недели #{week} из {total} читательского "
        f"маршрута по произведению «{source.title}» ({source.author}, {source.year}). "
        f"Жанр: {source.genre}. Класс: {source.school_grade}. "
        f"Темы ЕГЭ: {', '.join(source.ege_topics) or '—'}. "
        f"Цитата из произведения (НЕ переписывай и НЕ придумывай новых): "
        f"«{source.fragment}». "
        f"Сделай 2–3 предложения для подростка: что читать на этой неделе, "
        f"на что обратить внимание, какой вопрос задать себе после чтения. "
        f"Без пафоса, без выдумок, без новых цитат."
    )
    messages = [
        LLMMessage(role="system", content=SYSTEM_PROMPT),
        LLMMessage(role="user", content=user_prompt),
    ]
    try:
        resp: LLMResponse = await router.complete(messages, temperature=0.3, max_tokens=220)
        text = resp.text.strip()
        if not text:
            return _template_week_description(source), None
        return text, resp.provider
    except LLMError as exc:
        logger.warning("llm week description failed: %s", exc)
        return _template_week_description(source), None


async def _llm_summary(
    router: LLMRouter, query: str, sources: list[Source]
) -> tuple[str, LLMResponse | None]:
    titles = "; ".join(f"«{s.title}» ({s.author})" for s in sources[:6])
    user_prompt = (
        f"Запрос пользователя: «{query}». "
        f"Подобранные источники из корпуса public domain: {titles}. "
        f"Сделай короткое резюме маршрута из 1–2 предложений для подростка 14–22 лет: "
        f"что он получит, пройдя этот путь. Без пафоса, без новых цитат, без выдумок."
    )
    messages = [
        LLMMessage(role="system", content=SYSTEM_PROMPT),
        LLMMessage(role="user", content=user_prompt),
    ]
    try:
        resp = await router.complete(messages, temperature=0.3, max_tokens=180)
        text = resp.text.strip()
        if not text:
            return _template_summary(query, len(sources)), resp
        return text, resp
    except LLMError as exc:
        logger.warning("llm summary failed: %s", exc)
        return _template_summary(query, len(sources)), None


async def build_route_async(
    query: str,
    weeks: int = 4,
    router: LLMRouter | None = None,
) -> Route:
    sources = search(query, limit=max(weeks, 5))
    if not sources:
        return Route(
            query=query,
            summary=(
                "По вашему запросу в демо-корпусе пока нет источников. "
                "В продуктовой версии маршрут строится по фондам РГБ и НЭБ."
            ),
            weeks=[],
            sources=[],
            disclaimer=_disclaimer("mock"),
            llm_provider="none",
            llm_model="-",
        )

    router = router or get_router()
    n_weeks = min(weeks, len(sources))
    selected = sources[:n_weeks]

    week_tasks = [_llm_week_description(router, s, i + 1, n_weeks) for i, s in enumerate(selected)]
    summary_task = _llm_summary(router, query, selected)
    week_results, (summary_text, summary_resp) = await asyncio.gather(
        asyncio.gather(*week_tasks), summary_task
    )

    plan: list[RouteWeek] = []
    used_provider: str | None = None
    used_model: str = "chitai-mock-v1"
    for i, (s, (description, prov)) in enumerate(zip(selected, week_results, strict=False)):
        if prov:
            used_provider = used_provider or prov
        plan.append(
            RouteWeek(
                week=i + 1,
                title=f"Неделя {i + 1}. {BASE_TITLES[i]}",
                description=description,
                book=f"{s.author}. «{s.title}»",
                book_id=s.id,
                fragment=s.fragment,
                citation=s.citation,
                public_domain_url=s.public_domain_url,
                actions=list(DEFAULT_ACTIONS),
                pushkin_card_event=(
                    PUSHKIN_EVENTS[i % len(PUSHKIN_EVENTS)] if s.pushkin_card else None
                ),
                llm_provider=prov,
            )
        )

    if summary_resp is not None:
        used_provider = used_provider or summary_resp.provider
        used_model = summary_resp.model
    final_provider = used_provider or "mock"

    return Route(
        query=query,
        summary=summary_text,
        weeks=plan,
        sources=selected,
        disclaimer=_disclaimer(final_provider),
        llm_provider=final_provider,
        llm_model=used_model,
    )


def build_route(query: str, weeks: int = 4) -> Route:
    """Синхронная обёртка для совместимости со старым кодом и CLI."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            raise RuntimeError(
                "build_route() called inside running event loop. "
                "Use build_route_async() instead."
            )
    except RuntimeError as exc:
        if "running event loop" in str(exc):
            raise
    return asyncio.run(build_route_async(query, weeks=weeks))
