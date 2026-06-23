import os
import re
import ast
from typing import List, Dict, Any, Tuple
from pypdf import PdfReader

class CodeCallVisitor(ast.NodeVisitor):
    def __init__(self):
        self.called_funcs = []

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            self.called_funcs.append(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            self.called_funcs.append(node.func.attr)
        self.generic_visit(node)


class ParserService:
    def parse_file(self, file_path: str) -> Dict[str, Any]:
        """Tự động phát hiện loại file và thực hiện parse phù hợp"""
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        
        # Đọc nội dung file
        if ext == ".pdf":
            return self._parse_pdf(file_path)
        
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
            return {"chunks": [], "classes": [], "functions": [], "calls": [], "type": "unknown"}

        if ext == ".md":
            return self._parse_markdown(content, file_path)
        elif ext == ".py":
            return self._parse_python(content, file_path)
        elif ext in [".java", ".cs", ".js", ".ts"]:
            return self._parse_generic_code(content, file_path, ext)
        else:
            # Fallback cho các file text khác (sliding window chunking)
            return self._parse_text_fallback(content, file_path)

    def _parse_markdown(self, content: str, file_path: str) -> Dict[str, Any]:
        """Phân tích tài liệu Markdown (.md) theo cấu trúc heading"""
        lines = content.splitlines()
        chunks = []
        current_chunk = []
        current_heading = "Overview"
        start_line = 1
        
        for idx, line in enumerate(lines, 1):
            # Phát hiện heading (# Title, ## Section)
            if line.startswith("#"):
                # Lưu chunk cũ nếu có nội dung
                if current_chunk:
                    text_content = "\n".join(current_chunk).strip()
                    if text_content:
                        chunks.append({
                            "text": f"{current_heading}\n{text_content}",
                            "type": "document",
                            "start_line": start_line,
                            "end_line": idx - 1,
                            "heading": current_heading
                        })
                current_heading = line.lstrip("#").strip()
                current_chunk = [line]
                start_line = idx
            else:
                current_chunk.append(line)
                
        # Lưu chunk cuối cùng
        if current_chunk:
            text_content = "\n".join(current_chunk).strip()
            if text_content:
                chunks.append({
                    "text": f"{current_heading}\n{text_content}",
                    "type": "document",
                    "start_line": start_line,
                    "end_line": len(lines),
                    "heading": current_heading
                })
                
        # Nếu file md không chứa heading nào cả
        if not chunks and content.strip():
            chunks.append({
                "text": content,
                "type": "document",
                "start_line": 1,
                "end_line": len(lines),
                "heading": "Overview"
            })
            
        return {
            "chunks": chunks,
            "classes": [],
            "functions": [],
            "calls": [],
            "type": "document"
        }

    def _parse_pdf(self, file_path: str) -> Dict[str, Any]:
        """Phân tích file PDF thành các chunks theo từng trang"""
        chunks = []
        try:
            reader = PdfReader(file_path)
            for idx, page in enumerate(reader.pages, 1):
                text = page.extract_text()
                if text.strip():
                    chunks.append({
                        "text": f"Page {idx}:\n{text.strip()}",
                        "type": "document",
                        "start_line": idx,
                        "end_line": idx,
                        "heading": f"Page {idx}"
                    })
        except Exception as e:
            print(f"Error parsing PDF {file_path}: {e}")
            
        return {
            "chunks": chunks,
            "classes": [],
            "functions": [],
            "calls": [],
            "type": "document"
        }

    def _parse_python(self, content: str, file_path: str) -> Dict[str, Any]:
        """Phân tích AST của code Python để trích xuất Class, Function và quan hệ CALLS"""
        lines = content.splitlines()
        chunks = []
        classes = []
        functions = []
        calls = []
        
        try:
            tree = ast.parse(content, filename=file_path)
        except SyntaxError as e:
            print(f"Syntax error parsing {file_path}, falling back to generic parser: {e}")
            return self._parse_generic_code(content, file_path, ".py")

        for node in ast.walk(tree):
            # Parse Class
            if isinstance(node, ast.ClassDef):
                start_line = node.lineno
                end_line = getattr(node, "end_lineno", len(lines))
                class_code = "\n".join(lines[start_line-1 : end_line])
                classes.append({
                    "name": node.name,
                    "start_line": start_line,
                    "end_line": end_line
                })
                chunks.append({
                    "text": f"class {node.name}:\n{class_code}",
                    "type": "code",
                    "name": node.name,
                    "entity_type": "class",
                    "start_line": start_line,
                    "end_line": end_line
                })
                
            # Parse Function/Method
            elif isinstance(node, ast.FunctionDef):
                start_line = node.lineno
                end_line = getattr(node, "end_lineno", len(lines))
                func_code = "\n".join(lines[start_line-1 : end_line])
                
                # Tìm class cha (nếu có)
                parent_class = None
                parent = getattr(node, "parent", None) # Không có sẵn, ta dò bằng cách tìm trong AST
                # Dò cha đơn giản: kiểm tra nếu hàm định nghĩa bên trong phạm vi dòng của class nào đó
                for cls in classes:
                    if cls["start_line"] < start_line < cls["end_line"]:
                        parent_class = cls["name"]
                        break
                        
                functions.append({
                    "name": node.name,
                    "class_name": parent_class,
                    "start_line": start_line,
                    "end_line": end_line
                })
                
                chunks.append({
                    "text": f"def {node.name}:\n{func_code}",
                    "type": "code",
                    "name": node.name,
                    "entity_type": "function",
                    "parent_class": parent_class,
                    "start_line": start_line,
                    "end_line": end_line
                })
                
                # Tìm quan hệ CALLS trong thân hàm
                visitor = CodeCallVisitor()
                visitor.visit(node)
                for callee in visitor.called_funcs:
                    # Tránh tự gọi chính mình hoặc các hàm internal quá cơ bản
                    if callee != node.name and not callee.startswith("__"):
                        calls.append((node.name, callee))
                        
        # Nếu không trích xuất được chunk nào (ví dụ file script phẳng), chunk cả file
        if not chunks and content.strip():
            chunks.append({
                "text": content,
                "type": "code",
                "entity_type": "file",
                "name": os.path.basename(file_path),
                "start_line": 1,
                "end_line": len(lines)
            })

        return {
            "chunks": chunks,
            "classes": classes,
            "functions": functions,
            "calls": list(set(calls)), # loại bỏ trùng lặp
            "type": "code"
        }

    def _parse_generic_code(self, content: str, file_path: str, ext: str) -> Dict[str, Any]:
        """Phân tích mã nguồn Java, C#, JS/TS bằng Regex và phân đoạn"""
        lines = content.splitlines()
        chunks = []
        classes = []
        functions = []
        calls = []

        # Các regex mẫu để nhận diện class và function cơ bản
        class_regex = re.compile(r'(?:class|interface|struct)\s+(\w+)')
        
        # Regex cho function (Java, C#, JS, C++)
        if ext in [".js", ".ts"]:
            # function foo(...) hoặc const foo = (...) => hoặc foo(...) {
            func_regex = re.compile(r'(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=\s*(?:\([^)]*\)|[^=]+)\s*=>|(\w+)\s*\([^)]*\)\s*\{)')
        else:
            # Java/C#: public void foo(...) { or static int bar()
            func_regex = re.compile(r'(?:public|private|protected|static|\s)+\s+[\w<>[\]]+\s+(\w+)\s*\([^)]*\)\s*(?:throws\s+\w+\s*)?\{')

        # Dò tìm theo dòng
        for idx, line in enumerate(lines, 1):
            class_match = class_regex.search(line)
            if class_match:
                class_name = class_match.group(1)
                classes.append({
                    "name": class_name,
                    "start_line": idx,
                    "end_line": min(idx + 50, len(lines)) # Dò thô khoảng 50 dòng
                })
                
            func_match = func_regex.search(line)
            if func_match:
                # Lấy group khớp tên hàm
                groups = func_match.groups()
                func_name = next((g for g in groups if g is not None), None)
                if func_name and func_name not in ["if", "for", "while", "switch", "catch"]:
                    functions.append({
                        "name": func_name,
                        "class_name": classes[-1]["name"] if classes else None,
                        "start_line": idx,
                        "end_line": min(idx + 30, len(lines)) # Dò thô khoảng 30 dòng
                    })

        # Do dùng regex thô nên không xác định được dòng đóng block chuẩn xác,
        # Ta cập nhật lại end_line dựa vào điểm bắt đầu của hàm tiếp theo
        for i in range(len(functions) - 1):
            functions[i]["end_line"] = functions[i+1]["start_line"] - 1

        for i in range(len(classes) - 1):
            classes[i]["end_line"] = classes[i+1]["start_line"] - 1

        # Tạo các chunks từ danh sách functions trích xuất được
        for func in functions:
            start = func["start_line"]
            end = func["end_line"]
            func_code = "\n".join(lines[start-1 : end])
            chunks.append({
                "text": func_code,
                "type": "code",
                "name": func["name"],
                "entity_type": "function",
                "parent_class": func["class_name"],
                "start_line": start,
                "end_line": end
            })

        # Thêm chunk cho cả các file nếu chunks quá ít
        if not chunks and content.strip():
            # Sliding window chunking cho file code
            chunks = self._chunk_by_sliding_window(content, "code")

        return {
            "chunks": chunks,
            "classes": classes,
            "functions": functions,
            "calls": calls,
            "type": "code"
        }

    def _parse_text_fallback(self, content: str, file_path: str) -> Dict[str, Any]:
        """Fallback cho các file dạng text chung"""
        chunks = self._chunk_by_sliding_window(content, "document")
        return {
            "chunks": chunks,
            "classes": [],
            "functions": [],
            "calls": [],
            "type": "document"
        }

    def _chunk_by_sliding_window(self, content: str, doc_type: str, chunk_size: int = 500, overlap: int = 100) -> List[Dict[str, Any]]:
        """Chia nhỏ văn bản bằng cửa sổ trượt (Sliding Window)"""
        lines = content.splitlines()
        chunks = []
        
        current_text = ""
        current_start_line = 1
        
        for idx, line in enumerate(lines, 1):
            if len(current_text) + len(line) < chunk_size:
                current_text += "\n" + line if current_text else line
            else:
                chunks.append({
                    "text": current_text,
                    "type": doc_type,
                    "start_line": current_start_line,
                    "end_line": idx - 1
                })
                # Giữ lại một phần overlap (ví dụ lấy 2 dòng cuối)
                overlap_lines = current_text.splitlines()[-2:] if current_text else []
                current_text = "\n".join(overlap_lines + [line])
                current_start_line = max(1, idx - len(overlap_lines))
                
        if current_text.strip():
            chunks.append({
                "text": current_text,
                "type": doc_type,
                "start_line": current_start_line,
                "end_line": len(lines)
            })
            
        return chunks

# Singleton instance
parser_service = ParserService()
