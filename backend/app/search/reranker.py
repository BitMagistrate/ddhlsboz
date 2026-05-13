"""
Кросс-энкодер для переранжирования top-N кандидатов.

* `LexicalReranker`  — детерминированный fallback на основе BM25-фич + Jaccard +
                       совпадения биграмм. Не требует сети, годится для CI.
                       При желании поверх можно поставить ансамбль с lex+vec score.
* `RemoteReranker`   — для production: pluggable HTTP-вызов к bge-reranker-v2-m3
                       (Yandex Cloud Foundation Models или внутренний инференс).
                       В CI не дёргается, потому что требует ключей.

Контракт:
    rerank(query, candidates, *, limit) -> list[RerankedHit]

`candidates` — кортежи (doc_id, текст, base_score). На выходе — отсортированные
по новой релевантности кандидаты.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

from .tokenizer import tokenize


@dataclass(frozen=True)
class RerankedHit:
    doc_id: str
    score: float
    base_score: float


class Reranker(ABC):
    name: str = "abstract"

    @abstractmethod
    async def rerank(
        self,
        query: str,
        candidates: list[tuple[str, str, float]],
        *,
        limit: int = 10,
    ) -> list[RerankedHit]: ...


class LexicalReranker(Reranker):
    """Без сети: комбинирует Jaccard, биграмм-overlap и базовый score."""

    name = "lexical"

    @staticmethod
    def _bigrams(tokens: list[str]) -> set[tuple[str, str]]:
        return set(zip(tokens, tokens[1:], strict=False))

    @classmethod
    def _features(cls, q_tokens: list[str], d_tokens: list[str]) -> tuple[float, float]:
        if not q_tokens or not d_tokens:
            return 0.0, 0.0
        qs = set(q_tokens)
        ds = set(d_tokens)
        jacc = len(qs & ds) / len(qs | ds) if (qs | ds) else 0.0
        qb = cls._bigrams(q_tokens)
        db = cls._bigrams(d_tokens)
        big = len(qb & db) / len(qb | db) if (qb | db) else 0.0
        return jacc, big

    async def rerank(
        self,
        query: str,
        candidates: list[tuple[str, str, float]],
        *,
        limit: int = 10,
    ) -> list[RerankedHit]:
        q_tokens = tokenize(query)
        out: list[RerankedHit] = []
        for doc_id, text, base in candidates:
            d_tokens = tokenize(text)
            jacc, big = self._features(q_tokens, d_tokens)
            # детерминированная линейная комбинация: 50% базовый score + 30% jaccard + 20% bigrams.
            score = 0.5 * base + 0.3 * jacc + 0.2 * big
            out.append(RerankedHit(doc_id=doc_id, score=score, base_score=base))
        out.sort(key=lambda h: h.score, reverse=True)
        return out[:limit]


class RemoteReranker(Reranker):
    """Hook для production: bge-reranker-v2-m3 через HTTP API.

    Тестируется через httpx mock в test_reranker.py — ключи не требуются для CI.
    """

    name = "remote"

    def __init__(
        self,
        endpoint: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        *,
        timeout: float = 12.0,
    ) -> None:
        self.endpoint = endpoint or os.environ.get(
            "RERANKER_ENDPOINT",
            "https://llm.api.cloud.yandex.net/foundationModels/v1/rerank",
        )
        self.api_key = api_key or os.environ.get(
            "RERANKER_API_KEY", os.environ.get("YANDEX_GPT_API_KEY", "")
        )
        self.model = model or os.environ.get("RERANKER_MODEL", "bge-reranker-v2-m3")
        self.timeout = timeout

    async def is_configured(self) -> bool:
        return bool(self.api_key and self.endpoint)

    async def rerank(
        self,
        query: str,
        candidates: list[tuple[str, str, float]],
        *,
        limit: int = 10,
    ) -> list[RerankedHit]:
        if not await self.is_configured() or not candidates:
            # graceful: если ключей нет — отдаём кандидатов как есть, не ломаем пайплайн.
            return [RerankedHit(doc_id=d, score=s, base_score=s) for d, _, s in candidates[:limit]]
        body = {
            "model": self.model,
            "query": query,
            "passages": [{"id": did, "text": text} for did, text, _ in candidates],
        }
        headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(self.endpoint, json=body, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        scored = data.get("scores") or data.get("results") or []
        # На выходе ожидается список {id: ..., score: ...} в любом порядке.
        score_map = {item.get("id"): float(item.get("score", 0)) for item in scored}
        out: list[RerankedHit] = []
        for did, _, base in candidates:
            s = score_map.get(did, base)
            out.append(RerankedHit(doc_id=did, score=s, base_score=base))
        out.sort(key=lambda h: h.score, reverse=True)
        return out[:limit]


def select_reranker() -> Reranker | None:
    name = os.environ.get("HYBRID_RERANKER", "lexical").lower().strip()
    if name == "remote":
        return RemoteReranker()
    if name == "none":
        return None
    return LexicalReranker()
