"""Тесты новых фич: characters, challenge, exam_plan, quickread, quote_game,
literary_calendar, roi, i18n."""

from __future__ import annotations

import datetime as _dt

import pytest
from fastapi.testclient import TestClient

from app import (
    challenge as challenge_mod,
)
from app import (
    characters as characters_mod,
)
from app import (
    exam_plan as exam_plan_mod,
)
from app import (
    i18n as i18n_mod,
)
from app import (
    literary_calendar as calendar_mod,
)
from app import (
    quickread as quickread_mod,
)
from app import (
    quote_game as quote_game_mod,
)
from app import (
    roi as roi_mod,
)
from app import (
    state as state_mod,
)
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_state():
    state_mod.reset_kv()
    yield
    state_mod.reset_kv()


# ── characters ───────────────────────────────────────────────────────────────


def test_characters_list_has_raskolnikov():
    items = characters_mod.list_characters()
    slugs = {c["slug"] for c in items}
    assert "raskolnikov" in slugs
    assert "bazarov" in slugs


@pytest.mark.asyncio
async def test_ask_character_returns_citations():
    ans = await characters_mod.ask_character("raskolnikov", "Почему ты убил?")
    assert ans.character == "raskolnikov"
    # Хоть один из вариантов: либо ответ ground'нут с источниками,
    # либо есть дисклеймер «не в каноне» + цитаты из книги.
    assert isinstance(ans.citations, list)
    assert ans.book["title"] == "Преступление и наказание"


@pytest.mark.asyncio
async def test_ask_unknown_character_raises():
    with pytest.raises(KeyError):
        await characters_mod.ask_character("hermione", "Where is the wand?")


def test_api_characters_endpoint():
    r = client.get("/api/characters")
    assert r.status_code == 200
    assert len(r.json()["items"]) >= 5


def test_api_character_ask_endpoint():
    r = client.post(
        "/api/characters/ask",
        json={"character": "tatiana", "question": "Расскажи о письме"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["character"] == "tatiana"
    assert "citations" in body
    assert "safety" in body


def test_api_character_ask_unknown_returns_404():
    r = client.post(
        "/api/characters/ask",
        json={"character": "harry_potter", "question": "Что с твоим шрамом?"},
    )
    assert r.status_code == 404


# ── challenge ─────────────────────────────────────────────────────────────────


def test_challenge_progress_starts_empty():
    p = challenge_mod.get_progress("u1")
    assert p.completed == []
    assert p.target == 100
    assert p.next_milestone is not None
    assert p.next_milestone["threshold"] == 1


def test_challenge_mark_unmark_and_badges():
    p = challenge_mod.mark_read("u2", "pushkin_onegin")
    assert "pushkin_onegin" in p.completed
    # Первый бейдж 'Первый шаг' уже заработан
    assert any(b["slug"] == "first_step" for b in p.earned_badges)
    p2 = challenge_mod.unmark("u2", "pushkin_onegin")
    assert "pushkin_onegin" not in p2.completed


def test_challenge_mark_unknown_book_404():
    with pytest.raises(KeyError):
        challenge_mod.mark_read("u3", "no_such_book")


def test_api_challenge_books_endpoint():
    r = client.get("/api/challenge/books")
    assert r.status_code == 200
    assert r.json()["target"] == 100


def test_api_challenge_progress_and_mark_flow():
    user_id = "test-user-flow"
    r0 = client.get(f"/api/challenge/progress?user_id={user_id}")
    assert r0.json()["completed_count"] == 0
    r1 = client.post(
        "/api/challenge/mark-read",
        json={"user_id": user_id, "book_id": "pushkin_onegin"},
    )
    assert r1.status_code == 200
    assert r1.json()["completed_count"] == 1
    r2 = client.post(
        "/api/challenge/unmark",
        json={"user_id": user_id, "book_id": "pushkin_onegin"},
    )
    assert r2.json()["completed_count"] == 0


# ── exam_plan ─────────────────────────────────────────────────────────────────


def test_exam_plan_basic():
    future = (_dt.date.today() + _dt.timedelta(weeks=6)).isoformat()
    plan = exam_plan_mod.build_plan("u-exam", future, level=5)
    assert plan.weeks_left == 6
    assert len(plan.weeks) == 6
    assert plan.weeks[0].focus_topics
    assert plan.weeks[0].fragment
    d = exam_plan_mod.plan_to_dict(plan)
    assert d["weeks_left"] == 6
    assert "disclaimer" in d


def test_exam_plan_bad_date_raises():
    with pytest.raises(ValueError):
        exam_plan_mod.build_plan("u", "not-a-date")


def test_exam_plan_endpoint():
    future = (_dt.date.today() + _dt.timedelta(weeks=4)).isoformat()
    r = client.post(
        "/api/exam/plan",
        json={"user_id": "alice", "exam_date": future, "level": 6},
    )
    assert r.status_code == 200
    assert r.json()["weeks_left"] == 4


def test_exam_plan_endpoint_400_on_bad_date():
    r = client.post(
        "/api/exam/plan",
        json={"user_id": "alice", "exam_date": "tomorrow", "level": 6},
    )
    assert r.status_code == 400


# ── quickread ─────────────────────────────────────────────────────────────────


def test_quickread_basic():
    qr = quickread_mod.build("pushkin_onegin")
    assert qr.book_id == "pushkin_onegin"
    assert qr.estimated_minutes == 5
    assert qr.citations
    assert qr.flashcard["front"]


def test_quickread_endpoint_404():
    r = client.get("/api/quickread/no_such_book")
    assert r.status_code == 404


def test_quickread_endpoint_ok():
    r = client.get("/api/quickread/pushkin_onegin")
    assert r.status_code == 200
    body = r.json()
    assert body["estimated_minutes"] == 5
    assert body["talking_points"]


# ── quote_game ────────────────────────────────────────────────────────────────


def test_quote_game_full_round():
    r = quote_game_mod.new_round(seed=42)
    assert r.round_id
    assert len(r.options) == 4
    # Правильный ответ — в опциях
    assert any(o["id"] == r.correct_book_id for o in r.options)
    correct_result = quote_game_mod.check(r.round_id, r.correct_book_id)
    assert correct_result["correct"] is True


def test_quote_game_wrong_answer():
    r = quote_game_mod.new_round(seed=7)
    wrong = next(o["id"] for o in r.options if o["id"] != r.correct_book_id)
    res = quote_game_mod.check(r.round_id, wrong)
    assert res["correct"] is False
    assert res["correct_book_id"] == r.correct_book_id


def test_quote_game_unknown_round():
    with pytest.raises(KeyError):
        quote_game_mod.check("nope", "pushkin_onegin")


def test_quote_game_api_flow():
    r1 = client.post("/api/quote-game/new", params={"seed": 123})
    assert r1.status_code == 200
    body = r1.json()
    r2 = client.post(
        "/api/quote-game/check",
        json={"round_id": body["round_id"], "answer_book_id": body["options"][0]["id"]},
    )
    assert r2.status_code == 200
    assert "correct" in r2.json()


# ── literary_calendar ─────────────────────────────────────────────────────────


def test_calendar_pushkin_birthday():
    entries = calendar_mod.today_entries(today=_dt.date(2026, 6, 6))
    titles = {e.title for e in entries}
    assert any("Пушкин" in t for t in titles)


def test_calendar_by_month():
    items = calendar_mod.by_month(1)
    assert items  # январь — Чехов, Грибоедов и пр.


def test_calendar_api_today():
    r = client.get("/api/calendar/today")
    assert r.status_code == 200


def test_calendar_api_month_validation():
    r = client.get("/api/calendar/month/13")
    assert r.status_code == 400


# ── roi ───────────────────────────────────────────────────────────────────────


def test_roi_compute_default():
    out = roi_mod.compute(roi_mod.RoiInputs())
    assert out["annual_cost_rub"] > 0
    assert out["teacher_hours_saved"] > 0
    assert "disclaimer" in out


def test_roi_compute_zero_students():
    out = roi_mod.compute(roi_mod.RoiInputs(students=0, teachers=0))
    assert out["annual_cost_rub"] >= 0
    assert out["expected_ege_points_total"] == 0
    # cost-per-student деление-на-ноль не падает
    assert out["cost_per_student_per_year_rub"] >= 0


def test_roi_endpoint_uses_user_inputs():
    r = client.post(
        "/api/roi/compute",
        json={"students": 500, "teachers": 25},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["inputs"]["students"] == 500
    assert body["roi_ratio"] >= 0


# ── i18n ──────────────────────────────────────────────────────────────────────


def test_i18n_ru_default():
    out = i18n_mod.resolve(None)
    assert out["nav.curator"] == "Маршрут"


def test_i18n_unknown_locale_falls_back_to_ru():
    out = i18n_mod.resolve("xx")
    assert out["nav.search"] == "Поиск"


def test_i18n_tt_translation():
    out = i18n_mod.resolve("tt")
    assert "Эзләү" in out["nav.search"] or out["nav.search"] != "Поиск"


def test_i18n_locales_metadata():
    meta = i18n_mod.locales()
    assert meta["default"] == "ru"
    codes = {entry["code"] for entry in meta["supported"]}
    assert {"ru", "tt", "ba"}.issubset(codes)


def test_i18n_endpoints():
    r = client.get("/api/i18n?locale=ba")
    assert r.status_code == 200
    assert r.json()["locale"] == "ba"
    r2 = client.get("/api/i18n/locales")
    assert "supported" in r2.json()
