"""
Memory Service for NomadNest AI Agent.
Uses ChromaDB to store and retrieve user preferences, facts, and context.
"""
import os
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from datetime import datetime
from typing import List, Dict, Optional
import uuid

# Initialize ChromaDB client
# Use persistent storage in the 'data' directory
PERSIST_DIR = os.path.join(os.getcwd(), "data", "chromadb")
os.makedirs(PERSIST_DIR, exist_ok=True)

client = chromadb.PersistentClient(path=PERSIST_DIR)

# Use default SentenceTransformer embedding function (all-MiniLM-L6-v2)
# This model is small, fast, and good for general semantic search
default_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)

# Get or create the collection for user memories
collection = client.get_or_create_collection(
    name="user_memories",
    embedding_function=default_ef,
    metadata={"hnsw:space": "cosine"}
)


# Singleton instance pattern
class MemoryService:
    """Service to manage long-term memory for AI agents."""

    def __init__(self):
        self.collection = collection

    def add_memory(self, user_id: str, text: str, memory_type: str = "fact", metadata: Dict = None) -> str:
        """
        Add a new memory for a user.
        """
        memory_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()
        
        # Base metadata
        meta = {
            "user_id": user_id,
            "type": memory_type,
            "timestamp": timestamp,
            "source": "user_interaction"
        }
        
        # Merge optional metadata if provided
        if metadata:
            # ChromaDB metadata values must be int, float, str, or bool
            # Filter out incompatible types just in case
            valid_metadata = {k: v for k, v in metadata.items() if isinstance(v, (str, int, float, bool))}
            meta.update(valid_metadata)
        
        self.collection.add(
            documents=[text],
            metadatas=[meta],
            ids=[memory_id]
        )
        return memory_id

    def search_memories(self, user_id: str, query_text: str, limit: int = 5) -> List[Dict]:
        """
        Retrieve relevant memories for a user based on a query.
        """
        results = self.collection.query(
            query_texts=[query_text],
            n_results=limit,
            where={"user_id": user_id}
        )
        
        memories = []
        if results['documents'] and results['documents'][0]:
            for i, doc in enumerate(results['documents'][0]):
                metadata = results['metadatas'][0][i]
                memories.append({
                    "text": doc,
                    "type": metadata.get("type", "unknown"),
                    "timestamp": metadata.get("timestamp"),
                    "distance": results['distances'][0][i] if results.get('distances') else None
                })
        
        return memories
    
    # Alias for compatibility with ai_concierge.py usage
    def retrieve_relevant(self, user_id: str, query: str, limit: int = 5) -> List[str]:
        """Retrieve just the text of relevant memories."""
        memories = self.search_memories(user_id, query, limit)
        return [m["text"] for m in memories]

    def get_all_memories(self, user_id: str, limit: int = 20) -> List[Dict]:
        """Get the most recent memories for a user."""
        results = self.collection.get(
            where={"user_id": user_id},
            limit=limit,
            include=['documents', 'metadatas']
        )
        
        memories = []
        if results['documents']:
            for i, doc in enumerate(results['documents']):
                metadata = results['metadatas'][i]
                memories.append({
                    "text": doc,
                    "type": metadata.get("type", "unknown"),
                    "timestamp": metadata.get("timestamp")
                })
                
        # Sort by timestamp descending (if available)
        memories.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        return memories

    def delete_memory(self, user_id: str, memory_id: str) -> bool:
        """Delete a specific memory."""
        try:
            self.collection.delete(
                ids=[memory_id],
                where={"user_id": user_id}
            )
            return True
        except Exception:
            return False

# Export singleton instance
memory_service = MemoryService()
