import os
import pytest
from app.services.parser_service import parser_service

def test_parse_python_code():
    # Setup đường dẫn tới file calculator mẫu
    current_dir = os.path.dirname(__file__)
    calc_path = os.path.abspath(os.path.join(current_dir, "..", "demo_sample", "src", "calculator.py"))
    
    assert os.path.exists(calc_path), f"File {calc_path} does not exist"
    
    result = parser_service.parse_file(calc_path)
    
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

def test_parse_markdown_docs():
    current_dir = os.path.dirname(__file__)
    spec_path = os.path.abspath(os.path.join(current_dir, "..", "demo_sample", "docs", "specification.md"))
    
    assert os.path.exists(spec_path), f"File {spec_path} does not exist"
    
    result = parser_service.parse_file(spec_path)
    
    assert result["type"] == "document"
    assert len(result["chunks"]) >= 3
    
    headings = [chunk["heading"] for chunk in result["chunks"] if "heading" in chunk]
    assert "Calculator Project Specification" in headings
    assert "Addition Feature" in headings
    assert "Subtraction Feature" in headings
