"""Тесты режима «Учёба» (PR#9/PDF/URL/TEXT/24/25/G2/FIB/WT/MASTERY/27a)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import study as study_mod
from app.llm.router import reset_router
from app.main import app


@pytest.fixture(autouse=True)
def _reset(monkeypatch: pytest.MonkeyPatch) -> None:
    """LLM mock + чистое хранилище материалов на каждый тест."""

    for var in (
        "YANDEX_GPT_API_KEY",
        "YANDEX_GPT_FOLDER_ID",
        "GIGACHAT_AUTHORIZATION_KEY",
        "GIGACHAT_SCOPE",
    ):
        monkeypatch.delenv(var, raising=False)
    reset_router()
    study_mod.reset_store()


def _client() -> TestClient:
    return TestClient(app)


# ── module-level ────────────────────────────────────────────────────────────


def test_ingest_text_creates_material_and_chunks() -> None:
    m = study_mod.ingest_text("u1", "Заметки", "Это пробный текст. " * 80)
    assert m.kind == "text"
    assert m.id.startswith("mt_")
    chunks = study_mod.material_chunks(m.id)
    assert len(chunks) >= 1
    assert chunks[0].terms  # terms заполнены


def test_search_chunks_returns_relevant_for_keyword() -> None:
    m = study_mod.ingest_text(
        "u1",
        "Война и мир",
        "Война началась в 1812 году. " * 5
        + "\n\nМир пришёл в 1815. " * 5
        + "\n\nНаполеон проиграл при Бородино. " * 5,
    )
    hits = study_mod.search_chunks(m.id, "Наполеон Бородино")
    assert hits
    assert any("Бородино" in c.text for c in hits)


def test_delete_material_cascades_chunks() -> None:
    m = study_mod.ingest_text("u1", "X", "Достаточно длинный текст. " * 20)
    assert study_mod.delete_material(m.id, actor="u1")
    assert study_mod.get_material(m.id) is None
    assert study_mod.material_chunks(m.id) == []


def test_audio_ingest_requires_biometry_consent() -> None:
    # Контракт PR#23: без согласия на биометрию аудио не принимаем.
    import asyncio

    with pytest.raises(PermissionError):
        asyncio.run(
            study_mod.ingest_audio_stub(
                "u1", "rec", biometry_consent=False, age_ok=True
            )
        )


def test_mastery_starts_empty() -> None:
    out = study_mod.mastery_for_user("u-empty")
    assert out["buckets"] == {
        "unfamiliar": 0,
        "learning": 0,
        "familiar": 0,
        "mastered": 0,
    }


# ── API endpoints ───────────────────────────────────────────────────────────


def _ingest_text(client: TestClient, *, text: str = "Длинный текст. " * 50) -> dict:
    r = client.post(
        "/api/study/ingest/text",
        json={"title": "T1", "text": text},
        headers={"X-User-Id": "u1"},
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_api_ingest_text_and_list() -> None:
    with _client() as c:
        m = _ingest_text(c)
        assert m["chunks_count"] >= 1
        r = c.get("/api/study/materials", headers={"X-User-Id": "u1"})
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 1
        assert data["items"][0]["id"] == m["id"]


def test_api_universal_ingest_dispatches_text() -> None:
    with _client() as c:
        r = c.post(
            "/api/study/ingest",
            json={"kind": "text", "title": "T", "text": "Длинный текст. " * 40},
            headers={"X-User-Id": "u1"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["kind"] == "text"


def test_api_universal_ingest_rejects_unknown_kind() -> None:
    with _client() as c:
        r = c.post(
            "/api/study/ingest",
            json={"kind": "satellite_image"},
            headers={"X-User-Id": "u1"},
        )
        assert r.status_code == 400


def test_api_ingest_audio_403_without_consent() -> None:
    with _client() as c:
        r = c.post(
            "/api/study/ingest/audio",
            json={"title": "rec", "biometry_consent": False, "age_ok": True},
            headers={"X-User-Id": "u1"},
        )
        assert r.status_code == 403


def test_api_ingest_audio_ok_with_consent() -> None:
    with _client() as c:
        r = c.post(
            "/api/study/ingest/audio",
            json={"title": "rec", "biometry_consent": True, "age_ok": True},
            headers={"X-User-Id": "u1"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "processing"
        assert r.json()["kind"] == "audio"


def test_api_conspect_qa_flashcards_quiz_essay() -> None:
    with _client() as c:
        m = _ingest_text(
            c,
            text=(
                "Александр Пушкин написал «Капитанскую дочку» в 1836 году. "
                "Главный герой — Пётр Гринёв. "
                "Пугачёв подарил Гринёву заячий тулуп. " * 4
            ),
        )
        mid = m["id"]
        # Конспект (mock fallback)
        r = c.post(f"/api/study/material/{mid}/conspect")
        assert r.status_code == 200
        consp = r.json()
        assert "summary" in consp
        # Q&A
        r = c.post(
            f"/api/study/material/{mid}/qa",
            json={"question": "Кто главный герой?"},
            headers={"X-User-Id": "u1"},
        )
        assert r.status_code == 200
        assert "answer" in r.json()
        # Flashcards
        r = c.post(
            f"/api/study/material/{mid}/flashcards", json={"count": 3}
        )
        assert r.status_code == 200
        assert r.json()["count"] >= 1
        # Quiz
        r = c.post(
            f"/api/study/material/{mid}/quiz", json={"count": 3}
        )
        assert r.status_code == 200
        items = r.json()["items"]
        assert items, r.text
        for it in items:
            assert it["options"]
            assert 0 <= it["correct_index"] < len(it["options"])
            assert len(it["explanation_wrong"]) == len(it["options"]) - 1
        # FIB
        r = c.post(f"/api/study/material/{mid}/fib", json={"count": 2})
        assert r.status_code == 200
        # Эссе
        r = c.post(
            f"/api/study/material/{mid}/essay/grade",
            json={
                "prompt": "В чём смысл «Капитанской дочки»?",
                "essay": "Капитанская дочка — о чести и долге. " * 30,
            },
            headers={"X-User-Id": "u1"},
        )
        assert r.status_code == 200
        out = r.json()
        assert "result" in out
        assert out["result"]["total"] >= 0


def test_api_delete_material_cascades() -> None:
    with _client() as c:
        m = _ingest_text(c)
        mid = m["id"]
        r = c.delete(f"/api/study/material/{mid}", headers={"X-User-Id": "u1"})
        assert r.status_code == 200
        r = c.get(f"/api/study/material/{mid}")
        assert r.status_code == 404


def test_api_tariffs_and_waitlist_and_subscription() -> None:
    with _client() as c:
        r = c.get("/api/study/tariffs")
        assert r.status_code == 200
        ts = r.json()["tariffs"]
        assert set(ts) == {"free", "week", "month", "year"}
        r = c.post(
            "/api/study/waitlist",
            json={"email": "user@example.ru", "source": "pricing"},
        )
        assert r.status_code == 200
        r = c.post(
            "/api/study/subscription",
            json={"tariff": "month"},
            headers={"X-User-Id": "u1"},
        )
        assert r.status_code == 200
        r = c.get("/api/study/subscription", headers={"X-User-Id": "u1"})
        assert r.json()["tariff"] == "month"


def test_api_share_invite_resolve_and_comments() -> None:
    with _client() as c:
        m = _ingest_text(c)
        mid = m["id"]
        r = c.post(
            f"/api/study/material/{mid}/share",
            json={"role": "viewer"},
            headers={"X-User-Id": "u1"},
        )
        assert r.status_code == 200
        tok = r.json()["token"]
        r = c.get(f"/api/study/share/{tok}")
        assert r.status_code == 200
        assert r.json()["material"]["id"] == mid
        r = c.post(
            f"/api/study/material/{mid}/comments",
            json={"body": "интересно"},
            headers={"X-User-Id": "u1"},
        )
        assert r.status_code == 200
        r = c.get(f"/api/study/material/{mid}/comments")
        assert r.json()["count"] == 1


def test_api_html_export_works() -> None:
    with _client() as c:
        m = _ingest_text(c)
        mid = m["id"]
        r = c.get(f"/api/study/material/{mid}/export.html")
        assert r.status_code == 200
        assert "ЧитАИ" in r.text or "конспект" in r.text.lower()
