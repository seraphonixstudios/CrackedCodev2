import sys
import os
import json
import logging
import threading
import hashlib
import time
from pathlib import Path
from typing import Optional, Dict, List, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s'
)
logger = logging.getLogger("CrackedCodeEngine")


class Intent(Enum):
    CHAT = "chat"
    CODE = "code"
    DEBUG = "debug"
    SEARCH = "search"
    REVIEW = "review"
    EXECUTE = "execute"
    BUILD = "build"
    PLAN = "plan"
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
    artifacts: List[str] = field(default_factory=list)
    error: Optional[str] = None
    execution_time: float = 0.0


class VoiceEngine:
    def __init__(self, model: str = "medium.en"):
        self.model = model
        self.whisper = None
        self.lock = threading.Lock()
        logger.info(f"VoiceEngine init: {model}")

    def load(self):
        if self.whisper:
            return True
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
        
        with self.lock:
            try:
                import io
                import wave
                
                buffer = io.BytesIO()
                with wave.open(buffer, 'wb') as f:
                    f.setnchannels(1)
                    f.setsampwidth(2)
                    f.setframerate(16000)
                    f.writeframes(audio_bytes)
                buffer.seek(0)
                
                result = self.whisper.transcribe(buffer)
                text = result[0].strip()
                logger.info(f"Transcribed: {text[:50]}...")
                return text
            except Exception as e:
                logger.error(f"Transcribe failed: {e}")
                return ""


class OllamaBridge:
    def __init__(self, model: str = "qwen3:8b-gpu"):
        self.model = model
        self.ollama = None
        self.client = None
        self.available_models = []
        self.host = "http://localhost:11434"
        self._connected = False
        logger.info(f"OllamaBridge init: {model}")

    def detect(self) -> Dict:
        result = {"available": False, "models": [], "host": self.host, "selected": self.model}
        try:
            import ollama
            self.ollama = ollama
            response = ollama.list()
            result["models"] = [m.model for m in response.models]
            result["available"] = True
            
            if self.model not in result["models"]:
                self.model = result["models"][0] if result["models"] else "qwen3:8b-gpu"
                result["selected"] = self.model
            
            logger.info(f"Ollama detected: {result['models']}")
            self._connected = True
        except Exception as e:
            logger.error(f"Ollama detection failed: {e}")
        return result

    def connect(self) -> bool:
        return self.detect()["available"]

    def chat(self, prompt: str, system: str = "", context: Dict = None) -> AgentResponse:
        if not self.ollama:
            self.connect()
        
        start = time.time()
        try:
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            
            response = self.ollama.chat(
                model=self.model,
                messages=messages,
                options={"temperature": 0.1}
            )
            
            text = response.message.content
            exec_time = time.time() - start
            
            logger.info(f"Ollama response: {text[:50]}... ({exec_time:.2f}s)")
            return AgentResponse(success=True, text=text, execution_time=exec_time)
            
        except Exception as e:
            logger.error(f"Ollama chat failed: {e}")
            return AgentResponse(success=False, error=str(e))


class CodeExecutor:
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.allowed_commands = [
            "python", "pytest", "ruff", "git", "npm", "node", "pip"
        ]
        logger.info(f"CodeExecutor init: {project_root}")

    def execute(self, code: str, mode: str = "exec") -> AgentResponse:
        start = time.time()
        
        if mode == "exec":
            return self.run_code(code, start)
        elif mode == "shell":
            return self.run_shell(code, start)
        elif mode == "test":
            return self.run_tests(code, start)
        
        return AgentResponse(success=False, error=f"Unknown mode: {mode}")

    def run_code(self, code: str, start: float) -> AgentResponse:
        try:
            result = {}
            exec_globals = {"result": result, "__name__": "__main__"}
            exec(code, exec_globals)
            text = str(result.get("output", "Executed"))
            return AgentResponse(success=True, text=text, execution_time=time.time() - start)
        except Exception as e:
            return AgentResponse(success=False, error=str(e))

    def run_shell(self, cmd: str, start: float) -> AgentResponse:
        import subprocess
        
        parts = cmd.strip().split()
        if not parts or parts[0] not in self.allowed_commands:
            return AgentResponse(success=False, error=f"Command not allowed: {parts[0] if parts else 'none'}")
        
        try:
            result = subprocess.run(
                cmd, shell=True,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=self.project_root
            )
            text = result.stdout or result.stderr
            return AgentResponse(
                success=result.returncode == 0,
                text=text,
                error=str(result.stderr) if result.returncode else None,
                execution_time=time.time() - start
            )
        except Exception as e:
            return AgentResponse(success=False, error=str(e))

    def run_tests(self, pattern: str, start: float) -> AgentResponse:
        return self.run_shell(f"pytest {pattern}", start)


class SessionManager:
    def __init__(self, session_file: str = "session.json"):
        self.session_file = Path(session_file)
        self.session: Dict = {}
        self.load()
        logger.info(f"SessionManager init: {session_file}")

    def load(self):
        if self.session_file.exists():
            with open(self.session_file) as f:
                self.session = json.load(f)
            logger.info(f"Loaded session: {len(self.session.get('history', []))} turns")

    def save(self):
        with open(self.session_file, 'w') as f:
            json.dump(self.session, f, indent=2, default=str)
        logger.info("Session saved")

    def add_turn(self, request: PromptRequest, response: AgentResponse):
        turn = {
            "timestamp": request.timestamp.isoformat(),
            "request": {
                "text": request.text,
                "intent": request.intent.value,
                "user_level": request.user_level
            },
            "response": {
                "success": response.success,
                "text": response.text[:200] if response.text else "",
                "error": response.error,
                "execution_time": response.execution_time
            }
        }
        self.session.setdefault("history", []).append(turn)
        
        if len(self.session["history"]) > 100:
            self.session["history"] = self.session["history"][-100:]
        
        self.save()

    def get_history(self, limit: int = 10) -> List[Dict]:
        return self.session.get("history", [])[-limit:]


class CrackedCodeEngine:
    PROMPT_TEMPLATES = {
        Intent.CODE: "You are an expert coder. Write clean, idiomatic Python code.\n\nTask: {prompt}",
        Intent.DEBUG: "You are a debugging expert. Find and fix bugs.\n\nTask: {prompt}",
        Intent.REVIEW: "You are a code reviewer. Analyze code quality and suggest improvements.\n\nTask: {prompt}",
        Intent.SEARCH: "Search the codebase for: {prompt}",
        Intent.BUILD: "Create a complete implementation plan for: {prompt}",
    }

    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.model = self.config.get("model", "qwen3:8b-gpu")
        self.project_root = self.config.get("project_root", ".")
        
        self.voice = VoiceEngine(self.config.get("whisper_size", "medium.en"))
        self.ollama = OllamaBridge(self.model)
        self.executor = CodeExecutor(self.project_root)
        self.session = SessionManager()
        
        self.plan_enabled = True
        self.build_enabled = True
        self.voice_enabled = False
        
        self._health_check()
        logger.info("CrackedCodeEngine initialized")

    def _health_check(self):
        ollama_status = self.ollama.detect()
        logger.info(f"Health: Ollama={ollama_status['available']}")
        logger.info(f"Health: Models={ollama_status['models']}")
        
    def get_status(self) -> Dict:
        ollama = self.ollama.detect()
        return {
            "version": "2.3.2",
            "model": self.model,
            "plan": self.plan_enabled,
            "build": self.build_enabled,
            "voice": self.voice_enabled,
            "ollama_available": ollama["available"],
            "ollama_models": ollama["models"],
            "ollama_host": ollama["host"],
            "history_length": len(self.session.get("history", []))
        }

    async def process(self, prompt: str) -> AgentResponse:
        request = self.parse_intent(prompt)
        
        if not self.plan_enabled and request.intent != Intent.CHAT:
            return AgentResponse(
                success=False,
                text="Plan mode is disabled",
                intent=request.intent
            )
        
        logger.info(f"Processing: {request.intent.value} - {prompt[:50]}...")
        
        if request.intent == Intent.EXECUTE:
            return await self.execute_code(prompt)
        
        response = await self.ai_process(request)
        
        self.session.add_turn(request, response)
        
        if self.build_enabled and Intent.BUILD:
            self.executor.run_code(response.text)
        
        return response

    def parse_intent(self, prompt: str) -> PromptRequest:
        intent = Intent.CHAT
        text = prompt.lower()
        
        if any(k in text for k in ["debug", "fix", "error", "bug"]):
            intent = Intent.DEBUG
        elif any(k in text for k in ["write", "create", "implement"]):
            intent = Intent.CODE
        elif any(k in text for k in ["review", "analyze", "check"]):
            intent = Intent.REVIEW
        elif any(k in text for k in ["search", "find", "locate"]):
            intent = Intent.SEARCH
        elif any(k in text for k in ["build", "run", "execute"]):
            intent = Intent.EXECUTE
        elif any(k in text for k in ["plan", "design", "architecture"]):
            intent = Intent.BUILD
        
        return PromptRequest(text=prompt, intent=intent)

    async def ai_process(self, request: PromptRequest) -> AgentResponse:
        template = self.PROMPT_TEMPLATES.get(request.intent, "{prompt}")
        prompt = template.format(prompt=request.text)
        
        system = "You are CrackedCode, an expert AI coding assistant."
        
        response = self.ollama.chat(prompt, system)
        
        if response.success:
            response.intent = request.intent
        
        return response

    async def execute_code(self, prompt: str) -> AgentResponse:
        prompt = prompt.replace("run ", "").replace("execute ", "").strip()
        
        if not prompt:
            return AgentResponse(success=False, error="No code to execute")
        
        response = self.executor.run_shell(prompt)
        return response

    def voice_transcribe(self, audio: bytes) -> str:
        return self.voice.transcribe(audio)

    def get_status(self) -> Dict:
        return {
            "model": self.model,
            "plan": self.plan_enabled,
            "build": self.build_enabled,
            "voice": self.voice_enabled,
            "history_length": len(self.session.get("history", []))
        }


_engine: Optional[CrackedCodeEngine] = None


def get_engine(config: Dict = None) -> CrackedCodeEngine:
    global _engine
    if _engine is None:
        _engine = CrackedCodeEngine(config)
    return _engine