from __future__ import annotations
from typing import List

from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool

from src.services.JiraService import JiraService


class JiraGetIssueArgs(BaseModel):
    issue_key: str = Field(description="Jira issue key, e.g. ABC-123")


class JiraSearchIssuesArgs(BaseModel):
    jql: str = Field(description="JQL query string")
    limit: int = Field(default=10, ge=1, le=50, description="Maximum number of issues to return")


class JiraContextBundleArgs(BaseModel):
    issue_key: str = Field(description="Jira issue key, e.g. ABC-123")


class JiraToolset:
    def __init__(self, service: JiraService):
        self.service = service

    def _get_issue(self, issue_key: str) -> dict:
        return self.service.get_issue(issue_key)

    def _search_issues(self, jql: str, limit: int = 10) -> dict:
        return self.service.search_issues(jql=jql, limit=limit)

    def _get_context_bundle(self, issue_key: str) -> dict:
        return self.service.get_context_bundle(issue_key)

    def get_tools(self) -> List[StructuredTool]:
        return [
            StructuredTool.from_function(
                func=self._get_issue,
                name="jira_get_issue",
                description=(
                    "Get a Jira issue by key and return normalized fields such as summary, "
                    "description, status, assignee, priority, labels, and linked issues."
                ),
                args_schema=JiraGetIssueArgs,
            ),
            StructuredTool.from_function(
                func=self._search_issues,
                name="jira_search_issues",
                description=(
                    "Search Jira issues using JQL and return compact normalized results."
                ),
                args_schema=JiraSearchIssuesArgs,
            ),
            StructuredTool.from_function(
                func=self._get_context_bundle,
                name="jira_get_context_bundle",
                description=(
                    "Get compact investigation context for one issue, including the issue itself "
                    "and a preview of linked issues."
                ),
                args_schema=JiraContextBundleArgs,
            ),
        ]