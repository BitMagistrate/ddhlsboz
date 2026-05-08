"""Тесты AI-audit-ready: model card, prompt registry, бенчмарк-стор."""

from __future__ import annotations

import pytest

from app import audit


@pytest.fixture(autouse=True)
def _reset_bench() -> None:
    audit.get_benchmark_store().reset()
    yield
    audit.get_benchmark_store().reset()


def test_model_card_required_sections() -> None:
    mc = audit.get_model_card().to_dict()
    for key in (
        "name",
        "version",
        "intended_use",
        "not_intended_use",
        "training_data",
        "metrics",
        "limitations",
        "ethical_considerations",
        "governance",
    ):
        assert key in mc
    assert "152-ФЗ" in " ".join(mc["governance"]["compliance"])


def test_model_card_forbids_essay_generation() -> None:
    mc = audit.get_model_card().to_dict()
    forbidden = " ".join(mc["not_intended_use"])
    assert "сочинени" in forbidden.lower() or "реферат" in forbidden.lower()
    assert "антиплагиат" in forbidden.lower() or "детектор" in forbidden.lower()


def test_prompts_registry_has_curator_system() -> None:
    names = {p.name for p in audit.get_prompts()}
    assert "curator.system" in names
    # Проверяем безопасную метку.
    sys_prompt = next(p for p in audit.get_prompts() if p.name == "curator.system")
    assert "Никогда не пишешь за пользователя" in sys_prompt.template


def test_prompts_serialize_to_dict() -> None:
    payload = [p.to_dict() for p in audit.get_prompts()]
    for p in payload:
        for k in ("name", "purpose", "template", "audience", "version", "locale"):
            assert k in p
        assert p["locale"] == "ru-RU"


def test_benchmark_store_keeps_latest() -> None:
    store = audit.get_benchmark_store()
    rec1 = audit.BenchmarkRecord(ts="2026-01-01T00:00:00", metrics={"p_at_5": 0.5})
    rec2 = audit.BenchmarkRecord(ts="2026-01-02T00:00:00", metrics={"p_at_5": 0.9})
    store.add(rec1)
    store.add(rec2)
    assert store.latest() is rec2
    assert len(store.all()) == 2


def test_benchmark_store_caps_history() -> None:
    store = audit.get_benchmark_store()
    for i in range(60):
        store.add(audit.BenchmarkRecord(ts=str(i), metrics={"i": i}))
    items = store.all()
    assert len(items) == 50
    # Первая удержанная запись — №10.
    assert items[0].metrics["i"] == 10
