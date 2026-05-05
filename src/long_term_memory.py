"""Persistent Long-Term Memory - Vector store of all agent experiences.

Stores conversations, decisions, code patterns, errors, and fixes for
retrieval during future tasks. Uses existing RAG infrastructure.

Features:
- Memory ingestion: conversations, decisions, errors, fixes
- Semantic search: find relevant past experiences
- Context injection: automatically surface memories for new tasks
- Persistence: JSON + vector store on disk
"""

import hashlib
import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.logger_config import get_logger

try:
    from src.codebase_rag import EmbeddingProvider, VectorStore
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False

logger = get_logger("LongTermMemory")


@dataclass
class MemoryEntry:
    """A single memory entry."""
    content: str
    memory_type: str  # conversation, decision, error, fix, pattern, insight
    timestamp: float = field(default_factory=time.time)
    tags: List[str] = field(default_factory=list)
    source: str = ""  # e.g., "autonomous_producer", "user_chat", "debugger"
    confidence: float = 0.5
    id: str = ""
    
    def __post_init__(self):
        if not self.id:
            self.id = hashlib.sha256(f"{self.content}:{self.timestamp}".encode()).hexdigest()[:16]


class LongTermMemory:
    """Persistent long-term memory using vector search."""
    
    def __init__(self, storage_path: str = ".crackedcode/memory", model: str = "qwen3:8b-gpu"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.entries: List[MemoryEntry] = []
        self.model = model
        
        self._embedding_provider: Optional[Any] = None
        self._vector_store: Optional[Any] = None
        
        if RAG_AVAILABLE:
            try:
                self._embedding_provider = EmbeddingProvider(model=model)
                self._vector_store = VectorStore()  # Uses default initialization
            except Exception as e:
                logger.warning(f"Could not initialize embeddings for memory: {e}")
        
        self._load_entries()
    
    def _load_entries(self):
        """Load persisted memory entries."""
        memory_file = self.storage_path / "memories.json"
        if memory_file.exists():
            try:
                data = json.loads(memory_file.read_text())
                for item in data:
                    entry = MemoryEntry(
                        content=item["content"],
                        memory_type=item["memory_type"],
                        timestamp=item["timestamp"],
                        tags=item.get("tags", []),
                        source=item.get("source", ""),
                        confidence=item.get("confidence", 0.5),
                        id=item.get("id", ""),
                    )
                    self.entries.append(entry)
                logger.info(f"Loaded {len(self.entries)} memories from {memory_file}")
            except Exception as e:
                logger.error(f"Failed to load memories: {e}")
    
    def _save_entries(self):
        """Persist memory entries to disk."""
        memory_file = self.storage_path / "memories.json"
        try:
            data = [asdict(e) for e in self.entries]
            memory_file.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.error(f"Failed to save memories: {e}")
    
    def remember(self, content: str, memory_type: str = "insight", tags: List[str] = None,
                 source: str = "", confidence: float = 0.5) -> MemoryEntry:
        """Store a new memory.
        
        Args:
            content: The memory content
            memory_type: Type of memory (conversation, decision, error, fix, pattern, insight)
            tags: Searchable tags
            source: Which component created this memory
            confidence: Confidence in the memory (0-1)
            
        Returns:
            The stored MemoryEntry
        """
        entry = MemoryEntry(
            content=content,
            memory_type=memory_type,
            tags=tags or [],
            source=source,
            confidence=confidence,
        )
        
        self.entries.append(entry)
        
        # Add to vector store if available
        if self._vector_store and self._embedding_provider:
            try:
                embedding = self._embedding_provider.embed(content)
                self._vector_store.add(entry.id, embedding, {
                    "content": content,
                    "type": memory_type,
                    "tags": tags or [],
                    "source": source,
                })
            except Exception as e:
                logger.warning(f"Failed to add memory to vector store: {e}")
        
        self._save_entries()
        logger.info(f"Memory stored: [{memory_type}] {content[:60]}...")
        return entry
    
    def recall(self, query: str, memory_type: str = None, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search memories by semantic similarity.
        
        Args:
            query: Search query
            memory_type: Filter by memory type
            top_k: Number of results
            
        Returns:
            List of matching memories with scores
        """
        results = []
        
        # Vector search if available
        if self._vector_store and self._embedding_provider and len(self.entries) > 0:
            try:
                query_embedding = self._embedding_provider.embed(query)
                vector_results = self._vector_store.search(query_embedding, top_k=top_k * 2)
                
                for result in vector_results:
                    entry = next((e for e in self.entries if e.id == result["id"]), None)
                    if entry:
                        if memory_type and entry.memory_type != memory_type:
                            continue
                        results.append({
                            "entry": entry,
                            "score": result["score"],
                            "content": entry.content,
                            "type": entry.memory_type,
                            "source": entry.source,
                            "timestamp": entry.timestamp,
                        })
            except Exception as e:
                logger.warning(f"Vector search failed, falling back to keyword: {e}")
        
        # Fallback to keyword matching
        if not results:
            query_lower = query.lower()
            for entry in self.entries:
                if memory_type and entry.memory_type != memory_type:
                    continue
                score = 0
                if query_lower in entry.content.lower():
                    score += 1.0
                for tag in entry.tags:
                    if query_lower in tag.lower():
                        score += 0.5
                if score > 0:
                    results.append({
                        "entry": entry,
                        "score": score,
                        "content": entry.content,
                        "type": entry.memory_type,
                        "source": entry.source,
                        "timestamp": entry.timestamp,
                    })
        
        # Sort by score and limit
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]
    
    def get_context_for_prompt(self, query: str, top_k: int = 3) -> str:
        """Get formatted memory context for LLM prompt injection.
        
        Args:
            query: Current task/query
            top_k: Number of memories to include
            
        Returns:
            Formatted context string or empty string
        """
        memories = self.recall(query, top_k=top_k)
        if not memories:
            return ""
        
        lines = ["## Relevant Past Experiences\n"]
        for i, mem in enumerate(memories, 1):
            age_days = (time.time() - mem["timestamp"]) / 86400
            age_str = f"{age_days:.0f} days ago" if age_days > 1 else "recently"
            lines.append(f"{i}. [{mem['type'].upper()}] ({age_str}) {mem['content']}")
        
        return "\n".join(lines) + "\n"
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        by_type = {}
        for entry in self.entries:
            by_type[entry.memory_type] = by_type.get(entry.memory_type, 0) + 1
        
        return {
            "total_memories": len(self.entries),
            "by_type": by_type,
            "vector_store_enabled": self._vector_store is not None,
            "storage_path": str(self.storage_path),
        }
    
    def clear(self):
        """Clear all memories."""
        self.entries.clear()
        if self._vector_store:
            self._vector_store.clear()
        self._save_entries()
        logger.info("All memories cleared")


# Singleton instance
_memory_instance: Optional[LongTermMemory] = None

def get_long_term_memory(storage_path: str = ".crackedcode/memory", model: str = "qwen3:8b-gpu") -> LongTermMemory:
    """Get the global LongTermMemory instance."""
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = LongTermMemory(storage_path=storage_path, model=model)
    return _memory_instance
