"""Тесты Pushkin Card каталога: фильтрация и рекомендации."""

from __future__ import annotations

import pytest

from app import pushkin


def test_catalog_has_canonical_events() -> None:
    ids = {e.id for e in pushkin.list_events()}
    assert "evt-rgb-01" in ids
    assert "evt-yakutsk-01" in ids
    assert "evt-yasnaya-01" in ids


def test_event_to_dict_age_range_label() -> None:
    evt = pushkin.list_events()[0]
    payload = evt.to_dict()
    assert payload["age_range"] == f"{evt.age_min}–{evt.age_max}"
    assert payload["price_rub"] == evt.price_rub


@pytest.mark.parametrize(
    "book_id, expected_event_id",
    [
        ("pushkin_onegin", "evt-rgb-01"),
        ("ostrovsky_groza", "evt-mxat-01"),
        ("dostoevsky_pn", "evt-pushkinhouse-01"),
        ("karim_long_long", "evt-ufa-01"),
        ("olonkho_djurulu", "evt-yakutsk-01"),
    ],
)
def test_by_book(book_id: str, expected_event_id: str) -> None:
    events = pushkin.by_book(book_id)
    assert any(e.id == expected_event_id for e in events)


def test_by_region() -> None:
    moscow = pushkin.by_region("RU-MOW")
    assert all(e.region == "RU-MOW" for e in moscow)
    assert moscow


def test_by_theme_case_insensitive() -> None:
    silver = pushkin.by_theme("серебряный век")
    assert any("Серебряный" in t for t in (theme for e in silver for theme in e.themes))


def test_recommend_returns_book_aware_first() -> None:
    out = pushkin.recommend(["pushkin_onegin", "tolstoy_war"], region="RU-MOW", limit=4)
    ids = {e.id for e in out}
    assert "evt-rgb-01" in ids


def test_recommend_respects_limit() -> None:
    out = pushkin.recommend(["pushkin_onegin"], limit=1)
    assert len(out) == 1


def test_recommend_falls_back_to_region() -> None:
    """Если по книгам нашли мало — добиваем по региону."""
    out = pushkin.recommend(["zzz_unknown"], region="RU-SPE", limit=3)
    assert all(e.region == "RU-SPE" for e in out)
    assert out
