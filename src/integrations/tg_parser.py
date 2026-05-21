from __future__ import annotations

from typing import Any


def extract_message(update: dict[str, Any]) -> dict[str, Any] | None:
    return (
            update.get("message")
            or update.get("edited_message")
    )


def extract_text_message(update: dict[str, Any]) -> tuple[int | None, str | None]:
    msg = extract_message(update)
    if not msg:
        return None, None

    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    text = msg.get("text")

    if not chat_id or not text:
        return chat_id, None

    return chat_id, text.strip()

def chunk_text(text: str, chunk_size: int = 3500) -> list[str]:
    text = text.strip()
    if not text:
        return ["Done, but there was no final text output."]
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]
