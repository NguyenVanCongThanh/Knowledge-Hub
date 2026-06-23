import os
from typing import List, Dict, Any, Optional
from app.database.qdrant_client import qdrant_db
from app.database.neo4j_client import neo4j_db
from app.services.embedding_service import embedding_service

class RetrievalService:
    def retrieve(
        self, 
        project_name: str, 
        project_path: str,
        query: str, 
        top_k: int = 5,
        type_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Thực hiện tìm kiếm lai (Hybrid Retrieval) kết hợp Vector Search và Graph Search.
        """
        # 1. Sinh vector embedding cho câu truy vấn
        query_vector = embedding_service.get_embedding(query)
        
        # 2. Tìm kiếm tương đồng ngữ nghĩa trong Vector DB (Qdrant)
        vector_hits = qdrant_db.search_similar(
            project_name=project_name,
            query_vector=query_vector,
            top_k=top_k,
            type_filter=type_filter
        )
        
        results = []
        seen_ids = set()
        
        # 3. Lấy kết quả từ Vector Search và thực hiện mở rộng qua Đồ thị Tri thức (Neo4j)
        for hit in vector_hits:
            payload = hit["payload"]
            score = hit["score"]
            file_path = payload["file_path"]
            entity_name = payload.get("name")
            chunk_type = payload["type"]
            
            seen_ids.add(hit["id"])
            
            # Đọc lại code gốc chính xác nếu là code chunk (bảo đảm độ tin cậy)
            text_content = payload.get("text", "")
            
            result_item = {
                "file": file_path,
                "start_line": payload.get("start_line", 0),
                "end_line": payload.get("end_line", 0),
                "score": round(score, 4),
                "type": chunk_type,
                "text": text_content,
                "source": "vector",
                "related_context": []
            }
            
            # 4. Graph Search: Truy xuất thực thể liên quan từ Neo4j để làm giàu ngữ cảnh
            try:
                related_nodes = neo4j_db.get_related_nodes(
                    project_name=project_name,
                    file_path=file_path,
                    name=entity_name
                )
                
                # Phân tích quan hệ từ Neo4j
                for node in related_nodes:
                    labels = node["labels"]
                    props = node["properties"]
                    relationship = node["relationship"]
                    
                    # Nếu tìm thấy file tài liệu hướng dẫn/SRS liên kết với code này
                    if "DocumentChunk" in labels:
                        result_item["related_context"].append({
                            "type": "documentation",
                            "relationship": relationship,
                            "heading": props.get("heading", ""),
                            "file_path": props.get("file_path", "")
                        })
                    # Nếu tìm thấy hàm gọi/được gọi từ hàm này
                    elif "Function" in labels:
                        result_item["related_context"].append({
                            "type": "code_function",
                            "relationship": relationship,
                            "name": props.get("name", ""),
                            "file_path": props.get("file_path", "")
                        })
                    # Nếu tìm thấy commit đã sửa file này gần đây
                    elif "Commit" in labels:
                        result_item["related_context"].append({
                            "type": "git_commit",
                            "relationship": relationship,
                            "message": props.get("message", ""),
                            "author": props.get("author", "")
                        })
            except Exception as e:
                print(f"Error expanding graph context for {file_path}: {e}")
                
            results.append(result_item)
            
        # 5. Graph Expansion (Mở rộng kết quả tìm kiếm từ Đồ thị)
        # Nếu có các node Document liên quan mật thiết đến các file code tìm được mà chưa xuất hiện ở Vector search,
        # chúng ta có thể nạp thêm chúng vào (nhưng với trọng số thấp hơn)
        graph_expanded_items = []
        for res in results:
            for rel in res["related_context"]:
                # Nếu tìm thấy document chunk liên quan mà chưa nằm trong top kết quả vector
                if rel["type"] == "documentation":
                    doc_path = rel["file_path"]
                    # Dò tìm file tài liệu để đọc nội dung
                    abs_doc_path = os.path.join(project_path, doc_path)
                    if os.path.exists(abs_doc_path) and doc_path not in [r["file"] for r in results]:
                        try:
                            # Đọc một phần tài liệu làm context
                            with open(abs_doc_path, "r", encoding="utf-8", errors="ignore") as f:
                                doc_content = f.read()[:800] # lấy 800 ký tự đầu
                            
                            # Thêm vào danh sách mở rộng
                            graph_expanded_items.append({
                                "file": doc_path,
                                "start_line": 1,
                                "end_line": 20,
                                "score": round(res["score"] * 0.8, 4), # Hạ điểm số vì tìm qua quan hệ gián tiếp
                                "type": "document",
                                "text": f"(Trích xuất từ quan hệ {res['file']}):\n{doc_content}",
                                "source": "graph_expansion",
                                "related_context": []
                            })
                        except Exception:
                            pass
                            
        results.extend(graph_expanded_items)
        
        # Sắp xếp lại danh sách kết quả theo điểm số relevance giảm dần
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

# Singleton instance
retrieval_service = RetrievalService()
