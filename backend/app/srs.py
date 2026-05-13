"""
Карточки и алгоритм SRS (SM-2) для тренажёра ЧитАИ.

Закрывает D3 из master TODO. Карточки строятся из тренажёрного банка вопросов
и из RAG-цитат. SM-2 — каноничный спейсед-репетишн (Piotr Wozniak, 1985 г.),
тот же, что используется в Anki/SuperMemo.

Хранение в демо in-memory (ConcurrentDict per user). В production — Postgres
с отдельной таблицей `srs_cards` (см. миграцию в /05_Юр_пакет/dpia.md).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Lock

from .state import StateBackend, get_state_backend


def _sm2_next(*, ease: float, repetitions: int, interval: int, quality: int) -> tuple[float, int, int]:
    """SM-2: возвращает (new_ease, new_repetitions, new_interval_days).

    quality ∈ [0..5], где 0 — забыл совсем, 5 — отличный ответ.
    """
    if quality < 3:
        return max(1.3, ease), 0, 1
    if repetitions == 0:
        new_interval = 1
    elif repetitions == 1:
        new_interval = 6
    else:
        new_interval = max(1, round(interval * ease))
    new_ease = max(1.3, ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))
    return new_ease, repetitions + 1, new_interval


@dataclass
class FlashCard:
    card_id: str
    user_id: str
    front: str
    back: str
    tags: list[str] = field(default_factory=list)
    ease: float = 2.5
    repetitions: int = 0
    interval_days: int = 0
    last_reviewed_ts: float = 0.0
    next_due_ts: float = field(default_factory=lambda: time.time())

    def to_dict(self) -> dict:
        return {
            "card_id": self.card_id,
            "user_id": self.user_id,
            "front": self.front,
            "back": self.back,
            "tags": list(self.tags),
            "ease": round(self.ease, 3),
            "repetitions": self.repetitions,
            "interval_days": self.interval_days,
            "last_reviewed_ts": self.last_reviewed_ts,
            "next_due_ts": self.next_due_ts,
        }


class SrsStore:
    def __init__(self, backend: StateBackend | None = None) -> None:
        self._lock = Lock()
        self._cards: dict[str, FlashCard] = {}
        self._backend = backend or get_state_backend("srs")
        self._load_unlocked()

    # ── persistence ─────────────────────────────────────────────────────
    def _serialize_unlocked(self) -> dict:
        return {"version": 1, "cards": [c.to_dict() for c in self._cards.values()]}

    def _load_unlocked(self) -> None:
        if not self._backend.enabled:
            return
        payload = self._backend.load()
        if not isinstance(payload, dict):
            return
        for raw in payload.get("cards") or []:
            try:
                card = FlashCard(
                    card_id=str(raw["card_id"]),
                    user_id=str(raw["user_id"]),
                    front=str(raw["front"]),
                    back=str(raw["back"]),
                    tags=list(raw.get("tags") or []),
                    ease=float(raw.get("ease", 2.5)),
                    repetitions=int(raw.get("repetitions", 0)),
                    interval_days=int(raw.get("interval_days", 0)),
                    last_reviewed_ts=float(raw.get("last_reviewed_ts", 0.0)),
                    next_due_ts=float(raw.get("next_due_ts", time.time())),
                )
                self._cards[card.card_id] = card
            except (KeyError, ValueError, TypeError):
                continue

    def _flush_unlocked(self) -> None:
        if self._backend.enabled:
            self._backend.save(self._serialize_unlocked())

    # ── public API ──────────────────────────────────────────────────────
    def upsert(self, card: FlashCard) -> FlashCard:
        with self._lock:
            self._cards[card.card_id] = card
            self._flush_unlocked()
            return card

    def get(self, card_id: str) -> FlashCard | None:
        with self._lock:
            return self._cards.get(card_id)

    def for_user(self, user_id: str) -> list[FlashCard]:
        with self._lock:
            return [c for c in self._cards.values() if c.user_id == user_id]

    def due(self, user_id: str, now: float | None = None, limit: int = 20) -> list[FlashCard]:
        now = now or time.time()
        with self._lock:
            cards = [c for c in self._cards.values() if c.user_id == user_id and c.next_due_ts <= now]
        cards.sort(key=lambda c: c.next_due_ts)
        return cards[:limit]

    def review(self, card_id: str, quality: int, now: float | None = None) -> FlashCard:
        if not 0 <= quality <= 5:
            raise ValueError("quality must be in [0..5]")
        now = now or time.time()
        with self._lock:
            card = self._cards.get(card_id)
            if card is None:
                raise KeyError(card_id)
            ease, reps, interval = _sm2_next(
                ease=card.ease,
                repetitions=card.repetitions,
                interval=card.interval_days,
                quality=quality,
            )
            card.ease = ease
            card.repetitions = reps
            card.interval_days = interval
            card.last_reviewed_ts = now
            card.next_due_ts = now + interval * 86400
            self._flush_unlocked()
            return card

    def reset(self) -> None:
        with self._lock:
            self._cards.clear()
            self._flush_unlocked()


_STORE = SrsStore()


def get_store() -> SrsStore:
    return _STORE


def reset_store_for_testing() -> None:
    global _STORE
    _STORE = SrsStore()


def make_card_from_route_week(user_id: str, week: dict) -> FlashCard:
    """Сборка карточки из RouteWeek.to_dict(). Front — вопрос, Back — цитата."""
    book = week.get("book", "?")
    fragment = week.get("fragment", "")
    front = f"Кто автор и какое произведение содержит фрагмент: «{fragment[:120]}»?"
    back = f"{book}\nЦитата (без подмены): «{fragment}».\nИсточник: {week.get('citation', '')}"
    return FlashCard(
        card_id=f"card-{user_id}-{week.get('book_id', 'x')}-{week.get('week', 0)}",
        user_id=user_id,
        front=front,
        back=back,
        tags=["route", str(week.get("book_id", ""))],
    )
