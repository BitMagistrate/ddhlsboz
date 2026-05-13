"""
literary_calendar.py — Литературный календарь.

Эндпоинт `/api/calendar/today` возвращает события русской литературы:
дни рождения авторов, годовщины публикаций, премьеры. Все факты —
только то, что можно проверить по public-domain энциклопедиям.

Структура:
    [
      {"date": "MM-DD", "kind": "birth|publication|premiere", "title": "...", "year": 1799, "source_id": "..."},
      ...
    ]
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass


@dataclass(frozen=True)
class CalendarEntry:
    date: str  # MM-DD
    kind: str
    title: str
    year: int
    source_id: str | None = None
    note: str = ""


CALENDAR: list[CalendarEntry] = [
    CalendarEntry("06-06", "birth", "День рождения А. С. Пушкина", 1799, "pushkin_onegin"),
    CalendarEntry("01-29", "death", "Дата смерти А. С. Пушкина", 1837, "pushkin_onegin"),
    CalendarEntry("10-15", "birth", "День рождения М. Ю. Лермонтова", 1814, "lermontov_geroi"),
    CalendarEntry("09-09", "birth", "День рождения Л. Н. Толстого", 1828, "tolstoy_war"),
    CalendarEntry("11-11", "birth", "День рождения Ф. М. Достоевского", 1821, "dostoevsky_pn"),
    CalendarEntry("01-29", "birth", "День рождения А. П. Чехова", 1860, "chekhov_visnevy"),
    CalendarEntry(
        "01-29",
        "premiere",
        "Премьера «Вишнёвого сада» в Художественном театре",
        1904,
        "chekhov_visnevy",
    ),
    CalendarEntry("04-01", "birth", "День рождения Н. В. Гоголя", 1809, "gogol_dushi"),
    CalendarEntry("11-09", "birth", "День рождения И. С. Тургенева", 1818, "turgenev_otcy"),
    CalendarEntry(
        "01-15",
        "birth",
        "День рождения А. С. Грибоедова",
        1795,
        "griboedov_gore",
    ),
    CalendarEntry("06-18", "birth", "День рождения И. А. Гончарова", 1812, "goncharov_oblomov"),
    CalendarEntry("04-12", "birth", "День рождения А. Н. Островского", 1823, "ostrovsky_groza"),
    CalendarEntry("01-30", "publication", "Первый номер «Современника» (журнал)", 1836),
    CalendarEntry("11-26", "birth", "День рождения А. А. Блока", 1880, "blok_dvenadtsat"),
    CalendarEntry("06-23", "birth", "День рождения А. А. Ахматовой", 1889, "ahmatova_rekviem"),
    CalendarEntry(
        "10-08",
        "birth",
        "День рождения М. И. Цветаевой",
        1892,
        "tsvetaeva_moskva",
    ),
    CalendarEntry(
        "07-19",
        "birth",
        "День рождения В. В. Маяковского",
        1893,
        "mayakovsky_oblako",
    ),
    CalendarEntry(
        "05-15",
        "birth",
        "День рождения М. А. Булгакова",
        1891,
        "bulgakov_master",
    ),
    CalendarEntry(
        "05-24",
        "birth",
        "День рождения М. А. Шолохова",
        1905,
        "sholokhov_tihiy",
    ),
    CalendarEntry(
        "12-11",
        "birth",
        "День рождения А. И. Солженицына",
        1918,
        "solzhenitsyn_ivan_denisovich",
    ),
    CalendarEntry(
        "04-26",
        "birth",
        "День рождения Габдуллы Тукая",
        1886,
        "tukay_native",
    ),
    CalendarEntry(
        "10-22",
        "birth",
        "День рождения Мустая Карима",
        1919,
        "karim_long_long",
    ),
    CalendarEntry(
        "12-12",
        "birth",
        "День рождения Чингиза Айтматова",
        1928,
        "aitmatov_kassandra",
    ),
]


def today_entries(today: _dt.date | None = None) -> list[CalendarEntry]:
    today = today or _dt.date.today()
    key = f"{today.month:02d}-{today.day:02d}"
    return [e for e in CALENDAR if e.date == key]


def by_month(month: int) -> list[CalendarEntry]:
    return [e for e in CALENDAR if e.date.startswith(f"{month:02d}-")]


def entry_to_dict(e: CalendarEntry) -> dict:
    return {
        "date": e.date,
        "kind": e.kind,
        "title": e.title,
        "year": e.year,
        "source_id": e.source_id,
        "note": e.note,
    }
