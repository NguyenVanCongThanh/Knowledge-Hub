from fastapi import FastAPI
from app.api.routes import router
from app.database.neo4j_client import neo4j_db

app = FastAPI(
    title="SDLC Knowledge Hub API",
    description="Dịch vụ tri thức chuyên biệt làm bộ nhớ dài hạn cho AI Agents trong SDLC.",
    version="1.0.0"
)

# Đăng ký các endpoints
app.include_router(router)

@app.get("/", summary="Trạng thái hệ thống")
async def root():
    return {
        "status": "healthy",
        "service": "SDLC Knowledge Hub",
        "version": "1.0.0",
        "docs_url": "/docs"
    }

@app.on_event("shutdown")
def shutdown_event():
    # Đóng kết nối Neo4j Driver
    try:
        neo4j_db.close()
        print("Closed Neo4j connection driver.")
    except Exception as e:
        print(f"Error closing Neo4j connection: {e}")
