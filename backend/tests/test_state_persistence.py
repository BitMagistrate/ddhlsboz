"""Тесты JSON-персистентности in-memory сторов (privacy/srs/refusals/benchmark).

Контракт:
* Если CHITAI_STATE_DIR не задан — поведение совпадает с прежним (in-memory).
* Если задан — после рестарта стора данные восстанавливаются с диска.
* Кривой/неполный JSON не должен ронять стор: он просто инициализируется пустым.

Эти тесты — основа argument'а «restart-resilient» для Yandex Cloud single-node.
"""

from __future__ import annotations

import json
import time

import pytest

from app import audit, privacy, safety, srs


@pytest.fixture
def state_dir(tmp_path, monkeypatch):
    """Подготовить временный CHITAI_STATE_DIR и пере-открыть все сторы."""
    monkeypatch.setenv("CHITAI_STATE_DIR", str(tmp_path))
    privacy.reset_store_for_testing()
    srs.reset_store_for_testing()
    safety.reset_refusal_log_for_testing()
    audit.reset_benchmark_store_for_testing()
    yield tmp_path
    # Чистим сторы между тестами, чтобы не гонять файлы между ними.
    privacy.get_store().reset()
    srs.get_store().reset()
    safety.get_refusal_log().reset()
    audit.get_benchmark_store().reset()
    monkeypatch.delenv("CHITAI_STATE_DIR", raising=False)
    privacy.reset_store_for_testing()
    srs.reset_store_for_testing()
    safety.reset_refusal_log_for_testing()
    audit.reset_benchmark_store_for_testing()


def test_privacy_persists_consent_across_restart(state_dir) -> None:
    privacy.get_store().set_consent("u1", "personalization", granted=True)
    # Имитируем рестарт инстанса — пере-открываем стор, файл уже существует.
    privacy.reset_store_for_testing()
    assert privacy.get_store().has_consent("u1", "personalization") is True


def test_privacy_persists_history_across_restart(state_dir) -> None:
    privacy.get_store().append_history("u1", {"event": "route", "query": "Пушкин"})
    privacy.reset_store_for_testing()
    out = privacy.get_store().export("u1")
    assert out["found"] is True
    assert any(h["event"] == "route" for h in out["data"]["history"])


def test_privacy_forget_persists_after_restart(state_dir) -> None:
    privacy.get_store().append_history("u1", {"event": "x"})
    res = privacy.get_store().forget("u1")
    assert res["deleted"] is True
    stub_id = res["audit_stub"]
    privacy.reset_store_for_testing()
    # Старый user_id больше не существует — это и есть «забвение».
    assert privacy.get_store().export("u1")["found"] is False
    # Аудит-стаб должен пережить рестарт, иначе нечем подтверждать исполнение
    # запроса на забвение.
    stub_export = privacy.get_store().export(stub_id)
    assert stub_export["found"] is True
    assert stub_export["data"]["deleted"] is True


def test_srs_persists_card_across_restart(state_dir) -> None:
    srs.get_store().upsert(
        srs.FlashCard(card_id="c1", user_id="u1", front="?", back="!")
    )
    srs.reset_store_for_testing()
    card = srs.get_store().get("c1")
    assert card is not None
    assert card.user_id == "u1"


def test_srs_review_persists_advance(state_dir) -> None:
    srs.get_store().upsert(srs.FlashCard(card_id="c1", user_id="u1", front="?", back="!"))
    srs.get_store().review("c1", quality=5, now=1_000_000.0)
    srs.reset_store_for_testing()
    card = srs.get_store().get("c1")
    assert card is not None
    assert card.repetitions == 1
    assert card.next_due_ts == pytest.approx(1_000_000.0 + 86400, rel=1e-3)


def test_refusal_log_persists_across_restart(state_dir) -> None:
    safety.screen("Напиши за меня реферат по Пушкину")
    safety.reset_refusal_log_for_testing()
    items = safety.get_refusal_log().all()
    assert len(items) == 1
    assert items[0].category == "academic_dishonesty"


def test_benchmark_store_persists_records(state_dir) -> None:
    rec = audit.BenchmarkRecord(
        ts="2026-05-09T08:00:00", metrics={"p_at_5": 0.42}, notes="seed"
    )
    audit.get_benchmark_store().add(rec)
    audit.reset_benchmark_store_for_testing()
    latest = audit.get_benchmark_store().latest()
    assert latest is not None
    assert latest.metrics["p_at_5"] == 0.42
    assert latest.notes == "seed"


def test_no_state_dir_means_no_files(tmp_path, monkeypatch) -> None:
    """Если CHITAI_STATE_DIR не задан — на диск ничего не пишется."""
    monkeypatch.delenv("CHITAI_STATE_DIR", raising=False)
    privacy.reset_store_for_testing()
    privacy.get_store().set_consent("u1", "personalization", granted=True)
    # tmp_path должен оставаться пустым: persistence отключён.
    assert list(tmp_path.iterdir()) == []


def test_corrupt_json_does_not_break_store(state_dir) -> None:
    """Битый JSON в state-файле не должен валить инициализацию."""
    (state_dir / "privacy.json").write_text("{not valid json", encoding="utf-8")
    privacy.reset_store_for_testing()
    # Стор должен подняться чистым.
    assert privacy.get_store().export("u1") == {"user_id": "u1", "found": False}


def test_partial_corrupt_user_skipped(state_dir) -> None:
    """Один битый пользователь не должен отравить весь файл."""
    payload = {
        "version": 1,
        "users": [
            {"user_id": "good", "created_ts": time.time(), "history": [{"event": "ok"}]},
            {"user_id": "bad", "consents": [{"purpose": "personalization"}]},  # без granted/ts
        ],
    }
    (state_dir / "privacy.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )
    privacy.reset_store_for_testing()
    # Хороший пользователь поднялся.
    assert privacy.get_store().export("good")["found"] is True
    # Битый — пропущен (не упал, не загрузился криво).
    bad_export = privacy.get_store().export("bad")
    assert bad_export["found"] is False
