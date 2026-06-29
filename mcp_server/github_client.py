import os
import httpx
import tempfile
import zipfile
import io

GITHUB_TOKEN = os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN", "")

class GitHubClient:
    def __init__(self, token: str = GITHUB_TOKEN):
        self.token = token
        self.headers = {
            "Accept": "application/vnd.github.v3+json"
        }
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"

    def get_issue(self, owner: str, repo: str, issue_number: int):
        url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}"
        with httpx.Client() as client:
            response = client.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()

    def get_pull_request(self, owner: str, repo: str, pr_number: int):
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
        with httpx.Client() as client:
            response = client.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()

    def get_pull_request_files(self, owner: str, repo: str, pr_number: int):
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files"
        with httpx.Client() as client:
            response = client.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()

    def download_repo_zip(self, owner: str, repo: str, ref: str = "main", dest_dir: str = None) -> str:
        """
        Downloads a repo as a ZIP file, extracts it to dest_dir, and returns the path to the root folder.
        """
        url = f"https://api.github.com/repos/{owner}/{repo}/zipball/{ref}"
        
        with httpx.Client(follow_redirects=True, timeout=60.0) as client:
            response = client.get(url, headers=self.headers)
            response.raise_for_status()
            
            z = zipfile.ZipFile(io.BytesIO(response.content))
            if not dest_dir:
                dest_dir = tempfile.mkdtemp()
            z.extractall(path=dest_dir)
            
            # The zip file contains a root directory named like "owner-repo-commit_sha"
            extracted_dirs = [os.path.join(dest_dir, name) for name in os.listdir(dest_dir) 
                              if os.path.isdir(os.path.join(dest_dir, name))]
            if extracted_dirs:
                return extracted_dirs[0]
            return dest_dir
