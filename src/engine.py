import sys
import os
import json
import logging
import threading
import time
from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s | %(levelname)s | %(name)s | %(message)s')
logger = logging.getLogger("CrackedCodeEngine")


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

    def detect(self) -> Dict:
        result = {"available": False, "models": [], "host": "http://localhost:11434", "selected": self.model}
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
        except Exception as e:
            logger.error(f"Ollama detection failed: {e}")
        return result

    def chat(self, prompt: str, system: str = "") -> AgentResponse:
        if not self.ollama:
            self.detect()
        start = time.time()
        try:
            messages = [{"role": "system", "content": system}] if system else []
            messages.append({"role": "user", "content": prompt})
            response = self.ollama.chat(model=self.model, messages=messages, options={"temperature": 0.1})
            text = response.message.content
            return AgentResponse(success=True, text=text, execution_time=time.time() - start)
        except Exception as e:
            logger.error(f"Ollama chat failed: {e}")
            return AgentResponse(success=False, error=str(e))


class CodeExecutor:
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.allowed = ["python", "pytest", "ruff", "git", "npm", "node", "pip"]

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
        Intent.CODE: "Write clean Python code.\n\nTask: {prompt}",
        Intent.DEBUG: "Find and fix bugs.\n\nTask: {prompt}",
        Intent.REVIEW: "Analyze code quality.\n\nTask: {prompt}",
        Intent.BUILD: "Create implementation plan.\n\nTask: {prompt}",
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
        self._check()
        logger.info("CrackedCodeEngine initialized")

    def _check(self):
        status = self.ollama.detect()
        logger.info(f"Ollama: {status['available']}, Models: {status['models']}")

    def get_status(self) -> Dict:
        ollama = self.ollama.detect()
        return {"version": "2.3.3", "model": self.model, "plan": self.plan_enabled, "build": self.build_enabled,
                "ollama_available": ollama["available"], "ollama_models": ollama["models"], "history_length": self.session.history_len()}

    def parse_intent(self, prompt: str) -> PromptRequest:
        intent = Intent.CHAT
        text = prompt.lower()
        if any(k in text for k in ["debug", "fix", "bug"]): intent = Intent.DEBUG
        elif any(k in text for k in ["write", "create"]): intent = Intent.CODE
        elif any(k in text for k in ["review"]): intent = Intent.REVIEW
        elif any(k in text for k in ["build", "plan"]): intent = Intent.BUILD
        elif any(k in text for k in ["run", "execute"]): intent = Intent.EXECUTE
        return PromptRequest(text=prompt, intent=intent)

    async def process(self, prompt: str) -> AgentResponse:
        request = self.parse_intent(prompt)
        if not self.plan_enabled and request.intent != Intent.CHAT:
            return AgentResponse(success=False, text="Plan disabled")
        logger.info(f"Processing: {request.intent.value}")
        if request.intent == Intent.EXECUTE:
            return self.executor.run_shell(prompt.replace("run ", "").replace("execute ", "").strip())
        template = self.PROMPT_TEMPLATES.get(request.intent, "{prompt}")
        response = self.ollama.chat(template.format(prompt=request.text))
        if response.success:
            self.session.add_turn(request, response)
        return response


_engine: Optional[CrackedCodeEngine] = None


def get_engine(config: Dict = None) -> CrackedCodeEngine:
    global _engine
    if _engine is None:
        _engine = CrackedCodeEngine(config)
    return _engine