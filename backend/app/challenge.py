"""
challenge.py — Челлендж «100 книг за год» + бейджи.

Лента из 100 произведений (упорядоченные «легко → сложно») и
система бейджей. Прогресс хранится в `state.py` (JSON-persistent).
"""

from __future__ import annotations

from dataclasses import dataclass

from . import corpus as corpus_mod
from . import state as state_mod

BADGES: list[dict] = [
    {"slug": "first_step", "title": "Первый шаг", "threshold": 1, "icon": "📖"},
    {"slug": "five_books", "title": "Пять книг", "threshold": 5, "icon": "🎯"},
    {"slug": "ten_books", "title": "Десять книг", "threshold": 10, "icon": "🌟"},
    {"slug": "quarter_century", "title": "Четверть пути", "threshold": 25, "icon": "🏆"},
    {"slug": "half_century", "title": "Полпути", "threshold": 50, "icon": "🥈"},
    {"slug": "century_reader", "title": "Стократный читатель", "threshold": 100, "icon": "🥇"},
    {"slug": "pushkin_fan", "title": "Пушкинист", "threshold": 3, "icon": "🎩", "filter": "pushkin"},
    {"slug": "tolstoy_fan", "title": "Толстовед", "threshold": 2, "icon": "🐎", "filter": "tolstoy"},
    {
        "slug": "ege_ready",
        "title": "ЕГЭ-готов",
        "threshold": 10,
        "icon": "🎓",
        "filter": "ege",
    },
]


@dataclass
class ChallengeProgress:
    user_id: str
    completed: list[str]
    target: int
    earned_badges: list[dict]
    next_milestone: dict | None


def _book_list() -> list[corpus_mod.Source]:
    """Упорядоченный список — приоритет: курс школы, потом ЕГЭ-темы."""
    return sorted(corpus_mod.CORPUS, key=lambda s: (s.school_grade, -len(s.ege_topics), s.id))


def get_books() -> list[dict]:
    return [
        {
            "id": s.id,
            "author": s.author,
            "title": s.title,
            "school_grade": s.school_grade,
            "year": s.year,
            "ege_topics": s.ege_topics,
        }
        for s in _book_list()
    ]


def _state_key(user_id: str) -> str:
    return f"challenge_progress:{user_id.strip()}"


def _filter_matches(book: corpus_mod.Source | None, filter_slug: str) -> bool:
    if book is None:
        return False
    if filter_slug == "pushkin":
        return "Пушкин" in book.author or book.pushkin_card
    if filter_slug == "tolstoy":
        return "Толстой" in book.author
    if filter_slug == "ege":
        return len(book.ege_topics) > 0
    return False


def _calc_badges(completed_ids: list[str]) -> list[dict]:
    earned = []
    completed_books = [corpus_mod.by_id(bid) for bid in completed_ids]
    for badge in BADGES:
        flt = badge.get("filter")
        if flt:
            count = sum(1 for b in completed_books if _filter_matches(b, flt))
        else:
            count = len(completed_ids)
        if count >= badge["threshold"]:
            earned.append({**badge, "earned_at_count": count})
    return earned


def _next_milestone(completed_count: int) -> dict | None:
    for badge in BADGES:
        if badge.get("filter"):
            continue
        if completed_count < badge["threshold"]:
            return {**badge, "remaining": badge["threshold"] - completed_count}
    return None


def get_progress(user_id: str) -> ChallengeProgress:
    raw = state_mod.get(_state_key(user_id), default={"completed": []})
    completed = list(dict.fromkeys(raw.get("completed", [])))
    earned = _calc_badges(completed)
    return ChallengeProgress(
        user_id=user_id,
        completed=completed,
        target=100,
        earned_badges=earned,
        next_milestone=_next_milestone(len(completed)),
    )


def mark_read(user_id: str, book_id: str) -> ChallengeProgress:
    if corpus_mod.by_id(book_id) is None:
        raise KeyError(f"unknown book_id: {book_id}")
    raw = state_mod.get(_state_key(user_id), default={"completed": []})
    completed = list(dict.fromkeys(raw.get("completed", []) + [book_id]))
    state_mod.set_value(_state_key(user_id), {"completed": completed})
    return get_progress(user_id)


def unmark(user_id: str, book_id: str) -> ChallengeProgress:
    raw = state_mod.get(_state_key(user_id), default={"completed": []})
    completed = [b for b in raw.get("completed", []) if b != book_id]
    state_mod.set_value(_state_key(user_id), {"completed": completed})
    return get_progress(user_id)
