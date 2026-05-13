"""Тесты для ЧитАИ-бота: форматирование, меню, HTTP-обёртки."""

from __future__ import annotations

import sys
from pathlib import Path

import httpx
import pytest
import respx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bot


@pytest.fixture(autouse=True)
def _reset_api_base(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bot, "API_BASE", "http://api.test")


def test_main_menu_has_four_buttons() -> None:
    menu = bot.main_menu()
    assert len(menu.inline_keyboard) == 4
    captions = [row[0].text for row in menu.inline_keyboard]
    assert "Куратор: маршрут чтения" in captions
    assert "Тренажёр ЕГЭ" in captions
    assert "Пушкинская карта" in captions
    assert "О проекте" in captions


def test_format_route_renders_summary_and_weeks() -> None:
    route = {
        "summary": "4 недели по Пушкину",
        "weeks": [
            {
                "title": "Неделя 1",
                "description": "Капитанская дочка",
                "fragment": "Береги честь смолоду",
                "citation": "Пушкин А.С.",
                "public_domain_url": "https://example.org/k.txt",
                "pushkin_card_event": "Музей Пушкина",
            }
        ],
        "disclaimer": "Демо-режим.",
    }
    text = bot.format_route(route)
    assert "*Маршрут на 4 недели*" in text
    assert "_4 недели по Пушкину_" in text
    assert "*Неделя 1*" in text
    assert "Береги честь смолоду" in text
    assert "Пушкин А.С." in text
    assert "https://example.org/k.txt" in text
    assert "Музей Пушкина" in text
    assert "Демо-режим." in text


def test_format_route_handles_missing_optional_fields() -> None:
    route = {
        "summary": "Краткий маршрут",
        "weeks": [
            {
                "title": "Неделя 1",
                "description": "Описание",
                "fragment": "Цитата",
                "citation": "Источник",
            }
        ],
    }
    text = bot.format_route(route)
    assert "Неделя 1" in text
    assert "Текст:" not in text
    assert "Пушкинская карта:" not in text


def test_welcome_text_contains_compliance_disclaimer() -> None:
    assert "152" not in bot.WELCOME or "общественного достояния" in bot.WELCOME
    assert "ЧитАИ" in bot.WELCOME
    assert "Пушкинской карте" in bot.WELCOME


def test_examples_are_unique_and_non_empty() -> None:
    assert len(bot.EXAMPLES) >= 4
    assert len(set(bot.EXAMPLES)) == len(bot.EXAMPLES)
    assert all(isinstance(q, str) and len(q) > 5 for q in bot.EXAMPLES)


@pytest.mark.asyncio
async def test_fetch_route_posts_to_curator_endpoint() -> None:
    with respx.mock(assert_all_called=True) as router:
        route_mock = router.post("http://api.test/api/curator/route").respond(
            200,
            json={"query": "x", "summary": "ok", "weeks": [], "sources": [], "disclaimer": ""},
        )
        result = await bot.fetch_route("Хочу понять Пушкина за 4 недели")
        assert route_mock.called
        request = route_mock.calls.last.request
        body = request.read().decode("utf-8")
        assert "Хочу понять Пушкина за 4 недели" in body
        assert "weeks" in body
        assert result["summary"] == "ok"


@pytest.mark.asyncio
async def test_fetch_quiz_uses_default_subject_and_limit() -> None:
    with respx.mock(assert_all_called=True) as router:
        quiz_mock = router.get("http://api.test/api/trainer/quiz").respond(
            200, json={"items": []}
        )
        await bot.fetch_quiz()
        called_url = str(quiz_mock.calls.last.request.url)
        assert "subject=%D0%9B%D0%B8%D1%82%D0%B5%D1%80%D0%B0%D1%82%D1%83%D1%80%D0%B0" in called_url
        assert "limit=3" in called_url


@pytest.mark.asyncio
async def test_fetch_info_returns_json_body() -> None:
    with respx.mock(assert_all_called=True) as router:
        router.get("http://api.test/api/info").respond(
            200,
            json={
                "name": "ЧитАИ",
                "tagline": "ИИ-куратор",
                "stack": ["YandexGPT 5 Pro"],
                "audiences": ["Молодёжь 14–22"],
                "compliance": ["152-ФЗ"],
                "disclaimer": "Демо.",
            },
        )
        info = await bot.fetch_info()
        assert info["name"] == "ЧитАИ"
        assert "152-ФЗ" in info["compliance"]


@pytest.mark.asyncio
async def test_fetch_route_raises_on_http_error() -> None:
    with respx.mock(assert_all_called=True) as router:
        router.post("http://api.test/api/curator/route").respond(500)
        with pytest.raises(httpx.HTTPStatusError):
            await bot.fetch_route("любой запрос")
