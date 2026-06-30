import time
from datetime import datetime, timedelta
from app.database.postgres_client import postgres_client
from psycopg2.extras import RealDictCursor
from app.config import settings

class GroqManager:
    @staticmethod
    def add_key(name: str, api_key: str, status: str = "active") -> int:
        conn = postgres_client.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO groq_keys (name, api_key, status, created_at) VALUES (%s, %s, %s, %s) RETURNING id",
                    (name, api_key, status, datetime.now())
                )
                key_id = cursor.fetchone()[0]
                conn.commit()
                return key_id
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            postgres_client.release_connection(conn)

    @staticmethod
    def get_all_keys() -> list:
        conn = postgres_client.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT k.id, k.name, k.api_key, k.status, k.cooldown_until, k.remaining_requests, k.limit_requests, k.remaining_tokens, k.limit_tokens, k.created_at, COALESCE(SUM(u.total_tokens), 0) as total_used_tokens
                    FROM groq_keys k
                    LEFT JOIN token_usage u ON k.id = u.key_id
                    GROUP BY k.id, k.name, k.api_key, k.status, k.cooldown_until, k.remaining_requests, k.limit_requests, k.remaining_tokens, k.limit_tokens, k.created_at
                    ORDER BY k.id DESC
                """)
                rows = cursor.fetchall()
                
                keys = []
                for r in rows:
                    raw_key = r["api_key"]
                    masked_key = raw_key
                    if len(raw_key) > 10:
                        masked_key = f"{raw_key[:6]}...{raw_key[-4:]}"
                        
                    keys.append({
                        "id": r["id"],
                        "name": r["name"],
                        "api_key": masked_key,
                        "status": r["status"],
                        "cooldown_until": r["cooldown_until"].isoformat() if isinstance(r["cooldown_until"], datetime) else r["cooldown_until"],
                        "remaining_requests": r["remaining_requests"],
                        "limit_requests": r["limit_requests"],
                        "remaining_tokens": r["remaining_tokens"],
                        "limit_tokens": r["limit_tokens"],
                        "created_at": r["created_at"].isoformat() if isinstance(r["created_at"], datetime) else r["created_at"],
                        "total_used_tokens": int(r["total_used_tokens"])
                    })
                return keys
        finally:
            postgres_client.release_connection(conn)

    @staticmethod
    def update_key_status(key_id: int, status: str):
        conn = postgres_client.get_connection()
        try:
            with conn.cursor() as cursor:
                # Nếu kích hoạt lại, xóa cooldown
                if status == "active":
                    cursor.execute("UPDATE groq_keys SET status = %s, cooldown_until = NULL WHERE id = %s", (status, key_id))
                else:
                    cursor.execute("UPDATE groq_keys SET status = %s WHERE id = %s", (status, key_id))
                conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            postgres_client.release_connection(conn)

    @staticmethod
    def update_key_limits(key_id: int, remaining_req: int, limit_req: int, remaining_tok: int, limit_tok: int, api_key: str = None):
        conn = postgres_client.get_connection()
        try:
            with conn.cursor() as cursor:
                if key_id is not None:
                    cursor.execute("""
                        UPDATE groq_keys 
                        SET remaining_requests = %s, limit_requests = %s, remaining_tokens = %s, limit_tokens = %s
                        WHERE id = %s
                    """, (remaining_req, limit_req, remaining_tok, limit_tok, key_id))
                elif api_key is not None:
                    # Nếu key_id bị None do fallback, đối chiếu bằng api_key
                    cursor.execute("""
                        UPDATE groq_keys 
                        SET remaining_requests = %s, limit_requests = %s, remaining_tokens = %s, limit_tokens = %s
                        WHERE api_key = %s OR api_key LIKE %s
                    """, (remaining_req, limit_req, remaining_tok, limit_tok, api_key, f"{api_key[:6]}%"))
                conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            postgres_client.release_connection(conn)

    @staticmethod
    def set_key_cooldown(key_id: int, cooldown_seconds: int):
        conn = postgres_client.get_connection()
        try:
            with conn.cursor() as cursor:
                cooldown_until = datetime.now() + timedelta(seconds=cooldown_seconds)
                cursor.execute(
                    "UPDATE groq_keys SET status = 'rate_limited', cooldown_until = %s WHERE id = %s",
                    (cooldown_until, key_id)
                )
                conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            postgres_client.release_connection(conn)

    @staticmethod
    def update_key_name(key_id: int, name: str):
        conn = postgres_client.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE groq_keys SET name = %s WHERE id = %s", (name, key_id))
                conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            postgres_client.release_connection(conn)

    @staticmethod
    def delete_key(key_id: int):
        conn = postgres_client.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM groq_keys WHERE id = %s", (key_id,))
                conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            postgres_client.release_connection(conn)

    @staticmethod
    def get_active_key_count() -> int:
        conn = postgres_client.get_connection()
        try:
            with conn.cursor() as cursor:
                # Tự động hồi phục các key hết cooldown
                cursor.execute(
                    "UPDATE groq_keys SET status = 'active', cooldown_until = NULL WHERE status = 'rate_limited' AND cooldown_until <= %s",
                    (datetime.now(),)
                )
                conn.commit()
                
                cursor.execute("SELECT COUNT(*) FROM groq_keys WHERE status = 'active'")
                return cursor.fetchone()[0]
        except Exception:
            return 0
        finally:
            postgres_client.release_connection(conn)

    @staticmethod
    def get_active_key() -> tuple:
        """
        Lấy ra 1 key đang hoạt động (trạng thái active) để gọi API.
        Hỗ trợ xoay vòng key theo kiểu chọn key ít sử dụng nhất gần đây.
        """
        conn = postgres_client.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Tự động hồi phục các key hết cooldown trước khi chọn
                cursor.execute(
                    "UPDATE groq_keys SET status = 'active', cooldown_until = NULL WHERE status = 'rate_limited' AND cooldown_until <= %s",
                    (datetime.now(),)
                )
                conn.commit()
                
                cursor.execute("""
                    SELECT k.id, k.api_key FROM groq_keys k
                    LEFT JOIN token_usage u ON k.id = u.key_id
                    WHERE k.status = 'active' AND (k.cooldown_until IS NULL OR k.cooldown_until <= %s)
                    GROUP BY k.id, k.api_key
                    ORDER BY COUNT(u.id) ASC
                    LIMIT 1
                """, (datetime.now(),))
                row = cursor.fetchone()
                
                if row:
                    return row["id"], row["api_key"]
        finally:
            postgres_client.release_connection(conn)
            
        # Fallback về config .env
        env_keys = settings.GROQ_API_KEYS
        if env_keys:
            return None, env_keys[0]
            
        return None, ""

    @staticmethod
    def log_usage(key_id: int, model: str, prompt_tokens: int, completion_tokens: int):
        conn = postgres_client.get_connection()
        try:
            with conn.cursor() as cursor:
                total_tokens = prompt_tokens + completion_tokens
                cursor.execute("""
                    INSERT INTO token_usage (key_id, model, prompt_tokens, completion_tokens, total_tokens, timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (key_id, model, prompt_tokens, completion_tokens, total_tokens, datetime.now()))
                conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            postgres_client.release_connection(conn)

    @staticmethod
    def get_summary_stats(time_range: str = "7d") -> dict:
        if time_range not in ["24h", "7d", "30d"]:
            time_range = "7d"
            
        conn = postgres_client.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # 1. Thống kê tổng quan
                cursor.execute("SELECT COUNT(*) FROM groq_keys")
                total_keys = cursor.fetchone()["count"]
                
                cursor.execute("SELECT COUNT(*) FROM groq_keys WHERE status = 'active'")
                active_keys = cursor.fetchone()["count"]
                
                cursor.execute("SELECT SUM(total_tokens) as total_tokens FROM token_usage")
                usage_row = cursor.fetchone()
                total_tokens = usage_row["total_tokens"] or 0
                
                # 2. Lượng token dùng theo mốc thời gian động
                daily_usage = []
                
                if time_range == "24h":
                    # Lấy dữ liệu 24 giờ qua (chia theo từng giờ)
                    for i in range(23, -1, -1):
                        start_time = datetime.now().replace(minute=0, second=0, microsecond=0) - timedelta(hours=i)
                        end_time = start_time + timedelta(hours=1)
                        cursor.execute("""
                            SELECT SUM(total_tokens) as tokens
                            FROM token_usage 
                            WHERE timestamp >= %s AND timestamp < %s
                        """, (start_time, end_time))
                        row = cursor.fetchone()
                        daily_usage.append({
                            "date": start_time.strftime("%H:00"),
                            "tokens": row["tokens"] or 0
                        })
                else:
                    # Lấy dữ liệu theo ngày (7 ngày hoặc 30 ngày qua)
                    days_limit = 7 if time_range == "7d" else 30
                    for i in range(days_limit - 1, -1, -1):
                        date_val = datetime.now() - timedelta(days=i)
                        cursor.execute("""
                            SELECT SUM(total_tokens) as tokens
                            FROM token_usage 
                            WHERE timestamp::date = %s::date
                        """, (date_val.date(),))
                        row = cursor.fetchone()
                        daily_usage.append({
                            "date": date_val.strftime("%Y-%m-%d"),
                            "tokens": row["tokens"] or 0
                        })
                    
                # 3. Phân bổ token theo model
                cursor.execute("""
                    SELECT model, SUM(total_tokens) as tokens
                    FROM token_usage
                    GROUP BY model
                """)
                model_usage = [{"model": r["model"], "tokens": r["tokens"]} for r in cursor.fetchall()]
                
                # 4. Phân bổ token theo key
                cursor.execute("""
                    SELECT k.name, SUM(u.total_tokens) as tokens
                    FROM token_usage u
                    JOIN groq_keys k ON u.key_id = k.id
                    GROUP BY u.key_id, k.name
                """)
                key_usage = [{"key_name": r["name"], "tokens": r["tokens"]} for r in cursor.fetchall()]
                
                # 5. Top 15 logs gần nhất
                cursor.execute("""
                    SELECT u.id, k.name as key_name, u.model, u.prompt_tokens, u.completion_tokens, u.total_tokens, u.timestamp
                    FROM token_usage u
                    LEFT JOIN groq_keys k ON u.key_id = k.id
                    ORDER BY u.id DESC
                    LIMIT 15
                """)
                recent_logs = []
                for r in cursor.fetchall():
                    recent_logs.append({
                        "id": r["id"],
                        "key_name": r["key_name"] or "System ENV Key",
                        "model": r["model"],
                        "prompt_tokens": r["prompt_tokens"],
                        "completion_tokens": r["completion_tokens"],
                        "total_tokens": r["total_tokens"],
                        "timestamp": r["timestamp"].isoformat() if isinstance(r["timestamp"], datetime) else r["timestamp"]
                    })
                    
                return {
                    "total_keys": total_keys,
                    "active_keys": active_keys,
                    "total_tokens": total_tokens,
                    "daily_usage": daily_usage,
                    "model_usage": model_usage,
                    "key_usage": key_usage,
                    "recent_logs": recent_logs
                }
        finally:
            postgres_client.release_connection(conn)

groq_manager = GroqManager()

