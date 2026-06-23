from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class IngestRequest(BaseModel):
    project_name: str = Field(..., example="bookstore", description="Tên định danh dự án")
    path: str = Field(..., example="/data/bookstore", description="Đường dẫn tuyệt đối đến thư mục dự án")

class IngestResponse(BaseModel):
    project_name: str
    status: str
    indexed_files_count: int
    chunks_count: int
    commits_indexed: int

class QueryRequest(BaseModel):
    project: str = Field(..., example="bookstore", description="Tên định danh dự án cần truy vấn")
    query: str = Field(..., example="How is login implemented?", description="Câu hỏi truy vấn bằng ngôn ngữ tự nhiên")
    top_k: int = Field(5, ge=1, le=20, description="Số lượng kết quả mong muốn")
    type_filter: Optional[str] = Field(None, pattern="^(code|document)$", description="Lọc theo kiểu tri thức (code hoặc document)")

class RelatedContextSchema(BaseModel):
    type: str
    relationship: str
    name: Optional[str] = None
    heading: Optional[str] = None
    file_path: Optional[str] = None
    message: Optional[str] = None
    author: Optional[str] = None

class QueryResultItem(BaseModel):
    file: str
    start_line: int
    end_line: int
    score: float
    type: str
    text: str
    source: str
    related_context: List[RelatedContextSchema]

class QueryResponse(BaseModel):
    results: List[QueryResultItem]

class SyncRequest(BaseModel):
    project_name: str = Field(..., example="bookstore")
    path: str = Field(..., example="/data/bookstore")

class SyncResponse(BaseModel):
    status: str
    added_files: List[str]
    modified_files: List[str]
    deleted_files: List[str]
    new_chunks_count: int
