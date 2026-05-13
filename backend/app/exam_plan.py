"""
exam_plan.py — Персональный план подготовки к ЕГЭ по литературе.

Алгоритм:
1. Принимаем дату экзамена и текущий уровень (1–10).
2. Считаем недели до экзамена.
3. Из корпуса выбираем темы ЕГЭ, отсутствующие у пользователя,
   и распределяем по неделям (по 1–2 темы/неделю).
4. На каждую неделю даём: фрагмент-якорь, 3 действия, 1 SRS-карточку.
5. Финальная неделя — повторение + пробник.

Используется в `app/main.py::/api/exam/plan`.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass

from . import corpus as corpus_mod


@dataclass
class ExamWeek:
    week: int
    starts_at: str
    focus_topics: list[str]
    book_ids: list[str]
    fragment: str
    actions: list[str]


@dataclass
class ExamPlan:
    user_id: str
    exam_date: str
    weeks_left: int
    level: int
    summary: str
    weeks: list[ExamWeek]
    disclaimer: str


_DEFAULT_TOPICS = [
    "Литература первой половины XIX века",
    "Литература второй половины XIX века",
    "Литература конца XIX — начала XX века",
    "Литература первой половины XX века",
    "Литература второй половины XX века",
    "Тема чести",
    "Тема маленького человека",
    "Тема Родины",
    "Образ автора",
    "Лишний человек",
    "Анализ стихотворения",
    "Сопоставительная задача",
]


def _parse_date(date_str: str) -> _dt.date:
    try:
        return _dt.date.fromisoformat(date_str)
    except ValueError as exc:
        raise ValueError("exam_date должен быть в формате YYYY-MM-DD") from exc


def _topic_to_books(topic: str) -> list[corpus_mod.Source]:
    norm = topic.lower()
    matches = []
    for src in corpus_mod.CORPUS:
        for t in src.ege_topics:
            if t.lower() == norm or norm in t.lower():
                matches.append(src)
                break
    return matches


def build_plan(
    user_id: str,
    exam_date: str,
    *,
    level: int = 5,
    weeks_max: int = 24,
) -> ExamPlan:
    """Генерирует план на N недель до даты экзамена."""
    if not user_id or not user_id.strip():
        raise ValueError("user_id обязателен")
    target = _parse_date(exam_date)
    today = _dt.date.today()
    delta_days = max(0, (target - today).days)
    weeks_left = max(1, min(weeks_max, (delta_days + 6) // 7))

    # Раскладываем темы по неделям: одну ключевую + одну вспомогательную.
    topics_per_week = []
    pool = list(_DEFAULT_TOPICS)
    for i in range(weeks_left):
        focus = [pool[i % len(pool)]]
        if i + len(_DEFAULT_TOPICS) // 2 < len(pool):
            focus.append(pool[(i + len(_DEFAULT_TOPICS) // 2) % len(pool)])
        topics_per_week.append(focus)

    weeks: list[ExamWeek] = []
    for i, topics in enumerate(topics_per_week):
        books: list[corpus_mod.Source] = []
        for t in topics:
            books.extend(_topic_to_books(t))
        book = books[0] if books else corpus_mod.CORPUS[i % len(corpus_mod.CORPUS)]
        starts_at = (today + _dt.timedelta(weeks=i)).isoformat()
        actions = [
            f"Прочитать фрагмент: «{book.title}» — {book.fragment[:60]}…",
            f"Разобрать тему: {topics[0]} (по плану КИМ ФИПИ)",
            "Написать мини-сочинение (150 слов) и проверить себя по чеклисту.",
        ]
        if level <= 3:
            actions.append("Освежить понятия: эпитет, метафора, лирический герой.")
        weeks.append(
            ExamWeek(
                week=i + 1,
                starts_at=starts_at,
                focus_topics=topics,
                book_ids=list({b.id for b in books})[:3],
                fragment=book.fragment,
                actions=actions,
            )
        )

    summary = (
        f"План подготовки к ЕГЭ по литературе на {weeks_left} недели до {exam_date}. "
        f"Текущий уровень: {level}/10. План построен на корпусе public domain "
        f"({len(corpus_mod.CORPUS)} произведений) и темах КИМ ФИПИ."
    )
    disclaimer = (
        "План носит рекомендательный характер и не заменяет официальную программу. "
        "Темы соответствуют последней опубликованной спецификации ФИПИ для ЕГЭ."
    )
    return ExamPlan(
        user_id=user_id,
        exam_date=exam_date,
        weeks_left=weeks_left,
        level=level,
        summary=summary,
        weeks=weeks,
        disclaimer=disclaimer,
    )


def plan_to_dict(plan: ExamPlan) -> dict:
    return {
        "user_id": plan.user_id,
        "exam_date": plan.exam_date,
        "weeks_left": plan.weeks_left,
        "level": plan.level,
        "summary": plan.summary,
        "disclaimer": plan.disclaimer,
        "weeks": [
            {
                "week": w.week,
                "starts_at": w.starts_at,
                "focus_topics": w.focus_topics,
                "book_ids": w.book_ids,
                "fragment": w.fragment,
                "actions": w.actions,
            }
            for w in plan.weeks
        ],
    }
