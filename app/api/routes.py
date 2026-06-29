import os
from fastapi import APIRouter, HTTPException, Path, Query
from app.api.schemas import (
    IngestRequest, IngestResponse,
    QueryRequest, QueryResponse,
    SyncRequest, SyncResponse,
    GithubIngestRequest
)
from app.services.indexer_service import indexer_service
from app.services.retrieval_service import retrieval_service
from app.database.neo4j_client import neo4j_db

router = APIRouter()

@router.post("/ingest", response_model=IngestResponse, summary="Nạp dữ liệu toàn bộ project")
async def ingest_project(payload: IngestRequest):
    # Chuẩn hóa path: Nếu chạy trong Docker, /home/thanh được map vào /data
    # Nên nếu user truyền /home/thanh/abc, ta có thể đổi thành /data/abc
    # Hãy tự động chuẩn hóa để dễ dùng ở cả máy thật và Docker container
    project_path = payload.path
    if not os.path.exists(project_path):
        # Hãy thử chuyển đổi /home/thanh sang /data nếu đang chạy trong Docker
        docker_path = project_path.replace("/home/thanh", "/data")
        if os.path.exists(docker_path):
            project_path = docker_path
        else:
            raise HTTPException(
                status_code=400, 
                detail=f"Đường dẫn dự án không tồn tại: {payload.path} (đã thử kiểm tra cả {docker_path})"
            )
            
    try:
        result = await indexer_service.ingest_project(payload.project_name, project_path)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi xảy ra trong quá trình nạp dữ liệu: {str(e)}")

@router.post("/ingest/github", response_model=IngestResponse, summary="Nạp dữ liệu từ GitHub repository")
async def ingest_github_project(payload: GithubIngestRequest):
    try:
        result = await indexer_service.ingest_github_repo(
            project_name=payload.project_name,
            github_url=payload.github_url,
            branch=payload.branch,
            token=payload.token
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi xảy ra trong quá trình nạp dữ liệu từ GitHub: {str(e)}")

@router.post("/query", response_model=QueryResponse, summary="AI Agent truy vấn tri thức")
async def query_knowledge(payload: QueryRequest):
    # Dò tìm path thực tế của project dựa trên cấu hình lưu trữ
    # (Để đọc file gốc trả về text chính xác nếu cần)
    # Lấy path từ file hash đã lưu
    hash_file_path = os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "metadata")),
        f"{payload.project}_hashes.json"
    )
    
    project_path = ""
    # Mặc định lấy từ /data/ nếu chạy trong Docker, hoặc /home/thanh/ nếu chạy local
    if os.path.exists(f"/data/{payload.project}"):
        project_path = f"/data/{payload.project}"
    else:
        project_path = f"/home/thanh/{payload.project}"
        
    try:
        results = retrieval_service.retrieve(
            project_name=payload.project,
            project_path=project_path,
            query=payload.query,
            top_k=payload.top_k,
            type_filter=payload.type_filter
        )
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi thực hiện tìm kiếm tri thức: {str(e)}")

@router.post("/sync", response_model=SyncResponse, summary="Đồng bộ cập nhật tri thức")
async def sync_project(payload: SyncRequest):
    project_path = payload.path
    if not os.path.exists(project_path):
        docker_path = project_path.replace("/home/thanh", "/data")
        if os.path.exists(docker_path):
            project_path = docker_path
        else:
            raise HTTPException(status_code=400, detail=f"Đường dẫn dự án không tồn tại: {payload.path}")
            
    try:
        result = await indexer_service.sync_project(payload.project_name, project_path)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi đồng bộ dự án: {str(e)}")

@router.get("/graph/{project_name}/{entity}", summary="Truy vấn đồ thị quan hệ của một thực thể")
async def get_entity_graph(
    project_name: str = Path(..., description="Tên project"),
    entity: str = Path(..., description="Tên thực thể (hàm, class, hoặc file path)")
):
    try:
        # Truy vấn tìm node gốc
        with neo4j_db.driver.session() as session:
            query = """
            MATCH (n {project: $project_name})
            WHERE n.name = $entity OR n.path = $entity OR n.id = $entity
            MATCH (n)-[r]-(m)
            RETURN 
                labels(n) as source_labels, properties(n) as source_props,
                type(r) as rel_type,
                labels(m) as target_labels, properties(m) as target_props
            LIMIT 30
            """
            cursor = session.run(query, project_name=project_name, entity=entity)
            
            nodes = {}
            edges = []
            
            for record in cursor:
                # Node nguồn (root node)
                src_key = record["source_props"].get("name") or record["source_props"].get("path") or record["source_props"].get("id")
                if src_key not in nodes:
                    nodes[src_key] = {
                        "labels": record["source_labels"],
                        "properties": record["source_props"]
                    }
                    
                # Node đích (neighbor node)
                tgt_key = record["target_props"].get("name") or record["target_props"].get("path") or record["target_props"].get("id")
                if tgt_key not in nodes:
                    nodes[tgt_key] = {
                        "labels": record["target_labels"],
                        "properties": record["target_props"]
                    }
                    
                edges.append({
                    "source": src_key,
                    "target": tgt_key,
                    "type": record["rel_type"]
                })
                
            if not nodes:
                return {"message": f"Không tìm thấy thực thể '{entity}' trong project '{project_name}'."}
                
            return {
                "nodes": [{"id": k, **v} for k, v in nodes.items()],
                "edges": edges
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi truy vấn Neo4j: {str(e)}")
