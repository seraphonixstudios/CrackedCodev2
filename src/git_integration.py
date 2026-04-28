#!/usr/bin/env python3
"""
Git integration for CrackedCode sidebar
Shows diffs, commit status, and branch info
"""

import subprocess
import re
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class GitStatus(Enum):
    CLEAN = "clean"
    DIRTY = "dirty"
    AHEAD = "ahead"
    BEHIND = "behind"
    UNTRACKED = "untracked"
    CONFLICTED = "conflicted"


@dataclass
class GitCommit:
    hash: str
    short_hash: str
    message: str
    author: str
    timestamp: datetime
    branch: str


@dataclass
class GitDiff:
    file: str
    status: str
    additions: int = 0
    deletions: int = 0
    old_path: Optional[str] = None


@dataclass
class GitBranch:
    name: str
    is_current: bool
    is_remote: bool = False
    ahead: int = 0
    behind: int = 0


@dataclass
class GitInfo:
    root: Path
    branch: str
    status: GitStatus
    is_repo: bool = True
    commits_ahead: int = 0
    commits_behind: int = 0
    untracked: List[str] = field(default_factory=list)
    modified: List[str] = field(default_factory=list)
    staged: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)


class GitIntegration:
    UNTRACKED_STATUS = {"??", "A", "AM", "AD", "AU"}
    MODIFIED_STATUS = {"M", "MM", "RM", "D", "DM", "UD"}
    STAGED_STATUS = {"A", "R", "D", "M", "C", "U"}
    CONFLICT_STATUS = {"UU", "AA", "DD", "AU", "UA", "DU", "UD"}

    def __init__(self, root: str = "."):
        self.root = Path(root)
        self.git_root = self._find_git_root()

    def _run(self, args: list[str], capture: bool = True) -> Tuple[int, str, str]:
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=self.git_root,
                capture_output=capture,
                text=True,
                timeout=10
            )
            return result.returncode, result.stdout.strip(), result.stderr.strip()
        except Exception as e:
            return -1, "", str(e)

    def _find_git_root(self) -> Optional[Path]:
        if not (self.root / ".git").exists():
            return None

        _, out, _ = self._run(["rev-parse", "--show-toplevel"])
        if out:
            return Path(out)
        return self.root

    @property
    def is_repo(self) -> bool:
        return self.git_root is not None

    def get_branch(self) -> str:
        _, out, _ = self._run(["branch", "--show-current"])
        if not out:
            _, out, _ = self._run(["rev-parse", "--abbrev-ref", "HEAD"])
        return out or "HEAD"

    def get_branches(self) -> List[GitBranch]:
        _, out, _ = self._run(["branch", "-a"])
        if not out:
            return []

        branches: List[GitBranch] = []
        for line in out.split("\n"):
            line = line.strip()
            if not line:
                continue

            is_current = line.startswith("*")
            name = line.lstrip("* ").strip()

            is_remote = name.startswith("remotes/") or "/" in name

            branches.append(GitBranch(
                name=name,
                is_current=is_current,
                is_remote=is_remote
            ))

        return branches

    def get_status(self) -> GitInfo:
        if not self.is_repo:
            return GitInfo(
                root=self.root,
                branch="",
                status=GitStatus.CLEAN,
                is_repo=False
            )

        branch = self.get_branch()

        _, status_out, _ = self._run(["status", "--porcelain"])
        staged: list[str] = []
        modified: list[str] = []
        untracked: list[str] = []
        conflicts: list[str] = []

        for line in status_out.split("\n"):
            if len(line) < 3:
                continue

            index_status = line[0]
            worktree_status = line[1]
            filepath = line[3:].strip()

            if index_status == "?" or worktree_status == "?":
                untracked.append(filepath)
            elif index_status in self.CONFLICT_STATUS or worktree_status in self.CONFLICT_STATUS:
                conflicts.append(filepath)
            elif index_status in self.STAGED_STATUS or worktree_status in self.STAGED_STATUS:
                staged.append(filepath)
                if index_status not in self.STAGED_STATUS:
                    modified.append(filepath)
            elif worktree_status in self.MODIFIED_STATUS:
                modified.append(filepath)

        status = GitStatus.CLEAN
        if conflicts:
            status = GitStatus.CONFLICTED
        elif untracked or modified or staged:
            status = GitStatus.DIRTY
            if untracked:
                status = GitStatus.UNTRACKED

        _, ahead_out, _ = self._run(["rev-list", "--count", f"HEAD..origin/{branch}"])
        _, behind_out, _ = self._run(["rev-list", "--count", f"origin/{branch}..HEAD"])

        return GitInfo(
            root=self.git_root,
            branch=branch,
            status=status,
            is_repo=True,
            commits_ahead=int(ahead_out) if ahead_out.isdigit() else 0,
            commits_behind=int(behind_out) if behind_out.isdigit() else 0,
            untracked=untracked,
            modified=modified,
            staged=staged,
            conflicts=conflicts
        )

    def get_diff(self, file: str = "") -> List[GitDiff]:
        _, out, _ = self._run(["diff", "--numstat", file])
        if not out:
            return []

        diffs: List[GitDiff] = []
        for line in out.split("\n"):
            if not line:
                continue

            parts = line.split("\t")
            if len(parts) >= 3:
                add = int(parts[0]) if parts[0] != "-" else 0
                delete = int(parts[1]) if parts[1] != "-" else 0
                filepath = parts[2]

                diffs.append(GitDiff(
                    file=filepath,
                    status="M",
                    additions=add,
                    deletions=delete
                ))

        return diffs

    def get_staged_diff(self) -> List[GitDiff]:
        _, out, _ = self._run(["diff", "--cached", "--numstat"])
        if not out:
            return []

        diffs: List[GitDiff] = []
        for line in out.split("\n"):
            if not line:
                continue

            parts = line.split("\t")
            if len(parts) >= 3:
                add = int(parts[0]) if parts[0] != "-" else 0
                delete = int(parts[1]) if parts[1] != "-" else 0
                filepath = parts[2]

                diffs.append(GitDiff(
                    file=filepath,
                    status="S",
                    additions=add,
                    deletions=delete
                ))

        return diffs

    def get_recent_commits(self, count: int = 10) -> List[GitCommit]:
        _, out, _ = self._run([
            "log", "--format=%H|%h|%s|%an|%ai|%D",
            f"-{count}"
        ])

        if not out:
            return []

        commits: List[GitCommit] = []
        branch = self.get_branch()

        for line in out.split("\n"):
            if not line:
                continue

            parts = line.split("|")
            if len(parts) >= 5:
                try:
                    commits.append(GitCommit(
                        hash=parts[0],
                        short_hash=parts[1],
                        message=parts[2],
                        author=parts[3],
                        timestamp=datetime.fromisoformat(parts[4].replace(" ", "T")),
                        branch=branch
                    ))
                except (ValueError, IndexError):
                    continue

        return commits

    def stage_file(self, filepath: str) -> bool:
        code, _, err = self._run(["add", filepath])
        return code == 0

    def stage_all(self) -> bool:
        code, _, _ = self._run(["add", "-A"])
        return code == 0

    def commit(self, message: str) -> bool:
        self.stage_all()
        code, _, err = self._run(["commit", "-m", message])
        return code == 0

    def get_file_history(self, filepath: str, count: int = 10) -> List[GitCommit]:
        _, out, _ = self._run(["log", "--format=%H|%h|%s|%an|%ai", f"-{count}", "--", filepath])
        if not out:
            return []

        commits: List[GitCommit] = []
        for line in out.split("\n"):
            if not line:
                continue

            parts = line.split("|")
            if len(parts) >= 5:
                try:
                    commits.append(GitCommit(
                        hash=parts[0],
                        short_hash=parts[1],
                        message=parts[2],
                        author=parts[3],
                        timestamp=datetime.fromisoformat(parts[4].replace(" ", "T")),
                        branch=""
                    ))
                except ValueError:
                    continue

        return commits

    def format_status(self) -> str:
        info = self.get_status()

        if not info.is_repo:
            return "Not a git repository"

        lines = [f"Branch: {info.branch}"]

        if info.untracked:
            lines.append(f"Untracked: {len(info.untracked)}")
        if info.modified:
            lines.append(f"Modified: {len(info.modified)}")
        if info.staged:
            lines.append(f"Staged: {len(info.staged)}")
        if info.conflicts:
            lines.append(f"Conflicts: {len(info.conflicts)}")

        lines.append(f"Status: {info.status.value}")

        return "\n".join(lines)


def demo():
    print("=== GIT INTEGRATION DEMO ===\n")

    git = GitIntegration(".")

    if not git.is_repo:
        print("Error: Not a git repository")
        print(f"Checked path: {Path('.').resolve()}")
        return

    print(f"Repository root: {git.git_root}\n")

    print("--- BRANCH INFO ---")
    branches = git.get_branches()
    current = git.get_branch()
    print(f"Current branch: {current}")

    local_branches = [b for b in branches if not b.is_remote]
    remote_branches = [b for b in branches if b.is_remote]
    if local_branches:
        print(f"Local branches: {', '.join(b.name for b in local_branches[:5])}")
    if remote_branches:
        print(f"Remote branches: {len(remote_branches)}")

    print("\n--- GIT STATUS ---")
    info = git.get_status()
    print(f"Branch: {info.branch}")

    status_str = "clean" if info.status == GitStatus.CLEAN else "dirty"
    if info.status == GitStatus.CONFLICTED:
        status_str = "conflicted"
    elif info.untracked and not info.modified and not info.staged:
        status_str = "untracked files only"
    print(f"Working tree: {status_str}")

    if info.commits_ahead > 0 or info.commits_behind > 0:
        if info.commits_ahead > 0:
            print(f"{info.commits_ahead} commit(s) ahead of remote")
        if info.commits_behind > 0:
            print(f"{info.commits_behind} commit(s) behind remote")

    if info.staged:
        print(f"\nStaged ({len(info.staged)}):")
        for f in info.staged[:5]:
            print(f"  + {f}")
        if len(info.staged) > 5:
            print(f"  ... and {len(info.staged) - 5} more")

    if info.modified:
        print(f"\nModified ({len(info.modified)}):")
        for f in info.modified[:5]:
            print(f"  M {f}")
        if len(info.modified) > 5:
            print(f"  ... and {len(info.modified) - 5} more")

    if info.untracked:
        print(f"\nUntracked ({len(info.untracked)}):")
        for f in info.untracked[:5]:
            print(f"  ?? {f}")
        if len(info.untracked) > 5:
            print(f"  ... and {len(info.untracked) - 5} more")

    if info.conflicts:
        print(f"\nConflicted ({len(info.conflicts)}):")
        for f in info.conflicts:
            print(f"  UU {f}")

    if not (info.staged or info.modified or info.untracked or info.conflicts):
        print("No changes")

    print("\n--- RECENT COMMITS ---")
    commits = git.get_recent_commits(10)
    if not commits:
        print("No commits yet")
        return

    for i, c in enumerate(commits):
        date_str = c.timestamp.strftime("%Y-%m-%d %H:%M")
        msg = c.message[:60] + "..." if len(c.message) > 60 else c.message
        prefix = ">" if i == 0 else " "
        print(f"{prefix} {c.short_hash} | {date_str} | {c.author}")
        print(f"  {msg}")


if __name__ == "__main__":
    demo()