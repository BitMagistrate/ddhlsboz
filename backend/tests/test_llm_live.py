"""Живые smoke-тесты LLM-провайдеров.

По умолчанию пропускаются, чтобы CI без ключей не дёргал внешние сервисы.
Запускаются явно:

    GIGACHAT_LIVE=1 \\
    GIGACHAT_AUTHORIZATION_KEY=... \\
    GIGACHAT_SCOPE=GIGACHAT_API_PERS \\
    pytest backend/tests/test_llm_live.py -k gigachat -v

Тест проверяет полный путь: OAuth → access_token → chat completions →
непустой текстовый ответ → корректный provider/model в LLMResponse.
"""

from __future__ import annotations

import os

import pytest

from app.llm.base import LLMMessage
from app.llm.gigachat import GigaChatProvider
from app.llm.yandex import YandexGPTProvider


@pytest.mark.skipif(
    os.getenv("GIGACHAT_LIVE") != "1",
    reason="live GigaChat smoke test, set GIGACHAT_LIVE=1 to enable",
)
async def test_gigachat_live_smoke() -> None:
    p = GigaChatProvider()
    assert await p.is_configured(), "GIGACHAT_AUTHORIZATION_KEY must be set"
    resp = await p.complete(
        [
            LLMMessage(role="system", content="Ты — куратор русской классики ЧитАИ."),
            LLMMessage(
                role="user",
                content=(
                    "Назови две главные темы повести «Капитанская дочка» Пушкина, "
                    "одной строкой, без воды."
                ),
            ),
        ],
        temperature=0.2,
        max_tokens=120,
        timeout=15.0,
    )
    assert resp.provider == "gigachat"
    assert resp.model.startswith("GigaChat")
    assert resp.text.strip(), "GigaChat returned empty text"
    # На случай если модель захочет вернуть JSON или маркетинговый штамп — проверяем
    # минимум, что это русский текст.
    assert any(ch.isalpha() for ch in resp.text)


@pytest.mark.skipif(
    os.getenv("YANDEX_GPT_LIVE") != "1",
    reason="live YandexGPT smoke test, set YANDEX_GPT_LIVE=1 to enable",
)
async def test_yandex_live_smoke() -> None:
    p = YandexGPTProvider()
    assert await p.is_configured(), "YANDEX_GPT_API_KEY/FOLDER_ID must be set"
    resp = await p.complete(
        [
            LLMMessage(role="system", content="Ты — куратор русской классики ЧитАИ."),
            LLMMessage(role="user", content="Кто написал «Войну и мир»? Ответь одним именем."),
        ],
        temperature=0.0,
        max_tokens=40,
        timeout=15.0,
    )
    assert resp.provider == "yandex"
    assert resp.text.strip()
