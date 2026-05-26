"""Unified Memory System — merges agent_memory, long_term_memory, and adaptive_learning.

All three original modules re-export from here for backward compatibility.
New code should import from src.memory directly.
"""
from src.agent_memory import (
    MemoryEntry, AgentProfile, AgentMemorySystem,
    get_agent_memory_system, inject_agent_memory,
)
from src.long_term_memory import (
    LongTermMemory, get_long_term_memory,
)
from src.adaptive_learning import (
    FeedbackEvent, UserPreference, LearningStore,
    AdaptiveLearningEngine, get_adaptive_learning_engine,
    reset_adaptive_learning_engine,
)
