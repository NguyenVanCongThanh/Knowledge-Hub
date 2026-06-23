import uuid
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models
from app.config import settings

class QdrantDatabaseClient:
    def __init__(self):
        self.client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
        self.collection_name = "sdlc_knowledge"
        self._ensure_collection_exists()

    def _ensure_collection_exists(self):
        try:
            # Kiểm tra xem collection đã tồn tại chưa
            collections = self.client.get_collections().collections
            collection_names = [c.name for c in collections]
            
            if self.collection_name not in collection_names:
                # Tạo collection mới với vector size 384 (all-MiniLM-L6-v2)
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(
                        size=384,
                        distance=models.Distance.COSINE
                    )
                )
                print(f"Created Qdrant collection: {self.collection_name}")
        except Exception as e:
            print(f"Error ensuring Qdrant collection exists: {e}")

    def upsert_chunks(self, project_name: str, chunks: List[Dict[str, Any]]):
        """
        Upsert a list of chunks into Qdrant.
        Each chunk should have:
        - id: unique string or None (will generate UUID)
        - vector: List[float] (384 dim)
        - payload: Dict containing file_path, content, type (code/document), start_line, end_line, etc.
        """
        points = []
        for chunk in chunks:
            chunk_id = chunk.get("id")
            if not chunk_id:
                # Sinh UUID v5 dựa trên file path và content để có tính lặp lại (idempotent)
                namespace = uuid.NAMESPACE_URL
                name = f"{project_name}:{chunk['payload']['file_path']}:{chunk['payload'].get('start_line', 0)}:{chunk['payload'].get('end_line', 0)}"
                chunk_id = str(uuid.uuid5(namespace, name))
                
            payload = chunk["payload"]
            payload["project"] = project_name
            
            points.append(
                models.PointStruct(
                    id=chunk_id,
                    vector=chunk["vector"],
                    payload=payload
                )
            )
            
        if points:
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )

    def delete_project_chunks(self, project_name: str):
        """Xóa toàn bộ chunks thuộc về một project"""
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.Filter(
                must=[
                    models.FieldCondition(
                        key="project",
                        match=models.MatchValue(value=project_name)
                    )
                ]
            )
        )

    def delete_file_chunks(self, project_name: str, file_path: str):
        """Xóa các chunks của một file cụ thể trong project"""
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.Filter(
                must=[
                    models.FieldCondition(
                        key="project",
                        match=models.MatchValue(value=project_name)
                    ),
                    models.FieldCondition(
                        key="file_path",
                        match=models.MatchValue(value=file_path)
                    )
                ]
            )
        )

    def search_similar(
        self, 
        project_name: str, 
        query_vector: List[float], 
        top_k: int = 5, 
        type_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Tìm kiếm các vector tương đồng lọc theo project và type"""
        filter_conditions = [
            models.FieldCondition(
                key="project",
                match=models.MatchValue(value=project_name)
            )
        ]
        
        if type_filter:
            filter_conditions.append(
                models.FieldCondition(
                    key="type",
                    match=models.MatchValue(value=type_filter)
                )
            )
            
        search_result = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            query_filter=models.Filter(must=filter_conditions),
            limit=top_k
        )
        
        results = []
        for hit in search_result:
            results.append({
                "id": hit.id,
                "score": hit.score,
                "payload": hit.payload
            })
        return results

# Singleton instance
qdrant_db = QdrantDatabaseClient()
