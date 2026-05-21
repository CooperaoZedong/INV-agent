from os import environ
from pathlib import Path
from typing import Any, Dict

from langchain.agents import create_agent
from langchain_aws import ChatBedrockConverse

from src.clients.JiraClient import JiraClient
from src.services.JiraService import JiraService
from src.tools.JiraTools import JiraToolset
from src.services.RepoService import LocalRepoService, RepoServiceConfig
from src.tools.LocalRepoTools import LocalRepoToolset

def build_agent():
    jira_client = JiraClient(
        base_url=environ.get("JIRA_BASE_URL", ""),
        email=environ.get("JIRA_EMAIL", ""),
        api_token=environ.get("JIRA_API_TOKEN", "")
    )

    jira_service = JiraService(jira_client=jira_client)
    repo_service = LocalRepoService(RepoServiceConfig(
        repo_root=Path(environ.get("REPO_ROOT", "")).expanduser(),
    ))

    jira_tools = JiraToolset(service=jira_service).get_tools()
    repo_tools = LocalRepoToolset(service=repo_service).get_tools()

    llm = ChatBedrockConverse(
        model_id="eu.anthropic.claude-opus-4-6-v1",
        region_name="eu-west-1",
        temperature=0,
        max_tokens=4096,
    )

    agent = create_agent(
        tools=[*jira_tools, *repo_tools],
        model=llm,
        system_prompt=environ.get("SYSTEM_PROMPT", ""),
    )

    return agent

def run_agent(messages: list[dict[str, str]]):
    agent = build_agent()
    result = agent.invoke({"messages": messages})

    return result
