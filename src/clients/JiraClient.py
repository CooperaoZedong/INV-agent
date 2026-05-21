from typing import List, Dict, Any
import requests
from requests.auth import HTTPBasicAuth


class JiraClient:
    def __init__(self, base_url: str, email: str, api_token: str):
        self.base_url = base_url
        self.auth = HTTPBasicAuth(email, api_token)
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

    def get_issue(self, issue_key: str) -> Dict[str, Any]:
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}"
        response = requests.get(url, headers=self.headers, auth=self.auth)
        response.raise_for_status()
        return response.json()

    def search(self, jql: str, max_results: int = 20) -> Dict[str, Any]:
        url = f"{self.base_url}/rest/api/3/search/jql"
        params = {"jql": jql, "maxResults": max_results}
        resp = requests.get(url, auth=self.auth, headers=self.headers, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()