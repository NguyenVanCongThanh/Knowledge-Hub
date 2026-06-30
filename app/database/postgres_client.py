import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from app.config import settings
from datetime import datetime
import time
import os

class PostgresClient:
    def __init__(self):
        self.connection_pool = None
        self._initialize_pool()

    def _initialize_pool(self):
        retries = 5
        backoff = 2.0
        for attempt in range(retries):
            try:
                self.connection_pool = pool.SimpleConnectionPool(
                    1, 10,
                    host=settings.POSTGRES_HOST,
                    port=settings.POSTGRES_PORT,
                    user=settings.POSTGRES_USER,
                    password=settings.POSTGRES_PASSWORD,
                    database=settings.POSTGRES_DB
                )
                print("Successfully established PostgreSQL connection pool.")
                break
            except Exception as e:
                print(f"Error connecting to PostgreSQL (attempt {attempt+1}/{retries}): {e}")
                if attempt == retries - 1:
                    raise e
                time.sleep(backoff)
                backoff *= 2.0

    def get_connection(self):
        if not self.connection_pool:
            self._initialize_pool()
        return self.connection_pool.getconn()

    def release_connection(self, conn):
        if self.connection_pool:
            self.connection_pool.putconn(conn)

    def init_db(self):
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                # Tạo bảng groq_keys
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS groq_keys (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    api_key TEXT NOT NULL,
                    status VARCHAR(50) NOT NULL DEFAULT 'active',
                    cooldown_until TIMESTAMP,
                    remaining_requests INTEGER,
                    limit_requests INTEGER,
                    remaining_tokens INTEGER,
                    limit_tokens INTEGER,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """)

                # Loại bỏ các giá trị mặc định của các cột giới hạn nếu bảng đã tồn tại từ trước
                cursor.execute("""
                ALTER TABLE groq_keys ALTER COLUMN remaining_requests DROP DEFAULT;
                ALTER TABLE groq_keys ALTER COLUMN limit_requests DROP DEFAULT;
                ALTER TABLE groq_keys ALTER COLUMN remaining_tokens DROP DEFAULT;
                ALTER TABLE groq_keys ALTER COLUMN limit_tokens DROP DEFAULT;
                """)

                # Tự động import các key mới từ file .env nếu chúng chưa tồn tại trong PostgreSQL
                env_keys = settings.GROQ_API_KEYS
                if env_keys:
                    imported_count = 0
                    for api_key in env_keys:
                        # Kiểm tra xem API key này đã tồn tại trong DB chưa
                        cursor.execute("SELECT COUNT(*) FROM groq_keys WHERE api_key = %s", (api_key,))
                        exists = cursor.fetchone()[0]
                        if exists == 0:
                            # Đếm số lượng key hiện tại để đánh số thứ tự tiếp theo cho tên key
                            cursor.execute("SELECT COUNT(*) FROM groq_keys")
                            current_total = cursor.fetchone()[0]
                            new_name = f"ENV Key {current_total + 1}"
                            
                            print(f"Importing new key from .env: {new_name}")
                            cursor.execute("""
                            INSERT INTO groq_keys (name, api_key, status, created_at)
                            VALUES (%s, %s, %s, %s)
                            """, (new_name, api_key, "active", datetime.now()))
                            imported_count += 1
                    if imported_count > 0:
                        conn.commit()
                        print(f"Imported {imported_count} new ENV keys successfully.")

                 # Tạo bảng token_usage
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS token_usage (
                    id SERIAL PRIMARY KEY,
                    key_id INTEGER REFERENCES groq_keys(id) ON DELETE SET NULL,
                    model VARCHAR(100) NOT NULL,
                    prompt_tokens INTEGER NOT NULL,
                    completion_tokens INTEGER NOT NULL,
                    total_tokens INTEGER NOT NULL,
                    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """)

                # Tạo extension uuid-ossp và các bảng metadata
                cursor.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"")
                
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    name VARCHAR(255) UNIQUE NOT NULL,
                    owner VARCHAR(150),
                    repo VARCHAR(150),
                    branch VARCHAR(100) DEFAULT 'main',
                    local_cache_path TEXT,
                    last_commit_sha VARCHAR(40),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
                """)

                cursor.execute("""
                CREATE TABLE IF NOT EXISTS file_metadata (
                    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    file_path TEXT NOT NULL,
                    sha256_hash CHAR(64) NOT NULL,
                    size_bytes BIGINT,
                    is_indexed BOOLEAN DEFAULT FALSE,
                    last_sync_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT unique_project_file_path UNIQUE (project_id, file_path)
                )
                """)

                cursor.execute("""
                CREATE TABLE IF NOT EXISTS sync_logs (
                    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    from_commit_sha VARCHAR(40),
                    to_commit_sha VARCHAR(40) NOT NULL,
                    status VARCHAR(50) NOT NULL,
                    files_added INT DEFAULT 0,
                    files_modified INT DEFAULT 0,
                    files_deleted INT DEFAULT 0,
                    error_message TEXT,
                    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP WITH TIME ZONE
                )
                """)

                conn.commit()
                print("PostgreSQL tables checked/created successfully.")
        except Exception as e:
            conn.rollback()
            print(f"Failed to initialize PostgreSQL tables: {e}")
            raise e
        finally:
            self.release_connection(conn)

postgres_client = PostgresClient()

# Khởi tạo db khi import (chỉ chạy trong môi trường chạy thật, bỏ qua khi import trong lúc run test cục bộ nếu cần)
# Ở đây ta để try-except để không làm lỗi app nếu DB chưa sẵn sàng ngay lập tức lúc start container
try:
    postgres_client.init_db()
except Exception:
    pass
