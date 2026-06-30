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
        Sử dụng kết hợp giữa file hash (lưu trong PostgreSQL) và Git.
        """
        changes = {"added": [], "modified": [], "deleted": []}
        
        # Thử phân tích thông tin Git (owner, repo, branch, commit) từ project_path
        owner = None
        repo_name = None
        branch = "main"
        last_commit_sha = None
        if self.is_git_repo(project_path):
            try:
                g_repo = git.Repo(project_path, search_parent_directories=True)
                try:
                    branch = g_repo.active_branch.name
                except Exception:
                    pass
                try:
                    last_commit_sha = g_repo.head.commit.hexsha
                except Exception:
                    pass
                try:
                    remote_url = g_repo.remotes.origin.url
                    if "github.com" in remote_url:
                        parts = remote_url.split("github.com")[-1].strip(":/").replace(".git", "").split("/")
                        if len(parts) >= 2:
                            owner = parts[0]
                            repo_name = parts[1]
                except Exception:
                    pass
            except Exception:
                pass

        # Quét tất cả file hiện tại trong thư mục
        current_files = {}
        for root, dirs, files in os.walk(project_path):
            rel_root = os.path.relpath(root, project_path)
            if any(part in rel_root.split(os.sep) for part in [".git", "__pycache__", "node_modules", "data", "venv", ".idea"]):
                continue
            for file in files:
                _, ext = os.path.splitext(file)
                if ext.lower() not in [".py", ".java", ".cs", ".js", ".ts", ".md", ".pdf", ".txt"]:
                    continue
                
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, project_path)
                try:
                    current_files[rel_path] = {
                        "hash": self._calculate_file_hash(abs_path),
                        "size": os.path.getsize(abs_path)
                    }
                except Exception as e:
                    print(f"Error calculating hash/size for {abs_path}: {e}")

        # Đọc hash đã lưu trước đó từ PostgreSQL
        old_files = {}
        from app.database.postgres_client import postgres_client
        conn = postgres_client.get_connection()
        try:
            with conn.cursor() as cursor:
                # Lấy hoặc tạo thông tin project
                cursor.execute("SELECT id FROM projects WHERE name = %s", (project_name,))
                project_row = cursor.fetchone()
                if project_row:
                    project_id = project_row[0]
                else:
                    cursor.execute("""
                    INSERT INTO projects (name, owner, repo, branch, local_cache_path, last_commit_sha)
                    VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
                    """, (project_name, owner, repo_name, branch, project_path, last_commit_sha))
                    project_id = cursor.fetchone()[0]

                # Lấy các file metadata cũ
                cursor.execute("SELECT file_path, sha256_hash FROM file_metadata WHERE project_id = %s", (project_id,))
                old_files = {row[0]: row[1].strip() for row in cursor.fetchall()}

                # So sánh tìm sự thay đổi
                # 1. Tìm file mới và file bị sửa đổi
                for path, info in current_files.items():
                    file_hash = info["hash"]
                    if path not in old_files:
                        changes["added"].append(path)
                    elif old_files[path] != file_hash:
                        changes["modified"].append(path)
                        
                # 2. Tìm file bị xóa
                for path in old_files.keys():
                    if path not in current_files:
                        changes["deleted"].append(path)

                # Cập nhật PostgreSQL
                # Xóa file bị xóa
                if changes["deleted"]:
                    cursor.executemany("""
                    DELETE FROM file_metadata WHERE project_id = %s AND file_path = %s
                    """, [(project_id, path) for path in changes["deleted"]])
                
                # Thêm file mới
                if changes["added"]:
                    cursor.executemany("""
                    INSERT INTO file_metadata (project_id, file_path, sha256_hash, size_bytes, is_indexed)
                    VALUES (%s, %s, %s, %s, TRUE)
                    """, [(project_id, path, current_files[path]["hash"], current_files[path]["size"]) for path in changes["added"]])
                
                # Sửa file
                if changes["modified"]:
                    cursor.executemany("""
                    UPDATE file_metadata 
                    SET sha256_hash = %s, size_bytes = %s, is_indexed = TRUE, last_sync_at = CURRENT_TIMESTAMP
                    WHERE project_id = %s AND file_path = %s
                    """, [(current_files[path]["hash"], current_files[path]["size"], project_id, path) for path in changes["modified"]])

                # Cập nhật thông tin dự án
                cursor.execute("""
                UPDATE projects 
                SET last_commit_sha = %s, local_cache_path = %s, updated_at = CURRENT_TIMESTAMP 
                WHERE id = %s
                """, (last_commit_sha, project_path, project_id))

                conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"Error processing project diff in PostgreSQL: {e}")
            raise e
        finally:
            postgres_client.release_connection(conn)
            
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
