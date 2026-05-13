"""
bots/core.py — мульти-канальное ядро ЧитАИ (Telegram / MAX / VK / Web).

Зачем
-----
Прямая зависимость от `aiogram` (Telegram) есть только в `bot/` —
там она и останется. Этот модуль абстрагирует «канал», чтобы
один и тот же бизнес-сценарий (маршрут чтения, тренажёр, Пушкин)
запускался поверх Telegram, MAX, VK Сообщества и веб-чата.

Дизайн
------
- `Channel` — абстрактный класс с тремя методами: `send_text`,
  `send_buttons`, `send_image`. Каждый канал реализует это
  сам через свой SDK / HTTP API.
- `Incoming` — нормализованное входящее сообщение.
- `Router.dispatch(incoming, channel)` — раскладывает по intent-ам.
- `ChitaiClient` — единственная точка обращения к backend-у. Её
  используют все каналы; это упрощает идемпотентность и
  rate-limit (передаём `Idempotency-Key` через заголовок).

Тестируемость
-------------
Реальные SDK подключаются адаптерами в `bots/adapters/*`. Здесь
только in-memory `MemoryChannel` для юнит-тестов.
"""

from __future__ import annotations

import asyncio
import dataclasses
import enum
import os
from collections.abc import Awaitable, Callable
from typing import Any

import httpx


class ChannelKind(str, enum.Enum):
    TELEGRAM = "telegram"
    MAX = "max"
    VK = "vk"
    WEB = "web"
    ALICE = "alice"
    MEMORY = "memory"  # для тестов


@dataclasses.dataclass(frozen=True)
class Button:
    label: str
    callback: str  # intent или payload


@dataclasses.dataclass(frozen=True)
class Incoming:
    """Нормализованное входящее сообщение от канала."""

    user_id: str
    text: str
    intent: str | None = None
    payload: dict[str, Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True)
class Outgoing:
    """Стандартный ответ от хэндлера."""

    text: str
    buttons: tuple[Button, ...] = ()
    image_url: str | None = None
    citations: tuple[str, ...] = ()


class Channel:
    """Абстракция канала. Конкретные адаптеры (Telegram/MAX/VK) переопределяют."""

    kind: ChannelKind = ChannelKind.MEMORY

    async def send_text(self, user_id: str, text: str) -> None:
        raise NotImplementedError

    async def send_buttons(
        self, user_id: str, text: str, buttons: tuple[Button, ...]
    ) -> None:
        raise NotImplementedError

    async def send_image(self, user_id: str, url: str, caption: str = "") -> None:
        raise NotImplementedError


class MemoryChannel(Channel):
    """In-memory канал для юнит-тестов и моков."""

    kind = ChannelKind.MEMORY

    def __init__(self) -> None:
        self.outbox: list[dict[str, Any]] = []

    async def send_text(self, user_id: str, text: str) -> None:
        self.outbox.append({"kind": "text", "user_id": user_id, "text": text})

    async def send_buttons(
        self, user_id: str, text: str, buttons: tuple[Button, ...]
    ) -> None:
        self.outbox.append(
            {
                "kind": "buttons",
                "user_id": user_id,
                "text": text,
                "buttons": [dataclasses.asdict(b) for b in buttons],
            }
        )

    async def send_image(self, user_id: str, url: str, caption: str = "") -> None:
        self.outbox.append(
            {"kind": "image", "user_id": user_id, "url": url, "caption": caption}
        )


BUTTON_TEMPLATES: dict[str, tuple[Button, ...]] = {
    "main_menu": (
        Button(label="Маршрут чтения", callback="curator"),
        Button(label="Спросить Раскольникова", callback="ask_character"),
        Button(label="ЕГЭ-план", callback="exam_plan"),
        Button(label="100 книг", callback="challenge"),
        Button(label="5 минут на книгу", callback="quickread"),
        Button(label="Угадай по цитате", callback="quote_game"),
        Button(label="Календарь литературы", callback="calendar"),
        Button(label="О проекте", callback="about"),
    ),
}


def intent_for_text(text: str) -> str | None:
    """Очень простая классификация по ключевым словам.

    Это намеренно упрощено — настоящие интенты в проде поднимаются
    через embeddings (`/api/curator/route` уже принимает свободный текст).
    Порядок проверок имеет значение: «curator»-фразы (длинный запрос
    или знак вопроса в конце) выигрывают у «пушкин» как названия,
    чтобы запрос «Понять Пушкина за 4 недели?» уходил в curator,
    а не в Пушкинскую карту.
    """
    norm = text.strip().lower()
    if norm in {"/start", "/menu", "меню", "начать", "старт"}:
        return "menu"
    if norm in {"/about", "о проекте", "проект"}:
        return "about"
    if "100 книг" in norm or "челлендж" in norm:
        return "challenge"
    if "5 минут" in norm or "за 5 мин" in norm or "коротко" in norm:
        return "quickread"
    if "егэ" in norm or "экзамен" in norm:
        return "exam_plan"
    if norm.startswith("/route") or norm.endswith("?") or len(norm.split()) > 3:
        return "curator"
    if "пушкинская карта" in norm or ("пушкин" in norm and "карта" in norm):
        return "pushkin"
    return None


Handler = Callable[[Incoming, Channel, "ChitaiClient"], Awaitable[None]]


class Router:
    """Простой in-memory dispatcher по intent → handler."""

    def __init__(self) -> None:
        self._handlers: dict[str, Handler] = {}
        self._fallback: Handler | None = None

    def on(self, intent: str) -> Callable[[Handler], Handler]:
        def deco(fn: Handler) -> Handler:
            self._handlers[intent] = fn
            return fn

        return deco

    def fallback(self, fn: Handler) -> Handler:
        self._fallback = fn
        return fn

    async def dispatch(
        self, incoming: Incoming, channel: Channel, client: ChitaiClient
    ) -> None:
        intent = incoming.intent or intent_for_text(incoming.text)
        handler = self._handlers.get(intent or "")
        if handler is None:
            if self._fallback is not None:
                await self._fallback(incoming, channel, client)
            return
        await handler(incoming, channel, client)


class ChitaiClient:
    """Тонкая обёртка над backend-эндпоинтами. Используется всеми каналами."""

    def __init__(self, base_url: str | None = None, timeout: float = 20.0) -> None:
        self.base_url = (base_url or os.environ.get("API_BASE", "http://127.0.0.1:8000")).rstrip("/")
        self.timeout = timeout

    async def _post(self, path: str, json: dict, idempotency_key: str | None = None) -> dict:
        headers = {}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(self.base_url + path, json=json, headers=headers)
            r.raise_for_status()
            return r.json()

    async def _get(self, path: str, params: dict | None = None) -> dict:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.get(self.base_url + path, params=params)
            r.raise_for_status()
            return r.json()

    async def curator_route(self, query: str, weeks: int = 4, idempotency_key: str | None = None) -> dict:
        return await self._post(
            "/api/curator/route",
            {"query": query, "weeks": weeks},
            idempotency_key=idempotency_key,
        )

    async def ask_character(self, slug: str, question: str) -> dict:
        return await self._post(
            "/api/characters/ask",
            {"character": slug, "question": question},
        )

    async def quickread(self, book_id: str) -> dict:
        return await self._get(f"/api/quickread/{book_id}")

    async def exam_plan(self, user_id: str, exam_date: str, level: int = 5) -> dict:
        return await self._post(
            "/api/exam/plan",
            {"user_id": user_id, "exam_date": exam_date, "level": level},
        )

    async def challenge_progress(self, user_id: str) -> dict:
        return await self._get("/api/challenge/progress", {"user_id": user_id})

    async def calendar_today(self) -> dict:
        return await self._get("/api/calendar/today")

    async def info(self) -> dict:
        return await self._get("/api/info")


# ── Демонстрационный набор хэндлеров (общий для всех каналов) ────────────────


def build_default_router() -> Router:
    """Создаёт Router, который реализует стандартные хэндлеры
    («меню», «о проекте», «маршрут», «спросить Раскольникова»,
    «ЕГЭ-план», «100 книг», «5 минут на книгу», «календарь»).
    """
    router = Router()

    async def menu(incoming: Incoming, channel: Channel, client: ChitaiClient) -> None:
        await channel.send_buttons(
            incoming.user_id,
            "ЧитАИ — выберите режим. Все ответы основаны на public-domain корпусе.",
            BUTTON_TEMPLATES["main_menu"],
        )

    async def about(incoming: Incoming, channel: Channel, client: ChitaiClient) -> None:
        info = await client.info()
        await channel.send_text(
            incoming.user_id,
            f"{info['name']} — {info['tagline']}\n\n"
            f"Стек: {', '.join(info['stack'])}\n"
            f"Соответствие: {', '.join(info['compliance'])}\n\n"
            f"{info['disclaimer']}",
        )

    async def curator(incoming: Incoming, channel: Channel, client: ChitaiClient) -> None:
        route = await client.curator_route(
            incoming.text, weeks=4, idempotency_key=f"{incoming.user_id}:{hash(incoming.text)}"
        )
        weeks = route.get("weeks", [])
        if not weeks:
            await channel.send_text(
                incoming.user_id,
                "К сожалению, для этого запроса я не построил маршрут. "
                + (route.get("summary") or ""),
            )
            return
        text = f"Маршрут на {len(weeks)} недели:\n\n" + "\n\n".join(
            f"{w['week']}. {w['title']}\n{w['description']}\nЦитата: {w['fragment']}\n"
            f"Источник: {w['citation']}"
            for w in weeks
        )
        await channel.send_text(incoming.user_id, text)

    async def ask_character(
        incoming: Incoming, channel: Channel, client: ChitaiClient
    ) -> None:
        # формат текста: «raskolnikov: почему ты убил?»
        if ":" in incoming.text:
            slug, _, question = incoming.text.partition(":")
        else:
            slug, question = "raskolnikov", incoming.text
        ans = await client.ask_character(slug.strip(), question.strip())
        cites = "\n".join(
            f"• {c.get('citation') or c.get('fragment')}" for c in ans.get("citations", [])
        )
        text = ans["answer"] + ("\n\nИсточники:\n" + cites if cites else "")
        await channel.send_text(incoming.user_id, text)

    async def quickread(incoming: Incoming, channel: Channel, client: ChitaiClient) -> None:
        book_id = incoming.payload.get("book_id") or "pushkin_onegin"
        qr = await client.quickread(book_id)
        await channel.send_text(
            incoming.user_id,
            f"{qr['title']} — {qr['author']}\n\n{qr['plot']}\n\n"
            f"Цитата: «{qr['citations'][0]['fragment']}»\n\n"
            f"Вопрос для друга: {qr['talking_points'][0]}",
        )

    async def fallback(incoming: Incoming, channel: Channel, client: ChitaiClient) -> None:
        await menu(incoming, channel, client)

    router.on("menu")(menu)
    router.on("about")(about)
    router.on("curator")(curator)
    router.on("ask_character")(ask_character)
    router.on("quickread")(quickread)
    router.fallback(fallback)
    return router


async def run_demo(channel: Channel, client: ChitaiClient, text: str, user_id: str = "demo") -> None:
    """Удобный entry-point для отладки / e2e: прокидывает один текст в роутер."""
    router = build_default_router()
    await router.dispatch(Incoming(user_id=user_id, text=text), channel, client)


__all__ = [
    "BUTTON_TEMPLATES",
    "Button",
    "Channel",
    "ChannelKind",
    "ChitaiClient",
    "Incoming",
    "MemoryChannel",
    "Outgoing",
    "Router",
    "build_default_router",
    "intent_for_text",
    "run_demo",
]


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(run_demo(MemoryChannel(), ChitaiClient(), "/menu"))
