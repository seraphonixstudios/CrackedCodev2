#!/usr/bin/env python3
"""
CrackedCode Git Panel - Sidebar widget for Git integration
Shows branch status, file states, diffs, and commit operations.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Dict, List, Callable

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTreeWidget, QTreeWidgetItem, QLineEdit, QTextEdit,
    QDialog, QSplitter, QMenu, QMessageBox, QCheckBox,
    QGroupBox, QScrollArea, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QBrush, QAction

from src.git_integration import GitIntegration, GitStatus, GitDiff
from src.logger_config import get_logger

logger = get_logger("GitPanel")

# Color constants matching Atlantean theme
ATLAN_GREEN = "#00FF41"
ATLAN_RED = "#FF3333"
ATLAN_GOLD = "#FFD700"
ATLAN_CYAN = "#00FFFF"
ATLAN_PURPLE = "#9D00FF"
ATLAN_ORANGE = "#FF8C00"
ATLAN_DARK = "#0a0a0a"
ATLAN_MEDIUM = "#1a1a1a"

STATUS_COLORS = {
    "modified": ATLAN_ORANGE,
    "staged": ATLAN_GREEN,
    "untracked": ATLAN_GOLD,
    "conflict": ATLAN_RED,
    "deleted": ATLAN_RED,
    "renamed": ATLAN_CYAN,
}


class DiffViewerDialog(QDialog):
    """Dialog showing diff for a specific file."""

    def __init__(self, filepath: str, diff_text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"DIFF: {filepath}")
        self.setMinimumSize(700, 500)
        self._init_ui(diff_text)

    def _init_ui(self, diff_text: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self.diff_edit = QTextEdit(self)
        self.diff_edit.setReadOnly(True)
        self.diff_edit.setFont(QFont("Consolas", 10))
        self.diff_edit.setPlainText(diff_text)
        self.diff_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: #050505;
                color: {ATLAN_GREEN};
                border: 1px solid #333;
                border-radius: 6px;
                padding: 8px;
            }}
        """)
        layout.addWidget(self.diff_edit)

        close_btn = QPushButton("CLOSE", self)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)

        self._highlight_diff()

    def _highlight_diff(self):
        """Apply basic syntax highlighting to diff text."""
        from PyQt6.QtGui import QTextCharFormat, QColor

        doc = self.diff_edit.document()
        fmt_add = QTextCharFormat()
        fmt_add.setBackground(QBrush(QColor(0, 64, 0)))
        fmt_add.setForeground(QBrush(QColor(ATLAN_GREEN)))

        fmt_del = QTextCharFormat()
        fmt_del.setBackground(QBrush(QColor(64, 0, 0)))
        fmt_del.setForeground(QBrush(QColor(ATLAN_RED)))

        fmt_header = QTextCharFormat()
        fmt_header.setForeground(QBrush(QColor(ATLAN_CYAN)))
        fmt_header.setFontWeight(QFont.Weight.Bold)

        for i in range(doc.blockCount()):
            block = doc.findBlockByNumber(i)
            text = block.text()
            cursor = self.diff_edit.textCursor()
            cursor.setPosition(block.position())
            cursor.movePosition(cursor.MoveOperation.EndOfBlock, cursor.MoveMode.KeepAnchor)

            if text.startswith("+") and not text.startswith("+++"):
                cursor.setCharFormat(fmt_add)
            elif text.startswith("-") and not text.startswith("---"):
                cursor.setCharFormat(fmt_del)
            elif text.startswith("@@") or text.startswith("diff ") or text.startswith("index "):
                cursor.setCharFormat(fmt_header)


class GitPanelWidget(QWidget):
    """
    Git panel for the sidebar showing repository status,
    file states, and commit operations.
    """

    file_clicked = pyqtSignal(str)  # Emitted when user clicks a file
    status_changed = pyqtSignal()   # Emitted when git status changes

    def __init__(self, git: Optional[GitIntegration] = None, parent=None):
        super().__init__(parent)
        self.git = git or GitIntegration(".")
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self.refresh)
        self._refresh_timer.start(3000)  # Auto-refresh every 3s
        self._init_ui()
        self.refresh()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # Branch / status header
        self.branch_label = QLabel("BRANCH: —", self)
        self.branch_label.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
        self.branch_label.setStyleSheet(f"color: {ATLAN_CYAN};")
        layout.addWidget(self.branch_label)

        self.sync_label = QLabel("", self)
        self.sync_label.setFont(QFont("Consolas", 9))
        self.sync_label.setStyleSheet(f"color: {ATLAN_GOLD};")
        layout.addWidget(self.sync_label)

        # File tree
        self.files_tree = QTreeWidget(self)
        self.files_tree.setHeaderLabels(["File", "Status"])
        self.files_tree.setColumnWidth(0, 140)
        self.files_tree.setColumnWidth(1, 60)
        self.files_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.files_tree.customContextMenuRequested.connect(self._show_context_menu)
        self.files_tree.itemDoubleClicked.connect(self._on_file_double_clicked)
        self.files_tree.itemClicked.connect(self._on_file_clicked)
        self.files_tree.setStyleSheet(f"""
            QTreeWidget {{
                background-color: #050505;
                color: {ATLAN_GREEN};
                border: 1px solid #333;
                border-radius: 6px;
                outline: none;
            }}
            QTreeWidget::item {{
                padding: 4px;
                border-radius: 3px;
            }}
            QTreeWidget::item:selected {{
                background-color: {ATLAN_GREEN};
                color: {ATLAN_DARK};
            }}
            QHeaderView::section {{
                background-color: {ATLAN_MEDIUM};
                color: {ATLAN_GOLD};
                padding: 4px;
                border: 1px solid #333;
                font-weight: bold;
            }}
        """)
        layout.addWidget(self.files_tree, 1)

        # Commit section
        commit_group = QGroupBox("COMMIT", self)
        commit_layout = QVBoxLayout(commit_group)
        commit_layout.setContentsMargins(6, 10, 6, 6)
        commit_layout.setSpacing(6)

        self.commit_msg = QLineEdit(commit_group)
        self.commit_msg.setPlaceholderText("Commit message...")
        self.commit_msg.setStyleSheet(f"""
            QLineEdit {{
                background-color: #050505;
                color: {ATLAN_GREEN};
                border: 1px solid #333;
                border-radius: 6px;
                padding: 6px;
            }}
        """)
        commit_layout.addWidget(self.commit_msg)

        btn_row = QHBoxLayout()

        self.ai_commit_btn = QPushButton("AI MSG", commit_group)
        self.ai_commit_btn.setToolTip("Generate commit message from staged changes")
        self.ai_commit_btn.clicked.connect(self._generate_commit_message)
        btn_row.addWidget(self.ai_commit_btn)

        self.stage_all_btn = QPushButton("STAGE ALL", commit_group)
        self.stage_all_btn.setToolTip("Stage all changes")
        self.stage_all_btn.clicked.connect(self._stage_all)
        btn_row.addWidget(self.stage_all_btn)

        self.commit_btn = QPushButton("COMMIT", commit_group)
        self.commit_btn.setToolTip("Commit staged changes")
        self.commit_btn.clicked.connect(self._commit)
        self.commit_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ATLAN_GREEN};
                color: {ATLAN_DARK};
                border: none;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #00CC33; }}
        """)
        btn_row.addWidget(self.commit_btn)

        commit_layout.addLayout(btn_row)
        layout.addWidget(commit_group)

        # Quick actions
        actions_row = QHBoxLayout()

        self.pull_btn = QPushButton("PULL", self)
        self.pull_btn.setToolTip("git pull")
        self.pull_btn.clicked.connect(self._pull)
        actions_row.addWidget(self.pull_btn)

        self.push_btn = QPushButton("PUSH", self)
        self.push_btn.setToolTip("git push")
        self.push_btn.clicked.connect(self._push)
        actions_row.addWidget(self.push_btn)

        self.refresh_btn = QPushButton("↻", self)
        self.refresh_btn.setToolTip("Refresh git status")
        self.refresh_btn.setFixedWidth(32)
        self.refresh_btn.clicked.connect(self.refresh)
        actions_row.addWidget(self.refresh_btn)

        layout.addLayout(actions_row)

        # Status bar
        self.status_label = QLabel("Not a git repository", self)
        self.status_label.setFont(QFont("Consolas", 9))
        self.status_label.setStyleSheet("color: #666;")
        layout.addWidget(self.status_label)

    def refresh(self):
        """Refresh the git status display."""
        if not self.git.is_repo:
            self.status_label.setText("Not a git repository")
            self.branch_label.setText("BRANCH: —")
            self.sync_label.setText("")
            self.files_tree.clear()
            self.commit_btn.setEnabled(False)
            self.stage_all_btn.setEnabled(False)
            return

        try:
            info = self.git.get_status()

            # Update branch info
            self.branch_label.setText(f"BRANCH: {info.branch}")

            sync_text = ""
            if info.commits_ahead > 0:
                sync_text += f"↑{info.commits_ahead} "
            if info.commits_behind > 0:
                sync_text += f"↓{info.commits_behind}"
            self.sync_label.setText(sync_text)

            # Update file tree
            self.files_tree.clear()

            categories = [
                ("Staged", info.staged, "staged"),
                ("Modified", info.modified, "modified"),
                ("Untracked", info.untracked, "untracked"),
                ("Conflicts", info.conflicts, "conflict"),
            ]

            for cat_name, files, status_key in categories:
                if not files:
                    continue
                parent = QTreeWidgetItem(self.files_tree)
                parent.setText(0, f"{cat_name} ({len(files)})")
                parent.setText(1, "")
                parent.setFlags(parent.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                color = STATUS_COLORS.get(status_key, ATLAN_GREEN)
                parent.setForeground(0, QBrush(QColor(color)))
                parent.setFont(0, QFont("Consolas", 9, QFont.Weight.Bold))

                for f in files:
                    item = QTreeWidgetItem(parent)
                    item.setText(0, f)
                    item.setText(1, status_key.upper()[:3])
                    item.setForeground(0, QBrush(QColor(color)))
                    item.setForeground(1, QBrush(QColor(color)))
                    item.setFont(0, QFont("Consolas", 9))
                    item.setData(0, Qt.ItemDataRole.UserRole, (f, status_key))

            self.files_tree.expandAll()

            # Update status
            status_text = info.status.value.upper()
            self.status_label.setText(f"Status: {status_text}")
            self.status_label.setStyleSheet(f"color: {ATLAN_GREEN};")

            self.commit_btn.setEnabled(len(info.staged) > 0)
            self.stage_all_btn.setEnabled(
                len(info.modified) > 0 or len(info.untracked) > 0
            )

            self.status_changed.emit()

        except Exception as e:
            logger.error(f"Git refresh error: {e}")
            self.status_label.setText(f"Error: {e}")

    def _on_file_clicked(self, item: QTreeWidgetItem, column: int):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data:
            filepath, status = data
            self.file_clicked.emit(filepath)

    def _on_file_double_clicked(self, item: QTreeWidgetItem, column: int):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        filepath, status = data
        self._show_diff(filepath)

    def _show_context_menu(self, position):
        item = self.files_tree.itemAt(position)
        if not item:
            return

        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        filepath, status = data

        menu = QMenu(self)

        if status in ("modified", "untracked"):
            stage_action = QAction("Stage", self)
            stage_action.triggered.connect(lambda: self._stage_file(filepath))
            menu.addAction(stage_action)

        if status == "staged":
            unstage_action = QAction("Unstage", self)
            unstage_action.triggered.connect(lambda: self._unstage_file(filepath))
            menu.addAction(unstage_action)

        diff_action = QAction("View Diff", self)
        diff_action.triggered.connect(lambda: self._show_diff(filepath))
        menu.addAction(diff_action)

        menu.exec(self.files_tree.viewport().mapToGlobal(position))

    def _stage_file(self, filepath: str):
        try:
            self.git.stage_file(filepath)
            self.refresh()
        except Exception as e:
            logger.error(f"Stage error: {e}")

    def _unstage_file(self, filepath: str):
        try:
            import subprocess
            subprocess.run(
                ["git", "reset", "HEAD", filepath],
                cwd=self.git.git_root,
                capture_output=True,
                check=True,
            )
            self.refresh()
        except Exception as e:
            logger.error(f"Unstage error: {e}")

    def _stage_all(self):
        try:
            self.git.stage_all()
            self.refresh()
            logger.info("Staged all changes")
        except Exception as e:
            logger.error(f"Stage all error: {e}")

    def _show_diff(self, filepath: str):
        try:
            diffs = self.git.get_diff(filepath)
            if not diffs:
                QMessageBox.information(self, "Diff", "No diff available")
                return
            diff_text = f"Diff for {filepath}:\n"
            for d in diffs:
                diff_text += f"\n+{d.additions} -{d.deletions}  {d.file}\n"
            # Try to get raw diff
            try:
                _, raw, _ = self.git._run(["diff", filepath])
                if raw:
                    diff_text = raw
            except Exception:
                pass
            dlg = DiffViewerDialog(filepath, diff_text, self)
            dlg.exec()
        except Exception as e:
            logger.error(f"Diff error: {e}")

    def _commit(self):
        msg = self.commit_msg.text().strip()
        if not msg:
            QMessageBox.warning(self, "Commit", "Please enter a commit message")
            return
        try:
            if self.git.commit(msg):
                self.commit_msg.clear()
                self.refresh()
                logger.info(f"Committed: {msg[:50]}")
                if self.parent() and hasattr(self.parent(), "show_toast"):
                    self.parent().show_toast(f"Committed: {msg[:40]}")
            else:
                QMessageBox.warning(self, "Commit", "Commit failed")
        except Exception as e:
            logger.error(f"Commit error: {e}")
            QMessageBox.critical(self, "Commit Error", str(e))

    def _generate_commit_message(self):
        """Generate commit message using AI from staged diff."""
        try:
            staged_diff = self.git.get_staged_diff()
            if not staged_diff:
                QMessageBox.information(self, "AI Commit", "No staged changes to analyze")
                return

            diff_summary = "\n".join(
                f"{d.file}: +{d.additions}/-{d.deletions}" for d in staged_diff
            )

            # Try to use engine for AI generation
            engine = None
            if self.parent() and hasattr(self.parent(), "engine"):
                engine = self.parent().engine

            if engine:
                prompt = f"""Generate a concise git commit message (max 50 chars) for these changes:
{diff_summary}

Rules:
- Use imperative mood (e.g., 'add', 'fix', 'update')
- Be specific but brief
- No period at end
- Format: <type>: <description>

Commit message:"""
                response = engine.generate(prompt, max_tokens=50)
                if response and not response.startswith("Error"):
                    self.commit_msg.setText(response.strip().strip('"').strip("'"))
                    return

            # Fallback: simple heuristic
            files = [d.file for d in staged_diff]
            if len(files) == 1:
                msg = f"update {Path(files[0]).name}"
            else:
                types = set(Path(f).suffix for f in files if Path(f).suffix)
                if types:
                    msg = f"update {len(files)} files ({', '.join(types)})"
                else:
                    msg = f"update {len(files)} files"
            self.commit_msg.setText(msg)

        except Exception as e:
            logger.error(f"AI commit message error: {e}")
            QMessageBox.warning(self, "AI Commit", f"Could not generate message: {e}")

    def _pull(self):
        try:
            self.git._run(["pull"])
            self.refresh()
            if self.parent() and hasattr(self.parent(), "show_toast"):
                self.parent().show_toast("Pulled latest changes")
        except Exception as e:
            logger.error(f"Pull error: {e}")
            QMessageBox.critical(self, "Pull", str(e))

    def _push(self):
        try:
            self.git._run(["push"])
            self.refresh()
            if self.parent() and hasattr(self.parent(), "show_toast"):
                self.parent().show_toast("Pushed to remote")
        except Exception as e:
            logger.error(f"Push error: {e}")
            QMessageBox.critical(self, "Push", str(e))

    def set_repo(self, path: str):
        """Switch to a different repository."""
        self.git = GitIntegration(path)
        self.refresh()

    def get_current_branch(self) -> str:
        """Get current branch name."""
        if self.git.is_repo:
            return self.git.get_branch()
        return ""

    def shutdown(self):
        """Stop auto-refresh timer."""
        self._refresh_timer.stop()


__all__ = ["GitPanelWidget", "DiffViewerDialog"]
