"""GigaChat MAX (Сбер) адаптер.

Двухшаговая авторизация:
  1. POST https://ngw.devices.sberbank.ru:9443/api/v2/oauth
     headers: Authorization: Basic <auth_key>, RqUID, Content-Type
     body: scope=GIGACHAT_API_PERS  -> access_token (TTL ~30 мин)
  2. POST https://gigachat.devices.sberbank.ru/api/v1/chat/completions
     headers: Authorization: Bearer <access_token>
     body: OpenAI-совместимый формат

Документация: https://developers.sber.ru/docs/ru/gigachat/api/overview
"""

from __future__ import annotations

import os
import time
import uuid

import httpx

from .base import LLMError, LLMMessage, LLMProvider, LLMResponse

DEFAULT_OAUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
DEFAULT_CHAT_URL = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
DEFAULT_TOKEN_TTL = 25 * 60  # 25 минут — на 5 минут раньше реального истечения


class GigaChatProvider(LLMProvider):
    """Реальный GigaChat MAX. Кэширует access_token в памяти процесса."""

    name = "gigachat"

    def __init__(
        self,
        authorization_key: str | None = None,
        scope: str | None = None,
        model: str | None = None,
        oauth_url: str = DEFAULT_OAUTH_URL,
        chat_url: str = DEFAULT_CHAT_URL,
        verify_ssl: bool = False,  # сертификат Минцифры по умолчанию не в системе
        default_timeout: float = 20.0,
        max_retries: int = 2,
    ) -> None:
        self.authorization_key = authorization_key or os.getenv("GIGACHAT_AUTHORIZATION_KEY", "")
        self.scope = scope or os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
        self.model = model or os.getenv("GIGACHAT_MODEL", "GigaChat-Max")
        self.oauth_url = oauth_url
        self.chat_url = chat_url
        self.verify_ssl = verify_ssl
        self.default_timeout = default_timeout
        self.max_retries = max_retries
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0

    async def is_configured(self) -> bool:
        return bool(self.authorization_key) and bool(self.scope)

    async def _get_token(self, *, force_refresh: bool = False) -> str:
        now = time.time()
        if not force_refresh and self._access_token and now < self._token_expires_at - 30:
            return self._access_token
        headers = {
            "Authorization": f"Basic {self.authorization_key}",
            "RqUID": str(uuid.uuid4()),
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        data = {"scope": self.scope}
        async with httpx.AsyncClient(
            timeout=self.default_timeout, verify=self.verify_ssl
        ) as client:
            resp = await client.post(self.oauth_url, headers=headers, data=data)
            if resp.status_code >= 400:
                raise LLMError(f"gigachat oauth {resp.status_code}: {resp.text[:300]}")
            payload = resp.json()
        token = payload.get("access_token")
        if not token:
            raise LLMError(f"gigachat oauth: no access_token in {payload}")
        # Сбер возвращает expires_at в миллисекундах эпохи
        expires_at_ms = payload.get("expires_at")
        if isinstance(expires_at_ms, int | float) and expires_at_ms > now:
            self._token_expires_at = expires_at_ms / 1000.0
        else:
            self._token_expires_at = now + DEFAULT_TOKEN_TTL
        self._access_token = token
        return token

    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.3,
        max_tokens: int = 400,
        timeout: float | None = None,
    ) -> LLMResponse:
        if not await self.is_configured():
            raise LLMError("gigachat: authorization_key or scope missing")
        payload = {
            "model": self.model,
            "messages": [m.to_openai() for m in messages],
            "temperature": float(temperature),
            "max_tokens": int(max_tokens),
            "stream": False,
        }
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                token = await self._get_token(force_refresh=attempt > 0)
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                }
                async with httpx.AsyncClient(
                    timeout=timeout or self.default_timeout, verify=self.verify_ssl
                ) as client:
                    resp = await client.post(self.chat_url, headers=headers, json=payload)
                    if resp.status_code == 401 and attempt < self.max_retries:
                        # Токен мог протухнуть — обновим и повторим
                        self._access_token = None
                        continue
                    if resp.status_code >= 500:
                        raise LLMError(f"gigachat 5xx: {resp.status_code} {resp.text[:200]}")
                    if resp.status_code >= 400:
                        raise LLMError(f"gigachat {resp.status_code}: {resp.text[:300]}")
                    data = resp.json()
                choices = data.get("choices") or []
                if not choices:
                    raise LLMError(f"gigachat: empty choices, raw={data}")
                msg = choices[0].get("message") or {}
                text = msg.get("content") or ""
                if not text:
                    raise LLMError(f"gigachat: empty content, raw={data}")
                usage = data.get("usage") or {}
                return LLMResponse(
                    text=text.strip(),
                    provider=self.name,
                    model=data.get("model") or self.model,
                    prompt_tokens=int(usage.get("prompt_tokens", 0) or 0),
                    completion_tokens=int(usage.get("completion_tokens", 0) or 0),
                    total_tokens=int(usage.get("total_tokens", 0) or 0),
                    raw=data,
                )
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc
                if attempt >= self.max_retries:
                    raise LLMError(f"gigachat network: {exc}") from exc
            except LLMError as exc:
                last_exc = exc
                if "5xx" in str(exc) and attempt < self.max_retries:
                    continue
                raise
        raise LLMError(f"gigachat: exhausted retries ({last_exc})")
