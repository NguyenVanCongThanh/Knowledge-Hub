from typing import Dict, Any, Optional
import time

class ProgressService:
    def __init__(self):
        # Key: project_name, Value: dict containing job details
        self._jobs: Dict[str, Dict[str, Any]] = {}
        # Set of project names requested to cancel
        self._cancelled_projects = set()

    def request_cancel(self, project_name: str):
        """Đưa dự án vào danh sách yêu cầu hủy"""
        self._cancelled_projects.add(project_name)
        if project_name in self._jobs:
            self._jobs[project_name]["stage_text"] = "Đang thực hiện hủy và hoàn tác (rolling back)..."

    def is_cancelled(self, project_name: str) -> bool:
        """Kiểm tra xem dự án có yêu cầu hủy hay không"""
        return project_name in self._cancelled_projects

    def clear_cancel(self, project_name: str):
        """Xóa cờ hủy"""
        if project_name in self._cancelled_projects:
            self._cancelled_projects.remove(project_name)

    def start_job(self, project_name: str, job_type: str) -> Dict[str, Any]:
        """Khởi tạo trạng thái cho một job mới"""
        job = {
            "project_name": project_name,
            "job_type": job_type,          # "local_ingest", "github_ingest", "sync"
            "status": "running",           # "running", "completed", "failed"
            "stage": "started",            # "cloning", "diffing", "parsing", "extracting", "embedding", "neo4j", "finalizing"
            "stage_text": "Đang bắt đầu xử lý...",
            "total_files": 0,
            "processed_files": 0,
            "current_file": None,
            "total_chunks": 0,
            "processed_chunks": 0,
            "error_message": None,
            "progress_pct": 0.0,
            "started_at": time.time(),
            "updated_at": time.time()
        }
        self._jobs[project_name] = job
        return job

    def update_job(self, project_name: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Cập nhật các trường thông tin của job"""
        if project_name not in self._jobs:
            # Nếu chưa có job (có thể do gọi từ sync trực tiếp), khởi tạo mặc định
            self.start_job(project_name, "local_ingest")
        
        job = self._jobs[project_name]
        for key, value in kwargs.items():
            if key in job or key in ["total_files", "processed_files", "total_chunks", "processed_chunks", "current_file"]:
                job[key] = value
                
        # Tự động tính toán phần trăm tiến trình ước lượng
        total_files = job.get("total_files", 0)
        processed_files = job.get("processed_files", 0)
        total_chunks = job.get("total_chunks", 0)
        processed_chunks = job.get("processed_chunks", 0)
        stage = job.get("stage", "")

        # Trọng số phân chia theo các stage:
        # cloning/diffing: 5%
        # parsing/neo4j nodes: 45% (chia đều theo số files)
        # embedding/LLM/vector upsert: 45% (chia đều theo chunks)
        # finalizing/relations/commits: 5%
        
        pct = 0.0
        if stage == "cloning":
            pct = 2.0
        elif stage == "diffing":
            pct = 5.0
        elif stage in ["parsing", "extracting"]:
            file_progress = (processed_files / total_files) if total_files > 0 else 0.0
            pct = 5.0 + file_progress * 45.0
        elif stage == "embedding":
            chunk_progress = (processed_chunks / total_chunks) if total_chunks > 0 else 0.0
            pct = 50.0 + chunk_progress * 45.0
        elif stage == "finalizing":
            pct = 95.0
        elif job["status"] == "completed":
            pct = 100.0
        
        job["progress_pct"] = round(min(100.0, max(pct, 0.0)), 1)
        job["updated_at"] = time.time()
        return job

    def get_job(self, project_name: str) -> Optional[Dict[str, Any]]:
        """Lấy thông tin tiến trình của một project"""
        return self._jobs.get(project_name)

    def complete_job(self, project_name: str, indexed_files_count: int = 0, chunks_count: int = 0, commits_indexed: int = 0) -> Optional[Dict[str, Any]]:
        """Đánh dấu job hoàn thành thành công"""
        if project_name not in self._jobs:
            return None
        
        job = self._jobs[project_name]
        job.update({
            "status": "completed",
            "stage": "completed",
            "stage_text": "Hoàn thành nạp dữ liệu tri thức!",
            "processed_files": job["total_files"] if job.get("total_files", 0) > 0 else indexed_files_count,
            "processed_chunks": job["total_chunks"] if job.get("total_chunks", 0) > 0 else chunks_count,
            "progress_pct": 100.0,
            "updated_at": time.time(),
            # Thêm kết quả thống kê
            "indexed_files_count": indexed_files_count,
            "chunks_count": chunks_count,
            "commits_indexed": commits_indexed
        })
        return job

    def fail_job(self, project_name: str, error_message: str) -> Optional[Dict[str, Any]]:
        """Đánh dấu job thất bại kèm lỗi"""
        if project_name not in self._jobs:
            self.start_job(project_name, "local_ingest")
            
        job = self._jobs[project_name]
        job.update({
            "status": "failed",
            "stage_text": f"Lỗi: {error_message}",
            "error_message": error_message,
            "updated_at": time.time()
        })
        return job

progress_service = ProgressService()
