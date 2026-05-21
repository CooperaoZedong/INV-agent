from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from .schemas import RunResponse, ChatMessage, MainChatState as ChatState


RUN_STORE: dict[str, RunResponse] = {}

class JsonChatStateStore:
    def __init__(self):
        self.store = ChatState()

    def load(self) -> ChatState:
        data = self.store
        return ChatState.model_validate(data)

    def save(self, state: ChatState) -> None:
        self.store = state

    def append_message(self, role: Literal["user", "assistant"], content: str, source: Literal["streamlit", "telegram", "system"]) -> ChatState:
        self.store.messages.append(
            ChatMessage(
                role=role,
                content=content,
                created_at=datetime.now(timezone.utc).isoformat(),
                source=source,
            )
        )
        return self.store

    def update_pinned_context(self, **kwargs: Any) -> ChatState:
        self.store.pinned_context.update(kwargs)
        return self.store

    def update_summary(self, summary: str) -> ChatState:
        self.store.summary = summary
        return self.store

    def reset(self):
        self.store = ChatState()
        return self.store
