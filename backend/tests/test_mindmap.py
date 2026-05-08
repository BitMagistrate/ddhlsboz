"""Тесты mind map: граф «query → авторы → темы → книги»."""

from __future__ import annotations

import pytest

from app import mindmap
from app.retrieval import get_index


@pytest.fixture(autouse=True)
def _reset_index() -> None:
    get_index().reset()
    yield
    get_index().reset()


@pytest.mark.asyncio
async def test_build_mindmap_links_root_to_authors_and_books() -> None:
    mm = await mindmap.build_mindmap("Пушкин Онегин", limit=4)
    kinds = {n.kind for n in mm.nodes}
    assert "query" in kinds
    assert "author" in kinds
    assert "book" in kinds
    # Хотя бы одна цитата заземлена.
    assert mm.citations
    for c in mm.citations:
        assert c["fragment"]
        assert c["citation"]


@pytest.mark.asyncio
async def test_build_mindmap_returns_dict_payload() -> None:
    mm = await mindmap.build_mindmap("Серебряный век", limit=3)
    payload = mm.to_dict()
    assert payload["query"] == "Серебряный век"
    assert payload["nodes"]
    assert payload["edges"]
    for edge in payload["edges"]:
        assert edge["source"]
        assert edge["target"]


@pytest.mark.asyncio
async def test_themes_weight_equal_book_count() -> None:
    mm = await mindmap.build_mindmap("Достоевский ЕГЭ", limit=4)
    theme_nodes = [n for n in mm.nodes if n.kind == "theme"]
    if not theme_nodes:
        pytest.skip("на демо-корпусе у Достоевского может не быть тем ЕГЭ")
    for tn in theme_nodes:
        # вес ровно равен числу edges 'раскрывается' от темы к книгам.
        linked = sum(1 for e in mm.edges if e.source == tn.id and e.label == "раскрывается")
        assert tn.weight == float(linked)


@pytest.mark.asyncio
async def test_unknown_query_falls_back_to_corpus_head() -> None:
    """Хочется чтобы UI не получал пустой граф; берём начало корпуса."""
    mm = await mindmap.build_mindmap("zzzzz_qqqqq_unknown_topic_xyz", limit=2)
    assert any(n.kind == "book" for n in mm.nodes)
