"""
Канал MAX (Я.МАX). API находится в активной разработке (TamTam Bot API
и его наследники), поэтому здесь — каркас, который повторяет дизайн
VK-адаптера: голый httpx + REST. Когда API стабилизируется, метод
`_call` подменяется на актуальный endpoint без изменения интерфейса
`Channel`.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from ..core import Button, Channel, ChannelKind

log = logging.getLogger(__name__)


class MaxChannel(Channel):
    kind = ChannelKind.MAX

    def __init__(
        self,
        token: str | None = None,
        base_url: str = "https://botapi.tamtam.chat",
        timeout: float = 15.0,
    ) -> None:
        self.token = token or os.environ.get("MAX_BOT_TOKEN", "")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.token)

    async def _call(self, method: str, path: str, json: dict[str, Any] | None = None) -> dict:
        if not self.configured:
            raise RuntimeError("max channel not configured: MAX_BOT_TOKEN")
        params = {"access_token": self.token}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.request(method, self.base_url + path, params=params, json=json)
            r.raise_for_status()
            return r.json()

    async def send_text(self, user_id: str, text: str) -> None:
        await self._call(
            "POST",
            "/messages",
            json={"user_id": user_id, "text": text[:4000]},
        )

    async def send_buttons(self, user_id: str, text: str, buttons: tuple[Button, ...]) -> None:
        attachment = {
            "type": "inline_keyboard",
            "payload": {
                "buttons": [
                    [{"type": "callback", "text": b.label, "payload": b.callback}]
                    for b in buttons
                ]
            },
        }
        await self._call(
            "POST",
            "/messages",
            json={"user_id": user_id, "text": text[:4000], "attachments": [attachment]},
        )

    async def send_image(self, user_id: str, url: str, caption: str = "") -> None:
        attachment = {"type": "image", "payload": {"url": url}}
        await self._call(
            "POST",
            "/messages",
            json={
                "user_id": user_id,
                "text": (caption or "")[:4000],
                "attachments": [attachment],
            },
        )
