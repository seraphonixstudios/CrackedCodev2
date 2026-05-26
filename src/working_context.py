"""Working Context - Persistent current-session context for prompt injection.

Tracks what the user is currently working on, including recent exchanges,
active files, and the current task description. Persists across engine
restarts and auto-injects into every prompt alongside codebase RAG
context and long-term memory.

Storage:
    .crackedcode/working_context.json - JSON with recent exchanges + metadata

Integration:
    - Engine auto-loads on init, auto-saves on process()
    - Injected as <working-context> block into prompts
    - GUI status display shows current task and exchange count
"""

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any

from src.logger_config import get_logger

logger = get_logger("WorkingContext")


@dataclass
class Exchange:
    """A single user-assistant exchange."""
    prompt: str
    response: str
    intent: str = "chat"
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Exchange":
        return cls(**data)


@dataclass
class WorkingContextData:
    """Persistent working context state."""
    current_task: str = ""
    active_files: List[str] = field(default_factory=list)
    session_start: float = field(default_factory=time.time)
    last_interaction: float = field(default_factory=time.time)
    exchange_count: int = 0
    recent_exchanges: List[Dict] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkingContextData":
        return cls(**data)


class WorkingContext:
    """Persistent working context for the current session.

    Maintains a rolling window of recent exchanges, the current task,
    and active files. Survives engine restarts via JSON persistence.
    """

    MAX_EXCHANGES = 5

    def __init__(self, storage_path: str = ".crackedcode/working_context.json"):
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._data: WorkingContextData = WorkingContextData()
        self._load()

    def _load(self):
        """Load working context from disk, or start fresh."""
        if self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text(encoding="utf-8"))
                self._data = WorkingContextData.from_dict(data)
                logger.info(f"Loaded working context: {self._data.exchange_count} exchanges, "
                           f"{len(self._data.active_files)} files")
            except Exception as e:
                logger.warning(f"Failed to load working context, starting fresh: {e}")
                self._data = WorkingContextData()

    def _save(self):
        """Persist working context to disk."""
        try:
            self.storage_path.write_text(
                json.dumps(self._data.to_dict(), indent=2, default=str),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"Failed to save working context: {e}")

    def record_exchange(self, prompt: str, response: str, intent: str = "chat"):
        """Record a user-assistant exchange and update the rolling window."""
        exchange = Exchange(prompt=prompt, response=response, intent=intent)
        self._data.exchange_count += 1
        self._data.last_interaction = time.time()

        recent = self._data.recent_exchanges
        recent.append(exchange.to_dict())
        if len(recent) > self.MAX_EXCHANGES:
            self._data.recent_exchanges = recent[-self.MAX_EXCHANGES:]

        self._save()

    def set_task(self, task: str):
        """Set the current working task description."""
        self._data.current_task = task
        self._save()

    def add_active_file(self, file_path: str):
        """Add a file to the active files list (no duplicates)."""
        path = file_path.replace("\\", "/")
        if path not in self._data.active_files:
            self._data.active_files.append(path)
            self._data.active_files = self._data.active_files[-10:]
            self._save()

    def remove_active_file(self, file_path: str):
        """Remove a file from the active files list."""
        path = file_path.replace("\\", "/")
        if path in self._data.active_files:
            self._data.active_files.remove(path)
            self._save()

    def set_active_files(self, files: List[str]):
        """Replace the active files list."""
        self._data.active_files = [f.replace("\\", "/") for f in files][:10]
        self._save()

    def get_context_for_prompt(self, max_exchanges: int = 3) -> str:
        """Format working context as a prompt block for LLM injection.

        Returns an empty string if there is nothing meaningful to inject.
        """
        parts = []

        if self._data.current_task:
            parts.append(f"Current task: {self._data.current_task}")

        if self._data.active_files:
            files_str = ", ".join(self._data.active_files[:5])
            parts.append(f"Active files: {files_str}")

        if self._data.recent_exchanges:
            recent = self._data.recent_exchanges[-max_exchanges:]
            exchanges = []
            for ex in recent:
                exchanges.append(f"User: {ex['prompt'][:300]}")
                exchanges.append(f"Assistant: {ex['response'][:500]}")
            if exchanges:
                parts.append("Recent conversation:\n" + "\n".join(exchanges))

        if not parts:
            return ""

        result = "<working-context>\n" + "\n".join(parts) + "\n</working-context>"
        return result

    def get_status(self) -> Dict[str, Any]:
        """Get current working context status."""
        return {
            "current_task": self._data.current_task,
            "active_files": self._data.active_files,
            "exchange_count": self._data.exchange_count,
            "session_start": self._data.session_start,
            "last_interaction": self._data.last_interaction,
            "stored_exchanges": len(self._data.recent_exchanges),
        }

    def reset(self):
        """Clear the working context (start fresh)."""
        self._data = WorkingContextData()
        self._save()
        logger.info("Working context reset")


# Singleton
_instance: Optional[WorkingContext] = None


def get_working_context(storage_path: str = ".crackedcode/working_context.json") -> WorkingContext:
    """Get the global WorkingContext singleton."""
    global _instance
    if _instance is None:
        _instance = WorkingContext(storage_path=storage_path)
    return _instance


def reset_working_context():
    """Reset the global WorkingContext singleton (for testing)."""
    global _instance
    _instance = None
