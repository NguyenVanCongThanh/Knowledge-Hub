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
                cursor.execute("SELECT id, name, api_key, status, created_at FROM groq_keys ORDER BY id DESC")
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
                        "created_at": r["created_at"].isoformat() if isinstance(r["created_at"], datetime) else r["created_at"]
                    })
                return keys
        finally:
            postgres_client.release_connection(conn)

    @staticmethod
    def update_key_status(key_id: int, status: str):
        conn = postgres_client.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE groq_keys SET status = %s WHERE id = %s", (status, key_id))
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
    def get_active_key() -> tuple:
        """
        Lấy ra 1 key đang hoạt động (trạng thái active) để gọi API.
        Hỗ trợ xoay vòng key theo kiểu chọn key ít sử dụng nhất gần đây.
        """
        conn = postgres_client.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT k.id, k.api_key FROM groq_keys k
                    LEFT JOIN token_usage u ON k.id = u.key_id
                    WHERE k.status = 'active'
                    GROUP BY k.id, k.api_key
                    ORDER BY COUNT(u.id) ASC
                    LIMIT 1
                """)
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
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Tra cứu đơn giá model
                cursor.execute("SELECT prompt_cost_per_m, completion_cost_per_m FROM model_prices WHERE model = %s", (model,))
                price_row = cursor.fetchone()
                
                if price_row:
                    prompt_rate = price_row["prompt_cost_per_m"]
                    completion_rate = price_row["completion_cost_per_m"]
                else:
                    prompt_rate = 0.59
                    completion_rate = 0.79
                    
                estimated_cost = ((prompt_tokens * prompt_rate) + (completion_tokens * completion_rate)) / 1_000_000.0
                total_tokens = prompt_tokens + completion_tokens
                
                cursor.execute("""
                    INSERT INTO token_usage (key_id, model, prompt_tokens, completion_tokens, total_tokens, estimated_cost, timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (key_id, model, prompt_tokens, completion_tokens, total_tokens, estimated_cost, datetime.now()))
                conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            postgres_client.release_connection(conn)

    @staticmethod
    def get_summary_stats() -> dict:
        conn = postgres_client.get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # 1. Thống kê tổng quan
                cursor.execute("SELECT COUNT(*) FROM groq_keys")
                total_keys = cursor.fetchone()["count"]
                
                cursor.execute("SELECT COUNT(*) FROM groq_keys WHERE status = 'active'")
                active_keys = cursor.fetchone()["count"]
                
                cursor.execute("SELECT SUM(total_tokens) as total_tokens, SUM(estimated_cost) as total_cost FROM token_usage")
                usage_row = cursor.fetchone()
                total_tokens = usage_row["total_tokens"] or 0
                total_cost = usage_row["total_cost"] or 0.0
                
                # 2. Lượng token dùng theo ngày (7 ngày gần nhất)
                daily_usage = []
                for i in range(6, -1, -1):
                    date_val = datetime.now() - timedelta(days=i)
                    cursor.execute("""
                        SELECT SUM(total_tokens) as tokens, SUM(estimated_cost) as cost
                        FROM token_usage 
                        WHERE timestamp::date = %s::date
                    """, (date_val.date(),))
                    row = cursor.fetchone()
                    daily_usage.append({
                        "date": date_val.strftime("%Y-%m-%d"),
                        "tokens": row["tokens"] or 0,
                        "cost": round(row["cost"] or 0.0, 4)
                    })
                    
                # 3. Phân bổ token theo model
                cursor.execute("""
                    SELECT model, SUM(total_tokens) as tokens, SUM(estimated_cost) as cost
                    FROM token_usage
                    GROUP BY model
                """)
                model_usage = [{"model": r["model"], "tokens": r["tokens"], "cost": round(r["cost"], 4)} for r in cursor.fetchall()]
                
                # 4. Phân bổ token theo key
                cursor.execute("""
                    SELECT k.name, SUM(u.total_tokens) as tokens, SUM(u.estimated_cost) as cost
                    FROM token_usage u
                    JOIN groq_keys k ON u.key_id = k.id
                    GROUP BY u.key_id, k.name
                """)
                key_usage = [{"key_name": r["name"], "tokens": r["tokens"], "cost": round(r["cost"], 4)} for r in cursor.fetchall()]
                
                # 5. Top 15 logs gần nhất
                cursor.execute("""
                    SELECT u.id, k.name as key_name, u.model, u.prompt_tokens, u.completion_tokens, u.total_tokens, u.estimated_cost, u.timestamp
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
                        "estimated_cost": round(r["estimated_cost"], 6),
                        "timestamp": r["timestamp"].isoformat() if isinstance(r["timestamp"], datetime) else r["timestamp"]
                    })
                    
                return {
                    "total_keys": total_keys,
                    "active_keys": active_keys,
                    "total_tokens": total_tokens,
                    "total_cost": round(total_cost, 4),
                    "daily_usage": daily_usage,
                    "model_usage": model_usage,
                    "key_usage": key_usage,
                    "recent_logs": recent_logs
                }
        finally:
            postgres_client.release_connection(conn)

groq_manager = GroqManager()
