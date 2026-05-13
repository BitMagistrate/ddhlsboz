"""
ЧитАИ — Telegram-бот (демо-стенд, aiogram 3.x).

Запуск:
    pip install aiogram httpx
    export BOT_TOKEN=...
    export API_BASE=https://chitai-api.fly.dev   # или http://127.0.0.1:8000
    python bot.py

Бот ходит в backend по тем же эндпоинтам, что и веб-фронтенд.
В демо ответы детерминированы и опираются на корпус public domain.
В продакшене эндпоинт /api/curator/route проксирует YandexGPT 5 / GigaChat MAX
поверх pgvector-индекса фондов РГБ/НЭБ.
"""

from __future__ import annotations

import asyncio
import logging
import os

import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("chitai-bot")

API_BASE = os.environ.get("API_BASE", "http://127.0.0.1:8000")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "PLACEHOLDER_TOKEN")

WELCOME = (
    "Здравствуйте. Это ЧитАИ — ИИ-куратор русского культурного и образовательного "
    "контента.\n\n"
    "Я подбираю маршруты чтения по фондам РГБ и НЭБ, помогаю готовиться к ЕГЭ "
    "по литературе и истории, рекомендую события по Пушкинской карте.\n\n"
    "Все цитаты сопровождаются источниками. Демо-режим: используется корпус "
    "общественного достояния."
)

EXAMPLES = [
    "Хочу понять Пушкина за 4 недели",
    "Маршрут по Серебряному веку для 11 класса",
    "Подготовка к ЕГЭ по Достоевскому",
    "История России XIX века для подростка",
]


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Куратор: маршрут чтения", callback_data="curator")],
            [InlineKeyboardButton(text="Тренажёр ЕГЭ", callback_data="trainer")],
            [InlineKeyboardButton(text="Пушкинская карта", callback_data="pushkin")],
            [InlineKeyboardButton(text="О проекте", callback_data="about")],
        ]
    )


async def fetch_route(query: str) -> dict:
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(
            f"{API_BASE}/api/curator/route",
            json={"query": query, "weeks": 4},
        )
        r.raise_for_status()
        return r.json()


async def fetch_quiz(subject: str = "Литература") -> dict:
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(
            f"{API_BASE}/api/trainer/quiz",
            params={"subject": subject, "limit": 3},
        )
        r.raise_for_status()
        return r.json()


async def fetch_info() -> dict:
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(f"{API_BASE}/api/info")
        r.raise_for_status()
        return r.json()


def format_route(route: dict) -> str:
    lines = [f"*Маршрут на 4 недели*\n_{route.get('summary', '')}_\n"]
    for w in route.get("weeks", []):
        lines.append(f"*{w['title']}*")
        lines.append(w["description"])
        lines.append(f"_Цитата:_ {w['fragment']}")
        lines.append(f"_Источник:_ {w['citation']}")
        if w.get("public_domain_url"):
            lines.append(f"Текст: {w['public_domain_url']}")
        if w.get("pushkin_card_event"):
            lines.append(f"_Пушкинская карта:_ {w['pushkin_card_event']}")
        lines.append("")
    lines.append(route.get("disclaimer", ""))
    return "\n".join(lines)


dp = Dispatcher()


@dp.message(CommandStart())
async def on_start(msg: Message) -> None:
    await msg.answer(WELCOME, reply_markup=main_menu())


@dp.message(Command("about"))
async def on_about(msg: Message) -> None:
    info = await fetch_info()
    text = (
        f"*{info['name']}* — {info['tagline']}\n\n"
        f"Стек: {', '.join(info['stack'])}\n"
        f"Аудитории: {', '.join(info['audiences'])}\n"
        f"Соответствие: {', '.join(info['compliance'])}\n\n"
        f"{info['disclaimer']}"
    )
    await msg.answer(text, parse_mode="Markdown")


@dp.callback_query(F.data == "curator")
async def cb_curator(cq: CallbackQuery) -> None:
    text = "Введите запрос или выберите пример:\n\n" + "\n".join(
        f"• {q}" for q in EXAMPLES
    )
    await cq.message.answer(text)
    await cq.answer()


@dp.callback_query(F.data == "trainer")
async def cb_trainer(cq: CallbackQuery) -> None:
    quiz = await fetch_quiz("Литература")
    items = quiz.get("items", [])
    if not items:
        await cq.message.answer("Тренажёр временно недоступен.")
        return
    q = items[0]
    options = "\n".join(f"{i + 1}. {opt}" for i, opt in enumerate(q["options"]))
    await cq.message.answer(
        f"*Вопрос (Литература)*\n\n{q['question']}\n\n{options}\n\n"
        f"Ответьте номером (1–{len(q['options'])}). "
        f"id вопроса: `{q['id']}`",
        parse_mode="Markdown",
    )
    await cq.answer()


@dp.callback_query(F.data == "pushkin")
async def cb_pushkin(cq: CallbackQuery) -> None:
    await cq.message.answer(
        "Пушкинская карта (демо).\n\n"
        "В рабочей версии бот подбирает события партнёров (РГБ, музеи, театры) "
        "по интересам пользователя и его маршруту чтения. Источник событий — "
        "официальный каталог Пушкинской карты."
    )
    await cq.answer()


@dp.callback_query(F.data == "about")
async def cb_about(cq: CallbackQuery) -> None:
    await on_about(cq.message)
    await cq.answer()


@dp.message(F.text)
async def on_text(msg: Message) -> None:
    if not msg.text:
        return
    text = msg.text.strip()
    if text.isdigit() or len(text) < 3:
        await msg.answer(
            "Чтобы получить маршрут, опишите интерес одной фразой. "
            "Например: «Хочу понять Пушкина за 4 недели»."
        )
        return
    try:
        route = await fetch_route(text)
    except httpx.HTTPError as exc:
        log.exception("route fetch failed")
        await msg.answer(f"Сервис недоступен: {exc}")
        return
    await msg.answer(format_route(route), parse_mode="Markdown", disable_web_page_preview=True)


async def main() -> None:
    if BOT_TOKEN == "PLACEHOLDER_TOKEN":
        log.warning(
            "BOT_TOKEN не задан. Это демо-заглушка: бот не запустится без реального токена. "
            "Для запуска: export BOT_TOKEN=... && python bot.py"
        )
        return
    bot = Bot(BOT_TOKEN)
    log.info("ЧитАИ-бот запущен. API: %s", API_BASE)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
