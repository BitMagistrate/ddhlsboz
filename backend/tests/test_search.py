"""Тесты гибридного поиска: BM25, Vector, Reranker, чанкинг."""

from __future__ import annotations

import pytest

from app.search import (
    BM25Index,
    LexicalReranker,
    TfidfEmbeddings,
    VectorIndex,
    chunk_corpus,
    normalize,
    tokenize,
)
from app.search.hybrid import HybridSearch, _minmax
from app.search.stemmer import stem

# ── Tokenizer / stemmer ──────────────────────────────────────────────────


def test_normalize_lowercase_and_yo() -> None:
    assert normalize("Ёлка ПОД ёлкой") == "елка под елкой"


def test_tokenize_drops_stop_words() -> None:
    out = tokenize("Я читаю и понимаю Пушкина под небом")
    # стоп-слова «я», «и», «под» отброшены; «Пушкина» нормализован.
    joined = " ".join(out)
    for stop in ("я ", " и ", " под "):
        assert stop not in f" {joined} "


def test_tokenize_min_len() -> None:
    out = tokenize("a b cd ef gh", drop_stop=False, min_len=2, stem=False)
    assert "a" not in out
    assert "cd" in out


def test_stemmer_groups_inflections() -> None:
    forms = ["пушкин", "пушкина", "пушкину", "пушкине", "пушкиным"]
    stems = {stem(w) for w in forms}
    assert len(stems) == 1


def test_stemmer_keeps_short_tokens() -> None:
    assert stem("я") == "я"
    assert stem("он") == "он"


# ── BM25 ─────────────────────────────────────────────────────────────────


def _build_bm25() -> BM25Index:
    idx = BM25Index()
    idx.add("d1", "Пушкин Евгений Онегин роман в стихах")
    idx.add("d2", "Толстой Война и мир эпопея")
    idx.add("d3", "Чехов Вишнёвый сад комедия")
    idx.fit()
    return idx


def test_bm25_finds_query_match() -> None:
    idx = _build_bm25()
    hits = idx.search("Онегин", limit=3)
    assert hits[0].doc_id == "d1"
    assert hits[0].score > 0


def test_bm25_empty_index_returns_empty() -> None:
    idx = BM25Index()
    idx.fit()
    assert idx.search("Пушкин") == []


def test_bm25_unknown_term_returns_empty() -> None:
    idx = _build_bm25()
    assert idx.search("кваркваркваркварк") == []


def test_bm25_score_decreases_with_term_count() -> None:
    """Больше уникальных совпадений запроса => выше score."""
    idx = _build_bm25()
    one = idx.search("Пушкин", limit=1)[0].score
    two = idx.search("Пушкин Онегин", limit=1)[0].score
    assert two >= one


# ── TfidfEmbeddings + VectorIndex ────────────────────────────────────────


@pytest.mark.asyncio
async def test_vector_index_finds_semantic_neighbour() -> None:
    provider = TfidfEmbeddings()
    vec = VectorIndex(provider)
    await vec.fit(
        [
            ("d1", "Пушкин Онегин лишний человек"),
            ("d2", "Толстой Война и мир эпопея"),
            ("d3", "Чехов Вишнёвый сад комедия"),
        ]
    )
    hits = await vec.search("Пушкин Онегин", limit=2)
    assert hits[0].doc_id == "d1"


@pytest.mark.asyncio
async def test_vector_index_empty_query_returns_empty() -> None:
    provider = TfidfEmbeddings()
    vec = VectorIndex(provider)
    await vec.fit([("d1", "контент")])
    assert await vec.search("") == []


# ── Reranker ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_lexical_reranker_promotes_overlap() -> None:
    rer = LexicalReranker()
    # У "d1" больше пересечения биграмм с запросом.
    out = await rer.rerank(
        "Пушкин Онегин",
        candidates=[
            ("d2", "Толстой Война", 0.5),
            ("d1", "Пушкин Онегин лишний человек", 0.4),
        ],
        limit=2,
    )
    assert out[0].doc_id == "d1"


# ── _minmax ──────────────────────────────────────────────────────────────


def test_minmax_normalises_range() -> None:
    assert _minmax([1.0, 2.0, 3.0]) == [0.0, 0.5, 1.0]


def test_minmax_constant_values() -> None:
    assert _minmax([5.0, 5.0]) == [0.0, 0.0]


def test_minmax_empty() -> None:
    assert _minmax([]) == []


# ── Chunking ─────────────────────────────────────────────────────────────


def test_chunk_corpus_short_source_one_chunk() -> None:
    from app.corpus import Source

    s = Source(
        id="x",
        author="A",
        title="T",
        year=2000,
        genre="g",
        school_grade=9,
        ege_topics=["t1"],
        summary="короткий саммари",
        fragment="строка",
    )
    chunks = chunk_corpus([s])
    assert len(chunks) == 1
    assert chunks[0].chunk_id == "x#0"
    assert chunks[0].metadata["school_grade"] == 9


def test_chunk_corpus_long_source_splits() -> None:
    from app.corpus import Source

    long_text = " ".join(f"токен{i}" for i in range(2000))
    s = Source(
        id="long",
        author="A",
        title="T",
        year=2000,
        genre="g",
        school_grade=9,
        ege_topics=[],
        summary=long_text,
        fragment="",
    )
    chunks = chunk_corpus([s], chunk_size=500, overlap=80)
    assert len(chunks) > 1
    # все метаданные пробрасываются.
    assert all(c.metadata["genre"] == "g" for c in chunks)


# ── HybridSearch end-to-end ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_hybrid_search_blends_bm25_and_vector() -> None:
    from app.corpus import Source

    sources = [
        Source(id="d1", author="Пушкин", title="Онегин", year=1833, genre="роман", school_grade=9, ege_topics=["лишний человек"], summary="лишний человек", fragment="мой дядя"),
        Source(id="d2", author="Толстой", title="Война и мир", year=1869, genre="эпопея", school_grade=10, ege_topics=["1812"], summary="война и мир", fragment="не было величия"),
        Source(id="d3", author="Чехов", title="Вишнёвый сад", year=1903, genre="комедия", school_grade=10, ege_topics=["драма"], summary="вишнёвый сад", fragment="вся Россия наш сад"),
    ]
    chunks = chunk_corpus(sources)
    vec = VectorIndex(TfidfEmbeddings())
    hs = await HybridSearch.from_chunks(chunks, vector=vec, reranker=LexicalReranker(), threshold=0.0)
    results = await hs.search("Пушкин Онегин лишний человек", limit=3)
    assert results
    assert results[0].source_id == "d1"
    assert 0.0 <= results[0].score <= 1.5


@pytest.mark.asyncio
async def test_hybrid_search_threshold_filters_weak() -> None:
    from app.corpus import Source

    sources = [
        Source(id="d1", author="A", title="T", year=2000, genre="g", school_grade=9, ege_topics=[], summary="редкий узкоспециальный термин", fragment=""),
    ]
    chunks = chunk_corpus(sources)
    hs = await HybridSearch.from_chunks(chunks, vector=VectorIndex(TfidfEmbeddings()), threshold=0.99)
    # threshold почти 1.0 — выбрасываем всё.
    out = await hs.search("вообще другая тема", limit=3)
    assert out == []


@pytest.mark.asyncio
async def test_hybrid_search_empty_query() -> None:
    from app.corpus import Source

    chunks = chunk_corpus([Source(id="d1", author="A", title="T", year=2000, genre="g", school_grade=9, ege_topics=[], summary="x", fragment="")])
    hs = await HybridSearch.from_chunks(chunks, vector=VectorIndex(TfidfEmbeddings()))
    assert await hs.search("   ") == []
