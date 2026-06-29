import os
from fastapi import APIRouter, HTTPException, Query, Body
from fastapi.responses import HTMLResponse
from app.services.groq_manager import groq_manager
from pydantic import BaseModel, Field

router = APIRouter(prefix="", tags=["Groq Manager"]) # Bỏ prefix /groq ở router gốc để có thể phục vụ /dashboard và /api/groq/... một cách trực quan

class KeyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, description="Tên gợi nhớ của Key")
    api_key: str = Field(..., min_length=5, description="Groq API Key (gsk_...)")

class StatusUpdateRequest(BaseModel):
    status: str = Field(..., pattern="^(active|inactive|rate_limited)$", description="Trạng thái mới")

@router.get("/dashboard", response_class=HTMLResponse, summary="Giao diện quản lý Groq API Keys & Usage", include_in_schema=False)
async def get_dashboard():
    template_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "app", "templates", "dashboard.html"
    )
    if not os.path.exists(template_path):
        raise HTTPException(status_code=404, detail="Không tìm thấy file giao diện dashboard.html")
    with open(template_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)

# Đổi prefix của các API endpoints để chuẩn RESTful
@router.get("/api/groq/keys", summary="Lấy danh sách API Keys")
async def get_keys():
    try:
        return groq_manager.get_all_keys()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi lấy danh sách keys: {str(e)}")

@router.post("/api/groq/keys", summary="Thêm mới API Key")
async def add_key(payload: KeyCreateRequest):
    try:
        key_id = groq_manager.add_key(payload.name, payload.api_key)
        return {"message": "Thêm key thành công", "key_id": key_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi thêm key: {str(e)}")

@router.put("/api/groq/keys/{key_id}/status", summary="Cập nhật trạng thái API Key")
async def update_key_status(key_id: int, payload: StatusUpdateRequest):
    try:
        groq_manager.update_key_status(key_id, payload.status)
        return {"message": "Cập nhật trạng thái thành công"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi cập nhật trạng thái: {str(e)}")

@router.delete("/api/groq/keys/{key_id}", summary="Xóa API Key")
async def delete_key(key_id: int):
    try:
        groq_manager.delete_key(key_id)
        return {"message": "Xóa key thành công"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi xóa key: {str(e)}")

@router.get("/api/groq/usage/summary", summary="Lấy thống kê sử dụng token")
async def get_usage_summary():
    try:
        return groq_manager.get_summary_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi lấy thống kê sử dụng: {str(e)}")


