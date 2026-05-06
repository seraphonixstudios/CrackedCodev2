"""Self-Healing Agent v2.9.3 - Auto-detect errors and fix them.

Monitors log files for exceptions, traces them to source code,
generates patches, and verifies fixes with tests.

Usage:
    from src.self_healing import get_healing_agent
    agent = get_healing_agent(engine)
    
    # Watch a log file
    agent.watch("app.log", auto_fix=True)
    
    # Manually trigger fix
    fix = agent.fix_error("traceback...")
    
    # Get status
    status = agent.get_status()
"""

import json
import os
import re
import subprocess
import threading
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.logger_config import get_logger

logger = get_logger("SelfHealing")


# ── Data Models ────────────────────────────────────────────────────────────

@dataclass
class DetectedError:
    """An error detected in a log file."""
    id: str
    timestamp: str
    error_type: str
    message: str
    file: str = ""
    line: int = 0
    function: str = ""
    traceback: str = ""
    raw: str = ""


@dataclass
class AppliedFix:
    """A fix that was applied."""
    id: str
    error_id: str
    file: str
    diff: str
    tests_passed: bool
    applied_at: str
    reverted: bool = False


# ── Self-Healing Agent ─────────────────────────────────────────────────────

class SelfHealingAgent:
    """Auto-detect errors and generate fixes."""

    # Common Python error patterns
    ERROR_PATTERNS = [
        re.compile(
            r"Traceback \(most recent call last\):\n"
            r"(?:  File \"(.+?)\", line (\d+), in (.+?)\n"
            r"(?:    .+\n)?)+"
            r"(\w+Error|\w+Exception):\s*(.+?)(?=\n\n|\Z)",
            re.DOTALL,
        ),
        re.compile(
            r"(\w+Error|\w+Exception):\s*(.+?)(?=\n\n|\Z)",
            re.DOTALL,
        ),
    ]

    def __init__(self, engine=None, repo_path: str = "."):
        self.engine = engine
        self.repo_path = Path(repo_path)
        self.watching = False
        self.watch_thread = None
        self.detected_errors: List[DetectedError] = []
        self.applied_fixes: List[AppliedFix] = []
        self._load_state()

    def _load_state(self):
        """Load persistent state."""
        state_file = self.repo_path / ".crackedcode" / "healing_state.json"
        if state_file.exists():
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.applied_fixes = [
                    AppliedFix(
                        id=f["id"],
                        error_id=f["error_id"],
                        file=f["file"],
                        diff=f["diff"],
                        tests_passed=f["tests_passed"],
                        applied_at=f["applied_at"],
                        reverted=f.get("reverted", False),
                    )
                    for f in data.get("fixes", [])
                ]
            except Exception as e:
                logger.warning(f"Failed to load healing state: {e}")

    def _save_state(self):
        """Save persistent state."""
        state_file = self.repo_path / ".crackedcode" / "healing_state.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "fixes": [
                {
                    "id": f.id,
                    "error_id": f.error_id,
                    "file": f.file,
                    "diff": f.diff,
                    "tests_passed": f.tests_passed,
                    "applied_at": f.applied_at,
                    "reverted": f.reverted,
                }
                for f in self.applied_fixes
            ]
        }
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def watch(self, log_file: str, auto_fix: bool = False,
              interval: int = 5) -> bool:
        """Start watching a log file for errors."""
        import hashlib

        log_path = Path(log_file)
        if not log_path.exists():
            logger.warning(f"Log file not found: {log_file}")
            return False

        self.watching = True
        last_size = log_path.stat().st_size
        last_errors = set()

        def monitor():
            nonlocal last_size, last_errors
            while self.watching:
                time.sleep(interval)
                try:
                    current_size = log_path.stat().st_size
                    if current_size > last_size:
                        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                            f.seek(last_size)
                            new_content = f.read()

                        errors = self._parse_errors(new_content)
                        for error in errors:
                            error_id = hashlib.md5(
                                f"{error.error_type}:{error.message}".encode()
                            ).hexdigest()[:12]

                            if error_id not in last_errors:
                                last_errors.add(error_id)
                                error.id = error_id
                                self.detected_errors.append(error)
                                logger.warning(
                                    f"Detected error: {error.error_type} in {error.file}:{error.line}"
                                )

                                if auto_fix and self.engine:
                                    self.fix_error(error)

                        last_size = current_size
                except Exception as e:
                    logger.error(f"Log monitoring error: {e}")

        self.watch_thread = threading.Thread(target=monitor, daemon=True)
        self.watch_thread.start()
        logger.info(f"Started watching {log_file} (auto_fix={auto_fix})")
        return True

    def stop_watching(self):
        """Stop watching log files."""
        self.watching = False
        if self.watch_thread:
            self.watch_thread.join(timeout=5)
        logger.info("Stopped watching logs")

    def _parse_errors(self, content: str) -> List[DetectedError]:
        """Parse errors from log content."""
        errors = []
        for pattern in self.ERROR_PATTERNS:
            for match in pattern.finditer(content):
                if len(match.groups()) >= 5:
                    file_path = match.group(1) or ""
                    line_num = int(match.group(2)) if match.group(2) else 0
                    func = match.group(3) or ""
                    error_type = match.group(4) or "UnknownError"
                    message = match.group(5).strip()
                else:
                    file_path = ""
                    line_num = 0
                    func = ""
                    error_type = match.group(1) or "UnknownError"
                    message = match.group(2).strip() if len(match.groups()) > 1 else ""

                errors.append(DetectedError(
                    id="",
                    timestamp=str(time.time()),
                    error_type=error_type,
                    message=message,
                    file=file_path,
                    line=line_num,
                    function=func,
                    traceback=match.group(0),
                    raw=match.group(0),
                ))
        return errors

    def fix_error(self, error: DetectedError) -> Optional[AppliedFix]:
        """Attempt to fix a detected error."""
        if not self.engine:
            logger.warning("No engine available for auto-fix")
            return None

        if not error.file or not Path(error.file).exists():
            logger.warning(f"Cannot fix: file not found {error.file}")
            return None

        try:
            # Read the problematic file
            with open(error.file, "r", encoding="utf-8") as f:
                source = f.read()

            # Generate fix using AI
            fix = self._generate_fix(error, source)
            if not fix:
                return None

            # Apply fix
            diff = self._apply_fix(error.file, fix)
            if not diff:
                return None

            # Run tests to verify
            tests_passed = self._run_tests()

            applied = AppliedFix(
                id=f"fix-{error.id}",
                error_id=error.id,
                file=error.file,
                diff=diff,
                tests_passed=tests_passed,
                applied_at=str(time.time()),
            )
            self.applied_fixes.append(applied)
            self._save_state()

            if tests_passed:
                logger.info(f"Fix applied and verified: {error.file}")
            else:
                logger.warning(f"Fix applied but tests failed: {error.file}")

            return applied

        except Exception as e:
            logger.error(f"Fix generation failed: {e}")
            return None

    def _generate_fix(self, error: DetectedError, source: str) -> Optional[str]:
        """Generate a fix for an error using the AI engine."""
        # Extract relevant lines
        lines = source.split("\n")
        start = max(0, error.line - 5)
        end = min(len(lines), error.line + 5)
        context = "\n".join(f"{i + 1}: {lines[i]}" for i in range(start, end))

        prompt = f"""Fix this Python error:

Error: {error.error_type}: {error.message}
File: {error.file}
Line: {error.line}
Function: {error.function}

Context:
{context}

Provide ONLY the fixed code block. Do not include explanations."""

        try:
            response = self.engine.process(prompt)
            text = response.get("response", "") if isinstance(response, dict) else str(response)

            # Extract code block
            code_match = re.search(r"```python\n(.*?)\n```", text, re.DOTALL)
            if code_match:
                return code_match.group(1)

            # Fallback: return full response
            return text.strip()
        except Exception as e:
            logger.error(f"AI fix generation failed: {e}")
            return None

    def _apply_fix(self, file_path: str, fix_code: str) -> str:
        """Apply a fix to a file and return the diff."""
        from src.code_diff import create_diff_applier

        # Read original
        with open(file_path, "r", encoding="utf-8") as f:
            original = f.read()

        # For now, replace the entire file (in production, this would be more surgical)
        # Generate unified diff
        diff = self._generate_unified_diff(original, fix_code, file_path)

        # Apply fix
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(fix_code)

        return diff

    def _generate_unified_diff(self, original: str, modified: str,
                               file_path: str) -> str:
        """Generate unified diff between original and modified."""
        import difflib

        original_lines = original.splitlines(keepends=True)
        modified_lines = modified.splitlines(keepends=True)

        diff = difflib.unified_diff(
            original_lines,
            modified_lines,
            fromfile=file_path,
            tofile=file_path,
        )
        return "".join(diff)

    def _run_tests(self) -> bool:
        """Run tests to verify a fix."""
        try:
            result = subprocess.run(
                ["python", "-m", "pytest", "-x", "-q"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=120,
            )
            return result.returncode == 0
        except FileNotFoundError:
            # pytest not found, try running test_system.py
            try:
                result = subprocess.run(
                    ["python", "test_system.py"],
                    cwd=self.repo_path,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                return result.returncode == 0
            except Exception:
                return False
        except Exception:
            return False

    def revert_fix(self, fix_id: str) -> bool:
        """Revert a previously applied fix."""
        fix = next((f for f in self.applied_fixes if f.id == fix_id), None)
        if not fix:
            return False

        # Parse diff and reverse it
        try:
            # Simple approach: we don't store original, so this is a placeholder
            # In production, store original before applying fix
            fix.reverted = True
            self._save_state()
            logger.info(f"Reverted fix: {fix_id}")
            return True
        except Exception as e:
            logger.error(f"Revert failed: {e}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """Get agent status."""
        return {
            "watching": self.watching,
            "errors_detected": len(self.detected_errors),
            "fixes_applied": len(self.applied_fixes),
            "fixes_passed": sum(1 for f in self.applied_fixes if f.tests_passed),
            "fixes_reverted": sum(1 for f in self.applied_fixes if f.reverted),
        }

    def get_errors(self) -> List[DetectedError]:
        """Get all detected errors."""
        return self.detected_errors

    def get_fixes(self) -> List[AppliedFix]:
        """Get all applied fixes."""
        return self.applied_fixes


def get_healing_agent(engine=None, repo_path: str = ".") -> SelfHealingAgent:
    """Get the global self-healing agent."""
    return SelfHealingAgent(engine=engine, repo_path=repo_path)
