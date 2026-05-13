"""
ЧитАИ — мульти-канальное ядро ботов.

Этот пакет НЕ заменяет существующий `bot/` (Telegram, aiogram 3.x),
а лежит рядом и подключается, когда нужны новые каналы — MAX, VK Сообщества,
веб-чат на сайте, Alice. Существующий Telegram-бот продолжает работать
в проде без изменений и без новых зависимостей.

Дизайн:
- `core.Channel` — абстракция канала (send_text, send_buttons, send_image).
- `core.Incoming` — нормализованное входящее сообщение (text + buttons + user_id).
- `core.Router` — простой dispatch по intent-у.
- `core.ChitaiClient` — обёртка над backend-эндпоинтами (общая для всех каналов).
- `adapters.*` — конкретные реализации каналов (telegram/max/vk/web).

Контракт обратной совместимости: существующие 9 тестов в `bot/tests/`
остаются без изменений; этот пакет тестируется отдельно в `bots/tests/`.
"""

from .core import (
    BUTTON_TEMPLATES,
    Button,
    Channel,
    ChannelKind,
    ChitaiClient,
    Incoming,
    Outgoing,
    Router,
    intent_for_text,
)

__all__ = [
    "BUTTON_TEMPLATES",
    "Button",
    "Channel",
    "ChannelKind",
    "ChitaiClient",
    "Incoming",
    "Outgoing",
    "Router",
    "intent_for_text",
]
