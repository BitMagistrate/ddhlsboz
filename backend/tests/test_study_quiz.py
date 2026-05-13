"""Tests for /api/study/quiz endpoint (used by Brain Dash game)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_study_quiz_requires_either_param() -> None:
    resp = client.get("/api/study/quiz")
    assert resp.status_code == 400
    assert "konspekt_id" in resp.json()["detail"] or "book_id" in resp.json()["detail"]


def test_study_quiz_by_book_id_capitanskaya_dochka() -> None:
    resp = client.get("/api/study/quiz", params={"book_id": "capitanskaya-dochka", "count": 5})
    assert resp.status_code == 200
    data = resp.json()
    assert data["book_id"] == "capitanskaya-dochka"
    assert data["konspekt_id"] is None
    assert isinstance(data["questions"], list)
    assert len(data["questions"]) >= 1
    q0 = data["questions"][0]
    # Shape совместим с frontend QuizQuestion (см. games/common/types.ts).
    assert {"id", "text", "options", "correctOptionId", "difficulty"}.issubset(q0.keys())
    assert isinstance(q0["options"], list) and len(q0["options"]) >= 2
    for opt in q0["options"]:
        assert {"id", "text"}.issubset(opt.keys())
    # correctOptionId должен совпадать с одним из option.id.
    option_ids = {opt["id"] for opt in q0["options"]}
    assert q0["correctOptionId"] in option_ids


def test_study_quiz_count_clamped_to_max_20() -> None:
    resp = client.get("/api/study/quiz", params={"book_id": "voyna-i-mir", "count": 999})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["questions"]) <= 20


def test_study_quiz_count_clamped_to_min_1() -> None:
    resp = client.get("/api/study/quiz", params={"book_id": "voyna-i-mir", "count": 0})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["questions"]) >= 1


def test_study_quiz_unknown_book_falls_back_to_literature_pool() -> None:
    resp = client.get(
        "/api/study/quiz",
        params={"book_id": "несуществующая-книга", "count": 3},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["questions"]) == 3


def test_study_quiz_by_konspekt_id_works_as_book_id_alias() -> None:
    # Пока EX1–EX5 не реализованы, konspekt_id трактуется как book_id.
    resp = client.get(
        "/api/study/quiz",
        params={"konspekt_id": "evgeniy-onegin", "count": 2},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["konspekt_id"] == "evgeniy-onegin"
    assert data["book_id"] is None
    assert len(data["questions"]) >= 1
