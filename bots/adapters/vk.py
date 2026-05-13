"""
VK Сообщества — адаптер канала.

Реализован поверх голого httpx + VK Bot API (`messages.send`,
`groups.setLongPollServer`, `groups.getLongPollServer`). Никаких
тяжёлых SDK — это нужно, чтобы быстро поднять MVP на проде без
лишних зависимостей.

Запуск из CLI::

    export VK_GROUP_TOKEN=...
    export VK_GROUP_ID=...
    python -m bots.adapters.vk

Полная имплементация (long-poll loop) находится в `run()`. Тесты
в `bots/tests/test_vk_channel.py` мокают httpx через respx.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
from typing import Any

import httpx

from ..core import (
    Button,
    Channel,
    ChannelKind,
    ChitaiClient,
    Incoming,
    Router,
    build_default_router,
)

log = logging.getLogger(__name__)


class VKChannel(Channel):
    kind = ChannelKind.VK
    api_base = "https://api.vk.com/method"
    api_version = "5.199"

    def __init__(
        self,
        group_token: str | None = None,
        group_id: str | int | None = None,
        timeout: float = 15.0,
    ) -> None:
        self.token = group_token or os.environ.get("VK_GROUP_TOKEN", "")
        self.group_id = str(group_id or os.environ.get("VK_GROUP_ID", ""))
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.token and self.group_id)

    async def _call(self, method: str, params: dict[str, Any]) -> dict:
        if not self.configured:
            raise RuntimeError("vk channel not configured: VK_GROUP_TOKEN / VK_GROUP_ID")
        payload = {**params, "access_token": self.token, "v": self.api_version}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(f"{self.api_base}/{method}", data=payload)
            r.raise_for_status()
            data = r.json()
            if "error" in data:
                raise RuntimeError(f"vk error: {data['error']}")
            return data.get("response", {})

    async def send_text(self, user_id: str, text: str) -> None:
        await self._call(
            "messages.send",
            {
                "user_id": user_id,
                "message": text[:4000],
                "random_id": random.randint(1, 10**9),
            },
        )

    async def send_buttons(self, user_id: str, text: str, buttons: tuple[Button, ...]) -> None:
        keyboard = {
            "one_time": False,
            "inline": True,
            "buttons": [
                [
                    {
                        "action": {"type": "text", "label": b.label, "payload": f'{{"intent":"{b.callback}"}}'},
                        "color": "primary",
                    }
                ]
                for b in buttons
            ],
        }
        await self._call(
            "messages.send",
            {
                "user_id": user_id,
                "message": text[:4000],
                "keyboard": __import__("json").dumps(keyboard, ensure_ascii=False),
                "random_id": random.randint(1, 10**9),
            },
        )

    async def send_image(self, user_id: str, url: str, caption: str = "") -> None:
        await self._call(
            "messages.send",
            {
                "user_id": user_id,
                "message": (caption + "\n" + url)[:4000],
                "random_id": random.randint(1, 10**9),
            },
        )


def _intent_from_vk_event(event: dict) -> Incoming | None:
    """VK long-poll event → Incoming. Поддерживает только message_new."""
    if event.get("type") != "message_new":
        return None
    obj = event.get("object", {}).get("message") or event.get("object", {})
    user_id = str(obj.get("from_id") or obj.get("user_id") or "")
    text = obj.get("text", "")
    payload_raw = obj.get("payload")
    payload: dict[str, Any] = {}
    intent: str | None = None
    if payload_raw:
        try:
            import json as _json

            payload = _json.loads(payload_raw)
            intent = payload.get("intent")
        except (ValueError, TypeError):
            payload = {}
    return Incoming(user_id=user_id, text=text, intent=intent, payload=payload)


async def run(router: Router | None = None) -> None:  # pragma: no cover
    """Long-poll цикл. Запускается из CLI. В тестах не вызывается."""
    channel = VKChannel()
    if not channel.configured:
        raise SystemExit("VK channel not configured")
    client = ChitaiClient()
    router = router or build_default_router()
    lp = await channel._call(
        "groups.getLongPollServer", {"group_id": channel.group_id}
    )
    server, key, ts = lp["server"], lp["key"], lp["ts"]
    async with httpx.AsyncClient(timeout=35.0) as http:
        while True:
            r = await http.get(
                server,
                params={"act": "a_check", "key": key, "ts": ts, "wait": 25},
            )
            r.raise_for_status()
            data = r.json()
            ts = data.get("ts", ts)
            for ev in data.get("updates", []):
                incoming = _intent_from_vk_event(ev)
                if incoming is not None:
                    try:
                        await router.dispatch(incoming, channel, client)
                    except Exception as exc:
                        log.warning("vk dispatch failed: %s", exc)


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())
