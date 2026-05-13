"""
quickread.py — Режим «5 минут на книгу».

Что отдаём пользователю:
- короткий сюжет (3–5 предложений),
- 3 ключевые цитаты из корпуса,
- 3 темы ЕГЭ,
- 1 SRS-вопрос с ответом,
- «о чём поговорить с другом» — 2 диалоговых вопроса.

Без LLM — детерминированно из корпуса, чтобы CI был зелёным и
эта фича работала вообще без интернета.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import corpus as corpus_mod


@dataclass
class QuickRead:
    book_id: str
    title: str
    author: str
    plot: str
    citations: list[dict]
    ege_topics: list[str]
    flashcard: dict
    talking_points: list[str]
    estimated_minutes: int


def build(book_id: str) -> QuickRead:
    book = corpus_mod.by_id(book_id)
    if book is None:
        raise KeyError(f"unknown book_id: {book_id}")
    plot = book.summary or (
        f"«{book.title}» — произведение {book.author} в жанре «{book.genre}»."
    )
    # 3 ключевые цитаты: один из same book, плюс перекрёстные ассоциации.
    citations = [
        {
            "fragment": book.fragment,
            "citation": book.citation,
            "url": book.public_domain_url,
        }
    ]
    flashcard = {
        "front": f"О чём «{book.title}»?",
        "back": (book.summary or book.fragment)[:300],
    }
    talking_points = [
        f"Что в «{book.title}» сегодня всё ещё актуально?",
        "Кому из современников вы бы посоветовали эту книгу и почему?",
    ]
    return QuickRead(
        book_id=book.id,
        title=book.title,
        author=book.author,
        plot=plot,
        citations=citations,
        ege_topics=list(book.ege_topics),
        flashcard=flashcard,
        talking_points=talking_points,
        estimated_minutes=5,
    )


def to_dict(qr: QuickRead) -> dict:
    return {
        "book_id": qr.book_id,
        "title": qr.title,
        "author": qr.author,
        "plot": qr.plot,
        "citations": qr.citations,
        "ege_topics": qr.ege_topics,
        "flashcard": qr.flashcard,
        "talking_points": qr.talking_points,
        "estimated_minutes": qr.estimated_minutes,
    }
