# Knowledge Hub for AI Agents in SDLC

## 1. Tổng quan dự án

### 1.1 Mục tiêu

Xây dựng một **Knowledge Hub (dịch vụ tri thức)** đóng vai trò là:

* Long-term memory cho AI Agents
* Context provider cho các tác vụ trong SDLC
* Hệ thống truy xuất tri thức từ:

  * Source code
  * Tài liệu kỹ thuật (Markdown / PDF)
  * Git commit history
  * Requirement/SRS

---

### 1.2 Bài toán cần giải quyết

Trong quá trình phát triển phần mềm:

* AI Agent hoặc developer không thể đọc toàn bộ project lớn
* Context bị phân tán:

  * code nằm rải rác
  * docs không liên kết với code
  * git history bị bỏ quên

👉 Knowledge Hub giải quyết bằng cách:

* Index toàn bộ dữ liệu SDLC
* Liên kết tri thức giữa các thành phần
* Truy xuất thông minh theo query tự nhiên

---

## 2. Phạm vi hệ thống

### 2.1 Hệ thống là gì?

Knowledge Hub là một:

> **Standalone Knowledge Service (microservice độc lập)**

Không nằm trong project source code.

---

### 2.2 Cách hoạt động tổng quát

```
        +----------------------+
        |  AI Agent / User     |
        +----------+-----------+
                   |
                   v
        +----------------------+
        |  Knowledge Hub API   |
        +----------+-----------+
                   |
     ---------------------------------
     |              |                |
     v              v                v
 Vector DB      Graph DB        Metadata Store
(Qdrant)        (Neo4j)         (SQLite/JSON)
```

---

## 3. Input dữ liệu hệ thống

Knowledge Hub xử lý 4 loại dữ liệu chính:

### 3.1 Source Code

* Python / Java / C# / JS
* Parse theo function / class / module

### 3.2 Tài liệu kỹ thuật

* Markdown (.md)
* PDF (SRS, design docs)

### 3.3 Git History

* Commit messages
* Diff tracking
* Author / timestamp

### 3.4 Requirement (SRS)

* Feature descriptions
* Functional requirements
* Use cases

---

## 4. Kiến trúc hệ thống

### 4.1 Pipeline tổng thể

```
            INGESTION PIPELINE
                   |
    ---------------------------------
    |               |               |
 Code Parser   Doc Parser     Git Parser
    |               |               |
    ---------------------------------
                   |
            Chunking Engine
                   |
         Embedding Generator
                   |
     ---------------------------
     |                         |
 Vector DB              Knowledge Graph
 (Semantic search)      (Relations)
     |                         |
     -----------+-------------
                 |
         Hybrid Retrieval API
```

---

## 5. Thiết kế chi tiết các thành phần

---

### 5.1 Chunking Strategy

#### Source code

* Chunk theo:

  * function
  * class
  * logical block

Ví dụ:

```
def login():
def logout():
```

---

#### Markdown

* Chunk theo heading:

```
# Login Feature
## Flow
## Validation
```

---

#### Git log

* Mỗi commit = 1 chunk
* Extract:

  * message
  * changed files
  * diff summary

---

### 5.2 Embedding Layer

#### Mục tiêu:

Chuyển text → vector

#### Model đề xuất:

* sentence-transformers
* bge-small / e5-small

#### Output:

```json
{
  "chunk_id": "auth.py#login",
  "vector": [0.12, 0.98, ...]
}
```

---

### 5.3 Vector Database (Semantic Search)

#### Gợi ý:

* Qdrant (khuyến nghị)
* Weaviate
* ChromaDB

#### Chức năng:

* tìm code / doc theo meaning
* similarity search

---

### 5.4 Knowledge Graph

#### Database:

* Neo4j

#### Mục tiêu:

Biểu diễn quan hệ:

* Feature → Code
* Function → Function
* Requirement → Implementation

#### Ví dụ:

```
(Login Feature)
    |
implemented_by
    |
auth.py
```

```
login()
    |
calls
    |
validate_user()
```

---

### 5.5 Hybrid Retrieval

Kết hợp:

### (1) Semantic Search

* Vector DB

### (2) Graph Search

* Neo4j

### (3) Merge Results

Output:

```json
{
  "results": [
    {
      "file": "auth.py",
      "score": 0.94,
      "source": "vector + graph"
    }
  ]
}
```

---

## 6. API Design

### 6.1 Ingest Project

```
POST /ingest
```

```json
{
  "project_name": "bookstore",
  "path": "/data/bookstore"
}
```

---

### 6.2 Query Knowledge

```
POST /query
```

```json
{
  "project": "bookstore",
  "query": "How is login implemented?"
}
```

---

### Response

```json
{
  "results": [
    {
      "file": "auth.py",
      "start_line": 10,
      "end_line": 45,
      "score": 0.93,
      "type": "code"
    },
    {
      "file": "login.md",
      "score": 0.87,
      "type": "document"
    }
  ]
}
```

---

### 6.3 Sync (update data)

```
POST /sync
```

* detect file change
* re-index changed chunks
* update graph relations

---

### 6.4 Graph Query

```
GET /graph/{entity}
```

Example:

```
/graph/login_feature
```

---

## 7. Versioning Strategy (Git Integration)

### Mục tiêu:

Giữ Knowledge Hub luôn đồng bộ với source code

### Cách làm:

* Detect file change (hash / git diff)
* Re-index only changed files
* Remove outdated embeddings
* Update graph relations

---

## 8. Multi-project Isolation

### Nguyên tắc:

Không trộn dữ liệu giữa projects

### Solution:

* Namespace per project
* Metadata tagging

```json
{
  "project": "bookstore",
  "file": "auth.py"
}
```

---

## 9. Tech Stack đề xuất

### Backend

* FastAPI (Python)

### Parsing

* Tree-sitter (code parsing)
* PyMuPDF (PDF)
* Markdown parser

### Embedding

* sentence-transformers
* bge-small / e5-small

### Vector DB

* Qdrant

### Graph DB

* Neo4j

### Git integration

* GitPython

### Storage

* SQLite / JSON (metadata)

### Deployment

* Docker
* Docker Compose

---

## 10. LLM (Optional, không bắt buộc)

### Có thể KHÔNG dùng LLM

Hệ thống vẫn hoàn chỉnh.

---

### Nếu dùng LLM (optional enhancement)

Dùng cho:

* Extract entity từ text
* Generate relation graph
* Natural language answer

#### Local LLM:

* Ollama
* Qwen3 4B
* Llama 3 8B

---

## 11. Docker Architecture

```yaml
services:
  api:
    build: .

  qdrant:
    image: qdrant/qdrant

  neo4j:
    image: neo4j

  ollama:
    image: ollama/ollama   # optional
```

---

## 12. Demo Scenario (Quan trọng)

### Step 1: Ingest project

```
POST /ingest
```

---

### Step 2: Indexing result

* 100–500 chunks code
* 50–200 chunks docs
* 50–100 graph nodes

---

### Step 3: Query

```
How is shopping cart implemented?
```

---

### Step 4: Output

```json
{
  "file": "cart.py",
  "score": 0.95,
  "related_docs": ["cart.md"]
}
```

---

### Step 5: Update code

* modify function
* commit git

---

### Step 6: Sync

```
POST /sync
```

---

### Step 7: Query again

System returns updated knowledge (no stale info)

---

## 13. MVP Scope (khuyến nghị)

### BẮT BUỘC:

* Ingestion (code + docs)
* Chunking
* Vector DB search
* Graph DB basic
* REST API
* Docker

---

### OPTIONAL:

* Git sync auto
* Hybrid retrieval
* LLM integration
* Natural language answer

---

## 14. Output cuối cùng cần nộp

* Source code
* Architecture document (file này)
* Docker-compose
* Demo script
* Sample project (BookStore / Web App)

---

## 15. Kết luận

Knowledge Hub không phải chatbot.

Nó là:

> A structured retrieval + knowledge indexing system for SDLC

Giúp AI Agent:

* không cần đọc toàn bộ code
* nhưng vẫn hiểu đúng context dự án
