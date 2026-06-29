import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from app.config import settings
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
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """)

                # Tạo bảng token_usage
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS token_usage (
                    id SERIAL PRIMARY KEY,
                    key_id INTEGER REFERENCES groq_keys(id) ON DELETE SET NULL,
                    model VARCHAR(100) NOT NULL,
                    prompt_tokens INTEGER NOT NULL,
                    completion_tokens INTEGER NOT NULL,
                    total_tokens INTEGER NOT NULL,
                    estimated_cost DOUBLE PRECISION NOT NULL,
                    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """)

                # Tạo bảng model_prices
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS model_prices (
                    model VARCHAR(100) PRIMARY KEY,
                    prompt_cost_per_m DOUBLE PRECISION NOT NULL,
                    completion_cost_per_m DOUBLE PRECISION NOT NULL
                )
                """)

                # Chèn dữ liệu giá model mặc định
                default_prices = [
                    ("llama3-70b-8192", 0.59, 0.79),
                    ("llama3-8b-8192", 0.05, 0.08),
                    ("mixtral-8x7b-32768", 0.24, 0.24),
                    ("gemma2-9b-it", 0.20, 0.20),
                    ("llama-3.1-405b-reasoning", 5.33, 5.33),
                    ("llama-3.1-70b-versatile", 0.59, 0.79),
                    ("llama-3.1-8b-instant", 0.05, 0.08)
                ]
                for model, prompt_p, completion_p in default_prices:
                    cursor.execute("""
                    INSERT INTO model_prices (model, prompt_cost_per_m, completion_cost_per_m)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (model) DO NOTHING
                    """, (model, prompt_p, completion_p))

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
