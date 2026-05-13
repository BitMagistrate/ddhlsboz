"""
Okapi BM25 на чистом Python.

Вычислительно: 50k документов средней длины 200 токенов индексируются за <1s,
поиск top-50 — единицы миллисекунд. Этого с запасом хватает для демо-корпуса
ЧитАИ и для единичных регрессионных бенчмарков. В production индекс кладётся
в Postgres+pg_trgm/pgvector или OpenSearch — но контракт `BM25Index` не меняется.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

from .tokenizer import tokenize


@dataclass(frozen=True)
class BM25Hit:
    doc_id: str
    score: float


class BM25Index:
    """Okapi BM25 с настраиваемыми k1, b. По умолчанию k1=1.5, b=0.75 — стандарт."""

    def __init__(self, *, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.doc_ids: list[str] = []
        self.doc_lengths: list[int] = []
        self.term_freqs: list[Counter[str]] = []
        self.doc_freq: Counter[str] = Counter()
        self.avgdl: float = 0.0
        self.n: int = 0

    def add(self, doc_id: str, text: str) -> None:
        toks = tokenize(text)
        tf = Counter(toks)
        self.doc_ids.append(doc_id)
        self.term_freqs.append(tf)
        self.doc_lengths.append(len(toks))
        for term in tf:
            self.doc_freq[term] += 1

    def fit(self) -> None:
        self.n = len(self.doc_ids)
        if self.n == 0:
            self.avgdl = 0.0
            return
        self.avgdl = sum(self.doc_lengths) / self.n

    def _idf(self, term: str) -> float:
        df = self.doc_freq.get(term, 0)
        if df == 0:
            return 0.0
        # Robertson/Spärck Jones IDF c +0.5 сглаживанием — стандартная BM25 формула.
        return math.log(1 + (self.n - df + 0.5) / (df + 0.5))

    def search(self, query: str, *, limit: int = 50) -> list[BM25Hit]:
        if self.n == 0:
            return []
        q_terms = tokenize(query)
        if not q_terms:
            return []
        scores: list[tuple[str, float]] = []
        # уникальные термы запроса (повторение в запросе мало что меняет в RAG)
        unique_terms = list(dict.fromkeys(q_terms))
        idfs = {t: self._idf(t) for t in unique_terms}
        for i, tf in enumerate(self.term_freqs):
            dl = self.doc_lengths[i]
            if dl == 0:
                continue
            score = 0.0
            denom_norm = self.k1 * (1 - self.b + self.b * dl / (self.avgdl or 1.0))
            for term in unique_terms:
                f = tf.get(term, 0)
                if not f:
                    continue
                idf = idfs[term]
                if idf <= 0:
                    continue
                score += idf * (f * (self.k1 + 1)) / (f + denom_norm)
            if score > 0:
                scores.append((self.doc_ids[i], score))
        scores.sort(key=lambda x: x[1], reverse=True)
        return [BM25Hit(doc_id=d, score=s) for d, s in scores[:limit]]

    def __len__(self) -> int:
        return self.n
