"""Custom Rules Engine v2.10.0 - User-defined code review rules.

Allows users to define custom review rules via JSON/YAML config or Python API.
Rules are evaluated during code review alongside built-in rules.

Usage:
    from src.custom_rules import get_rules_engine

    engine = get_rules_engine()
    engine.add_rule(ReviewRule(
        name="no_print_debug",
        pattern=r"print\s*\(\s*['\"]debug",
        severity="warning",
        message="Remove debug print statements before committing",
    ))

    results = engine.review_file("src/main.py")
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

from src.logger_config import get_logger

logger = get_logger("CustomRules")


class Severity:
    """Review rule severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ReviewRule:
    """A custom code review rule."""
    name: str
    description: str = ""
    pattern: str = ""
    severity: str = Severity.WARNING
    message: str = ""
    enabled: bool = True
    file_patterns: List[str] = field(default_factory=lambda: ["*.py"])
    callback: Optional[Callable[[str, str], List[Dict[str, Any]]]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def compile_pattern(self) -> Optional[re.Pattern]:
        """Compile the regex pattern."""
        if not self.pattern:
            return None
        try:
            return re.compile(self.pattern, re.MULTILINE)
        except re.error as e:
            logger.warning(f"Invalid regex in rule '{self.name}': {e}")
            return None

    def matches_file(self, file_path: str) -> bool:
        """Check if this rule applies to the given file."""
        if not self.file_patterns:
            return True
        p = Path(file_path)
        for pattern in self.file_patterns:
            if p.match(pattern):
                return True
        return False


@dataclass
class ReviewFinding:
    """A finding from a review rule."""
    rule: str
    file: str
    line: int
    severity: str
    message: str
    snippet: str = ""


class CustomRulesEngine:
    """Engine for managing and executing custom review rules."""

    def __init__(self, config_path: str = ".crackedcode/custom_rules.json"):
        self.config_path = Path(config_path)
        self._rules: Dict[str, ReviewRule] = {}
        self._load_config()

    def _load_config(self):
        """Load rules from JSON config file."""
        if not self.config_path.exists():
            return
        try:
            data = json.loads(self.config_path.read_text(encoding="utf-8"))
            for rule_data in data.get("rules", []):
                rule = ReviewRule(
                    name=rule_data["name"],
                    description=rule_data.get("description", ""),
                    pattern=rule_data.get("pattern", ""),
                    severity=rule_data.get("severity", Severity.WARNING),
                    message=rule_data.get("message", ""),
                    enabled=rule_data.get("enabled", True),
                    file_patterns=rule_data.get("file_patterns", ["*.py"]),
                    metadata=rule_data.get("metadata", {}),
                )
                self._rules[rule.name] = rule
            logger.info(f"Loaded {len(self._rules)} custom rules from config")
        except Exception as e:
            logger.warning(f"Failed to load custom rules config: {e}")

    def save_config(self):
        """Save current rules to JSON config file."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "rules": [
                {
                    "name": r.name,
                    "description": r.description,
                    "pattern": r.pattern,
                    "severity": r.severity,
                    "message": r.message,
                    "enabled": r.enabled,
                    "file_patterns": r.file_patterns,
                    "metadata": r.metadata,
                }
                for r in self._rules.values()
            ]
        }
        self.config_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info(f"Saved {len(self._rules)} custom rules to config")

    def add_rule(self, rule: ReviewRule) -> ReviewRule:
        """Add or update a review rule."""
        self._rules[rule.name] = rule
        logger.info(f"Added custom rule: {rule.name} ({rule.severity})")
        return rule

    def remove_rule(self, name: str) -> bool:
        """Remove a review rule."""
        if name in self._rules:
            del self._rules[name]
            return True
        return False

    def get_rule(self, name: str) -> Optional[ReviewRule]:
        """Get a rule by name."""
        return self._rules.get(name)

    def list_rules(self, enabled_only: bool = False) -> List[ReviewRule]:
        """List all rules."""
        rules = list(self._rules.values())
        if enabled_only:
            rules = [r for r in rules if r.enabled]
        return rules

    def review_file(self, file_path: str) -> List[ReviewFinding]:
        """Review a single file against all enabled rules."""
        findings = []
        p = Path(file_path)

        if not p.exists() or not p.is_file():
            return findings

        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return findings

        lines = content.splitlines()

        for rule in self._rules.values():
            if not rule.enabled or not rule.matches_file(file_path):
                continue

            if rule.callback:
                try:
                    callback_findings = rule.callback(file_path, content)
                    for cf in callback_findings:
                        findings.append(ReviewFinding(
                            rule=rule.name,
                            file=file_path,
                            line=cf.get("line", 0),
                            severity=rule.severity,
                            message=cf.get("message", rule.message),
                            snippet=cf.get("snippet", ""),
                        ))
                except Exception as e:
                    logger.warning(f"Rule '{rule.name}' callback failed: {e}")

            compiled = rule.compile_pattern()
            if compiled:
                for line_num, line in enumerate(lines, 1):
                    if compiled.search(line):
                        findings.append(ReviewFinding(
                            rule=rule.name,
                            file=file_path,
                            line=line_num,
                            severity=rule.severity,
                            message=rule.message,
                            snippet=line.strip()[:100],
                        ))

        return findings

    def review_directory(self, directory: str, extensions: List[str] = None) -> Dict[str, List[ReviewFinding]]:
        """Review all files in a directory."""
        results = {}
        p = Path(directory)

        if not p.exists() or not p.is_dir():
            return results

        exts = extensions or [".py", ".js", ".ts", ".json", ".yaml", ".yml"]

        for file_path in p.rglob("*"):
            if not file_path.is_file() or file_path.suffix not in exts:
                continue
            if ".git" in str(file_path) or "node_modules" in str(file_path):
                continue

            findings = self.review_file(str(file_path))
            if findings:
                results[str(file_path)] = findings

        return results

    def get_stats(self) -> Dict[str, Any]:
        """Get rules engine statistics."""
        by_severity = {}
        for rule in self._rules.values():
            by_severity[rule.severity] = by_severity.get(rule.severity, 0) + 1

        return {
            "total_rules": len(self._rules),
            "enabled": sum(1 for r in self._rules.values() if r.enabled),
            "disabled": sum(1 for r in self._rules.values() if not r.enabled),
            "by_severity": by_severity,
            "config_path": str(self.config_path),
        }


_rules_engine: Optional[CustomRulesEngine] = None


def get_rules_engine(config_path: str = ".crackedcode/custom_rules.json") -> CustomRulesEngine:
    """Get the global custom rules engine."""
    global _rules_engine
    if _rules_engine is None:
        _rules_engine = CustomRulesEngine(config_path=config_path)
    return _rules_engine


def reset_rules_engine():
    """Reset the global rules engine (for testing)."""
    global _rules_engine
    _rules_engine = None
