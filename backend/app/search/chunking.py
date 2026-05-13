"""
Разбиение source-документов на пассажи 400–600 токенов с overlap 80.

Цель — увеличить precision@5: подсветить именно главу/абзац, а не книгу целиком.
В демо-корпусе у нас короткие фрагменты, поэтому в большинстве случаев один
Source = один Chunk; функция всё равно нужна для обработки длинных текстов
(например, при подключении полнотекстовых произведений из public domain).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .tokenizer import tokenize

if TYPE_CHECKING:
    from ..corpus import Source


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    source_id: str
    title: str
    text: str
    position: int
    metadata: dict


def _split_tokens(tokens: list[str], chunk_size: int, overlap: int) -> list[list[str]]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be in [0, chunk_size)")
    out: list[list[str]] = []
    step = max(1, chunk_size - overlap)
    if not tokens:
        return out
    i = 0
    while i < len(tokens):
        out.append(tokens[i : i + chunk_size])
        if i + chunk_size >= len(tokens):
            break
        i += step
    return out


def _composite_text(source: Source) -> str:
    """Собираем из Source единый текст, в порядке полезности для retrieval."""
    parts = [
        source.title,
        source.author,
        source.genre,
        source.summary,
        source.fragment,
        " ".join(source.ege_topics),
        f"класс {source.school_grade}",
        f"год {source.year}",
    ]
    return ". ".join(p for p in parts if p)


def chunk_corpus(
    sources: list[Source],
    *,
    chunk_size: int = 500,
    overlap: int = 80,
) -> list[Chunk]:
    """Возвращает список Chunk. У коротких Source — один чанк."""
    chunks: list[Chunk] = []
    for s in sources:
        text = _composite_text(s)
        toks = tokenize(text, drop_stop=False, min_len=1)
        if len(toks) <= chunk_size:
            chunks.append(
                Chunk(
                    chunk_id=f"{s.id}#0",
                    source_id=s.id,
                    title=f"{s.author}. {s.title}",
                    text=text,
                    position=0,
                    metadata={
                        "school_grade": s.school_grade,
                        "ege_topics": list(s.ege_topics),
                        "pushkin_card": s.pushkin_card,
                        "genre": s.genre,
                        "year": s.year,
                    },
                )
            )
            continue
        windows = _split_tokens(toks, chunk_size, overlap)
        for i, win in enumerate(windows):
            chunks.append(
                Chunk(
                    chunk_id=f"{s.id}#{i}",
                    source_id=s.id,
                    title=f"{s.author}. {s.title}",
                    text=" ".join(win),
                    position=i,
                    metadata={
                        "school_grade": s.school_grade,
                        "ege_topics": list(s.ege_topics),
                        "pushkin_card": s.pushkin_card,
                        "genre": s.genre,
                        "year": s.year,
                    },
                )
            )
    return chunks
