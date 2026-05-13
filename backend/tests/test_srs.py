"""Тесты SRS / SM-2: интервалы, ease, store, материализация из RouteWeek."""

from __future__ import annotations

import pytest

from app import srs


@pytest.fixture(autouse=True)
def _reset_store() -> None:
    srs.get_store().reset()
    yield
    srs.get_store().reset()


def test_sm2_first_pass_yields_one_day() -> None:
    ease, reps, interval = srs._sm2_next(ease=2.5, repetitions=0, interval=0, quality=4)
    assert reps == 1
    assert interval == 1
    assert ease >= 2.5  # quality 4 не уменьшает ease


def test_sm2_failure_resets_repetitions() -> None:
    ease, reps, interval = srs._sm2_next(ease=2.5, repetitions=3, interval=14, quality=1)
    assert reps == 0
    assert interval == 1
    assert ease == 2.5  # ease не падает ниже текущего при отказе


def test_sm2_growth_progression() -> None:
    """SM-2: 1 → 6 → ~6*ease → ..."""
    ease, reps, interval = srs._sm2_next(ease=2.5, repetitions=0, interval=0, quality=5)
    assert (reps, interval) == (1, 1)
    ease, reps, interval = srs._sm2_next(ease=ease, repetitions=reps, interval=interval, quality=5)
    assert (reps, interval) == (2, 6)
    ease, reps, interval = srs._sm2_next(ease=ease, repetitions=reps, interval=interval, quality=5)
    assert reps == 3
    assert interval >= 6


def test_sm2_minimum_ease_is_1_3() -> None:
    ease, _, _ = srs._sm2_next(ease=1.3, repetitions=10, interval=30, quality=0)
    assert ease == 1.3


def test_store_upsert_and_get() -> None:
    store = srs.get_store()
    card = srs.FlashCard(
        card_id="c1", user_id="u1", front="Кто автор Шинели?", back="Гоголь"
    )
    store.upsert(card)
    assert store.get("c1") is card
    assert store.for_user("u1") == [card]


def test_store_due_filters_by_user_and_time() -> None:
    store = srs.get_store()
    store.upsert(srs.FlashCard(card_id="c1", user_id="u1", front="?", back="!", next_due_ts=0))
    store.upsert(srs.FlashCard(card_id="c2", user_id="u2", front="?", back="!", next_due_ts=0))
    due_u1 = store.due("u1", now=1000.0)
    assert {c.card_id for c in due_u1} == {"c1"}


def test_store_review_advances_card() -> None:
    store = srs.get_store()
    store.upsert(srs.FlashCard(card_id="c1", user_id="u1", front="?", back="!"))
    updated = store.review("c1", quality=5, now=1_000_000.0)
    assert updated.repetitions == 1
    assert updated.interval_days == 1
    assert updated.next_due_ts == pytest.approx(1_000_000.0 + 86400, rel=1e-3)


def test_store_review_unknown_card_raises() -> None:
    with pytest.raises(KeyError):
        srs.get_store().review("missing", quality=4)


def test_review_quality_bounds() -> None:
    store = srs.get_store()
    store.upsert(srs.FlashCard(card_id="c1", user_id="u1", front="?", back="!"))
    with pytest.raises(ValueError):
        store.review("c1", quality=6)
    with pytest.raises(ValueError):
        store.review("c1", quality=-1)


def test_make_card_from_route_week_carries_citation() -> None:
    week = {
        "week": 1,
        "book": "Пушкин. «Капитанская дочка»",
        "book_id": "pushkin_dochka",
        "fragment": "Береги честь смолоду",
        "citation": "ПСС т.6",
    }
    card = srs.make_card_from_route_week("u1", week)
    assert card.user_id == "u1"
    assert "Капитанская дочка" in card.back
    assert "Береги честь смолоду" in card.back
    assert "Береги честь смолоду" in card.front
    assert "pushkin_dochka" in card.tags
