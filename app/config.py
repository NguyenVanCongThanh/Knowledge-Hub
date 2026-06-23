import os

class Settings:
    PROJECT_NAME: str = "Knowledge Hub SDLC"
    
    # Qdrant settings
    QDRANT_HOST: str = os.getenv("QDRANT_HOST", "localhost")
    QDRANT_PORT: int = int(os.getenv("QDRANT_PORT", 6333))
    
    # Neo4j settings
    NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "knowledgehubpassword")
    
    # Embedding model settings
    EMBEDDING_MODEL_NAME: str = os.getenv("EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
    
    # Storage settings
    METADATA_DIR: str = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "metadata"))
    
    def __init__(self):
        os.makedirs(self.METADATA_DIR, exist_ok=True)

settings = Settings()
