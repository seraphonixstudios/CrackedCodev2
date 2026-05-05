import sys
import os
import json
import re
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional, Dict, List, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio

from src.logger_config import get_logger

try:
    from src.reasoning import (
        ReasoningEngine, ThoughtChain, ReasoningType,
        get_reasoning_engine
    )
    _reasoning_available = True
except ImportError:
    _reasoning_available = False
    ReasoningEngine = None
    ThoughtChain = None
    ReasoningType = None
    get_reasoning_engine = None

try:
    from src.codebase_rag import CodebaseIndexer, SearchResult, get_codebase_indexer
    _rag_available = True
except ImportError:
    _rag_available = False
    CodebaseIndexer = None
    SearchResult = None
    get_codebase_indexer = None

try:
    from src.tool_framework import (
        ToolRegistry, ReActLoop, ToolPermission,
        get_tool_registry
    )
    _tools_available = True
except ImportError:
    _tools_available = False
    ToolRegistry = None
    ReActLoop = None
    ToolPermission = None
    get_tool_registry = None

try:
    from src.plugin_system import (
        PluginRegistry, HookPoint, get_plugin_registry, execute_hook
    )
    _plugins_available = True
except ImportError:
    _plugins_available = False
    PluginRegistry = None
    HookPoint = None
    get_plugin_registry = None
    execute_hook = None

logger = get_logger("CrackedCodeEngine")


class Intent(Enum):
    CHAT = "chat"
    CODE = "code"
    DEBUG = "debug"
    SEARCH = "search"
    REVIEW = "review"
    EXECUTE = "execute"
    BUILD = "build"
    HELP = "help"
    VISION = "vision"
    SECURITY = "security"
    BROWSE = "browse"


@dataclass
class PromptRequest:
    text: str
    intent: Intent = Intent.CHAT
    context: Dict = field(default_factory=dict)
    user_level: str = "intermediate"
    timestamp: datetime = field(default_factory=datetime.now)
    reasoning_log: List[Dict] = field(default_factory=list)
    
    def add_reasoning(self, step_type: str, content: str, confidence: float = 0.5):
        """Add a reasoning step to the request."""
        self.reasoning_log.append({
            "type": step_type,
            "content": content,
            "confidence": confidence,
            "timestamp": time.time(),
        })


@dataclass
class AgentResponse:
    success: bool
    text: str = ""
    intent: Intent = Intent.CHAT
    error: Optional[str] = None
    execution_time: float = 0.0
    reasoning_log: List[Dict] = field(default_factory=list)
    model_used: str = ""
    processing_path: str = ""
    
    def add_reasoning(self, step_type: str, content: str, confidence: float = 0.5):
        """Add a reasoning step to the response."""
        self.reasoning_log.append({
            "type": step_type,
            "content": content,
            "confidence": confidence,
            "timestamp": time.time(),
        })


class VoiceEngine:
    def __init__(self, model: str = "medium.en"):
        self.model = model
        self.whisper = None

    def load(self):
        try:
            from faster_whisper import WhisperModel
            self.whisper = WhisperModel(self.model, device="cuda", compute_type="int8")
            logger.info(f"Whisper loaded: {self.model}")
            return True
        except Exception as e:
            logger.error(f"Whisper load failed: {e}")
            return False

    def transcribe(self, audio_bytes: bytes) -> str:
        if not self.whisper:
            self.load()
        try:
            import io, wave
            buffer = io.BytesIO()
            with wave.open(buffer, 'wb') as f:
                f.setnchannels(1); f.setsampwidth(2); f.setframerate(16000)
                f.writeframes(audio_bytes)
            buffer.seek(0)
            result = self.whisper.transcribe(buffer)
            return result[0].strip()
        except Exception as e:
            logger.error(f"Transcribe failed: {e}")
            return ""


class OllamaBridge:
    def __init__(self, model: str = "qwen3:8b-gpu"):
        self.model = model
        self.ollama = None
        self.unified_mode = False
        self.models = {
            "qwen3:8b-gpu": {"role": "general", "strength": "reasoning,coding,planning"},
            "dolphin-llama3:8b-gpu": {"role": "creative", "strength": "conversation,writing,creative"},
            "llava:13b-gpu": {"role": "vision", "strength": "image,analysis,ocr"},
        }
        self.available_models = []
        self._cache: Dict[str, AgentResponse] = {}
        self._max_retries = 2
        self._context_window: List[Dict] = []
        self._max_context = 20

    def detect(self) -> Dict:
        result = {"available": False, "models": [], "host": "http://localhost:11434", "selected": self.model}
        try:
            import ollama
            self.ollama = ollama
            response = ollama.list()
            self.available_models = [m.model for m in response.models]
            result["models"] = self.available_models
            result["available"] = True
            if self.model not in result["models"]:
                self.model = result["models"][0] if result["models"] else "qwen3:8b-gpu"
            result["selected"] = self.model
            logger.info(f"Ollama detected: {result['models']}")
        except Exception as e:
            logger.error(f"Ollama detection failed: {e}")
        return result

    def set_unified_mode(self, enabled: bool = True):
        self.unified_mode = enabled
        logger.info(f"Unified mode: {'ENABLED' if enabled else 'DISABLED'}")

    def _get_cache_key(self, prompt: str, system: str, model: str) -> str:
        import hashlib
        content = f"{model}:{system}:{prompt}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def chat(self, prompt: str, system: str = "", model: str = None, use_cache: bool = True) -> AgentResponse:
        if not self.ollama:
            self.detect()
        
        cache_key = self._get_cache_key(prompt, system, model or self.model)
        if use_cache and cache_key in self._cache:
            logger.info(f"Cache hit for query")
            return self._cache[cache_key]
        
        start = time.time()
        target_model = model or self.model
        
        for attempt in range(self._max_retries + 1):
            try:
                messages = [{"role": "system", "content": system}] if system else []
                messages.extend(self._context_window[-self._max_context:])
                messages.append({"role": "user", "content": prompt})
                
                response = self.ollama.chat(model=target_model, messages=messages, options={"temperature": 0.1})
                text = response.message.content
                
                self._context_window.append({"role": "user", "content": prompt})
                self._context_window.append({"role": "assistant", "content": text})
                if len(self._context_window) > self._max_context * 2:
                    self._context_window = self._context_window[-self._max_context:]
                
                result = AgentResponse(success=True, text=text, execution_time=time.time() - start)
                
                if use_cache:
                    self._cache[cache_key] = result
                
                return result
            except Exception as e:
                logger.error(f"Ollama chat failed (attempt {attempt + 1}/{self._max_retries + 1}): {e}")
                if attempt < self._max_retries:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                return AgentResponse(success=False, error=str(e))
        
        return AgentResponse(success=False, error="Max retries exceeded")

    def chat_stream(self, prompt: str, system: str = "", model: str = None, callback: Callable[[str], None] = None):
        if not self.ollama:
            self.detect()
        
        target_model = model or self.model
        
        try:
            messages = [{"role": "system", "content": system}] if system else []
            messages.extend(self._context_window[-self._max_context:])
            messages.append({"role": "user", "content": prompt})
            
            stream = self.ollama.chat(model=target_model, messages=messages, stream=True, options={"temperature": 0.1})
            
            full_response = ""
            for chunk in stream:
                if hasattr(chunk, 'message') and hasattr(chunk.message, 'content'):
                    text = chunk.message.content
                    full_response += text
                    if callback:
                        callback(text)
            
            self._context_window.append({"role": "user", "content": prompt})
            self._context_window.append({"role": "assistant", "content": full_response})
            if len(self._context_window) > self._max_context * 2:
                self._context_window = self._context_window[-self._max_context:]
            
            return AgentResponse(success=True, text=full_response, execution_time=0.0)
        except Exception as e:
            logger.error(f"Ollama stream chat failed: {e}")
            return AgentResponse(success=False, error=str(e))

    def clear_cache(self):
        self._cache.clear()
        logger.info("Cache cleared")

    def clear_context(self):
        self._context_window.clear()
        logger.info("Context cleared")

    def get_cache_stats(self) -> Dict:
        return {
            "size": len(self._cache),
            "context_length": len(self._context_window),
            "max_context": self._max_context,
        }

    def unified_chat(self, prompt: str, system: str = "") -> AgentResponse:
        if not self.ollama:
            self.detect()
        
        start = time.time()
        
        if self.unified_mode and len(self.available_models) >= 3:
            qwen_model = "qwen3:8b-gpu" if "qwen3:8b-gpu" in self.available_models else self.available_models[0]
            dolphin_model = "dolphin-llama3:8b-gpu" if "dolphin-llama3:8b-gpu" in self.available_models else self.available_models[1] if len(self.available_models) > 1 else qwen_model
            
            system_prompt = system or "You are CrackedCode, a unified AI coding assistant."
            
            messages = [
                {"role": "system", "content": f"{system_prompt}\n\nYou have access to specialized knowledge from multiple AI models working in harmony."},
                {"role": "user", "content": f"[UNIFIED INTELLIGENCE MODE]\n\nAnalyze this request thoroughly:\n\n{prompt}\n\nProvide a comprehensive response that leverages all knowledge domains."}
            ]
            
            try:
                response = self.ollama.chat(model=qwen_model, messages=messages, options={"temperature": 0.2})
                text = response.message.content
                
                dolphin_messages = [
                    {"role": "system", "content": "You are a creative AI assistant. Review and enhance the following response with creative insights."},
                    {"role": "user", "content": f"Original response:\n\n{text}\n\nProvide additional creative perspectives and enhancements:"}
                ]
                
                try:
                    dolphin_response = self.ollama.chat(model=dolphin_model, messages=dolphin_messages, options={"temperature": 0.3})
                    creative_additions = dolphin_response.message.content
                    text = f"{text}\n\n--- Creative Insights ---\n{creative_additions}"
                except Exception as e:
                    logger.warning(f"Dolphin model enhancement failed: {e}")
                
                return AgentResponse(success=True, text=f"[UNIFIED BRAIN]\n\n{text}", execution_time=time.time() - start)
            except Exception as e:
                logger.error(f"Unified chat failed: {e}")
                return self.chat(prompt, system)
        else:
            return self.chat(prompt, system)

    def specialized_chat(self, prompt: str, specialty: str, system: str = "") -> AgentResponse:
        if not self.ollama:
            self.detect()
        
        start = time.time()
        
        specialty_map = {
            "vision": ("llava:13b-gpu", "You are a vision expert analyzing images."),
            "creative": ("dolphin-llama3:8b-gpu", "You are a creative and conversational AI."),
            "code": ("qwen3:8b-gpu", "You are an expert coding assistant."),
            "general": (self.model, "You are a helpful AI assistant."),
        }
        
        model_key = specialty_map.get(specialty, specialty_map["general"])
        target_model = model_key[0] if isinstance(model_key, tuple) else model_key
        
        if target_model not in self.available_models:
            target_model = self.model
        
        messages = [{"role": "system", "content": system or model_key[1]}] if isinstance(model_key, tuple) else []
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = self.ollama.chat(model=target_model, messages=messages, options={"temperature": 0.1})
            text = response.message.content
            return AgentResponse(success=True, text=f"[{specialty.upper()}] {text}", execution_time=time.time() - start)
        except Exception as e:
            logger.error(f"Specialized chat failed: {e}")
            return AgentResponse(success=False, error=str(e))


class CodeExecutor:
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.allowed = ["python", "pytest", "ruff", "git", "npm", "node", "pip", "echo", "ls", "dir", "cat", "type", "cd"]

    def run_shell(self, cmd: str) -> AgentResponse:
        import subprocess
        parts = cmd.strip().split()
        if not parts or parts[0] not in self.allowed:
            return AgentResponse(success=False, error=f"Not allowed: {parts[0] if parts else 'none'}")
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30, cwd=self.project_root)
            return AgentResponse(success=result.returncode == 0, text=result.stdout or result.stderr)
        except Exception as e:
            return AgentResponse(success=False, error=str(e))


class SessionManager:
    def __init__(self, session_file: str = "session.json"):
        self.session_file = Path(session_file)
        self.session: Dict = {}
        self.load()

    def load(self):
        if self.session_file.exists():
            try:
                with open(self.session_file) as f:
                    content = f.read().strip()
                    if content:
                        self.session = json.loads(content)
            except (json.JSONDecodeError, IOError):
                self.session = {"history": []}

    def save(self):
        with open(self.session_file, 'w') as f:
            json.dump(self.session, f, indent=2, default=str)

    def add_turn(self, request: PromptRequest, response: AgentResponse):
        turn = {"timestamp": request.timestamp.isoformat(), "request": request.text, "response": response.text[:200]}
        self.session.setdefault("history", []).append(turn)
        if len(self.session["history"]) > 100:
            self.session["history"] = self.session["history"][-100:]
        self.save()

    def history_len(self) -> int:
        return len(self.session.get("history", []))


class CrackedCodeEngine:
    PROMPT_TEMPLATES = {
        Intent.CODE: """Generate complete Python code for this task.

Requirements:
- Include all necessary imports
- Add proper error handling
- Include type hints and docstrings
- Write clean, production-ready code
- Follow PEP 8 style guidelines

Task: {prompt}

Output the code in a code block.
""",
        Intent.DEBUG: """Find and fix bugs in the following code.

Analysis Steps:
1. Identify the bug or issue
2. Explain the root cause
3. Provide the fixed code

Task: {prompt}

Output analysis and fixed code in a code block.
""",
        Intent.REVIEW: """Analyze and review the following code for quality.

Check:
1. Code structure and organization
2. Error handling
3. Performance considerations
4. Security issues
5. Best practices

Provide a detailed review with suggestions.

Task: {prompt}

Output review in a code block.
""",
        Intent.BUILD: """Create a detailed implementation plan for this task.

Include:
1. Overall architecture
2. File structure
3. Step-by-step implementation
4. Dependencies required
5. Testing strategy

Task: {prompt}

Output plan in a code block.
""",
        Intent.VISION: """Analyze the provided screenshot and answer the user's question.

Be specific about:
- UI elements (buttons, menus, text fields)
- Text content and labels
- Error messages or warnings
- Layout and visual structure

Question: {prompt}
""",
        Intent.SECURITY: """Perform a security analysis for this task.

Check for:
1. Hardcoded secrets, API keys, passwords
2. SQL injection, XSS, CSRF vulnerabilities
3. Unsafe deserialization or eval/exec usage
4. Missing input validation or sanitization
5. Insecure file permissions or configurations
6. Dependency vulnerabilities
7. Insecure communication (HTTP vs HTTPS)

Provide specific findings with file paths, line numbers, and remediation steps.

Task: {prompt}
""",
        Intent.BROWSE: """Analyze the following web page content and answer the user's question.

Content from {url}:
{content}

Question: {prompt}
""",
    }
    
    DEBUG_KEYWORDS = {
        "direct": ["debug", "bug", "error", "crash", "broken", "stacktrace", "traceback", "exception", "segfault", "overflow"],
        "phrases": ["fix bug", "fix error", "fix crash", "fix issue", "what's wrong", "what is wrong", "why is it failing", "why does it fail", "not working", "doesn't work", "won't work", "should be doing"],
        "negative": ["feature", "enhancement", "improve", "optimize", "refactor"],
    }
    CODE_KEYWORDS = {
        "direct": ["write", "create", "generate", "make", "implement", "code", "script", "function", "class", "program", "app", "application", "build a tool", "build an app", "build a script"],
        "phrases": ["write code", "write a function", "write a script", "write a program", "create a function", "create a class", "generate code", "generate a function", "implement this", "implement a", "how do i code", "how to code"],
        "negative": ["review", "explain", "understand", "plan", "design"],
    }
    REVIEW_KEYWORDS = {
        "direct": ["review", "analyze", "audit", "assess", "critique", "inspect", "examine", "evaluate", "refactor", "clean"],
        "phrases": ["code review", "review code", "review this", "look over", "best practices", "code smells", "is this good", "how to improve", "make better", "what's wrong with"],
        "negative": ["build", "create", "write", "generate", "new"],
    }
    BUILD_KEYWORDS = {
        "direct": ["plan", "design", "architecture", "outline", "blueprint", "roadmap", "strategy", "specification", "spec"],
        "phrases": ["how to build", "how to implement", "build plan", "implementation plan", "step by step", "step-by-step", "approach to", "design the", "architecture for", "plan the", "plan out", "design for"],
        "negative": ["run", "execute", "test", "debug", "fix"],
    }
    EXECUTE_KEYWORDS = {
        "direct": ["run", "execute", "test", "start", "launch", "invoke", "trigger", "compile", "deploy", "install"],
        "phrases": ["run the tests", "run tests", "run it", "execute this", "test the code", "test this", "run the code", "start the app", "launch the", "how to run", "how to execute", "how to test"],
        "negative": ["plan", "design", "write", "create", "review"],
    }
    SEARCH_KEYWORDS = {
        "direct": ["search", "grep", "locate", "where", "query", "scan", "browse", "list", "show"],
        "phrases": ["find file", "find where", "find all", "find the", "search for", "grep for", "where is", "where are", "show me where", "locate the", "look for", "look up"],
        "negative": ["create", "build", "write", "generate", "execute"],
    }
    VISION_KEYWORDS = {
        "direct": ["screen", "screenshot", "capture", "image", "picture", "photo", "visual", "look at", "see", "ocr", "read this"],
        "phrases": ["what's on my screen", "what is on my screen", "describe the screen", "analyze the screen", "capture screen", "take a screenshot", "what do you see", "read the screen", "extract text from", "detect errors on screen"],
        "negative": ["code", "write", "build", "create"],
    }
    SECURITY_KEYWORDS = {
        "direct": ["security", "secure", "audit", "scan", "vulnerability", "pentest", "cve", "exploit", "password", "secret", "token", "key", "leak", "sanitize", "escape", "inject", "xss", "csrf", "ssl", "tls", "auth", "encrypt", "hash", "salt"],
        "phrases": ["security audit", "scan for vulnerabilities", "check for secrets", "security review", "penetration test", "security scan", "audit code", "check permissions", "find vulnerabilities", "security check", "audit dependencies", "check for leaks", "secure this code"],
        "negative": ["feature", "build", "create", "write", "design"],
    }
    BROWSE_KEYWORDS = {
        "direct": ["browse", "web", "website", "site", "page", "url", "internet", "online", "click", "scroll", "navigate", "surf", "visit", "open link", "check site"],
        "phrases": ["go to website", "open this url", "browse to", "visit website", "check this site", "look at this page", "web page", "screenshot of", "what's on this website", "extract from page", "scrape this"],
        "negative": ["code", "write", "build", "create", "local"],
    }

    # Multi-model auto-routing: which model handles which intent best
    INTENT_TO_MODEL = {
        Intent.CODE: "model",           # primary model (qwen3) — reasoning, coding
        Intent.DEBUG: "model",          # primary model
        Intent.BUILD: "model",          # primary model
        Intent.REVIEW: "secondary_model",  # dolphin — creative conversation
        Intent.SECURITY: "model",       # primary model
        Intent.SEARCH: "model",         # primary model
        Intent.EXECUTE: "model",        # primary model
        Intent.VISION: "vision_model",  # llava — image analysis
        Intent.BROWSE: "model",         # primary model
        Intent.CHAT: "secondary_model",    # dolphin — conversation
        Intent.HELP: "secondary_model",    # dolphin — helpful responses
    }

    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.model = self.config.get("model", "qwen3:8b-gpu")
        self.vision_model = self.config.get("vision_model", "llava:13b-gpu")
        self.secondary_model = self.config.get("secondary_model", "dolphin-llama3:8b-gpu")
        self.project_root = self.config.get("project_root", ".")
        self.unified_mode = self.config.get("unified_mode", False)
        self.autonomous_enabled = self.config.get("autonomous_enabled", True)
        self.voice = VoiceEngine(self.config.get("whisper_size", "medium.en"))
        self.ollama = OllamaBridge(self.model)
        self.ollama.set_unified_mode(self.unified_mode)
        self.executor = CodeExecutor(self.project_root)
        self.session = SessionManager()
        self.plan_enabled = True
        self.build_enabled = True
        self._autonomous_producer = None
        self._codebase_indexer = None
        self._mcp_client = None
        self._long_term_memory = None
        self._conversation_manager = None
        self._init_mcp()
        self._init_long_term_memory()
        self._init_conversation_manager()
        self._check()
        logger.info("CrackedCodeEngine initialized")

    @property
    def codebase_indexer(self) -> Optional[CodebaseIndexer]:
        """Get or create the codebase indexer for semantic search."""
        if not _rag_available:
            return None
        if self._codebase_indexer is None:
            try:
                self._codebase_indexer = get_codebase_indexer(
                    self.project_root,
                    ollama_host=self.config.get("ollama_host", "http://localhost:11434"),
                    model=self.model,
                )
            except Exception as e:
                logger.warning(f"Failed to create codebase indexer: {e}")
        return self._codebase_indexer

    @property
    def mcp_client(self):
        """Get the MCP client for external tool connections."""
        return self._mcp_client

    def _init_mcp(self):
        """Initialize MCP client and connect configured servers."""
        try:
            from src.mcp_client import MCPConfigManager, get_mcp_client
            
            self._mcp_client = get_mcp_client()
            config_manager = MCPConfigManager()
            
            configs = config_manager.load_all()
            connected = 0
            for config in configs:
                if self._mcp_client.add_server(config):
                    connected += 1
            
            if connected > 0:
                # Sync MCP tools into tool registry
                from src.tool_framework import get_tool_registry
                registry = get_tool_registry()
                synced = registry.sync_mcp_tools(self._mcp_client)
                logger.info(f"MCP initialized: {connected} servers, {synced} tools synced")
            else:
                logger.info("MCP: No servers configured or enabled")
        except Exception as e:
            logger.warning(f"MCP initialization failed: {e}")
            self._mcp_client = None

    def _init_long_term_memory(self):
        """Initialize long-term memory for persistent agent experiences."""
        try:
            from src.long_term_memory import get_long_term_memory
            self._long_term_memory = get_long_term_memory(
                storage_path=Path(self.project_root) / ".crackedcode" / "memory",
                model=self.model,
            )
            stats = self._long_term_memory.get_stats()
            logger.info(f"Long-term memory initialized: {stats['total_memories']} memories")
        except Exception as e:
            logger.warning(f"Long-term memory initialization failed: {e}")
            self._long_term_memory = None

    @property
    def long_term_memory(self):
        """Get the long-term memory instance."""
        return self._long_term_memory

    def _init_conversation_manager(self):
        """Initialize conversation manager for persistent chat history."""
        try:
            from src.conversation_manager import get_conversation_manager
            self._conversation_manager = get_conversation_manager(
                db_path=str(Path(self.project_root) / ".crackedcode" / "conversations.db")
            )
            stats = self._conversation_manager.get_stats()
            logger.info(f"Conversation manager initialized: {stats['total_conversations']} conversations")
        except Exception as e:
            logger.warning(f"Conversation manager initialization failed: {e}")
            self._conversation_manager = None

    @property
    def conversation_manager(self):
        """Get the conversation manager instance."""
        return self._conversation_manager

    def _check(self):
        status = self.ollama.detect()
        logger.info(f"Ollama: {status['available']}, Models: {status['models']}")

    def set_unified_mode(self, enabled: bool = True):
        self.unified_mode = enabled
        self.ollama.set_unified_mode(enabled)
        logger.info(f"Unified mode: {'ENABLED' if enabled else 'DISABLED'}")

    def get_status(self) -> Dict:
        ollama = self.ollama.detect()
        cache_stats = self.ollama.get_cache_stats()
        
        mcp_status = {"enabled": False, "servers": 0, "tools": 0}
        if self._mcp_client:
            try:
                mcp_status = {
                    "enabled": True,
                    "servers": len(self._mcp_client.list_servers()),
                    "tools": len(self._mcp_client.list_tools()),
                }
            except Exception:
                pass
        
        return {
            "version": "2.7.0",
            "model": self.model,
            "vision_model": self.vision_model,
            "secondary_model": self.secondary_model,
            "unified_mode": self.unified_mode,
            "plan": self.plan_enabled,
            "build": self.build_enabled,
            "ollama_available": ollama["available"],
            "ollama_models": ollama["models"],
            "history_length": self.session.history_len(),
            "model_roles": self.ollama.models,
            "cache_size": cache_stats["size"],
            "context_length": cache_stats["context_length"],
            "mcp": mcp_status,
        }

    def _select_model_for_intent(self, intent: Intent) -> str:
        """Select the optimal model for a given intent.
        
        Returns the model name to use. Falls back to primary model
        if the preferred model is not available.
        """
        model_key = self.INTENT_TO_MODEL.get(intent, "model")
        
        if model_key == "vision_model":
            preferred = self.vision_model
        elif model_key == "secondary_model":
            preferred = self.secondary_model
        else:
            preferred = self.model
        
        # Check if preferred model is available
        available = self.ollama.available_models
        if preferred in available:
            return preferred
        
        # Fallback chain: preferred → primary → any available → default
        if self.model in available:
            return self.model
        if available:
            return available[0]
        
        return preferred  # Last resort, will likely fail but preserves intent

    def parse_intent(self, prompt: str, confidence_threshold: float = 0.3) -> PromptRequest:
        """Parse user intent from prompt with robust multi-layer matching."""
        text = prompt.lower().strip()
        words = re.findall(r'\b\w+\b', text)
        word_set = set(words)
        
        keyword_sets = {
            Intent.DEBUG: self.DEBUG_KEYWORDS,
            Intent.CODE: self.CODE_KEYWORDS,
            Intent.REVIEW: self.REVIEW_KEYWORDS,
            Intent.BUILD: self.BUILD_KEYWORDS,
            Intent.EXECUTE: self.EXECUTE_KEYWORDS,
            Intent.SEARCH: self.SEARCH_KEYWORDS,
            Intent.VISION: self.VISION_KEYWORDS,
            Intent.SECURITY: self.SECURITY_KEYWORDS,
            Intent.BROWSE: self.BROWSE_KEYWORDS,
        }
        
        intent_scores = {}
        
        for intent, keywords in keyword_sets.items():
            score = 0
            
            for kw in keywords["direct"]:
                if " " in kw:
                    if kw in text:
                        score += 3
                else:
                    if kw in word_set:
                        score += 2
            
            for phrase in keywords["phrases"]:
                if phrase in text:
                    score += 4
            
            for neg in keywords["negative"]:
                if " " in neg:
                    if neg in text:
                        score -= 2
                else:
                    if neg in word_set:
                        score -= 1
            
            intent_scores[intent] = max(score, 0)
        
        intent_scores[Intent.CHAT] = 0
        
        max_score = max(intent_scores.values())
        top_intents = [i for i, s in intent_scores.items() if s == max_score]
        
        tiebreaker_priority = [
            Intent.SECURITY,
            Intent.VISION,
            Intent.DEBUG,
            Intent.EXECUTE,
            Intent.SEARCH,
            Intent.REVIEW,
            Intent.BUILD,
            Intent.CODE,
            Intent.CHAT,
        ]
        
        reasoning_log = []
        
        # Step 1: Score analysis
        score_analysis = "Intent scoring analysis: " + ", ".join(
            f"{k.value}={v}" for k, v in intent_scores.items() if v > 0
        )
        reasoning_log.append({"type": "analysis", "content": score_analysis, "confidence": 0.7})
        
        if max_score >= 2:
            reasoning_log.append({"type": "analysis", "content": f"High confidence signals detected (max_score={max_score})", "confidence": 0.8})
            if len(top_intents) > 1:
                tie_reasoning = f"Tie detected between: {[i.value for i in top_intents]}. Applying tiebreaker priority."
                reasoning_log.append({"type": "analysis", "content": tie_reasoning, "confidence": 0.7})
                for p in tiebreaker_priority:
                    if p in top_intents:
                        intent = p
                        reasoning_log.append({"type": "decision", "content": f"Selected {p.value} via tiebreaker (higher priority in tiebreaker list)", "confidence": 0.75})
                        break
                else:
                    intent = top_intents[0]
                    reasoning_log.append({"type": "decision", "content": f"Selected {intent.value} as first in tie list", "confidence": 0.6})
            else:
                intent = top_intents[0]
                reasoning_log.append({"type": "decision", "content": f"Clear winner: {intent.value} (score={max_score}, no ties)", "confidence": 0.9})
        elif max_score == 1:
            intent = Intent.CHAT
            reasoning_log.append({"type": "decision", "content": "Weak signal detected (max_score=1), defaulting to CHAT for safety", "confidence": 0.5})
        else:
            reasoning_log.append({"type": "analysis", "content": "No keyword matches found. Analyzing sentence structure.", "confidence": 0.5})
            
            has_question = any(text.startswith(q) for q in ["how ", "what ", "why ", "can ", "is ", "are ", "do ", "does ", "when ", "where "])
            has_command = any(text.startswith(c) for c in ["run ", "start ", "open ", "show ", "list ", "get ", "set "])
            
            if has_command or "code" in word_set or "function" in word_set or "file" in word_set:
                intent = Intent.CODE
                reasoning_log.append({"type": "inference", "content": "Detected command structure or code reference, inferring CODE intent", "confidence": 0.6})
            elif has_question:
                reasoning_log.append({"type": "observation", "content": f"Question detected. Analyzing question words: {[w for w in ['debug', 'error', 'bug', 'fail', 'broken', 'review', 'better', 'improve', 'optimize', 'plan', 'design', 'architect', 'build', 'start', 'run', 'execute', 'test', 'install'] if w in word_set]}", "confidence": 0.5})
                if any(w in word_set for w in ["debug", "error", "bug", "fail", "broken"]):
                    intent = Intent.DEBUG
                    reasoning_log.append({"type": "decision", "content": "Question contains debug/error terms -> DEBUG intent", "confidence": 0.65})
                elif any(w in word_set for w in ["review", "better", "improve", "optimize"]):
                    intent = Intent.REVIEW
                    reasoning_log.append({"type": "decision", "content": "Question contains review/improve terms -> REVIEW intent", "confidence": 0.65})
                elif any(w in word_set for w in ["plan", "design", "architect", "build", "start"]):
                    intent = Intent.BUILD
                    reasoning_log.append({"type": "decision", "content": "Question contains plan/design terms -> BUILD intent", "confidence": 0.65})
                elif any(w in word_set for w in ["run", "execute", "test", "install"]):
                    intent = Intent.EXECUTE
                    reasoning_log.append({"type": "decision", "content": "Question contains run/execute terms -> EXECUTE intent", "confidence": 0.65})
                else:
                    intent = Intent.CHAT
                    reasoning_log.append({"type": "decision", "content": "Generic question with no specific coding terms -> CHAT intent", "confidence": 0.5})
            else:
                intent = Intent.CHAT
                reasoning_log.append({"type": "decision", "content": "No recognizable patterns -> default CHAT intent", "confidence": 0.4})
        
        total_possible = 20
        confidence = min(max_score / total_possible, 1.0)
        
        # Final reasoning summary
        reasoning_log.append({"type": "reflection", "content": f"Final intent: {intent.value} (confidence={confidence:.2f})", "confidence": confidence})
        
        context = {
            "keyword_matches": {k.value: v for k, v in intent_scores.items()},
            "confidence": round(confidence, 2),
            "word_count": len(words),
            "is_question": text.endswith("?") or any(text.startswith(q) for q in ["how ", "what ", "why ", "can "]),
            "has_code_reference": any(w in word_set for w in ["code", "function", "class", "file", "method", "module"]),
        }
        
        request = PromptRequest(
            text=prompt,
            intent=intent,
            context=context,
            timestamp=datetime.now()
        )
        request.reasoning_log = reasoning_log
        return request

    def _extract_code_from_response(self, text: str) -> tuple[str, str]:
        """Extract code from response text, handling code blocks."""
        import re
        
        code_block_pattern = r'```[\w]*\n(.*?)```'
        matches = re.findall(code_block_pattern, text, re.DOTALL)
        
        if matches:
            code = matches[0].strip()
            file_match = re.search(r'([\w_]+\.py)', text)
            filename = file_match.group(1) if file_match else "generated.py"
            return code, filename
        
        lines = text.split('\n')
        code_lines = []
        in_code = False
        
        for line in lines:
            if line.strip().startswith('```'):
                in_code = not in_code
                continue
            if in_code or not line.strip().startswith('#') and not line.strip().startswith('//'):
                if line.strip() and not any(line.strip().startswith(p) for p in ['import ', 'from ', 'def ', 'class ', 'if ', 'else:', 'elif ', 'for ', 'while ', 'return ', 'try:', 'except ', 'with ', 'print(']):
                    pass
                code_lines.append(line)
        
        code = '\n'.join(code_lines).strip()
        
        file_match = re.search(r'[\w_]+\.py', text)
        filename = file_match.group(0) if file_match else "generated.py"
        
        return code if code else text, filename

    def generate_code(self, prompt: str) -> AgentResponse:
        """Generate code and optionally save to file."""
        request = self.parse_intent(prompt)
        
        if request.intent == Intent.CHAT:
            request.intent = Intent.CODE
        
        template = self.PROMPT_TEMPLATES.get(request.intent, "Write Python code.\n\nTask: {prompt}")
        response = self.ollama.chat(template.format(prompt=prompt))
        
        if not response.success:
            return response
        
        code, filename = self._extract_code_from_response(response.text)
        
        response.text = code
        
        return response

    def generate_and_save(self, prompt: str, filepath: str = None) -> AgentResponse:
        """Generate code and save to file."""
        response = self.generate_code(prompt)
        
        if not response.success:
            return response
        
        if filepath is None:
            filepath = self._extract_filename(prompt) or "generated.py"
        
        try:
            filepath = Path(filepath)
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(response.text)
            response.text = f"# Saved to {filepath}\n\n{response.text}"
            logger.info(f"Code saved to {filepath}")
        except Exception as e:
            response.success = False
            response.error = f"Failed to save: {e}"
            logger.error(f"Failed to save code: {e}")
        
        return response

    def _extract_filename(self, prompt: str) -> str:
        """Extract filename from prompt if mentioned."""
        import re
        patterns = [
            r'create\s+(\w+\.py)',
            r'save\s+(?:it\s+)?to\s+(\w+\.py)',
            r'file\s+(\w+\.py)',
            r'named\s+(\w+\.py)',
            r'(?:in|to)\s+(\w+\.py)',
        ]
        for pattern in patterns:
            match = re.search(pattern, prompt.lower())
            if match:
                return match.group(1)
        return None

    async def process(self, prompt: str, streaming: bool = False, callback: Callable = None) -> AgentResponse:
        """Process a user prompt with full intent detection and execution.
        
        Includes complete reasoning chain for:
        - Intent classification decisions
        - Mode/plan checks
        - Execution path selection
        - Model selection
        - Response handling
        """
        # Plugin pre-process hook
        if _plugins_available:
            execute_hook(HookPoint.ENGINE_PRE_PROCESS, prompt)
        
        request = self.parse_intent(prompt)
        
        # Plugin intent parsed hook
        if _plugins_available:
            execute_hook(HookPoint.ENGINE_INTENT_PARSED, request)
        
        # Build execution path reasoning
        execution_reasoning = []
        execution_reasoning.append({"type": "observation", "content": f"Intent detected: {request.intent.value} (confidence: {request.context.get('confidence', 0):.2f})", "confidence": request.context.get('confidence', 0.5)})
        
        # Check plan mode
        if not self.plan_enabled and request.intent != Intent.CHAT:
            execution_reasoning.append({"type": "decision", "content": "Plan mode disabled - rejecting non-chat intent", "confidence": 1.0})
            return AgentResponse(
                success=False,
                text="Plan mode is disabled",
                reasoning_log=execution_reasoning,
                processing_path="plan_disabled_rejection"
            )
        execution_reasoning.append({"type": "observation", "content": "Plan mode enabled", "confidence": 1.0})
        
        # Check build mode
        if not self.build_enabled and request.intent == Intent.BUILD:
            execution_reasoning.append({"type": "analysis", "content": "BUILD mode disabled, falling back to CODE intent", "confidence": 0.8})
            logger.info("BUILD mode disabled, falling back to CODE intent")
            request.intent = Intent.CODE
        
        logger.info(f"Processing: {request.intent.value} (confidence: {request.context.get('confidence', 0):.2f})")
        
        # Route to execution handler with reasoning
        if request.intent == Intent.EXECUTE:
            execution_reasoning.append({"type": "decision", "content": "Routing to CodeExecutor (shell command execution)", "confidence": 0.9})
            cmd = prompt.replace("run ", "").replace("execute ", "").strip()
            response = self.executor.run_shell(cmd)
            response.reasoning_log = execution_reasoning + request.reasoning_log
            response.processing_path = "execute_shell"
            return response
        
        if request.intent == Intent.SEARCH:
            execution_reasoning.append({"type": "decision", "content": "Routing to file search handler", "confidence": 0.9})
            response = self._search_files(prompt)
            response.reasoning_log = execution_reasoning + request.reasoning_log
            response.processing_path = "file_search"
            return response
        
        # Vision processing path
        if request.intent == Intent.VISION:
            execution_reasoning.append({"type": "decision", "content": "Routing to vision analysis handler", "confidence": 0.9})
            try:
                from src.screen_capture import VisionAnalyzer
                analyzer = VisionAnalyzer(engine=self)
                result = analyzer.analyze_screen(prompt=prompt)
                
                if result.get("success"):
                    text = f"**Screen Analysis** (via {result.get('model', 'vision model')})\n\n"
                    text += f"Screenshot: {result.get('width', 0)}x{result.get('height', 0)}\n"
                    if result.get('screenshot_path'):
                        text += f"Saved: {result['screenshot_path']}\n\n"
                    text += f"**Analysis:**\n{result.get('analysis', 'No analysis')}\n"
                    
                    response = AgentResponse(
                        success=True,
                        text=text,
                        execution_time=0.0,
                        processing_path="vision_analysis",
                        model_used=result.get("model", "vision"),
                    )
                else:
                    response = AgentResponse(
                        success=False,
                        text="",
                        error=result.get("error", "Vision analysis failed"),
                        processing_path="vision_analysis",
                    )
            except Exception as e:
                response = AgentResponse(
                    success=False,
                    text="",
                    error=str(e),
                    processing_path="vision_analysis",
                )
            
            response.reasoning_log = execution_reasoning + request.reasoning_log
            return response
        
        # Security processing path
        if request.intent == Intent.SECURITY:
            execution_reasoning.append({"type": "decision", "content": "Routing to security analysis handler", "confidence": 0.9})
            try:
                from src.tool_framework import get_tool_registry
                registry = get_tool_registry()
                
                security_results = []
                
                # Run security tools
                tools_to_run = [
                    ("audit_secrets", {}),
                    ("check_permissions", {}),
                    ("analyze_vulnerabilities", {}),
                ]
                
                # Check if requirements.txt exists for dependency scan
                req_path = Path(self.project_root) / "requirements.txt"
                if req_path.exists():
                    tools_to_run.append(("scan_dependencies", {"requirements_path": str(req_path)}))
                
                for tool_name, params in tools_to_run:
                    try:
                        result = registry.execute(tool_name, **params)
                        if result.success and result.result:
                            security_results.append({"tool": tool_name, "result": result.result})
                    except Exception as e:
                        security_results.append({"tool": tool_name, "error": str(e)})
                
                # Build security report
                report_lines = ["**Security Analysis Report**\n"]
                total_issues = 0
                
                for item in security_results:
                    tool_name = item["tool"]
                    result = item.get("result", {})
                    
                    if "error" in item:
                        report_lines.append(f"\n*{tool_name}*: Error - {item['error']}")
                        continue
                    
                    if result.get("success"):
                        findings = result.get("findings", result.get("vulnerabilities", result.get("issues", [])))
                        count = result.get("secrets_found", result.get("vulnerabilities_found", result.get("issues_found", 0)))
                        total_issues += count
                        
                        report_lines.append(f"\n*{tool_name}*: {count} issues found")
                        for finding in findings[:10]:  # Limit to 10 per tool
                            if isinstance(finding, dict):
                                preview = finding.get("preview", finding.get("type", str(finding)))
                                file_info = finding.get("file", "")
                                line_info = f":{finding.get('line', '')}" if finding.get('line') else ""
                                report_lines.append(f"  - {file_info}{line_info}: {preview}")
                            else:
                                report_lines.append(f"  - {finding}")
                
                report_lines.append(f"\n**Total Issues Found: {total_issues}**")
                
                # Also get LLM analysis with security context
                template = self.PROMPT_TEMPLATES.get(Intent.SECURITY, "{prompt}")
                formatted_prompt = template.format(prompt=request.text)
                
                # Prepend security scan results
                security_context = "\n".join(report_lines)
                full_prompt = f"{security_context}\n\n{formatted_prompt}"
                
                response = self.ollama.chat(full_prompt)
                response.processing_path = "security_analysis"
                response.model_used = self.model
                
            except Exception as e:
                response = AgentResponse(
                    success=False,
                    text="",
                    error=str(e),
                    processing_path="security_analysis",
                )
            
            response.reasoning_log = execution_reasoning + request.reasoning_log
            return response
        
        # Browser processing path
        if request.intent == Intent.BROWSE:
            execution_reasoning.append({"type": "decision", "content": "Routing to browser automation handler", "confidence": 0.9})
            try:
                from src.browser_agent import get_browser_agent
                from src.tool_framework import get_tool_registry
                
                # Extract URL from prompt using simple regex
                import re
                url_match = re.search(r'https?://[^\s<>"{}|\\^`\[\]]+', request.text)
                url = url_match.group(0) if url_match else None
                
                if not url:
                    response = AgentResponse(
                        success=False,
                        text="",
                        error="No URL found in prompt. Please include a valid URL (e.g., https://example.com)",
                        processing_path="browser_automation",
                    )
                else:
                    agent = get_browser_agent(headless=True)
                    nav_result = agent.navigate(url)
                    
                    if not nav_result.success:
                        response = AgentResponse(
                            success=False,
                            text="",
                            error=f"Failed to navigate to {url}: {nav_result.error}",
                            processing_path="browser_automation",
                        )
                    else:
                        # Extract page text
                        text_result = agent.get_text()
                        content = text_result.content[:4000] if text_result.content else ""
                        
                        # Take screenshot
                        screenshot_result = agent.screenshot()
                        
                        agent.close()
                        
                        # Build response
                        report = f"**Browser Analysis: {nav_result.title}**\n"
                        report += f"URL: {nav_result.url}\n\n"
                        report += f"**Page Content (excerpt):**\n{content[:2000]}...\n\n"
                        if screenshot_result.screenshot:
                            report += f"Screenshot captured: {len(screenshot_result.screenshot)} bytes\n"
                        
                        # Ask LLM to analyze
                        template = self.PROMPT_TEMPLATES.get(Intent.BROWSE, "{prompt}")
                        formatted = template.format(prompt=request.text, url=nav_result.url, content=content[:3000])
                        llm_response = self.ollama.chat(formatted)
                        
                        if llm_response.success:
                            report += f"\n**AI Analysis:**\n{llm_response.text}"
                        
                        response = AgentResponse(
                            success=True,
                            text=report,
                            execution_time=0.0,
                            processing_path="browser_automation",
                            model_used=self.model,
                        )
            except Exception as e:
                response = AgentResponse(
                    success=False,
                    text="",
                    error=str(e),
                    processing_path="browser_automation",
                )
            
            response.reasoning_log = execution_reasoning + request.reasoning_log
            return response
        
        # LLM processing path with codebase context for relevant intents
        template = self.PROMPT_TEMPLATES.get(request.intent, "{prompt}")
        
        # Inject semantic context for code-related intents
        context_block = ""
        if request.intent in (Intent.CODE, Intent.DEBUG, Intent.REVIEW, Intent.BUILD, Intent.SECURITY):
            context_block = self.get_codebase_context(request.text, top_k=3)
            if context_block:
                execution_reasoning.append({"type": "observation", "content": f"Retrieved {len(context_block)} chars of codebase context via semantic search", "confidence": 0.85})
        
        # Inject long-term memory context
        memory_block = ""
        if self._long_term_memory:
            try:
                memory_block = self._long_term_memory.get_context_for_prompt(request.text, top_k=3)
                if memory_block:
                    execution_reasoning.append({"type": "observation", "content": "Retrieved relevant past experiences from long-term memory", "confidence": 0.75})
            except Exception as e:
                logger.warning(f"Memory retrieval failed: {e}")
        
        formatted_prompt = template.format(prompt=request.text)
        if context_block:
            formatted_prompt = context_block + "\n\n" + formatted_prompt
        if memory_block:
            formatted_prompt = memory_block + "\n" + formatted_prompt
        
        # Model selection reasoning
        selected_model = self._select_model_for_intent(request.intent)
        
        if self.unified_mode:
            execution_reasoning.append({"type": "decision", "content": "Using unified mode (multi-model ensemble)", "confidence": 0.8})
            response = self.ollama.unified_chat(formatted_prompt)
            response.model_used = "unified_ensemble"
            response.processing_path = "unified_chat"
        elif streaming and callback:
            execution_reasoning.append({"type": "decision", "content": f"Using streaming mode with {selected_model} (intent: {request.intent.value})", "confidence": 0.9})
            response = self.ollama.chat_stream(formatted_prompt, model=selected_model, callback=callback)
            response.model_used = selected_model
            response.processing_path = "stream_chat"
        else:
            execution_reasoning.append({"type": "decision", "content": f"Using standard chat with {selected_model} (intent: {request.intent.value})", "confidence": 0.9})
            response = self.ollama.chat(formatted_prompt, model=selected_model)
            response.model_used = selected_model
            response.processing_path = "standard_chat"
        
        # Combine reasoning logs
        response.reasoning_log = execution_reasoning + request.reasoning_log
        
        if response.success:
            execution_reasoning.append({"type": "reflection", "content": f"LLM responded successfully via {response.processing_path}", "confidence": 0.9})
            self.session.add_turn(request, response)
            
            # Store in conversation manager
            if self._conversation_manager:
                try:
                    self._conversation_manager.add_turn(
                        user_message=request.text,
                        assistant_response=response.text,
                        intent=request.intent.value,
                        model_used=response.model_used,
                        execution_time=response.execution_time,
                    )
                except Exception as e:
                    logger.warning(f"Failed to store conversation: {e}")
            
            # Store in long-term memory
            if self._long_term_memory:
                try:
                    self._long_term_memory.remember(
                        content=f"User: {request.text}\nAssistant: {response.text[:500]}",
                        memory_type="conversation",
                        tags=[request.intent.value, "auto"],
                        source="engine.process",
                        confidence=0.7,
                    )
                except Exception as e:
                    logger.warning(f"Failed to store memory: {e}")
        else:
            execution_reasoning.append({"type": "correction", "content": f"LLM failed: {response.error}", "confidence": 0.3})
            
            # Store error in conversation manager
            if self._conversation_manager:
                try:
                    self._conversation_manager.add_turn(
                        user_message=request.text,
                        assistant_response=f"[ERROR] {response.error}",
                        intent=request.intent.value,
                        model_used=response.model_used or "",
                        execution_time=response.execution_time,
                    )
                except Exception as e:
                    logger.warning(f"Failed to store error conversation: {e}")
            
            # Store error in long-term memory
            if self._long_term_memory:
                try:
                    self._long_term_memory.remember(
                        content=f"Error in {request.intent.value}: {response.error}",
                        memory_type="error",
                        tags=[request.intent.value, "error", "auto"],
                        source="engine.process",
                        confidence=0.8,
                    )
                except Exception as e:
                    logger.warning(f"Failed to store error memory: {e}")
        
        # Plugin post-process hook
        if _plugins_available:
            execute_hook(HookPoint.ENGINE_POST_PROCESS, response)
        
        return response
    
    def process_with_tools(self, prompt: str, max_iterations: int = 5) -> AgentResponse:
        """Process a prompt using the ReAct tool-calling framework.
        
        The agent reasons step-by-step, choosing tools to gather information
        and complete the task.
        
        Args:
            prompt: The task description
            max_iterations: Max ReAct iterations
            
        Returns:
            AgentResponse with final answer
        """
        if not _tools_available:
            return AgentResponse(success=False, text="", error="Tool framework not available")
        
        start = time.time()
        
        def llm_callback(prompt_text: str) -> str:
            """Internal LLM callback for ReAct loop."""
            response = self.ollama.chat(prompt_text, system="You are a coding agent. Use tools to accomplish tasks. Respond ONLY in JSON format.")
            return response.text if response.success else '{"thought": "LLM failed", "action": "finish", "answer": "Error: LLM unavailable"}'
        
        try:
            react = ReActLoop(agent_id="engine_react", max_iterations=max_iterations)
            result = react.run(
                task_description=prompt,
                llm_callback=llm_callback,
            )
            
            if result.get("success"):
                answer = result.get("final_answer", "Task completed")
                tool_calls = result.get("tool_calls", [])
                
                text = f"**ReAct Result** ({result['iterations']} iterations, {len(tool_calls)} tool calls)\n\n"
                text += f"**Answer:**\n{answer}\n\n"
                
                if tool_calls:
                    text += "**Tool Calls:**\n"
                    for tc in tool_calls:
                        text += f"- {tc['tool']} → {'success' if tc['success'] else 'failed'}: {tc['observation'][:80]}...\n"
                
                return AgentResponse(
                    success=True,
                    text=text,
                    execution_time=time.time() - start,
                    processing_path="react_tool_loop",
                )
            else:
                return AgentResponse(
                    success=False,
                    text="",
                    error=result.get("error", "ReAct loop failed"),
                    execution_time=time.time() - start,
                    processing_path="react_tool_loop",
                )
        except Exception as e:
            logger.error(f"process_with_tools failed: {e}")
            return AgentResponse(success=False, text="", error=str(e), processing_path="react_tool_loop")
    
    def _search_files(self, prompt: str) -> AgentResponse:
        """Search for files or content using semantic search (RAG) with keyword fallback."""
        search_terms = prompt.lower().replace("search ", "").replace("find ", "").replace("grep ", "").strip()
        
        # Try semantic search first
        if self.codebase_indexer:
            try:
                rag_results = self.codebase_indexer.search(search_terms, top_k=5)
                if rag_results:
                    lines = [f"Semantic Search Results for '{search_terms}':\n"]
                    for r in rag_results:
                        chunk = r.chunk
                        name = chunk.metadata.get("name", "")
                        type_label = f" [{chunk.chunk_type}: {name}]" if name else f" [{chunk.chunk_type}]"
                        lines.append(f"\n=== {chunk.file_path}{type_label} (relevance: {r.score:.2f}) ===")
                        lines.append(f"Lines {chunk.start_line}-{chunk.end_line} | {chunk.language}")
                        lines.append("```")
                        lines.append(chunk.content[:800])
                        lines.append("```")
                        if r.reasoning:
                            lines.append(f"Why: {r.reasoning}")
                    return AgentResponse(success=True, text="\n".join(lines))
            except Exception as e:
                logger.warning(f"Semantic search failed, falling back to keyword: {e}")
        
        # Keyword fallback
        results = []
        search_path = Path(self.project_root)
        
        for pattern in ["*.py", "*.json", "*.txt", "*.md", "*.yaml", "*.yml", "*.toml"]:
            for file in search_path.rglob(pattern):
                if self._should_ignore(file):
                    continue
                
                try:
                    content = file.read_text(errors='ignore')
                    if search_terms in content.lower():
                        lines = content.split('\n')
                        matching_lines = [f"{i+1}: {line}" for i, line in enumerate(lines) if search_terms in line.lower()]
                        results.append(f"=== {file.relative_to(search_path)} ===")
                        results.extend(matching_lines[:10])
                except Exception as e:
                    logger.debug(f"Search skip {file}: {e}")
                    continue
        
        if results:
            return AgentResponse(success=True, text=f"Keyword Search Results for '{search_terms}':\n\n" + "\n".join(results))
        else:
            return AgentResponse(success=True, text=f"No results found for '{search_terms}'")

    def get_codebase_context(self, query: str, top_k: int = 3) -> str:
        """Get semantic context from the codebase for LLM prompting."""
        if not self.codebase_indexer:
            return ""
        try:
            return self.codebase_indexer.get_context_for_prompt(query, top_k=top_k)
        except Exception as e:
            logger.debug(f"Codebase context retrieval failed: {e}")
            return ""
    
    def _should_ignore(self, path: Path) -> bool:
        """Check if a path should be ignored in searches."""
        ignore_dirs = {".git", "__pycache__", ".venv", "venv", "node_modules", ".idea", ".vscode", ".pytest_cache", "logs", ".env"}
        ignore_patterns = {".pyc", ".pyo", ".so", ".dll", ".dylib"}
        
        for part in path.parts:
            if part in ignore_dirs:
                return True
        
        if path.suffix in ignore_patterns:
            return True
        
        return False
    
    def validate_code(self, code: str) -> Dict:
        """Validate generated code for syntax and basic issues."""
        import ast
        import re
        
        result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "line_count": len(code.split('\n')),
        }
        
        try:
            ast.parse(code)
        except SyntaxError as e:
            result["valid"] = False
            result["errors"].append(f"Syntax error at line {e.lineno}: {e.msg}")
        
        if "import " not in code and "from " not in code:
            result["warnings"].append("No imports found - code may be incomplete")
        
        if "def " not in code and "class " not in code:
            result["warnings"].append("No functions or classes found")
        
        if not code.strip().endswith('\n'):
            result["warnings"].append("File does not end with newline")
        
        if len(code) > 10000:
            result["warnings"].append("Code exceeds 10000 characters - consider splitting")
        
        for i, line in enumerate(code.split('\n'), 1):
            if len(line) > 120:
                result["warnings"].append(f"Line {i} exceeds 120 characters")
        
        return result
    
    def execute_generated_code(self, code: str, timeout: int = 30) -> AgentResponse:
        """Execute generated code in a sandboxed environment."""
        import tempfile
        import ast
        
        validation = self.validate_code(code)
        
        if not validation["valid"]:
            return AgentResponse(
                success=False, 
                error=f"Code validation failed: {validation['errors'][0]}"
            )
        
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_path = f.name
            
            result = subprocess.run(
                [sys.executable, temp_path],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.project_root
            )
            
            os.unlink(temp_path)
            
            output = result.stdout
            if result.stderr:
                output += f"\n--- STDERR ---\n{result.stderr}"
            
            return AgentResponse(
                success=result.returncode == 0,
                text=output,
                execution_time=0.0
            )
            
        except subprocess.TimeoutExpired:
            return AgentResponse(success=False, error=f"Execution timed out after {timeout}s")
        except Exception as e:
            return AgentResponse(success=False, error=str(e))
    
    def get_code_stats(self, code: str) -> Dict:
        """Get statistics about generated code."""
        import ast
        
        lines = code.split('\n')
        
        stats = {
            "total_lines": len(lines),
            "code_lines": len([l for l in lines if l.strip() and not l.strip().startswith('#')]),
            "comment_lines": len([l for l in lines if l.strip().startswith('#')]),
            "blank_lines": len([l for l in lines if not l.strip()]),
            "functions": 0,
            "classes": 0,
            "imports": 0,
        }
        
        try:
            tree = ast.parse(code)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    stats["functions"] += 1
                elif isinstance(node, ast.ClassDef):
                    stats["classes"] += 1
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    stats["imports"] += 1
                    
        except SyntaxError:
            pass
        
        return stats

    @property
    def autonomous_producer(self):
        if self._autonomous_producer is None and self.autonomous_enabled:
            from src.autonomous import AutonomousAppProducer
            self._autonomous_producer = AutonomousAppProducer(
                engine=self,
                workspace_path=str(Path(self.project_root) / ".autonomous")
            )
        return self._autonomous_producer

    def autonomous_produce(self, spec: str, project_name: str = None, architecture: str = None,
                          output_dir: str = None, progress_callback: Callable = None,
                          phase_callback: Callable = None) -> Any:
        """Autonomously produce a complete application from specification.
        
        OpenClaw-style autonomous agent that handles the full development cycle:
        1. Analyze requirements
        2. Design architecture (auto-selects or uses specified pattern)
        3. Create project scaffold
        4. Generate all code files
        5. Write and run tests
        6. Self-correct test failures
        7. Generate documentation and deliver
        
        Args:
            spec: High-level specification (natural language)
            project_name: Project name (auto-generated from spec if not provided)
            architecture: Architecture pattern - mvc, clean, layered, cli, web_api, desktop_gui, microservices
            output_dir: Output directory (defaults to ./projects/{project_name})
            progress_callback: Callback(message: str, progress: float) for progress updates
            phase_callback: Callback(phase: Phase, message: str) for phase transitions
            
        Returns:
            AutonomousResult with production details
        """
        if not self.autonomous_enabled:
            return AgentResponse(success=False, error="Autonomous mode is disabled")
        
        producer = self.autonomous_producer
        if progress_callback:
            producer.set_progress_callback(progress_callback)
        if phase_callback:
            producer.set_phase_callback(phase_callback)
        
        arch_enum = None
        if architecture:
            from src.autonomous import ArchitecturePattern
            try:
                arch_enum = ArchitecturePattern(architecture.lower())
            except ValueError:
                pass
        
        result = producer.produce(
            spec=spec,
            project_name=project_name,
            architecture=arch_enum,
            output_dir=output_dir,
        )
        
        return result

    def get_autonomous_status(self) -> Dict:
        """Get autonomous producer status."""
        if self._autonomous_producer is None:
            return {"available": False, "enabled": self.autonomous_enabled}
        status = self._autonomous_producer.get_status()
        status["available"] = True
        status["enabled"] = self.autonomous_enabled
        return status

    def get_available_architectures(self) -> List[Dict[str, str]]:
        """Get list of available architecture patterns."""
        from src.autonomous import ARCHITECTURE_TEMPLATES, ArchitecturePattern
        return [
            {"name": p.value, "description": ARCHITECTURE_TEMPLATES[p]["description"]}
            for p in ArchitecturePattern
        ]

    @property
    def orchestrator(self):
        """Get or create the unified orchestrator."""
        from src.orchestrator import get_orchestrator
        return get_orchestrator(engine=self, max_workers=self.config.get("max_concurrent_agents", 4))

    def process_via_orchestrator(self, prompt: str, streaming: bool = False, callback: Callable = None) -> Any:
        """Process a prompt through the unified orchestrator with full task tracking.
        
        Args:
            prompt: User prompt
            streaming: Enable streaming responses
            callback: Streaming callback
            
        Returns:
            Task result with full lifecycle tracking
        """
        orch = self.orchestrator
        
        # Parse intent for agent selection
        request = self.parse_intent(prompt)
        intent = request.intent.value
        
        # Create and submit task
        task = orch.create_task(
            prompt=prompt,
            intent=intent,
            priority=orch.TaskPriority.NORMAL,
            metadata={"streaming": streaming, "callback": callback},
        )
        
        orch.submit(task)
        
        # Wait for completion (synchronous interface)
        while not task.is_terminal:
            import time
            time.sleep(0.1)
        
        return task

    def generate_code_via_orchestrator(self, prompt: str, filepath: str = None) -> Any:
        """Generate code through the orchestrator with task tracking."""
        orch = self.orchestrator
        
        task = orch.create_task(
            prompt=prompt,
            intent="code",
            priority=orch.TaskPriority.HIGH,
            metadata={"filepath": filepath},
        )
        
        orch.submit(task)
        
        while not task.is_terminal:
            import time
            time.sleep(0.1)
        
        return task

    def create_pipeline(self, steps: List[Dict[str, Any]]) -> str:
        """Create a multi-step task pipeline.
        
        Args:
            steps: List of step dicts with keys: prompt, intent, agent, priority
            
        Returns:
            First task ID
        """
        return self.orchestrator.create_pipeline(steps)

    def get_orchestrator_status(self) -> Dict:
        """Get orchestrator queue status."""
        return self.orchestrator.get_queue_status()

    def get_task(self, task_id: str) -> Any:
        """Get a task by ID."""
        return self.orchestrator.get_task(task_id)

    def get_all_tasks(self) -> List[Any]:
        """Get all tasks."""
        return self.orchestrator.get_all_tasks()

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a running or queued task."""
        return self.orchestrator.cancel_task(task_id)


_engine: Optional[CrackedCodeEngine] = None


def get_engine(config: Dict = None) -> CrackedCodeEngine:
    global _engine
    if _engine is None:
        _engine = CrackedCodeEngine(config)
    return _engine