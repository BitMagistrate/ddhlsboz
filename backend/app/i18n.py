"""
i18n.py — i18n каркас для ЧитАИ (ru / tt / ba).

Минимальный словарь UI-строк, чтобы фронт мог запросить
`/api/i18n?locale=tt` и получить перевод. Татарский и башкирский
заполнены ключевыми фразами интерфейса; остальное падает в ru.
"""

from __future__ import annotations

SUPPORTED_LOCALES = ("ru", "tt", "ba")
DEFAULT_LOCALE = "ru"

# Только то, что точно нужно UI. Остальное переводим по мере роста.
DICTIONARY: dict[str, dict[str, str]] = {
    "app.tagline": {
        "ru": "ИИ-куратор русского культурного и образовательного контента",
        "tt": "Рус мәдәни һәм мәгариф эчтәлеген ИИ-курәтуче",
        "ba": "Рус мәҙәни һәм мәғариф материалдары ИИ-куратор",
    },
    "nav.curator": {"ru": "Маршрут", "tt": "Маршрут", "ba": "Маршрут"},
    "nav.search": {"ru": "Поиск", "tt": "Эзләү", "ba": "Эҙләү"},
    "nav.mindmap": {"ru": "Карта тем", "tt": "Тема картасы", "ba": "Тема картаһы"},
    "nav.trainer": {"ru": "Тренажёр", "tt": "Тренажер", "ba": "Тренажер"},
    "nav.pushkin": {"ru": "Пушкинская карта", "tt": "Пушкин картасы", "ba": "Пушкин картаһы"},
    "nav.dashboard": {"ru": "Дашборд", "tt": "Идарә", "ba": "Идара"},
    "nav.about": {"ru": "О проекте", "tt": "Проект турында", "ba": "Проект тураһында"},
    "btn.build_route": {
        "ru": "Построить маршрут",
        "tt": "Маршрут төзергә",
        "ba": "Маршрут төҙөргә",
    },
    "btn.search": {"ru": "Искать", "tt": "Эзләргә", "ba": "Эҙләргә"},
    "btn.show_answer": {
        "ru": "Показать ответ",
        "tt": "Җавапны күрсәтергә",
        "ba": "Яуап күрһәтергә",
    },
    "label.region": {"ru": "Регион", "tt": "Төбәк", "ba": "Төбәк"},
    "label.privacy": {
        "ru": "Согласие на обработку (152-ФЗ)",
        "tt": "Эшкәртүгә ризалык (152-ФЗ)",
        "ba": "Эшкәртеүгә риза­лыҡ (152-ФЗ)",
    },
}


def _normalize(locale: str | None) -> str:
    if not locale:
        return DEFAULT_LOCALE
    norm = locale.strip().lower().split("-", 1)[0]
    return norm if norm in SUPPORTED_LOCALES else DEFAULT_LOCALE


def resolve(locale: str | None) -> dict[str, str]:
    """Возвращает словарь для указанной локали (ru-fallback по умолчанию)."""
    norm = _normalize(locale)
    out = {}
    for key, values in DICTIONARY.items():
        out[key] = values.get(norm) or values.get(DEFAULT_LOCALE) or key
    return out


def locales() -> dict:
    """Метаданные о доступных локалях для UI."""
    return {
        "default": DEFAULT_LOCALE,
        "supported": [
            {"code": "ru", "label": "Русский"},
            {"code": "tt", "label": "Татарча"},
            {"code": "ba", "label": "Башҡортса"},
        ],
        "coverage": {
            "ru": 1.0,
            "tt": sum(1 for v in DICTIONARY.values() if "tt" in v) / len(DICTIONARY),
            "ba": sum(1 for v in DICTIONARY.values() if "ba" in v) / len(DICTIONARY),
        },
    }
