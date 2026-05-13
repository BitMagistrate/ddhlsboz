"""
Гибридный поисковик ЧитАИ: BM25 + векторный поиск + reranker.

Архитектура:

* `tokenize`    — токенизация и нормализация (русские стоп-слова, нижний регистр).
* `BM25Index`   — Okapi BM25 на чистом Python, без внешних зависимостей.
* `VectorIndex` — TF-IDF cosine как baseline-эмбеддинг + hook для боевого
                  Yandex Embeddings / FRIDA / E5-small, чтобы CI не зависел от сети.
* `LexicalReranker` / `RemoteReranker` — переоценка top-N кандидатов;
                  remote-вариант умеет ходить в bge-reranker-v2-m3 через
                  Yandex Cloud Foundation Models, lex — детерминированный fallback.
* `HybridSearch` — финальный пайплайн `BM25 ∪ Vector → Rerank → threshold`.

Все модули — pluggable. В production они переключаются через ENV без переписывания кода:
    HYBRID_VECTOR_PROVIDER=yandex|tfidf
    HYBRID_RERANKER=remote|lexical|none
    HYBRID_THRESHOLD=0.18
"""

from .bm25 import BM25Index
from .chunking import Chunk, chunk_corpus
from .embeddings import EmbeddingProvider, TfidfEmbeddings, YandexEmbeddings
from .hybrid import HybridResult, HybridSearch
from .reranker import LexicalReranker, RemoteReranker, Reranker
from .tokenizer import RUSSIAN_STOP, normalize, tokenize
from .vector import VectorIndex

__all__ = [
    "BM25Index",
    "Chunk",
    "chunk_corpus",
    "EmbeddingProvider",
    "HybridResult",
    "HybridSearch",
    "LexicalReranker",
    "RemoteReranker",
    "Reranker",
    "RUSSIAN_STOP",
    "TfidfEmbeddings",
    "VectorIndex",
    "YandexEmbeddings",
    "normalize",
    "tokenize",
]
