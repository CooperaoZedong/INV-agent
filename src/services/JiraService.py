from __future__ import annotations
from typing import Any, Dict, List, Optional
from src.clients.JiraClient import JiraClient


class JiraService:
    def __init__(self, jira_client: JiraClient):
        self.jira_client = jira_client

    def _extract_plain_description(self, description: Any) -> Optional[str]:
        if description is None:
            return None

        if isinstance(description, str):
            return description

        if not isinstance(description, dict):
            return str(description)

        parts: List[str] = []

        def walk(node: Any) -> None:
            if isinstance(node, dict):
                text = node.get("text")
                if isinstance(text, str):
                    parts.append(text)

                for item in node.get("content", []) or []:
                    walk(item)

            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(description)
        text = " ".join(p.strip() for p in parts if p and p.strip())
        return text or None

    def _normalize_issue(self, issue: Dict[str, Any]) -> Dict[str, Any]:
        fields = issue.get("fields", {})

        return {
            "key": issue.get("key"),
            "summary": fields.get("summary"),
            "description": self._extract_plain_description(fields.get("description")),
            "status": fields.get("status", {}).get("name"),
            "assignee": fields.get("assignee", {}).get("displayName") if fields.get("assignee") else None,
            "reporter": fields.get("reporter", {}).get("displayName") if fields.get("reporter") else None,
            "created": fields.get("created"),
            "updated": fields.get("updated"),
            "priority": fields.get("priority", {}).get("name") if fields.get("priority") else None,
            "issue_type": fields.get("issuetype", {}).get("name") if fields.get("issuetype") else None,
        }

    def _extract_issue_links(self, links: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        for link in links or []:
            link_type = (link.get("type") or {}).get("name")

            inward = link.get("inwardIssue")
            if inward:
                inward_fields = inward.get("fields", {})
                results.append({
                    "direction": "inward",
                    "relationship": link_type,
                    "key": inward.get("key"),
                    "summary": inward_fields.get("summary"),
                    "status": (inward_fields.get("status") or {}).get("name"),
                })

            outward = link.get("outwardIssue")
            if outward:
                outward_fields = outward.get("fields", {})
                results.append({
                    "direction": "outward",
                    "relationship": link_type,
                    "key": outward.get("key"),
                    "summary": outward_fields.get("summary"),
                    "status": (outward_fields.get("status") or {}).get("name"),
                })

        return results

    def get_issue(self, issue_key: str) -> Dict[str, Any]:
        raw = self.jira_client.get_issue(issue_key)
        return self._normalize_issue(raw)

    def search_issues(self, jql: str, limit: int = 10) -> Dict[str, Any]:
        raw = self.jira_client.search(jql, max_results=limit)

        issues = []
        for item in raw.get("issues", []):
            normalized = self._normalize_issue(item)
            issues.append({
                "key": normalized["key"],
                "summary": normalized["summary"],
                "status": normalized["status"],
                "assignee": normalized["assignee"],
                "priority": normalized["priority"],
                "issue_type": normalized["issue_type"],
            })

        return {
            "total": raw.get("total"),
            "returned": len(issues),
            "issues": issues,
        }

    def get_context_bundle(self, issue_key: str) -> Dict[str, Any]:
        """
        Compact context for the agent:
        issue + linked issues preview.
        """
        issue = self.get_issue(issue_key)

        linked_keys = [x["key"] for x in issue.get("linked_issues", []) if x.get("key")]
        linked_preview = []

        for key in linked_keys[:5]:
            try:
                linked_preview.append(self.get_issue(key))
            except Exception as exc:
                linked_preview.append({
                    "key": key,
                    "error": f"Failed to load linked issue: {exc}",
                })

        return {
            "issue": issue,
            "linked_issues_preview": linked_preview,
        }