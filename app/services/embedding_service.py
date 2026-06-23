from typing import List
from sentence_transformers import SentenceTransformer
from app.config import settings

class EmbeddingService:
    def __init__(self):
        # Tải model từ cache hoặc tải trực tuyến nếu chưa có (Dockerfile đã tải trước model)
        self.model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)

    def get_embedding(self, text: str) -> List[float]:
        """Sinh vector embedding cho một chuỗi văn bản"""
        if not text.strip():
            # Trả về vector zero nếu text rỗng
            return [0.0] * self.model.get_sentence_embedding_dimension()
        
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Sinh vector embedding cho danh sách các chuỗi văn bản"""
        if not texts:
            return []
        
        # Lọc ra các text không rỗng để encode
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()

# Singleton instance
embedding_service = EmbeddingService()
