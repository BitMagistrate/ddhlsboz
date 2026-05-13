"""
quote_game.py — Мини-игра «Угадай произведение по цитате».

API:
- `new_round(seed)` — выбирает цитату из корпуса и 4 варианта ответа (1 правильный).
- `check(round_id, answer)` — проверяет ответ и возвращает объяснение.

Состояние раундов хранится в `state.py` (5 минут TTL).
"""

from __future__ import annotations

import hashlib
import random
import time
from dataclasses import dataclass

from . import corpus as corpus_mod
from . import state as state_mod

ROUND_TTL_SECONDS = 600
KV_PREFIX = "quote_round:"


@dataclass
class GameRound:
    round_id: str
    quote: str
    options: list[dict]  # {id, label}
    correct_book_id: str


def _stable_id(quote: str, salt: int) -> str:
    return hashlib.sha256(f"{quote}|{salt}".encode()).hexdigest()[:16]


def new_round(seed: int | None = None) -> GameRound:
    rng = random.Random(seed) if seed is not None else random.Random()
    pool = [b for b in corpus_mod.CORPUS if b.fragment]
    if len(pool) < 4:
        raise RuntimeError("corpus too small for quote game (need >=4 books with fragments)")
    correct = rng.choice(pool)
    distractors = rng.sample([b for b in pool if b.id != correct.id], 3)
    options = [
        {"id": b.id, "label": f"{b.author}. «{b.title}»"}
        for b in [correct] + distractors
    ]
    rng.shuffle(options)
    round_id = _stable_id(correct.fragment, int(time.time() * 1000))
    state_mod.set_value(
        KV_PREFIX + round_id,
        {
            "correct_book_id": correct.id,
            "options": options,
            "created": time.time(),
        },
    )
    return GameRound(
        round_id=round_id,
        quote=correct.fragment,
        options=options,
        correct_book_id=correct.id,
    )


def check(round_id: str, answer_book_id: str) -> dict:
    entry = state_mod.get(KV_PREFIX + round_id)
    if not entry:
        raise KeyError("round_expired_or_unknown")
    if time.time() - entry.get("created", 0) > ROUND_TTL_SECONDS:
        raise KeyError("round_expired")
    correct_id = entry["correct_book_id"]
    is_correct = answer_book_id == correct_id
    book = corpus_mod.by_id(correct_id)
    explanation = (
        f"«{book.title}» ({book.author}) — {book.summary or book.fragment[:120]}…"
        if book
        else ""
    )
    return {
        "round_id": round_id,
        "correct": is_correct,
        "correct_book_id": correct_id,
        "answer_book_id": answer_book_id,
        "explanation": explanation,
        "citation": book.citation if book else "",
    }


def round_to_dict(r: GameRound) -> dict:
    return {
        "round_id": r.round_id,
        "quote": r.quote,
        "options": r.options,
    }
