# src/ui/streamlit_app.py
from __future__ import annotations

import requests
import streamlit as st

API_BASE = st.secrets.get("API_BASE", "http://localhost:8000")


st.set_page_config(page_title="Pomoika Agent", layout="wide")


def submit_prompt(prompt: str) -> dict:
    resp = requests.post(
        f"{API_BASE}/runs",
        json={"prompt": prompt, "buffer": st.session_state.history},
        timeout=540,
    )
    resp.raise_for_status()
    return resp.json()


def render_tool_event(event: dict) -> None:
    label = f"{event['status'].upper()} · {event['tool_name']}"
    with st.expander(label, expanded=False):
        if event.get("input") is not None:
            st.markdown("**Input**")
            st.json(event["input"])
        if event.get("output") is not None:
            st.markdown("**Output**")
            st.json(event["output"])


def render_evidence_item(item: dict) -> None:
    kind = item["kind"]
    title = item["title"]
    data = item["data"]

    with st.expander(f"{kind} · {title}", expanded=False):
        if kind == "jira_issue":
            st.markdown(f"**Key:** {data.get('key', '-')}")
            st.markdown(f"**Summary:** {data.get('summary', '-')}")
            st.markdown(f"**Status:** {data.get('status', '-')}")
            st.markdown(f"**Assignee:** {data.get('assignee', '-')}")
            st.markdown("**Description**")
            st.write(data.get("description", ""))

        elif kind == "search_match":
            st.code(data.get("match", ""), language="text")
            st.caption(f"{data.get('path')}:{data.get('line')}")

        elif kind == "file_read":
            st.caption(
                f"{data.get('path')} · lines {data.get('start_line')}–{data.get('end_line')}"
            )
            language = "yaml" if str(data.get("path", "")).endswith((".yaml", ".yml")) else "python"
            st.code(data.get("content", ""), language=language)

        elif kind == "tree":
            st.json(data)

        else:
            st.json(data)


if "history" not in st.session_state:
    st.session_state.history = []

st.title("Pomoika Agent")
st.caption("Pomoika investigation assistant")

with st.sidebar:
    st.subheader("Settings")
    st.write(f"API: `{API_BASE}`")
    if st.button("Clear chat"):
        st.session_state.history = []
        st.rerun()

for item in st.session_state.history:
    with st.chat_message(item["role"]):
        st.markdown(item["text"])

prompt = st.chat_input("Ask the agent to investigate a Jira issue...")

if prompt:
    st.session_state.history.append({"role": "user", "text": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.status("Investigating Jira and repository...", expanded=True) as status:
            try:
                run = submit_prompt(prompt)
                status.update(label="Investigation complete", state="complete", expanded=False)
            except Exception as exc:
                status.update(label="Investigation failed", state="error", expanded=True)
                st.error(str(exc))
                st.stop()

        final_answer = run.get("final_answer", "")
        st.markdown(final_answer or "_No final answer returned._")
        st.session_state.history.append({"role": "assistant", "text": final_answer})

        tab1, tab2, tab3, tab4 = st.tabs(["Summary", "Tool Trace", "Evidence", "Raw"])

        with tab1:
            st.markdown(final_answer or "_No summary available._")

        with tab2:
            for event in run.get("tool_events", []):
                render_tool_event(event)

        with tab3:
            evidence = run.get("evidence", [])
            if not evidence:
                st.info("No evidence extracted.")
            for item in evidence:
                render_evidence_item(item)

        with tab4:
            st.json(run.get("raw", {}))