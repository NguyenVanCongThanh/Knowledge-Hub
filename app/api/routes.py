import os
from typing import Optional
from fastapi import APIRouter, HTTPException, Path, Query, BackgroundTasks
from app.api.schemas import (
    IngestRequest, IngestResponse,
    QueryRequest, QueryResponse,
    SyncRequest, SyncResponse,
    GithubIngestRequest, ProgressResponse
)
from app.services.indexer_service import indexer_service
from app.services.retrieval_service import retrieval_service
from app.database.neo4j_client import neo4j_db
from app.services.progress_service import progress_service
from app.api.groq_routes import router as groq_router

router = APIRouter()
router.include_router(groq_router)


async def run_ingest_project_bg(project_name: str, project_path: str):
    try:
        await indexer_service.ingest_project(project_name, project_path)
    except Exception as e:
        progress_service.fail_job(project_name, str(e))

async def run_ingest_github_bg(project_name: str, github_url: str, branch: str, token: Optional[str]):
    try:
        await indexer_service.ingest_github_repo(project_name, github_url, branch, token)
    except Exception as e:
        progress_service.fail_job(project_name, str(e))

@router.post("/ingest", response_model=IngestResponse, summary="Nạp dữ liệu toàn bộ project")
async def ingest_project(payload: IngestRequest, background_tasks: BackgroundTasks):
    project_path = payload.path
    if not os.path.exists(project_path):
        docker_path = project_path.replace("/home/thanh", "/data")
        if os.path.exists(docker_path):
            project_path = docker_path
        else:
            raise HTTPException(
                status_code=400, 
                detail=f"Đường dẫn dự án không tồn tại: {payload.path} (đã thử kiểm tra cả {docker_path})"
            )
            
    try:
        progress_service.start_job(payload.project_name, "local_ingest")
        background_tasks.add_task(run_ingest_project_bg, payload.project_name, project_path)
        return {
            "project_name": payload.project_name,
            "status": "processing"
        }
    except Exception as e:
        progress_service.fail_job(payload.project_name, str(e))
        raise HTTPException(status_code=500, detail=f"Lỗi xảy ra khi bắt đầu nạp dữ liệu: {str(e)}")

@router.post("/ingest/github", response_model=IngestResponse, summary="Nạp dữ liệu từ GitHub repository")
async def ingest_github_project(payload: GithubIngestRequest, background_tasks: BackgroundTasks):
    try:
        progress_service.start_job(payload.project_name, "github_ingest")
        background_tasks.add_task(
            run_ingest_github_bg, 
            payload.project_name,
            payload.github_url,
            payload.branch,
            payload.token
        )
        return {
            "project_name": payload.project_name,
            "status": "processing"
        }
    except Exception as e:
        progress_service.fail_job(payload.project_name, str(e))
        raise HTTPException(status_code=500, detail=f"Lỗi xảy ra khi bắt đầu nạp dữ liệu từ GitHub: {str(e)}")

@router.get("/ingest/status/{project_name}", response_model=ProgressResponse, summary="Lấy trạng thái tiến trình nạp dữ liệu")
async def get_ingest_status(project_name: str = Path(..., description="Tên định danh dự án")):
    job = progress_service.get_job(project_name)
    if not job:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy tiến trình nào cho dự án '{project_name}'")
    return job

@router.post("/ingest/cancel/{project_name}", summary="Yêu cầu hủy và khôi phục tiến trình nạp dữ liệu")
async def cancel_ingestion(project_name: str = Path(..., description="Tên định danh dự án")):
    job = progress_service.get_job(project_name)
    if not job:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy tiến trình nào đang chạy cho dự án '{project_name}'")
    if job.get("status") != "running":
        raise HTTPException(status_code=400, detail=f"Tiến trình của dự án '{project_name}' không ở trạng thái đang chạy (status is {job.get('status')})")
    
    progress_service.request_cancel(project_name)
    return {"message": f"Yêu cầu hủy tiến trình nạp của '{project_name}' đã được ghi nhận. Hệ thống đang tiến hành rollback..."}

@router.post("/query", response_model=QueryResponse, summary="AI Agent truy vấn tri thức")
async def query_knowledge(payload: QueryRequest):
    # Dò tìm path thực tế của project dựa trên cấu hình lưu trữ
    # (Để đọc file gốc trả về text chính xác nếu cần)
    project_path = ""
    # Lấy path từ database
    from app.database.postgres_client import postgres_client
    conn = postgres_client.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT local_cache_path FROM projects WHERE name = %s", (payload.project,))
            row = cursor.fetchone()
            if row and row[0]:
                project_path = row[0]
    except Exception as e:
        print(f"Error fetching project path from DB: {e}")
    finally:
        postgres_client.release_connection(conn)

    if not project_path:
        # Fallback nếu không tìm thấy trong DB
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
