import httpx
import json
import asyncio
import time
from typing import Dict, Any, List
from app.config import settings
from app.services.groq_manager import groq_manager

class LLMService:
    def __init__(self):
        self.model = settings.GROQ_MODEL_NAME
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"
        self._cooldown_until = {}  # {key: timestamp}
        self._lock = asyncio.Lock()

    def _cooldown_key(self, key: str, duration: float = 30.0):
        """Puts a key into cooldown due to rate limits."""
        self._cooldown_until[key] = time.time() + duration
        print(f"Key {key[:12]}... is cooling down for {duration} seconds.")

    async def call_groq_json(self, system_prompt: str, user_prompt: str, retries: int = 5, initial_backoff: float = 2.0) -> Dict[str, Any]:
        """Calls Groq API and expects a JSON response, with key rotation and exponential backoff."""
        backoff = initial_backoff
        for attempt in range(retries):
            # Lấy key năng động từ SQLite
            async with self._lock:
                # Xoay vòng key và lọc ra các key đang cooldown
                now = time.time()
                key_id, api_key = None, ""
                
                # Gọi manager lấy key
                key_id, api_key = groq_manager.get_active_key()
                
                # Nếu key được chọn đang trong thời gian cooldown, tiếp tục tìm key dự phòng trong .env
                if api_key in self._cooldown_until and self._cooldown_until[api_key] > now:
                    # Nếu key chính từ DB bị cooldown, thử fallback về các key trong .env khác
                    env_keys = settings.GROQ_API_KEYS
                    for ek in env_keys:
                        if ek not in self._cooldown_until or self._cooldown_until[ek] <= now:
                            api_key = ek
                            key_id = None
                            break

            if not api_key:
                print("Warning: No GROQ API key is configured or all keys are in cooldown. Returning empty extraction graph.")
                return {"entities": [], "relationships": []}

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.1
            }

            # Đo lường số key active để tính delay interval động chống quá tải RPM
            active_count = groq_manager.get_active_key_count()
            if active_count > 0:
                # RPM giới hạn của 1 key là 30. Hệ số an toàn 1.15 => Khoảng trễ tối thiểu
                delay_interval = (60.0 / (active_count * 30.0)) * 1.15
                await asyncio.sleep(delay_interval)

            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(self.api_url, headers=headers, json=payload)
                    
                    if response.status_code == 200:
                        data = response.json()
                        content = data["choices"][0]["message"]["content"]
                        
                        # Trích xuất và lưu log token sử dụng
                        usage = data.get("usage", {})
                        prompt_tokens = usage.get("prompt_tokens", 0)
                        completion_tokens = usage.get("completion_tokens", 0)
                        total_tokens = usage.get("total_tokens", 0)
                        
                        # Ghi nhận log token vào Database
                        groq_manager.log_usage(key_id, self.model, prompt_tokens, completion_tokens)
                        
                        # Cập nhật Rate Limit headers (remaining, limit) của key vào Database
                        try:
                            rem_req = response.headers.get("x-ratelimit-remaining-requests")
                            lim_req = response.headers.get("x-ratelimit-limit-requests")
                            rem_tok = response.headers.get("x-ratelimit-remaining-tokens")
                            lim_tok = response.headers.get("x-ratelimit-limit-tokens")
                            if rem_req and lim_req and rem_tok and lim_tok:
                                groq_manager.update_key_limits(
                                    key_id, 
                                    int(rem_req), 
                                    int(lim_req), 
                                    int(rem_tok), 
                                    int(lim_tok),
                                    api_key=api_key
                                )
                        except Exception as limit_err:
                            print(f"Lỗi cập nhật rate limit headers: {limit_err}")
                        
                        print(f"🔑 [Key: {api_key[:12]}...] model: {self.model} | Prompt: {prompt_tokens} tkn | Completion: {completion_tokens} tkn | Total: {total_tokens} tkn")
                        
                        return json.loads(content)
                    
                    elif response.status_code == 429:
                        # Đọc số giây chờ reset từ header của Groq
                        retry_after_str = response.headers.get("retry-after")
                        cooldown_duration = 30.0
                        if retry_after_str and retry_after_str.isdigit():
                            cooldown_duration = float(retry_after_str)
                        else:
                            reset_requests = response.headers.get("x-ratelimit-reset-requests")
                            if reset_requests:
                                if "ms" in reset_requests:
                                    cooldown_duration = float(reset_requests.replace("ms", "")) / 1000.0
                                elif "s" in reset_requests:
                                    cooldown_duration = float(reset_requests.replace("s", ""))
                        
                        self._cooldown_key(api_key, duration=cooldown_duration)
                        if key_id is not None:
                            groq_manager.set_key_cooldown(key_id, int(cooldown_duration))
                        print(f"Groq API Rate Limit (429) hit on key {api_key[:12]}... Cooldown for {cooldown_duration}s. Attempt {attempt + 1}/{retries}. Retrying...")
                        await asyncio.sleep(1.0)
                    else:
                        print(f"Groq API error HTTP {response.status_code}: {response.text}")
                        await asyncio.sleep(backoff)
                        backoff *= 2.0
            except Exception as e:
                print(f"Exception calling Groq API: {e}. Attempt {attempt + 1}/{retries}. Retrying in {backoff}s...")
                await asyncio.sleep(backoff)
                backoff *= 2.0

        raise Exception("Failed to call Groq API after multiple retries.")


    async def extract_knowledge(self, content_chunk: str, chunk_type: str, file_path: str) -> Dict[str, Any]:
        """Extracts nodes and relationships from a text chunk of document/code."""
        system_prompt = """You are a highly precise Knowledge Graph Extraction assistant. 
Your task is to analyze the provided text chunk (from a software project's documentation or source code) and extract key Entities (nodes) and Relationships (edges).

## Entity Types:
- Concept: Conceptual ideas, design patterns, algorithms, or functional features (e.g., "RAG", "OAuth2", "Embedding", "Chunking").
- Component: System modules, libraries, or architectural layers (e.g., "Neo4j Database Client", "Git Service", "FastAPI").
- Technology: Programming languages, frameworks, protocols, or tools (e.g., "Python", "Docker", "Neo4j", "Cypher", "Git").
- Artifact: Configuration files, build definitions, or data files (e.g., "Dockerfile", ".env", "requirements.txt").

## Relationship Types:
- DEPENDS_ON: Indicates a component or concept relies on another (e.g., [FastAPI] -DEPENDS_ON-> [Python]).
- EXPLAINS: An documentation chunk explaining a class, function, or concept (e.g., [DocumentChunk] -EXPLAINS-> [RAG]).
- USES: General utilization relationship (e.g., [IndexerService] -USES-> [Qdrant]).
- RELATED_TO: General conceptual connection.

## Output Format:
You MUST respond in JSON format with EXACTLY this structure:
{
  "entities": [
    {
      "name": "Entity Name (clean, capitalized, unique)",
      "label": "Concept|Component|Technology|Artifact",
      "properties": {
        "description": "Brief description of what this entity is"
      }
    }
  ],
  "relationships": [
    {
      "source": "Entity Name",
      "target": "Entity Name",
      "type": "DEPENDS_ON|EXPLAINS|USES|RELATED_TO",
      "properties": {
        "description": "Context of the connection"
      }
    }
  ]
}

Ensure all extracted entity names match exactly between the 'entities' list and the 'relationships' list.
Keep names clean and generic so they can merge nicely across chunks. Do not create duplicates.
Only extract directly supported entities and relations. Do not extrapolate too much.
"""
        
        user_prompt = f"Analyze the following {chunk_type} chunk from the file '{file_path}':\n\n{content_chunk}"
        try:
            result = await self.call_groq_json(system_prompt, user_prompt)
            return result
        except Exception as e:
            print(f"Error during LLM extraction: {e}")
            return {"entities": [], "relationships": []}

llm_service = LLMService()
