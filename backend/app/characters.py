"""
characters.py — «Спроси Раскольникова»: ролевой режим с RAG-якорем.

Идея
----
Пользователь выбирает героя (Раскольников / Базаров / Чацкий / Татьяна Ларина /
Печорин) и задаёт ему вопросы. Герой отвечает ТОЛЬКО на основе цитат и
парафразов из своего произведения. Если в тексте нет ответа — герой
честно говорит «в романе об этом не сказано».

Этическая граница (важно)
-------------------------
Это не «фанфик-генератор». Это RAG-якорь:
- system prompt запрещает героическую отсебятину,
- LLM-ответ проходит через `_force_citation`: если в нём нет
  цитаты из корпуса, на выходе приклеивается дисклеймер «вне канона».
- Полный лог в audit (см. `app/audit.py`).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from . import corpus as corpus_mod
from . import retrieval as retrieval_mod


@dataclass(frozen=True)
class CharacterProfile:
    slug: str
    name: str
    book_id: str
    author: str
    book_title: str
    persona_summary: str
    typical_themes: tuple[str, ...]
    out_of_canon_phrase: str = "В романе об этом не сказано — могу опираться только на текст."


CHARACTERS: dict[str, CharacterProfile] = {
    "raskolnikov": CharacterProfile(
        slug="raskolnikov",
        name="Родион Раскольников",
        book_id="dostoevsky_pn",
        author="Ф. М. Достоевский",
        book_title="Преступление и наказание",
        persona_summary=(
            "Молодой студент, бывший юрист. Совершает преступление, "
            "движимый теорией о «праве сильных», и долго мучается совестью."
        ),
        typical_themes=("совесть", "теория", "социальная несправедливость", "вера"),
    ),
    "bazarov": CharacterProfile(
        slug="bazarov",
        name="Евгений Базаров",
        book_id="turgenev_otcy",
        author="И. С. Тургенев",
        book_title="Отцы и дети",
        persona_summary=(
            "Молодой нигилист, врач, отрицающий искусство и романтику. "
            "Сталкивается с любовью к Анне Сергеевне и переоценивает свои взгляды."
        ),
        typical_themes=("нигилизм", "наука", "поколения", "любовь"),
    ),
    "chatsky": CharacterProfile(
        slug="chatsky",
        name="Александр Чацкий",
        book_id="griboedov_gore",
        author="А. С. Грибоедов",
        book_title="Горе от ума",
        persona_summary=(
            "Молодой дворянин, вернувшийся из-за границы. Высмеивает "
            "московское общество и оказывается одинок в своих идеалах."
        ),
        typical_themes=("ум", "общество", "свобода", "карьера"),
    ),
    "tatiana": CharacterProfile(
        slug="tatiana",
        name="Татьяна Ларина",
        book_id="pushkin_onegin",
        author="А. С. Пушкин",
        book_title="Евгений Онегин",
        persona_summary=(
            "Тихая, мечтательная девушка из деревни. Любит читать, искренне "
            "пишет письмо Онегину, позднее — княгиня, верная своему долгу."
        ),
        typical_themes=("любовь", "долг", "честь", "природа"),
    ),
    "pechorin": CharacterProfile(
        slug="pechorin",
        name="Григорий Печорин",
        book_id="lermontov_geroi",
        author="М. Ю. Лермонтов",
        book_title="Герой нашего времени",
        persona_summary=(
            "Молодой офицер, циник и эгоист, страдающий «лишним человек»: "
            "разочарованный в обществе, ищущий смысл в риске и любви."
        ),
        typical_themes=("разочарование", "судьба", "одиночество", "честь"),
    ),
}


@dataclass
class CharacterAnswer:
    character: str
    question: str
    answer: str
    citations: list[dict]
    grounded: bool
    book: dict


def list_characters() -> list[dict]:
    return [
        {
            "slug": c.slug,
            "name": c.name,
            "book": c.book_title,
            "author": c.author,
            "persona": c.persona_summary,
            "themes": list(c.typical_themes),
        }
        for c in CHARACTERS.values()
    ]


def get_character(slug: str) -> CharacterProfile | None:
    return CHARACTERS.get(slug.strip().lower())


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _force_citation(
    raw_answer: str,
    sources: Iterable[corpus_mod.Source],
    character: CharacterProfile,
) -> tuple[str, bool]:
    """Если ответ LLM не содержит ни одной цитаты из найденных источников,
    помечаем `grounded=False` и добавляем дисклеймер.
    """
    answer_norm = _normalize(raw_answer)
    grounded = False
    for src in sources:
        snippet = _normalize(src.fragment)[:200]
        if snippet and (snippet[:60] in answer_norm or snippet[:40] in answer_norm):
            grounded = True
            break
    if grounded:
        return raw_answer, True
    return (
        f"{character.out_of_canon_phrase}\n\n"
        f"Что есть в тексте «{character.book_title}» по этому вопросу:\n"
        + "\n".join(f"• {src.fragment}" for src in list(sources)[:2])
    ), False


async def ask_character(slug: str, question: str, limit: int = 4) -> CharacterAnswer:
    """
    RAG over single book → ответ героя.

    Реализация работает без живого LLM: достаём релевантные фрагменты
    из произведения и собираем структурированный ответ. Когда подключён
    LLM-роутер (PR12+), он добавляется ниже как этап «pretty-print», но
    канон проверяется через `_force_citation`.
    """
    character = get_character(slug)
    if character is None:
        raise KeyError(f"unknown character: {slug}")

    book = corpus_mod.by_id(character.book_id)
    sources = await retrieval_mod.hybrid_search_sources(question, limit=limit)
    book_sources = [s for s in sources if s.id == character.book_id] or (
        [book] if book is not None else []
    )

    # Формируем «реплику героя» детерминированно — без LLM, чтобы тесты
    # были устойчивы. LLM-обвес добавляется в основном слое, если ключи есть.
    fragments_text = "\n".join(f"• {s.fragment}" for s in book_sources[:2])
    raw_answer = (
        f"{character.name}: «{book_sources[0].fragment}» — это близко к тому, "
        f"что вы спрашиваете. "
        + (f"Также: {book_sources[1].fragment}" if len(book_sources) >= 2 else "")
    ) if book_sources else character.out_of_canon_phrase

    answer, grounded = _force_citation(raw_answer, book_sources, character)
    citations = [
        {
            "source_id": s.id,
            "fragment": s.fragment,
            "citation": s.citation,
            "url": s.public_domain_url,
        }
        for s in book_sources[:3]
    ]
    return CharacterAnswer(
        character=character.slug,
        question=question,
        answer=answer if not grounded else raw_answer + "\n\nИсточники:\n" + fragments_text,
        citations=citations,
        grounded=grounded,
        book={
            "id": book.id if book else character.book_id,
            "title": character.book_title,
            "author": character.author,
        },
    )
