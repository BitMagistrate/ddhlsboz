"""
Наблюдаемость ЧитАИ: метрики Prometheus-совместимые + структурированный лог.

Зависимости минимальны: in-process Counter/Histogram без `prometheus_client`,
чтобы CI и offline-демо не тащили лишних пакетов. Эндпоинт `/metrics`
отдаёт текст в формате `text/plain; version=0.0.4`, его читает любой Prometheus
scrape без модификаций.

Что закрывается:
* E6 из master TODO — дашборд продукта в реальном времени.
* AI-audit-ready (F4) — counter отказов, p95 латентности.
* Открытость для жюри: можно пройти со scrape-таргетом и показать живые цифры.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections import defaultdict
from contextvars import ContextVar
from dataclasses import dataclass, field
from threading import Lock

REQUEST_ID: ContextVar[str] = ContextVar("request_id", default="-")


@dataclass
class Histogram:
    buckets_le: tuple[float, ...] = (
        0.05,
        0.1,
        0.25,
        0.5,
        1.0,
        2.0,
        5.0,
        10.0,
        30.0,
    )
    counts: dict[float, int] = field(default_factory=lambda: defaultdict(int))
    inf: int = 0
    sum: float = 0.0
    n: int = 0

    def observe(self, value: float) -> None:
        for b in self.buckets_le:
            if value <= b:
                self.counts[b] += 1
        self.inf += 1
        self.sum += value
        self.n += 1


class Metrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self.counters: dict[tuple[str, tuple[tuple[str, str], ...]], int] = defaultdict(int)
        self.histograms: dict[tuple[str, tuple[tuple[str, str], ...]], Histogram] = defaultdict(
            Histogram
        )
        self.gauges: dict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)

    def _key(self, name: str, labels: dict[str, str] | None) -> tuple:
        if labels:
            return (name, tuple(sorted(labels.items())))
        return (name, ())

    def inc(self, name: str, labels: dict[str, str] | None = None, value: int = 1) -> None:
        with self._lock:
            self.counters[self._key(name, labels)] += value

    def counter(
        self, name: str, value: float = 1.0, labels: dict[str, str] | None = None
    ) -> None:
        """Удобный фасад для добавления значения в счётчик (alias для inc).

        Подчёркивает Prometheus-семантику и принимает аргументы в порядке
        (name, value, labels), как у клиентских библиотек.
        """
        with self._lock:
            self.counters[self._key(name, labels)] += int(value)

    def observe(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        with self._lock:
            self.histograms[self._key(name, labels)].observe(value)

    def set_gauge(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        with self._lock:
            self.gauges[self._key(name, labels)] = value

    def render_prometheus(self) -> str:
        """Сериализация в формате Prometheus exposition format 0.0.4."""
        lines: list[str] = []
        with self._lock:
            for (name, label_pairs), val in sorted(self.counters.items()):
                lines.append(f"# TYPE {name} counter")
                lines.append(f"{name}{_fmt_labels(label_pairs)} {val}")
            for (name, label_pairs), val in sorted(self.gauges.items()):
                lines.append(f"# TYPE {name} gauge")
                lines.append(f"{name}{_fmt_labels(label_pairs)} {val}")
            for (name, label_pairs), hist in sorted(self.histograms.items()):
                lines.append(f"# TYPE {name} histogram")
                cumulative = 0
                for b in hist.buckets_le:
                    cumulative += hist.counts.get(b, 0)
                    bucket_labels = label_pairs + (("le", _le_str(b)),)
                    lines.append(f"{name}_bucket{_fmt_labels(bucket_labels)} {cumulative}")
                inf_labels = label_pairs + (("le", "+Inf"),)
                lines.append(f"{name}_bucket{_fmt_labels(inf_labels)} {hist.inf}")
                lines.append(f"{name}_count{_fmt_labels(label_pairs)} {hist.n}")
                lines.append(f"{name}_sum{_fmt_labels(label_pairs)} {hist.sum:.6f}")
        return "\n".join(lines) + "\n"

    def reset(self) -> None:
        with self._lock:
            self.counters.clear()
            self.histograms.clear()
            self.gauges.clear()


def _fmt_labels(pairs: tuple[tuple[str, str], ...]) -> str:
    if not pairs:
        return ""
    inner = ",".join(f'{k}="{_escape(v)}"' for k, v in pairs)
    return "{" + inner + "}"


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _le_str(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return f"{value:g}"


_METRICS = Metrics()


def get_metrics() -> Metrics:
    return _METRICS


class JsonLogFormatter(logging.Formatter):
    """JSON-форматтер: structured logs для ELK/Loki + request_id."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": REQUEST_ID.get(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        # пробрасываем custom-поля, добавленные через extra=
        for key, val in record.__dict__.items():
            if key in (
                "args",
                "asctime",
                "created",
                "exc_info",
                "exc_text",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "message",
                "module",
                "msecs",
                "msg",
                "name",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "stack_info",
                "thread",
                "threadName",
                "taskName",
            ):
                continue
            payload[key] = val
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: int = logging.INFO, *, json: bool = True) -> None:
    """Настраивает root logger. Вызывается один раз при старте FastAPI."""
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    handler = logging.StreamHandler()
    if json:
        handler.setFormatter(JsonLogFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root.addHandler(handler)
    root.setLevel(level)


def new_request_id() -> str:
    rid = uuid.uuid4().hex[:16]
    REQUEST_ID.set(rid)
    return rid


def set_request_id(rid: str) -> None:
    """Принудительно фиксирует request_id в текущем контексте."""
    REQUEST_ID.set(rid)


def get_request_id() -> str:
    return REQUEST_ID.get()
