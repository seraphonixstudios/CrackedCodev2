"""Conversation Manager - Persistent chat history with search and export.

Features:
- SQLite-backed chat storage
- Named conversations with metadata
- Search across all conversations
- Export to markdown
- Auto-save every turn
- Resume on startup
"""

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.logger_config import get_logger

logger = get_logger("ConversationManager")


@dataclass
class ConversationTurn:
    """A single turn in a conversation."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: float = field(default_factory=time.time)
    user_message: str = ""
    assistant_response: str = ""
    intent: str = "chat"
    model_used: str = ""
    execution_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Conversation:
    """A conversation session."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = "New Conversation"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    turns: List[ConversationTurn] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "turn_count": len(self.turns),
            "tags": self.tags,
            "metadata": self.metadata,
        }


class ConversationManager:
    """Manages persistent conversation history with SQLite."""
    
    def __init__(self, db_path: str = ".crackedcode/conversations.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._current_conversation: Optional[Conversation] = None
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite database with tables."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                
                # Conversations table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS conversations (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        created_at REAL NOT NULL,
                        updated_at REAL NOT NULL,
                        tags TEXT,
                        metadata TEXT
                    )
                """)
                
                # Turns table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS turns (
                        id TEXT PRIMARY KEY,
                        conversation_id TEXT NOT NULL,
                        timestamp REAL NOT NULL,
                        user_message TEXT,
                        assistant_response TEXT,
                        intent TEXT,
                        model_used TEXT,
                        execution_time REAL,
                        metadata TEXT,
                        FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                    )
                """)
                
                # Indexes for search performance
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_turns_conv_id 
                    ON turns(conversation_id)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_turns_user_msg 
                    ON turns(user_message)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_turns_assistant 
                    ON turns(assistant_response)
                """)
                
                conn.commit()
                logger.info(f"Conversation database initialized: {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to init conversation DB: {e}")
    
    def create_conversation(self, name: str = None, tags: List[str] = None) -> Conversation:
        """Create a new conversation."""
        conv = Conversation(
            name=name or f"Conversation {time.strftime('%Y-%m-%d %H:%M')}",
            tags=tags or [],
        )
        
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO conversations (id, name, created_at, updated_at, tags, metadata)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        conv.id,
                        conv.name,
                        conv.created_at,
                        conv.updated_at,
                        json.dumps(conv.tags),
                        json.dumps(conv.metadata),
                    ),
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to create conversation: {e}")
        
        self._current_conversation = conv
        logger.info(f"Created conversation: {conv.name} ({conv.id})")
        return conv
    
    def add_turn(
        self,
        user_message: str,
        assistant_response: str,
        intent: str = "chat",
        model_used: str = "",
        execution_time: float = 0.0,
        metadata: Dict[str, Any] = None,
    ) -> ConversationTurn:
        """Add a turn to the current conversation."""
        if not self._current_conversation:
            self.create_conversation()
        
        turn = ConversationTurn(
            user_message=user_message,
            assistant_response=assistant_response,
            intent=intent,
            model_used=model_used,
            execution_time=execution_time,
            metadata=metadata or {},
        )
        
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                
                # Insert turn
                cursor.execute(
                    """
                    INSERT INTO turns (id, conversation_id, timestamp, user_message,
                                     assistant_response, intent, model_used, execution_time, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        turn.id,
                        self._current_conversation.id,
                        turn.timestamp,
                        turn.user_message,
                        turn.assistant_response,
                        turn.intent,
                        turn.model_used,
                        turn.execution_time,
                        json.dumps(turn.metadata),
                    ),
                )
                
                # Update conversation timestamp
                self._current_conversation.updated_at = time.time()
                cursor.execute(
                    "UPDATE conversations SET updated_at = ? WHERE id = ?",
                    (self._current_conversation.updated_at, self._current_conversation.id),
                )
                
                conn.commit()
                
                # Add to in-memory list
                self._current_conversation.turns.append(turn)
        except Exception as e:
            logger.error(f"Failed to add turn: {e}")
        
        return turn
    
    def load_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Load a conversation from the database."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                
                # Load conversation
                cursor.execute(
                    "SELECT id, name, created_at, updated_at, tags, metadata FROM conversations WHERE id = ?",
                    (conversation_id,),
                )
                row = cursor.fetchone()
                
                if not row:
                    return None
                
                conv = Conversation(
                    id=row[0],
                    name=row[1],
                    created_at=row[2],
                    updated_at=row[3],
                    tags=json.loads(row[4]) if row[4] else [],
                    metadata=json.loads(row[5]) if row[5] else {},
                )
                
                # Load turns
                cursor.execute(
                    """
                    SELECT id, timestamp, user_message, assistant_response, intent,
                           model_used, execution_time, metadata
                    FROM turns
                    WHERE conversation_id = ?
                    ORDER BY timestamp
                    """,
                    (conversation_id,),
                )
                
                for turn_row in cursor.fetchall():
                    turn = ConversationTurn(
                        id=turn_row[0],
                        timestamp=turn_row[1],
                        user_message=turn_row[2],
                        assistant_response=turn_row[3],
                        intent=turn_row[4],
                        model_used=turn_row[5],
                        execution_time=turn_row[6],
                        metadata=json.loads(turn_row[7]) if turn_row[7] else {},
                    )
                    conv.turns.append(turn)
                
                self._current_conversation = conv
                logger.info(f"Loaded conversation: {conv.name} ({len(conv.turns)} turns)")
                return conv
        except Exception as e:
            logger.error(f"Failed to load conversation: {e}")
            return None
    
    def list_conversations(self, limit: int = 50) -> List[Conversation]:
        """List all conversations ordered by most recent."""
        conversations = []
        
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, name, created_at, updated_at, tags, metadata
                    FROM conversations
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                )
                
                for row in cursor.fetchall():
                    conv = Conversation(
                        id=row[0],
                        name=row[1],
                        created_at=row[2],
                        updated_at=row[3],
                        tags=json.loads(row[4]) if row[4] else [],
                        metadata=json.loads(row[5]) if row[5] else {},
                    )
                    conversations.append(conv)
        except Exception as e:
            logger.error(f"Failed to list conversations: {e}")
        
        return conversations
    
    def search_conversations(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search across all conversations for matching messages."""
        results = []
        
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                
                # Search in both user messages and assistant responses
                cursor.execute(
                    """
                    SELECT t.id, t.conversation_id, c.name, t.timestamp,
                           t.user_message, t.assistant_response, t.intent
                    FROM turns t
                    JOIN conversations c ON t.conversation_id = c.id
                    WHERE t.user_message LIKE ? OR t.assistant_response LIKE ?
                    ORDER BY t.timestamp DESC
                    LIMIT ?
                    """,
                    (f"%{query}%", f"%{query}%", limit),
                )
                
                for row in cursor.fetchall():
                    results.append({
                        "turn_id": row[0],
                        "conversation_id": row[1],
                        "conversation_name": row[2],
                        "timestamp": row[3],
                        "user_message": row[4][:200],
                        "assistant_response": row[5][:200],
                        "intent": row[6],
                    })
        except Exception as e:
            logger.error(f"Failed to search conversations: {e}")
        
        return results
    
    def rename_conversation(self, conversation_id: str, new_name: str) -> bool:
        """Rename a conversation."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE conversations SET name = ? WHERE id = ?",
                    (new_name, conversation_id),
                )
                conn.commit()
                
                if self._current_conversation and self._current_conversation.id == conversation_id:
                    self._current_conversation.name = new_name
                
                logger.info(f"Renamed conversation {conversation_id} to: {new_name}")
                return True
        except Exception as e:
            logger.error(f"Failed to rename conversation: {e}")
            return False
    
    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation and all its turns."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                
                # Delete turns first (cascade)
                cursor.execute("DELETE FROM turns WHERE conversation_id = ?", (conversation_id,))
                
                # Delete conversation
                cursor.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
                conn.commit()
                
                if self._current_conversation and self._current_conversation.id == conversation_id:
                    self._current_conversation = None
                
                logger.info(f"Deleted conversation: {conversation_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to delete conversation: {e}")
            return False
    
    def export_to_markdown(self, conversation_id: str, output_path: str = None) -> str:
        """Export a conversation to markdown format."""
        conv = self.load_conversation(conversation_id)
        if not conv:
            return ""
        
        lines = [
            f"# {conv.name}",
            f"",
            f"**Created:** {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(conv.created_at))}",
            f"**Turns:** {len(conv.turns)}",
            f"**Tags:** {', '.join(conv.tags) if conv.tags else 'None'}",
            f"",
            "---",
            f"",
        ]
        
        for i, turn in enumerate(conv.turns, 1):
            lines.extend([
                f"### Turn {i} [{turn.intent}]",
                f"",
                f"**User:** {turn.user_message}",
                f"",
                f"**Assistant:** {turn.assistant_response}",
                f"",
            ])
        
        content = "\n".join(lines)
        
        if output_path:
            try:
                p = Path(output_path)
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content, encoding="utf-8")
                logger.info(f"Exported conversation to {output_path}")
            except Exception as e:
                logger.error(f"Failed to export conversation: {e}")
        
        return content
    
    def get_current_conversation(self) -> Optional[Conversation]:
        """Get the current active conversation."""
        return self._current_conversation
    
    def get_stats(self) -> Dict[str, Any]:
        """Get conversation statistics."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                
                cursor.execute("SELECT COUNT(*) FROM conversations")
                total_conversations = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM turns")
                total_turns = cursor.fetchone()[0]
                
                return {
                    "total_conversations": total_conversations,
                    "total_turns": total_turns,
                    "db_path": str(self.db_path),
                    "current_conversation": self._current_conversation.name if self._current_conversation else None,
                }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"total_conversations": 0, "total_turns": 0, "error": str(e)}


# Singleton instance
_manager_instance: Optional[ConversationManager] = None

def get_conversation_manager(db_path: str = ".crackedcode/conversations.db") -> ConversationManager:
    """Get the global ConversationManager instance."""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = ConversationManager(db_path=db_path)
    return _manager_instance
