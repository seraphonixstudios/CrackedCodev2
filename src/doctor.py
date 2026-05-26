"""Doctor / Health Check v2.10.0 - System diagnostics and component testing.

Automatically test every component and report exactly what's broken.

Usage:
    # Full diagnostics
    python src/main.py doctor

    # Check specific component
    python src/main.py doctor --component ollama
    python src/main.py doctor --component memory

    # Output formats
    python src/main.py doctor --json
    python src/main.py doctor --quiet

    # API
    GET /health
    GET /health/{component}
"""

import json
import os
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.logger_config import get_logger

logger = get_logger("Doctor")


# ── Data Models ────────────────────────────────────────────────────────────

@dataclass
class HealthCheck:
    """A single health check result."""
    component: str
    name: str
    status: str  # ok, warning, error
    message: str
    duration_ms: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthReport:
    """Complete health report."""
    overall: str = "ok"  # ok, warning, error
    checks: List[HealthCheck] = field(default_factory=list)
    duration_ms: float = 0.0
    timestamp: str = ""
    version: str = ""


# ── Doctor ─────────────────────────────────────────────────────────────────

class Doctor:
    """System diagnostics and health checks."""
    
    CHECKS = {
        "ollama": ["connection", "models", "response"],
        "engine": ["init", "models_loaded"],
        "api": ["server", "endpoints"],
        "memory": ["long_term", "agent_memory"],
        "git": ["repo", "hooks"],
        "voice": ["stt", "tts"],
        "files": ["config", "storage"],
    }
    
    def __init__(self, version: str = "2.10.0"):
        self.version = version
        self.results: List[HealthCheck] = []
    
    def run_all(self) -> HealthReport:
        """Run all health checks."""
        start = time.time()
        self.results = []
        
        # Run all component checks
        for component in self.CHECKS:
            self._check_component(component)
        
        # Determine overall status
        statuses = [c.status for c in self.results]
        overall = "ok"
        if "error" in statuses:
            overall = "error"
        elif "warning" in statuses:
            overall = "warning"
        
        return HealthReport(
            overall=overall,
            checks=self.results,
            duration_ms=(time.time() - start) * 1000,
            timestamp=datetime.utcnow().isoformat() if 'datetime' in dir() else str(time.time()),
            version=self.version,
        )
    
    def run_component(self, component: str) -> List[HealthCheck]:
        """Run checks for a specific component."""
        self.results = []
        self._check_component(component)
        return self.results
    
    def _check_component(self, component: str):
        """Run all checks for a component."""
        checks = self.CHECKS.get(component, [])
        for check_name in checks:
            check_method = getattr(self, f"_check_{component}_{check_name}", None)
            if check_method:
                try:
                    start = time.time()
                    check_method()
                    duration = (time.time() - start) * 1000
                    # Update duration on last result
                    if self.results and self.results[-1].component == component:
                        self.results[-1].duration_ms = duration
                except Exception as e:
                    self._add_result(component, check_name, "error", f"Check crashed: {e}")
    
    def _add_result(self, component: str, name: str, status: str, message: str, details: Optional[Dict[str, Any]] = None):
        """Add a health check result."""
        self.results.append(HealthCheck(
            component=component,
            name=name,
            status=status,
            message=message,
            details=details or {},
        ))
    
    # ── Ollama checks ──────────────────────────────────────────────────────
    
    def _check_ollama_connection(self):
        """Check Ollama connectivity."""
        try:
            import requests
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                models = [m.get("name", "") for m in data.get("models", [])]
                self._add_result("ollama", "connection", "ok", f"Connected, {len(models)} models available", {"models": models})
            else:
                self._add_result("ollama", "connection", "error", f"HTTP {response.status_code}")
        except requests.ConnectionError:
            self._add_result("ollama", "connection", "error", "Ollama not running on localhost:11434")
        except Exception as e:
            self._add_result("ollama", "connection", "error", str(e))
    
    def _check_ollama_models(self):
        """Check required models are available."""
        try:
            import requests
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                models = [m.get("name", "").split(":")[0] for m in data.get("models", [])]
                
                required = ["qwen3", "llava", "dolphin"]
                missing = [r for r in required if r not in models]
                
                if missing:
                    self._add_result("ollama", "models", "warning", f"Missing recommended models: {', '.join(missing)}", {"available": models})
                else:
                    self._add_result("ollama", "models", "ok", "All recommended models available", {"available": models})
            else:
                self._add_result("ollama", "models", "error", "Cannot check models")
        except Exception as e:
            self._add_result("ollama", "models", "error", str(e))
    
    def _check_ollama_response(self):
        """Test Ollama can generate a response."""
        try:
            import requests
            payload = {
                "model": "qwen3:8b-gpu",
                "prompt": "Say 'pong'",
                "stream": False,
            }
            response = requests.post("http://localhost:11434/api/generate", json=payload, timeout=30)
            if response.status_code == 200:
                data = response.json()
                text = data.get("response", "")
                if text:
                    self._add_result("ollama", "response", "ok", "Model responding correctly", {"response_preview": text[:50]})
                else:
                    self._add_result("ollama", "response", "warning", "Empty response from model")
            else:
                self._add_result("ollama", "response", "error", f"HTTP {response.status_code}")
        except Exception as e:
            self._add_result("ollama", "response", "error", str(e))
    
    # ── Engine checks ──────────────────────────────────────────────────────
    
    def _check_engine_init(self):
        """Check engine can initialize."""
        try:
            from src.engine import CrackedCodeEngine
            engine = CrackedCodeEngine()
            self._add_result("engine", "init", "ok", "Engine initialized successfully", {"model": engine.model})
        except Exception as e:
            self._add_result("engine", "init", "error", str(e))
    
    def _check_engine_models_loaded(self):
        """Check engine has models configured."""
        try:
            from src.engine import CrackedCodeEngine
            engine = CrackedCodeEngine()
            models = engine.available_models if hasattr(engine, "available_models") else []
            if models:
                self._add_result("engine", "models_loaded", "ok", f"{len(models)} models loaded", {"models": models})
            else:
                self._add_result("engine", "models_loaded", "warning", "No models loaded")
        except Exception as e:
            self._add_result("engine", "models_loaded", "error", str(e))
    
    # ── API checks ─────────────────────────────────────────────────────────
    
    def _check_api_server(self):
        """Check API server is accessible."""
        try:
            import requests
            response = requests.get("http://localhost:8080/status", timeout=5)
            if response.status_code == 200:
                self._add_result("api", "server", "ok", "API server responding", {"status_code": response.status_code})
            else:
                self._add_result("api", "server", "warning", f"API returned {response.status_code}")
        except requests.ConnectionError:
            self._add_result("api", "server", "warning", "API server not running on localhost:8080")
        except Exception as e:
            self._add_result("api", "server", "error", str(e))
    
    def _check_api_endpoints(self):
        """Check key API endpoints exist."""
        try:
            import requests
            endpoints = ["/status", "/models", "/tools", "/agents"]
            results = {}
            for endpoint in endpoints:
                try:
                    resp = requests.get(f"http://localhost:8080{endpoint}", timeout=3)
                    results[endpoint] = resp.status_code == 200
                except Exception:
                    results[endpoint] = False
            
            all_ok = all(results.values())
            status = "ok" if all_ok else "warning"
            self._add_result("api", "endpoints", status, f"{sum(results.values())}/{len(results)} endpoints OK", {"details": results})
        except Exception as e:
            self._add_result("api", "endpoints", "error", str(e))
    
    # ── Memory checks ──────────────────────────────────────────────────────
    
    def _check_memory_long_term(self):
        """Check long-term memory system."""
        try:
            from src.long_term_memory import LongTermMemory
            memory = LongTermMemory()
            self._add_result("memory", "long_term", "ok", "Long-term memory initialized")
        except ImportError:
            self._add_result("memory", "long_term", "warning", "Long-term memory module not available")
        except Exception as e:
            self._add_result("memory", "long_term", "error", str(e))
    
    def _check_memory_agent_memory(self):
        """Check agent memory system."""
        try:
            from src.agent_memory import get_agent_memory_system
            memory = get_agent_memory_system()
            stats = memory.get_stats()
            self._add_result("memory", "agent_memory", "ok", f"Agent memory: {stats.get('total_agents', 0)} agents, {stats.get('total_entries', 0)} entries", stats)
        except ImportError:
            self._add_result("memory", "agent_memory", "warning", "Agent memory module not available")
        except Exception as e:
            self._add_result("memory", "agent_memory", "error", str(e))
    
    # ── Git checks ─────────────────────────────────────────────────────────
    
    def _check_git_repo(self):
        """Check git repository status."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                self._add_result("git", "repo", "ok", "Git repository detected", {"git_dir": result.stdout.strip()})
            else:
                self._add_result("git", "repo", "warning", "Not a git repository")
        except FileNotFoundError:
            self._add_result("git", "repo", "warning", "Git not installed")
        except Exception as e:
            self._add_result("git", "repo", "error", str(e))
    
    def _check_git_hooks(self):
        """Check git hooks."""
        try:
            from src.git_hooks import GitHookManager
            manager = GitHookManager()
            status = manager.get_status()
            if status.get("pre_commit_installed"):
                self._add_result("git", "hooks", "ok", "Pre-commit hook installed")
            else:
                self._add_result("git", "hooks", "ok", "No pre-commit hook (optional)")
        except ImportError:
            self._add_result("git", "hooks", "warning", "Git hooks module not available")
        except Exception as e:
            self._add_result("git", "hooks", "error", str(e))
    
    # ── Voice checks ───────────────────────────────────────────────────────
    
    def _check_voice_stt(self):
        """Check speech-to-text availability."""
        try:
            import faster_whisper
            self._add_result("voice", "stt", "ok", "faster-whisper available")
        except ImportError:
            self._add_result("voice", "stt", "warning", "faster-whisper not installed (optional)")
        except Exception as e:
            self._add_result("voice", "stt", "error", str(e))
    
    def _check_voice_tts(self):
        """Check text-to-speech availability."""
        try:
            import pyttsx3
            self._add_result("voice", "tts", "ok", "pyttsx3 available")
        except ImportError:
            self._add_result("voice", "tts", "warning", "pyttsx3 not installed (optional)")
        except Exception as e:
            self._add_result("voice", "tts", "error", str(e))
    
    # ── File checks ────────────────────────────────────────────────────────
    
    def _check_files_config(self):
        """Check configuration file."""
        config_path = Path("config.json")
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                self._add_result("files", "config", "ok", f"Config loaded: {len(cfg)} top-level keys", {"keys": list(cfg.keys())})
            except json.JSONDecodeError:
                self._add_result("files", "config", "error", "config.json is invalid JSON")
            except Exception as e:
                self._add_result("files", "config", "error", str(e))
        else:
            self._add_result("files", "config", "error", "config.json not found")
    
    def _check_files_storage(self):
        """Check storage directories."""
        dirs = {
            ".crackedcode": "Main storage",
            ".crackedcode/agent_memory": "Agent memory",
            ".crackedcode/knowledge": "Knowledge base",
            ".crackedcode/traces": "Execution traces",
            ".crackedcode/benchmarks": "Benchmarks",
        }
        
        results = {}
        for d, label in dirs.items():
            path = Path(d)
            exists = path.exists()
            results[d] = {"exists": exists, "label": label}
        
        all_exist = all(r["exists"] for r in results.values())
        status = "ok" if all_exist else "warning"
        self._add_result("files", "storage", status, f"Storage dirs: {sum(r['exists'] for r in results.values())}/{len(results)} exist", {"details": results})
    
    # ── Formatting ─────────────────────────────────────────────────────────
    
    def format_report(self, report: HealthReport, json_output: bool = False) -> str:
        """Format a health report for display."""
        if json_output:
            return json.dumps({
                "overall": report.overall,
                "version": report.version,
                "timestamp": report.timestamp,
                "duration_ms": round(report.duration_ms, 2),
                "checks": [
                    {
                        "component": c.component,
                        "name": c.name,
                        "status": c.status,
                        "message": c.message,
                        "duration_ms": round(c.duration_ms, 2),
                        "details": c.details,
                    }
                    for c in report.checks
                ],
            }, indent=2)
        
        lines = []
        lines.append("")
        lines.append("=" * 70)
        lines.append(f"  🏥 CRACKEDCODE HEALTH CHECK v{report.version}")
        lines.append("=" * 70)
        lines.append("")
        
        # Overall status
        emoji = {"ok": "✅", "warning": "⚠️", "error": "❌"}.get(report.overall, "❓")
        lines.append(f"  Overall: {emoji} {report.overall.upper()}")
        lines.append(f"  Duration: {report.duration_ms:.0f}ms")
        lines.append("")
        
        # Group by component
        by_component = {}
        for check in report.checks:
            by_component.setdefault(check.component, []).append(check)
        
        for component, checks in sorted(by_component.items()):
            lines.append(f"  {component.upper()}")
            lines.append(f"  {'─' * 60}")
            
            for check in checks:
                emoji = {"ok": "✅", "warning": "⚠️", "error": "❌"}.get(check.status, "❓")
                lines.append(f"    {emoji} {check.name}: {check.message}")
                if check.details:
                    for key, val in check.details.items():
                        if isinstance(val, (str, int, float, bool)):
                            lines.append(f"       {key}: {val}")
            
            lines.append("")
        
        # Summary
        ok_count = sum(1 for c in report.checks if c.status == "ok")
        warn_count = sum(1 for c in report.checks if c.status == "warning")
        error_count = sum(1 for c in report.checks if c.status == "error")
        
        lines.append("=" * 70)
        lines.append(f"  Summary: {ok_count} OK | {warn_count} Warnings | {error_count} Errors")
        lines.append("=" * 70)
        lines.append("")
        
        return "\n".join(lines)


def run_health_check(component: Optional[str] = None, json_output: bool = False, version: str = "2.10.0") -> HealthReport:
    """Run health check and return report."""
    doctor = Doctor(version=version)
    
    if component:
        checks = doctor.run_component(component)
        report = HealthReport(
            overall="ok" if not any(c.status == "error" for c in checks) else "error",
            checks=checks,
            version=version,
        )
    else:
        report = doctor.run_all()
    
    return report

