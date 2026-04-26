#!/usr/bin/env python3
"""
File watcher for CrackedCode - monitors project files for changes
"""

import time
import threading
from pathlib import Path
from typing import Callable, Dict, Set, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import hashlib
import logging

logger = logging.getLogger("FileWatcher")

ChangeType = Enum("ChangeType", ["CREATED", "MODIFIED", "DELETED", "MOVED"])


@dataclass
class FileChange:
    path: Path
    change_type: ChangeType
    timestamp: datetime = field(default_factory=datetime.now)
    old_path: Optional[Path] = None
    size: int = 0


class FileWatcher:
    DEFAULT_IGNORED = {
        "__pycache__", ".git", ".pytest_cache", ".venv", "venv",
        "node_modules", ".idea", ".vscode", ".DS_Store", "*.pyc",
        "*.pyo", "*.so", "*.dll", "*.dylib", ".env", ".env.local"
    }

    def __init__(
        self,
        root: str = ".",
        ignored: Set[str] | None = None,
        debounce: float = 0.5,
        on_change: Callable[[FileChange], None] | None = None
    ):
        self.root = Path(root)
        self.ignored = self.DEFAULT_IGNORED | (ignored or set())
        self.debounce = debounce
        self.on_change = on_change

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._file_hashes: Dict[Path, str] = {}
        self._lock = threading.Lock()

        self.changes: list[FileChange] = []
        self.stats = {"scans": 0, "changes": 0, "errors": 0}

    def _should_ignore(self, path: Path) -> bool:
        parts = path.parts
        for part in parts:
            for pattern in self.ignored:
                if pattern.startswith("*."):
                    if path.suffix == pattern[1:]:
                        return True
                elif part == pattern:
                    return True
        return False

    def _get_hash(self, path: Path) -> str:
        try:
            content = path.read_bytes()
            return hashlib.md5(content).hexdigest()
        except Exception:
            return ""

    def _scan(self) -> list[FileChange]:
        changes: list[FileChange] = []

        current_files: set[Path] = set()

        try:
            for p in self.root.rglob("*"):
                if not p.is_file():
                    continue
                if self._should_ignore(p):
                    continue
                current_files.add(p)

                if p not in self._file_hashes:
                    changes.append(FileChange(
                        path=p,
                        change_type=ChangeType.CREATED,
                        size=p.stat().st_size if p.exists() else 0
                    ))
                else:
                    current_hash = self._get_hash(p)
                    if current_hash != self._file_hashes[p]:
                        changes.append(FileChange(
                            path=p,
                            change_type=ChangeType.MODIFIED,
                            size=p.stat().st_size if p.exists() else 0
                        ))
                        self._file_hashes[p] = current_hash

        except Exception as e:
            logger.error(f"Scan error: {e}")
            self.stats["errors"] += 1

        deleted: list[Path] = []
        for path in list(self._file_hashes.keys()):
            if path not in current_files:
                deleted.append(path)
                changes.append(FileChange(
                    path=path,
                    change_type=ChangeType.DELETED
                ))

        for path in deleted:
            del self._file_hashes[path]

        for p in current_files:
            if p not in self._file_hashes:
                self._file_hashes[p] = self._get_hash(p)

        return changes

    def _watch_loop(self) -> None:
        logger.info(f"FileWatcher started: {self.root}")

        for p in self.root.rglob("*"):
            if p.is_file() and not self._should_ignore(p):
                self._file_hashes[p] = self._get_hash(p)

        while self._running:
            self.stats["scans"] += 1
            changes = self._scan()

            if changes:
                for change in changes:
                    self.stats["changes"] += 1
                    self.changes.append(change)
                    logger.info(f"Change: {change.change_type.name} {change.path}")

                    if self.on_change:
                        try:
                            self.on_change(change)
                        except Exception as e:
                            logger.error(f"Callback error: {e}")

            time.sleep(self.debounce)

        logger.info("FileWatcher stopped")

    def start(self) -> None:
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    def get_stats(self) -> Dict:
        return {
            **self.stats,
            "watching": len(self._file_hashes),
            "root": str(self.root)
        }

    def clear_changes(self) -> None:
        self.changes.clear()


def demo():
    print("=== FILE WATCHER DEMO ===\n")

    def on_change(change: FileChange) -> None:
        print(f"  {change.change_type.name}: {change.path}")

    watcher = FileWatcher(".", on_change=on_change, debounce=1.0)
    watcher.start()

    print("Watching for changes (Ctrl+C to stop)...\n")

    try:
        while True:
            time.sleep(1)
            if watcher.changes:
                print(f"\nStats: {watcher.get_stats()}\n")
                watcher.clear_changes()
    except KeyboardInterrupt:
        watcher.stop()
        print("\nStopped.")


if __name__ == "__main__":
    demo()