"""
Токенизатор и нормализатор для русского корпуса ЧитАИ.

Цель — быть быстрым (для BM25 на 50–500k чанков), детерминированным (CI/тесты)
и предсказуемым на смеси русского и редких латинских терминов (литературоведение).

Морфология НЕ выполняется здесь (стемминг/лемматизация — отдельный плагин,
который мы можем включить через `app.search.lemmatize` поверх токенизатора).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

_TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9][A-Za-zА-Яа-яЁё0-9-]*", re.UNICODE)
_HYPHEN_RE = re.compile(r"-+")


# Минимальный список русских и английских стоп-слов: предлоги, союзы, частицы.
# Отдельный модуль на ~500 слов был бы избыточен для демо; при необходимости
# заменяется на pymorphy3.lemmatizer + nltk.corpus.stopwords без правок API.
RUSSIAN_STOP: frozenset[str] = frozenset(
    {
        "а",
        "без",
        "более",
        "больше",
        "будет",
        "будто",
        "бы",
        "был",
        "была",
        "были",
        "было",
        "быть",
        "в",
        "вам",
        "вас",
        "ведь",
        "вне",
        "во",
        "вот",
        "впрочем",
        "все",
        "всегда",
        "всех",
        "всем",
        "вы",
        "где",
        "да",
        "даже",
        "для",
        "до",
        "его",
        "ее",
        "её",
        "ей",
        "ему",
        "если",
        "есть",
        "ещё",
        "еще",
        "же",
        "за",
        "и",
        "из",
        "или",
        "им",
        "их",
        "к",
        "как",
        "какая",
        "какой",
        "когда",
        "конечно",
        "которая",
        "которые",
        "который",
        "кто",
        "ли",
        "либо",
        "между",
        "меня",
        "мне",
        "мы",
        "на",
        "над",
        "надо",
        "нам",
        "нас",
        "не",
        "него",
        "неё",
        "нее",
        "них",
        "но",
        "ну",
        "о",
        "об",
        "однако",
        "он",
        "она",
        "они",
        "оно",
        "от",
        "очень",
        "по",
        "под",
        "после",
        "при",
        "про",
        "разве",
        "с",
        "сам",
        "свое",
        "своё",
        "свои",
        "свою",
        "себя",
        "сейчас",
        "со",
        "так",
        "также",
        "такие",
        "такой",
        "там",
        "те",
        "тебя",
        "тем",
        "теперь",
        "то",
        "тогда",
        "тоже",
        "только",
        "том",
        "тот",
        "ты",
        "у",
        "уж",
        "уже",
        "хоть",
        "хотя",
        "чего",
        "чей",
        "чем",
        "что",
        "чтобы",
        "чуть",
        "эта",
        "эти",
        "это",
        "этот",
        "я",
        "the",
        "a",
        "an",
        "and",
        "or",
        "of",
        "in",
        "on",
        "to",
        "for",
        "is",
        "are",
        "was",
        "were",
        "be",
        "by",
        "with",
        "as",
        "at",
        "from",
        "this",
        "that",
        "it",
    }
)


def normalize(text: str) -> str:
    """NFKC + lower + ё → е, чтобы избежать дублей и дрейфа индексов между ОС."""
    text = unicodedata.normalize("NFKC", text)
    text = text.lower().replace("ё", "е")
    return text


def tokenize(
    text: str, *, drop_stop: bool = True, min_len: int = 2, stem: bool = True
) -> list[str]:
    """Токенизация. Возвращает список токенов в порядке появления.

    При `stem=True` применяет лёгкий русский стеммер, чтобы запросы
    в косвенных падежах матчили леммы корпуса. Стоп-слова отбрасываются
    ДО стемминга — чтобы не получить «пуст» из «пусть» и наоборот.
    """
    text = normalize(text)
    raw = _TOKEN_RE.findall(text)
    out: list[str] = []
    # импорт здесь — избегаем циклов и платим один раз на модуль.
    if stem:
        from .stemmer import stem as _stem
    for tok in raw:
        tok = _HYPHEN_RE.sub("-", tok).strip("-")
        if not tok:
            continue
        if len(tok) < min_len:
            continue
        if drop_stop and tok in RUSSIAN_STOP:
            continue
        if stem:
            tok = _stem(tok)
        out.append(tok)
    return out


def tokens_set(text: str) -> set[str]:
    return set(tokenize(text))


def jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    sa = set(a)
    sb = set(b)
    if not sa and not sb:
        return 0.0
    union = sa | sb
    if not union:
        return 0.0
    return len(sa & sb) / len(union)
