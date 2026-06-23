# Hệ thống Quản lý Tri thức (Knowledge Hub) cho AI Agents trong SDLC

Tài liệu này mô tả chi tiết kiến trúc kỹ thuật, mô hình dữ liệu và các thuật toán lõi của hệ thống **Knowledge Hub** đóng vai trò là lớp bộ nhớ dài hạn và cung cấp ngữ cảnh thông minh cho các AI Agent trong chu kỳ phát triển phần mềm (SDLC).

---

## 1. Kiến trúc Tổng thể (System Architecture)

Hệ thống hoạt động dưới dạng một standalone microservice cung cấp giao diện REST API.

```
       [ AI Agent / User ]
               │ (Query / Ingest / Sync)
               ▼
   ┌────────────────────────────────┐
   │       FastAPI API Service      │
   └───────┬────────────────┬───────┘
           │                │
           ▼                ▼
   ┌───────────────┐┌───────────────┐
   │ Qdrant (Vec)  ││ Neo4j (Graph) │
   │               ││               │
   │ - Semantic    ││ - Structural  │
   │ - Similarities││ - Relations   │
   └───────────────┘└───────────────┘
```

---

## 2. Đường ống xử lý Dữ liệu (Ingestion Pipeline)

Khi nhận yêu cầu nạp dự án qua `/ingest`, hệ thống thực hiện các bước sau:

```
[Project Path] ──► [File Scanner] ──► [Parsers (AST & Regex & Markdown)]
                                                │
                 ┌──────────────────────────────┴──────────────────────────────┐
                 ▼ (Text Chunks)                                               ▼ (Entity Relations)
       [Embedding Model]                                                 [Graph Builder]
                 │ (all-MiniLM-L6-v2)                                          │
                 ▼                                                             ▼
     [Qdrant: Vector Storage]                                      [Neo4j: Knowledge Graph]
```

### 2.1 Chiến lược phân đoạn (Chunking Strategies)
* **Python Code AST Parsing**: Sử dụng bộ phân tích cú pháp cây cú pháp trừu tượng (`ast` module) của Python để định vị chính xác vị trí của từng Class và Function, lấy ra code block đầy đủ kèm theo thông tin dòng bắt đầu (`start_line`) và dòng kết thúc (`end_line`).
* **Generic Code Regex Parsing**: Đối với Java, C#, JS/TS, hệ thống sử dụng Regex tối ưu để nhận diện các dòng khai báo lớp và chữ ký hàm, phân đoạn mã nguồn xung quanh các thực thể đó.
* **Markdown Document Chunking**: Tách nhỏ tài liệu dựa trên cấu trúc các thẻ tiêu đề (`#`, `##`, `###`).
* **PDF Document Chunking**: Tách tài liệu theo từng trang để giữ tính độc lập và số trang làm metadata tham chiếu.

---

## 3. Thiết kế Cơ sở dữ liệu (Database Design)

### 3.1 Vector Database (Qdrant)
Hệ thống sử dụng một collection duy nhất tên là `sdlc_knowledge` với:
* **Vector size**: 384 (Khớp với chiều ra của model `all-MiniLM-L6-v2`).
* **Distance Metric**: `COSINE` (Độ tương đồng Cosine).
* **Metadata Payload**:
  ```json
  {
    "project": "tên_dự_án",
    "file_path": "đường_dẫn_tương_đối",
    "type": "code / document",
    "text": "nội_dung_chunk",
    "start_line": 10,
    "end_line": 25,
    "heading": "Tiêu đề (nếu là tài liệu)",
    "name": "Tên hàm/class (nếu là code)",
    "entity_type": "function / class / file"
  }
  ```

### 3.2 Knowledge Graph (Neo4j)
Đồ thị biểu diễn mối liên kết cấu trúc và logic trong dự án SDLC:

#### Các loại Node:
* `Project`: Đại diện cho dự án.
* `File`: File mã nguồn hoặc tài liệu trong dự án.
* `Class`: Class khai báo trong mã nguồn.
* `Function`: Hàm hoặc phương thức.
* `DocumentChunk`: Một phân đoạn tài liệu kỹ thuật hoặc SRS.
* `Commit`: Commit trong lịch sử Git.

#### Các mối quan hệ (Relationships):
* `(Project)-[:HAS_FILE]->(File)`
* `(File)-[:CONTAINS]->(Class)`
* `(File)-[:CONTAINS]->(Function)`
* `(Class)-[:CONTAINS]->(Function)`
* `(File)-[:CONTAINS]->(DocumentChunk)`
* `(Function)-[:CALLS]->(Function)`: Hàm A gọi hàm B.
* `(Commit)-[:MODIFIED]->(File)`: Commit sửa đổi file.
* `(Function/Class/File)-[:IMPLEMENTS]->(DocumentChunk)`: Mã nguồn hiện thực hóa yêu cầu mô tả trong tài liệu.

---

## 4. Thiết lập liên kết tri thức (Knowledge Linking)

Để tự động liên kết tài liệu mô tả tính năng với code triển khai tính năng đó (mối quan hệ `IMPLEMENTS`), hệ thống sử dụng kết hợp 2 phương pháp:
1. **Đối sánh thực thể (Keyword Matching)**: Quét văn bản của các chunk tài liệu, nếu xuất hiện tên Class hoặc Function của dự án (trừ các tên hàm thông thường như `run`, `main`), hệ thống sẽ tự động tạo liên kết `[:IMPLEMENTS]`.
2. **Đối sánh ngữ nghĩa (Semantic Similarity Link)**: Với mỗi hàm mã nguồn, hệ thống sinh vector embedding và tìm kiếm top 2 chunk tài liệu tương đồng nhất trên Qdrant. Nếu điểm tương đồng $score \ge 0.65$, hệ thống sẽ tự động nối quan hệ `[:IMPLEMENTS]` trong Neo4j.

---

## 5. Tìm kiếm lai (Hybrid Retrieval Flow)

Quy trình xử lý khi AI Agent gọi `/query`:

```
[Query Text] ──► [Embedding Generator] ──► [Qdrant Semantic Search]
                                                      │ (Top K hits)
                                                      ▼
[Rich Context Results] ◄── [Rerank & Merge] ◄── [Neo4j Graph Expansion]
                                           (Lấy thêm: DocumentChunks,
                                            Called/Caller Functions,
                                            Recent Commits)
```

1. **Semantic Search**: Tìm kiếm $K$ kết quả tương đồng nhất về mặt ngữ nghĩa trong Qdrant.
2. **Graph Expansion**: Với mỗi kết quả tìm được, truy vấn Neo4j để tìm các node lân cận trong vòng 1-2 bước nhảy:
   * Nếu có tài liệu `[:IMPLEMENTS]` liên quan -> Trích xuất làm ngữ cảnh tài liệu bổ trợ.
   * Nếu có quan hệ gọi hàm `[:CALLS]` -> Bổ sung thông tin các hàm liên quan.
   * Nếu có commit sửa đổi gần đây -> Giúp AI Agent biết lịch sử sửa đổi file này.
3. **Rerank & Merge**: Kết hợp kết quả từ hai nguồn, chuẩn hóa điểm số và trả về danh sách JSON cấu trúc sắp xếp theo thứ tự giảm dần của độ tin cậy.

---

## 6. Cơ chế cập nhật tri thức tự động (Sync & Eviction)

Hệ thống cung cấp API `/sync` để đồng bộ khi dự án thay đổi:
1. Quét toàn bộ thư mục dự án và tính toán SHA-256 hash của từng file.
2. So sánh danh sách hash hiện tại với trạng thái đã lưu tại `data/metadata/{project_name}_hashes.json`:
   * **File bị xóa**: Xóa toàn bộ vector chunks trong Qdrant và xóa các node liên quan (Class, Function, DocumentChunk) trong Neo4j (**Eviction policy**).
   * **File bị sửa đổi/thêm mới**: Xóa dữ liệu cũ của file đó (nếu có), thực hiện parse lại, sinh vector embeddings mới, cập nhật lại Neo4j và Qdrant.
3. Quét lịch sử Git commit để ghi nhận các thay đổi commit mới nhất.
