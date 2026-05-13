"""Тесты честного бенчмарка retrieval (A3) и audit-стора."""

from __future__ import annotations

import pytest

from app import audit, benchmark
from app.retrieval import get_index


@pytest.fixture(autouse=True)
def _reset() -> None:
    audit.get_benchmark_store().reset()
    get_index().reset()
    yield
    audit.get_benchmark_store().reset()
    get_index().reset()


@pytest.mark.asyncio
async def test_evaluate_passes_jury_thresholds() -> None:
    """Фиксируем пороги жюри: hit@5≥0.95, recall@5≥0.85, MRR≥0.85.

    P@5 в среднем ограничено снизу: у большинства запросов 1 релевант,
    поэтому P@5 < 0.5 — это нормально и даёт recall@5 ≈ 1.0.
    Контракт жюри — recall и MRR.
    """
    scores = await benchmark.evaluate(benchmark.GOLDEN_SET, k=5)
    assert scores.n_queries == len(benchmark.GOLDEN_SET)
    assert scores.hit_at_5 >= 0.95, f"hit@5={scores.hit_at_5:.3f} ниже порога 0.95"
    assert scores.mrr >= 0.85, f"MRR={scores.mrr:.3f} ниже порога 0.85"
    assert scores.recall_at_5 >= 0.85, f"recall@5={scores.recall_at_5:.3f} ниже порога 0.85"


@pytest.mark.asyncio
async def test_evaluate_empty_set_zero() -> None:
    scores = await benchmark.evaluate(golden=(), k=5)
    assert scores.n_queries == 0
    assert scores.p_at_5 == 0.0
    assert scores.misses == []


@pytest.mark.asyncio
async def test_record_run_writes_to_audit_store() -> None:
    scores = await benchmark.evaluate(benchmark.GOLDEN_SET[:3], k=5)
    rec = benchmark.record_run(scores, notes="unit-test")
    assert rec.notes == "unit-test"
    assert audit.get_benchmark_store().latest() is rec
    assert audit.get_benchmark_store().latest().metrics["p_at_5"] == scores.to_dict()["p_at_5"]


def test_scores_to_dict_rounding() -> None:
    s = benchmark.RetrievalScores(p_at_5=0.123456, p_at_3=0.5, recall_at_5=0.7, mrr=0.8, hit_at_5=1.0, n_queries=4)
    d = s.to_dict()
    assert d["p_at_5"] == 0.1235
    assert d["n_queries"] == 4
    assert d["misses"] == []
