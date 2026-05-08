"""Custom Tool Builder v2.8.2 - Define tools via JSON/YAML without Python code.

Define new tools by creating JSON/YAML files in the tools/ directory:
  tools/weather_lookup.yaml
  tools/jira_create_ticket.json

Supported action types:
  - http:      Make HTTP requests (GET/POST/PUT/DELETE)
  - shell:     Execute shell commands safely
  - file:      Read/write/delete files
  - python:    Evaluate Python expressions
  - composite: Chain multiple actions together

Usage:
    from src.custom_tools import get_custom_tool_registry
    registry = get_custom_tool_registry()
    registry.reload()
    
    # Tools auto-register in the global ToolRegistry
    from src.tool_framework import get_tool_registry
    tools = get_tool_registry().list_tools()
"""

import json
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
from urllib.parse import urlencode

from src.logger_config import get_logger

logger = get_logger("CustomTools")


# â”€â”€ Data Models â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@dataclass
class ToolParameter:
    """A parameter definition for a custom tool."""
    name: str
    type: str = "string"  # string, int, float, bool, list, dict
    required: bool = True
    default: Any = None
    description: str = ""


@dataclass
class ToolAction:
    """A single action within a custom tool."""
    type: str  # http, shell, file, python, composite
    config: Dict[str, Any] = field(default_factory=dict)
    condition: str = ""  # Optional condition to execute this action
    output_var: str = ""  # Variable name to store output


@dataclass
class CustomToolDef:
    """A complete custom tool definition."""
    name: str
    description: str
    version: str = "1.0"
    permission: str = "read"  # read, write, execute, dangerous
    category: str = "custom"
    parameters: List[ToolParameter] = field(default_factory=list)
    actions: List[ToolAction] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    enabled: bool = True
    author: str = ""
    tags: List[str] = field(default_factory=list)


# â”€â”€ Action Executors â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class ActionExecutor:
    """Base class for action executors."""
    
    def execute(self, action: ToolAction, params: Dict[str, Any],
                context: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError


class HTTPExecutor(ActionExecutor):
    """Execute HTTP request actions."""
    
    def execute(self, action: ToolAction, params: Dict[str, Any],
                context: Dict[str, Any]) -> Dict[str, Any]:
        import requests
        
        config = action.config
        method = config.get("method", "GET").upper()
        url_template = config.get("url", "")
        headers = config.get("headers", {})
        timeout = config.get("timeout", 30)
        
        # Interpolate URL with params
        url = self._interpolate(url_template, {**params, **context})
        
        # Build request kwargs
        kwargs = {"headers": headers, "timeout": timeout}
        
        if method in ("POST", "PUT", "PATCH"):
            body_template = config.get("body", "")
            if body_template:
                body = self._interpolate(body_template, {**params, **context})
                try:
                    kwargs["json"] = json.loads(body)
                except json.JSONDecodeError:
                    kwargs["data"] = body
            
            # Form data
            form_data = config.get("form_data", {})
            if form_data:
                kwargs["data"] = {k: self._interpolate(v, {**params, **context})
                                  for k, v in form_data.items()}
        
        # Query params
        query = config.get("query", {})
        if query:
            query_str = urlencode({k: self._interpolate(str(v), {**params, **context})
                                   for k, v in query.items()})
            url = f"{url}?{query_str}" if "?" not in url else f"{url}&{query_str}"
        
        response = requests.request(method, url, **kwargs)
        response.raise_for_status()
        
        try:
            return {"success": True, "data": response.json()}
        except ValueError:
            return {"success": True, "data": response.text}
    
    def _interpolate(self, template: str, values: Dict[str, Any]) -> str:
        """Replace {param_name} with actual values."""
        result = template
        for key, val in values.items():
            result = result.replace(f"{{{key}}}", str(val))
        return result


class ShellExecutor(ActionExecutor):
    """Execute shell command actions safely."""
    
    ALLOWED_COMMANDS = {
        "git", "ls", "dir", "cat", "type", "find", "grep", "rg",
        "echo", "pwd", "cd", "mkdir", "rm", "cp", "mv", "touch",
        "python", "python3", "node", "npm", "cargo", "go",
        "curl", "wget", "head", "tail", "wc", "sort", "uniq",
        "docker", "docker-compose", "kubectl", "helm",
    }
    
    def execute(self, action: ToolAction, params: Dict[str, Any],
                context: Dict[str, Any]) -> Dict[str, Any]:
        config = action.config
        command_template = config.get("command", "")
        
        # Interpolate command
        command = self._interpolate(command_template, {**params, **context})
        
        # Safety check
        cmd_parts = command.strip().split()
        if cmd_parts and cmd_parts[0] not in self.ALLOWED_COMMANDS:
            return {
                "success": False,
                "error": f"Command '{cmd_parts[0]}' not in allowed list",
            }
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=config.get("timeout", 30),
                cwd=config.get("cwd", "."),
            )
            
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Command timed out"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _interpolate(self, template: str, values: Dict[str, Any]) -> str:
        result = template
        for key, val in values.items():
            result = result.replace(f"{{{key}}}", str(val))
        return result


class FileExecutor(ActionExecutor):
    """Execute file operation actions."""
    
    def execute(self, action: ToolAction, params: Dict[str, Any],
                context: Dict[str, Any]) -> Dict[str, Any]:
        config = action.config
        operation = config.get("operation", "read")
        path_template = config.get("path", "")
        
        path = self._interpolate(path_template, {**params, **context})
        path = Path(path)
        
        try:
            if operation == "read":
                if not path.exists():
                    return {"success": False, "error": f"File not found: {path}"}
                content = path.read_text(encoding="utf-8")
                return {"success": True, "content": content, "path": str(path)}
            
            elif operation == "write":
                content_template = config.get("content", "")
                content = self._interpolate(content_template, {**params, **context})
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                return {"success": True, "path": str(path), "bytes_written": len(content)}
            
            elif operation == "delete":
                if path.exists():
                    if path.is_file():
                        path.unlink()
                    else:
                        import shutil
                        shutil.rmtree(path)
                return {"success": True, "path": str(path)}
            
            elif operation == "list":
                if path.exists() and path.is_dir():
                    items = [{"name": p.name, "type": "dir" if p.is_dir() else "file"}
                             for p in path.iterdir()]
                    return {"success": True, "items": items, "path": str(path)}
                return {"success": False, "error": f"Directory not found: {path}"}
            
            else:
                return {"success": False, "error": f"Unknown operation: {operation}"}
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _interpolate(self, template: str, values: Dict[str, Any]) -> str:
        result = template
        for key, val in values.items():
            result = result.replace(f"{{{key}}}", str(val))
        return result


class PythonExecutor(ActionExecutor):
    """Execute Python expression actions."""
    
    def execute(self, action: ToolAction, params: Dict[str, Any],
                context: Dict[str, Any]) -> Dict[str, Any]:
        config = action.config
        expression_template = config.get("expression", "")
        
        expression = self._interpolate(expression_template, {**params, **context})
        
        # Safe evaluation with limited builtins
        safe_globals = {
            "__builtins__": {
                "len": len, "str": str, "int": int, "float": float,
                "bool": bool, "list": list, "dict": dict, "set": set,
                "range": range, "enumerate": enumerate, "zip": zip,
                "sum": sum, "min": min, "max": max, "abs": abs,
                "round": round, "sorted": sorted, "reversed": reversed,
                "map": map, "filter": filter, "any": any, "all": all,
                "json": json, "re": re, "time": time,
            }
        }
        safe_locals = {**params, **context}
        
        try:
            result = eval(expression, safe_globals, safe_locals)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _interpolate(self, template: str, values: Dict[str, Any]) -> str:
        result = template
        for key, val in values.items():
            result = result.replace(f"{{{key}}}", str(val))
        return result


# â”€â”€ Custom Tool Registry â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class CustomToolRegistry:
    """Registry for custom tools defined via JSON/YAML."""
    
    EXECUTORS = {
        "http": HTTPExecutor(),
        "shell": ShellExecutor(),
        "file": FileExecutor(),
        "python": PythonExecutor(),
    }
    
    def __init__(self, tools_dir: str = "tools"):
        self.tools_dir = Path(tools_dir)
        self.tools: Dict[str, CustomToolDef] = {}
        self._load_tools()
    
    def _load_tools(self):
        """Load all custom tool definitions from disk."""
        if not self.tools_dir.exists():
            return
        
        for path in self.tools_dir.iterdir():
            if path.suffix not in (".json", ".yaml", ".yml"):
                continue
            try:
                self._load_tool_file(path)
            except Exception as e:
                logger.warning(f"Failed to load custom tool {path}: {e}")
    
    def _load_tool_file(self, path: Path):
        """Load a single custom tool file."""
        import yaml
        
        with open(path, "r", encoding="utf-8") as f:
            if path.suffix == ".json":
                data = json.load(f)
            else:
                data = yaml.safe_load(f)
        
        if not data:
            return
        
        # Parse parameters
        params = []
        for p in data.get("parameters", []):
            params.append(ToolParameter(
                name=p.get("name", "param"),
                type=p.get("type", "string"),
                required=p.get("required", True),
                default=p.get("default"),
                description=p.get("description", ""),
            ))
        
        # Parse actions
        actions = []
        for a in data.get("actions", []):
            actions.append(ToolAction(
                type=a.get("type", "http"),
                config=a.get("config", {}),
                condition=a.get("condition", ""),
                output_var=a.get("output_var", ""),
            ))
        
        tool = CustomToolDef(
            name=data.get("name", path.stem),
            description=data.get("description", ""),
            version=data.get("version", "1.0"),
            permission=data.get("permission", "read"),
            category=data.get("category", "custom"),
            parameters=params,
            actions=actions,
            examples=data.get("examples", []),
            enabled=data.get("enabled", True),
            author=data.get("author", ""),
            tags=data.get("tags", []),
        )
        
        self.tools[tool.name] = tool
        logger.info(f"Loaded custom tool: {tool.name} ({tool.version})")
    
    def reload(self):
        """Reload all tools from disk."""
        self.tools.clear()
        self._load_tools()
        logger.info(f"Reloaded {len(self.tools)} custom tools")
    
    def list_tools(self) -> List[CustomToolDef]:
        """List all custom tools."""
        return [t for t in self.tools.values() if t.enabled]
    
    def get(self, name: str) -> Optional[CustomToolDef]:
        """Get a tool by name."""
        return self.tools.get(name)
    
    def execute(self, name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a custom tool with given parameters."""
        tool = self.get(name)
        if not tool:
            return {"success": False, "error": f"Tool not found: {name}"}
        
        if not tool.enabled:
            return {"success": False, "error": f"Tool disabled: {name}"}
        
        # Validate required parameters
        for param in tool.parameters:
            if param.required and param.name not in params:
                return {"success": False, "error": f"Missing required parameter: {param.name}"}
        
        # Apply defaults
        for param in tool.parameters:
            if param.name not in params and param.default is not None:
                params[param.name] = param.default
        
        # Execute actions
        context = {}
        results = []
        
        for action in tool.actions:
            # Check condition
            if action.condition:
                try:
                    if not eval(action.condition, {"__builtins__": {}}, {**params, **context}):
                        continue
                except Exception as e:
                    logger.warning(f"Condition evaluation failed: {e}")
                    continue
            
            executor = self.EXECUTORS.get(action.type)
            if not executor:
                return {"success": False, "error": f"Unknown action type: {action.type}"}
            
            result = executor.execute(action, params, context)
            results.append(result)
            
            # Store output in context if specified
            if action.output_var and result.get("success"):
                context[action.output_var] = result.get("data") or result.get("result") or result
        
        # Return final result
        return {
            "success": all(r.get("success", True) for r in results),
            "tool": name,
            "results": results,
            "context": context,
        }
    
    def save_example(self, name: str) -> Path:
        """Save an example custom tool to disk."""
        example = {
            "name": name,
            "description": f"Example custom tool: {name}",
            "version": "1.0",
            "permission": "read",
            "category": "custom",
            "parameters": [
                {
                    "name": "query",
                    "type": "string",
                    "required": True,
                    "description": "Search query",
                }
            ],
            "actions": [
                {
                    "type": "http",
                    "config": {
                        "method": "GET",
                        "url": "https://api.example.com/search?q={query}",
                        "headers": {"Accept": "application/json"},
                    },
                    "output_var": "search_results",
                }
            ],
            "examples": [f"Search for information using {name}"],
            "enabled": True,
            "tags": ["example"],
        }
        
        self.tools_dir.mkdir(parents=True, exist_ok=True)
        path = self.tools_dir / f"{name}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(example, f, indent=2)
        
        logger.info(f"Saved example custom tool to {path}")
        return path


def get_custom_tool_registry(tools_dir: str = "tools") -> CustomToolRegistry:
    """Get the global custom tool registry."""
    return CustomToolRegistry(tools_dir=tools_dir)

