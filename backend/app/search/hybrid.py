"""
Финальный пайплайн `BM25 ∪ Vector → Rerank → threshold`.

* Линейное смешивание BM25 и cosine с нормализацией min-max в пределах батча.
* Reranker идёт поверх объединённого top-N (по умолчанию 30).
* `threshold` отсекает шум; на демо-корпусе из 22 источников оптимум ≈0.18,
  на больших корпусах его задаёт A3-бенчмарк.

Все параметры — настраиваемые, читаются из ENV/конструктора. Это позволяет
менять behavior без переписывания пайплайна (например, в Streaming-режиме
или в B2G-инсталляции с строгим threshold).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .bm25 import BM25Index
from .chunking import Chunk
from .reranker import Reranker
from .vector import VectorIndex


def _minmax(values: list[float]) -> list[float]:
    if not values:
        return []
    lo = min(values)
    hi = max(values)
    if hi - lo < 1e-12:
        return [0.0 for _ in values]
    return [(v - lo) / (hi - lo) for v in values]


@dataclass(frozen=True)
class HybridResult:
    chunk_id: str
    source_id: str
    title: str
    text: str
    score: float
    bm25_score: float
    vector_score: float
    rerank_score: float
    metadata: dict


class HybridSearch:
    def __init__(
        self,
        chunks: list[Chunk],
        bm25: BM25Index,
        vector: VectorIndex | None,
        reranker: Reranker | None = None,
        *,
        bm25_weight: float = 0.55,
        vector_weight: float = 0.45,
        threshold: float | None = None,
        candidate_pool: int = 30,
    ) -> None:
        self.chunks = {c.chunk_id: c for c in chunks}
        self.bm25 = bm25
        self.vector = vector
        self.reranker = reranker
        self.bm25_weight = bm25_weight
        self.vector_weight = vector_weight
        if threshold is None:
            threshold = float(os.environ.get("HYBRID_THRESHOLD", "0.0"))
        self.threshold = threshold
        self.candidate_pool = candidate_pool

    @classmethod
    async def from_chunks(
        cls,
        chunks: list[Chunk],
        *,
        vector: VectorIndex | None = None,
        reranker: Reranker | None = None,
        bm25_weight: float = 0.55,
        vector_weight: float = 0.45,
        threshold: float | None = None,
    ) -> HybridSearch:
        bm25 = BM25Index()
        for c in chunks:
            bm25.add(c.chunk_id, c.text)
        bm25.fit()
        if vector is not None:
            await vector.fit([(c.chunk_id, c.text) for c in chunks])
        return cls(
            chunks=chunks,
            bm25=bm25,
            vector=vector,
            reranker=reranker,
            bm25_weight=bm25_weight,
            vector_weight=vector_weight,
            threshold=threshold,
        )

    async def search(self, query: str, *, limit: int = 5) -> list[HybridResult]:
        if not query.strip() or not self.chunks:
            return []
        bm25_hits = self.bm25.search(query, limit=self.candidate_pool)
        vec_hits = []
        if self.vector is not None and len(self.vector) > 0:
            vec_hits = await self.vector.search(query, limit=self.candidate_pool)

        # объединяем кандидатов
        bm25_map = {h.doc_id: h.score for h in bm25_hits}
        vec_map = {h.doc_id: h.score for h in vec_hits}
        candidate_ids = list({*bm25_map.keys(), *vec_map.keys()})
        if not candidate_ids:
            return []

        # min-max нормализация в пределах батча — стабилизирует смешение разных шкал.
        bm25_norms = _minmax([bm25_map.get(cid, 0.0) for cid in candidate_ids])
        vec_norms = _minmax([vec_map.get(cid, 0.0) for cid in candidate_ids])
        combined: list[tuple[str, float, float, float]] = []  # (cid, mixed, bm25_n, vec_n)
        for i, cid in enumerate(candidate_ids):
            mixed = self.bm25_weight * bm25_norms[i] + self.vector_weight * vec_norms[i]
            combined.append((cid, mixed, bm25_norms[i], vec_norms[i]))
        combined.sort(key=lambda x: x[1], reverse=True)

        # rerank top-N
        top = combined[: self.candidate_pool]
        rerank_input = [(cid, self.chunks[cid].text, mixed) for cid, mixed, _, _ in top]
        if self.reranker is not None:
            reranked = await self.reranker.rerank(query, rerank_input, limit=self.candidate_pool)
            score_map: dict[str, tuple[float, float]] = {
                r.doc_id: (r.score, r.base_score) for r in reranked
            }
            # сохраняем порядок из reranker
            ordered_ids = [r.doc_id for r in reranked]
        else:
            score_map = {cid: (mixed, mixed) for cid, mixed, _, _ in top}
            ordered_ids = [cid for cid, _, _, _ in top]

        per_id = {cid: (bm25, vec) for cid, _, bm25, vec in top}

        out: list[HybridResult] = []
        for cid in ordered_ids:
            score, base = score_map[cid]
            if score < self.threshold:
                continue
            chunk = self.chunks[cid]
            bm25_n, vec_n = per_id.get(cid, (0.0, 0.0))
            out.append(
                HybridResult(
                    chunk_id=chunk.chunk_id,
                    source_id=chunk.source_id,
                    title=chunk.title,
                    text=chunk.text,
                    score=score,
                    bm25_score=bm25_n,
                    vector_score=vec_n,
                    rerank_score=score if self.reranker else base,
                    metadata=chunk.metadata,
                )
            )
            if len(out) >= limit:
                break
        return out
