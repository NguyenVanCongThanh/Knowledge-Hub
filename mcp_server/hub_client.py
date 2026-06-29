import os
import httpx

KNOWLEDGE_HUB_API_URL = os.environ.get("KNOWLEDGE_HUB_API_URL", "http://localhost:8000")

class KnowledgeHubClient:
    def __init__(self, base_url: str = KNOWLEDGE_HUB_API_URL):
        self.base_url = base_url.rstrip("/")

    def query(self, project: str, query_text: str, top_k: int = 5, type_filter: str = None):
        url = f"{self.base_url}/query"
        payload = {
            "project": project,
            "query": query_text,
            "top_k": top_k
        }
        if type_filter:
            payload["type_filter"] = type_filter
            
        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            return response.json()

    def ingest(self, project_name: str, path: str):
        url = f"{self.base_url}/ingest"
        payload = {
            "project_name": project_name,
            "path": path
        }
        with httpx.Client(timeout=120.0) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            return response.json()

    def ingest_github(self, project_name: str, github_url: str, branch: str = "main", token: str = None):
        url = f"{self.base_url}/ingest/github"
        payload = {
            "project_name": project_name,
            "github_url": github_url,
            "branch": branch,
        }
        if token:
            payload["token"] = token
            
        with httpx.Client(timeout=300.0) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            return response.json()

    def sync(self, project_name: str, path: str):
        url = f"{self.base_url}/sync"
        payload = {
            "project_name": project_name,
            "path": path
        }
        with httpx.Client(timeout=120.0) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            return response.json()

    def get_graph(self, project_name: str, entity: str):
        url = f"{self.base_url}/graph/{project_name}/{entity}"
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.json()
