from __future__ import annotations

from typing import Any

import httpx


class TelegramBotClient:
    def __init__(self, token: str):
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"

    async def _post(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{self.base_url}/{method}", json=payload)
            resp.raise_for_status()
            data = resp.json()
            if not data.get("ok"):
                raise RuntimeError(f"Telegram API error: {data}")
            return data

    async def send_message(
            self,
            chat_id: int | str,
            text: str,
            parse_mode: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        return await self._post("sendMessage", payload)

    async def set_webhook(
            self,
            url: str,
            secret_token: str,
            allowed_updates: list[str] | None = None,
            drop_pending_updates: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "url": url,
            "secret_token": secret_token,
            "drop_pending_updates": drop_pending_updates,
        }
        if allowed_updates is not None:
            payload["allowed_updates"] = allowed_updates
        return await self._post("setWebhook", payload)

    async def set_my_commands(self, commands: list[dict[str, str]]) -> dict[str, Any]:
        return await self._post("setMyCommands", {"commands": commands})