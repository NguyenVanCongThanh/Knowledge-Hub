# Knowledge Hub for AI Agents in SDLC

Hệ thống Trung tâm quản lý tri thức (Knowledge Hub) đóng vai trò là bộ nhớ dài hạn (Long-term Memory) và nền tảng cung cấp ngữ cảnh (Context Provider) thông minh cho các AI Agent tham gia vào Chu kỳ phát triển phần mềm (SDLC).

Hệ thống thực hiện:
1. **Nạp & Phân đoạn tri thức (Ingestion & Chunking)**: Hỗ trợ nạp source code local hoặc trực tiếp từ GitHub. Phân tích mã nguồn (sử dụng Python AST cho Python, regex cho các ngôn ngữ khác) và tài liệu Markdown/PDF thành các chunk logic.
2. **Lưu trữ lai (Hybrid Storage)**: Lưu vector embeddings (`all-MiniLM-L6-v2`) vào **Qdrant** và lưu trữ mối liên kết thực thể (class, function, file, commit, document chunk) vào **Neo4j**.
3. **Tìm kiếm lai (Hybrid Retrieval)**: Kết hợp tìm kiếm ngữ nghĩa (Semantic search) từ Qdrant và mở rộng đồ thị (Graph expansion) từ Neo4j để trích xuất ngữ cảnh đầy đủ và chính xác nhất cho AI Agent.
4. **Đồng bộ tự động (Sync & Eviction)**: Sử dụng so khớp hash file để phát hiện các thay đổi (thêm mới, sửa đổi hoặc xóa file) để cập nhật cơ sở dữ liệu thời gian thực.
5. **Cầu nối MCP (Model Context Protocol)**: Cung cấp giao thức MCP cho phép các AI Editor/Agent (như Cursor, Claude Desktop, Gemini IDE) gọi trực tiếp các công cụ của Knowledge Hub.

---

## 1. Yêu cầu hệ thống
* Docker & Docker Compose
* Git (nếu muốn nạp lịch sử Git commit)
* Python 3.10+ (nếu chạy MCP Server ở local máy host)

---

## 2. Hướng dẫn khởi chạy hệ thống (Build/Deploy)

Chạy toàn bộ cụm dịch vụ (FastAPI Service + Qdrant + Neo4j) bằng một câu lệnh:

```bash
docker compose up -d --build
```

Sau khi chạy thành công, các cổng dịch vụ sau sẽ được kích hoạt:
* **FastAPI Service API**: `http://localhost:8000` (Tài liệu Swagger UI tại `http://localhost:8000/docs`)
* **Qdrant Dashboard**: `http://localhost:6333/dashboard`
* **Neo4j Browser**: `http://localhost:7474` (Đăng nhập bằng User: `neo4j` / Mật khẩu: `knowledgehubpassword`)

### Dừng hệ thống (Stop)
```bash
# Dừng các container
docker compose down

# Dừng container và xóa toàn bộ dữ liệu lưu trữ (Lưu ý: Mất toàn bộ tri thức đã nạp)
docker compose down -v
```

---

## 3. Các API chính của FastAPI Service

### 3.1. Nạp dữ liệu dự án từ Local (`/ingest`)
Gửi đường dẫn thư mục local để phân tích và nạp vào DB:
```bash
curl -X POST "http://localhost:8000/ingest" \
     -H "Content-Type: application/json" \
     -d '{
       "project_name": "calculator_demo",
       "path": "/app/demo_sample"
     }'
```
*(Lưu ý: `/app/demo_sample` là đường dẫn của dự án bên trong Docker container hoặc `/data/` nếu map ổ đĩa).*

### 3.2. Nạp dữ liệu từ GitHub (`/ingest/github`)
Tải và nạp trực tiếp dự án từ repo GitHub công khai hoặc riêng tư:
```bash
curl -X POST "http://localhost:8000/ingest/github" \
     -H "Content-Type: application/json" \
     -d '{
       "project_name": "my_github_project",
       "github_url": "https://github.com/user/repo",
       "branch": "main",
       "token": "ghp_your_github_personal_access_token_if_private"
     }'
```

### 3.3. Truy vấn ngữ cảnh (`/query`)
AI Agent gửi câu hỏi bằng ngôn ngữ tự nhiên để tìm kiếm ngữ cảnh:
```bash
curl -X POST "http://localhost:8000/query" \
     -H "Content-Type: application/json" \
     -d '{
       "project": "calculator_demo",
       "query": "Làm thế nào để cộng hai số?",
       "top_k": 2,
       "type_filter": "code"
     }'
```

### 3.4. Đồng bộ tự động (`/sync`)
Đồng bộ các file bị thay đổi (thêm mới, chỉnh sửa, xóa):
```bash
curl -X POST "http://localhost:8000/sync" \
     -H "Content-Type: application/json" \
     -d '{
       "project_name": "calculator_demo",
       "path": "/app/demo_sample"
     }'
```

### 3.5. Truy vấn đồ thị quan hệ (`/graph/{project_name}/{entity}`)
Lấy sơ đồ cấu trúc/quan hệ xung quanh một thực thể (hàm, class hoặc file):
```bash
curl -X GET "http://localhost:8000/graph/calculator_demo/add"
```

---

## 4. Tích hợp MCP Server cho AI Agent (Claude Desktop / Cursor)

MCP Server đóng vai trò là cầu nối trực tiếp để các AI Agent giao tiếp với Knowledge Hub và GitHub API.

### Môi trường chạy thử (Debug)
```bash
cd /home/thanh/Knowledge-Hub
export PYTHONPATH=.
python3 -m mcp_server.server
```

### Cấu hình Claude Desktop / Cursor
Thêm cấu hình sau vào file cấu hình của client (ví dụ: `claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "knowledge-hub-bridge": {
      "command": "python3",
      "args": [
        "-m", 
        "mcp_server.server"
      ],
      "env": {
        "KNOWLEDGE_HUB_API_URL": "http://localhost:8000",
        "GITHUB_PERSONAL_ACCESS_TOKEN": "YOUR_GITHUB_TOKEN",
        "PYTHONPATH": "/home/thanh/Knowledge-Hub"
      }
    }
  }
}
```

Các công cụ MCP cung cấp:
* `query_knowledge_hub`: Tìm kiếm ngữ cảnh từ Knowledge Hub.
* `ingest_local_project` / `sync_local_project`: Nạp/Đồng bộ dự án cục bộ.
* `get_entity_relations`: Lấy sơ đồ quan hệ của class/function/file từ Neo4j.
* `github_get_issue` / `github_get_pull_request`: Đọc Issue/PR từ GitHub.
* `sync_github_repo_to_knowledge_hub`: Tự động tải từ GitHub và nạp vào Knowledge Hub.

---

## 5. Chạy Unit Tests

Thực hiện kiểm thử các module bên trong Docker container:
```bash
docker compose exec knowledge-service pytest tests/
```
