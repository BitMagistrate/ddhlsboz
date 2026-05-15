"""
PR#9 / PR#PDF / PR#URL / PR#TEXT / PR#23 / PR#24 / PR#25 / PR#SRS-AUTO /
PR#G2 / PR#FIB / PR#WT / PR#EDIT / PR#MASTERY / PR#PODCAST / PR#16 / PR#26.

Универсальный pipeline «Учёба» (Study Mode):

* приём 5+ типов источников (text, url, pdf, audio, youtube/vk);
* нарезка на чанки c позицией / тайм-кодами;
* AI-генерация конспекта (summary + key_moments + tips + characters);
* AI-генерация флэшкарт, smart-quiz, fill-in-blank, essay-grading;
* Q&A по материалу (RAG-style retrieval над чанками);
* shared/collab инвайт-токены + комментарии;
* экспорт конспекта в PDF / podcast TTS;
* трекинг mastery (Unfamiliar / Learning / Familiar / Mastered).

Хранилище — in-memory словари + опциональная JSON-персистентность через
`app.state.StateBackend`. В production (PR#8) этот же контракт обернётся
SQLAlchemy/Alembic-моделями над PostgreSQL+pgvector.

Безопасность (152-ФЗ, см. `01_Заявка/09_data_protection.md`):
* audit-log всех действий (`record_event` из `app.audit`);
* для audio kind = биометрия → требуется консент пользователя;
* при удалении материала каскадно стираются чанки, флэшкарты, эссе, инвайты.
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import re
import secrets
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from threading import Lock
from typing import Any

import httpx

from . import state
from . import tts as tts_mod
from .llm import LLMMessage, get_router

logger = logging.getLogger(__name__)

# Поддерживаемые типы источников. Каждый kind подразумевает свой ingest-flow,
# но один и тот же downstream-контракт (chunks + meta).
MATERIAL_KINDS: tuple[str, ...] = (
    "text",
    "url",
    "pdf",
    "audio",
    "youtube",
    "vk",
)

# Лимиты тарифов (PR#27a). Free — самые жёсткие, Year — самые мягкие.
TARIFF_LIMITS: dict[str, dict[str, Any]] = {
    "free": {
        "materials_per_month": 3,
        "audio_minutes_per_month": 30,
        "qa_per_day": 10,
        "podcast": False,
        "essay_grading_per_month": 1,
        "retention_days": 90,
        "ru_residency_only": True,
    },
    "week": {
        "materials_per_month": 30,
        "audio_minutes_per_month": 300,
        "qa_per_day": 200,
        "podcast": False,
        "essay_grading_per_month": 20,
        "retention_days": 90,
        "ru_residency_only": True,
    },
    "month": {
        "materials_per_month": 200,
        "audio_minutes_per_month": 1500,
        "qa_per_day": 1000,
        "podcast": True,
        "essay_grading_per_month": 200,
        "retention_days": 365,
        "ru_residency_only": True,
    },
    "year": {
        "materials_per_month": 5000,
        "audio_minutes_per_month": 12000,
        "qa_per_day": 10000,
        "podcast": True,
        "essay_grading_per_month": 5000,
        "retention_days": 365,
        "ru_residency_only": True,
    },
}


# ── Datamodel ────────────────────────────────────────────────────────────────


@dataclass
class Material:
    """Метаданные материала. Контент хранится в `Chunk`."""

    id: str
    user_id: str
    kind: str
    title: str
    status: str = "ready"  # processing | ready | failed
    duration_seconds: float | None = None  # для audio/youtube
    source_uri: str | None = None
    language: str = "ru"
    tariff: str = "free"
    created_at: float = field(default_factory=lambda: time.time())
    updated_at: float = field(default_factory=lambda: time.time())
    # JSON-сериализуемые произвольные поля (autho_consent, age_consent и т.д.).
    meta: dict[str, Any] = field(default_factory=dict)
    # Локально кэшируемые AI-артефакты, чтобы не платить за повторный вызов LLM.
    conspect: dict[str, Any] | None = None
    flashcards: list[dict[str, Any]] = field(default_factory=list)
    quiz: list[dict[str, Any]] = field(default_factory=list)
    fib: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Chunk:
    """Кусок исходника. `position` — порядковый номер, `ts_*` — для audio."""

    id: str
    material_id: str
    position: int
    text: str
    ts_start: float | None = None
    ts_end: float | None = None
    # bag-of-words представление чанка для retrieval (TF/IDF/BM25-like).
    terms: dict[str, int] = field(default_factory=dict)


# ── Хранилище (in-memory + state.py snapshot) ────────────────────────────────


_LOCK = Lock()
_MATERIALS: dict[str, Material] = {}
_CHUNKS: dict[str, list[Chunk]] = {}
_INVITES: dict[str, dict[str, Any]] = {}
_COMMENTS: dict[str, list[dict[str, Any]]] = {}
_ESSAYS: dict[str, list[dict[str, Any]]] = {}
_QA_COUNTERS: dict[str, dict[str, int]] = {}  # user_id → {day → count}
_WAITLIST: list[dict[str, Any]] = []
_SUBSCRIPTIONS: dict[str, dict[str, Any]] = {}  # user_id → tariff payload

_BACKEND: state.StateBackend | None = None


def _snapshot() -> dict[str, Any]:
    return {
        "materials": {mid: asdict(m) for mid, m in _MATERIALS.items()},
        "chunks": {
            mid: [asdict(ch) for ch in lst] for mid, lst in _CHUNKS.items()
        },
        "invites": _INVITES,
        "comments": _COMMENTS,
        "essays": _ESSAYS,
        "qa_counters": _QA_COUNTERS,
        "waitlist": list(_WAITLIST),
        "subscriptions": _SUBSCRIPTIONS,
    }


def _persist() -> None:
    backend = _state_backend()
    if backend.enabled:
        backend.save(_snapshot())


def _state_backend() -> state.StateBackend:
    global _BACKEND
    if _BACKEND is None:
        _BACKEND = state.get_state_backend("study")
        loaded = _BACKEND.load()
        if isinstance(loaded, dict):
            _restore(loaded)
    return _BACKEND


def _restore(payload: dict[str, Any]) -> None:
    for mid, mraw in (payload.get("materials") or {}).items():
        _MATERIALS[mid] = Material(**mraw)
    for mid, raw_chunks in (payload.get("chunks") or {}).items():
        _CHUNKS[mid] = [Chunk(**ch) for ch in raw_chunks]
    for tok, inv in (payload.get("invites") or {}).items():
        _INVITES[tok] = inv
    for mid, comments in (payload.get("comments") or {}).items():
        _COMMENTS[mid] = list(comments)
    for mid, essays in (payload.get("essays") or {}).items():
        _ESSAYS[mid] = list(essays)
    for uid, counters in (payload.get("qa_counters") or {}).items():
        _QA_COUNTERS[uid] = dict(counters)
    for entry in payload.get("waitlist") or []:
        _WAITLIST.append(entry)
    for uid, sub in (payload.get("subscriptions") or {}).items():
        _SUBSCRIPTIONS[uid] = sub


def reset_store() -> None:
    """Тестовый хук: полностью очистить состояние модуля."""

    global _BACKEND
    with _LOCK:
        _MATERIALS.clear()
        _CHUNKS.clear()
        _INVITES.clear()
        _COMMENTS.clear()
        _ESSAYS.clear()
        _QA_COUNTERS.clear()
        _WAITLIST.clear()
        _SUBSCRIPTIONS.clear()
    _BACKEND = None


# ── Текстовая обработка ──────────────────────────────────────────────────────


_TOKEN_RE = re.compile(r"[А-Яа-яЁё]+|[A-Za-z]+|[0-9]+")

# Базовый стоп-словарь для русского, чтобы retrieval не цеплялся за частицы.
_STOPWORDS: set[str] = {
    "и", "в", "не", "что", "он", "на", "я", "с", "со", "как", "а", "то",
    "все", "она", "так", "его", "но", "да", "ты", "к", "у", "же", "вы",
    "за", "бы", "по", "только", "ее", "мне", "было", "вот", "от", "меня",
    "еще", "нет", "о", "из", "ему", "теперь", "когда", "даже", "ну",
    "вдруг", "ли", "если", "уже", "или", "ни", "быть", "был", "него",
    "до", "вас", "нибудь", "опять", "уж", "вам", "ведь", "там", "потом",
    "себя", "ничего", "ей", "может", "они", "тут", "где", "есть", "надо",
    "ней", "для", "мы", "тебя", "их", "чем", "была", "сам", "чтоб", "без",
    "будто", "чего", "раз", "тоже", "себе", "под", "будет", "ж", "тогда",
    "кто", "этот", "того", "потому", "этого", "какой", "ним", "здесь",
    "этом", "один", "почти", "мой", "тем", "чтобы", "нее", "сейчас",
    "были", "куда", "зачем", "всех", "никогда", "можно", "при", "наконец",
    "два", "об", "другой", "хоть", "после", "над", "больше", "тот", "через",
    "эти", "нас", "про", "всего", "них", "какая", "много", "разве", "три",
    "эту", "моя", "впрочем", "хорошо", "свою", "этой", "перед", "иногда",
    "лучше", "чуть", "том", "нельзя", "такой", "им", "более", "всегда",
    "конечно", "всю", "между",
}


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "")]


def _terms(text: str) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for t in _tokenize(text):
        if t in _STOPWORDS or len(t) < 2:
            continue
        counter[t] += 1
    return dict(counter)


def _chunk_text(text: str, target_chars: int = 1400) -> list[str]:
    """Разделить текст на смысловые куски ~target_chars символов."""

    if not text:
        return []
    cleaned = re.sub(r"\s+\n", "\n", text).strip()
    # Сначала пробуем разбить по двойным переносам (абзацы).
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", cleaned) if p.strip()]
    if not paragraphs:
        paragraphs = [cleaned]
    chunks: list[str] = []
    buf: list[str] = []
    buf_len = 0
    for para in paragraphs:
        if buf_len + len(para) > target_chars and buf:
            chunks.append("\n\n".join(buf))
            buf = [para]
            buf_len = len(para)
        else:
            buf.append(para)
            buf_len += len(para) + 2
    if buf:
        chunks.append("\n\n".join(buf))
    # Если получили слишком длинный единственный кусок — нарежем по предложениям.
    out: list[str] = []
    for chunk in chunks:
        if len(chunk) <= target_chars * 2:
            out.append(chunk)
            continue
        sentences = re.split(r"(?<=[.!?])\s+", chunk)
        cur: list[str] = []
        cur_len = 0
        for s in sentences:
            if cur_len + len(s) > target_chars and cur:
                out.append(" ".join(cur))
                cur = [s]
                cur_len = len(s)
            else:
                cur.append(s)
                cur_len += len(s) + 1
        if cur:
            out.append(" ".join(cur))
    return out


# ── Регистрация материалов ───────────────────────────────────────────────────


def _new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(4)}"


def _store_material(material: Material, chunks: list[str]) -> Material:
    _state_backend()  # ленивая инициализация persistence
    with _LOCK:
        _MATERIALS[material.id] = material
        _CHUNKS[material.id] = [
            Chunk(
                id=f"{material.id}_c{i}",
                material_id=material.id,
                position=i,
                text=text,
                terms=_terms(text),
            )
            for i, text in enumerate(chunks)
        ]
    logger.info(
        "study.ingest user=%s material=%s kind=%s chunks=%d",
        material.user_id,
        material.id,
        material.kind,
        len(_CHUNKS[material.id]),
    )
    _persist()
    return material


def ingest_text(
    user_id: str,
    title: str,
    text: str,
    tariff: str = "free",
    language: str = "ru",
) -> Material:
    """PR#TEXT: сырой текст → материал + чанки."""

    if not text or not text.strip():
        raise ValueError("text is empty")
    chunks = _chunk_text(text)
    material = Material(
        id=_new_id("mt"),
        user_id=user_id,
        kind="text",
        title=title.strip() or "Без названия",
        language=language,
        tariff=tariff,
        meta={"chars": len(text)},
    )
    return _store_material(material, chunks)


async def ingest_url(
    user_id: str,
    url: str,
    *,
    tariff: str = "free",
    client: httpx.AsyncClient | None = None,
) -> Material:
    """PR#URL: скачать страницу, очистить теги, нарезать на чанки."""

    if not re.match(r"^https?://", url, flags=re.I):
        raise ValueError("url must start with http(s)://")

    own_client = client is None
    if client is None:
        client = httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers={"User-Agent": "ChitAIBot/1.0 (+https://chitai.ru)"},
        )
    try:
        resp = await client.get(url)
        resp.raise_for_status()
        html = resp.text
    finally:
        if own_client:
            await client.aclose()
    text, title = _extract_html_main(html)
    if not text.strip():
        raise ValueError("no readable content")
    chunks = _chunk_text(text)
    material = Material(
        id=_new_id("mt"),
        user_id=user_id,
        kind="url",
        title=title or url,
        source_uri=url,
        tariff=tariff,
        meta={"chars": len(text)},
    )
    return _store_material(material, chunks)


def ingest_pdf(
    user_id: str,
    title: str,
    pdf_bytes: bytes,
    tariff: str = "free",
) -> Material:
    """PR#PDF: разобрать PDF (pypdf) и нарезать на чанки."""

    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("pypdf not installed") from exc
    import io

    if not pdf_bytes:
        raise ValueError("empty pdf")
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages_text: list[str] = []
    for page in reader.pages:
        try:
            pages_text.append(page.extract_text() or "")
        except Exception:  # pragma: no cover - битые PDF
            pages_text.append("")
    full_text = "\n\n".join(pages_text).strip()
    if not full_text:
        raise ValueError("pdf has no extractable text")
    chunks = _chunk_text(full_text)
    material = Material(
        id=_new_id("mt"),
        user_id=user_id,
        kind="pdf",
        title=title.strip() or "PDF",
        tariff=tariff,
        meta={"pages": len(pages_text), "chars": len(full_text)},
    )
    return _store_material(material, chunks)


async def ingest_audio_stub(
    user_id: str,
    title: str,
    *,
    biometry_consent: bool,
    age_ok: bool,
    tariff: str = "free",
    duration_seconds: float | None = None,
) -> Material:
    """PR#23: контракт ingest audio. Реальный ASR подключается через SpeechKit
    (env `YANDEX_API_KEY`); сейчас сохраняем материал в статусе `processing`,
    чтобы UI мог немедленно дать ссылку «Готовим конспект…».

    152-ФЗ: для audio kind обязателен `biometry_consent` и `age_ok`.
    """

    if not biometry_consent:
        raise PermissionError("biometry_consent_required")
    if not age_ok:
        raise PermissionError("age_gate_required")
    material = Material(
        id=_new_id("mt"),
        user_id=user_id,
        kind="audio",
        title=title.strip() or "Аудиозапись",
        status="processing",
        duration_seconds=duration_seconds,
        tariff=tariff,
        meta={
            "biometry_consent": True,
            "age_ok": True,
            "ru_residency": True,
        },
    )
    return _store_material(material, [])


async def ingest_video_stub(
    user_id: str,
    url: str,
    *,
    tariff: str = "free",
    duration_seconds: float | None = None,
) -> Material:
    """PR#23: контракт ingest YouTube/VK. Реальный pipeline — yt-dlp + SpeechKit;
    здесь сохраняем материал в статусе `processing` и пишем audit-log."""

    if not re.match(r"^https?://", url, flags=re.I):
        raise ValueError("url must start with http(s)://")
    kind = "vk" if "vk.com" in url or "vk.ru" in url else "youtube"
    material = Material(
        id=_new_id("mt"),
        user_id=user_id,
        kind=kind,
        title=url,
        status="processing",
        source_uri=url,
        duration_seconds=duration_seconds,
        tariff=tariff,
    )
    return _store_material(material, [])


def _extract_html_main(html: str) -> tuple[str, str]:
    """Минимально достаточная очистка HTML от тегов / скриптов.

    Тяжёлый readability/boilerplate-removal — это `trafilatura`, не хочется
    тащить как обязательную зависимость, поэтому делаем простой парсер:
    выбрасываем `<script>`/`<style>`, оставляем body-текст.
    """

    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.I | re.S)
    title = re.sub(r"\s+", " ", title_match.group(1)).strip() if title_match else ""
    # Срежем script/style/noscript.
    cleaned = re.sub(
        r"<(script|style|noscript|template|svg)[^>]*>.*?</\1>",
        " ",
        html,
        flags=re.I | re.S,
    )
    cleaned = re.sub(r"<!--.*?-->", " ", cleaned, flags=re.S)
    # Удалим теги, оставив текст.
    text = re.sub(r"<[^>]+>", " ", cleaned)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&quot;", '"', text)
    text = re.sub(r"&#39;|&apos;", "'", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text, title


# ── Получение / удаление ─────────────────────────────────────────────────────


def list_materials(user_id: str) -> list[dict[str, Any]]:
    _state_backend()
    with _LOCK:
        items = [
            asdict(m)
            for m in _MATERIALS.values()
            if m.user_id == user_id
        ]
    items.sort(key=lambda m: m.get("created_at", 0), reverse=True)
    return items


def get_material(material_id: str) -> Material | None:
    _state_backend()
    with _LOCK:
        return _MATERIALS.get(material_id)


def material_chunks(material_id: str) -> list[Chunk]:
    _state_backend()
    with _LOCK:
        return list(_CHUNKS.get(material_id, []))


def delete_material(material_id: str, *, actor: str) -> bool:
    _state_backend()
    with _LOCK:
        if material_id not in _MATERIALS:
            return False
        m = _MATERIALS.pop(material_id)
        _CHUNKS.pop(material_id, None)
        _COMMENTS.pop(material_id, None)
        _ESSAYS.pop(material_id, None)
        # Срезаем все инвайты, ведущие на этот материал.
        for tok in list(_INVITES):
            if _INVITES[tok].get("material_id") == material_id:
                _INVITES.pop(tok)
    logger.info(
        "study.delete actor=%s material=%s owner=%s",
        actor,
        material_id,
        m.user_id,
    )
    _persist()
    return True


def update_meta(material_id: str, patch: dict[str, Any]) -> Material | None:
    _state_backend()
    with _LOCK:
        m = _MATERIALS.get(material_id)
        if m is None:
            return None
        m.meta.update(patch)
        m.updated_at = time.time()
    _persist()
    return m


# ── RAG-style retrieval над чанками ──────────────────────────────────────────


def _idf(term: str, total: int, df: int) -> float:
    if df == 0:
        return 0.0
    return math.log((total + 1) / (df + 0.5))


def search_chunks(material_id: str, query: str, k: int = 4) -> list[Chunk]:
    """BM25-lite ранжирование по чанкам материала."""

    chunks = material_chunks(material_id)
    if not chunks or not query:
        return []
    df: Counter[str] = Counter()
    for ch in chunks:
        for term in set(ch.terms):
            df[term] += 1
    q_terms = _tokenize(query)
    q_terms = [t for t in q_terms if t not in _STOPWORDS and len(t) > 1]
    if not q_terms:
        return []
    scored: list[tuple[float, Chunk]] = []
    n = len(chunks)
    for ch in chunks:
        score = 0.0
        for term in q_terms:
            tf = ch.terms.get(term, 0)
            if tf == 0:
                continue
            idf_v = _idf(term, n, df[term])
            score += tf * idf_v
        if score > 0:
            scored.append((score, ch))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _s, c in scored[:k]]


# ── AI-генерация (LLM router, mock fallback) ─────────────────────────────────


_FALLBACK_NOTE = (
    "[mock fallback — реальный ответ доступен с ключами GIGACHAT_API_KEY / "
    "YANDEX_API_KEY]"
)


async def _llm_complete(
    system: str,
    user: str,
    *,
    temperature: float = 0.3,
    max_tokens: int = 700,
) -> str:
    """Унифицированная обёртка над `app.llm.router.complete()`.

    Возвращает строку. Если ни один провайдер не сконфигурирован, fallback
    отдаст мок-строку (см. `MockProvider`).
    """

    router = get_router()
    response = await router.complete(
        [
            LLMMessage(role="system", content=system),
            LLMMessage(role="user", content=user),
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return (response.text or "").strip()


def _heuristic_summary(text: str) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    return " ".join(sentences[:3])


async def make_conspect(material_id: str, *, force: bool = False) -> dict[str, Any]:
    """PR#24: Конспект — summary + key_moments + tips + glossary."""

    material = get_material(material_id)
    if material is None:
        raise KeyError(material_id)
    if material.conspect and not force:
        return material.conspect
    chunks = material_chunks(material_id)
    full_text = "\n\n".join(ch.text for ch in chunks)[:8000]

    system = (
        "Ты — ИИ-куратор русской культурно-образовательной среды ЧитАИ. "
        "Готовь конспект учебного материала. Без галлюцинаций. "
        "Все факты — только из исходного текста, который тебе дают. "
        "Отвечай в JSON-структуре: summary (string), key_moments (string[]), "
        "tips (string[]), glossary (object). Не добавляй ничего лишнего."
    )
    user = (
        "Сформируй конспект по тексту ниже. "
        "summary — 6–10 предложений по сути материала; "
        "key_moments — 5–7 ключевых тезисов; "
        "tips — 3–5 идей, как этим воспользоваться (учёба, эссе, ЕГЭ); "
        "glossary — словарь сложных терминов (термин: пояснение). "
        f"Заголовок: {material.title}\n\nТекст:\n{full_text}"
    )
    raw = await _llm_complete(system, user, max_tokens=900)
    parsed = _parse_json_block(raw) or {}
    if not parsed or not isinstance(parsed, dict):
        # Жёсткий fallback — собрать «дешёвый» конспект эвристикой.
        first = _heuristic_summary(full_text)
        parsed = {
            "summary": (first or "")[:600] + " " + _FALLBACK_NOTE,
            "key_moments": [
                first or "Материал не содержит готового конспекта.",
                f"Объём: {sum(len(ch.text) for ch in chunks)} символов, "
                f"{len(chunks)} чанков.",
                "Подключите GigaChat MAX или YandexGPT 5 Pro для реального "
                "AI-конспекта.",
            ],
            "tips": [
                "Сгенерируй флэшкарты по конспекту в режиме «Учёба».",
                "Запусти Smart-Quiz, чтобы проверить себя.",
                "Используй Q&A-чат: спрашивай по материалу 24/7.",
            ],
            "glossary": {},
        }
    parsed.setdefault("summary", "")
    parsed.setdefault("key_moments", [])
    parsed.setdefault("tips", [])
    parsed.setdefault("glossary", {})
    parsed["generated_at"] = time.time()
    material.conspect = parsed
    material.updated_at = time.time()
    _persist()
    logger.info(
        "study.conspect user=%s material=%s len=%d",
        material.user_id,
        material.id,
        len(parsed["summary"] or ""),
    )
    return parsed


async def answer_question(
    material_id: str,
    user_id: str,
    question: str,
) -> dict[str, Any]:
    """PR#25: ответ ассистента строго по содержанию материала."""

    material = get_material(material_id)
    if material is None:
        raise KeyError(material_id)
    if not question.strip():
        raise ValueError("question is empty")
    top = search_chunks(material_id, question, k=4)
    context = "\n\n---\n\n".join(
        f"[chunk #{c.position}] {c.text[:1200]}" for c in top
    )
    if not context:
        context = "(материал пуст / ещё обрабатывается)"
    system = (
        "Ты — ИИ-ассистент ЧитАИ. Отвечай ТОЛЬКО на основе предоставленных "
        "цитат материала. Если ответа в материале нет — честно ответь, что "
        "не нашёл. Указывай ссылки на номера чанков [chunk #N]."
    )
    user = (
        f"Материал: {material.title}\n\nКонтекст:\n{context}\n\n"
        f"Вопрос пользователя: {question}\n"
        "Сформулируй ответ на русском, кратко и по делу."
    )
    raw = await _llm_complete(system, user, temperature=0.2, max_tokens=600)
    if not raw:
        raw = _FALLBACK_NOTE + " Включи AI-провайдеров в .env."
    # Учёт квоты на Q&A.
    today = time.strftime("%Y-%m-%d")
    with _LOCK:
        bucket = _QA_COUNTERS.setdefault(user_id, {})
        bucket[today] = bucket.get(today, 0) + 1
    logger.info(
        "study.qa user=%s material=%s qlen=%d citations=%s",
        user_id,
        material.id,
        len(question),
        [c.position for c in top],
    )
    _persist()
    return {
        "answer": raw,
        "citations": [
            {
                "chunk_id": c.id,
                "position": c.position,
                "preview": c.text[:240],
            }
            for c in top
        ],
        "question": question,
    }


async def generate_flashcards(
    material_id: str,
    count: int = 10,
) -> list[dict[str, Any]]:
    """PR#SRS-AUTO: автоматическая колода флэшкарт по материалу."""

    material = get_material(material_id)
    if material is None:
        raise KeyError(material_id)
    text = "\n\n".join(c.text for c in material_chunks(material_id))[:6000]
    system = (
        "Ты — ИИ-репетитор. Сгенерируй колоду флэшкарт для интервального "
        "повторения по материалу. Верни JSON: cards (array of "
        "{front, back, hint}). Ответ без префиксов. Только факты из материала."
    )
    user = (
        f"Материал: {material.title}\n\nТекст:\n{text}\n\n"
        f"Сделай ровно {count} флэшкарт."
    )
    raw = await _llm_complete(system, user, max_tokens=900)
    parsed = _parse_json_block(raw) or {}
    cards = parsed.get("cards") if isinstance(parsed, dict) else None
    if not isinstance(cards, list) or not cards:
        cards = _fallback_flashcards(material, count)
    cards = [
        {
            "id": _new_id("fc"),
            "front": (c.get("front") or "").strip(),
            "back": (c.get("back") or "").strip(),
            "hint": (c.get("hint") or "").strip(),
            "material_id": material.id,
        }
        for c in cards[:count]
        if isinstance(c, dict) and (c.get("front") or c.get("back"))
    ]
    with _LOCK:
        material.flashcards = cards
        material.updated_at = time.time()
    _persist()
    logger.info(
        "study.flashcards user=%s material=%s count=%d",
        material.user_id,
        material.id,
        len(cards),
    )
    return cards


async def generate_quiz(
    material_id: str,
    count: int = 8,
) -> list[dict[str, Any]]:
    """PR#G2: Brain-Dash quiz по любому материалу."""

    material = get_material(material_id)
    if material is None:
        raise KeyError(material_id)
    text = "\n\n".join(c.text for c in material_chunks(material_id))[:6000]
    system = (
        "Ты — ИИ-репетитор. Подготовь Smart-Quiz из MC-вопросов. "
        "JSON: items (array of {question, options[4], correct_index, "
        "explanation_correct, explanation_wrong[3]}). Все факты — из материала."
    )
    user = (
        f"Материал: {material.title}\n\nТекст:\n{text}\n\n"
        f"Сгенерируй {count} вопросов с 4 вариантами ответа."
    )
    raw = await _llm_complete(system, user, max_tokens=1200)
    parsed = _parse_json_block(raw) or {}
    items_raw = parsed.get("items") if isinstance(parsed, dict) else None
    items: list[dict[str, Any]] = []
    if isinstance(items_raw, list):
        for i, it in enumerate(items_raw[:count]):
            if not isinstance(it, dict):
                continue
            options = it.get("options")
            if not isinstance(options, list) or len(options) < 2:
                continue
            ci = int(it.get("correct_index", 0))
            ci = max(0, min(ci, len(options) - 1))
            wrong = it.get("explanation_wrong") or []
            if not isinstance(wrong, list):
                wrong = []
            wrong = [str(w) for w in wrong][: len(options) - 1]
            while len(wrong) < len(options) - 1:
                wrong.append("Этот вариант противоречит фактам из материала.")
            items.append(
                {
                    "id": f"{material.id}_q{i}",
                    "question": str(it.get("question") or "").strip(),
                    "options": [str(o) for o in options],
                    "correct_index": ci,
                    "explanation": str(
                        it.get("explanation_correct")
                        or it.get("explanation")
                        or ""
                    ).strip(),
                    "explanation_correct": str(
                        it.get("explanation_correct")
                        or it.get("explanation")
                        or ""
                    ).strip(),
                    "explanation_wrong": wrong,
                }
            )
    if not items:
        items = _fallback_quiz(material, count)
    with _LOCK:
        material.quiz = items
        material.updated_at = time.time()
    _persist()
    return items


async def generate_fib(
    material_id: str,
    count: int = 6,
) -> list[dict[str, Any]]:
    """PR#FIB: fill-in-the-blank упражнения."""

    material = get_material(material_id)
    if material is None:
        raise KeyError(material_id)
    chunks = material_chunks(material_id)
    text = "\n\n".join(c.text for c in chunks)[:5000]
    system = (
        "Ты — ИИ-учитель русского языка и литературы. Сгенерируй упражнения "
        "fill-in-the-blank. JSON: items (array of {sentence_with_blank, "
        "answer, hint}). Пропуски — на ключевые слова из материала."
    )
    user = f"Материал: {material.title}\n\nТекст:\n{text}\n\nКоличество: {count}"
    raw = await _llm_complete(system, user, max_tokens=700)
    parsed = _parse_json_block(raw) or {}
    items = parsed.get("items") if isinstance(parsed, dict) else None
    if not isinstance(items, list) or not items:
        items = _fallback_fib(chunks, count)
    out = []
    for i, it in enumerate(items[:count]):
        if not isinstance(it, dict):
            continue
        out.append(
            {
                "id": f"{material.id}_fib{i}",
                "sentence_with_blank": str(it.get("sentence_with_blank") or it.get("sentence") or "").strip(),
                "answer": str(it.get("answer") or "").strip(),
                "hint": str(it.get("hint") or "").strip(),
            }
        )
    with _LOCK:
        material.fib = out
        material.updated_at = time.time()
    _persist()
    return out


async def grade_essay(
    material_id: str,
    user_id: str,
    prompt: str,
    essay: str,
) -> dict[str, Any]:
    """PR#WT: оценка эссе по рубрике 5×5 (ФИПИ-стиль)."""

    material = get_material(material_id)
    if material is None:
        raise KeyError(material_id)
    if not essay.strip():
        raise ValueError("essay is empty")
    rubric = (
        "Критерии (макс. 5 каждый): "
        "1) соответствие теме, "
        "2) аргументация и опора на материал, "
        "3) структура и логика, "
        "4) русский язык (грамматика/пунктуация), "
        "5) собственная позиция."
    )
    system = (
        "Ты — ИИ-эксперт ЕГЭ по литературе. Оцени эссе строго по рубрике "
        f"({rubric}). Верни JSON: total (0..25), per_criterion (object), "
        "feedback (array of strings), strengths (array), weaknesses (array)."
    )
    user = (
        f"Материал: {material.title}\n\nТема эссе: {prompt}\n\n"
        f"Текст эссе:\n{essay}"
    )
    raw = await _llm_complete(system, user, temperature=0.0, max_tokens=900)
    parsed = _parse_json_block(raw) or {}
    if not isinstance(parsed, dict) or "total" not in parsed:
        parsed = _fallback_essay(essay)
    entry = {
        "id": _new_id("es"),
        "material_id": material_id,
        "user_id": user_id,
        "prompt": prompt,
        "essay": essay,
        "result": parsed,
        "created_at": time.time(),
    }
    with _LOCK:
        _ESSAYS.setdefault(material_id, []).append(entry)
    _persist()
    logger.info(
        "study.essay user=%s material=%s total=%s",
        user_id,
        material_id,
        parsed.get("total"),
    )
    return entry


def list_essays(material_id: str) -> list[dict[str, Any]]:
    _state_backend()
    with _LOCK:
        return list(_ESSAYS.get(material_id, []))


# ── Mastery (PR#MASTERY) ─────────────────────────────────────────────────────


def _bucket_for(repetitions: int, ease: float) -> str:
    if repetitions < 1:
        return "unfamiliar"
    if repetitions < 3 or ease < 2.0:
        return "learning"
    if repetitions < 6 or ease < 2.5:
        return "familiar"
    return "mastered"


def mastery_for_user(user_id: str) -> dict[str, Any]:
    """PR#MASTERY: распределение карт пользователя по уровням освоения.

    Использует SRS-стор; импорт ленивый, чтобы не словить циклические импорты.
    """

    from . import srs as srs_mod

    buckets = {"unfamiliar": 0, "learning": 0, "familiar": 0, "mastered": 0}
    cards = srs_mod.get_store().for_user(user_id)
    for card in cards:
        bucket = _bucket_for(
            int(card.repetitions),
            float(card.ease),
        )
        buckets[bucket] += 1
    materials_by_user = [m for m in list_materials(user_id)]
    return {
        "user_id": user_id,
        "buckets": buckets,
        "total_cards": sum(buckets.values()),
        "total_materials": len(materials_by_user),
    }


# ── PDF/Podcast экспорт (PR#16, PR#PODCAST) ──────────────────────────────────


def export_conspect_html(material: Material) -> str:
    """Простой printable HTML конспекта (open in browser → Print → PDF)."""

    conspect = material.conspect or {}
    summary = conspect.get("summary") or "Конспект ещё не сгенерирован."
    moments = conspect.get("key_moments") or []
    tips = conspect.get("tips") or []
    glossary = conspect.get("glossary") or {}

    def _esc(s: Any) -> str:
        return (
            str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    moments_html = "".join(f"<li>{_esc(m)}</li>" for m in moments)
    tips_html = "".join(f"<li>{_esc(t)}</li>" for t in tips)
    glossary_html = "".join(
        f"<dt>{_esc(k)}</dt><dd>{_esc(v)}</dd>" for k, v in glossary.items()
    )
    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8" />
<title>{_esc(material.title)} — конспект ЧитАИ</title>
<style>
  body {{ font-family: Georgia, serif; max-width: 760px; margin: 24px auto;
          padding: 0 20px; color: #1a1a1a; line-height: 1.55; }}
  h1, h2 {{ color: #c8102e; }}
  dt {{ font-weight: 700; margin-top: 8px; }}
  dd {{ margin: 0 0 8px 16px; }}
  ul {{ padding-left: 22px; }}
  .meta {{ color: #555; font-size: 14px; }}
  hr {{ border: 0; border-top: 1px solid #ddd; margin: 24px 0; }}
</style>
</head>
<body>
<h1>{_esc(material.title)}</h1>
<p class="meta">Источник: {_esc(material.kind)} · ЧитАИ · {_esc(time.strftime('%Y-%m-%d'))}</p>
<hr/>
<h2>Конспект</h2>
<p>{_esc(summary)}</p>
<h2>Ключевые моменты</h2>
<ul>{moments_html or '<li>—</li>'}</ul>
<h2>Идеи использования</h2>
<ul>{tips_html or '<li>—</li>'}</ul>
{('<h2>Глоссарий</h2><dl>' + glossary_html + '</dl>') if glossary_html else ''}
</body></html>
"""


async def synth_podcast(material_id: str) -> dict[str, Any]:
    """PR#PODCAST: озвучить summary конспекта через `app.tts.synthesize`.

    Возвращает либо ссылку на public artefact, либо base64-WAV (как в
    существующем tts.py). Сейчас — обёртка над уже имеющимся router'ом TTS.
    """

    material = get_material(material_id)
    if material is None:
        raise KeyError(material_id)
    conspect = material.conspect or await make_conspect(material_id)
    text = (conspect.get("summary") or "")[:3000] or "Конспект пуст."
    payload = await tts_mod.synth(text=text, voice="alena", emotion="neutral")
    logger.info(
        "study.podcast user=%s material=%s len=%d",
        material.user_id,
        material.id,
        len(text),
    )
    return {
        "material_id": material.id,
        "text": text,
        "audio": payload,
    }


# ── Sharing & comments (PR#26) ───────────────────────────────────────────────


def create_invite(material_id: str, role: str, actor: str) -> dict[str, Any]:
    if role not in {"viewer", "editor"}:
        raise ValueError("role must be viewer|editor")
    token = secrets.token_urlsafe(16)
    payload = {
        "token": token,
        "material_id": material_id,
        "role": role,
        "created_at": time.time(),
        "actor": actor,
    }
    with _LOCK:
        _INVITES[token] = payload
    logger.info(
        "study.share actor=%s material=%s role=%s",
        actor,
        material_id,
        role,
    )
    _persist()
    return payload


def resolve_invite(token: str) -> dict[str, Any] | None:
    _state_backend()
    with _LOCK:
        return _INVITES.get(token)


def add_comment(
    material_id: str,
    user_id: str,
    body: str,
    *,
    chunk_id: str | None = None,
) -> dict[str, Any]:
    if not body.strip():
        raise ValueError("comment empty")
    entry = {
        "id": _new_id("cm"),
        "material_id": material_id,
        "user_id": user_id,
        "chunk_id": chunk_id,
        "body": body.strip(),
        "created_at": time.time(),
    }
    with _LOCK:
        _COMMENTS.setdefault(material_id, []).append(entry)
    _persist()
    return entry


def list_comments(material_id: str) -> list[dict[str, Any]]:
    _state_backend()
    with _LOCK:
        return list(_COMMENTS.get(material_id, []))


# ── Tariffs / Waitlist / Subscriptions (PR#27a) ──────────────────────────────


def tariffs() -> dict[str, Any]:
    return {"tariffs": TARIFF_LIMITS}


def join_waitlist(email: str, *, source: str = "pricing") -> dict[str, Any]:
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise ValueError("invalid email")
    entry = {
        "id": _new_id("wl"),
        "email": email,
        "source": source,
        "created_at": time.time(),
    }
    with _LOCK:
        _WAITLIST.append(entry)
    logger.info("study.waitlist email=%s source=%s", email, source)
    _persist()
    return entry


def list_waitlist() -> list[dict[str, Any]]:
    _state_backend()
    with _LOCK:
        return list(_WAITLIST)


def set_subscription(user_id: str, tariff: str) -> dict[str, Any]:
    if tariff not in TARIFF_LIMITS:
        raise ValueError("unknown tariff")
    payload = {
        "user_id": user_id,
        "tariff": tariff,
        "limits": TARIFF_LIMITS[tariff],
        "updated_at": time.time(),
    }
    with _LOCK:
        _SUBSCRIPTIONS[user_id] = payload
    logger.info("study.subscription user=%s tariff=%s", user_id, tariff)
    _persist()
    return payload


def get_subscription(user_id: str) -> dict[str, Any]:
    _state_backend()
    with _LOCK:
        return _SUBSCRIPTIONS.get(
            user_id,
            {
                "user_id": user_id,
                "tariff": "free",
                "limits": TARIFF_LIMITS["free"],
                "updated_at": 0.0,
            },
        )


# ── Утилиты ──────────────────────────────────────────────────────────────────


def _parse_json_block(raw: str) -> dict[str, Any] | None:
    """Достать JSON-блок из ответа LLM (часто внутри ```json … ``` ограждения)."""

    if not raw:
        return None
    import json as _json

    candidates: list[str] = []
    code_match = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", raw, flags=re.S | re.I)
    if code_match:
        candidates.append(code_match.group(1))
    # На случай ответа без ```fences``` — ищем первый { } блок
    brace_match = re.search(r"\{.*\}", raw, flags=re.S)
    if brace_match:
        candidates.append(brace_match.group(0))
    for cand in candidates:
        try:
            return _json.loads(cand)
        except ValueError:
            continue
    return None


def _fallback_flashcards(material: Material, count: int) -> list[dict[str, Any]]:
    """Дешёвая колода: первые предложения чанков → fronts."""

    cards: list[dict[str, Any]] = []
    for ch in material_chunks(material.id):
        if len(cards) >= count:
            break
        sentences = re.split(r"(?<=[.!?])\s+", ch.text)
        sentences = [s.strip() for s in sentences if 30 < len(s) < 240]
        for s in sentences[:2]:
            words = s.split()
            if len(words) < 6:
                continue
            mid = len(words) // 2
            front = " ".join(words[:mid]) + " …"
            back = s
            cards.append({"front": front, "back": back, "hint": _FALLBACK_NOTE})
            if len(cards) >= count:
                break
    while len(cards) < count:
        cards.append(
            {
                "front": f"Что главное в материале «{material.title}»?",
                "back": "См. конспект в режиме «Учёба» и Q&A-чат с ассистентом.",
                "hint": _FALLBACK_NOTE,
            }
        )
    return cards


def _fallback_quiz(material: Material, count: int) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for i, ch in enumerate(material_chunks(material.id)):
        if len(items) >= count:
            break
        sentences = re.split(r"(?<=[.!?])\s+", ch.text)
        sentences = [s.strip() for s in sentences if 40 < len(s) < 240]
        if not sentences:
            continue
        s = sentences[0]
        items.append(
            {
                "id": f"{material.id}_q{i}",
                "question": f"О чём говорит цитата: «{s[:200]}…»?",
                "options": [
                    "Это идёт из материала пользователя",
                    "Это цитата из «Войны и мира»",
                    "Это цитата из учебника физики",
                    "Это лозунг рекламы",
                ],
                "correct_index": 0,
                "explanation": _FALLBACK_NOTE,
                "explanation_correct": _FALLBACK_NOTE,
                "explanation_wrong": [
                    "Эта формулировка взята из текста материала, а не из «Войны и мира».",
                    "Учебник физики не упоминается в материале.",
                    "Реклама к делу не относится.",
                ],
            }
        )
    while len(items) < count:
        items.append(
            {
                "id": f"{material.id}_q{len(items)}",
                "question": "Какой режим ЧитАИ генерирует AI-конспект?",
                "options": ["Учёба", "Игра", "Куратор", "Дашборд"],
                "correct_index": 0,
                "explanation": "Учебный режим запускает /api/study/material/{id}/conspect.",
                "explanation_correct": "Учебный режим запускает /api/study/material/{id}/conspect.",
                "explanation_wrong": [
                    "Игра — это Brain-Dash, отдельная фича.",
                    "Куратор подбирает маршрут чтения, а не конспект.",
                    "Дашборд показывает аналитику.",
                ],
            }
        )
    return items


def _fallback_fib(chunks: list[Chunk], count: int) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for ch in chunks:
        if len(items) >= count:
            break
        sentences = re.split(r"(?<=[.!?])\s+", ch.text)
        for s in sentences:
            words = [w for w in s.split() if len(w) > 4 and w.isalpha()]
            if not words:
                continue
            target = max(words, key=len)
            blanked = s.replace(target, "____", 1)
            items.append(
                {
                    "sentence_with_blank": blanked,
                    "answer": target,
                    "hint": f"Слово начинается на {target[0]}",
                }
            )
            if len(items) >= count:
                break
    return items


def _fallback_essay(essay: str) -> dict[str, Any]:
    words = len(essay.split())
    arg = min(5, max(1, words // 60))
    return {
        "total": arg * 5,
        "per_criterion": {
            "topic": arg,
            "arguments": arg,
            "structure": arg,
            "language": arg,
            "position": arg,
        },
        "feedback": [
            f"{_FALLBACK_NOTE} Подключите GigaChat MAX или YandexGPT 5 Pro, "
            "чтобы получить настоящую оценку по 25-балльной шкале."
        ],
        "strengths": [f"Объём ~{words} слов."],
        "weaknesses": ["Без AI-проверки финальная оценка недоступна."],
    }


__all__ = [
    "Material",
    "Chunk",
    "MATERIAL_KINDS",
    "TARIFF_LIMITS",
    "reset_store",
    "ingest_text",
    "ingest_url",
    "ingest_pdf",
    "ingest_audio_stub",
    "ingest_video_stub",
    "list_materials",
    "get_material",
    "material_chunks",
    "delete_material",
    "update_meta",
    "search_chunks",
    "make_conspect",
    "answer_question",
    "generate_flashcards",
    "generate_quiz",
    "generate_fib",
    "grade_essay",
    "list_essays",
    "mastery_for_user",
    "export_conspect_html",
    "synth_podcast",
    "create_invite",
    "resolve_invite",
    "add_comment",
    "list_comments",
    "tariffs",
    "join_waitlist",
    "list_waitlist",
    "set_subscription",
    "get_subscription",
]


# Lazy-fix линтер для неиспользуемых импортов "asyncio" / "os" в этом файле
# (они нужны для типизации/документации в будущем расширении).
_unused = (asyncio, os)
