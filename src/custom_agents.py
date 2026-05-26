"""Custom Agent Definition - Load user-defined agents from file-based definitions.

Mirrors opencode's approach: agents are defined as markdown files in .opencode/agents/.
Supports both markdown (frontmatter) and YAML/JSON formats.

Example (.opencode/agents/custom.md):
    ---
    name: custom
    mode: subagent
    description: Does custom things
    model: qwen3:8b-gpu
    permission:
      edit: deny
      bash: deny
    ---
    You are a custom agent. Do the thing.
"""

import json
import re
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
    name: str
    mode: str = "subagent"
    role: str = ""
    capabilities: List[str] = field(default_factory=list)
    system_prompt: str = ""
    tools: List[str] = field(default_factory=list)
    model: str = ""
    intents: List[str] = field(default_factory=list)
    description: str = ""
    enabled: bool = True
    permission: Dict[str, str] = field(default_factory=dict)

    def validate(self) -> List[str]:
        errors = []
        if not self.name:
            errors.append("Agent name is required")
        if not self.system_prompt:
            errors.append("System prompt is recommended")
        return errors

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "mode": self.mode,
            "description": self.description,
            "system_prompt": self.system_prompt,
            "permission": self.permission,
        }


def _parse_markdown_frontmatter(content: str) -> tuple:
    """Parse markdown frontmatter (--- ... ---) and body."""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", content, re.DOTALL)
    if m:
        frontmatter = yaml.safe_load(m.group(1)) if YAML_AVAILABLE else {}
        body = m.group(2).strip()
        return frontmatter or {}, body
    return {}, content.strip()


class CustomAgentRegistry:
    """Registry for loading custom agent definitions from file-based sources.
    
    Scans these locations in order (later overrides earlier):
      - .opencode/agents/*.md, *.yaml, *.yml, *.json
      - ~/.config/opencode/agents/*.md, *.yaml, *.yml, *.json
    """
    
    def __init__(self, config_dirs: Optional[List[str]] = None, config_dir: Optional[str] = None):
        if config_dir:
            self.config_dirs = [config_dir]
        elif config_dirs:
            self.config_dirs = config_dirs
        else:
            self.config_dirs = [".opencode/agents", "agents"]
        self.agents: Dict[str, CustomAgentDef] = {}
        self._load_all()
    
    def _load_all(self):
        """Load all agent definitions from config directories."""
        for config_dir in self.config_dirs:
            d = Path(config_dir)
            if not d.exists():
                continue
            for file_path in sorted(d.iterdir()):
                if file_path.suffix.lower() not in (".md", ".yaml", ".yml", ".json"):
                    continue
                try:
                    agent = self._load_file(file_path)
                    if agent:
                        self.agents[agent.name] = agent
                        logger.info(f"Loaded agent: {agent.name} ({agent.mode}) from {file_path}")
                except Exception as e:
                    logger.error(f"Failed to load agent config {file_path}: {e}")
    
    def _load_file(self, file_path: Path) -> Optional[CustomAgentDef]:
        content = file_path.read_text(encoding="utf-8")
        name = file_path.stem
        description = ""
        system_prompt = ""
        mode = "subagent"
        model = ""
        permission = {}
        intents = []

        if file_path.suffix.lower() == ".md":
            frontmatter, body = _parse_markdown_frontmatter(content)
            if frontmatter:
                name = frontmatter.get("name", name)
                description = frontmatter.get("description", "")
                mode = frontmatter.get("mode", "subagent")
                model = frontmatter.get("model", "")
                permission = frontmatter.get("permission", {})
                system_prompt = body
            else:
                system_prompt = body
        elif file_path.suffix.lower() in (".yaml", ".yml"):
            if not YAML_AVAILABLE:
                return None
            data = yaml.safe_load(content)
            if data:
                name = data.get("name", name)
                description = data.get("description", "")
                mode = data.get("mode", "subagent")
                model = data.get("model", "")
                permission = data.get("permission", {})
                intents = data.get("intents", [])
                system_prompt = data.get("system_prompt", "")
        else:
            data = json.loads(content)
            if data:
                name = data.get("name", name)
                description = data.get("description", "")
                mode = data.get("mode", "subagent")
                model = data.get("model", "")
                permission = data.get("permission", {})
                intents = data.get("intents", [])
                system_prompt = data.get("system_prompt", "")
        return CustomAgentDef(
            name=name,
            mode=mode,
            description=description,
            system_prompt=system_prompt,
            model=model,
            permission=permission,
            intents=intents,
        )
    
    def get(self, name: str) -> Optional[CustomAgentDef]:
        return self.agents.get(name)
    
    def list_agents(self) -> List[CustomAgentDef]:
        return list(self.agents.values())
    
    def list_enabled(self) -> List[CustomAgentDef]:
        return [a for a in self.agents.values() if a.enabled]
    
    def get_intent_map(self) -> Dict[str, str]:
        mapping = {}
        for agent in self.list_enabled():
            for intent in agent.intents:
                mapping[intent.lower()] = agent.name
        return mapping
    
    def reload(self):
        self.agents.clear()
        self._load_all()
        logger.info(f"Reloaded {len(self.agents)} custom agents")
    
    def save_example(self, name: str = "example_agent"):
        import json
        example = {
            "name": name,
            "mode": "subagent",
            "description": "An example custom agent",
            "system_prompt": "You are a specialized agent focused on code quality and best practices.",
            "intents": ["quality", "refactor", "optimize"],
            "enabled": True,
        }
        path = Path(self.config_dirs[0]) / f"{name}.json"
        path.write_text(json.dumps(example, indent=2), encoding="utf-8")
        logger.info(f"Saved example agent to {path}")
        return path


def get_custom_agent_registry() -> CustomAgentRegistry:
    if not hasattr(get_custom_agent_registry, "_instance"):
        get_custom_agent_registry._instance = CustomAgentRegistry()
    return get_custom_agent_registry._instance

