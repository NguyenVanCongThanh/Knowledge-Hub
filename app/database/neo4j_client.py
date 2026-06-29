from typing import List, Dict, Any
from neo4j import GraphDatabase
from app.config import settings

class Neo4jDatabaseClient:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            settings.NEO4J_URI, 
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )

    def close(self):
        self.driver.close()

    def clear_project(self, project_name: str):
        """Xóa toàn bộ các nodes và relationships liên quan đến một project"""
        query = """
        MATCH (p:Project {name: $project_name})
        DETACH DELETE p
        """
        # Đồng thời xóa các nodes mồ côi liên quan đến project
        query_orphans = """
        MATCH (n) WHERE n.project = $project_name
        DETACH DELETE n
        """
        with self.driver.session() as session:
            session.run(query, project_name=project_name)
            session.run(query_orphans, project_name=project_name)

    def delete_file_nodes(self, project_name: str, file_path: str):
        """Xóa các node Class, Function, DocumentChunk được chứa trong file cụ thể trước khi re-index"""
        query = """
        MATCH (p:Project {name: $project_name})-[:HAS_FILE]->(f:File {path: $file_path})
        OPTIONAL MATCH (f)-[:CONTAINS]->(child)
        DETACH DELETE child
        DETACH DELETE f
        """
        with self.driver.session() as session:
            session.run(query, project_name=project_name, file_path=file_path)

    def ensure_project_node(self, project_name: str):
        query = """
        MERGE (p:Project {name: $project_name})
        ON CREATE SET p.created_at = timestamp()
        RETURN p
        """
        with self.driver.session() as session:
            session.run(query, project_name=project_name)

    def create_file_node(self, project_name: str, file_path: str, file_hash: str, file_type: str):
        self.ensure_project_node(project_name)
        query = """
        MATCH (p:Project {name: $project_name})
        MERGE (f:File {path: $file_path, project: $project_name})
        SET f.hash = $file_hash, f.type = $file_type, f.updated_at = timestamp()
        MERGE (p)-[:HAS_FILE]->(f)
        """
        with self.driver.session() as session:
            session.run(query, project_name=project_name, file_path=file_path, file_hash=file_hash, file_type=file_type)

    def create_class_node(self, project_name: str, file_path: str, class_name: str):
        query = """
        MATCH (f:File {path: $file_path, project: $project_name})
        MERGE (c:Class {name: $class_name, file_path: $file_path, project: $project_name})
        MERGE (f)-[:CONTAINS]->(c)
        """
        with self.driver.session() as session:
            session.run(query, project_name=project_name, file_path=file_path, class_name=class_name)

    def create_function_node(
        self, 
        project_name: str, 
        file_path: str, 
        func_name: str, 
        class_name: str = None, 
        start_line: int = 0, 
        end_line: int = 0
    ):
        with self.driver.session() as session:
            if class_name:
                query = """
                MATCH (c:Class {name: $class_name, file_path: $file_path, project: $project_name})
                MERGE (fn:Function {name: $func_name, file_path: $file_path, project: $project_name, class_name: $class_name})
                SET fn.start_line = $start_line, fn.end_line = $end_line
                MERGE (c)-[:CONTAINS]->(fn)
                """
                session.run(
                    query, 
                    project_name=project_name, 
                    file_path=file_path, 
                    class_name=class_name, 
                    func_name=func_name, 
                    start_line=start_line, 
                    end_line=end_line
                )
            else:
                query = """
                MATCH (f:File {path: $file_path, project: $project_name})
                MERGE (fn:Function {name: $func_name, file_path: $file_path, project: $project_name})
                SET fn.start_line = $start_line, fn.end_line = $end_line
                MERGE (f)-[:CONTAINS]->(fn)
                """
                session.run(
                    query, 
                    project_name=project_name, 
                    file_path=file_path, 
                    func_name=func_name, 
                    start_line=start_line, 
                    end_line=end_line
                )

    def create_document_chunk_node(self, project_name: str, file_path: str, chunk_id: str, heading: str):
        query = """
        MATCH (f:File {path: $file_path, project: $project_name})
        MERGE (ch:DocumentChunk {id: $chunk_id, project: $project_name})
        SET ch.heading = $heading, ch.file_path = $file_path
        MERGE (f)-[:CONTAINS]->(ch)
        """
        with self.driver.session() as session:
            session.run(query, project_name=project_name, file_path=file_path, chunk_id=chunk_id, heading=heading)

    def create_call_relationship(self, project_name: str, caller_name: str, callee_name: str):
        """Tạo quan hệ CALLS giữa các hàm"""
        query = """
        MATCH (caller:Function {project: $project_name, name: $caller_name})
        MATCH (callee:Function {project: $project_name, name: $callee_name})
        MERGE (caller)-[:CALLS]->(callee)
        """
        with self.driver.session() as session:
            session.run(query, project_name=project_name, caller_name=caller_name, callee_name=callee_name)

    def create_implements_relationship(self, project_name: str, file_path: str, entity_name: str, entity_type: str, chunk_id: str):
        """Tạo quan hệ IMPLEMENTS giữa code entity (Function/Class/File) và DocumentChunk"""
        if entity_type == "function":
            query = """
            MATCH (fn:Function {project: $project_name, file_path: $file_path, name: $entity_name})
            MATCH (ch:DocumentChunk {project: $project_name, id: $chunk_id})
            MERGE (fn)-[:IMPLEMENTS]->(ch)
            """
        elif entity_type == "class":
            query = """
            MATCH (c:Class {project: $project_name, file_path: $file_path, name: $entity_name})
            MATCH (ch:DocumentChunk {project: $project_name, id: $chunk_id})
            MERGE (c)-[:IMPLEMENTS]->(ch)
            """
        else:
            query = """
            MATCH (f:File {project: $project_name, path: $file_path})
            MATCH (ch:DocumentChunk {project: $project_name, id: $chunk_id})
            MERGE (f)-[:IMPLEMENTS]->(ch)
            """
        with self.driver.session() as session:
            session.run(query, project_name=project_name, file_path=file_path, entity_name=entity_name, chunk_id=chunk_id)

    def create_commit_node(self, project_name: str, commit_hash: str, message: str, author: str, date: float, modified_files: List[str]):
        query_commit = """
        MERGE (c:Commit {hash: $commit_hash, project: $project_name})
        SET c.message = $message, c.author = $author, c.date = $date
        """
        with self.driver.session() as session:
            session.run(query_commit, project_name=project_name, commit_hash=commit_hash, message=message, author=author, date=date)
            
            for file_path in modified_files:
                query_relation = """
                MATCH (c:Commit {hash: $commit_hash, project: $project_name})
                MATCH (f:File {path: $file_path, project: $project_name})
                MERGE (c)-[:MODIFIED]->(f)
                """
                session.run(query_relation, project_name=project_name, commit_hash=commit_hash, file_path=file_path)

    def get_related_nodes(self, project_name: str, file_path: str, name: str = None) -> List[Dict[str, Any]]:
        """Lấy các node lân cận (cách 1-2 bước nhảy) để mở rộng context tìm kiếm"""
        with self.driver.session() as session:
            if name:
                query = """
                MATCH (n {project: $project_name, file_path: $file_path, name: $name})-[r]-(m)
                RETURN labels(m) as labels, properties(m) as props, type(r) as rel_type
                LIMIT 20
                """
                result = session.run(query, project_name=project_name, file_path=file_path, name=name)
            else:
                query = """
                MATCH (n:File {project: $project_name, path: $file_path})-[r]-(m)
                RETURN labels(m) as labels, properties(m) as props, type(r) as rel_type
                LIMIT 20
                """
                result = session.run(query, project_name=project_name, file_path=file_path)
            
            neighbors = []
            for record in result:
                neighbors.append({
                    "labels": record["labels"],
                    "properties": record["props"],
                    "relationship": record["rel_type"]
                })
            return neighbors

    def create_extracted_entity(self, project_name: str, label: str, name: str, properties: Dict[str, Any]):
        """Tạo thực thể động được trích xuất bởi LLM"""
        # Đảm bảo label hợp lệ
        valid_labels = {"Concept", "Component", "Technology", "Artifact", "DocumentChunk", "Class", "Function", "File"}
        if label not in valid_labels:
            label = "Concept"
            
        query = f"""
        MERGE (e:{label} {{name: $name, project: $project_name}})
        ON CREATE SET e.created_by = 'LLM', e.created_at = timestamp()
        ON MATCH SET e.updated_at = timestamp()
        """
        for key in properties.keys():
            if key not in ["name", "project"]:
                query += f"\nSET e.{key} = ${key}"
                
        with self.driver.session() as session:
            session.run(query, project_name=project_name, name=name, **properties)

    def create_extracted_relationship(
        self, 
        project_name: str, 
        source_name: str, 
        source_label: str, 
        target_name: str, 
        target_label: str, 
        rel_type: str, 
        properties: Dict[str, Any]
    ):
        """Tạo quan hệ động được trích xuất bởi LLM"""
        valid_labels = {"Concept", "Component", "Technology", "Artifact", "DocumentChunk", "Class", "Function", "File"}
        if source_label not in valid_labels:
            source_label = "Concept"
        if target_label not in valid_labels:
            target_label = "Concept"
            
        valid_rel_types = {"DEPENDS_ON", "EXPLAINS", "USES", "RELATED_TO", "IMPLEMENTS", "CALLS", "MODIFIED"}
        if rel_type not in valid_rel_types:
            rel_type = "RELATED_TO"
            
        source_match_key = "id" if source_label == "DocumentChunk" else ("path" if source_label == "File" else "name")
        target_match_key = "id" if target_label == "DocumentChunk" else ("path" if target_label == "File" else "name")

        query = f"""
        MATCH (source:{source_label} {{{source_match_key}: $source_name, project: $project_name}})
        MATCH (target:{target_label} {{{target_match_key}: $target_name, project: $project_name}})
        MERGE (source)-[r:{rel_type}]->(target)
        ON CREATE SET r.created_by = 'LLM', r.created_at = timestamp()
        """
        for key in properties.keys():
            query += f"\nSET r.{key} = ${key}"
            
        with self.driver.session() as session:
            session.run(
                query, 
                project_name=project_name, 
                source_name=source_name, 
                target_name=target_name, 
                **properties
            )

# Singleton instance
neo4j_db = Neo4jDatabaseClient()
