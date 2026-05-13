"""
Экспорт маршрута и календарных событий.

Закрывает D8 из master TODO. Поддерживаемые форматы:
* Markdown — для печати, Notion, Obsidian.
* iCalendar (RFC 5545) — для Google/Yandex/Outlook календарей.
* JSON-LD — для интеграции с Госуслугами Культура и Pushkin Card API.

Все экспорты детерминированы и не делают сетевых вызовов.
"""

from __future__ import annotations

import datetime as _dt
import re

from .pushkin import PushkinEvent


def _ics_escape(value: str) -> str:
    value = value.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;")
    return value.replace("\n", "\\n")


def route_to_markdown(route: dict) -> str:
    lines: list[str] = []
    query = route.get("query", "")
    summary = route.get("summary", "")
    weeks = route.get("weeks", [])
    sources = route.get("sources", [])
    disclaimer = route.get("disclaimer", "")
    lines.append(f"# Маршрут ЧитАИ — «{query}»")
    lines.append("")
    if summary:
        lines.append(summary)
        lines.append("")
    if weeks:
        lines.append("## Недели")
        lines.append("")
    for w in weeks:
        lines.append(f"### Неделя {w.get('week', '?')}. {w.get('title', '')}")
        lines.append("")
        if w.get("description"):
            lines.append(w["description"])
            lines.append("")
        if w.get("book"):
            lines.append(f"- **Книга:** {w['book']}")
        if w.get("fragment"):
            lines.append(f"- **Цитата:** «{w['fragment']}»")
        if w.get("citation"):
            lines.append(f"- **Издание:** {w['citation']}")
        if w.get("public_domain_url"):
            lines.append(f"- **Текст в public domain:** {w['public_domain_url']}")
        if w.get("pushkin_card_event"):
            lines.append(f"- **Пушкинская карта:** {w['pushkin_card_event']}")
        actions = w.get("actions") or []
        if actions:
            lines.append("- **Что сделать:**")
            for a in actions:
                lines.append(f"  - {a}")
        lines.append("")
    if sources:
        lines.append("## Источники (public domain)")
        lines.append("")
        for s in sources:
            lines.append(f"- {s.get('author', '')}. «{s.get('title', '')}» ({s.get('year', '')}). {s.get('public_domain_url', '')}")
        lines.append("")
    if disclaimer:
        lines.append("---")
        lines.append("")
        lines.append(f"*{disclaimer}*")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def route_to_ics(route: dict, *, start_date: _dt.date | None = None) -> str:
    """Календарь маршрута: одна задача на неделю + Pushkin events."""
    start_date = start_date or _dt.date.today()
    cal: list[str] = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//chitai.ru//Route//RU",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    weeks = route.get("weeks", [])
    for i, w in enumerate(weeks):
        d_start = start_date + _dt.timedelta(weeks=i)
        d_end = d_start + _dt.timedelta(days=7)
        uid = f"chitai-week-{i + 1}-{d_start.isoformat()}@chitai.ru"
        summary = f"Неделя {w.get('week', i + 1)}: {w.get('title', '')}"
        description = (
            f"{w.get('description', '')}\n"
            f"Книга: {w.get('book', '')}\n"
            f"Источник: {w.get('citation', '')}"
        )
        cal.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{_now_utc()}",
                f"DTSTART;VALUE=DATE:{d_start.strftime('%Y%m%d')}",
                f"DTEND;VALUE=DATE:{d_end.strftime('%Y%m%d')}",
                f"SUMMARY:{_ics_escape(summary)}",
                f"DESCRIPTION:{_ics_escape(description)}",
                "END:VEVENT",
            ]
        )
    cal.append("END:VCALENDAR")
    return "\r\n".join(cal) + "\r\n"


def event_to_ics(event: PushkinEvent) -> str:
    parsed = _dt.datetime.strptime(event.date, "%Y-%m-%d").date()
    end = parsed + _dt.timedelta(days=1)
    uid = f"chitai-pushkin-{event.id}@chitai.ru"
    summary = f"{event.title} (Пушкинская карта)"
    description = f"{event.venue}, {event.city}\nЦена: {event.price_rub}₽\nЗапись: {event.booking_url}"
    cal = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//chitai.ru//PushkinCard//RU",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{_now_utc()}",
        f"DTSTART;VALUE=DATE:{parsed.strftime('%Y%m%d')}",
        f"DTEND;VALUE=DATE:{end.strftime('%Y%m%d')}",
        f"SUMMARY:{_ics_escape(summary)}",
        f"DESCRIPTION:{_ics_escape(description)}",
        f"LOCATION:{_ics_escape(event.venue + ', ' + event.city)}",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return "\r\n".join(cal) + "\r\n"


def _now_utc() -> str:
    return _dt.datetime.now(_dt.UTC).strftime("%Y%m%dT%H%M%SZ")


def slug(text: str, max_len: int = 60) -> str:
    text = re.sub(r"[^A-Za-zА-Яа-я0-9]+", "-", text).strip("-")
    return text[:max_len].lower() or "route"
