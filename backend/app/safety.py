"""
Безопасность RAG-куратора ЧитАИ: red-team фильтр запроса + мониторинг отказов.

Что закрывает:
* В B2G/школу нельзя пускать систему, которую можно «уговорить» написать
  ученику готовый реферат, обмануть учителя, или выдать вредный совет.
* Жюри Нейрофеста подсвечивает Trust & Safety как обязательный блок.
* AI-audit-ready (F4): отказы должны логгироваться и быть аудируемыми.

Реализация — детерминированные правила (regex + ключевые слова), без LLM:
быстрый, объяснимый, вписывается в требования 152-ФЗ (ничего не отправляем
вовне). Для production добавляются ML-классификаторы (SafeRussianBERT и т.п.),
но контракт `screen(query)` сохраняется.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import dataclass
from enum import StrEnum

from .state import StateBackend, get_state_backend

logger = logging.getLogger(__name__)


class SafetyVerdict(StrEnum):
    OK = "ok"
    REFUSE = "refuse"
    CLARIFY = "clarify"


@dataclass(frozen=True)
class SafetyResult:
    verdict: SafetyVerdict
    reason: str
    category: str = ""
    suggestion: str = ""

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict.value,
            "reason": self.reason,
            "category": self.category,
            "suggestion": self.suggestion,
        }


# Ниже — категории запросов, которые мы НИКОГДА не выполняем,
# даже если LLM сконфигурирован. Это и есть антитеза «zachet.tech».
REFUSAL_PATTERNS: list[tuple[str, str, str]] = [
    (
        "academic_dishonesty",
        r"(напиши|сделай|сгенерируй|пришли|подготовь)[^?\n]{0,80}?"
        r"(реферат|сочинение|эссе|курсов|диплом|итоговое сочинение)[^?\n]{0,80}?"
        r"(за меня|вместо меня|чтобы сдать|чтобы зачёл|чтобы зачет)?",
        "ЧитАИ не пишет за пользователя готовых работ. Я подскажу план, "
        "цитаты и опорные тезисы, но текст работы вы создаёте сами.",
    ),
    (
        "anti_ai_detector",
        r"(обойти|обмани|перехитри|перехитрить|обмануть|анти[-\s]?(ai|gpt|плагиат))",
        "Я не помогаю обходить системы антиплагиата или ИИ-детекторы. "
        "Если нужно научиться писать самостоятельно — могу собрать маршрут.",
    ),
    (
        "harm_self",
        r"(как (мне )?(умереть|покончить с собой)|способ самоубийства)",
        "Это сигнал, по которому ЧитАИ отвечает только одной вещью: "
        "8-800-2000-122 — бесплатный телефон доверия. Я с тобой.",
    ),
    (
        "harm_others",
        r"(сделать\s+(бомбу|взрывчатку)|устро(ить|ишь|ит)\s+теракт|"
        r"отрав(ить|ляю|и)\s+человека|причинить\s+(вред|боль)\s+другому)",
        "ЧитАИ не помогает причинять вред людям и не отвечает на такие запросы.",
    ),
    (
        "extremism",
        r"(убей|убить|унич(тожить|тожь|тожать)?|расстреля)\s*\w*\s+(всех\s+)?"
        r"(еврее?в|мусульман|русских|украинцев|кавказц|армян|таджик|узбек|чеченц)",
        "ЧитАИ не поддерживает экстремистские и ксенофобные запросы. "
        "Я работаю с русской классикой, наукой и культурой — отбрось формулировку.",
    ),
    (
        "csam",
        r"(детск\w*\s+порн|child\s+porn|csam)",
        "Это категория абсолютного запрета. Запрос отправлен в системный аудит.",
    ),
    (
        "explicit_sex",
        r"(порн[оы]|секс\s+с\s+(несовершенно|подростк))",
        "ЧитАИ — образовательный продукт для подростков 14–22 лет, "
        "и сексуальный контент — вне нашего профиля. Сформулируйте по-другому.",
    ),
]

CLARIFY_PATTERNS: list[tuple[str, str, str]] = [
    (
        "single_word",
        r"^\s*\S{1,3}\s*$",
        "Слишком короткий запрос. Попробуйте: «Маршрут по Достоевскому для 10 класса».",
    ),
]


_COMPILED_REFUSE = [(c, re.compile(p, re.IGNORECASE | re.UNICODE), msg) for c, p, msg in REFUSAL_PATTERNS]
_COMPILED_CLARIFY = [(c, re.compile(p, re.IGNORECASE | re.UNICODE), msg) for c, p, msg in CLARIFY_PATTERNS]


@dataclass
class RefusalRecord:
    ts: float
    query: str
    category: str
    reason: str

    def to_dict(self) -> dict:
        return {
            "ts": self.ts,
            "query": self.query,
            "category": self.category,
            "reason": self.reason,
        }


class RefusalLog:
    """Аудиторский журнал отказов (in-memory кольцевой буфер + опциональный JSON).

    В production пишется в Postgres / S3 / SIEM. В demo / Yandex Cloud
    single-node — на диск через `state` бэкенд (env CHITAI_STATE_DIR), чтобы
    рестарт инстанса не стирал журнал отказов: для аудита и Trust & Safety
    это важнее, чем сам факт что лог short-lived.
    """

    def __init__(self, capacity: int = 200, backend: StateBackend | None = None) -> None:
        self.capacity = capacity
        self._lock = threading.Lock()
        self._items: list[RefusalRecord] = []
        self._backend = backend or get_state_backend("refusals")
        self._load_unlocked()

    # ── persistence ─────────────────────────────────────────────────────
    def _serialize_unlocked(self) -> dict:
        return {"version": 1, "items": [r.to_dict() for r in self._items]}

    def _load_unlocked(self) -> None:
        if not self._backend.enabled:
            return
        payload = self._backend.load()
        if not isinstance(payload, dict):
            return
        for raw in payload.get("items") or []:
            try:
                self._items.append(
                    RefusalRecord(
                        ts=float(raw["ts"]),
                        query=str(raw["query"]),
                        category=str(raw["category"]),
                        reason=str(raw.get("reason", "")),
                    )
                )
            except (KeyError, ValueError, TypeError):
                continue
        if len(self._items) > self.capacity:
            self._items = self._items[-self.capacity :]

    def _flush_unlocked(self) -> None:
        if self._backend.enabled:
            self._backend.save(self._serialize_unlocked())

    # ── public API ──────────────────────────────────────────────────────
    def add(self, query: str, category: str, reason: str) -> None:
        with self._lock:
            self._items.append(RefusalRecord(time.time(), query[:300], category, reason))
            if len(self._items) > self.capacity:
                self._items = self._items[-self.capacity :]
            self._flush_unlocked()

    def all(self) -> list[RefusalRecord]:
        with self._lock:
            return list(self._items)

    def reset(self) -> None:
        with self._lock:
            self._items.clear()
            self._flush_unlocked()


_LOG = RefusalLog()


def get_refusal_log() -> RefusalLog:
    return _LOG


def reset_refusal_log_for_testing() -> None:
    global _LOG
    _LOG = RefusalLog()


def screen(query: str) -> SafetyResult:
    """Главная точка входа. Не зависит от LLM, работает синхронно."""
    if not query or not query.strip():
        return SafetyResult(
            verdict=SafetyVerdict.CLARIFY,
            reason="empty_query",
            category="empty",
            suggestion="Опишите цель: класс, период, автор или тема.",
        )
    for cat, regex, msg in _COMPILED_REFUSE:
        if regex.search(query):
            _LOG.add(query, cat, msg)
            logger.info("safety_refuse category=%s", cat)
            return SafetyResult(
                verdict=SafetyVerdict.REFUSE, reason=msg, category=cat, suggestion=""
            )
    for cat, regex, msg in _COMPILED_CLARIFY:
        if regex.match(query):
            return SafetyResult(
                verdict=SafetyVerdict.CLARIFY,
                reason=msg,
                category=cat,
                suggestion="Например: «4 недели по Серебряному веку, 11 класс».",
            )
    return SafetyResult(verdict=SafetyVerdict.OK, reason="", category="", suggestion="")
