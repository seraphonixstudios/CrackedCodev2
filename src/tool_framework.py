"""Tool Calling Framework - ReAct-style agent tools with safety and JSON schema.

Provides a decorator-based tool registry with:
- Automatic JSON schema generation from type hints
- Permission levels (READ, WRITE, EXECUTE, DANGEROUS)
- ReAct loop: Thought → Action → Observation → Reflection
- Built-in tools for file system, shell, git, code analysis

Architecture:
    @tool decorator → ToolRegistry → ReActLoop → AgentWorker
"""

import os
import re
import json
import time
import inspect
import hashlib
import subprocess
from pathlib import Path
from typing import Optional, Dict, List, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps

from src.logger_config import get_logger

try:
    from src.reasoning import get_reasoning_engine, ReasoningType
    REASONING_AVAILABLE = True
except ImportError:
    REASONING_AVAILABLE = False

try:
    from src.codebase_rag import get_codebase_indexer
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False

logger = get_logger("ToolFramework")


class ToolPermission(Enum):
    """Permission levels for tool execution."""
    READ = "read"           # Read-only: file read, directory list, search
    WRITE = "write"         # File modifications: write, delete, move
    EXECUTE = "execute"     # Safe execution: run tests, linters
    DANGEROUS = "dangerous" # Potentially harmful: shell commands, git push


class ToolCategory(Enum):
    """Categories for organizing tools."""
    FILESYSTEM = "filesystem"
    CODE = "code"
    SHELL = "shell"
    GIT = "git"
    RAG = "rag"
    ENGINE = "engine"
    REASONING = "reasoning"
    SYSTEM = "system"


@dataclass
class ToolResult:
    """Result of a tool execution."""
    success: bool
    tool_name: str
    result: Any = None
    error: str = ""
    duration: float = 0.0
    permission: str = ""
    observation: str = ""  # Human-readable observation for ReAct loop

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "tool_name": self.tool_name,
            "result": self.result,
            "error": self.error,
            "duration": round(self.duration, 3),
            "permission": self.permission,
            "observation": self.observation,
        }


@dataclass
class Tool:
    """A callable tool with metadata."""
    name: str
    description: str
    handler: Callable
    parameters: Dict[str, Any] = field(default_factory=dict)
    permission: ToolPermission = ToolPermission.READ
    category: ToolCategory = ToolCategory.SYSTEM
    examples: List[str] = field(default_factory=list)

    def get_schema(self) -> Dict[str, Any]:
        """Get JSON schema for this tool."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "permission": self.permission.value,
            "category": self.category.value,
            "examples": self.examples,
        }

    def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with given parameters."""
        start = time.time()
        try:
            # Validate required parameters
            sig = inspect.signature(self.handler)
            bound = sig.bind(**kwargs)
            bound.apply_defaults()
            
            result = self.handler(**kwargs)
            
            observation = self._build_observation(result)
            
            return ToolResult(
                success=True,
                tool_name=self.name,
                result=result,
                duration=time.time() - start,
                permission=self.permission.value,
                observation=observation,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                tool_name=self.name,
                error=str(e),
                duration=time.time() - start,
                permission=self.permission.value,
                observation=f"Failed to execute {self.name}: {str(e)}",
            )

    def _build_observation(self, result: Any) -> str:
        """Build a human-readable observation from the result."""
        if isinstance(result, dict):
            if "content" in result:
                preview = str(result["content"])[:200]
                return f"Retrieved {len(str(result['content']))} chars. Preview: {preview}..."
            if "files" in result:
                return f"Found {len(result.get('files', []))} items."
            if "output" in result:
                preview = str(result["output"])[:200]
                return f"Command output ({len(str(result['output']))} chars). Preview: {preview}..."
            if "matches" in result:
                return f"Found {len(result.get('matches', []))} matches."
        if isinstance(result, list):
            return f"Found {len(result)} items."
        if isinstance(result, str):
            preview = result[:200]
            return f"Result ({len(result)} chars): {preview}..."
        return f"Result: {str(result)[:200]}"


def _python_type_to_json_schema(annotation: Any) -> Dict[str, Any]:
    """Convert a Python type annotation to JSON schema."""
    if annotation == str or annotation == "str":
        return {"type": "string"}
    elif annotation == int or annotation == "int":
        return {"type": "integer"}
    elif annotation == float or annotation == "float":
        return {"type": "number"}
    elif annotation == bool or annotation == "bool":
        return {"type": "boolean"}
    elif annotation == list or annotation == "list" or getattr(annotation, "__origin__", None) == list:
        return {"type": "array"}
    elif annotation == dict or annotation == "dict" or getattr(annotation, "__origin__", None) == dict:
        return {"type": "object"}
    elif hasattr(annotation, "__args__") and len(annotation.__args__) == 2 and type(None) in annotation.__args__:
        # Optional[X] → nullable
        inner = [a for a in annotation.__args__ if a is not type(None)][0]
        schema = _python_type_to_json_schema(inner)
        schema["nullable"] = True
        return schema
    else:
        return {"type": "string"}


def tool(name: str = None, description: str = None, permission: ToolPermission = ToolPermission.READ,
         category: ToolCategory = ToolCategory.SYSTEM, examples: List[str] = None):
    """Decorator to register a function as a tool.
    
    Auto-generates JSON schema from type hints and docstring.
    
    Usage:
        @tool(description="Read a file", permission=ToolPermission.READ, category=ToolCategory.FILESYSTEM)
        def read_file(path: str) -> Dict[str, Any]:
            ...
    """
    def decorator(func: Callable) -> Callable:
        tool_name = name or func.__name__
        tool_desc = description or (func.__doc__ or "").strip().split("\n")[0]
        
        # Extract parameters from signature
        sig = inspect.signature(func)
        params = {}
        for param_name, param in sig.parameters.items():
            if param_name.startswith("_"):
                continue
            param_schema = _python_type_to_json_schema(param.annotation)
            if param.default != inspect.Parameter.empty:
                param_schema["default"] = param.default
            else:
                param_schema["required"] = True
            params[param_name] = param_schema
        
        # Register
        registry = ToolRegistry.get_instance()
        registry.register(Tool(
            name=tool_name,
            description=tool_desc,
            handler=func,
            parameters=params,
            permission=permission,
            category=category,
            examples=examples or [],
        ))
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        wrapper._tool_name = tool_name
        return wrapper
    
    return decorator


class ToolRegistry:
    """Central registry for all tools."""
    
    _instance: Optional["ToolRegistry"] = None
    
    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        self._permissions: Dict[str, bool] = {}  # tool_name -> allowed
        self._execution_log: List[Dict[str, Any]] = []
        self.max_log_size = 1000
    
    @classmethod
    def get_instance(cls) -> "ToolRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset(cls):
        cls._instance = None
    
    def register(self, tool: Tool) -> Tool:
        """Register a tool."""
        self._tools[tool.name] = tool
        # Default: all permissions granted except DANGEROUS
        self._permissions[tool.name] = tool.permission != ToolPermission.DANGEROUS
        logger.info(f"Registered tool: {tool.name} ({tool.permission.value})")
        return tool
    
    def get(self, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        return self._tools.get(name)
    
    def list_tools(self, category: ToolCategory = None, permission: ToolPermission = None) -> List[Tool]:
        """List all tools with optional filtering."""
        tools = list(self._tools.values())
        if category:
            tools = [t for t in tools if t.category == category]
        if permission:
            tools = [t for t in tools if t.permission == permission]
        return tools
    
    def get_schemas(self, category: ToolCategory = None) -> List[Dict[str, Any]]:
        """Get JSON schemas for all tools."""
        return [t.get_schema() for t in self.list_tools(category)]
    
    def set_permission(self, tool_name: str, allowed: bool):
        """Enable or disable a tool."""
        if tool_name in self._permissions:
            self._permissions[tool_name] = allowed
    
    def is_allowed(self, tool_name: str) -> bool:
        """Check if a tool is allowed to execute."""
        return self._permissions.get(tool_name, False)
    
    def execute(self, tool_name: str, **kwargs) -> ToolResult:
        """Execute a tool by name with parameters."""
        tool = self.get(tool_name)
        if not tool:
            return ToolResult(
                success=False,
                tool_name=tool_name,
                error=f"Tool '{tool_name}' not found",
                observation=f"Tool '{tool_name}' not found in registry.",
            )
        
        if not self.is_allowed(tool_name):
            return ToolResult(
                success=False,
                tool_name=tool_name,
                error=f"Tool '{tool_name}' is not permitted ({tool.permission.value})",
                observation=f"Permission denied: {tool_name} requires {tool.permission.value} permission.",
            )
        
        result = tool.execute(**kwargs)
        self._log_execution(result)
        return result
    
    def _log_execution(self, result: ToolResult):
        """Log tool execution."""
        entry = {
            "timestamp": time.time(),
            **result.to_dict(),
        }
        self._execution_log.append(entry)
        if len(self._execution_log) > self.max_log_size:
            self._execution_log = self._execution_log[-self.max_log_size:]
    
    def get_execution_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent execution log."""
        return self._execution_log[-limit:]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        total = len(self._tools)
        by_category = {}
        by_permission = {}
        for t in self._tools.values():
            by_category[t.category.value] = by_category.get(t.category.value, 0) + 1
            by_permission[t.permission.value] = by_permission.get(t.permission.value, 0) + 1
        
        successful = sum(1 for e in self._execution_log if e.get("success"))
        total_exec = len(self._execution_log)
        
        return {
            "total_tools": total,
            "by_category": by_category,
            "by_permission": by_permission,
            "total_executions": total_exec,
            "successful_executions": successful,
            "success_rate": round(successful / total_exec, 3) if total_exec > 0 else 1.0,
        }


# ─────────────────────────────────────────────────────────────────────────────
# BUILT-IN TOOLS
# ─────────────────────────────────────────────────────────────────────────────

@tool(description="Read contents of a file", permission=ToolPermission.READ, category=ToolCategory.FILESYSTEM,
      examples=["read_file(path='src/main.py')"])
def read_file(path: str, limit_lines: int = 100) -> Dict[str, Any]:
    """Read a file's contents with optional line limit."""
    try:
        p = Path(path)
        if not p.exists():
            return {"success": False, "error": f"File not found: {path}"}
        
        content = p.read_text(encoding="utf-8", errors="ignore")
        lines = content.split("\n")
        truncated = len(lines) > limit_lines
        display_lines = lines[:limit_lines]
        
        return {
            "success": True,
            "path": str(p.resolve()),
            "content": "\n".join(display_lines),
            "total_lines": len(lines),
            "truncated": truncated,
            "size_bytes": len(content.encode("utf-8")),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@tool(description="Write contents to a file", permission=ToolPermission.WRITE, category=ToolCategory.FILESYSTEM,
      examples=["write_file(path='src/utils.py', content='def helper(): pass')"])
def write_file(path: str, content: str) -> Dict[str, Any]:
    """Write content to a file (creates directories if needed)."""
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return {
            "success": True,
            "path": str(p.resolve()),
            "size_bytes": len(content.encode("utf-8")),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@tool(description="List files in a directory", permission=ToolPermission.READ, category=ToolCategory.FILESYSTEM,
      examples=["list_directory(path='src')"])
def list_directory(path: str = ".") -> Dict[str, Any]:
    """List files and directories."""
    try:
        p = Path(path)
        if not p.exists():
            return {"success": False, "error": f"Path not found: {path}"}
        
        entries = []
        for entry in p.iterdir():
            entries.append({
                "name": entry.name,
                "type": "directory" if entry.is_dir() else "file",
                "size": entry.stat().st_size if entry.is_file() else None,
            })
        
        return {
            "success": True,
            "path": str(p.resolve()),
            "entries": entries,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@tool(description="Search files by content pattern", permission=ToolPermission.READ, category=ToolCategory.FILESYSTEM,
      examples=["grep_files(pattern='def main', path='src', extension='.py')"])
def grep_files(pattern: str, path: str = ".", extension: str = ".py") -> Dict[str, Any]:
    """Grep for pattern in files."""
    try:
        matches = []
        p = Path(path)
        files = list(p.rglob(f"*{extension}")) if extension else list(p.rglob("*"))
        
        for file in files:
            if not file.is_file():
                continue
            try:
                content = file.read_text(encoding="utf-8", errors="ignore")
                lines = content.split("\n")
                for i, line in enumerate(lines):
                    if re.search(pattern, line):
                        matches.append({
                            "file": str(file.relative_to(p)),
                            "line": i + 1,
                            "content": line.strip(),
                        })
            except Exception:
                continue
        
        return {
            "success": True,
            "pattern": pattern,
            "matches": matches,
            "match_count": len(matches),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@tool(description="Get function/class signature from source", permission=ToolPermission.READ, category=ToolCategory.CODE,
      examples=["get_signature(path='src/engine.py', name='CrackedCodeEngine')"])
def get_signature(path: str, name: str) -> Dict[str, Any]:
    """Extract signature of a function or class from a file."""
    try:
        content = Path(path).read_text(encoding="utf-8", errors="ignore")
        
        # Try function
        func_match = re.search(rf"^[ \t]*(?:async\s+)?def\s+{re.escape(name)}\s*\((.*?)\)(?:\s*->\s*([^:]+))?:",
                              content, re.MULTILINE)
        if func_match:
            return {
                "success": True,
                "type": "function",
                "name": name,
                "signature": f"def {name}({func_match.group(1)}) -> {func_match.group(2) or 'Any'}",
                "parameters": [p.strip() for p in func_match.group(1).split(",") if p.strip()],
            }
        
        # Try class
        class_match = re.search(rf"^[ \t]*class\s+{re.escape(name)}\s*(?:\((.*?)\))?:",
                                content, re.MULTILINE)
        if class_match:
            return {
                "success": True,
                "type": "class",
                "name": name,
                "signature": f"class {name}({class_match.group(1) or ''})",
                "bases": [b.strip() for b in class_match.group(1).split(",")] if class_match.group(1) else [],
            }
        
        return {"success": False, "error": f"'{name}' not found in {path}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@tool(description="Run Python tests with pytest", permission=ToolPermission.EXECUTE, category=ToolCategory.SHELL,
      examples=["run_tests(path='tests', verbose=True)"])
def run_tests(path: str = ".", verbose: bool = False) -> Dict[str, Any]:
    """Run pytest tests in a directory."""
    try:
        cmd = ["python", "-m", "pytest", path]
        if verbose:
            cmd.append("-v")
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        return {
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "output": result.stdout,
            "stderr": result.stderr,
            "command": " ".join(cmd),
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Tests timed out after 120s"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@tool(description="Run ruff linter on code", permission=ToolPermission.EXECUTE, category=ToolCategory.SHELL,
      examples=["run_linter(path='src')"])
def run_linter(path: str = ".") -> Dict[str, Any]:
    """Run ruff linter on code files."""
    try:
        cmd = ["python", "-m", "ruff", "check", path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        return {
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "output": result.stdout,
            "stderr": result.stderr,
            "command": " ".join(cmd),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@tool(description="Run a safe shell command", permission=ToolPermission.DANGEROUS, category=ToolCategory.SHELL,
      examples=["run_shell(command='python --version')"])
def run_shell(command: str, timeout: int = 30) -> Dict[str, Any]:
    """Execute a shell command (dangerous - requires approval)."""
    try:
        # Safety check
        dangerous = {"rm", "del", "format", "fdisk", "mkfs", "dd"}
        tokens = command.lower().split()
        if any(d in tokens for d in dangerous):
            return {"success": False, "error": f"Command blocked for safety: {command}"}
        
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout)
        
        return {
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "output": result.stdout,
            "stderr": result.stderr,
            "command": command,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Command timed out after {timeout}s"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@tool(description="Get git status", permission=ToolPermission.READ, category=ToolCategory.GIT,
      examples=["git_status()"])
def git_status() -> Dict[str, Any]:
    """Get current git repository status."""
    try:
        result = subprocess.run(["git", "status", "--short"], capture_output=True, text=True, timeout=10)
        branch_result = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True, timeout=10)
        
        lines = result.stdout.strip().split("\n") if result.stdout.strip() else []
        
        return {
            "success": True,
            "branch": branch_result.stdout.strip(),
            "modified": [l for l in lines if l.startswith(" M") or l.startswith("M ")],
            "staged": [l for l in lines if l.startswith("A ") or l.startswith("M ")],
            "untracked": [l for l in lines if l.startswith("??")],
            "raw": result.stdout,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@tool(description="Get git diff for a file", permission=ToolPermission.READ, category=ToolCategory.GIT,
      examples=["git_diff(path='src/main.py')"])
def git_diff(path: str = None) -> Dict[str, Any]:
    """Get git diff for a specific file or all changes."""
    try:
        cmd = ["git", "diff"]
        if path:
            cmd.append(path)
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        return {
            "success": True,
            "output": result.stdout,
            "has_changes": len(result.stdout) > 0,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@tool(description="Semantic search over the codebase", permission=ToolPermission.READ, category=ToolCategory.RAG,
      examples=["search_codebase(query='authentication logic', top_k=5)"])
def search_codebase(query: str, top_k: int = 5, project_path: str = ".") -> Dict[str, Any]:
    """Search codebase using semantic embeddings."""
    if not RAG_AVAILABLE:
        return {"success": False, "error": "Codebase RAG not available"}
    
    try:
        indexer = get_codebase_indexer(project_path)
        indexer.index()
        results = indexer.search(query, top_k=top_k)
        
        return {
            "success": True,
            "query": query,
            "results": [
                {
                    "file": r.chunk.file_path,
                    "type": r.chunk.chunk_type,
                    "lines": f"{r.chunk.start_line}-{r.chunk.end_line}",
                    "score": round(r.score, 3),
                    "reasoning": r.reasoning,
                    "preview": r.chunk.content[:300],
                }
                for r in results
            ],
            "result_count": len(results),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@tool(description="Get relevant codebase context for a query", permission=ToolPermission.READ, category=ToolCategory.RAG,
      examples=["get_context(query='How to add a new endpoint?')"])
def get_context(query: str, project_path: str = ".", top_k: int = 3) -> Dict[str, Any]:
    """Get formatted context from codebase for LLM prompting."""
    if not RAG_AVAILABLE:
        return {"success": False, "error": "Codebase RAG not available"}
    
    try:
        indexer = get_codebase_indexer(project_path)
        indexer.index()
        context = indexer.get_context_for_prompt(query, top_k=top_k)
        
        return {
            "success": True,
            "query": query,
            "context": context,
            "context_length": len(context),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@tool(description="Log an observation to the reasoning engine", permission=ToolPermission.READ, category=ToolCategory.REASONING,
      examples=["log_observation(agent_id='coder', content='Found 3 bugs', confidence=0.8)"])
def log_observation(agent_id: str, content: str, confidence: float = 0.5, evidence: List[str] = None) -> Dict[str, Any]:
    """Log an observation step to the reasoning engine."""
    if not REASONING_AVAILABLE:
        return {"success": False, "error": "Reasoning engine not available"}
    
    try:
        engine = get_reasoning_engine()
        engine.add_reasoning_step(agent_id, content, step_type=ReasoningType.OBSERVATION, confidence=confidence, evidence=evidence or [])
        return {"success": True, "agent_id": agent_id, "content": content, "confidence": confidence}
    except Exception as e:
        return {"success": False, "error": str(e)}


@tool(description="Log a decision to the reasoning engine", permission=ToolPermission.READ, category=ToolCategory.REASONING,
      examples=["log_decision(agent_id='coder', content='Use FastAPI', confidence=0.9)"])
def log_decision(agent_id: str, content: str, confidence: float = 0.7, evidence: List[str] = None) -> Dict[str, Any]:
    """Log a decision step to the reasoning engine."""
    if not REASONING_AVAILABLE:
        return {"success": False, "error": "Reasoning engine not available"}
    
    try:
        engine = get_reasoning_engine()
        engine.add_reasoning_step(agent_id, content, step_type=ReasoningType.DECISION, confidence=confidence, evidence=evidence or [])
        return {"success": True, "agent_id": agent_id, "content": content, "confidence": confidence}
    except Exception as e:
        return {"success": False, "error": str(e)}


@tool(description="Get tool registry statistics", permission=ToolPermission.READ, category=ToolCategory.SYSTEM,
      examples=["get_tool_stats()"])
def get_tool_stats() -> Dict[str, Any]:
    """Get statistics about the tool registry."""
    registry = ToolRegistry.get_instance()
    return {"success": True, **registry.get_stats()}


@tool(description="List available tools with schemas", permission=ToolPermission.READ, category=ToolCategory.SYSTEM,
      examples=["list_tools()"])
def list_tools() -> Dict[str, Any]:
    """List all available tools with their schemas."""
    registry = ToolRegistry.get_instance()
    tools = registry.list_tools()
    
    return {
        "success": True,
        "tools": [t.get_schema() for t in tools],
        "count": len(tools),
    }


# ─────────────────────────────────────────────────────────────────────────────
# ReAct LOOP
# ─────────────────────────────────────────────────────────────────────────────

class ReActLoop:
    """ReAct reasoning loop: Thought → Action → Observation → Reflection."""
    
    def __init__(self, agent_id: str = "react_agent", max_iterations: int = 10):
        self.agent_id = agent_id
        self.max_iterations = max_iterations
        self.history: List[Dict[str, Any]] = []
        self.reasoning_engine = get_reasoning_engine() if REASONING_AVAILABLE else None
    
    def run(self, task_description: str, tool_schemas: List[Dict[str, Any]] = None,
            llm_callback: Callable[[str], str] = None) -> Dict[str, Any]:
        """Run the ReAct loop for a given task.
        
        Args:
            task_description: What the agent should accomplish
            tool_schemas: Available tools (auto-fetched if not provided)
            llm_callback: Function(prompt) -> response_text for LLM calls
            
        Returns:
            Dict with final_answer, iterations, tool_calls, reasoning
        """
        if not llm_callback:
            return {"success": False, "error": "No LLM callback provided"}
        
        registry = ToolRegistry.get_instance()
        schemas = tool_schemas or registry.get_schemas()
        
        # Start reasoning chain
        if self.reasoning_engine:
            self.reasoning_engine.create_reasoning_chain(
                self.agent_id,
                title=f"ReAct: {task_description[:50]}",
                context=task_description,
                tags=["react", "tool_calling"],
            )
        
        prompt_history = f"Task: {task_description}\n\nAvailable tools:\n"
        for schema in schemas:
            prompt_history += f"- {schema['name']}: {schema['description']}\n"
        
        prompt_history += "\nYou must respond in JSON format:\n"
        prompt_history += '{"thought": "your reasoning", "action": "tool_name", "parameters": {"key": "value"}}\n'
        prompt_history += 'Or when done: {"thought": "final reasoning", "action": "finish", "answer": "your final answer"}\n'
        
        iterations = 0
        tool_calls = []
        
        for iteration in range(self.max_iterations):
            iterations += 1
            
            # Think
            llm_prompt = prompt_history + f"\nIteration {iteration + 1}/{self.max_iterations}\nRespond with JSON:"
            response_text = llm_callback(llm_prompt)
            
            # Parse JSON response
            try:
                # Extract JSON from response
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if not json_match:
                    continue
                response = json.loads(json_match.group())
            except json.JSONDecodeError:
                continue
            
            thought = response.get("thought", "")
            action = response.get("action", "")
            
            # Log thought
            if self.reasoning_engine:
                self.reasoning_engine.add_reasoning_step(
                    self.agent_id, thought, step_type=ReasoningType.ANALYSIS, confidence=0.7
                )
            
            # Check if finished
            if action == "finish" or action == "done":
                answer = response.get("answer", response.get("result", "Task completed"))
                if self.reasoning_engine:
                    self.reasoning_engine.complete_reasoning_chain(self.agent_id, answer, 0.9)
                
                return {
                    "success": True,
                    "final_answer": answer,
                    "iterations": iterations,
                    "tool_calls": tool_calls,
                    "history": self.history,
                }
            
            # Execute tool
            params = response.get("parameters", response.get("args", {}))
            result = registry.execute(action, **params)
            
            tool_calls.append({
                "iteration": iteration,
                "tool": action,
                "parameters": params,
                "success": result.success,
                "observation": result.observation,
            })
            
            # Add observation to history
            prompt_history += f"\n[Thought {iteration}] {thought}\n"
            prompt_history += f"[Action] {action}({json.dumps(params)})\n"
            prompt_history += f"[Observation] {result.observation}\n"
            
            self.history.append({
                "iteration": iteration,
                "thought": thought,
                "action": action,
                "parameters": params,
                "observation": result.observation,
                "success": result.success,
            })
        
        # Max iterations reached
        return {
            "success": False,
            "error": f"Max iterations ({self.max_iterations}) reached without completion",
            "iterations": iterations,
            "tool_calls": tool_calls,
            "history": self.history,
        }


# Convenience function
def get_tool_registry() -> ToolRegistry:
    """Get the global tool registry."""
    return ToolRegistry.get_instance()
