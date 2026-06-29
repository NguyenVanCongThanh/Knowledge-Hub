# MCP Server - Knowledge Hub & GitHub Bridge

MCP Server này đóng vai trò cầu nối cho phép các AI Agents (ví dụ: Claude Desktop, Cursor, Gemini IDE) tích hợp trực tiếp với dịch vụ **Knowledge Hub** và **GitHub API**.

## Các chức năng cung cấp (Tools)

1. **`query_knowledge_hub`**: Tìm kiếm ngữ cảnh ngữ nghĩa & quan hệ từ Knowledge Hub.
2. **`ingest_local_project`**: Đăng ký nạp một dự án local vào cơ sở dữ liệu tri thức.
3. **`sync_local_project`**: Đồng bộ các thay đổi local với Knowledge Hub.
4. **`get_entity_relations`**: Truy vấn sơ đồ quan hệ của class/function/file từ Neo4j.
5. **`github_get_issue`**: Truy xuất nội dung GitHub Issue.
6. **`github_get_pull_request`**: Truy xuất thông tin PR bao gồm file thay đổi và diff patches.
7. **`sync_github_repo_to_knowledge_hub`**: Bridge tự động tải repo từ GitHub và nạp thẳng vào Knowledge Hub.

---

## Yêu cầu hệ thống

- Python 3.10+
- Thư viện `mcp` (được cài đặt qua `pip install mcp`)
- Service **Knowledge Hub** đang chạy (mặc định tại `http://localhost:8000`)
- GitHub Personal Access Token (nếu làm việc với private repos hoặc tránh bị rate limit)

---

## Hướng dẫn cài đặt & Cấu hình Client

### Cấu hình Claude Desktop

Thêm đoạn cấu hình sau vào file cấu hình của Claude Desktop:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

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

### Chạy kiểm tra thủ công (Debugging)

Bạn có thể chạy thử trực tiếp MCP server bằng môi trường Stdio:

```bash
cd /home/thanh/Knowledge-Hub
export PYTHONPATH=.
python3 -m mcp_server.server
```
*(MCP Server sẽ khởi động và đợi các thông điệp JSON-RPC chuẩn qua stdin).*
