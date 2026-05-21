from os import environ
from pathlib import Path

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
        repo_root=Path("~/Documents/Workspace/AMIPaC/ai-bedrock-integration-activities").expanduser(),
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

    response = jira_client.search('key = "RMM-26541"', max_results=5)
    print('SEARCH RESULT: ', response)

    return agent


def main():
    agent = build_agent()
    result = agent.invoke({
        "messages": [
            {
                "role": "user",
                "content": (
                    "Investigate issue RMM-26541. "
                    "Summarize the problem, likely affected modules, dependencies, and a possible implementation plan."
                ),
            }
        ]
    })

    print(result)

if __name__ == "__main__":
    main()