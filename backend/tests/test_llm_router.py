"""Тесты LLM-роутера и провайдеров.

Все провайдеры тестируются через respx (mock httpx) — реальная сеть не нужна.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from app.llm import (
    GigaChatProvider,
    LLMError,
    LLMMessage,
    LLMRouter,
    MockProvider,
    YandexGPTProvider,
)
from app.llm.router import reset_router


@pytest.fixture(autouse=True)
def _reset_router_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    """Изолируем тесты от .env: чистые ключи + сброс singleton-роутера."""
    for var in (
        "YANDEX_GPT_API_KEY",
        "YANDEX_GPT_FOLDER_ID",
        "YANDEX_GPT_MODEL",
        "GIGACHAT_AUTHORIZATION_KEY",
        "GIGACHAT_SCOPE",
        "GIGACHAT_MODEL",
        "LLM_PRIMARY",
    ):
        monkeypatch.delenv(var, raising=False)
    reset_router()


def _msgs() -> list[LLMMessage]:
    return [
        LLMMessage(role="system", content="Ты — куратор."),
        LLMMessage(role="user", content="Расскажи про «Капитанскую дочку»."),
    ]


# ======================== MockProvider ========================


@pytest.mark.asyncio
async def test_mock_provider_always_configured() -> None:
    p = MockProvider()
    assert await p.is_configured() is True


@pytest.mark.asyncio
async def test_mock_provider_returns_deterministic_response() -> None:
    p = MockProvider()
    r1 = await p.complete(_msgs())
    r2 = await p.complete(_msgs())
    assert r1.text == r2.text
    assert r1.provider == "mock"
    assert r1.model == "chitai-mock-v1"
    assert "Маршрут собран по запросу" in r1.text
    assert r1.total_tokens > 0


@pytest.mark.asyncio
async def test_mock_provider_handles_empty_messages() -> None:
    p = MockProvider()
    r = await p.complete([])
    assert r.text
    assert r.provider == "mock"


# ======================== YandexGPTProvider ========================


@pytest.mark.asyncio
async def test_yandex_not_configured_without_keys() -> None:
    p = YandexGPTProvider(api_key="", folder_id="")
    assert await p.is_configured() is False
    with pytest.raises(LLMError, match="missing"):
        await p.complete(_msgs())


@pytest.mark.asyncio
async def test_yandex_model_uri_handles_short_form() -> None:
    p = YandexGPTProvider(api_key="k", folder_id="b1g_test", model="yandexgpt/latest")
    assert p._model_uri() == "gpt://b1g_test/yandexgpt/latest"


@pytest.mark.asyncio
async def test_yandex_model_uri_passes_through_full_uri() -> None:
    p = YandexGPTProvider(api_key="k", folder_id="b1g", model="gpt://other/model/rc")
    assert p._model_uri() == "gpt://other/model/rc"


@pytest.mark.asyncio
@respx.mock
async def test_yandex_complete_happy_path() -> None:
    respx.post("https://llm.api.cloud.yandex.net/foundationModels/v1/completion").mock(
        return_value=httpx.Response(
            200,
            json={
                "result": {
                    "alternatives": [{"message": {"role": "assistant", "text": "Краткий ответ."}}],
                    "usage": {
                        "inputTextTokens": "12",
                        "completionTokens": "3",
                        "totalTokens": "15",
                    },
                    "modelVersion": "yandexgpt-5-pro",
                }
            },
        )
    )
    p = YandexGPTProvider(api_key="k", folder_id="b1g_x", model="yandexgpt/latest")
    r = await p.complete(_msgs(), max_tokens=200)
    assert r.text == "Краткий ответ."
    assert r.provider == "yandex"
    assert r.model == "yandexgpt-5-pro"
    assert r.prompt_tokens == 12
    assert r.completion_tokens == 3
    assert r.total_tokens == 15


@pytest.mark.asyncio
@respx.mock
async def test_yandex_4xx_no_retry() -> None:
    route = respx.post("https://llm.api.cloud.yandex.net/foundationModels/v1/completion").mock(
        return_value=httpx.Response(403, text="permission denied")
    )
    p = YandexGPTProvider(api_key="k", folder_id="b1g", max_retries=2)
    with pytest.raises(LLMError, match="403"):
        await p.complete(_msgs())
    assert route.call_count == 1  # без ретраев


@pytest.mark.asyncio
@respx.mock
async def test_yandex_5xx_retries_then_succeeds() -> None:
    route = respx.post("https://llm.api.cloud.yandex.net/foundationModels/v1/completion").mock(
        side_effect=[
            httpx.Response(503, text="upstream busy"),
            httpx.Response(
                200,
                json={
                    "result": {
                        "alternatives": [{"message": {"role": "assistant", "text": "Готово."}}],
                        "usage": {},
                        "modelVersion": "yandexgpt",
                    }
                },
            ),
        ]
    )
    p = YandexGPTProvider(api_key="k", folder_id="b1g", max_retries=2)
    r = await p.complete(_msgs())
    assert r.text == "Готово."
    assert route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_yandex_empty_alternatives_raises() -> None:
    respx.post("https://llm.api.cloud.yandex.net/foundationModels/v1/completion").mock(
        return_value=httpx.Response(200, json={"result": {"alternatives": []}})
    )
    p = YandexGPTProvider(api_key="k", folder_id="b1g")
    with pytest.raises(LLMError, match="empty"):
        await p.complete(_msgs())


# ======================== GigaChatProvider ========================


@pytest.mark.asyncio
async def test_gigachat_not_configured_without_keys() -> None:
    # scope="" хитрый: `or` в __init__ подхватывает дефолт из ENV/фабрики.
    # Для чистого теста проверяем без authorization_key — этого достаточно.
    p = GigaChatProvider(authorization_key="", scope="GIGACHAT_API_PERS")
    assert await p.is_configured() is False


@pytest.mark.asyncio
@respx.mock
async def test_gigachat_oauth_then_chat_happy_path() -> None:
    respx.post("https://ngw.devices.sberbank.ru:9443/api/v2/oauth").mock(
        return_value=httpx.Response(
            200,
            json={"access_token": "sber.tok.123", "expires_at": 0},
        )
    )
    respx.post("https://gigachat.devices.sberbank.ru/api/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [{"message": {"role": "assistant", "content": "Пушкин — поэт."}}],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 4,
                    "total_tokens": 14,
                },
                "model": "GigaChat-Max:2.0",
            },
        )
    )
    p = GigaChatProvider(authorization_key="key", scope="GIGACHAT_API_PERS")
    r = await p.complete(_msgs())
    assert r.text == "Пушкин — поэт."
    assert r.provider == "gigachat"
    assert r.model == "GigaChat-Max:2.0"
    assert r.total_tokens == 14
    # Токен закэширован, второй вызов не дёргает oauth повторно.
    assert p._access_token == "sber.tok.123"


@pytest.mark.asyncio
@respx.mock
async def test_gigachat_oauth_failure_raises() -> None:
    respx.post("https://ngw.devices.sberbank.ru:9443/api/v2/oauth").mock(
        return_value=httpx.Response(401, text="bad authorization key")
    )
    p = GigaChatProvider(authorization_key="bad", scope="GIGACHAT_API_PERS")
    with pytest.raises(LLMError, match="oauth 401"):
        await p.complete(_msgs())


@pytest.mark.asyncio
@respx.mock
async def test_gigachat_token_refresh_on_401() -> None:
    respx.post("https://ngw.devices.sberbank.ru:9443/api/v2/oauth").mock(
        side_effect=[
            httpx.Response(200, json={"access_token": "tok.old"}),
            httpx.Response(200, json={"access_token": "tok.new"}),
        ]
    )
    respx.post("https://gigachat.devices.sberbank.ru/api/v1/chat/completions").mock(
        side_effect=[
            httpx.Response(401, text="token expired"),
            httpx.Response(
                200,
                json={
                    "choices": [{"message": {"role": "assistant", "content": "Ответ"}}],
                    "usage": {},
                    "model": "GigaChat-Max",
                },
            ),
        ]
    )
    p = GigaChatProvider(authorization_key="key", scope="GIGACHAT_API_PERS", max_retries=2)
    r = await p.complete(_msgs())
    assert r.text == "Ответ"
    assert p._access_token == "tok.new"


# ======================== LLMRouter ========================


@pytest.mark.asyncio
async def test_router_uses_primary_when_configured() -> None:
    primary = MockProvider()
    secondary = MockProvider()
    router = LLMRouter(primary=primary, secondary=secondary, fallback=MockProvider())
    r = await router.complete(_msgs())
    assert r.provider == "mock"


@pytest.mark.asyncio
async def test_router_falls_back_when_primary_not_configured() -> None:
    primary = YandexGPTProvider(api_key="", folder_id="")  # not configured
    secondary = MockProvider()
    router = LLMRouter(primary=primary, secondary=secondary)
    r = await router.complete(_msgs())
    assert r.provider == "mock"


@pytest.mark.asyncio
@respx.mock
async def test_router_falls_back_to_secondary_on_primary_5xx() -> None:
    respx.post("https://llm.api.cloud.yandex.net/foundationModels/v1/completion").mock(
        return_value=httpx.Response(503, text="bad gateway")
    )
    respx.post("https://ngw.devices.sberbank.ru:9443/api/v2/oauth").mock(
        return_value=httpx.Response(200, json={"access_token": "t"})
    )
    respx.post("https://gigachat.devices.sberbank.ru/api/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "GigaChat-ответ"}}],
                "usage": {},
                "model": "GigaChat-Max",
            },
        )
    )
    primary = YandexGPTProvider(api_key="k", folder_id="b1g", max_retries=0)
    secondary = GigaChatProvider(authorization_key="key", scope="GIGACHAT_API_PERS")
    router = LLMRouter(primary=primary, secondary=secondary)
    r = await router.complete(_msgs())
    assert r.provider == "gigachat"
    assert r.text == "GigaChat-ответ"


@pytest.mark.asyncio
async def test_router_falls_back_to_mock_when_both_fail() -> None:
    primary = YandexGPTProvider(api_key="", folder_id="")
    secondary = GigaChatProvider(authorization_key="", scope="GIGACHAT_API_PERS")
    router = LLMRouter(primary=primary, secondary=secondary)
    r = await router.complete(_msgs())
    assert r.provider == "mock"
    # Прозрачный лог: причины фолбэка попадают в raw.
    reasons = r.raw.get("fallback_reasons", [])
    assert any("yandex" in s and "not_configured" in s for s in reasons)
    assert any("gigachat" in s and "not_configured" in s for s in reasons)


@pytest.mark.asyncio
async def test_router_status_no_secrets_leaked() -> None:
    primary = YandexGPTProvider(
        api_key="leak_key_value", folder_id="leak_folder", model="yandexgpt/latest"
    )
    secondary = GigaChatProvider(authorization_key="leak_basic_value", scope="GIGACHAT_API_PERS")
    router = LLMRouter(primary=primary, secondary=secondary)
    s = await router.status()
    blob = repr(s)
    assert "leak_key_value" not in blob
    assert "leak_folder" not in blob
    assert "leak_basic_value" not in blob
    # Структура корректная.
    names = [p["name"] for p in s["providers"]]
    assert "yandex" in names
    assert "gigachat" in names
    assert s["fallback"]["name"] == "mock"


def test_router_from_env_default_primary_yandex(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_PRIMARY", raising=False)
    monkeypatch.setenv("YANDEX_GPT_API_KEY", "k")
    monkeypatch.setenv("YANDEX_GPT_FOLDER_ID", "b1g")
    monkeypatch.setenv("GIGACHAT_AUTHORIZATION_KEY", "g")
    router = LLMRouter.from_env()
    assert router.primary.name == "yandex"
    assert router.secondary.name == "gigachat"


def test_router_from_env_can_swap_to_gigachat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_PRIMARY", "gigachat")
    router = LLMRouter.from_env()
    assert router.primary.name == "gigachat"
    assert router.secondary.name == "yandex"
