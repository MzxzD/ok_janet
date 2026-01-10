"""
Memory Manager - Handles client-specific memory isolation
"""
import os
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import json


class MemoryManager:
    """Manages isolated memory contexts for multiple clients"""
    
    def __init__(self, base_memory_path: str = "./memory_vaults"):
        self.base_memory_path = Path(base_memory_path)
        self.base_memory_path.mkdir(parents=True, exist_ok=True)
        self.client_memories: Dict[str, List[Dict[str, Any]]] = {}
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database with client_id support"""
        db_path = self.base_memory_path / "janet_memory.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Create conversations table with client_id
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
        """)
        
        # Create index on client_id for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_client_id 
            ON conversations(client_id)
        """)
        
        # Create memories table (for ChromaDB-like functionality)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id TEXT NOT NULL,
                content TEXT NOT NULL,
                embedding TEXT,
                metadata TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_memories_client_id 
            ON memories(client_id)
        """)
        
        conn.commit()
        conn.close()
    
    def get_client_memory_context(self, client_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get conversation history for a client"""
        if client_id in self.client_memories:
            return self.client_memories[client_id][-limit:]
        
        # Load from database
        db_path = self.base_memory_path / "janet_memory.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT role, content, timestamp, metadata
            FROM conversations
            WHERE client_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (client_id, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        # Convert to memory context format
        context = []
        for role, content, timestamp, metadata in reversed(rows):
            context.append({
                "role": role,
                "content": content,
                "timestamp": timestamp,
                "metadata": json.loads(metadata) if metadata else {}
            })
        
        self.client_memories[client_id] = context
        return context
    
    def add_to_memory(self, client_id: str, role: str, content: str, 
                     metadata: Optional[Dict[str, Any]] = None):
        """Add a message to client's memory"""
        # Add to in-memory cache
        if client_id not in self.client_memories:
            self.client_memories[client_id] = []
        
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        self.client_memories[client_id].append(message)
        
        # Persist to database
        db_path = self.base_memory_path / "janet_memory.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO conversations (client_id, role, content, metadata)
            VALUES (?, ?, ?, ?)
        """, (client_id, role, content, json.dumps(metadata or {})))
        
        conn.commit()
        conn.close()
    
    def search_memories(self, client_id: str, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search client's memories (simple text search for now)"""
        db_path = self.base_memory_path / "janet_memory.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT content, metadata, timestamp
            FROM memories
            WHERE client_id = ? AND content LIKE ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (client_id, f"%{query}%", limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        results = []
        for content, metadata, timestamp in rows:
            results.append({
                "content": content,
                "metadata": json.loads(metadata) if metadata else {},
                "timestamp": timestamp
            })
        
        return results
    
    def save_memory(self, client_id: str, content: str, 
                   embedding: Optional[List[float]] = None,
                   metadata: Optional[Dict[str, Any]] = None):
        """Save a memory (for ChromaDB-like functionality)"""
        db_path = self.base_memory_path / "janet_memory.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        embedding_str = json.dumps(embedding) if embedding else None
        
        cursor.execute("""
            INSERT INTO memories (client_id, content, embedding, metadata)
            VALUES (?, ?, ?, ?)
        """, (client_id, content, embedding_str, json.dumps(metadata or {})))
        
        conn.commit()
        conn.close()
    
    def clear_client_memory(self, client_id: str):
        """Clear all memory for a client"""
        if client_id in self.client_memories:
            del self.client_memories[client_id]
        
        db_path = self.base_memory_path / "janet_memory.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM conversations WHERE client_id = ?", (client_id,))
        cursor.execute("DELETE FROM memories WHERE client_id = ?", (client_id,))
        
        conn.commit()
        conn.close()
    
    def get_client_count(self) -> int:
        """Get number of unique clients with memory"""
        db_path = self.base_memory_path / "janet_memory.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(DISTINCT client_id) FROM conversations")
        count = cursor.fetchone()[0]
        
        conn.close()
        return count
    
    def export_context(self, client_id: str, limit: int = 100) -> Dict[str, Any]:
        """
        Export conversation context for soul transfer.
        
        Args:
            client_id: Client identifier
            limit: Maximum number of messages to export
            
        Returns:
            Dictionary containing exported context
        """
        context = self.get_client_memory_context(client_id, limit=limit)
        return {
            "client_id": client_id,
            "messages": context,
            "exported_at": datetime.utcnow().isoformat()
        }
    
    def import_context(self, exported_context: Dict[str, Any]) -> int:
        """
        Import conversation context from soul transfer.
        
        Args:
            exported_context: Exported context dictionary
            
        Returns:
            Number of messages imported
        """
        client_id = exported_context.get("client_id")
        messages = exported_context.get("messages", [])
        
        if not client_id:
            return 0
        
        imported_count = 0
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")
            if role and content:
                self.add_to_memory(
                    client_id,
                    role,
                    content,
                    metadata=msg.get("metadata", {})
                )
                imported_count += 1
        
        return imported_count
