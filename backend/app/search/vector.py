"""
Векторный индекс над `EmbeddingProvider`. Внутри — плотный/разреженный словарь;
поиск — линейный cosine. Для 50–500 документов это идеально, дальше — pgvector.
"""

from __future__ import annotations

from dataclasses import dataclass

from .embeddings import EmbeddingProvider, TfidfEmbeddings, cosine


@dataclass(frozen=True)
class VectorHit:
    doc_id: str
    score: float


class VectorIndex:
    def __init__(self, provider: EmbeddingProvider) -> None:
        self.provider = provider
        self.doc_ids: list[str] = []
        self.vectors: list[dict[str, float]] = []

    async def fit(self, docs: list[tuple[str, str]]) -> None:
        if isinstance(self.provider, TfidfEmbeddings):
            self.provider.fit([text for _, text in docs])
        self.doc_ids = []
        self.vectors = []
        for doc_id, text in docs:
            vec = await self.provider.embed_doc(text)
            self.doc_ids.append(doc_id)
            self.vectors.append(vec)

    async def search(self, query: str, *, limit: int = 50) -> list[VectorHit]:
        if not self.vectors:
            return []
        qvec = await self.provider.embed_query(query)
        if not qvec:
            return []
        scored = [(self.doc_ids[i], cosine(qvec, self.vectors[i])) for i in range(len(self.vectors))]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [VectorHit(doc_id=d, score=s) for d, s in scored[:limit] if s > 0]

    def __len__(self) -> int:
        return len(self.doc_ids)
