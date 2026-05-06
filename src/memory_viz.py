"""Memory Visualization v2.9.4 - CLI visualization for agent memories.

Pretty-print agent memory profiles, patterns, and statistics.

Usage:
    python src/main.py memory --agent security
    python src/main.py memory --all
    python src/main.py memory --stats
    python src/main.py memory --agent security --patterns
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.logger_config import get_logger

logger = get_logger("MemoryViz")


# ── Visual Components ──────────────────────────────────────────────────────

SEVERITY_COLORS = {
    "critical": "\033[91m",  # Red
    "high": "\033[93m",      # Yellow
    "medium": "\033[94m",    # Blue
    "low": "\033[92m",       # Green
    "info": "\033[90m",      # Gray
}
RESET = "\033[0m"
BOLD = "\033[1m"
UNDERLINE = "\033[4m"


def _color(text: str, color: str) -> str:
    """Apply ANSI color to text."""
    return f"{color}{text}{RESET}"


def _bar(value: float, max_width: int = 40) -> str:
    """Draw an ASCII bar."""
    filled = int(value * max_width)
    empty = max_width - filled
    return f"[{'█' * filled}{'░' * empty}] {value*100:.0f}%"


def _box(title: str, content: str, width: int = 70) -> str:
    """Draw a box around content."""
    lines = content.strip().split("\n")
    result = [f"┌{'─' * (width - 2)}┐"]
    result.append(f"│ {BOLD}{title}{RESET}{' ' * (width - len(title) - 3)}│")
    result.append(f"├{'─' * (width - 2)}┤")
    for line in lines:
        # Truncate long lines
        if len(line) > width - 4:
            line = line[:width - 7] + "..."
        result.append(f"│ {line}{' ' * (width - len(line) - 3)}│")
    result.append(f"└{'─' * (width - 2)}┘")
    return "\n".join(result)


# ── Visualizers ────────────────────────────────────────────────────────────

class MemoryVisualizer:
    """Visualize agent memory in the terminal."""
    
    def __init__(self, storage_dir: str = ".crackedcode/agent_memory"):
        self.storage_dir = Path(storage_dir)
    
    def show_agent(self, agent: str, show_patterns: bool = False,
                   show_entries: bool = False, limit: int = 10) -> str:
        """Display an agent's memory profile."""
        from src.agent_memory import get_agent_memory_system
        
        memory = get_agent_memory_system(storage_dir=str(self.storage_dir))
        profile = memory.get_profile(agent)
        entries = memory.recall(agent, limit=9999)
        patterns = memory.get_patterns(agent) if show_patterns else []
        
        if not profile and not entries:
            return f"No memories found for agent: {agent}"
        
        parts = []
        
        # Header
        parts.append(f"\n{_color('═' * 70, BOLD)}")
        parts.append(f"{_color('  🤖 AGENT MEMORY PROFILE', BOLD)}")
        parts.append(f"{_color('     ' + agent.upper(), UNDERLINE)}")
        parts.append(f"{_color('═' * 70, BOLD)}\n")
        
        # Stats
        if profile:
            parts.append(_box("Statistics", f"""
Total Interactions: {profile.total_interactions}
Success Rate: {_bar(profile.success_rate)}
Expertise Areas: {', '.join(profile.expertise_areas) or 'None'}
Preferred Tools: {', '.join(profile.preferred_tools) or 'None'}
Common Mistakes: {', '.join(profile.common_mistakes) or 'None'}
            """.strip()))
        
        # Entries by category
        if entries:
            by_category = {}
            for e in entries:
                by_category[e.category] = by_category.get(e.category, 0) + 1
            
            parts.append("\n" + _box("Memory Distribution", "\n".join(
                f"{cat:12} {'▓' * count} {count}"
                for cat, count in sorted(by_category.items())
            )))
        
        # Recent entries
        if show_entries and entries:
            recent = sorted(entries, key=lambda e: e.timestamp, reverse=True)[:limit]
            entry_lines = []
            for e in recent:
                emoji = {"fact": "📌", "preference": "⭐", "decision": "🎯",
                         "error": "❌", "fix": "🔧", "interaction": "💬"}.get(e.category, "📝")
                entry_lines.append(f"{emoji} [{e.category}] {str(e.content)[:50]}...")
                entry_lines.append(f"    📅 {e.timestamp[:19]} | Importance: {e.importance}")
            
            parts.append("\n" + _box(f"Recent Memories (last {limit})", "\n".join(entry_lines)))
        
        # Patterns
        if show_patterns and patterns:
            pattern_lines = []
            for p in sorted(patterns, key=lambda x: x.frequency, reverse=True)[:10]:
                bar = _bar(p.success_rate)
                pattern_lines.append(f"{p.pattern[:40]:40} | Freq: {p.frequency:3} | {bar}")
            
            parts.append("\n" + _box("Experience Patterns (top 10)", "\n".join(pattern_lines)))
        
        # Summary
        if profile and profile.summary:
            parts.append("\n" + _box("Auto-Generated Summary", profile.summary[:500]))
        
        parts.append(f"\n{_color('═' * 70, BOLD)}\n")
        
        return "\n".join(parts)
    
    def show_all(self) -> str:
        """Display all agents with memories."""
        from src.agent_memory import get_agent_memory_system
        
        memory = get_agent_memory_system(storage_dir=str(self.storage_dir))
        agents = memory.list_agents()
        stats = memory.get_stats()
        
        if not agents:
            return "No agent memories found."
        
        parts = []
        parts.append(f"\n{_color('═' * 70, BOLD)}")
        parts.append(f"{_color('  🤖 AGENT MEMORY DASHBOARD', BOLD)}")
        parts.append(f"{_color('═' * 70, BOLD)}\n")
        
        # Overall stats
        parts.append(_box("System Overview", f"""
Total Agents: {stats['total_agents']}
Total Entries: {stats['total_entries']}
Storage: {stats['storage_dir']}
        """.strip()))
        
        # Agent list
        agent_lines = []
        for agent_info in stats.get("agents", []):
            agent_name = agent_info["agent"]
            entries = agent_info["entries"]
            interactions = agent_info["interactions"]
            bar = "█" * min(entries, 30)
            agent_lines.append(f"{agent_name:15} {bar:30} {entries:4} entries | {interactions} interactions")
        
        parts.append("\n" + _box("Agents", "\n".join(agent_lines)))
        
        # Category breakdown
        by_cat = stats.get("by_category", {})
        if by_cat:
            cat_lines = []
            for cat, count in sorted(by_cat.items(), key=lambda x: x[1], reverse=True):
                bar = "▓" * min(count, 30)
                cat_lines.append(f"{cat:12} {bar:30} {count}")
            parts.append("\n" + _box("Categories", "\n".join(cat_lines)))
        
        parts.append(f"\n{_color('═' * 70, BOLD)}\n")
        
        return "\n".join(parts)
    
    def show_stats(self) -> str:
        """Display system statistics."""
        from src.agent_memory import get_agent_memory_system
        
        memory = get_agent_memory_system(storage_dir=str(self.storage_dir))
        stats = memory.get_stats()
        
        parts = []
        parts.append(f"\n{_color('═' * 70, BOLD)}")
        parts.append(f"{_color('  📊 AGENT MEMORY STATISTICS', BOLD)}")
        parts.append(f"{_color('═' * 70, BOLD)}\n")
        
        parts.append(f"Total Agents: {stats['total_agents']}")
        parts.append(f"Total Entries: {stats['total_entries']}")
        parts.append(f"Storage Directory: {stats['storage_dir']}")
        
        if stats.get("by_category"):
            parts.append("\nBy Category:")
            for cat, count in sorted(stats["by_category"].items()):
                parts.append(f"  {cat:12}: {count}")
        
        parts.append(f"\n{_color('═' * 70, BOLD)}\n")
        
        return "\n".join(parts)


def show_agent_memory(agent: Optional[str] = None, all_agents: bool = False,
                      stats_only: bool = False, show_patterns: bool = False,
                      show_entries: bool = False, limit: int = 10) -> str:
    """Main entry point for memory visualization."""
    viz = MemoryVisualizer()
    
    if stats_only:
        return viz.show_stats()
    elif all_agents:
        return viz.show_all()
    elif agent:
        return viz.show_agent(agent, show_patterns=show_patterns,
                              show_entries=show_entries, limit=limit)
    else:
        return "Use --agent <name>, --all, or --stats"


# ── CLI helpers ────────────────────────────────────────────────────────────

def print_memory(agent: Optional[str] = None, **kwargs):
    """Print memory visualization to stdout."""
    output = show_agent_memory(agent=agent, **kwargs)
    print(output)
