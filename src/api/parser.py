from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from .schemas import MainChatState as ChatState, ChatTurn, EvidenceItem, RunResponse, ToolEvent


def _safe_json_loads(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except Exception:
        return value


def _extract_ai_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text")
                if text:
                    parts.append(str(text))
        return "\n".join(parts).strip()

    return ""


def _to_raw_message(msg: Any) -> dict[str, Any]:
    return {
        "type": msg.__class__.__name__,
        "content": getattr(msg, "content", None),
        "tool_calls": getattr(msg, "tool_calls", []),
        "name": getattr(msg, "name", None),
        "tool_call_id": getattr(msg, "tool_call_id", None),
        "id": getattr(msg, "id", None),
    }


def _clip_text(text: str, max_chars: int) -> str:
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n...[truncated]"


def _format_pinned_context(pinned_context: dict) -> str:
    if not pinned_context:
        return ""
    return json.dumps(pinned_context, indent=2, ensure_ascii=False)


def normalize_agent_output(prompt: str, agent_output: dict[str, Any]) -> RunResponse:
    messages = agent_output.get("messages", [])

    chat: list[ChatTurn] = []
    tool_events: list[ToolEvent] = []
    evidence: list[EvidenceItem] = []

    tool_request_index: dict[str, int] = {}
    final_answer = ""

    for msg in messages:
        msg_type = msg.__class__.__name__
        content = getattr(msg, "content", None)

        if msg_type == "HumanMessage":
            text = _extract_ai_text(content) if not isinstance(content, str) else content.strip()
            if text:
                chat.append(ChatTurn(role="user", text=text))

        elif msg_type == "AIMessage":
            text = _extract_ai_text(content)
            if text:
                chat.append(ChatTurn(role="assistant", text=text))
                final_answer = text

            for tool_call in getattr(msg, "tool_calls", []) or []:
                event = ToolEvent(
                    tool_call_id=tool_call.get("id"),
                    tool_name=tool_call.get("name", "unknown_tool"),
                    status="requested",
                    input=tool_call.get("args"),
                    output=None,
                )
                tool_request_index[tool_call.get("id")] = len(tool_events)
                tool_events.append(event)

        elif msg_type == "ToolMessage":
            tool_name = getattr(msg, "name", "unknown_tool")
            tool_call_id = getattr(msg, "tool_call_id", None)
            parsed_output = _safe_json_loads(content)

            if tool_call_id in tool_request_index:
                idx = tool_request_index[tool_call_id]
                tool_events[idx] = ToolEvent(
                    tool_call_id=tool_call_id,
                    tool_name=tool_events[idx].tool_name,
                    status="completed",
                    input=tool_events[idx].input,
                    output=parsed_output,
                )
            else:
                tool_events.append(
                    ToolEvent(
                        tool_call_id=tool_call_id,
                        tool_name=tool_name,
                        status="completed",
                        input=None,
                        output=parsed_output,
                    )
                )

            extracted = extract_evidence_from_tool(tool_name, parsed_output)
            evidence.extend(extracted)

    return RunResponse(
        run_id=str(uuid4()),
        prompt=prompt,
        final_answer=final_answer,
        chat=chat,
        tool_events=tool_events,
        evidence=evidence,
        raw={"messages": [_to_raw_message(m) for m in messages]},
    )


def extract_evidence_from_tool(tool_name: str, output: Any) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []

    if tool_name == "jira_get_context_bundle" and isinstance(output, dict):
        issue = output.get("issue")
        if issue:
            items.append(
                EvidenceItem(
                    kind="jira_issue",
                    title=f"{issue.get('key')}: {issue.get('summary')}",
                    data=issue,
                )
            )

    elif tool_name == "repo_search_code" and isinstance(output, dict):
        for match in output.get("matches", [])[:20]:
            items.append(
                EvidenceItem(
                    kind="search_match",
                    title=f"{match.get('path')}:{match.get('line')}",
                    data=match,
                )
            )

    elif tool_name == "repo_read_file" and isinstance(output, dict):
        items.append(
            EvidenceItem(
                kind="file_read",
                title=output.get("path", "file"),
                data=output,
            )
        )

    elif tool_name == "repo_list_tree" and isinstance(output, dict):
        items.append(
            EvidenceItem(
                kind="tree",
                title=f"Tree: {output.get('root', '.')}",
                data=output,
            )
        )

    else:
        if isinstance(output, dict):
            items.append(
                EvidenceItem(
                    kind="other",
                    title=tool_name,
                    data=output,
                )
            )

    return items


def build_llm_messages(
        state: ChatState,
        user_message: str,
        *,
        system_prompt: str | None = None,
        max_recent_turns: int = 3,
        max_summary_chars: int = 4000,
        max_message_chars: int = 3000,
) -> list[dict[str, str]]:
    """
    Build a compact message package for the LLM:
    - optional system prompt
    - pinned context
    - rolling summary
    - last N user/assistant turns
    - current user message

    Note:
    - only replay dialogue messages here
    - do not replay raw tool traces by default
    """

    messages: list[dict[str, str]] = []

    if system_prompt:
        messages.append({
            "role": "system",
            "content": system_prompt,
        })

    if state.pinned_context:
        messages.append({
            "role": "system",
            "content": (
                "Pinned context for this ongoing investigation:\n"
                f"{_format_pinned_context(state.pinned_context)}"
            ),
        })

    if state.summary.strip():
        messages.append({
            "role": "system",
            "content": (
                "Summary of the prior conversation and findings:\n"
                f"{_clip_text(state.summary, max_summary_chars)}"
            ),
        })

    recent_turns = state.messages[-max_recent_turns:]
    for turn in recent_turns:
        messages.append({
            "role": turn.role,
            "content": _clip_text(turn.content, max_message_chars),
        })

    messages.append({
        "role": "user",
        "content": user_message.strip(),
    })

    return messages
