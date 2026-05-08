"""Code Review Bot v2.9.6 - Automated PR/code review that runs continuously.

Monitors git repositories for changes and automatically runs code reviews
using the reviewer agent. Can run on push, PR, or on a schedule.

Usage:
    from src.code_review_bot import get_review_bot
    bot = get_review_bot()
    bot.start_monitoring(".")
    
    # Or trigger manually
    result = bot.review_commit("HEAD~1", ".")
"""

import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.logger_config import get_logger

logger = get_logger("CodeReviewBot")


# â”€â”€ Data Models â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@dataclass
class ReviewIssue:
    """A single issue found during code review."""
    file: str
    line: int
    severity: str  # critical, high, medium, low, info
    category: str  # security, style, performance, bug, documentation
    message: str
    suggestion: str = ""
    confidence: float = 0.8


@dataclass
class ReviewReport:
    """Complete code review report."""
    commit: str
    files_reviewed: List[str] = field(default_factory=list)
    issues: List[ReviewIssue] = field(default_factory=list)
    summary: str = ""
    verdict: str = "pass"  # pass, conditional, fail
    score: float = 0.0  # 0-100
    duration: float = 0.0
    started_at: str = ""
    completed_at: str = ""


@dataclass
class ReviewRule:
    """A review rule for automated checking."""
    name: str
    category: str
    severity: str
    pattern: str = ""  # regex pattern
    message: str = ""
    suggestion: str = ""
    languages: List[str] = field(default_factory=list)
    enabled: bool = True


# â”€â”€ Code Review Bot â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class CodeReviewBot:
    """Automated code review bot."""
    
    BUILT_IN_RULES = [
        ReviewRule(
            name="hardcoded_password",
            category="security",
            severity="critical",
            pattern=r'(password|passwd|pwd)\s*=\s*[\'"][^\'"]+[\'"]',
            message="Potential hardcoded password detected",
            suggestion="Use environment variables or a secrets manager",
            languages=["python", "javascript", "java", "go"],
        ),
        ReviewRule(
            name="sql_injection",
            category="security",
            severity="critical",
            pattern=r'(execute|query|raw)\s*\(\s*[\'"].*%s',
            message="Potential SQL injection vulnerability",
            suggestion="Use parameterized queries or an ORM",
            languages=["python", "javascript", "java", "php"],
        ),
        ReviewRule(
            name="eval_usage",
            category="security",
            severity="high",
            pattern=r'\beval\s*\(',
            message="Dangerous eval() usage detected",
            suggestion="Use ast.literal_eval or json.loads for safe parsing",
            languages=["python", "javascript"],
        ),
        ReviewRule(
            name="todo_comment",
            category="documentation",
            severity="info",
            pattern=r'#\s*(TODO|FIXME|HACK|XXX|BUG)',
            message="TODO/FIXME comment found",
            suggestion="Address or create an issue to track this",
            languages=["python", "javascript", "java", "go", "rust"],
        ),
        ReviewRule(
            name="print_debug",
            category="style",
            severity="low",
            pattern=r'\bprint\s*\(',
            message="Debug print statement found",
            suggestion="Use logging instead of print for production code",
            languages=["python"],
        ),
        ReviewRule(
            name="unused_import",
            category="style",
            severity="low",
            pattern=r'^import\s+\w+',
            message="Check for unused imports",
            suggestion="Remove unused imports to keep code clean",
            languages=["python", "java", "go"],
        ),
        ReviewRule(
            name="no_error_handling",
            category="bug",
            severity="medium",
            pattern=r'^(?!.*except).*open\s*\(',
            message="File operation without error handling",
            suggestion="Wrap file operations in try/except blocks",
            languages=["python"],
        ),
        ReviewRule(
            name="insecure_http",
            category="security",
            severity="medium",
            pattern=r'http://(?!localhost|127\.0\.0\.1)',
            message="Insecure HTTP URL detected",
            suggestion="Use HTTPS for external URLs",
            languages=["python", "javascript", "java", "go"],
        ),
    ]
    
    def __init__(self, engine=None, github_client=None):
        self.engine = engine
        self.github_client = github_client
        self.rules = self.BUILT_IN_RULES.copy()
        self.monitoring = False
        self.monitor_thread = None
    
    def review_commit(self, commit: str, repo_path: str = ".",
                      files: Optional[List[str]] = None) -> ReviewReport:
        """Review a specific commit."""
        from datetime import datetime
        
        start = time.time()
        started_at = datetime.utcnow().isoformat()
        
        # Get changed files
        if files is None:
            files = self._get_changed_files(commit, repo_path)
        
        issues: List[ReviewIssue] = []
        
        # Run rule-based checks
        for file_path in files:
            file_issues = self._check_file(file_path, repo_path)
            issues.extend(file_issues)
        
        # Run AI review if engine available
        ai_issues = []
        if self.engine:
            ai_issues = self._run_ai_review(files, repo_path)
            issues.extend(ai_issues)
        
        # Calculate score
        score = self._calculate_score(issues, len(files))
        
        # Determine verdict
        critical = sum(1 for i in issues if i.severity == "critical")
        high = sum(1 for i in issues if i.severity == "high")
        
        if critical > 0:
            verdict = "fail"
        elif high > 2:
            verdict = "conditional"
        else:
            verdict = "pass"
        
        # Generate summary
        summary = self._generate_summary(files, issues, verdict, score)
        
        completed_at = datetime.utcnow().isoformat()
        
        return ReviewReport(
            commit=commit,
            files_reviewed=files,
            issues=issues,
            summary=summary,
            verdict=verdict,
            score=score,
            duration=time.time() - start,
            started_at=started_at,
            completed_at=completed_at,
        )
    
    def review_pr(self, repo: str, pr_number: int) -> ReviewReport:
        """Review a GitHub pull request."""
        if self.github_client is None:
            return ReviewReport(
                commit=f"PR #{pr_number}",
                summary="GitHub client not configured",
                verdict="error",
                score=0,
            )
        
        try:
            # Get PR diff
            diff_text = self.github_client.get_pr_diff(repo, pr_number)
            
            # Parse diff for files
            files = self._parse_diff_files(diff_text)
            
            # Run review
            report = self.review_commit(f"PR #{pr_number}", files=files)
            
            # Post review comment
            if report.issues:
                comment = self._format_review_comment(report)
                self.github_client.post_pr_comment(repo, pr_number, comment)
            
            return report
        except Exception as e:
            logger.error(f"PR review failed: {e}")
            return ReviewReport(
                commit=f"PR #{pr_number}",
                summary=f"Review failed: {e}",
                verdict="error",
                score=0,
            )
    
    def start_monitoring(self, repo_path: str = ".",
                         interval: int = 60,
                         on_review: Optional[callable] = None):
        """Start monitoring repository for new commits."""
        import threading
        
        self.monitoring = True
        last_commit = self._get_latest_commit(repo_path)
        
        def monitor():
            nonlocal last_commit
            while self.monitoring:
                time.sleep(interval)
                try:
                    current_commit = self._get_latest_commit(repo_path)
                    if current_commit != last_commit:
                        logger.info(f"New commit detected: {current_commit}")
                        report = self.review_commit(current_commit, repo_path)
                        
                        if on_review:
                            on_review(report)
                        
                        last_commit = current_commit
                except Exception as e:
                    logger.error(f"Monitoring error: {e}")
        
        self.monitor_thread = threading.Thread(target=monitor, daemon=True)
        self.monitor_thread.start()
        logger.info(f"Started monitoring {repo_path} every {interval}s")
    
    def stop_monitoring(self):
        """Stop monitoring."""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("Stopped monitoring")
    
    def add_rule(self, rule: ReviewRule):
        """Add a custom review rule."""
        self.rules.append(rule)
        logger.info(f"Added review rule: {rule.name}")
    
    def _get_changed_files(self, commit: str, repo_path: str) -> List[str]:
        """Get list of files changed in a commit."""
        try:
            result = subprocess.run(
                ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", commit],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            return [f for f in result.stdout.strip().split("\n") if f]
        except subprocess.CalledProcessError:
            return []
    
    def _get_latest_commit(self, repo_path: str) -> str:
        """Get the latest commit hash."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return ""
    
    def _check_file(self, file_path: str, repo_path: str) -> List[ReviewIssue]:
        """Run all rules against a file."""
        issues = []
        full_path = Path(repo_path) / file_path
        
        if not full_path.exists():
            return issues
        
        # Determine language from extension
        ext = full_path.suffix.lower()
        lang_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "javascript",
            ".java": "java",
            ".go": "go",
            ".rs": "rust",
            ".php": "php",
        }
        language = lang_map.get(ext, "")
        
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception:
            return issues
        
        for rule in self.rules:
            if not rule.enabled:
                continue
            if rule.languages and language not in rule.languages:
                continue
            if not rule.pattern:
                continue
            
            import re
            pattern = re.compile(rule.pattern, re.IGNORECASE)
            
            for line_num, line in enumerate(lines, 1):
                if pattern.search(line):
                    issues.append(ReviewIssue(
                        file=file_path,
                        line=line_num,
                        severity=rule.severity,
                        category=rule.category,
                        message=rule.message,
                        suggestion=rule.suggestion,
                    ))
        
        return issues
    
    def _run_ai_review(self, files: List[str], repo_path: str) -> List[ReviewIssue]:
        """Run AI-based code review."""
        if self.engine is None:
            return []
        
        issues = []
        
        for file_path in files[:5]:  # Limit to first 5 files for performance
            full_path = Path(repo_path) / file_path
            if not full_path.exists():
                continue
            
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()[:4000]  # Limit content size
            except Exception:
                continue
            
            prompt = f"""Review the following code for issues. Be specific about line numbers and severity.

File: {file_path}

```
{content}
```

Identify any security vulnerabilities, bugs, performance issues, or style problems.
Format each issue as:
LINE: <line_number>
SEVERITY: <critical|high|medium|low|info>
CATEGORY: <security|bug|performance|style|documentation>
MESSAGE: <description>
SUGGESTION: <how to fix>
"""
            
            try:
                response = self.engine.process(prompt)
                text = response.get("response", "")
                
                # Parse issues from response
                file_issues = self._parse_ai_issues(text, file_path)
                issues.extend(file_issues)
            except Exception as e:
                logger.warning(f"AI review failed for {file_path}: {e}")
        
        return issues
    
    def _parse_ai_issues(self, text: str, file_path: str) -> List[ReviewIssue]:
        """Parse AI review response into structured issues."""
        issues = []
        
        # Simple parsing - look for LINE: patterns
        import re
        pattern = r'LINE:\s*(\d+)\s*\nSEVERITY:\s*(\w+)\s*\nCATEGORY:\s*(\w+)\s*\nMESSAGE:\s*(.+?)\nSUGGESTION:\s*(.+?)(?=\nLINE:|\Z)'
        
        for match in re.finditer(pattern, text, re.DOTALL):
            line = int(match.group(1))
            severity = match.group(2).lower()
            category = match.group(3).lower()
            message = match.group(4).strip()
            suggestion = match.group(5).strip()
            
            issues.append(ReviewIssue(
                file=file_path,
                line=line,
                severity=severity,
                category=category,
                message=message,
                suggestion=suggestion,
            ))
        
        return issues
    
    def _calculate_score(self, issues: List[ReviewIssue], file_count: int) -> float:
        """Calculate review score (0-100)."""
        if file_count == 0:
            return 100.0
        
        # Base score
        score = 100.0
        
        # Deduct for issues
        severity_weights = {
            "critical": -20,
            "high": -10,
            "medium": -5,
            "low": -2,
            "info": -0.5,
        }
        
        for issue in issues:
            score += severity_weights.get(issue.severity, -1)
        
        # Normalize by file count
        score = max(0.0, min(100.0, score))
        
        return round(score, 1)
    
    def _generate_summary(self, files: List[str], issues: List[ReviewIssue],
                          verdict: str, score: float) -> str:
        """Generate human-readable summary."""
        summary = f"Code Review Report\n"
        summary += f"==================\n\n"
        summary += f"Files reviewed: {len(files)}\n"
        summary += f"Issues found: {len(issues)}\n"
        summary += f"Score: {score}/100\n"
        summary += f"Verdict: {verdict.upper()}\n\n"
        
        if issues:
            summary += "Issues by severity:\n"
            for severity in ["critical", "high", "medium", "low", "info"]:
                count = sum(1 for i in issues if i.severity == severity)
                if count > 0:
                    summary += f"  {severity}: {count}\n"
            
            summary += "\nTop issues:\n"
            for issue in sorted(issues, key=lambda i: ["critical", "high", "medium", "low", "info"].index(i.severity))[:5]:
                summary += f"  [{issue.severity.upper()}] {issue.file}:{issue.line} - {issue.message}\n"
        
        return summary
    
    def _parse_diff_files(self, diff_text: str) -> List[str]:
        """Parse files from diff text."""
        import re
        files = re.findall(r'^diff --git a/(.+) b/', diff_text, re.MULTILINE)
        return files
    
    def _format_review_comment(self, report: ReviewReport) -> str:
        """Format review report as GitHub comment."""
        comment = f"## CrackedCode Review Bot\n\n"
        comment += f"**Verdict:** {report.verdict.upper()}\n"
        comment += f"**Score:** {report.score}/100\n"
        comment += f"**Files reviewed:** {len(report.files_reviewed)}\n"
        comment += f"**Issues found:** {len(report.issues)}\n\n"
        
        if report.issues:
            comment += "### Issues\n\n"
            for issue in sorted(report.issues, key=lambda i: ["critical", "high", "medium", "low", "info"].index(i.severity))[:10]:
                emoji = {"critical": "ðŸ”´", "high": "ðŸŸ ", "medium": "ðŸŸ¡", "low": "ðŸ”µ", "info": "âšª"}.get(issue.severity, "âšª")
                comment += f"{emoji} **{issue.severity.upper()}** `{issue.file}:{issue.line}`\n"
                comment += f"   {issue.message}\n"
                if issue.suggestion:
                    comment += f"   ðŸ’¡ {issue.suggestion}\n"
                comment += "\n"
        
        return comment


def get_review_bot(engine=None, github_client=None) -> CodeReviewBot:
    """Get the global code review bot."""
    return CodeReviewBot(engine=engine, github_client=github_client)

