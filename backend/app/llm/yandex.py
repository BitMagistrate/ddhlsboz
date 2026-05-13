"""YandexGPT 5 Pro / Lite адаптер.

Аутентификация: API-ключ из Yandex AI Studio (`Authorization: Api-Key ...`).
Документация: https://yandex.cloud/ru/docs/foundation-models/concepts/api-key
"""

from __future__ import annotations

import os

import httpx

from .base import LLMError, LLMMessage, LLMProvider, LLMResponse

DEFAULT_ENDPOINT = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"


class YandexGPTProvider(LLMProvider):
    """Реальный YandexGPT через Foundation Models API."""

    name = "yandex"

    def __init__(
        self,
        api_key: str | None = None,
        folder_id: str | None = None,
        model: str | None = None,
        endpoint: str = DEFAULT_ENDPOINT,
        default_timeout: float = 20.0,
        max_retries: int = 2,
    ) -> None:
        self.api_key = api_key or os.getenv("YANDEX_GPT_API_KEY", "")
        self.folder_id = folder_id or os.getenv("YANDEX_GPT_FOLDER_ID", "")
        self.model = model or os.getenv("YANDEX_GPT_MODEL", "yandexgpt/latest")
        self.endpoint = endpoint
        self.default_timeout = default_timeout
        self.max_retries = max_retries

    async def is_configured(self) -> bool:
        return bool(self.api_key) and bool(self.folder_id)

    def _model_uri(self) -> str:
        # Поддерживаем форматы:
        #   "yandexgpt/latest"  -> "gpt://<folder>/yandexgpt/latest"
        #   "gpt://..."         -> как есть
        if self.model.startswith("gpt://"):
            return self.model
        return f"gpt://{self.folder_id}/{self.model}"

    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.3,
        max_tokens: int = 400,
        timeout: float | None = None,
    ) -> LLMResponse:
        if not await self.is_configured():
            raise LLMError("yandex: API key or folder_id missing")
        payload = {
            "modelUri": self._model_uri(),
            "completionOptions": {
                "stream": False,
                "temperature": float(temperature),
                "maxTokens": int(max_tokens),
            },
            "messages": [m.to_yandex() for m in messages],
        }
        headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "Content-Type": "application/json",
        }
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=timeout or self.default_timeout) as client:
                    resp = await client.post(self.endpoint, headers=headers, json=payload)
                    if resp.status_code >= 500:
                        raise LLMError(f"yandex 5xx: {resp.status_code} {resp.text[:200]}")
                    if resp.status_code >= 400:
                        raise LLMError(f"yandex {resp.status_code}: {resp.text[:300]}")
                    data = resp.json()
                result = data.get("result") or {}
                alts = result.get("alternatives") or []
                if not alts:
                    raise LLMError(f"yandex: empty alternatives, raw={data}")
                msg = alts[0].get("message") or {}
                text = msg.get("text") or ""
                if not text:
                    raise LLMError(f"yandex: empty text, raw={data}")
                usage = result.get("usage") or {}
                return LLMResponse(
                    text=text.strip(),
                    provider=self.name,
                    model=result.get("modelVersion") or self.model,
                    prompt_tokens=int(usage.get("inputTextTokens", 0) or 0),
                    completion_tokens=int(usage.get("completionTokens", 0) or 0),
                    total_tokens=int(usage.get("totalTokens", 0) or 0),
                    raw=data,
                )
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc
                if attempt >= self.max_retries:
                    raise LLMError(f"yandex network: {exc}") from exc
            except LLMError as exc:
                last_exc = exc
                # 5xx ретраим, 4xx — сразу выходим
                if "5xx" in str(exc) and attempt < self.max_retries:
                    continue
                raise
        raise LLMError(f"yandex: exhausted retries ({last_exc})")
