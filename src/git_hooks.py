"""Git Hooks v2.9.4 - Pre-commit code review and security scanning.

Install a pre-commit hook that runs the code review bot on every commit.
Blocks commits with critical issues, warns on high/medium issues.

Usage:
    # Install hook
    python src/main.py install-hook

    # Or programmatically
    from src.git_hooks import install_precommit_hook
    install_precommit_hook()

    # Uninstall
    python src/main.py uninstall-hook
"""

import os
import stat
import subprocess
import sys
from pathlib import Path
from typing import Optional

from src.logger_config import get_logger

logger = get_logger("GitHooks")


# ── Hook Templates ─────────────────────────────────────────────────────────

PRE_COMMIT_TEMPLATE = '''#!/usr/bin/env python3
"""CrackedCode Pre-commit Hook - Auto-installed."""

import subprocess
import sys

def main():
    print("🔍 CrackedCode Pre-commit Review...")
    
    try:
        # Run code review on staged files
        result = subprocess.run(
            [sys.executable, "-c", ""
from src.code_review_bot import get_review_bot
bot = get_review_bot()
report = bot.review_commit('HEAD', repo_path='.')
print(f"VERDICT: {report.verdict}")
print(f"SCORE: {report.score}/100")
print(f"ISSUES: {len(report.issues)}")
for issue in sorted(report.issues, key=lambda i: ['critical','high','medium','low','info'].index(i.severity))[:10]:
    print(f"  [{issue.severity.upper()}] {issue.file}:{issue.line} - {issue.message}")
if report.verdict == 'fail':
    sys.exit(1)
            """],
            capture_output=True,
            text=True,
            timeout=60,
        )
        
        print(result.stdout)
        if result.returncode != 0:
            print("❌ Commit blocked: Critical issues found")
            print("   Use --no-verify to bypass (not recommended)")
            sys.exit(1)
        
        print("✅ Pre-commit review passed")
        sys.exit(0)
    except Exception as e:
        print(f"⚠️  Pre-commit review failed: {e}")
        print("   Allowing commit (review could not run)")
        sys.exit(0)

if __name__ == "__main__":
    main()
'''


# ── Hook Manager ───────────────────────────────────────────────────────────

class GitHookManager:
    """Manage Git hooks for CrackedCode."""
    
    def __init__(self, repo_path: str = "."):
        self.repo_path = Path(repo_path)
        self.git_dir = self._find_git_dir()
        self.hooks_dir = self.git_dir / "hooks" if self.git_dir else None
    
    def _find_git_dir(self) -> Optional[Path]:
        """Find the .git directory."""
        current = self.repo_path.resolve()
        while current != current.parent:
            git_dir = current / ".git"
            if git_dir.exists():
                return git_dir
            current = current.parent
        return None
    
    def is_git_repo(self) -> bool:
        """Check if we're in a git repository."""
        return self.git_dir is not None
    
    def hook_exists(self, name: str = "pre-commit") -> bool:
        """Check if a hook already exists."""
        if not self.hooks_dir:
            return False
        hook_path = self.hooks_dir / name
        return hook_path.exists()
    
    def install_precommit(self, force: bool = False) -> bool:
        """Install the pre-commit hook."""
        if not self.is_git_repo():
            logger.error("Not a git repository")
            return False
        
        if not self.hooks_dir:
            logger.error("Could not find hooks directory")
            return False
        
        self.hooks_dir.mkdir(parents=True, exist_ok=True)
        hook_path = self.hooks_dir / "pre-commit"
        
        if hook_path.exists() and not force:
            logger.warning("Pre-commit hook already exists. Use force=True to overwrite.")
            return False
        
        # Write hook
        hook_path.write_text(PRE_COMMIT_TEMPLATE, encoding="utf-8")
        
        # Make executable
        hook_path.chmod(hook_path.stat().st_mode | stat.S_IEXEC)
        
        logger.info(f"Installed pre-commit hook to {hook_path}")
        return True
    
    def uninstall_precommit(self) -> bool:
        """Remove the pre-commit hook."""
        if not self.hooks_dir:
            return False
        
        hook_path = self.hooks_dir / "pre-commit"
        if not hook_path.exists():
            logger.info("No pre-commit hook to uninstall")
            return True
        
        # Check if it's our hook
        content = hook_path.read_text(encoding="utf-8")
        if "CrackedCode Pre-commit Hook" not in content:
            logger.warning("Pre-commit hook was not installed by CrackedCode. Skipping.")
            return False
        
        hook_path.unlink()
        logger.info("Uninstalled pre-commit hook")
        return True
    
    def run_precommit(self) -> bool:
        """Run the pre-commit review manually."""
        from src.code_review_bot import get_review_bot
        
        print("🔍 Running CrackedCode pre-commit review...")
        
        bot = get_review_bot()
        report = bot.review_commit("HEAD", repo_path=str(self.repo_path))
        
        print(f"\n{'='*60}")
        print(f"VERDICT: {report.verdict.upper()}")
        print(f"SCORE: {report.score}/100")
        print(f"ISSUES: {len(report.issues)}")
        print(f"{'='*60}\n")
        
        if report.issues:
            print("Top issues:")
            severity_order = ["critical", "high", "medium", "low", "info"]
            sorted_issues = sorted(report.issues, key=lambda i: severity_order.index(i.severity))
            for issue in sorted_issues[:10]:
                emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵", "info": "⚪"}.get(issue.severity, "⚪")
                print(f"{emoji} [{issue.severity.upper()}] {issue.file}:{issue.line}")
                print(f"   {issue.message}")
                if issue.suggestion:
                    print(f"   💡 {issue.suggestion}")
                print()
        
        if report.verdict == "fail":
            print("❌ Commit would be blocked: Critical issues found")
            return False
        elif report.verdict == "conditional":
            print("⚠️  Commit would be warned: High severity issues found")
            return True
        else:
            print("✅ Review passed")
            return True
    
    def get_status(self) -> dict:
        """Get hook installation status."""
        return {
            "is_git_repo": self.is_git_repo(),
            "git_dir": str(self.git_dir) if self.git_dir else None,
            "hooks_dir": str(self.hooks_dir) if self.hooks_dir else None,
            "pre_commit_installed": self.hook_exists("pre-commit"),
            "pre_commit_is_crackedcode": False,
        }


def install_precommit_hook(repo_path: str = ".", force: bool = False) -> bool:
    """Install the CrackedCode pre-commit hook."""
    manager = GitHookManager(repo_path=repo_path)
    return manager.install_precommit(force=force)


def uninstall_precommit_hook(repo_path: str = ".") -> bool:
    """Uninstall the CrackedCode pre-commit hook."""
    manager = GitHookManager(repo_path=repo_path)
    return manager.uninstall_precommit()


def run_precommit_review(repo_path: str = ".") -> bool:
    """Run the pre-commit review manually."""
    manager = GitHookManager(repo_path=repo_path)
    return manager.run_precommit()
