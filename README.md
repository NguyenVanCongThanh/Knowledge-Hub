# Knowledge Hub for AI Agents in SDLC

Hệ thống Trung tâm quản lý tri thức (Knowledge Hub) chuyên biệt đóng vai trò là bộ nhớ dài hạn (Long-term Memory) và nền tảng cung cấp ngữ cảnh (Context Provider) cho các AI Agent tham gia vào Chu kỳ phát triển phần mềm (SDLC).

Hệ thống thực hiện:
1. **Nạp & Phân đoạn tri thức (Ingestion & Chunking)**: Phân tích mã nguồn (sử dụng Python AST) và tài liệu Markdown/PDF thành các chunk logic.
2. **Lưu trữ lai (Hybrid Storage)**: Lưu vector embeddings (all-MiniLM-L6-v2) vào **Qdrant** và lưu trữ mối liên kết thực thể (class, function, file, commit, document chunk) vào **Neo4j**.
3. **Tìm kiếm lai (Hybrid Retrieval)**: Kết hợp tìm kiếm ngữ nghĩa (Semantic search) từ Qdrant và mở rộng đồ thị (Graph expansion) từ Neo4j để trích xuất ngữ cảnh liên quan nhất cho AI Agent.
4. **Đồng bộ tự động (Sync & Eviction)**: Sử dụng so khớp hash file để phát hiện các file thêm mới, sửa đổi hoặc bị xóa để cập nhật cơ sở dữ liệu thời gian thực.

---

## 1. Yêu cầu hệ thống
* Docker & Docker Compose
* Git (nếu muốn nạp lịch sử Git commit)

---

## 2. Hướng dẫn khởi chạy hệ thống (Build/Deploy)

Chạy toàn bộ cụm dịch vụ (FastAPI Service + Qdrant + Neo4j) chỉ bằng một câu lệnh:

```bash
docker compose up -d --build
```

Sau khi chạy thành công, các cổng dịch vụ sau sẽ được kích hoạt:
* **FastAPI Service API**: `http://localhost:8000` (Tài liệu Swagger UI tại `http://localhost:8000/docs`)
* **Qdrant Dashboard**: `http://localhost:6333/dashboard`
* **Neo4j Browser**: `http://localhost:7474` (Đăng nhập bằng User: `neo4j` / Mật khẩu: `knowledgehubpassword`)

---

## 3. Kịch bản Demo hoạt động (Demo Scenario)

Để chạy thử nghiệm demo, chúng tôi đã chuẩn bị sẵn một dự án mẫu nằm ở thư mục `demo_sample`.

### Bước 1: Nạp dự án (Ingestion)
Gửi yêu cầu nạp dự án mẫu `demo_sample` vào hệ thống:

```bash
curl -X POST "http://localhost:8000/ingest" \
     -H "Content-Type: application/json" \
     -d '{
       "project_name": "calculator_demo",
       "path": "/app/demo_sample"
     }'
```

*Lưu ý: `/app/demo_sample` là đường dẫn của dự án mẫu bên trong Docker container (thư mục hiện tại được mount vào `/app`).*

**Response mẫu:**
```json
{
  "project_name": "calculator_demo",
  "status": "success",
  "indexed_files_count": 3,
  "chunks_count": 6,
  "commits_indexed": 0
}
```

### Bước 2: AI Agent truy vấn ngữ cảnh (Querying)
AI Agent gửi câu hỏi bằng ngôn ngữ tự nhiên để tìm kiếm ngữ cảnh:

```bash
curl -X POST "http://localhost:8000/query" \
     -H "Content-Type: application/json" \
     -d '{
       "project": "calculator_demo",
       "query": "Làm thế nào để cộng hai số?",
       "top_k": 2
     }'
```

**Response mẫu (Trả về cả code, document mô tả tính năng liên quan và mối liên kết đồ thị):**
```json
{
  "results": [
    {
      "file": "demo_sample/src/calculator.py",
      "start_line": 8,
      "end_line": 15,
      "score": 0.7854,
      "type": "code",
      "text": "    def add(self, a: float, b: float) -> float:\n        \"\"\"\n        Thực hiện phép tính cộng hai số.\n        Ví dụ: add(1, 2) -> 3.0\n        \"\"\"\n        self.log_operation(\"add\", a, b)\n        return float(a + b)",
      "source": "vector",
      "related_context": [
        {
          "type": "documentation",
          "relationship": "IMPLEMENTS",
          "heading": "Addition Feature",
          "file_path": "demo_sample/docs/specification.md"
        },
        {
          "type": "code_function",
          "relationship": "CALLS",
          "name": "log_operation",
          "file_path": "demo_sample/src/calculator.py"
        }
      ]
    }
  ]
}
```

### Bước 3: Đồng bộ tự động khi thay đổi file (Sync)
Giả sử bạn chỉnh sửa file `demo_sample/src/calculator.py` (hoặc thêm một file mới). Hãy gọi API `/sync` để hệ thống tự động phát hiện thay đổi và làm mới tri thức:

```bash
curl -X POST "http://localhost:8000/sync" \
     -H "Content-Type: application/json" \
     -d '{
       "project_name": "calculator_demo",
       "path": "/app/demo_sample"
     }'
```

**Response mẫu:**
```json
{
  "status": "success",
  "added_files": [],
  "modified_files": [
    "demo_sample/src/calculator.py"
  ],
  "deleted_files": [],
  "new_chunks_count": 4
}
```

### Bước 4: Truy vấn quan hệ đồ thị (Graph Query)
Để vẽ hoặc lấy cấu trúc đồ thị xung quanh một hàm (ví dụ hàm `add`):

```bash
curl -X GET "http://localhost:8000/graph/calculator_demo/add"
```

---

## 4. Chạy Unit Tests

Bạn có thể chạy toàn bộ các bài kiểm thử tự động trực tiếp bên trong Docker container:

```bash
docker compose exec knowledge-service pytest tests/
```
