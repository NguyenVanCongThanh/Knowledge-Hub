import httpx
import json
import asyncio
from typing import Dict, Any, List
from app.config import settings

class LLMService:
    def __init__(self):
        self.api_key = settings.GROQ_API_KEY
        self.model = settings.GROQ_MODEL_NAME
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"

    async def call_groq_json(self, system_prompt: str, user_prompt: str, retries: int = 5, initial_backoff: float = 2.0) -> Dict[str, Any]:
        """Calls Groq API and expects a JSON response, with exponential backoff on rate limits."""
        if not self.api_key:
            # Fallback mock/empty if key is not configured to prevent crashes
            print("Warning: GROQ_API_KEY is not configured. Returning empty extraction graph.")
            return {"entities": [], "relationships": []}

        headers = {
            "Authorization": f"Bearer {self.api_key}",
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

        backoff = initial_backoff
        for attempt in range(retries):
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(self.api_url, headers=headers, json=payload)
                    
                    if response.status_code == 200:
                        data = response.json()
                        content = data["choices"][0]["message"]["content"]
                        return json.loads(content)
                    
                    elif response.status_code == 429:
                        # Rate limit hit, backoff and retry
                        print(f"Groq API Rate Limit (429) hit. Attempt {attempt + 1}/{retries}. Retrying in {backoff}s...")
                        await asyncio.sleep(backoff)
                        backoff *= 2.0
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
