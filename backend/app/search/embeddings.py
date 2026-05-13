"""
Эмбеддинги для векторного поиска.

* `EmbeddingProvider` — async-контракт.
* `TfidfEmbeddings` — детерминированная реализация без сети, для CI/демо. Даёт
                      разумные cosine-метрики на корпусе из ~30 документов
                      благодаря IDF-взвешиванию.
* `YandexEmbeddings` — production-адаптер на Yandex Foundation Models
                      (`text-search-doc/v1` и `text-search-query/v1`).
                      В CI не используется, потому что требует ключей.

Через ENV переключение:
    HYBRID_VECTOR_PROVIDER=yandex|tfidf  (default: tfidf)
"""

from __future__ import annotations

import math
import os
from abc import ABC, abstractmethod
from collections import Counter

import httpx

from .tokenizer import tokenize


class EmbeddingProvider(ABC):
    """Async-контракт. Возвращает векторы в виде словарей {term/dim: weight}."""

    name: str = "abstract"

    @abstractmethod
    async def is_configured(self) -> bool: ...

    @abstractmethod
    async def embed_doc(self, text: str) -> dict[str, float]: ...

    @abstractmethod
    async def embed_query(self, text: str) -> dict[str, float]: ...


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    # перебираем по меньшему словарю — быстрее.
    if len(b) < len(a):
        a, b = b, a
    num = 0.0
    for k, va in a.items():
        vb = b.get(k)
        if vb is not None:
            num += va * vb
    if num == 0.0:
        return 0.0
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return num / (na * nb)


class TfidfEmbeddings(EmbeddingProvider):
    """Sparse TF-IDF embeddings.

    Корпус-зависимая IDF собирается на этапе `fit()`. Пара doc/query режимов
    выбирает ту же модель, что и Yandex text-search-* (асимметрия не нужна).
    """

    name = "tfidf"

    def __init__(self) -> None:
        self.df: Counter[str] = Counter()
        self.n: int = 0

    def fit(self, docs: list[str]) -> None:
        self.df.clear()
        for doc in docs:
            for term in set(tokenize(doc)):
                self.df[term] += 1
        self.n = len(docs)

    def _vec(self, text: str) -> dict[str, float]:
        if self.n == 0:
            return {}
        toks = tokenize(text)
        if not toks:
            return {}
        tf = Counter(toks)
        out: dict[str, float] = {}
        max_tf = max(tf.values())
        for term, f in tf.items():
            df = self.df.get(term, 0)
            if df == 0:
                # OOV-термины из запроса — игнорируем (они не помогают cosine).
                continue
            tf_norm = 0.5 + 0.5 * (f / max_tf)
            idf = math.log((1 + self.n) / (1 + df)) + 1.0
            out[term] = tf_norm * idf
        return out

    async def is_configured(self) -> bool:
        return self.n > 0

    async def embed_doc(self, text: str) -> dict[str, float]:
        return self._vec(text)

    async def embed_query(self, text: str) -> dict[str, float]:
        return self._vec(text)


class YandexEmbeddings(EmbeddingProvider):
    """Yandex Foundation Models — text-search-doc / text-search-query.

    Документация: https://yandex.cloud/ru/docs/foundation-models/concepts/embeddings.
    Возвращаемые векторы плотные (256-мерные). Для совместимости с cosine() мы
    переводим их в словарь {idx: weight}.
    """

    name = "yandex"

    DOC_MODEL_TPL = "emb://{folder_id}/text-search-doc/latest"
    QUERY_MODEL_TPL = "emb://{folder_id}/text-search-query/latest"
    ENDPOINT = "https://llm.api.cloud.yandex.net/foundationModels/v1/textEmbedding"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        folder_id: str | None = None,
        timeout: float = 12.0,
    ) -> None:
        self.api_key = api_key or os.environ.get("YANDEX_GPT_API_KEY", "")
        self.folder_id = folder_id or os.environ.get("YANDEX_GPT_FOLDER_ID", "")
        self.timeout = timeout

    async def is_configured(self) -> bool:
        return bool(self.api_key and self.folder_id)

    async def _call(self, model: str, text: str) -> dict[str, float]:
        if not await self.is_configured():
            raise RuntimeError("YandexEmbeddings not configured")
        headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "Content-Type": "application/json",
            "x-folder-id": self.folder_id,
        }
        body = {"modelUri": model, "text": text[:8000]}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(self.ENDPOINT, json=body, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        embedding = data.get("embedding", [])
        return {str(i): float(v) for i, v in enumerate(embedding)}

    async def embed_doc(self, text: str) -> dict[str, float]:
        return await self._call(self.DOC_MODEL_TPL.format(folder_id=self.folder_id), text)

    async def embed_query(self, text: str) -> dict[str, float]:
        return await self._call(self.QUERY_MODEL_TPL.format(folder_id=self.folder_id), text)


def select_provider() -> EmbeddingProvider:
    """Выбор провайдера по ENV. По умолчанию tfidf, чтобы CI был самодостаточным."""
    name = os.environ.get("HYBRID_VECTOR_PROVIDER", "tfidf").lower().strip()
    if name == "yandex":
        return YandexEmbeddings()
    return TfidfEmbeddings()
