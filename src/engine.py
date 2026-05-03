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


@dataclass
class PromptRequest:
    text: str
    intent: Intent = Intent.CHAT
    context: Dict = field(default_factory=dict)
    user_level: str = "intermediate"
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class AgentResponse:
    success: bool
    text: str = ""
    intent: Intent = Intent.CHAT
    error: Optional[str] = None
    execution_time: float = 0.0


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

    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.model = self.config.get("model", "qwen3:8b-gpu")
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
        self._check()
        logger.info("CrackedCodeEngine initialized")

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
        return {
            "version": "2.6.0",
            "model": self.model,
            "unified_mode": self.unified_mode,
            "plan": self.plan_enabled,
            "build": self.build_enabled,
            "ollama_available": ollama["available"],
            "ollama_models": ollama["models"],
            "history_length": self.session.history_len(),
            "model_roles": self.ollama.models,
            "cache_size": cache_stats["size"],
            "context_length": cache_stats["context_length"],
        }

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
            Intent.DEBUG,
            Intent.EXECUTE,
            Intent.SEARCH,
            Intent.REVIEW,
            Intent.BUILD,
            Intent.CODE,
            Intent.CHAT,
        ]
        
        if max_score >= 2:
            if len(top_intents) > 1:
                for p in tiebreaker_priority:
                    if p in top_intents:
                        intent = p
                        break
                else:
                    intent = top_intents[0]
            else:
                intent = top_intents[0]
        elif max_score == 1:
            intent = Intent.CHAT
        else:
            has_question = any(text.startswith(q) for q in ["how ", "what ", "why ", "can ", "is ", "are ", "do ", "does ", "when ", "where "])
            has_command = any(text.startswith(c) for c in ["run ", "start ", "open ", "show ", "list ", "get ", "set "])
            
            if has_command or "code" in word_set or "function" in word_set or "file" in word_set:
                intent = Intent.CODE
            elif has_question:
                if any(w in word_set for w in ["debug", "error", "bug", "fail", "broken"]):
                    intent = Intent.DEBUG
                elif any(w in word_set for w in ["review", "better", "improve", "optimize"]):
                    intent = Intent.REVIEW
                elif any(w in word_set for w in ["plan", "design", "architect", "build", "start"]):
                    intent = Intent.BUILD
                elif any(w in word_set for w in ["run", "execute", "test", "install"]):
                    intent = Intent.EXECUTE
                else:
                    intent = Intent.CHAT
            else:
                intent = Intent.CHAT
        
        total_possible = 20
        confidence = min(max_score / total_possible, 1.0)
        
        context = {
            "keyword_matches": {k.value: v for k, v in intent_scores.items()},
            "confidence": round(confidence, 2),
            "word_count": len(words),
            "is_question": text.endswith("?") or any(text.startswith(q) for q in ["how ", "what ", "why ", "can "]),
            "has_code_reference": any(w in word_set for w in ["code", "function", "class", "file", "method", "module"]),
        }
        
        return PromptRequest(
            text=prompt,
            intent=intent,
            context=context,
            timestamp=datetime.now()
        )

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
        """Process a user prompt with full intent detection and execution."""
        request = self.parse_intent(prompt)
        
        if not self.plan_enabled and request.intent != Intent.CHAT:
            return AgentResponse(success=False, text="Plan mode is disabled")
        
        if not self.build_enabled and request.intent == Intent.BUILD:
            logger.info("BUILD mode disabled, falling back to CODE intent")
            request.intent = Intent.CODE
        
        logger.info(f"Processing: {request.intent.value} (confidence: {request.context.get('confidence', 0):.2f})")
        
        if request.intent == Intent.EXECUTE:
            cmd = prompt.replace("run ", "").replace("execute ", "").strip()
            return self.executor.run_shell(cmd)
        
        if request.intent == Intent.SEARCH:
            return self._search_files(prompt)
        
        template = self.PROMPT_TEMPLATES.get(request.intent, "{prompt}")
        formatted_prompt = template.format(prompt=request.text)
        
        if self.unified_mode:
            response = self.ollama.unified_chat(formatted_prompt)
        elif streaming and callback:
            response = self.ollama.chat_stream(formatted_prompt, callback=callback)
        else:
            response = self.ollama.chat(formatted_prompt)
        
        if response.success:
            self.session.add_turn(request, response)
        
        return response
    
    def _search_files(self, prompt: str) -> AgentResponse:
        """Search for files or content in the project."""
        search_terms = prompt.lower().replace("search ", "").replace("find ", "").replace("grep ", "").strip()
        
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
            return AgentResponse(success=True, text=f"Search results for '{search_terms}':\n\n" + "\n".join(results))
        else:
            return AgentResponse(success=True, text=f"No results found for '{search_terms}'")
    
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