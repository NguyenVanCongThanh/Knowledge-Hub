import os
import tempfile
import pytest
from app.services.parser_service import parser_service

@pytest.fixture
def temp_python_file():
    code_content = """class Calculator:
    def log_operation(self, op, result):
        print(f"{op}: {result}")

    def add(self, a, b):
        res = a + b
        self.log_operation("add", res)
        return res

    def subtract(self, a, b):
        res = a - b
        self.log_operation("subtract", res)
        return res
"""
    # Tạo file python tạm thời
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False, encoding="utf-8") as f:
        f.write(code_content)
        temp_path = f.name
        
    yield temp_path
    
    # Dọn dẹp sau khi test xong
    if os.path.exists(temp_path):
        os.remove(temp_path)

@pytest.fixture
def temp_markdown_file():
    md_content = """# Calculator Project Specification

This is a simple calculator project.

## Addition Feature

Provides addition capabilities.

## Subtraction Feature

Provides subtraction capabilities.
"""
    # Tạo file markdown tạm thời
    with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False, encoding="utf-8") as f:
        f.write(md_content)
        temp_path = f.name
        
    yield temp_path
    
    # Dọn dẹp sau khi test xong
    if os.path.exists(temp_path):
        os.remove(temp_path)

def test_parse_python_code(temp_python_file):
    result = parser_service.parse_file(temp_python_file)
    
    assert result["type"] == "code"
    
    # Kiểm tra xem có nhận diện đúng class Calculator
    classes = [c["name"] for c in result["classes"]]
    assert "Calculator" in classes
    
    # Kiểm tra xem có nhận diện các hàm add, subtract, log_operation
    funcs = [f["name"] for f in result["functions"]]
    assert "add" in funcs
    assert "subtract" in funcs
    assert "log_operation" in funcs
    
    # Kiểm tra quan hệ calls (add -> log_operation, subtract -> log_operation)
    calls = result["calls"]
    assert ("add", "log_operation") in calls
    assert ("subtract", "log_operation") in calls

def test_parse_markdown_docs(temp_markdown_file):
    result = parser_service.parse_file(temp_markdown_file)
    
    assert result["type"] == "document"
    assert len(result["chunks"]) >= 3
    
    headings = [chunk["heading"] for chunk in result["chunks"] if "heading" in chunk]
    assert "Calculator Project Specification" in headings
    assert "Addition Feature" in headings
    assert "Subtraction Feature" in headings

def test_parse_pdf_with_markitdown(monkeypatch):
    class MockResult:
        text_content = """# PDF Title
Some content under title.
## Section 1
Content under section 1.
"""

    class MockMarkItDown:
        def convert(self, file_path):
            return MockResult()

    # Mock the import inside _parse_pdf
    import sys
    from types import ModuleType
    
    mock_markitdown_module = ModuleType("markitdown")
    mock_markitdown_module.MarkItDown = MockMarkItDown
    sys.modules["markitdown"] = mock_markitdown_module

    # Test PDF parsing with MarkItDown mock
    result = parser_service.parse_file("dummy.pdf")
    
    assert result["type"] == "document"
    assert len(result["chunks"]) >= 2
    headings = [chunk["heading"] for chunk in result["chunks"]]
    assert "PDF Title" in headings
    assert "Section 1" in headings
