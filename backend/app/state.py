"""
Опциональная JSON-персистентность для in-memory сторов.

Контекст: в демо/CI сторы (privacy/srs/safety/benchmark) живут в памяти.
В production за ними стоит PostgreSQL, но между этими двумя крайностями есть
большой и реальный сценарий — Yandex Cloud demo с одним инстансом, где
рестарт не должен стирать журналы 152-ФЗ и SRS-карточки.

Контракт прост: каждый стор владеет одним JSON-файлом в `CHITAI_STATE_DIR`.
При старте стора (если каталог задан) он `load()` свой файл; на каждое
изменение он `save()` снапшот целиком. Для лога запросов и SRS этого достаточно.

Если `CHITAI_STATE_DIR` не задан — backend вырождается в no-op и режим
поведения совпадает с прежним (все тесты остаются зелёными).

Это НЕ замена базе данных. Это «не теряем данные при `systemctl restart`».
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)


class StateBackend:
    """JSON-файл per стор. Atomic write через tmp + os.replace."""

    def __init__(self, path: Path | None) -> None:
        self.path = path
        self._lock = Lock()

    @property
    def enabled(self) -> bool:
        return self.path is not None

    def load(self) -> Any | None:
        if self.path is None:
            return None
        if not self.path.exists():
            return None
        try:
            with self._lock:
                raw = self.path.read_text(encoding="utf-8")
            if not raw.strip():
                return None
            return json.loads(raw)
        except (OSError, ValueError) as exc:
            logger.warning("state: failed to load %s: %s", self.path, exc)
            return None

    def save(self, payload: Any) -> None:
        if self.path is None:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            data = json.dumps(payload, ensure_ascii=False, indent=2)
            with self._lock:
                # Atomic write: tmp + os.replace гарантирует целостность файла
                # даже при kill -9 в момент записи.
                fd, tmp_path = tempfile.mkstemp(
                    prefix=self.path.name + ".",
                    suffix=".tmp",
                    dir=str(self.path.parent),
                )
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as fh:
                        fh.write(data)
                    os.replace(tmp_path, self.path)
                except Exception:
                    # Уберём временный файл, если os.replace не сработал.
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass
                    raise
        except OSError as exc:
            logger.warning("state: failed to save %s: %s", self.path, exc)


def get_state_dir() -> Path | None:
    """Каталог из ENV `CHITAI_STATE_DIR`. None — значит persistence выключен."""
    raw = os.environ.get("CHITAI_STATE_DIR", "").strip()
    if not raw:
        return None
    return Path(raw).expanduser()


def get_state_backend(name: str) -> StateBackend:
    """Бэкенд для одного стора. Имя файла = `<name>.json`."""
    base = get_state_dir()
    if base is None:
        return StateBackend(None)
    return StateBackend(base / f"{name}.json")


# ---------------------------------------------------------------------------
# Простой KV-стор для лёгких модулей (challenge, quote_game и т.п.).
# Хранится в памяти; при наличии CHITAI_STATE_DIR — снэпшотится в `kv.json`.
# Это намеренно простая абстракция: нет TTL, нет конкуррентных транзакций,
# только put/get/del/iter. Для бо́льших сторов (privacy/srs/audit/safety)
# используется отдельный StateBackend с собственными контрактами.
# ---------------------------------------------------------------------------

_KV_LOCK = Lock()
_KV_DATA: dict[str, Any] = {}
_KV_BACKEND: StateBackend | None = None


def _kv_backend() -> StateBackend:
    global _KV_BACKEND
    if _KV_BACKEND is None:
        _KV_BACKEND = get_state_backend("kv")
        loaded = _KV_BACKEND.load()
        if isinstance(loaded, dict):
            _KV_DATA.update(loaded)
    return _KV_BACKEND


def get(key: str, default: Any = None) -> Any:
    """Прочитать ключ. Если нет — вернуть default (deep-копию)."""
    _kv_backend()
    with _KV_LOCK:
        value = _KV_DATA.get(key)
    if value is None:
        # Возвращаем deep-копию default'а, чтобы вызывающий код не мутировал
        # общий объект.
        if isinstance(default, dict | list):
            return json.loads(json.dumps(default))
        return default
    return value


def set_value(key: str, value: Any) -> None:
    """Записать ключ + (опционально) сохранить snapshot KV-стора на диск."""
    backend = _kv_backend()
    with _KV_LOCK:
        _KV_DATA[key] = value
        if backend.enabled:
            backend.save(dict(_KV_DATA))


def delete(key: str) -> None:
    """Удалить ключ (если есть). Snapshot обновится, если persistence включён."""
    backend = _kv_backend()
    with _KV_LOCK:
        if key in _KV_DATA:
            _KV_DATA.pop(key)
            if backend.enabled:
                backend.save(dict(_KV_DATA))


def keys() -> list[str]:
    """Список всех ключей KV-стора."""
    _kv_backend()
    with _KV_LOCK:
        return list(_KV_DATA.keys())


def reset_kv() -> None:
    """Очистить KV (используется тестами). Snapshot обновится на диске."""
    global _KV_BACKEND
    with _KV_LOCK:
        _KV_DATA.clear()
        if _KV_BACKEND is not None and _KV_BACKEND.enabled:
            _KV_BACKEND.save({})
    # Сбрасываем кэшированный backend, чтобы следующий get/set перечитал ENV.
    _KV_BACKEND = None
