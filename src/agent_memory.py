"""Advanced Agent Memory v2.10.0 - Per-agent persistent memory with summarization.

Each agent role (architect, security, coder, etc.) maintains its own memory
namespace with facts, preferences, decisions, errors, and fixes. Automatic
summarization condenses experience into actionable context.

Usage:
    from src.agent_memory import get_agent_memory_system
    memory = get_agent_memory_system()
    
    # Store agent experience
    memory.remember("security", "found_vulnerability", {
        "type": "SQL injection",
        "file": "auth.py",
        "fix": "Use parameterized queries",
    })
    
    # Retrieve relevant context
    context = memory.get_context("security", "authentication code review")
    
    # Auto-summarize agent experience
    summary = memory.summarize("security")
"""

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from src.logger_config import get_logger

logger = get_logger("AgentMemory")


# ── Data Models ────────────────────────────────────────────────────────────

@dataclass
class MemoryEntry:
    """A single memory entry for an agent."""
    id: str
    agent: str
    category: str  # fact, preference, decision, error, fix, interaction
    content: Dict[str, Any]
    importance: float = 1.0  # 0-1
    confidence: float = 1.0  # 0-1
    timestamp: str = ""
    access_count: int = 0
    last_accessed: str = ""
    tags: List[str] = field(default_factory=list)
    related_entries: List[str] = field(default_factory=list)


@dataclass
class AgentProfile:
    """Persistent profile for an agent."""
    agent: str
    created_at: str = ""
    total_interactions: int = 0
    success_rate: float = 0.0
    expertise_areas: List[str] = field(default_factory=list)
    preferred_tools: List[str] = field(default_factory=list)
    common_mistakes: List[str] = field(default_factory=list)
    summary: str = ""
    last_summarized: str = ""


@dataclass
class ExperiencePattern:
    """A learned pattern from agent experience."""
    pattern: str
    category: str
    frequency: int = 1
    success_rate: float = 0.0
    first_seen: str = ""
    last_seen: str = ""
    examples: List[str] = field(default_factory=list)


# ── Agent Memory System ────────────────────────────────────────────────────

class AgentMemorySystem:
    """Per-agent persistent memory with automatic summarization."""

    CATEGORIES = ["fact", "preference", "decision", "error", "fix", "interaction"]

    def __init__(self, storage_dir: str = ".crackedcode/agent_memory"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.memories: Dict[str, List[MemoryEntry]] = {}  # agent -> entries
        self.profiles: Dict[str, AgentProfile] = {}
        self.patterns: Dict[str, List[ExperiencePattern]] = {}
        self._load_all()

    def _agent_dir(self, agent: str) -> Path:
        """Get storage directory for an agent."""
        return self.storage_dir / agent

    def _load_all(self):
        """Load all agent memories from disk."""
        if not self.storage_dir.exists():
            return

        for agent_dir in self.storage_dir.iterdir():
            if not agent_dir.is_dir():
                continue
            agent = agent_dir.name
            self._load_agent(agent)

    def _load_agent(self, agent: str):
        """Load a single agent's memories."""
        agent_dir = self._agent_dir(agent)

        # Load memories
        memories_file = agent_dir / "memories.json"
        if memories_file.exists():
            try:
                with open(memories_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.memories[agent] = [
                    MemoryEntry(
                        id=e["id"],
                        agent=e["agent"],
                        category=e["category"],
                        content=e["content"],
                        importance=e.get("importance", 1.0),
                        confidence=e.get("confidence", 1.0),
                        timestamp=e.get("timestamp", ""),
                        access_count=e.get("access_count", 0),
                        last_accessed=e.get("last_accessed", ""),
                        tags=e.get("tags", []),
                        related_entries=e.get("related_entries", []),
                    )
                    for e in data.get("entries", [])
                ]
            except Exception as e:
                logger.warning(f"Failed to load memories for {agent}: {e}")
                self.memories[agent] = []
        else:
            self.memories[agent] = []

        # Load profile
        profile_file = agent_dir / "profile.json"
        if profile_file.exists():
            try:
                with open(profile_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.profiles[agent] = AgentProfile(
                    agent=data["agent"],
                    created_at=data.get("created_at", ""),
                    total_interactions=data.get("total_interactions", 0),
                    success_rate=data.get("success_rate", 0.0),
                    expertise_areas=data.get("expertise_areas", []),
                    preferred_tools=data.get("preferred_tools", []),
                    common_mistakes=data.get("common_mistakes", []),
                    summary=data.get("summary", ""),
                    last_summarized=data.get("last_summarized", ""),
                )
            except Exception as e:
                logger.warning(f"Failed to load profile for {agent}: {e}")
                self.profiles[agent] = AgentProfile(agent=agent)
        else:
            self.profiles[agent] = AgentProfile(agent=agent)

        # Load patterns
        patterns_file = agent_dir / "patterns.json"
        if patterns_file.exists():
            try:
                with open(patterns_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.patterns[agent] = [
                    ExperiencePattern(
                        pattern=p["pattern"],
                        category=p["category"],
                        frequency=p.get("frequency", 1),
                        success_rate=p.get("success_rate", 0.0),
                        first_seen=p.get("first_seen", ""),
                        last_seen=p.get("last_seen", ""),
                        examples=p.get("examples", []),
                    )
                    for p in data.get("patterns", [])
                ]
            except Exception as e:
                logger.warning(f"Failed to load patterns for {agent}: {e}")
                self.patterns[agent] = []
        else:
            self.patterns[agent] = []

    def _save_agent(self, agent: str):
        """Save a single agent's memories to disk."""
        agent_dir = self._agent_dir(agent)
        agent_dir.mkdir(parents=True, exist_ok=True)

        # Save memories
        memories_file = agent_dir / "memories.json"
        entries = self.memories.get(agent, [])
        with open(memories_file, "w", encoding="utf-8") as f:
            json.dump({
                "entries": [
                    {
                        "id": e.id,
                        "agent": e.agent,
                        "category": e.category,
                        "content": e.content,
                        "importance": e.importance,
                        "confidence": e.confidence,
                        "timestamp": e.timestamp,
                        "access_count": e.access_count,
                        "last_accessed": e.last_accessed,
                        "tags": e.tags,
                        "related_entries": e.related_entries,
                    }
                    for e in entries
                ]
            }, f, indent=2)

        # Save profile
        profile = self.profiles.get(agent, AgentProfile(agent=agent))
        profile_file = agent_dir / "profile.json"
        with open(profile_file, "w", encoding="utf-8") as f:
            json.dump({
                "agent": profile.agent,
                "created_at": profile.created_at,
                "total_interactions": profile.total_interactions,
                "success_rate": profile.success_rate,
                "expertise_areas": profile.expertise_areas,
                "preferred_tools": profile.preferred_tools,
                "common_mistakes": profile.common_mistakes,
                "summary": profile.summary,
                "last_summarized": profile.last_summarized,
            }, f, indent=2)

        # Save patterns
        patterns = self.patterns.get(agent, [])
        patterns_file = agent_dir / "patterns.json"
        with open(patterns_file, "w", encoding="utf-8") as f:
            json.dump({
                "patterns": [
                    {
                        "pattern": p.pattern,
                        "category": p.category,
                        "frequency": p.frequency,
                        "success_rate": p.success_rate,
                        "first_seen": p.first_seen,
                        "last_seen": p.last_seen,
                        "examples": p.examples,
                    }
                    for p in patterns
                ]
            }, f, indent=2)

    def remember(
        self,
        agent: str,
        category: str,
        content: Dict[str, Any],
        importance: float = 1.0,
        confidence: float = 1.0,
        tags: Optional[List[str]] = None,
    ) -> MemoryEntry:
        """Store a memory for an agent."""
        if category not in self.CATEGORIES:
            category = "fact"

        entry_id = hashlib.md5(
            f"{agent}:{category}:{json.dumps(content, sort_keys=True)}:{time.time()}".encode()
        ).hexdigest()[:12]

        entry = MemoryEntry(
            id=entry_id,
            agent=agent,
            category=category,
            content=content,
            importance=importance,
            confidence=confidence,
            timestamp=datetime.utcnow().isoformat(),
            last_accessed=datetime.utcnow().isoformat(),
            tags=tags or [],
        )

        if agent not in self.memories:
            self.memories[agent] = []
            self.profiles[agent] = AgentProfile(agent=agent)
            self.patterns[agent] = []

        self.memories[agent].append(entry)

        # Update profile
        profile = self.profiles[agent]
        profile.total_interactions += 1

        # Extract expertise from facts
        if category == "fact" and "expertise" in content:
            expertise = content["expertise"]
            if isinstance(expertise, str) and expertise not in profile.expertise_areas:
                profile.expertise_areas.append(expertise)
            elif isinstance(expertise, list):
                for e in expertise:
                    if e not in profile.expertise_areas:
                        profile.expertise_areas.append(e)

        # Track tools
        if category == "preference" and "tool" in content:
            tool = content["tool"]
            if tool not in profile.preferred_tools:
                profile.preferred_tools.append(tool)

        # Track mistakes
        if category == "error" and "type" in content:
            mistake = content["type"]
            if mistake not in profile.common_mistakes:
                profile.common_mistakes.append(mistake)

        # Update patterns
        self._update_patterns(agent, entry)

        self._save_agent(agent)
        logger.info(f"Agent {agent} remembered: {category} ({entry_id})")
        return entry

    def _update_patterns(self, agent: str, entry: MemoryEntry):
        """Update experience patterns from a memory entry."""
        patterns = self.patterns.get(agent, [])

        # Extract pattern key from content
        content_str = json.dumps(entry.content, sort_keys=True)
        pattern_key = self._extract_pattern_key(entry.category, entry.content)

        existing = next((p for p in patterns if p.pattern == pattern_key), None)
        if existing:
            existing.frequency += 1
            existing.last_seen = entry.timestamp
            if len(existing.examples) < 5:
                existing.examples.append(content_str[:200])
        else:
            patterns.append(ExperiencePattern(
                pattern=pattern_key,
                category=entry.category,
                frequency=1,
                first_seen=entry.timestamp,
                last_seen=entry.timestamp,
                examples=[content_str[:200]],
            ))

        self.patterns[agent] = patterns

    def _extract_pattern_key(self, category: str, content: Dict[str, Any]) -> str:
        """Extract a pattern key from memory content."""
        if "type" in content:
            return f"{category}:{content['type']}"
        elif "topic" in content:
            return f"{category}:{content['topic']}"
        elif "file" in content:
            return f"{category}:{Path(content['file']).suffix or 'unknown'}"
        else:
            # Hash the content for a unique key
            return f"{category}:{hashlib.md5(json.dumps(content, sort_keys=True).encode()).hexdigest()[:8]}"

    def recall(
        self,
        agent: str,
        query: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 10,
    ) -> List[MemoryEntry]:
        """Retrieve memories for an agent, optionally filtered."""
        entries = self.memories.get(agent, [])

        if category:
            entries = [e for e in entries if e.category == category]

        if query:
            query_lower = query.lower()
            entries = [
                e for e in entries
                if query_lower in json.dumps(e.content).lower()
                or any(query_lower in t.lower() for t in e.tags)
            ]

        # Sort by importance and recency
        now = time.time()
        def score(e: MemoryEntry) -> float:
            recency = 1.0
            if e.timestamp:
                try:
                    age = now - datetime.fromisoformat(e.timestamp).timestamp()
                    recency = max(0.1, 1.0 - (age / (86400 * 30)))  # Decay over 30 days
                except Exception:
                    pass
            return e.importance * e.confidence * recency * (1 + e.access_count * 0.1)

        entries.sort(key=score, reverse=True)

        # Update access counts
        for e in entries[:limit]:
            e.access_count += 1
            e.last_accessed = datetime.utcnow().isoformat()

        return entries[:limit]

    def get_context(self, agent: str, task: str, max_entries: int = 5) -> str:
        """Get formatted memory context for an agent on a task."""
        entries = self.recall(agent, query=task, limit=max_entries)

        if not entries:
            return ""

        context_parts = [f"## {agent.upper()} Agent Memory"]

        for entry in entries:
            content_str = self._format_entry(entry)
            context_parts.append(f"\n[{entry.category.upper()}] {content_str}")

        # Add profile summary
        profile = self.profiles.get(agent)
        if profile and profile.summary:
            context_parts.insert(1, f"\n### Summary\n{profile.summary}")

        return "\n".join(context_parts)

    def _format_entry(self, entry: MemoryEntry) -> str:
        """Format a memory entry for context injection."""
        parts = []
        for key, val in entry.content.items():
            if isinstance(val, str) and len(val) < 200:
                parts.append(f"{key}: {val}")
            elif isinstance(val, str):
                parts.append(f"{key}: {val[:200]}...")
            else:
                parts.append(f"{key}: {str(val)[:200]}")
        return " | ".join(parts)

    def summarize(self, agent: str, engine=None) -> str:
        """Generate a summary of an agent's experience."""
        entries = self.memories.get(agent, [])
        profile = self.profiles.get(agent, AgentProfile(agent=agent))

        if not entries:
            return "No memories yet."

        # Build summary from patterns and high-importance memories
        patterns = self.patterns.get(agent, [])
        top_patterns = sorted(patterns, key=lambda p: p.frequency, reverse=True)[:5]

        facts = [e for e in entries if e.category == "fact"]
        top_facts = sorted(facts, key=lambda e: e.importance, reverse=True)[:5]

        errors = [e for e in entries if e.category == "error"]
        fixes = [e for e in entries if e.category == "fix"]

        summary_parts = [f"# {agent.upper()} Agent Experience Summary"]
        summary_parts.append(f"\nTotal interactions: {profile.total_interactions}")
        summary_parts.append(f"Expertise areas: {', '.join(profile.expertise_areas) or 'None recorded'}")

        if top_patterns:
            summary_parts.append("\n## Common Patterns")
            for p in top_patterns:
                summary_parts.append(f"- {p.pattern} (seen {p.frequency} times)")

        if top_facts:
            summary_parts.append("\n## Key Facts")
            for f in top_facts:
                summary_parts.append(f"- {self._format_entry(f)}")

        if errors:
            summary_parts.append(f"\n## Known Issues ({len(errors)} total)")
            for e in errors[:3]:
                summary_parts.append(f"- {self._format_entry(e)}")

        if fixes:
            summary_parts.append(f"\n## Applied Fixes ({len(fixes)} total)")
            for f in fixes[:3]:
                summary_parts.append(f"- {self._format_entry(f)}")

        if profile.preferred_tools:
            summary_parts.append(f"\n## Preferred Tools: {', '.join(profile.preferred_tools)}")

        summary = "\n".join(summary_parts)

        # LLM-enhanced summarization if engine available
        if engine and hasattr(engine, "ollama"):
            try:
                llm_prompt = f"""Analyze this agent's experience data and produce a concise, actionable summary.
Focus on: recurring patterns, critical lessons, and recommendations for future tasks.

{summary}

Provide a 3-4 sentence executive summary followed by 3 key recommendations."""

                llm_response = engine.ollama.chat(llm_prompt, system="You are an expert analyst summarizing agent experience.", use_cache=False)
                if llm_response.success:
                    summary = f"# {agent.upper()} Agent Experience Summary (LLM-Enhanced)\n\n{llm_response.text}\n\n---\n\n## Raw Data\n{summary}"
                    logger.info(f"LLM-enhanced summary generated for agent {agent}")
            except Exception as e:
                logger.warning(f"LLM summarization failed for {agent}: {e}")

        # Update profile
        profile.summary = summary
        profile.last_summarized = datetime.utcnow().isoformat()
        self._save_agent(agent)

        return summary

    def forget(self, agent: str, entry_id: str) -> bool:
        """Remove a specific memory entry."""
        entries = self.memories.get(agent, [])
        original_len = len(entries)
        self.memories[agent] = [e for e in entries if e.id != entry_id]

        if len(self.memories[agent]) < original_len:
            self._save_agent(agent)
            logger.info(f"Agent {agent} forgot entry: {entry_id}")
            return True
        return False

    def clear_agent(self, agent: str) -> bool:
        """Clear all memories for an agent."""
        if agent in self.memories:
            self.memories[agent] = []
            self.profiles[agent] = AgentProfile(agent=agent)
            self.patterns[agent] = []
            self._save_agent(agent)
            logger.info(f"Cleared all memories for agent: {agent}")
            return True
        return False

    def get_profile(self, agent: str) -> Optional[AgentProfile]:
        """Get an agent's profile."""
        return self.profiles.get(agent)

    def get_patterns(self, agent: str) -> List[ExperiencePattern]:
        """Get an agent's learned patterns."""
        return self.patterns.get(agent, [])

    def list_agents(self) -> List[str]:
        """List all agents with memories."""
        return list(self.memories.keys())

    def get_stats(self) -> Dict[str, Any]:
        """Get system-wide memory statistics."""
        total_entries = sum(len(entries) for entries in self.memories.values())
        total_agents = len(self.memories)

        by_category = {}
        for entries in self.memories.values():
            for entry in entries:
                by_category[entry.category] = by_category.get(entry.category, 0) + 1

        return {
            "total_agents": total_agents,
            "total_entries": total_entries,
            "storage_dir": str(self.storage_dir),
            "by_category": by_category,
            "agents": [
                {
                    "agent": agent,
                    "entries": len(entries),
                    "interactions": self.profiles.get(agent, AgentProfile(agent=agent)).total_interactions,
                }
                for agent, entries in self.memories.items()
            ],
        }

    def merge_context(self, agent: str, context: str) -> str:
        """Merge agent memory context with a task context string."""
        memory_context = self.get_context(agent, context)
        if memory_context:
            return f"{memory_context}\n\n---\n\n{context}"
        return context


# ── Integration helpers ────────────────────────────────────────────────────

def get_agent_memory_system(storage_dir: str = ".crackedcode/agent_memory") -> AgentMemorySystem:
    """Get the global agent memory system."""
    return AgentMemorySystem(storage_dir=storage_dir)


def inject_agent_memory(agent: str, prompt: str, storage_dir: str = ".crackedcode/agent_memory") -> str:
    """Inject agent memory context into a prompt."""
    memory = get_agent_memory_system(storage_dir=storage_dir)
    return memory.merge_context(agent, prompt)

