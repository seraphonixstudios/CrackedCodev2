"""Custom Agent Definition - Load user-defined agents from YAML/JSON configs.

Features:
- Define new agents without touching Python code
- YAML/JSON configuration files in agents/ directory
- Auto-validation of agent definitions
- Runtime agent creation and registration
- Custom intents, capabilities, tools, and system prompts

Example:
    # agents/pen_tester.yaml
    name: pen_tester
    role: security
    capabilities: [scan, fuzz, audit, exploit]
    system_prompt: "You are a security penetration tester..."
    tools: [audit_secrets, analyze_vulnerabilities, run_shell]
    model: qwen3:8b-gpu
    intents: [pentest, exploit, fuzz]
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.logger_config import get_logger

logger = get_logger("CustomAgents")


try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


@dataclass
class CustomAgentDef:
    """Definition of a custom agent."""
    name: str
    role: str
    capabilities: List[str] = field(default_factory=list)
    system_prompt: str = ""
    tools: List[str] = field(default_factory=list)
    model: str = ""
    intents: List[str] = field(default_factory=list)
    description: str = ""
    enabled: bool = True
    priority: int = 5  # 1-10, higher = more important in tiebreaker
    
    def validate(self) -> List[str]:
        """Validate the agent definition. Returns list of errors."""
        errors = []
        
        if not self.name or not self.name.strip():
            errors.append("Agent name is required")
        
        if not self.role or not self.role.strip():
            errors.append("Agent role is required")
        
        if not self.capabilities:
            errors.append("At least one capability is required")
        
        if len(self.name) > 50:
            errors.append("Agent name too long (max 50 chars)")
        
        if not self.system_prompt:
            errors.append("System prompt is recommended")
        
        return errors
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "role": self.role,
            "capabilities": self.capabilities,
            "system_prompt": self.system_prompt,
            "tools": self.tools,
            "model": self.model,
            "intents": self.intents,
            "description": self.description,
            "enabled": self.enabled,
            "priority": self.priority,
        }


class CustomAgentRegistry:
    """Registry for loading and managing custom agent definitions."""
    
    def __init__(self, config_dir: str = "agents"):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)
        self.agents: Dict[str, CustomAgentDef] = {}
        self._load_all()
    
    def _load_all(self):
        """Load all agent definitions from the config directory."""
        if not self.config_dir.exists():
            return
        
        for file_path in self.config_dir.iterdir():
            if file_path.suffix.lower() not in (".yaml", ".yml", ".json"):
                continue
            
            try:
                agent = self._load_file(file_path)
                if agent:
                    errors = agent.validate()
                    if errors:
                        logger.warning(f"Agent '{agent.name}' validation errors: {errors}")
                        continue
                    
                    self.agents[agent.name] = agent
                    logger.info(f"Loaded custom agent: {agent.name} ({agent.role})")
            except Exception as e:
                logger.error(f"Failed to load agent config {file_path}: {e}")
    
    def _load_file(self, file_path: Path) -> Optional[CustomAgentDef]:
        """Load a single agent definition file."""
        content = file_path.read_text(encoding="utf-8")
        
        if file_path.suffix.lower() in (".yaml", ".yml"):
            if not YAML_AVAILABLE:
                logger.warning("PyYAML not installed, cannot load YAML configs")
                return None
            data = yaml.safe_load(content)
        else:
            data = json.loads(content)
        
        if not data or not isinstance(data, dict):
            return None
        
        return CustomAgentDef(
            name=data.get("name", file_path.stem),
            role=data.get("role", "custom"),
            capabilities=data.get("capabilities", []),
            system_prompt=data.get("system_prompt", ""),
            tools=data.get("tools", []),
            model=data.get("model", ""),
            intents=data.get("intents", []),
            description=data.get("description", ""),
            enabled=data.get("enabled", True),
            priority=data.get("priority", 5),
        )
    
    def get(self, name: str) -> Optional[CustomAgentDef]:
        """Get a custom agent definition by name."""
        return self.agents.get(name)
    
    def list_agents(self) -> List[CustomAgentDef]:
        """List all loaded custom agents."""
        return list(self.agents.values())
    
    def list_enabled(self) -> List[CustomAgentDef]:
        """List only enabled custom agents."""
        return [a for a in self.agents.values() if a.enabled]
    
    def get_intent_map(self) -> Dict[str, str]:
        """Get mapping of intents to custom agent names."""
        mapping = {}
        for agent in self.list_enabled():
            for intent in agent.intents:
                mapping[intent.lower()] = agent.name
        return mapping
    
    def reload(self):
        """Reload all agent definitions from disk."""
        self.agents.clear()
        self._load_all()
        logger.info(f"Reloaded {len(self.agents)} custom agents")
    
    def save_example(self, name: str = "example_agent"):
        """Save an example agent definition file."""
        example = {
            "name": name,
            "role": "custom",
            "description": "An example custom agent",
            "capabilities": ["analyze", "review", "suggest"],
            "system_prompt": "You are a specialized agent focused on code quality and best practices.",
            "tools": ["read_file", "grep_files", "run_tests"],
            "model": "qwen3:8b-gpu",
            "intents": ["quality", "refactor", "optimize"],
            "enabled": True,
            "priority": 5,
        }
        
        path = self.config_dir / f"{name}.json"
        path.write_text(json.dumps(example, indent=2))
        logger.info(f"Saved example agent to {path}")
        return path


def get_custom_agent_registry(config_dir: str = "agents") -> CustomAgentRegistry:
    """Get the global CustomAgentRegistry instance."""
    if not hasattr(get_custom_agent_registry, "_instance"):
        get_custom_agent_registry._instance = CustomAgentRegistry(config_dir)
    return get_custom_agent_registry._instance
