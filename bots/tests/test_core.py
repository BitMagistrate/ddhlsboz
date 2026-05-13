"""Юнит-тесты для мульти-канального ядра ботов."""

from __future__ import annotations

import json

import pytest

from bots.core import (
    BUTTON_TEMPLATES,
    Button,
    ChitaiClient,
    Incoming,
    MemoryChannel,
    Router,
    build_default_router,
    intent_for_text,
)


def test_intent_menu():
    assert intent_for_text("/start") == "menu"
    assert intent_for_text("меню") == "menu"


def test_intent_about():
    assert intent_for_text("/about") == "about"
    assert intent_for_text("о проекте") == "about"


def test_intent_curator():
    assert intent_for_text("Хочу понять Пушкина за 4 недели?") == "curator"
    assert intent_for_text("Маршрут по Серебряному веку для 11 класса") == "curator"


def test_intent_specific_modes():
    assert intent_for_text("ЕГЭ план") == "exam_plan"
    assert intent_for_text("100 книг") == "challenge"
    assert intent_for_text("Прочти за 5 минут") == "quickread"
    assert intent_for_text("Пушкинская карта") == "pushkin"
    # Длинный запрос про Пушкина с вопросом → curator (не «пушкинская карта»)
    assert intent_for_text("Понять Пушкина за 4 недели?") == "curator"


def test_intent_none_for_short_unknown():
    assert intent_for_text("привет") is None


@pytest.mark.asyncio
async def test_memory_channel_records_all_kinds():
    ch = MemoryChannel()
    await ch.send_text("u1", "hello")
    await ch.send_buttons("u1", "menu", (Button(label="a", callback="x"),))
    await ch.send_image("u1", "https://example.com/i.png", caption="cap")
    assert len(ch.outbox) == 3
    assert ch.outbox[0]["kind"] == "text"
    assert ch.outbox[1]["kind"] == "buttons"
    assert ch.outbox[2]["kind"] == "image"


@pytest.mark.asyncio
async def test_router_dispatches_to_handler():
    ch = MemoryChannel()
    client = ChitaiClient(base_url="http://unused")
    router = Router()
    called: list[str] = []

    @router.on("menu")
    async def menu(incoming, channel, client):
        called.append(incoming.user_id)
        await channel.send_text(incoming.user_id, "menu shown")

    await router.dispatch(Incoming(user_id="u1", text="/menu"), ch, client)
    assert called == ["u1"]
    assert ch.outbox[0]["text"] == "menu shown"


@pytest.mark.asyncio
async def test_router_fallback_when_no_intent():
    ch = MemoryChannel()
    client = ChitaiClient(base_url="http://unused")
    router = Router()
    called: list[str] = []

    @router.fallback
    async def fb(incoming, channel, client):
        called.append("fallback")

    await router.dispatch(Incoming(user_id="u1", text="бла-бла"), ch, client)
    assert called == ["fallback"]


@pytest.mark.asyncio
async def test_button_templates_have_main_menu():
    buttons = BUTTON_TEMPLATES["main_menu"]
    assert any(b.callback == "curator" for b in buttons)
    assert any(b.callback == "ask_character" for b in buttons)
    assert any(b.callback == "challenge" for b in buttons)


@pytest.mark.asyncio
async def test_default_router_menu_handler_renders_buttons():
    ch = MemoryChannel()
    client = ChitaiClient(base_url="http://unused")
    router = build_default_router()
    await router.dispatch(Incoming(user_id="u1", text="/start"), ch, client)
    assert ch.outbox
    assert ch.outbox[-1]["kind"] == "buttons"
    callbacks = {b["callback"] for b in ch.outbox[-1]["buttons"]}
    assert "curator" in callbacks


@pytest.mark.asyncio
async def test_vk_event_parser_extracts_intent():
    """Внутренний хелпер: VK-событие → Incoming с распарсенным intent."""
    from bots.adapters.vk import _intent_from_vk_event

    ev = {
        "type": "message_new",
        "object": {
            "message": {
                "from_id": 12345,
                "text": "",
                "payload": json.dumps({"intent": "curator"}),
            }
        },
    }
    inc = _intent_from_vk_event(ev)
    assert inc is not None
    assert inc.user_id == "12345"
    assert inc.intent == "curator"


@pytest.mark.asyncio
async def test_vk_event_parser_ignores_unknown_type():
    from bots.adapters.vk import _intent_from_vk_event

    assert _intent_from_vk_event({"type": "group_leave"}) is None


def test_vk_channel_not_configured_without_token(monkeypatch):
    monkeypatch.delenv("VK_GROUP_TOKEN", raising=False)
    monkeypatch.delenv("VK_GROUP_ID", raising=False)
    from bots.adapters.vk import VKChannel

    assert VKChannel().configured is False


def test_max_channel_not_configured_without_token(monkeypatch):
    monkeypatch.delenv("MAX_BOT_TOKEN", raising=False)
    from bots.adapters.max import MaxChannel

    assert MaxChannel().configured is False
