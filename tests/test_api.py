import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data

@patch("app.api.routes.indexer_service.ingest_project")
def test_ingest_endpoint(mock_ingest):
    # Thiết lập mock return value
    mock_ingest.return_value = {
        "project_name": "test_project",
        "status": "success",
        "indexed_files_count": 5,
        "chunks_count": 20,
        "commits_indexed": 3
    }
    
    # Gửi request với path giả định tồn tại (sử dụng thư mục hiện tại để vượt qua kiểm tra check os.path.exists)
    response = client.post("/ingest", json={
        "project_name": "test_project",
        "path": "."
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["project_name"] == "test_project"
    assert data["chunks_count"] == 20
    
    mock_ingest.assert_called_once_with("test_project", ".")

@patch("app.api.routes.retrieval_service.retrieve")
def test_query_endpoint(mock_retrieve):
    mock_retrieve.return_value = [
        {
            "file": "src/calculator.py",
            "start_line": 8,
            "end_line": 15,
            "score": 0.92,
            "type": "code",
            "text": "def add(self, a, b):\n    return a + b",
            "source": "vector",
            "related_context": [
                {
                    "type": "documentation",
                    "relationship": "IMPLEMENTS",
                    "heading": "Addition Feature",
                    "file_path": "docs/specification.md"
                }
            ]
        }
    ]
    
    response = client.post("/query", json={
        "project": "test_project",
        "query": "How to add two numbers?",
        "top_k": 3
    })
    
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert len(data["results"]) == 1
    assert data["results"][0]["file"] == "src/calculator.py"
    assert data["results"][0]["score"] == 0.92
    assert data["results"][0]["related_context"][0]["heading"] == "Addition Feature"

@patch("app.api.routes.indexer_service.sync_project")
def test_sync_endpoint(mock_sync):
    mock_sync.return_value = {
        "status": "success",
        "added_files": [],
        "modified_files": ["src/calculator.py"],
        "deleted_files": [],
        "new_chunks_count": 3
    }
    
    response = client.post("/sync", json={
        "project_name": "test_project",
        "path": "."
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "src/calculator.py" in data["modified_files"]
