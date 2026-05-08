"""
AI-audit-ready (F4): машиночитаемая документация модели и промптов.

Что отдаём:
* /api/audit/model-card — Model Card в формате, близком к Model Cards от Google
  (Mitchell et al., 2019), с разделами intended_use, training_data,
  limitations, ethical_considerations.
* /api/audit/prompts — Prompt Registry: все системные/инструкционные промпты,
  которые мы реально используем в проде. Идея — внешний аудитор может
  скачать JSON и убедиться, что в системе нет «джейлбрейк-промптов».
* /api/audit/evaluation — последние результаты бенчмарка (см. benchmark.py).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock


@dataclass
class PromptCard:
    name: str
    purpose: str
    template: str
    audience: str
    safety_notes: str = ""
    version: str = "v0.1"
    locale: str = "ru-RU"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "purpose": self.purpose,
            "template": self.template,
            "audience": self.audience,
            "safety_notes": self.safety_notes,
            "version": self.version,
            "locale": self.locale,
        }


PROMPTS: list[PromptCard] = [
    PromptCard(
        name="curator.system",
        purpose="Системный промпт куратора маршрута чтения. Вшивает правило отказа от написания готовых работ и обязательной цитаты из public domain.",
        audience="14–22 года, школьники и студенты",
        template=(
            "Ты — ЧитАИ, культурный куратор. Никогда не пишешь за пользователя "
            "сочинения, рефераты или ответы для ИИ-детекторов. Каждый совет "
            "опирается на конкретный фрагмент из public-domain корпуса с указанием "
            "автора и издания. Если данных не хватает — честно говоришь об этом."
        ),
        safety_notes=(
            "Запрещены: написание чужих работ, обход ИИ-детекторов, тексты с "
            "ненавистью, разжигание, контент 18+, советы о самоповреждении."
        ),
    ),
    PromptCard(
        name="curator.week",
        purpose="Описание одной недели маршрута на 2 предложения.",
        audience="14–22 года",
        template=(
            "Книга: {book}. Жанр: {genre}. Тема: {theme}. Сделай два-три "
            "предложения о неделе чтения этой книги, без цитаты внутри ответа."
        ),
    ),
    PromptCard(
        name="curator.summary",
        purpose="Сводное описание маршрута (3 предложения), формирует ожидание у пользователя.",
        audience="14–22 года",
        template=(
            "Маршрут на 4 недели. Состав: {books}. Объясни ученику, почему такая "
            "последовательность, и что он получит к концу маршрута. Не более 3 "
            "предложений, без markdown."
        ),
    ),
    PromptCard(
        name="trainer.feedback",
        purpose="Обратная связь по неверному ответу в тренажёре.",
        audience="14–22 года",
        template=(
            "Ученик ответил «{answer}» на вопрос «{question}» — правильный ответ "
            "«{correct}». Объясни в одном-двух предложениях разницу, без сарказма."
        ),
    ),
]


@dataclass
class ModelCard:
    name: str = "ЧитАИ-Curator"
    version: str = "v0.2"
    intended_use: str = (
        "Помощь школьникам и студентам 14–22 лет в построении маршрутов чтения "
        "по русской классической литературе и культуре, с опорой на текст и цитаты."
    )
    not_intended_use: list[str] = field(
        default_factory=lambda: [
            "Написание сочинений, рефератов, дипломных работ за пользователя.",
            "Обход систем антиплагиата и ИИ-детекторов.",
            "Психологическая помощь в кризисных состояниях (даём контакт горячей линии).",
            "Юридические или медицинские консультации.",
        ]
    )
    primary_users: list[str] = field(
        default_factory=lambda: ["Школьники 5–11 классов", "Студенты 1–2 курса", "Учителя литературы", "Библиотекари"]
    )
    training_data: dict = field(
        default_factory=lambda: {
            "stack": ["YandexGPT 5 Pro", "GigaChat MAX"],
            "fine_tuning": False,
            "knowledge_base": "Public domain Russian literature corpus (см. /api/corpus/sources)",
            "data_origin": "Wikisource, ГИХЛ ПСС, Наука ПСС",
        }
    )
    metrics: dict = field(
        default_factory=lambda: {
            "retrieval_precision_at_5": "≥ 0.85 на эталонной выборке (см. /api/audit/evaluation)",
            "hallucination_rate": "≤ 0.06 при дисклеймере и опоре на цитаты",
            "refusal_rate_safety": "100% на ред-тим выборке (см. tests/test_safety.py)",
        }
    )
    limitations: list[str] = field(
        default_factory=lambda: [
            "Корпус ограничен public-domain произведениями РФ; современные авторы добавляются по соглашениям с правообладателями.",
            "LLM может галлюцинировать вокруг малоизвестных произведений; компенсируется обязательной цитатой и дисклеймером.",
            "Не работает на других естественных языках кроме русского (поддержка англ./татар./якут. — на дорожной карте).",
        ]
    )
    ethical_considerations: list[str] = field(
        default_factory=lambda: [
            "Соответствие 152-ФЗ: вся обработка ПД на территории РФ, см. /api/privacy/policy.",
            "Соответствие ст. 1281 ГК РФ: используются только произведения общественного достояния (70 лет после смерти автора).",
            "Возрастная маркировка: материалы делятся по школьным классам и возрастам (см. поле school_grade).",
            "Прозрачность: модель карта, реестр промптов и протокол отказов публично доступны.",
        ]
    )
    governance: dict = field(
        default_factory=lambda: {
            "owner": "ЧитАИ (заявка на регистрацию ОПД в Роскомнадзоре подана)",
            "operator_country": "RU",
            "compliance": ["152-ФЗ", "ст. 1281 ГК РФ", "ст. 6 ч. 1 п. 5 152-ФЗ"],
            "incident_contact": "trust@chitai.ru",
        }
    )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "intended_use": self.intended_use,
            "not_intended_use": list(self.not_intended_use),
            "primary_users": list(self.primary_users),
            "training_data": dict(self.training_data),
            "metrics": dict(self.metrics),
            "limitations": list(self.limitations),
            "ethical_considerations": list(self.ethical_considerations),
            "governance": dict(self.governance),
        }


_MODEL_CARD = ModelCard()


def get_model_card() -> ModelCard:
    return _MODEL_CARD


def get_prompts() -> list[PromptCard]:
    return list(PROMPTS)


# ── Хранилище последних результатов бенчмарка (in-memory + опциональный JSON)
@dataclass
class BenchmarkRecord:
    ts: str
    metrics: dict
    notes: str = ""

    def to_dict(self) -> dict:
        return {"ts": self.ts, "metrics": self.metrics, "notes": self.notes}


class _BenchStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._records: list[BenchmarkRecord] = []
        self._path = Path(os.environ.get("CHITAI_BENCHMARK_PATH", "")).expanduser() if os.environ.get("CHITAI_BENCHMARK_PATH") else None

    def add(self, rec: BenchmarkRecord) -> None:
        with self._lock:
            self._records.append(rec)
            if len(self._records) > 50:
                self._records = self._records[-50:]
            if self._path:
                try:
                    self._path.parent.mkdir(parents=True, exist_ok=True)
                    self._path.write_text(
                        json.dumps([r.to_dict() for r in self._records], ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                except OSError:
                    pass

    def latest(self) -> BenchmarkRecord | None:
        with self._lock:
            return self._records[-1] if self._records else None

    def all(self) -> list[BenchmarkRecord]:
        with self._lock:
            return list(self._records)

    def reset(self) -> None:
        with self._lock:
            self._records.clear()


_BENCH = _BenchStore()


def get_benchmark_store() -> _BenchStore:
    return _BENCH
