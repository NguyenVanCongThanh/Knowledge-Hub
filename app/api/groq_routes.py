import os
from fastapi import APIRouter, HTTPException, Query, Body
from app.services.groq_manager import groq_manager
from pydantic import BaseModel, Field

router = APIRouter(prefix="", tags=["Groq Manager"]) # Bỏ prefix /groq ở router gốc để có thể phục vụ /dashboard và /api/groq/... một cách trực quan

class KeyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, description="Tên gợi nhớ của Key")
    api_key: str = Field(..., min_length=5, description="Groq API Key (gsk_...)")

class StatusUpdateRequest(BaseModel):
    status: str = Field(..., pattern="^(active|inactive|rate_limited)$", description="Trạng thái mới")

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

class NameUpdateRequest(BaseModel):
    name: str = Field(..., min_length=1, description="Tên gợi nhớ mới")

@router.put("/api/groq/keys/{key_id}/name", summary="Cập nhật tên API Key")
async def update_key_name(key_id: int, payload: NameUpdateRequest):
    try:
        groq_manager.update_key_name(key_id, payload.name)
        return {"message": "Cập nhật tên thành công"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi cập nhật tên key: {str(e)}")

@router.delete("/api/groq/keys/{key_id}", summary="Xóa API Key")
async def delete_key(key_id: int):
    try:
        groq_manager.delete_key(key_id)
        return {"message": "Xóa key thành công"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi xóa key: {str(e)}")

@router.get("/api/groq/usage/summary", summary="Lấy thống kê sử dụng token")
async def get_usage_summary(range: str = Query("7d", pattern="^(24h|7d|30d)$", description="Mốc thời gian lọc (24h, 7d, 30d)")):
    try:
        return groq_manager.get_summary_stats(time_range=range)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi lấy thống kê sử dụng: {str(e)}")

class TestCallRequest(BaseModel):
    prompt: str = Field("Hello, write a short sentence.", description="Prompt test gọi Groq")

@router.post("/api/groq/test-call", summary="Gọi test thử nghiệm Groq API (giúp kiểm tra xoay vòng key & ghi log token)")
async def test_groq_call(payload: TestCallRequest = Body(...)):
    try:
        from app.services.llm_service import llm_service
        # Gọi thử groq bằng logic call_groq_json
        system_prompt = "You are a helpful assistant. Response in JSON with a single key 'response'."
        user_prompt = payload.prompt
        result = await llm_service.call_groq_json(system_prompt, user_prompt)
        return {"status": "success", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi test gọi Groq: {str(e)}")


