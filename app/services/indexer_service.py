import os
import re
import uuid
from typing import List, Dict, Any
from app.config import settings
from app.database.qdrant_client import qdrant_db
from app.database.neo4j_client import neo4j_db
from app.services.parser_service import parser_service
from app.services.embedding_service import embedding_service
from app.services.git_service import git_service
from app.services.extraction_orchestrator import extraction_orchestrator

class IndexerService:
    async def ingest_project(self, project_name: str, project_path: str) -> Dict[str, Any]:
        """Thực hiện nạp dữ liệu toàn bộ project lần đầu (Full Index)"""
        # 1. Dọn dẹp dữ liệu cũ của project này
        qdrant_db.delete_project_chunks(project_name)
        neo4j_db.clear_project(project_name)
        
        # Dọn dẹp dữ liệu cũ của project này trong PostgreSQL
        from app.database.postgres_client import postgres_client
        conn = postgres_client.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM projects WHERE name = %s", (project_name,))
                conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"Error clearing old project metadata in PostgreSQL: {e}")
        finally:
            postgres_client.release_connection(conn)
                
        # Khởi tạo node project
        neo4j_db.ensure_project_node(project_name)
        
        # 2. Thu thập và phân loại toàn bộ file trong project
        indexed_files = []
        all_parsed_data = {}
        all_chunks_to_upsert = []
        
        # Quét dự án bằng git_service để khởi tạo hash file
        diff = git_service.get_project_diff(project_name, project_path)
        all_files = diff["added"] + diff["modified"]
        
        # 3. Parse từng file và chuẩn bị embeddings
        for rel_path in all_files:
            abs_path = os.path.join(project_path, rel_path)
            if not os.path.exists(abs_path):
                continue
                
            file_hash = git_service._calculate_file_hash(abs_path)
            parsed = parser_service.parse_file(abs_path)
            parsed["file_hash"] = file_hash
            parsed["rel_path"] = rel_path
            
            all_parsed_data[rel_path] = parsed
            indexed_files.append(rel_path)
            
            # Ghi node File vào Neo4j
            neo4j_db.create_file_node(
                project_name=project_name, 
                file_path=rel_path, 
                file_hash=file_hash, 
                file_type=parsed["type"]
            )
            
            # Tạo các class/function/chunk nodes trong Neo4j
            if parsed["type"] == "code":
                for cls in parsed["classes"]:
                    neo4j_db.create_class_node(project_name, rel_path, cls["name"])
                for func in parsed["functions"]:
                    neo4j_db.create_function_node(
                        project_name=project_name,
                        file_path=rel_path,
                        func_name=func["name"],
                        class_name=func["class_name"],
                        start_line=func["start_line"],
                        end_line=func["end_line"]
                    )
            elif parsed["type"] == "document":
                for idx, chunk in enumerate(parsed["chunks"]):
                    # Sinh UUID v5 hợp lệ cho point id của Qdrant
                    namespace = uuid.NAMESPACE_URL
                    name_key = f"{project_name}:{rel_path}:chunk:{idx}"
                    chunk_id = str(uuid.uuid5(namespace, name_key))
                    
                    heading = chunk.get("heading", f"Section {idx}")
                    neo4j_db.create_document_chunk_node(project_name, rel_path, chunk_id, heading)
                    chunk["id"] = chunk_id  # Gán ID phục vụ vector mapping
            
            # Trích xuất tri thức bằng LLM (Groq) bất đồng bộ cho file hiện tại
            if parsed["chunks"]:
                await extraction_orchestrator.process_project_chunks(project_name, rel_path, parsed["chunks"])
            
            # Chuẩn bị dữ liệu để sinh vector
            texts = [c["text"] for c in parsed["chunks"]]
            if texts:
                vectors = embedding_service.get_embeddings(texts)
                for chunk, vector in zip(parsed["chunks"], vectors):
                    payload = {
                        "file_path": rel_path,
                        "text": chunk["text"],
                        "type": chunk["type"],
                        "start_line": chunk.get("start_line", 0),
                        "end_line": chunk.get("end_line", 0),
                    }
                    if "heading" in chunk:
                        payload["heading"] = chunk["heading"]
                    if "name" in chunk:
                        payload["name"] = chunk["name"]
                    if "entity_type" in chunk:
                        payload["entity_type"] = chunk["entity_type"]
                        
                    all_chunks_to_upsert.append({
                        "id": chunk.get("id"),
                        "vector": vector,
                        "payload": payload
                    })

        # 4. Upsert vectors vào Qdrant
        if all_chunks_to_upsert:
            qdrant_db.upsert_chunks(project_name, all_chunks_to_upsert)

        # 5. Xây dựng các mối quan hệ (CALLS, IMPLEMENTS)
        self._build_relations(project_name, all_parsed_data)
        
        # 6. Index lịch sử Git commits
        commits = git_service.get_commits(project_path, limit=20)
        for commit in commits:
            # Lọc các file bị ảnh hưởng mà có trong dự án đã index
            modified_in_project = [f for f in commit["modified_files"] if f in indexed_files]
            neo4j_db.create_commit_node(
                project_name=project_name,
                commit_hash=commit["hash"],
                message=commit["message"],
                author=commit["author"],
                date=float(commit["date"]),
                modified_files=modified_in_project
            )
            
        return {
            "project_name": project_name,
            "status": "success",
            "indexed_files_count": len(indexed_files),
            "chunks_count": len(all_chunks_to_upsert),
            "commits_indexed": len(commits)
        }

    async def sync_project(self, project_name: str, project_path: str) -> Dict[str, Any]:
        """Cơ chế cập nhật tri thức tự động (Sync/Eviction)"""
        if not os.path.exists(project_path):
            return {"status": "error", "message": "Project path does not exist"}
            
        # Xác định sự thay đổi file
        diff = git_service.get_project_diff(project_name, project_path)
        
        # 1. Xử lý các file bị xóa (Eviction)
        for rel_path in diff["deleted"]:
            qdrant_db.delete_file_chunks(project_name, rel_path)
            neo4j_db.delete_file_nodes(project_name, rel_path)
            
        # 2. Xử lý file bị sửa đổi và thêm mới
        files_to_index = diff["added"] + diff["modified"]
        all_parsed_data = {}
        all_chunks_to_upsert = []
        
        for rel_path in files_to_index:
            abs_path = os.path.join(project_path, rel_path)
            if not os.path.exists(abs_path):
                continue
                
            # Xóa các node cũ nếu là file sửa đổi
            if rel_path in diff["modified"]:
                qdrant_db.delete_file_chunks(project_name, rel_path)
                neo4j_db.delete_file_nodes(project_name, rel_path)
                
            file_hash = git_service._calculate_file_hash(abs_path)
            parsed = parser_service.parse_file(abs_path)
            parsed["file_hash"] = file_hash
            parsed["rel_path"] = rel_path
            
            all_parsed_data[rel_path] = parsed
            
            # Tạo file node mới
            neo4j_db.create_file_node(project_name, rel_path, file_hash, parsed["type"])
            
            # Tạo các Class, Function, Chunk node
            if parsed["type"] == "code":
                for cls in parsed["classes"]:
                    neo4j_db.create_class_node(project_name, rel_path, cls["name"])
                for func in parsed["functions"]:
                    neo4j_db.create_function_node(
                        project_name=project_name,
                        file_path=rel_path,
                        func_name=func["name"],
                        class_name=func["class_name"],
                        start_line=func["start_line"],
                        end_line=func["end_line"]
                    )
            elif parsed["type"] == "document":
                for idx, chunk in enumerate(parsed["chunks"]):
                    # Sinh UUID v5 hợp lệ cho point id của Qdrant
                    namespace = uuid.NAMESPACE_URL
                    name_key = f"{project_name}:{rel_path}:chunk:{idx}"
                    chunk_id = str(uuid.uuid5(namespace, name_key))
                    
                    heading = chunk.get("heading", f"Section {idx}")
                    neo4j_db.create_document_chunk_node(project_name, rel_path, chunk_id, heading)
                    chunk["id"] = chunk_id
            
            # Trích xuất tri thức bằng LLM (Groq) bất đồng bộ cho file hiện tại
            if parsed["chunks"]:
                await extraction_orchestrator.process_project_chunks(project_name, rel_path, parsed["chunks"])
            
            # Chuẩn bị dữ liệu sinh vector
            texts = [c["text"] for c in parsed["chunks"]]
            if texts:
                vectors = embedding_service.get_embeddings(texts)
                for chunk, vector in zip(parsed["chunks"], vectors):
                    payload = {
                        "file_path": rel_path,
                        "text": chunk["text"],
                        "type": chunk["type"],
                        "start_line": chunk.get("start_line", 0),
                        "end_line": chunk.get("end_line", 0),
                    }
                    if "heading" in chunk:
                        payload["heading"] = chunk["heading"]
                    if "name" in chunk:
                        payload["name"] = chunk["name"]
                    if "entity_type" in chunk:
                        payload["entity_type"] = chunk["entity_type"]
                        
                    all_chunks_to_upsert.append({
                        "id": chunk.get("id"),
                        "vector": vector,
                        "payload": payload
                    })

        # Upsert vector mới
        if all_chunks_to_upsert:
            qdrant_db.upsert_chunks(project_name, all_chunks_to_upsert)
            
        # Re-build quan hệ cho các file thay đổi/mới
        if all_parsed_data:
            self._build_relations(project_name, all_parsed_data)

        # Cập nhật các commit mới nhất
        commits = git_service.get_commits(project_path, limit=5)
        for commit in commits:
            neo4j_db.create_commit_node(
                project_name=project_name,
                commit_hash=commit["hash"],
                message=commit["message"],
                author=commit["author"],
                date=float(commit["date"]),
                modified_files=[f for f in commit["modified_files"] if os.path.exists(os.path.join(project_path, f))]
            )

        return {
            "status": "success",
            "added_files": diff["added"],
            "modified_files": diff["modified"],
            "deleted_files": diff["deleted"],
            "new_chunks_count": len(all_chunks_to_upsert)
        }

    async def ingest_github_repo(self, project_name: str, github_url: str, branch: str = "main", token: str = None) -> Dict[str, Any]:
        """Tải/clone repository từ GitHub và thực hiện ingest_project"""
        import git
        import shutil
        
        # Tạo đường dẫn lưu trữ cục bộ
        local_path = os.path.join(settings.GITHUB_REPOS_DIR, project_name)
        
        # Chuẩn hóa URL nếu có token
        clone_url = github_url
        if token:
            clean_url = github_url.replace("https://", "").replace("http://", "")
            clone_url = f"https://{token}@{clean_url}"
            
        if os.path.exists(local_path):
            print(f"Directory {local_path} already exists. Pulling latest changes...")
            try:
                repo = git.Repo(local_path)
                origin = repo.remote(name="origin")
                origin.set_url(clone_url)
                
                repo.git.fetch()
                repo.git.checkout(branch)
                origin.pull()
            except Exception as e:
                print(f"Error pulling repository: {e}. Re-cloning...")
                shutil.rmtree(local_path)
                git.Repo.clone_from(clone_url, local_path, branch=branch)
        else:
            print(f"Cloning {github_url} (branch: {branch}) into {local_path}...")
            git.Repo.clone_from(clone_url, local_path, branch=branch)
            
        return await self.ingest_project(project_name, local_path)

    def _build_relations(self, project_name: str, parsed_data: Dict[str, Dict[str, Any]]):
        """Xây dựng liên kết CALLS giữa code và IMPLEMENTS giữa code - tài liệu"""
        # 1. Tạo quan hệ CALLS
        for file_path, parsed in parsed_data.items():
            if parsed["type"] == "code":
                for caller, callee in parsed["calls"]:
                    neo4j_db.create_call_relationship(project_name, caller, callee)

        # 2. Tạo quan hệ IMPLEMENTS (Liên kết tri thức)
        # Cách 1: Liên kết dựa trên đối sánh thực thể (keyword matching)
        # Quét các document chunks, nếu chứa tên function hoặc class thì tạo link
        all_docs = []
        for file_path, parsed in parsed_data.items():
            if parsed["type"] == "document":
                all_docs.extend(parsed["chunks"])

        for file_path, parsed in parsed_data.items():
            if parsed["type"] == "code":
                # Đối sánh với class names
                for cls in parsed["classes"]:
                    cls_name = cls["name"]
                    pattern = re.compile(rf"\b{re.escape(cls_name)}\b", re.IGNORECASE)
                    for doc_chunk in all_docs:
                        if "id" in doc_chunk and pattern.search(doc_chunk["text"]):
                            neo4j_db.create_implements_relationship(
                                project_name=project_name,
                                file_path=file_path,
                                entity_name=cls_name,
                                entity_type="class",
                                chunk_id=doc_chunk["id"]
                            )
                
                # Đối sánh với function names
                for func in parsed["functions"]:
                    func_name = func["name"]
                    # Bỏ qua các tên hàm quá ngắn hoặc generic (như 'run', 'main', 'add') để tránh nhiễu
                    if len(func_name) <= 3 or func_name in ["init", "main", "test", "load", "save"]:
                        continue
                    pattern = re.compile(rf"\b{re.escape(func_name)}\b", re.IGNORECASE)
                    for doc_chunk in all_docs:
                        if "id" in doc_chunk and pattern.search(doc_chunk["text"]):
                            neo4j_db.create_implements_relationship(
                                project_name=project_name,
                                file_path=file_path,
                                entity_name=func_name,
                                entity_type="function",
                                chunk_id=doc_chunk["id"]
                            )

        # Cách 2: Semantic Similarity-based link (Semantic Rerank link)
        # Sử dụng Vector DB để tìm các document chunk khớp ngữ nghĩa nhất cho mỗi hàm
        for file_path, parsed in parsed_data.items():
            if parsed["type"] == "code" and parsed["functions"]:
                for func in parsed["functions"]:
                    func_name = func["name"]
                    func_text = ""
                    # Tìm nội dung của function chunk
                    for chunk in parsed["chunks"]:
                        if chunk.get("name") == func_name and chunk.get("entity_type") == "function":
                            func_text = chunk["text"]
                            break
                    
                    if not func_text:
                        continue
                        
                    # Tìm tài liệu tương tự nhất
                    try:
                        func_vector = embedding_service.get_embedding(func_text)
                        hits = qdrant_db.search_similar(
                            project_name=project_name,
                            query_vector=func_vector,
                            top_k=2,
                            type_filter="document"
                        )
                        # Nếu độ tương đồng cao (> 0.65), tạo quan hệ IMPLEMENTS
                        for hit in hits:
                            if hit["score"] >= 0.65:
                                doc_chunk_id = hit["id"]
                                neo4j_db.create_implements_relationship(
                                    project_name=project_name,
                                    file_path=file_path,
                                    entity_name=func_name,
                                    entity_type="function",
                                    chunk_id=doc_chunk_id
                                )
                    except Exception as e:
                        print(f"Error during semantic relation building for {func_name}: {e}")

# Singleton instance
indexer_service = IndexerService()
