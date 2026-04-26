#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   █████╗  ██████╗  ██████╗ ████████╗    ██████╗  ██╗     ██╗ ██████╗ ██████╗  █████╗ ║
║  ██╔══██╗██╔═══██╗██╔═══██╗╚══██╔══╝    ██╔══██╗ ██║     ██║██╔════╝ ██╔══██╗██╔══██╗║
║  ███████║██║   ██║██║   ██║   ██║       ██████╔╝ ██║     ██║██║  ███╗██████╔╝███████║║
║  ██╔══██║██║   ██║██║   ██║   ██║       ██╔══██╗ ██║     ██║██║   ██║██╔══██╗██╔══██║║
║  ██║  ██║╚██████╔╝╚██████╔╝   ██║       ██║  ██║ ███████╗██║██║   ██║██║  ██║██║  ██║║
║  ╚═╝  ╚═╝ ╚═════╝  ╚═════╝    ╚═╝       ╚═╝  ╚═╝ ╚══════╝╚═╝╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝║
║                                                                              ║
║                        CrackedCode Voice System                               ║
║              SOTA Local Multi-Agent Coding Swarm with Voice I/O             ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

CrackedCode - Production-Grade Local AI Coding Assistant
100% Offline • 100% Private • 100% Free

Version: 2.0.0
License: MIT
Platforms: Linux, macOS, Windows (WSL)

Features:
- Multi-Agent Swarm: Supervisor → Architect → Coder → Executor → Reviewer
- Voice I/O: Speech-to-Text (faster-whisper) + Text-to-Speech (Piper)
- Tool Use: File read/write, shell execution, code analysis
- Debate Protocol: Coder-Reviewer dynamic resolution
- Blackboard Memory: Persistent cross-agent coordination

Author: CrackedCode Team
Website: https://github.com/crackedcode
"""

import os
import sys
import json
import subprocess
import signal
import threading
import time
import platform
import re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging

try:
    from faster_whisper import WhisperModel
    import sounddevice as sd
    import numpy as np
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    FASTER_WHISPER_AVAILABLE = False
    print("Warning: faster-whisper not installed. Voice features disabled.")
    print("Install with: pip install faster-whisper sounddevice numpy")

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    print("Warning: ollama Python SDK not installed.")
    print("Install with: pip install ollama")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('crackedcode.log', mode='a')
    ]
)
logger = logging.getLogger('CrackedCode')


class AgentType(Enum):
    SUPERVISOR = "supervisor"
    ARCHITECT = "architect"
    CODER = "coder"
    EXECUTOR = "executor"
    REVIEWER = "reviewer"
    SPECIALIST = "specialist"


@dataclass
class Task:
    id: int
    agent: str
    description: str
    status: str = "pending"
    result: Optional[Dict] = None
    error: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None

    @property
    def duration(self) -> float:
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0.0


@dataclass
class AgentResponse:
    action: str
    reasoning: str = ""
    data: Dict = field(default_factory=dict)
    success: bool = True
    error: Optional[str] = None


class BLACKBOARD:
    PROJECT_CONTEXT = ""
    FILES = {}
    PLAN = []
    DEBATE_LOG = []
    CONSENSUS = {}
    AGENT_MEMORY = {}
    TASK_HISTORY = []


class CrackedCodeConfig:
    DEFAULT_CONFIG = {
        "model": "qwen3-coder:32b",
        "whisper_size": "medium.en",
        "tts_voice": "en_US-lessac-medium",
        "sample_rate": 16000,
        "push_to_talk": False,
        "max_concurrent_agents": 4,
        "task_timeout": 120,
        "ollama_host": "http://localhost:11434",
        "allowed_shell_commands": [
            "git", "npm", "node", "python", "python3", "pip", "pip3",
            "ruff", "mypy", "pytest", "cargo", "go", "curl", "wget",
            "ls", "dir", "cd", "mkdir", "rm", "cp", "mv", "cat", "type",
            "find", "grep", "rg", "echo"
        ],
        "project_root": str(Path.cwd()),
        "log_level": "INFO",
        "voice_enabled": True,
        "auto_save_blackboard": True,
        "debate_rounds": 3,
        "max_retries": 2,
        "temperature": 0.1,
        "num_ctx": 16384,
    }

    def __init__(self, config_path: Optional[str] = None):
        self.config = self.DEFAULT_CONFIG.copy()
        if config_path and Path(config_path).exists():
            self.load(config_path)

    def load(self, config_path: str):
        try:
            with open(config_path, 'r') as f:
                user_config = json.load(f)
                self.config.update(user_config)
                logger.info(f"Loaded config from {config_path}")
        except Exception as e:
            logger.warning(f"Failed to load config: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

    def set(self, key: str, value: Any):
        self.config[key] = value

    def save(self, config_path: str):
        with open(config_path, 'w') as f:
            json.dump(self.config, f, indent=2)
        logger.info(f"Saved config to {config_path}")


AGENT_SYSTEM_PROMPTS = {
    AgentType.SUPERVISOR.value: """You are the Supervisor Agent - the orchestrator of the CrackedCode Multi-Agent Swarm.

Your role:
- Analyze complex coding tasks and break them into structured subtask plans
- Assign appropriate agents (Architect, Coder, Executor, Reviewer, Specialist) to each subtask
- Ensure proper task dependency ordering
- Coordinate inter-agent communication via the BLACKBOARD
- Makefinal decision when consensus is reached

Output format - MUST be valid JSON:
{
  "plan": [
    {
      "id": 1,
      "agent": "architect|coder|executor|reviewer|specialist",
      "description": "detailed task description",
      "priority": "high|medium|low",
      "depends_on": []  // array of task IDs this depends on
    }
  ],
  "reasoning": "your analysis and task breakdown reasoning"
}

Guidelines:
- Break complex tasks into 3-7 manageable subtasks
- Assign "coder" for code generation
- Assign "architect" for system design
- Assign "executor" for running commands
- Assign "reviewer" for code critique
- Consider task dependencies for ordering
- Output ONLY valid JSON, no additional text""",

    AgentType.ARCHITECT.value: """You are the Architect Agent - the system design specialist.

Your role:
- Design SOTA system architecture using modern patterns (2026 best practices)
- Create Mermaid diagrams for visual representation
- Define file structures and component relationships
- Select appropriate tech stacks
- Document API contracts and data models
- Consider scalability, security, and performance

Output format - MUST be valid JSON:
{
  "action": "design_system",
  "design": {
    "overview": "system overview description",
    "components": [
      {
        "name": "component name",
        "type": "service|module|class",
        "responsibilities": ["responsibility 1", "responsibility 2"],
        "dependencies": ["dependency 1", "dependency 2"]
      }
    ],
    "api_contracts": [
      {
        "endpoint": "/api/v1/resource",
        "method": "GET|POST|PUT|DELETE",
        "request": {"param": "type"},
        "response": {"status": "code", "data": {}}
      }
    ],
    "data_models": [
      {
        "name": "ModelName",
        "fields": {"field": "type"},
        "relationships": []
      }
    ],
    "mermaid": "graph TD; A-->B; B-->C;"
  },
  "files": [
    {"path": "src/main.py", "description": "entry point"},
    {"path": "src/models/__init__.py", "description": "model definitions"}
  ],
  "reasoning": "your architectural decisions and trade-offs"
}

Guidelines:
- Use modern patterns: Clean Architecture, DDD, Event-Driven
- Consider 2026 best practices
- Include security by design
- Plan for scaling
- Output ONLY valid JSON, no additional text""",

    AgentType.CODER.value: """You are the Coder Agent - the code generation specialist.

Your role:
- Write production-ready code with 2026 best practices
- Follow clean code principles
- Implement proper error handling
- Add comprehensive comments for complex logic
- Consider security and performance
- Write testable code

Available tools:
- read_file(path): Read file content
- write_file(path, content): Write code to file
- run_shell(command): Execute shell commands

Output format - MUST be valid JSON:
{
  "action": "write_file",
  "path": "src/module/file.py",
  "content": "full Python code...",
  "language": "python|javascript|typescript|go|rust|etc",
  "reasoning": "code design decisions and implementation details",
  "tests": [
    {"description": "test case 1", "input": "value", "expected": "result"}
  ]
}

Guidelines:
- Production-ready code only
- Follow PEP 8 (Python), ESLint (JS), etc.
- Add docstrings and type hints
- Handle errors gracefully
- Consider edge cases
- Output ONLY valid JSON, no additional text""",

    AgentType.EXECUTOR.value: """You are the Executor Agent - the command execution specialist.

Your role:
- Execute safe shell commands
- Report comprehensive results
- Handle errors gracefully
- Support multiple platforms (Linux, macOS, Windows)
- Provide detailed logging

Available tools:
- run_shell(command, timeout): Execute command (default timeout 30s)

Output format - MUST be valid JSON:
{
  "action": "run_shell",
  "command": "npm install",
  "timeout": 60,
  "expected_output": "what success looks like",
  "error_patterns": ["error pattern 1", "error pattern 2"]
}

Result format:
{
  "action": "shell_result",
  "stdout": "command output",
  "stderr": "errors",
  "exit_code": 0,
  "success": true/false,
  "duration": 1.23,
  "analysis": "result analysis"
}

Guidelines:
- Use allowed commands only
- Provide meaningful timeouts
- Report all output streams
- Handle failures gracefully
- Output ONLY valid JSON, no additional text""",

    AgentType.REVIEWER.value: """You are the Reviewer Agent - the code critique specialist.

Your role:
- Analyze code for bugs, security issues, performance problems
- Check for code smells and anti-patterns
- Verify test coverage
- Ensure security best practices
- Score code quality 0-100
- Run debate protocol with Coder

Available tools:
- read_file(path): Read file content
- run_shell(command): Execute linters, tests

Output format - MUST be valid JSON:
{
  "action": "review",
  "score": 85,
  "issues": [
    {
      "severity": "critical|high|medium|low",
      "category": "security|performance|bug|code_smell",
      "location": "file:line",
      "description": "issue description",
      "suggestion": "how to fix"
    }
  ],
  "strengths": ["good practice 1", "good practice 2"],
  "suggestions": ["improvement 1", "improvement 2"],
  "debate_required": true/false,
  "debate_points": ["point to debate with coder"],
  "reasoning": "review analysis"
}

If score < 80 or security issues found, debate is required.
Output ONLY valid JSON, no additional text""",

    AgentType.SPECIALIST.value: """You are the Specialist Agent - dynamic task handler.

Your role:
- Handle niche tasks assigned by Supervisor
- Provide expert analysis
- Adapt to task requirements
- Research and document findings

Output format - MUST be valid JSON:
{
  "action": "specialist_analysis",
  "findings": [
    {"topic": "finding 1", "details": "detailed explanation"}
  ],
  "recommendations": ["recommendation 1", "recommendation 2"],
  "resources": ["resource 1", "resource 2"],
  "reasoning": "analysis reasoning"
}

Guidelines:
- Be thorough and precise
- Provide actionable insights
- Include relevant research
- Output ONLY valid JSON, no additional text"""
}


class ToolRegistry:
    def __init__(self, config: CrackedCodeConfig):
        self.config = config
        self.tools = {}

    def register(self, name: str, func: callable):
        self.tools[name] = func

    def execute(self, name: str, **kwargs) -> Any:
        if name in self.tools:
            return self.tools[name](**kwargs)
        raise ValueError(f"Unknown tool: {name}")

    def get_available_tools(self) -> List[str]:
        return list(self.tools.keys())


class FileTools:
    def __init__(self, config: CrackedCodeConfig):
        self.config = config

    def read_file(self, path: str, max_size: int = 50000) -> str:
        p = Path(path)
        if not p.exists():
            return json.dumps({"error": f"File not found: {path}"})

        try:
            content = p.read_text(encoding='utf-8')
            BLACKBOARD.FILES[str(p)] = content[:max_size]
            return json.dumps({
                "success": True,
                "path": str(p),
                "content": content[:max_size],
                "size": len(content),
                "truncated": len(content) > max_size
            })
        except Exception as e:
            return json.dumps({
                "error": str(e),
                "path": str(p)
            })

    def write_file(self, path: str, content: str, create_dirs: bool = True) -> str:
        p = Path(path)
        try:
            if create_dirs:
                p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding='utf-8')
            BLACKBOARD.FILES[str(p)] = content
            return json.dumps({
                "success": True,
                "path": str(p),
                "size": len(content)
            })
        except Exception as e:
            return json.dumps({
                "error": str(e),
                "path": str(p)
            })

    def delete_file(self, path: str) -> str:
        p = Path(path)
        try:
            if p.exists():
                p.unlink()
                if str(p) in BLACKBOARD.FILES:
                    del BLACKBOARD.FILES[str(p)]
                return json.dumps({"success": True, "path": str(p)})
            return json.dumps({"error": f"File not found: {path}"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    def list_directory(self, path: str = ".", pattern: str = "*") -> str:
        p = Path(path)
        try:
            files = []
            for item in p.glob(pattern):
                files.append({
                    "name": item.name,
                    "type": "dir" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else 0,
                    "path": str(item)
                })
            return json.dumps({
                "success": True,
                "path": str(p),
                "files": files,
                "count": len(files)
            })
        except Exception as e:
            return json.dumps({"error": str(e)})


class ShellTools:
    def __init__(self, config: CrackedCodeConfig):
        self.config = config
        self.allowed_commands = config.get("allowed_shell_commands", [])

    def is_command_allowed(self, cmd: str) -> bool:
        parts = cmd.split()
        if not parts:
            return False
        base_cmd = parts[0].lower()

        if platform.system() == "Windows":
            base_cmd = base_cmd.replace('.exe', '')

        return any(base_cmd.startswith(allowed) for allowed in self.allowed_commands)

    def run_shell(self, cmd: str, timeout: int = 30, cwd: Optional[str] = None) -> str:
        if not self.is_command_allowed(cmd):
            return json.dumps({
                "error": f"Command not allowed: {cmd}",
                "allowed": self.allowed_commands[:10]
            })

        try:
            start_time = time.time()
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd or self.config.get("project_root"),
                encoding='utf-8',
                errors='replace'
            )
            duration = time.time() - start_time

            return json.dumps({
                "success": result.returncode == 0,
                "command": cmd,
                "stdout": result.stdout[:10000],
                "stderr": result.stderr[:5000],
                "exit_code": result.returncode,
                "duration": round(duration, 3),
                "truncated": len(result.stdout) > 10000 or len(result.stderr) > 5000
            })
        except subprocess.TimeoutExpired:
            return json.dumps({
                "error": f"Command timed out after {timeout}s",
                "command": cmd,
                "timeout": timeout
            })
        except Exception as e:
            return json.dumps({
                "error": str(e),
                "command": cmd
            })


class OllamaClient:
    def __init__(self, config: CrackedCodeConfig):
        self.config = config
        self.model = config.get("model", "qwen3-coder:32b")
        self.host = config.get("ollama_host", "http://localhost:11434")

    def chat(self, agent: str, prompt: str, context: Optional[str] = None,
            format_json: bool = True) -> AgentResponse:
        system_prompt = AGENT_SYSTEM_PROMPTS.get(agent, AGENT_SYSTEM_PROMPTS[AgentType.CODER.value])

        context_str = f"""
BLACKBOARD STATE:
{json.dumps({
    "project_context": BLACKBOARD.PROJECT_CONTEXT,
    "files_tracked": len(BLACKBOARD.FILES),
    "plan": BLACKBOARD.PLAN[-5:] if BLACKBOARD.PLAN else [],
    "debate_rounds": len(BLACKBOARD.DEBATE_LOG)
}, indent=2)}

PROJECT ROOT: {self.config.get('project_root')}
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{context_str}\n\nTASK: {prompt}"}
        ]

        try:
            ollama_host = os.environ.get('OLLAMA_HOST', self.host)
            response = ollama.chat(
                model=self.model,
                messages=messages,
                format="json" if format_json else None,
                options={
                    "temperature": self.config.get("temperature", 0.1),
                    "num_ctx": self.config.get("num_ctx", 16384),
                }
            )

            content = response['message']['content']

            try:
                data = json.loads(content)
                return AgentResponse(
                    action=data.get('action', 'unknown'),
                    reasoning=data.get('reasoning', ''),
                    data=data,
                    success=True
                )
            except json.JSONDecodeError:
                return AgentResponse(
                    action='text',
                    reasoning='Non-JSON response',
                    data={'raw': content},
                    success=True
                )

        except Exception as e:
            logger.error(f"Ollama error: {e}")
            return AgentResponse(
                action='error',
                reasoning=str(e),
                data={},
                success=False,
                error=str(e)
            )

    def is_available(self) -> bool:
        try:
            response = ollama.list()
            return self.model in [m['name'] for m in response.get('models', [])]
        except:
            return False

    def pull_model(self, model: Optional[str] = None):
        model = model or self.model
        try:
            logger.info(f"Pulling model: {model}")
            ollama.pull(model)
            return True
        except Exception as e:
            logger.error(f"Failed to pull model: {e}")
            return False


class VoiceController:
    def __init__(self, config: CrackedCodeConfig):
        self.config = config
        self.stt_model = None
        self.sample_rate = config.get("sample_rate", 16000)
        self.push_to_talk = config.get("push_to_talk", False)
        self.whisper_size = config.get("whisper_size", "medium.en")

    def init_stt(self) -> bool:
        if not FASTER_WHISPER_AVAILABLE:
            logger.warning("faster-whisper not available")
            return False

        if not self.config.get("voice_enabled", True):
            logger.info("Voice disabled in config")
            return False

        try:
            device = "cuda" if self._check_cuda() else "cpu"
            compute = "float16" if device == "cuda" else "int8"

            logger.info(f"Loading Whisper: {self.whisper_size} on {device}")
            self.stt_model = WhisperModel(
                self.whisper_size,
                device=device,
                compute_type=compute
            )
            logger.info("STT initialized successfully")
            return True

        except Exception as e:
            logger.error(f"STT init failed: {e}")
            return False

    def _check_cuda(self) -> bool:
        if platform.system() == "Windows":
            try:
                subprocess.run(["nvidia-smi"], capture_output=True, check=True)
                return True
            except:
                return False
        else:
            return False

    def listen(self, duration: float = 5.0) -> str:
        if not self.stt_model:
            logger.warning("STT not initialized")
            return ""

        try:
            logger.info(f"Listening for {duration}s...")
            recording = sd.rec(
                int(duration * self.sample_rate),
                samplerate=self.sample_rate,
                channels=1,
                dtype='float32'
            )
            sd.wait()
            audio = np.squeeze(recording)

            segments, _ = self.stt_model.transcribe(
                audio,
                beam_size=5,
                language="en",
                vad_filter=True
            )

            transcript = " ".join(seg.text for seg in segments).strip()
            logger.info(f"Transcribed: {transcript[:100]}...")
            return transcript

        except Exception as e:
            logger.error(f"Listen error: {e}")
            return f"Error: {e}"

    def speak(self, text: str) -> bool:
        try:
            logger.info(f"TTS: {text[:50]}...")

            if platform.system() == "Windows":
                piper_exe = Path.home() / ".piper" / "piper.exe"
                voice_model = Path.home() / ".piper" / f"{self.config.get('tts_voice')}.onnx"
            else:
                piper_exe = Path("/usr/local/bin/piper")
                voice_model = Path.home() / ".local/share/piper-voices" / f"{self.config.get('tts_voice')}.onnx"

            if not piper_exe.exists():
                logger.warning("Piper not found")
                return False

            output_wav = "/tmp/crackedcode_response.wav"
            cmd = [
                str(piper_exe),
                "--model", str(voice_model),
                "--output_file", output_wav
            ]

            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
            proc.communicate(input=text.encode(), timeout=10)

            if platform.system() == "Windows":
                subprocess.run(["start", output_wav], shell=True, capture_output=True)
            else:
                subprocess.run(["aplay", output_wav], capture_output=True)

            return True

        except FileNotFoundError:
            logger.warning("Piper not installed")
            return False
        except Exception as e:
            logger.error(f"TTS error: {e}")
            return False


class AgentSwarm:
    def __init__(self, config: CrackedCodeConfig):
        self.config = config
        self.ollama = OllamaClient(config)
        self.file_tools = FileTools(config)
        self.shell_tools = ShellTools(config)
        self.voice = VoiceController(config)
        self.max_workers = config.get("max_concurrent_agents", 4)
        self.task_timeout = config.get("task_timeout", 120)

    def _execute_task(self, task: Task) -> Tuple[Task, Dict]:
        task.status = "running"
        task.start_time = time.time()

        logger.info(f"Executing task {task.id}: {task.agent}")

        try:
            response = self.ollama.chat(task.agent, task.description)

            if task.agent == AgentType.CODER.value and response.action == "write_file":
                result = self.file_tools.write_file(
                    response.data.get("path", ""),
                    response.data.get("content", "")
                )
                task.result = json.loads(result)

            elif task.agent == AgentType.EXECUTOR.value:
                cmd = response.data.get("command", "")
                timeout = response.data.get("timeout", 30)
                result = self.shell_tools.run_shell(cmd, timeout)
                task.result = json.loads(result)

            elif task.agent == "read_file" and response.data.get("path"):
                result = self.file_tools.read_file(response.data.get("path"))
                task.result = json.loads(result)

            else:
                task.result = response.data

            task.status = "completed"
            task.end_time = time.time()

        except Exception as e:
            logger.error(f"Task {task.id} failed: {e}")
            task.status = "failed"
            task.error = str(e)
            task.end_time = time.time()

        BLACKBOARD.TASK_HISTORY.append(task)
        return task, task.result

    def run_plan(self, plan: List[Dict]) -> List[Tuple[Task, Dict]]:
        tasks = [
            Task(
                id=t["id"],
                agent=t["agent"],
                description=t["description"],
                status="pending"
            )
            for t in plan
        ]

        BLACKBOARD.PLAN = plan
        results = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._execute_task, task): task
                for task in tasks
            }

            for future in as_completed(futures, timeout=self.task_timeout):
                task = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"Task {task.id} exception: {e}")
                    task.status = "failed"
                    task.error = str(e)
                    results.append((task, {"error": str(e)}))

        return results

    def run_debate_protocol(self, coder_result: Dict, reviewer_result: Dict,
                           rounds: int = 3) -> Dict:
        BLACKBOARD.DEBATE_LOG.append({
            "coder": coder_result,
            "reviewer": reviewer_result
        })

        for round_num in range(rounds):
            logger.info(f"Debate round {round_num + 1}/{rounds}")

            coder_response = self.ollama.chat(
                AgentType.CODER.value,
                f"Respond to reviewer issues: {reviewer_result.get('issues', [])}"
            )

            reviewer_response = self.ollama.chat(
                AgentType.REVIEWER.value,
                f"Evaluate coder response to issues"
            )

            BLACKBOARD.DEBATE_LOG.append({
                "round": round_num + 1,
                "coder": coder_response.data,
                "reviewer": reviewer_response.data
            })

            if reviewer_response.data.get("score", 0) >= 80:
                break

        consensus = reviewer_response.data
        BLACKBOARD.CONSENSUS = consensus
        return consensus


class CrackedCode:
    VERSION = "2.0.0"
    BANNER = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   █████╗  ██████╗  ██████╗ ████████╗    ██████╗  ██╗     ██╗ ██████╗ ██████╗  █████╗ ║
║  ██╔══██╗██╔═══██╗██╔═══██╗╚══██╔══╝    ██╔══██╗ ██║     ██║██╔════╝ ██╔══██╗██╔══██╗║
║  ███████║██║   ██║██║   ██║   ██║       ██████╔╝ ██║     ██║██║  ███╗██████╔╝███████║║
║  ██╔══██║██║   ██║██║   ██║   ██║       ██╔══██╗ ██║     ██║██║   ██║██╔══██╗██╔══██║║
║  ██║  ██║╚██████╔╝╚██████╔╝   ██║       ██║  ██║ ███████╗██║██║   ██║██║  ██║██║  ██║║
║  ╚═╝  ╚═╝ ╚═════╝  ╚═════╝    ╚═╝       ╚═╝  ╚═╝ ╚══════╝╚═╝╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝║
║                                                                              ║
║                        CrackedCode Voice System                               ║
║              SOTA Local Multi-Agent Coding Swarm with Voice I/O             ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

Version: {version}
Platform: {platform}
Python: {python}
"""

    def __init__(self, config_path: Optional[str] = None):
        self.config = CrackedCodeConfig(config_path)
        self.swarm = AgentSwarm(self.config)
        self.running = False

        logger.info(f"CrackedCode v{self.VERSION} initializing...")

    def _print_banner(self):
        print(self.BANNER.format(
            version=self.VERSION,
            platform=platform.system(),
            python=platform.python_version()
        ))
        print("-" * 70)

    def start(self):
        self._print_banner()

        if not OLLAMA_AVAILABLE:
            logger.error("Ollama SDK not available")
            print("Error: Ollama SDK required. Install with: pip install ollama")
            return False

        if not self.swarm.ollama.is_available():
            logger.warning("Ollama not available, attempting model pull...")
            if not self.swarm.ollama.pull_model():
                logger.error("Failed to connect to Ollama")
                print("Error: Ollama not running. Start with: ollama serve")
                return False

        self.config.set("voice_enabled", self.swarm.voice.init_stt())

        self.running = True
        logger.info("CrackedCode ready")
        print("\n🎯 CrackedCode is ready!")
        print("\nCommands:")
        print("  • 'exit' - Quit")
        print("  • 'show blackboard' - View memory")
        print("  • 'show history' - View task history")
        print("  • 'help' - Show this help")
        print()

        return True

    def run(self):
        if not self.start():
            return

        while self.running:
            try:
                if self.config.get("push_to_talk"):
                    input("\nPress Enter to speak... ")

                if self.swarm.voice.stt_model:
                    transcript = self.swarm.voice.listen()
                else:
                    transcript = input("You: ").strip()

                if not transcript:
                    continue

                print(f"\n👤 You: {transcript}")

                if transcript.lower() in ["exit", "quit", "shutdown"]:
                    logger.info("Shutting down...")
                    print("\n👋 CrackedCode shutting down. Goodnight!")
                    self.swarm.voice.speak("Shutting down. Goodnight!")
                    break

                if transcript.lower() == "show blackboard":
                    print("\n" + "=" * 50)
                    print("BLACKBOARD STATE")
                    print("=" * 50)
                    print(json.dumps({
                        "project_context": BLACKBOARD.PROJECT_CONTEXT,
                        "files_tracked": len(BLACKBOARD.FILES),
                        "plan": BLACKBOARD.PLAN,
                        "debate_rounds": len(BLACKBOARD.DEBATE_LOG),
                        "consensus": BLACKBOARD.CONSENSUS
                    }, indent=2))
                    continue

                if transcript.lower() == "show history":
                    print("\n" + "=" * 50)
                    print("TASK HISTORY")
                    print("=" * 50)
                    for task in BLACKBOARD.TASK_HISTORY[-10:]:
                        print(f"  Task {task.id}: {task.agent} - {task.status}")
                    continue

                if transcript.lower() == "help":
                    self._print_banner()
                    continue

                supervisor_response = self.swarm.ollama.chat(
                    AgentType.SUPERVISOR.value,
                    transcript
                )

                plan = supervisor_response.data.get("plan", [
                    {"id": 1, "agent": "architect", "description": transcript}
                ])

                print(f"\n📋 Supervisor created {len(plan)} subtasks")
                self.swarm.voice.speak(f"Executing {len(plan)} subtasks")

                results = self.swarm.run_plan(plan)

                for task, result in results:
                    if result.get("action") == "review":
                        coder_result = next(
                            (r[1] for r in results if r[1].get("action") == "write_file"),
                            {}
                        )
                        if result.get("debate_required") or result.get("score", 0) < 80:
                            consensus = self.swarm.run_debate_protocol(
                                coder_result,
                                result,
                                self.config.get("debate_rounds", 3)
                            )
                            print(f"\n⚖️  Debate resolved. Score: {consensus.get('score')}")

                completed = len([t for t, r in results if t.status == "completed"])
                summary = f"Complete. {completed}/{len(results)} tasks succeeded."

                print(f"\n✅ {summary}")
                self.swarm.voice.speak(summary)

            except KeyboardInterrupt:
                print("\n\nInterrupted. Type 'exit' to quit.")
            except Exception as e:
                logger.error(f"Error: {e}")
                print(f"\n❌ Error: {e}")

        self.running = False


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="CrackedCode - SOTA Local Multi-Agent Coding Swarm"
    )
    parser.add_argument(
        "-c", "--config",
        help="Path to config JSON file",
        default=None
    )
    parser.add_argument(
        "--model",
        help="Ollama model to use",
        default=None
    )
    parser.add_argument(
        "--no-voice",
        help="Disable voice features",
        action="store_true"
    )
    parser.add_argument(
        "--push-to-talk",
        help="Enable push-to-talk mode",
        action="store_true"
    )

    args = parser.parse_args()

    app = CrackedCode(args.config)

    if args.model:
        app.config.set("model", args.model)

    if args.no_voice:
        app.config.set("voice_enabled", False)

    if args.push_to_talk:
        app.config.set("push_to_talk", True)

    app.run()


if __name__ == "__main__":
    main()