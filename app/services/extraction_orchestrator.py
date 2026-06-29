import asyncio
from typing import List, Dict, Any
from app.config import settings
from app.services.llm_service import llm_service
from app.database.neo4j_client import neo4j_db

class ExtractionOrchestrator:
    def __init__(self):
        self.semaphore = asyncio.Semaphore(settings.LLM_EXTRACTION_CONCURRENCY)

    async def process_chunk(self, project_name: str, file_path: str, chunk: Dict[str, Any]):
        """Processes a single chunk: extracts data using LLM and saves to Neo4j."""
        async with self.semaphore:
            chunk_text = chunk.get("text", "")
            chunk_type = chunk.get("type", "document")
            entity_type = chunk.get("entity_type", "document")
            
            # Determine source node details in Neo4j
            source_name = ""
            source_label = ""
            
            if entity_type == "class":
                source_name = chunk.get("name", "")
                source_label = "Class"
            elif entity_type == "function":
                source_name = chunk.get("name", "")
                source_label = "Function"
            elif entity_type == "file":
                source_name = file_path
                source_label = "File"
            else:
                source_name = chunk.get("id", "")
                source_label = "DocumentChunk"

            if not chunk_text or not source_name:
                return

            print(f"Extracting knowledge from {source_label} '{source_name}' in {file_path}...")
            
            # 1. Call LLM to extract knowledge graph
            extracted_graph = await llm_service.extract_knowledge(chunk_text, chunk_type, file_path)
            
            entities = extracted_graph.get("entities", [])
            relationships = extracted_graph.get("relationships", [])
            
            # 2. Ingest into Neo4j
            # Create the extracted entities first
            for ent in entities:
                name = ent.get("name")
                label = ent.get("label", "Concept")
                props = ent.get("properties", {})
                if not name:
                    continue
                
                # Create the custom entity node
                neo4j_db.create_extracted_entity(project_name, label, name, props)
                
                # Link source code/document chunk to this extracted entity
                neo4j_db.create_extracted_relationship(
                    project_name=project_name,
                    source_name=source_name,
                    source_label=source_label,
                    target_name=name,
                    target_label=label,
                    rel_type="EXPLAINS",
                    properties={"description": "Mentioned or explained in chunk", "file_path": file_path}
                )

            # Create relationships between extracted entities
            for rel in relationships:
                source = rel.get("source")
                target = rel.get("target")
                rel_type = rel.get("type", "RELATED_TO")
                props = rel.get("properties", {})
                
                if not source or not target:
                    continue
                
                # Find matching label from the entities list
                source_label_extracted = "Concept"
                target_label_extracted = "Concept"
                for ent in entities:
                    if ent.get("name") == source:
                        source_label_extracted = ent.get("label", "Concept")
                    if ent.get("name") == target:
                        target_label_extracted = ent.get("label", "Concept")
                        
                neo4j_db.create_extracted_relationship(
                    project_name=project_name,
                    source_name=source,
                    source_label=source_label_extracted,
                    target_name=target,
                    target_label=target_label_extracted,
                    rel_type=rel_type,
                    properties=props
                )

    async def process_project_chunks(self, project_name: str, file_path: str, chunks: List[Dict[str, Any]]):
        """Orchestrates extraction for multiple chunks asynchronously."""
        tasks = []
        for chunk in chunks:
            tasks.append(self.process_chunk(project_name, file_path, chunk))
        
        if tasks:
            await asyncio.gather(*tasks)

extraction_orchestrator = ExtractionOrchestrator()
