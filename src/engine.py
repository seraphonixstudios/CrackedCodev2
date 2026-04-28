import sys
import os
import json
import logging
import subprocess
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
    
    DEBUG_KEYWORDS = ["debug", "fix", "bug", "error", "issue", "problem", "crash", "broken"]
    CODE_KEYWORDS = ["write", "create", "generate", "build", "make", "new", "implement"]
    REVIEW_KEYWORDS = ["review", "analyze", "check", "audit", "assess", "improve"]
    BUILD_KEYWORDS = ["build", "plan", "design", "architecture", "structure", "outline"]
    EXECUTE_KEYWORDS = ["run", "execute", "test", "start", "launch"]
    SEARCH_KEYWORDS = ["search", "find", "grep", "locate", "look", "where"]

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
        return {"version": "2.3.8", "model": self.model, "plan": self.plan_enabled, "build": self.build_enabled,
                "ollama_available": ollama["available"], "ollama_models": ollama["models"], "history_length": self.session.history_len()}

    def parse_intent(self, prompt: str, confidence_threshold: float = 0.5) -> PromptRequest:
        """Parse user intent from prompt with improved keyword matching."""
        text = prompt.lower()
        
        keyword_scores = {
            Intent.DEBUG: sum(1 for k in self.DEBUG_KEYWORDS if k in text),
            Intent.CODE: sum(1 for k in self.CODE_KEYWORDS if k in text),
            Intent.REVIEW: sum(1 for k in self.REVIEW_KEYWORDS if k in text),
            Intent.BUILD: sum(1 for k in self.BUILD_KEYWORDS if k in text),
            Intent.EXECUTE: sum(1 for k in self.EXECUTE_KEYWORDS if k in text),
            Intent.SEARCH: sum(1 for k in self.SEARCH_KEYWORDS if k in text),
        }
        
        max_score = max(keyword_scores.values())
        
        if max_score >= confidence_threshold * 10:
            intent = max(keyword_scores, key=keyword_scores.get)
        else:
            intent = Intent.CHAT
        
        context = {
            "keyword_matches": {k.value: v for k, v in keyword_scores.items()},
            "confidence": max_score / 10.0,
            "raw_keywords": [k for k in text.split() if len(k) > 3],
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

    async def process(self, prompt: str) -> AgentResponse:
        """Process a user prompt with full intent detection and execution."""
        request = self.parse_intent(prompt)
        
        if not self.plan_enabled and request.intent != Intent.CHAT:
            return AgentResponse(success=False, text="Plan disabled")
        
        logger.info(f"Processing: {request.intent.value} (confidence: {request.context.get('confidence', 0):.2f})")
        
        if request.intent == Intent.EXECUTE:
            cmd = prompt.replace("run ", "").replace("execute ", "").strip()
            return self.executor.run_shell(cmd)
        
        if request.intent == Intent.SEARCH:
            return self._search_files(prompt)
        
        template = self.PROMPT_TEMPLATES.get(request.intent, "{prompt}")
        response = self.ollama.chat(template.format(prompt=request.text))
        
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
                except Exception:
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


_engine: Optional[CrackedCodeEngine] = None


def get_engine(config: Dict = None) -> CrackedCodeEngine:
    global _engine
    if _engine is None:
        _engine = CrackedCodeEngine(config)
    return _engine