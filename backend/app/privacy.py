"""
152-ФЗ: согласие, экспорт данных, право на забвение.

Что закрывает:
* E1 из master TODO — публичная политика приватности и API.
* Жюри Нейрофеста: «работа с детьми + 152-ФЗ — критическая зона».
* Differentiation от zachet.tech: у них нет ни одной страницы про обработку
  персданных, у нас — полностью документированный жизненный цикл данных.

Реализация — in-memory словарь с опциональной JSON-персистентностью на диск
(env `CHITAI_STATE_DIR`). Когда переменная задана, store автоматически
загружается на старте и пишется на каждое изменение. В production —
PostgreSQL (см. /05_Юр_пакет/152fz_dpia.md), контракт идентичный.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from threading import Lock

from .state import StateBackend, get_state_backend

CONSENT_PURPOSES = (
    "service_delivery",       # обязательная: сборка маршрутов, история
    "analytics_aggregated",   # опциональная: обезличенная аналитика
    "personalization",        # опциональная: рекомендации
    "marketing",              # опциональная: рассылки
    "research",               # опциональная: участие в исследованиях
)


@dataclass
class ConsentRecord:
    user_id: str
    purpose: str
    granted: bool
    ts: float
    revoked_ts: float | None = None
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "purpose": self.purpose,
            "granted": self.granted,
            "ts": self.ts,
            "revoked_ts": self.revoked_ts,
            "notes": self.notes,
        }


@dataclass
class UserProfile:
    user_id: str
    role: str = "student"
    age_group: str = "14-22"
    region: str = "RU-MOW"
    created_ts: float = field(default_factory=lambda: time.time())
    history: list[dict] = field(default_factory=list)
    consents: list[ConsentRecord] = field(default_factory=list)
    deleted: bool = False

    def to_dict(self, *, include_history: bool = True) -> dict:
        out = {
            "user_id": self.user_id,
            "role": self.role,
            "age_group": self.age_group,
            "region": self.region,
            "created_ts": self.created_ts,
            "deleted": self.deleted,
            "consents": [c.to_dict() for c in self.consents],
        }
        if include_history:
            out["history"] = list(self.history)
        return out


class PrivacyStore:
    def __init__(self, backend: StateBackend | None = None) -> None:
        self._lock = Lock()
        self._users: dict[str, UserProfile] = {}
        self._backend = backend or get_state_backend("privacy")
        self._load_unlocked()

    # ── persistence helpers ─────────────────────────────────────────────
    def _serialize_unlocked(self) -> dict:
        return {
            "version": 1,
            "users": [profile.to_dict() for profile in self._users.values()],
        }

    def _load_unlocked(self) -> None:
        if not self._backend.enabled:
            return
        payload = self._backend.load()
        if not isinstance(payload, dict):
            return
        users = payload.get("users") or []
        for raw in users:
            try:
                profile = UserProfile(
                    user_id=str(raw["user_id"]),
                    role=str(raw.get("role", "student")),
                    age_group=str(raw.get("age_group", "14-22")),
                    region=str(raw.get("region", "RU-MOW")),
                    created_ts=float(raw.get("created_ts", time.time())),
                    history=list(raw.get("history") or []),
                    consents=[
                        ConsentRecord(
                            user_id=str(c["user_id"]),
                            purpose=str(c["purpose"]),
                            granted=bool(c["granted"]),
                            ts=float(c["ts"]),
                            revoked_ts=(float(c["revoked_ts"]) if c.get("revoked_ts") is not None else None),
                            notes=str(c.get("notes", "")),
                        )
                        for c in (raw.get("consents") or [])
                    ],
                    deleted=bool(raw.get("deleted", False)),
                )
                self._users[profile.user_id] = profile
            except (KeyError, ValueError, TypeError):
                # один битый юзер не должен ронять весь стор.
                continue

    def _flush_unlocked(self) -> None:
        if self._backend.enabled:
            self._backend.save(self._serialize_unlocked())

    # ── public API ──────────────────────────────────────────────────────
    def get_or_create(self, user_id: str) -> UserProfile:
        with self._lock:
            if user_id not in self._users:
                self._users[user_id] = UserProfile(user_id=user_id)
                self._flush_unlocked()
            return self._users[user_id]

    def set_consent(
        self, user_id: str, purpose: str, granted: bool, notes: str = ""
    ) -> ConsentRecord:
        if purpose not in CONSENT_PURPOSES:
            raise ValueError(f"unknown purpose: {purpose}")
        with self._lock:
            profile = self._users.setdefault(user_id, UserProfile(user_id=user_id))
            now = time.time()
            # отзыв предыдущей записи с той же целью
            for c in profile.consents:
                if c.purpose == purpose and c.granted and c.revoked_ts is None:
                    c.revoked_ts = now
            rec = ConsentRecord(
                user_id=user_id, purpose=purpose, granted=granted, ts=now, notes=notes
            )
            profile.consents.append(rec)
            self._flush_unlocked()
            return rec

    def has_consent(self, user_id: str, purpose: str) -> bool:
        with self._lock:
            profile = self._users.get(user_id)
            if not profile:
                return False
            for c in reversed(profile.consents):
                if c.purpose != purpose:
                    continue
                if c.revoked_ts is not None:
                    return False
                return c.granted
            return False

    def list_consents(self, user_id: str) -> list[ConsentRecord]:
        """Полная история согласий пользователя (включая отозванные).

        Контракт: список упорядочен от старых к новым. Если профиля нет —
        возвращаем пустой список вместо 404, чтобы фронт мог рендерить
        форму со значениями по умолчанию.
        """
        with self._lock:
            profile = self._users.get(user_id)
            if not profile:
                return []
            return list(profile.consents)

    def append_history(self, user_id: str, event: dict) -> None:
        with self._lock:
            profile = self._users.setdefault(user_id, UserProfile(user_id=user_id))
            if profile.deleted:
                return
            profile.history.append(event)
            # ограничим разумным окном чтобы in-memory store не рос бесконечно.
            if len(profile.history) > 500:
                profile.history = profile.history[-500:]
            self._flush_unlocked()

    def export(self, user_id: str) -> dict:
        with self._lock:
            profile = self._users.get(user_id)
            if not profile:
                return {"user_id": user_id, "found": False}
            return {"user_id": user_id, "found": True, "data": profile.to_dict()}

    def forget(self, user_id: str) -> dict:
        """Право на забвение (152-ФЗ ст. 14). Удаляет историю, оставляет
        обезличенный аудит-стаб для подтверждения исполнения запроса."""
        with self._lock:
            profile = self._users.get(user_id)
            if not profile:
                return {"user_id": user_id, "deleted": False, "reason": "not_found"}
            stub_id = f"deleted-{uuid.uuid4().hex[:12]}"
            # ВАЖНО: stub-профиль кладём под `stub_id`, не под `user_id`,
            # иначе `del self._users[user_id]` стирал и стаб тоже (был баг).
            self._users[stub_id] = UserProfile(
                user_id=stub_id,
                role="deleted",
                age_group="-",
                region="-",
                deleted=True,
            )
            del self._users[user_id]
            self._flush_unlocked()
            return {"user_id": user_id, "deleted": True, "audit_stub": stub_id}

    def reset(self) -> None:
        with self._lock:
            self._users.clear()
            self._flush_unlocked()


_STORE = PrivacyStore()


def get_store() -> PrivacyStore:
    return _STORE


def reset_store_for_testing() -> None:
    """Тесты переопределяют env CHITAI_STATE_DIR, и им нужен свежий стор
    с пере-открытым backend. На проде не вызывается."""
    global _STORE
    _STORE = PrivacyStore()


def policy_summary() -> dict:
    """Публичная сводка политики обработки персданных. Машиночитаема для аудитов."""
    return {
        "law": "152-ФЗ «О персональных данных»",
        "data_localization": "Все данные обрабатываются и хранятся на территории РФ (Yandex Cloud, дата-центры в Москве и Владимире).",
        "operator": {
            "name": "ЧитАИ (заявка на регистрацию ОПД в Роскомнадзоре подана)",
            "contact_email": "privacy@chitai.ru",
            "dpo_contact": "dpo@chitai.ru",
        },
        "lawful_bases": ["Согласие субъекта (ст. 6 ч. 1 п. 1)", "Договор (ст. 6 ч. 1 п. 5)"],
        "purposes": [
            {"id": "service_delivery", "required": True, "description": "Сборка персонального маршрута чтения, сохранение прогресса."},
            {"id": "personalization", "required": False, "description": "Подбор рекомендаций под уровень и интерес."},
            {"id": "analytics_aggregated", "required": False, "description": "Обезличенная продуктовая аналитика."},
            {"id": "marketing", "required": False, "description": "Информационные рассылки (только по согласию)."},
            {"id": "research", "required": False, "description": "Анонимные данные для исследований культурного поведения молодёжи."},
        ],
        "data_minimization": [
            "Не собираем номера телефонов и адреса до момента оплаты.",
            "Профиль ребёнка/подростка <14 лет создаётся только при участии родителя (ст. 9 ч. 4).",
            "Тексты пользовательских заметок шифруются at-rest (AES-256).",
        ],
        "rights": [
            "Право на доступ (GET /api/privacy/export?user_id=...)",
            "Право на забвение (POST /api/privacy/forget)",
            "Право на отзыв согласия (POST /api/privacy/consent с granted=false)",
            "Право на исправление данных",
        ],
        "retention": {
            "default_days": 365,
            "after_account_close_days": 30,
            "audit_log_years": 5,
        },
        "subprocessors": [
            {"name": "Yandex Cloud", "country": "RU", "purpose": "Hosting + LLM"},
            {"name": "СберТех (GigaChat)", "country": "RU", "purpose": "LLM secondary"},
        ],
        "international_transfer": False,
        "version": "v0.1-2026-05-08",
    }
