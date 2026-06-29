import os
import hashlib
import json
from typing import Dict, List, Any, Optional
import git
from app.config import settings

class GitService:
    def is_git_repo(self, path: str) -> bool:
        try:
            _ = git.Repo(path, search_parent_directories=True)
            return True
        except (git.InvalidGitRepositoryError, git.NoSuchPathError):
            return False

    def get_commits(self, project_path: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Lấy danh sách các commit gần đây kèm file thay đổi"""
        commits_data = []
        if not self.is_git_repo(project_path):
            return []
        
        try:
            repo = git.Repo(project_path, search_parent_directories=True)
            commits = list(repo.iter_commits(max_count=limit))
            
            for commit in commits:
                modified_files = []
                # Lấy danh sách file thay đổi trong commit so với parent
                if commit.parents:
                    diffs = commit.parents[0].diff(commit)
                    for d in diffs:
                        if d.a_path:
                            modified_files.append(d.a_path)
                else:
                    # Commit đầu tiên của repo
                    modified_files = [item.path for item in commit.tree.traverse() if item.type == 'file']
                
                commits_data.append({
                    "hash": commit.hexsha,
                    "message": commit.summary,
                    "author": commit.author.name,
                    "date": commit.committed_date, # Unix timestamp
                    "modified_files": modified_files
                })
        except Exception as e:
            print(f"Error getting git commits from {project_path}: {e}")
            
        return commits_data

    def get_project_diff(self, project_name: str, project_path: str) -> Dict[str, List[str]]:
        """
        Phát hiện sự thay đổi file (thêm, sửa, xóa) trong project.
        Sử dụng kết hợp giữa file hash (để chạy được với mọi thư mục) và Git.
        """
        changes = {"added": [], "modified": [], "deleted": []}
        
        # Đường dẫn file lưu hash metadata
        hash_file_path = os.path.join(settings.METADATA_DIR, f"{project_name}_hashes.json")
        
        # Quét tất cả file hiện tại trong thư mục
        current_files = {}
        for root, dirs, files in os.walk(project_path):
            # Bỏ qua các thư mục đặc biệt dựa trên đường dẫn tương đối của dự án
            rel_root = os.path.relpath(root, project_path)
            if any(part in rel_root.split(os.sep) for part in [".git", "__pycache__", "node_modules", "data", "venv", ".idea"]):
                continue
            for file in files:
                # Chỉ xử lý các đuôi file quan trọng
                _, ext = os.path.splitext(file)
                if ext.lower() not in [".py", ".java", ".cs", ".js", ".ts", ".md", ".pdf", ".txt"]:
                    continue
                
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, project_path)
                try:
                    current_files[rel_path] = self._calculate_file_hash(abs_path)
                except Exception as e:
                    print(f"Error calculating hash for {abs_path}: {e}")

        # Đọc hash đã lưu trước đó
        old_files = {}
        if os.path.exists(hash_file_path):
            try:
                with open(hash_file_path, "r", encoding="utf-8") as f:
                    old_files = json.load(f)
            except Exception as e:
                print(f"Error loading old hashes: {e}")

        # So sánh tìm sự thay đổi
        # 1. Tìm file mới và file bị sửa đổi
        for path, file_hash in current_files.items():
            if path not in old_files:
                changes["added"].append(path)
            elif old_files[path] != file_hash:
                changes["modified"].append(path)
                
        # 2. Tìm file bị xóa
        for path in old_files.keys():
            if path not in current_files:
                changes["deleted"].append(path)

        # Lưu lại trạng thái hash mới
        try:
            with open(hash_file_path, "w", encoding="utf-8") as f:
                json.dump(current_files, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving current hashes: {e}")
            
        return changes

    def _calculate_file_hash(self, file_path: str) -> str:
        """Tính SHA-256 hash của một file"""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256.update(byte_block)
        return sha256.hexdigest()

# Singleton instance
git_service = GitService()
