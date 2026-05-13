"""Тесты экспорта Markdown / iCalendar."""

from __future__ import annotations

import datetime as _dt

from app import exports, pushkin


def _route_fixture() -> dict:
    return {
        "query": "Пушкин Онегин",
        "summary": "Маршрут на 2 недели по запросу.",
        "weeks": [
            {
                "week": 1,
                "title": "Неделя 1. Знакомство",
                "description": "Читаем «Евгения Онегина».",
                "book": "А. С. Пушкин. «Евгений Онегин»",
                "book_id": "pushkin_onegin",
                "fragment": "Мой дядя самых честных правил",
                "citation": "Пушкин А.С. ПСС т.5",
                "public_domain_url": "https://ru.wikisource.org/...",
                "actions": ["Прочитать главу 1", "Сделать конспект"],
                "pushkin_card_event": "Лекция в РГБ",
            },
            {
                "week": 2,
                "title": "Неделя 2. Анализ",
                "description": "Разбор героев.",
                "book": "А. С. Пушкин. «Евгений Онегин»",
                "book_id": "pushkin_onegin",
                "fragment": "Татьяна, русская душою",
                "citation": "Пушкин А.С. ПСС т.5",
                "public_domain_url": "https://ru.wikisource.org/...",
                "actions": [],
                "pushkin_card_event": None,
            },
        ],
        "sources": [
            {
                "id": "pushkin_onegin",
                "title": "Евгений Онегин",
                "author": "А. С. Пушкин",
                "year": 1833,
                "public_domain_url": "https://ru.wikisource.org/...",
            }
        ],
        "disclaimer": "Демо-режим (без живого LLM).",
    }


def test_markdown_renders_full_route() -> None:
    md = exports.route_to_markdown(_route_fixture())
    assert md.startswith("# Маршрут ЧитАИ — «Пушкин Онегин»")
    assert "## Недели" in md
    assert "### Неделя 1." in md
    assert "Татьяна, русская душою" in md
    assert "## Источники" in md
    assert "Демо-режим" in md


def test_markdown_no_weeks_section_if_empty() -> None:
    md = exports.route_to_markdown({"query": "?", "summary": "—", "weeks": [], "sources": []})
    assert "## Недели" not in md
    assert "## Источники" not in md


def test_ics_calendar_has_two_events_and_crlf() -> None:
    ics = exports.route_to_ics(_route_fixture(), start_date=_dt.date(2026, 9, 1))
    assert ics.startswith("BEGIN:VCALENDAR")
    assert ics.endswith("END:VCALENDAR\r\n")
    assert ics.count("BEGIN:VEVENT") == 2
    assert "DTSTART;VALUE=DATE:20260901" in ics
    # Неделя 2 — через 7 дней.
    assert "DTSTART;VALUE=DATE:20260908" in ics


def test_ics_escape_special_chars() -> None:
    route = _route_fixture()
    route["weeks"][0]["title"] = "Неделя; с, запятыми"
    ics = exports.route_to_ics(route, start_date=_dt.date(2026, 9, 1))
    assert "\\;" in ics
    assert "\\," in ics


def test_event_to_ics_renders_pushkin_event() -> None:
    evt = pushkin.list_events()[0]
    ics = exports.event_to_ics(evt)
    assert "BEGIN:VEVENT" in ics
    assert evt.title.split(";")[0] in ics or evt.title.split(",")[0] in ics
    assert "Пушкинская карта" in ics


def test_slug_safe() -> None:
    assert exports.slug("Хочу Пушкина за 4 недели!") == "хочу-пушкина-за-4-недели"
    assert exports.slug("") == "route"


def test_slug_truncation() -> None:
    out = exports.slug("Очень длинная строка " * 20, max_len=30)
    assert len(out) <= 30
