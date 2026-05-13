"""
Глобальный singleton гибридного поисковика поверх корпуса ЧитАИ.

Создаётся лениво при первом обращении (или при startup-хуке FastAPI), один
индекс на процесс. В тестах можно дернуть `reset()` чтобы пересобрать с
другими параметрами/корпусом.

Поведение детерминировано без сети: TF-IDF embeddings + lexical reranker.
В production переключается через ENV (HYBRID_VECTOR_PROVIDER, HYBRID_RERANKER).
"""

from __future__ import annotations

import asyncio
import logging
import os

from . import corpus as corpus_mod
from .corpus import Source
from .search import (
    HybridResult,
    HybridSearch,
    Reranker,
    VectorIndex,
)
from .search.embeddings import select_provider
from .search.reranker import select_reranker

logger = logging.getLogger(__name__)


class HybridIndex:
    def __init__(self) -> None:
        self._search: HybridSearch | None = None
        self._lock = asyncio.Lock()
        self._sources: list[Source] = []

    async def build(self, sources: list[Source] | None = None) -> HybridSearch:
        async with self._lock:
            if sources is None:
                sources = corpus_mod.CORPUS
            self._sources = list(sources)
            from .search.chunking import chunk_corpus

            chunks = chunk_corpus(self._sources)
            provider = select_provider()
            vector = VectorIndex(provider)
            reranker: Reranker | None = select_reranker()
            self._search = await HybridSearch.from_chunks(
                chunks,
                vector=vector,
                reranker=reranker,
                threshold=float(os.environ.get("HYBRID_THRESHOLD", "0.0")),
            )
            logger.info(
                "hybrid index built: chunks=%d, vector=%s, reranker=%s",
                len(chunks),
                provider.name,
                reranker.name if reranker else "none",
            )
            return self._search

    async def search(self, query: str, *, limit: int = 5) -> list[HybridResult]:
        if self._search is None:
            await self.build()
        assert self._search is not None
        return await self._search.search(query, limit=limit)

    def reset(self) -> None:
        self._search = None
        self._sources = []


_INDEX = HybridIndex()


def get_index() -> HybridIndex:
    return _INDEX


async def hybrid_search_sources(query: str, *, limit: int = 5) -> list[Source]:
    """Поиск через гибридный пайплайн с маппингом chunk → Source.

    При совпадении нескольких chunks одного source — берём максимум по score
    и сохраняем порядок появления (стабильность важна для UI и кэшей).
    """
    hits = await _INDEX.search(query, limit=limit * 3)
    seen: dict[str, Source] = {}
    for h in hits:
        if h.source_id in seen:
            continue
        s = corpus_mod.by_id(h.source_id)
        if s is None:
            continue
        seen[h.source_id] = s
        if len(seen) >= limit:
            break
    return list(seen.values())
