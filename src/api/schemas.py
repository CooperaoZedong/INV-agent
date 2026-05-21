from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    created_at: str
    source: Literal["streamlit", "telegram", "system"] = "system"


class MainChatState(BaseModel):
    summary: str = ""
    pinned_context: dict[str, Any] = Field(default_factory=dict)
    messages: list[ChatMessage] = Field(default_factory=list)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)


class RunRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    repo_root: str | None = None


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    text: str


class ToolEvent(BaseModel):
    tool_call_id: str | None = None
    tool_name: str
    status: Literal["requested", "completed"]
    input: dict[str, Any] | None = None
    output: Any | None = None


class EvidenceItem(BaseModel):
    kind: Literal["jira_issue", "search_match", "file_read", "tree", "other"]
    title: str
    data: dict[str, Any]


class RunResponse(BaseModel):
    run_id: str
    prompt: str
    final_answer: str
    chat: list[ChatTurn]
    tool_events: list[ToolEvent]
    evidence: list[EvidenceItem]
    raw: dict[str, Any]
