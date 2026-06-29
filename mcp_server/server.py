import os
import sys
from mcp.server.fastmcp import FastMCP
from mcp_server.hub_client import KnowledgeHubClient
from mcp_server.github_client import GitHubClient

# Initialize FastMCP server
mcp = FastMCP("Knowledge Hub Bridge")

# Clients
hub_client = KnowledgeHubClient()
github_client = GitHubClient()

@mcp.tool()
def query_knowledge_hub(project: str, query: str, top_k: int = 5, type_filter: str = None) -> str:
    """
    Query semantic and structural context from the Knowledge Hub for a specific project.
    
    Args:
        project: The name of the project.
        query: Semantic query text.
        top_k: Number of results to retrieve.
        type_filter: Filter results by type ('code' or 'document').
    """
    try:
        results = hub_client.query(project=project, query_text=query, top_k=top_k, type_filter=type_filter)
        return str(results)
    except Exception as e:
        return f"Error querying Knowledge Hub: {str(e)}"

@mcp.tool()
def ingest_local_project(project_name: str, path: str) -> str:
    """
    Ingest a local directory/project into the Knowledge Hub.
    
    Args:
        project_name: A unique identifier name for the project.
        path: Absolute path to the project directory.
    """
    try:
        result = hub_client.ingest(project_name=project_name, path=path)
        return str(result)
    except Exception as e:
        return f"Error ingesting project: {str(e)}"

@mcp.tool()
def sync_local_project(project_name: str, path: str) -> str:
    """
    Synchronize/update changes in a local directory/project with the Knowledge Hub.
    
    Args:
        project_name: The identifier name of the project.
        path: Absolute path to the project directory.
    """
    try:
        result = hub_client.sync(project_name=project_name, path=path)
        return str(result)
    except Exception as e:
        return f"Error syncing project: {str(e)}"

@mcp.tool()
def get_entity_relations(project_name: str, entity: str) -> str:
    """
    Retrieve structural/relationship graph data for a specific code entity or file path.
    
    Args:
        project_name: The name of the project.
        entity: The entity name (e.g. class, function, file path).
    """
    try:
        result = hub_client.get_graph(project_name=project_name, entity=entity)
        return str(result)
    except Exception as e:
        return f"Error retrieving entity relations: {str(e)}"

@mcp.tool()
def github_get_issue(owner: str, repo: str, issue_number: int) -> str:
    """
    Retrieve details of a GitHub Issue.
    
    Args:
        owner: The owner of the GitHub repository.
        repo: The repository name.
        issue_number: The issue number.
    """
    try:
        issue = github_client.get_issue(owner=owner, repo=repo, issue_number=issue_number)
        return f"Title: {issue.get('title')}\nState: {issue.get('state')}\n\nBody:\n{issue.get('body')}"
    except Exception as e:
        return f"Error fetching GitHub issue: {str(e)}"

@mcp.tool()
def github_get_pull_request(owner: str, repo: str, pr_number: int) -> str:
    """
    Retrieve pull request details, changed files, and patch diffs.
    
    Args:
        owner: The owner of the GitHub repository.
        repo: The repository name.
        pr_number: The pull request number.
    """
    try:
        pr = github_client.get_pull_request(owner=owner, repo=repo, pr_number=pr_number)
        files = github_client.get_pull_request_files(owner=owner, repo=repo, pr_number=pr_number)
        
        output = [
            f"Title: {pr.get('title')}",
            f"State: {pr.get('state')}",
            f"Mergeable: {pr.get('mergeable')}",
            f"Body:\n{pr.get('body')}",
            "\nFiles changed:"
        ]
        
        for file in files:
            output.append(f"- {file.get('filename')} ({file.get('status')})")
            if file.get('patch'):
                output.append(f"  Patch:\n{file.get('patch')}\n")
                
        return "\n".join(output)
    except Exception as e:
        return f"Error fetching GitHub PR: {str(e)}"

@mcp.tool()
def sync_github_repo_to_knowledge_hub(owner: str, repo: str, branch: str = "main") -> str:
    """
    Download and sync a GitHub repository into the Knowledge Hub service.
    
    Args:
        owner: The owner of the repository.
        repo: The repository name.
        branch: The branch or reference to fetch (defaults to 'main').
    """
    try:
        project_name = f"{owner}_{repo}"
        github_url = f"https://github.com/{owner}/{repo}"
        print(f"Requesting backend to ingest {owner}/{repo} branch {branch}...", file=sys.stderr)
        result = hub_client.ingest_github(project_name=project_name, github_url=github_url, branch=branch)
        return f"Successfully synced GitHub repository {owner}/{repo} to Knowledge Hub under project ID: '{project_name}'\nResult: {str(result)}"
    except Exception as e:
        return f"Error syncing GitHub repository to Knowledge Hub: {str(e)}"

@mcp.tool()
def ingest_github_repo(project_name: str, github_url: str, branch: str = "main", token: str = None) -> str:
    """
    Ingest any arbitrary GitHub repository directly into the Knowledge Hub.
    
    Args:
        project_name: The name you want to give to this project in Knowledge Hub.
        github_url: The full HTTPS URL of the GitHub repository (e.g. https://github.com/owner/repo).
        branch: The branch name (defaults to 'main').
        token: Optional Personal Access Token for private repositories.
    """
    try:
        print(f"Requesting backend to ingest {github_url} branch {branch}...", file=sys.stderr)
        result = hub_client.ingest_github(project_name=project_name, github_url=github_url, branch=branch, token=token)
        return f"Successfully ingested GitHub repository {github_url} into Knowledge Hub under project name: '{project_name}'\nResult: {str(result)}"
    except Exception as e:
        return f"Error ingesting GitHub repository: {str(e)}"

if __name__ == "__main__":
    mcp.run()
