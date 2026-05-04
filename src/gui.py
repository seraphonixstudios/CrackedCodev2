import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import random
import time
import threading
import traceback
import io
import re
import base64
import hashlib
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QMenuBar, QMenu, QToolBar,
    QStatusBar, QLabel, QFileDialog, QMessageBox, QTabWidget,
    QListWidget, QListWidgetItem, QSplitter, QGroupBox, QCheckBox, QComboBox, QSpinBox,
    QScrollArea, QFrame, QDialog, QInputDialog, QProgressBar, QSlider, QTreeWidget,
    QTreeWidgetItem, QStackedWidget, QSizePolicy, QDockWidget, QToolTip
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QSettings, QUrl, QMimeData, QSize, QPropertyAnimation, QEasingCurve, QPoint
from PyQt6.QtGui import (
    QAction, QIcon, QFont, QColor, QTextCursor, QKeySequence,
    QGuiApplication, QDesktopServices, QPainter, QDragEnterEvent, QDropEvent, QPixmap, QImage, QPalette,
    QLinearGradient, QBrush, QFontMetrics, QTextCharFormat
)
from PyQt6.QtNetwork import QLocalSocket, QLocalServer

from src.engine import get_engine, CrackedCodeEngine, Intent

try:
    from src.voice_engine import (
        UnifiedVoiceEngine, VoiceConfig, CommandType,
        STTResult, TTSResult, VoiceCommand
    )
    VOICE_AVAILABLE = True
except ImportError:
    VOICE_AVAILABLE = False

from src.logger_config import get_logger

try:
    from src.gui_enhancements import (
        ToastNotification, ToastType, QuickActionsDialog,
        QuickActionItem, WelcomeWidget, EnhancedStatusBar,
        KeyboardShortcutHelper
    )
    ENHANCEMENTS_AVAILABLE = True
except ImportError as e:
    ENHANCEMENTS_AVAILABLE = False

try:
    from src.gui_git_panel import GitPanelWidget
    GIT_PANEL_AVAILABLE = True
except ImportError:
    GIT_PANEL_AVAILABLE = False

try:
    from src.file_watcher import FileWatcher, FileChange, ChangeType
    FILEWATCHER_AVAILABLE = True
except ImportError:
    FILEWATCHER_AVAILABLE = False

try:
    from src.gui_settings import SettingsDialog
    SETTINGS_AVAILABLE = True
except ImportError:
    SETTINGS_AVAILABLE = False

try:
    from src.gui_syntax import get_highlighter, HIGHLIGHTERS
    SYNTAX_AVAILABLE = True
except ImportError:
    SYNTAX_AVAILABLE = False

try:
    from src.reasoning import get_reasoning_engine, ReasoningType
    REASONING_AVAILABLE = True
except ImportError:
    REASONING_AVAILABLE = False

try:
    from src.tool_framework import get_tool_registry, ToolPermission, ToolCategory
    TOOLS_AVAILABLE = True
except ImportError:
    TOOLS_AVAILABLE = False

try:
    from src.plugin_system import (
        PluginRegistry, HookPoint, get_plugin_registry, execute_hook
    )
    PLUGINS_AVAILABLE = True
except ImportError:
    PLUGINS_AVAILABLE = False
    PluginRegistry = None
    HookPoint = None
    get_plugin_registry = None
    execute_hook = None

logger = get_logger("CrackedCodeGUI")

ATLAN_GREEN = "#00FF41"
ATLAN_CYAN = "#00FFFF"
ATLAN_GOLD = "#FFD700"
ATLAN_RED = "#FF3333"
ATLAN_PURPLE = "#9D00FF"
ATLAN_BLUE = "#0080FF"
ATLAN_ORANGE = "#FF8C00"
ATLAN_DARK = "#0a0a0a"
ATLAN_MEDIUM = "#1a1a1a"
ATLAN_LIGHT = "#2a2a2a"
ATLAN_BORDER = "#333333"

FILE_ICONS = {
    ".py": "", ".js": "", ".ts": "", ".html": "", ".css": "",
    ".json": "", ".md": "", ".txt": "", ".yml": "", ".yaml": "",
    ".toml": "", ".cfg": "", ".ini": "", ".xml": "", ".csv": "",
    ".sh": "", ".bat": "", ".ps1": "", ".rs": "", ".go": "",
    ".c": "", ".cpp": "", ".h": "", ".java": "",
}

EXT_COLORS = {
    ".py": ATLAN_GREEN, ".js": ATLAN_GOLD, ".ts": ATLAN_BLUE,
    ".html": ATLAN_ORANGE, ".css": ATLAN_PURPLE, ".json": ATLAN_CYAN,
    ".md": ATLAN_GREEN, ".txt": "#888888",
}

COMMAND_HISTORY = []
HISTORY_INDEX = -1


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NotificationType(Enum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class AgentTask:
    task_counter = 0
    
    def __init__(self, intent: str, prompt: str, agent: str = "Coder"):
        AgentTask.task_counter += 1
        self.task_id = f"task_{AgentTask.task_counter}"
        self.intent = intent
        self.prompt = prompt
        self.agent = agent
        self.status = TaskStatus.PENDING
        self.result = None
        self.error = None
        self.timestamp = time.time()
        self.start_time = None
        self.end_time = None

    @property
    def duration(self) -> float:
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0.0

    def start(self):
        self.status = TaskStatus.RUNNING
        self.start_time = time.time()

    def complete(self, result: str):
        self.status = TaskStatus.COMPLETED
        self.result = result
        self.end_time = time.time()

    def fail(self, error: str):
        self.status = TaskStatus.FAILED
        self.error = error
        self.end_time = time.time()

    def cancel(self):
        self.status = TaskStatus.CANCELLED
        self.end_time = time.time()

    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "intent": self.intent,
            "prompt": self.prompt,
            "agent": self.agent,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "duration": self.duration,
        }


class NotificationWidget(QFrame):
    def __init__(self, message: str, ntype: NotificationType = NotificationType.INFO, parent=None):
        super().__init__(parent)
        self.ntype = ntype
        self.setAutoFillBackground(True)
        self.setFixedHeight(40)
        
        self.opacity = 1.0
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 4)
        
        colors = {
            NotificationType.INFO: ATLAN_CYAN,
            NotificationType.SUCCESS: ATLAN_GREEN,
            NotificationType.WARNING: ATLAN_GOLD,
            NotificationType.ERROR: ATLAN_RED,
        }
        icons = {
            NotificationType.INFO: "i",
            NotificationType.SUCCESS: "+",
            NotificationType.WARNING: "!",
            NotificationType.ERROR: "x",
        }
        
        color = colors.get(ntype, ATLAN_CYAN)
        icon = icons.get(ntype, "i")
        
        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet(f"""
            background-color: {color};
            color: {ATLAN_DARK};
            font-weight: bold;
            border-radius: 10px;
            min-width: 20px;
            min-height: 20px;
            max-width: 20px;
            max-height: 20px;
            qproperty-alignment: AlignCenter;
        """)
        layout.addWidget(icon_lbl)
        
        msg_lbl = QLabel(message)
        msg_lbl.setStyleSheet(f"color: {color}; font-size: 11px;")
        layout.addWidget(msg_lbl)
        
        close_btn = QPushButton("x")
        close_btn.setFixedWidth(20)
        close_btn.setStyleSheet(f"color: {color}; border: none; font-weight: bold;")
        close_btn.clicked.connect(self.close_notification)
        layout.addWidget(close_btn)
        
        self.setStyleSheet(f"""
            NotificationWidget {{
                background-color: {ATLAN_MEDIUM};
                border: 1px solid {color};
                border-radius: 6px;
            }}
        """)
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.fade_out)
        self.timer.start(5000)

    def fade_out(self):
        self.opacity -= 0.1
        if self.opacity <= 0:
            self.close_notification()
        else:
            self.setGraphicsEffect(None)
            self.repaint()

    def close_notification(self):
        self.timer.stop()
        self.setParent(None)
        self.deleteLater()


class AgentOrchestrator:
    """GUI-facing orchestrator that wraps UnifiedOrchestrator.
    
    Provides visual agent status tracking while delegating actual
    execution to the unified orchestration system.
    """
    
    def __init__(self, gui_ref: Any = None, engine=None):
        self.gui = gui_ref
        self.engine = engine
        self._unified: Optional[Any] = None
        
        # Visual agent state (for display only)
        self.agents = {
            "Supervisor": {
                "role": "coordinates",
                "status": "idle",
                "capabilities": ["all", "delegate", "manage"],
                "icon": "S",
                "color": ATLAN_PURPLE,
                "tasks_completed": 0,
            },
            "Architect": {
                "role": "design",
                "status": "idle",
                "capabilities": ["planning", "architecture", "blueprint"],
                "icon": "A",
                "color": ATLAN_CYAN,
                "tasks_completed": 0,
            },
            "Coder": {
                "role": "implementation",
                "status": "idle",
                "capabilities": ["code", "write", "modify", "create"],
                "icon": "C",
                "color": ATLAN_GREEN,
                "tasks_completed": 0,
            },
            "Executor": {
                "role": "execution",
                "status": "idle",
                "capabilities": ["run", "execute", "test", "deploy"],
                "icon": "E",
                "color": ATLAN_GOLD,
                "tasks_completed": 0,
            },
            "Reviewer": {
                "role": "analysis",
                "status": "idle",
                "capabilities": ["review", "debug", "optimize", "fix"],
                "icon": "R",
                "color": ATLAN_RED,
                "tasks_completed": 0,
            },
            "Searcher": {
                "role": "discovery",
                "status": "idle",
                "capabilities": ["search", "find", "grep", "analyze"],
                "icon": "F",
                "color": ATLAN_GREEN,
                "tasks_completed": 0,
            },
        }
        
        # Legacy task tracking (for compatibility)
        self.tasks: List[AgentTask] = []
        self.task_queue: List[AgentTask] = []
        self.current_task: Optional[AgentTask] = None
        
        self.delegation_rules = {
            Intent.CODE: "Coder",
            Intent.DEBUG: "Reviewer",
            Intent.REVIEW: "Reviewer",
            Intent.BUILD: "Architect",
            Intent.EXECUTE: "Executor",
            Intent.SEARCH: "Searcher",
            Intent.HELP: "Supervisor",
            Intent.CHAT: "Coder",
        }
    
    @property
    def unified(self):
        """Get or create unified orchestrator."""
        if self._unified is None:
            from src.orchestrator import get_orchestrator
            self._unified = get_orchestrator(
                engine=self.engine,
                max_workers=4
            )
            # Set up callbacks
            self._unified.on_task_created = self._on_task_created
            self._unified.on_task_started = self._on_task_started
            self._unified.on_task_completed = self._on_task_completed
            self._unified.on_task_failed = self._on_task_failed
            self._unified.on_queue_changed = self._on_queue_changed
            self._unified.start()
        return self._unified
    
    def _on_task_created(self, task):
        """Callback when unified task is created."""
        # Update visual agent state
        agent_name = self._role_to_agent(task.agent.value if hasattr(task.agent, 'value') else str(task.agent))
        if agent_name in self.agents:
            self.agents[agent_name]["status"] = "active"
        self._update_gui()
    
    def _on_task_started(self, task):
        """Callback when unified task starts."""
        self._update_gui()
    
    def _on_task_completed(self, task):
        """Callback when unified task completes."""
        agent_name = self._role_to_agent(task.agent.value if hasattr(task.agent, 'value') else str(task.agent))
        if agent_name in self.agents:
            self.agents[agent_name]["status"] = "idle"
            self.agents[agent_name]["tasks_completed"] += 1
        self._update_gui()
    
    def _on_task_failed(self, task):
        """Callback when unified task fails."""
        agent_name = self._role_to_agent(task.agent.value if hasattr(task.agent, 'value') else str(task.agent))
        if agent_name in self.agents:
            self.agents[agent_name]["status"] = "idle"
        self._update_gui()
    
    def _on_queue_changed(self):
        """Callback when queue changes."""
        self._update_gui()
    
    def _role_to_agent(self, role: str) -> str:
        """Map orchestrator role to GUI agent name."""
        mapping = {
            "supervisor": "Supervisor",
            "architect": "Architect",
            "coder": "Coder",
            "executor": "Executor",
            "reviewer": "Reviewer",
            "searcher": "Searcher",
            "tester": "Reviewer",
            "debugger": "Reviewer",
            "documenter": "Supervisor",
        }
        return mapping.get(role.lower(), "Coder")
    
    def delegate(self, intent: Intent, prompt: str) -> Tuple[str, AgentTask]:
        """Delegate a task through the unified orchestrator.
        
        Also creates a legacy AgentTask for GUI display compatibility.
        """
        agent_name = self.delegation_rules.get(intent, "Coder")
        
        # Create legacy task for GUI display
        task = AgentTask(intent.value, prompt, agent_name)
        self.tasks.append(task)
        self.task_queue.append(task)
        self.agents[agent_name]["status"] = "active"
        
        # Submit to unified orchestrator
        try:
            unified_task = self.unified.create_task(
                prompt=prompt,
                intent=intent.value,
                priority=self.unified.TaskPriority.NORMAL,
            )
            self.unified.submit(unified_task)
            # Store mapping
            task._unified_id = unified_task.id
        except Exception as e:
            logger.warning(f"Unified orchestrator delegate failed: {e}")
        
        self._update_gui()
        return agent_name, task
    
    def complete_task(self, task_id: str, result: str):
        """Mark task as completed."""
        for task in self.tasks:
            if task.task_id == task_id:
                task.complete(result)
                if task.agent in self.agents:
                    self.agents[task.agent]["status"] = "idle"
                    self.agents[task.agent]["tasks_completed"] += 1
                self.current_task = None
                break
        self._update_gui()
    
    def fail_task(self, task_id: str, error: str):
        """Mark task as failed."""
        for task in self.tasks:
            if task.task_id == task_id:
                task.fail(error)
                if task.agent in self.agents:
                    self.agents[task.agent]["status"] = "idle"
                self.current_task = None
                break
        self._update_gui()
    
    def cancel_task(self, task_id: str):
        """Cancel a task."""
        for task in self.tasks:
            if task.task_id == task_id:
                task.cancel()
                # Also cancel in unified orchestrator
                if hasattr(task, '_unified_id'):
                    try:
                        self.unified.cancel_task(task._unified_id)
                    except Exception:
                        pass
                if task.agent in self.agents:
                    self.agents[task.agent]["status"] = "idle"
                if self.current_task and self.current_task.task_id == task_id:
                    self.current_task = None
                break
        self._update_gui()
    
    def get_active_agents(self) -> List[str]:
        """Get list of currently active agents."""
        return [name for name, data in self.agents.items() if data["status"] == "active"]
    
    def get_queue_status(self) -> Dict:
        """Get current queue status from unified orchestrator."""
        try:
            unified_status = self.unified.get_queue_status()
        except Exception:
            unified_status = {}
        
        # Combine with legacy status
        return {
            "pending": unified_status.get("pending", 0),
            "queued": unified_status.get("queued", 0),
            "running": unified_status.get("running", 0),
            "completed": unified_status.get("completed", 0),
            "failed": unified_status.get("failed", 0),
            "cancelled": unified_status.get("cancelled", 0),
            "active_agents": self.get_active_agents(),
            "current_task": self.current_task.to_dict() if self.current_task else None,
            "max_workers": unified_status.get("max_workers", 4),
            "running_tasks": unified_status.get("running_tasks", []),
        }
    
    def clear_completed(self):
        """Clear completed tasks from display."""
        self.tasks = [t for t in self.tasks if t.status in [TaskStatus.PENDING, TaskStatus.RUNNING]]
    
    def _update_gui(self):
        """Trigger GUI update."""
        if self.gui and hasattr(self.gui, 'update_orchestrator_display'):
            self.gui.update_orchestrator_display()


class MatrixOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.matrix_chars = "アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン0123456789@#$%&*"
        self.drops = []
        self.cols = 80
        for _ in range(self.cols):
            self.drops.append({"y": random.randint(-100, 0), "speed": random.uniform(0.5, 2.0)})
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_rain)
        self.timer.start(50)
        self.visible = False

    def toggle(self):
        self.visible = not self.visible
        if self.visible:
            self.timer.start(50)
        else:
            self.timer.stop()
            self.update()

    def update_rain(self):
        if not self.visible:
            return
        for drop in self.drops:
            drop["y"] += drop["speed"]
            if drop["y"] > self.height():
                drop["y"] = random.randint(-20, 0)
        self.update()

    def paintEvent(self, event):
        if not self.visible:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width() // max(self.cols, 1)
        for i, drop in enumerate(self.drops):
            color = QColor(0, 255, 65, random.randint(100, 200))
            painter.setPen(color)
            font = QFont("Consolas", 10)
            font.setBold(True)
            painter.setFont(font)
            char = random.choice(self.matrix_chars)
            if w > 0:
                painter.drawText(i * w, int(drop["y"]), w, 20, Qt.AlignmentFlag.AlignCenter, char)


class PulseIndicator(QFrame):
    def __init__(self, color: str = ATLAN_GREEN, parent=None):
        super().__init__(parent)
        self.setFixedSize(12, 12)
        self.color = QColor(color)
        self.pulse_value = 1.0
        self.pulse_dir = -1
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.pulse)
        self.timer.start(100)
        
        self.setStyleSheet(f"""
            PulseIndicator {{
                background-color: {color};
                border-radius: 6px;
            }}
        """)

    def pulse(self):
        self.pulse_value += self.pulse_dir * 0.05
        if self.pulse_value >= 1.0:
            self.pulse_value = 1.0
            self.pulse_dir = -1
        elif self.pulse_value <= 0.3:
            self.pulse_value = 0.3
            self.pulse_dir = 1
        
        alpha = int(255 * self.pulse_value)
        self.setStyleSheet(f"""
            PulseIndicator {{
                background-color: rgba({self.color.red()}, {self.color.green()}, {self.color.blue()}, {alpha});
                border-radius: 6px;
            }}
        """)

    def stop(self):
        self.timer.stop()


class TaskFilterWidget(QWidget):
    filter_changed = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        
    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        
        self.all_btn = QPushButton("ALL")
        self.pending_btn = QPushButton("PEND")
        self.running_btn = QPushButton("RUN")
        self.completed_btn = QPushButton("DONE")
        self.failed_btn = QPushButton("FAIL")
        
        for btn in [self.all_btn, self.pending_btn, self.running_btn, self.completed_btn, self.failed_btn]:
            btn.setFixedHeight(20)
            btn.setFixedWidth(40)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {ATLAN_LIGHT};
                    color: {ATLAN_GREEN};
                    border: 1px solid {ATLAN_BORDER};
                    font-size: 9px;
                    border-radius: 3px;
                }}
                QPushButton:checked {{
                    background-color: {ATLAN_GREEN};
                    color: {ATLAN_DARK};
                }}
            """)
        
        self.all_btn.setCheckable(True)
        self.all_btn.setChecked(True)
        self.pending_btn.setCheckable(True)
        self.running_btn.setCheckable(True)
        self.completed_btn.setCheckable(True)
        self.failed_btn.setCheckable(True)
        
        self.all_btn.clicked.connect(lambda: self.set_filter("all"))
        self.pending_btn.clicked.connect(lambda: self.set_filter("pending"))
        self.running_btn.clicked.connect(lambda: self.set_filter("running"))
        self.completed_btn.clicked.connect(lambda: self.set_filter("completed"))
        self.failed_btn.clicked.connect(lambda: self.set_filter("failed"))
        
        layout.addWidget(self.all_btn)
        layout.addWidget(self.pending_btn)
        layout.addWidget(self.running_btn)
        layout.addWidget(self.completed_btn)
        layout.addWidget(self.failed_btn)
        layout.addStretch()
        
    def set_filter(self, status: str):
        for btn in [self.all_btn, self.pending_btn, self.running_btn, self.completed_btn, self.failed_btn]:
            btn.setChecked(False)
        
        if status == "all":
            self.all_btn.setChecked(True)
        elif status == "pending":
            self.pending_btn.setChecked(True)
        elif status == "running":
            self.running_btn.setChecked(True)
        elif status == "completed":
            self.completed_btn.setChecked(True)
        elif status == "failed":
            self.failed_btn.setChecked(True)
            
        self.filter_changed.emit(status)


class TaskQueueWidget(QWidget):
    task_selected = pyqtSignal(str)
    
    def __init__(self, orchestrator: AgentOrchestrator):
        super().__init__()
        self.orchestrator = orchestrator
        self.current_filter = "all"
        self.init_ui()
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.refresh)
        self.update_timer.start(500)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        header_lbl = QLabel("TASK QUEUE")
        header_lbl.setStyleSheet(f"font-weight: bold; color: {ATLAN_GOLD}; padding: 2px;")
        header_layout.addWidget(header_lbl)
        
        self.clear_btn = QPushButton("CLR")
        self.clear_btn.setFixedHeight(20)
        self.clear_btn.setFixedWidth(30)
        self.clear_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ATLAN_RED};
                color: {ATLAN_DARK};
                border: none;
                font-size: 9px;
                border-radius: 3px;
                font-weight: bold;
            }}
        """)
        self.clear_btn.clicked.connect(self.clear_completed)
        header_layout.addWidget(self.clear_btn)
        
        layout.addWidget(header)
        
        self.filter_widget = TaskFilterWidget()
        self.filter_widget.filter_changed.connect(self.set_filter)
        layout.addWidget(self.filter_widget)
        
        self.task_list = QListWidget()
        self.task_list.itemClicked.connect(lambda item: self.task_selected.emit(item.data(Qt.ItemDataRole.UserRole)))
        self.task_list.itemDoubleClicked.connect(self.show_task_details)
        layout.addWidget(self.task_list)
        
        stats_layout = QHBoxLayout()
        self.pending_label = QLabel("Pending: 0")
        self.running_label = QLabel("Running: 0")
        self.completed_label = QLabel("Done: 0")
        stats_layout.addWidget(self.pending_label)
        stats_layout.addWidget(self.running_label)
        stats_layout.addWidget(self.completed_label)
        layout.addLayout(stats_layout)

    def set_filter(self, status: str):
        self.current_filter = status
        self.refresh()

    def clear_completed(self):
        self.orchestrator.clear_completed()
        self.refresh()

    def show_task_details(self, item):
        task_id = item.data(Qt.ItemDataRole.UserRole)
        for task in self.orchestrator.tasks:
            if task.task_id == task_id:
                details = f"Task: {task.task_id}\nAgent: {task.agent}\nIntent: {task.intent}\nStatus: {task.status.value}\nPrompt: {task.prompt}\nDuration: {task.duration:.2f}s"
                if task.result:
                    details += f"\nResult: {task.result[:200]}"
                if task.error:
                    details += f"\nError: {task.error}"
                QMessageBox.information(self, "Task Details", details)
                break

    def refresh(self):
        self.task_list.clear()
        status = self.orchestrator.get_queue_status()
        
        tasks = self.orchestrator.tasks[-15:]
        
        if self.current_filter != "all":
            tasks = [t for t in tasks if t.status.value == self.current_filter]
        
        for task in tasks:
            status_icon = {
                TaskStatus.PENDING: "",
                TaskStatus.RUNNING: "◐",
                TaskStatus.COMPLETED: "●",
                TaskStatus.FAILED: "x",
                TaskStatus.CANCELLED: "o",
            }.get(task.status, "?")
            
            item_text = f"{status_icon} [{task.agent}] {task.prompt[:35]}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, task.task_id)
            item.setToolTip(f"{task.task_id}\n{task.agent}: {task.prompt}")
            
            if task.status == TaskStatus.RUNNING:
                item.setBackground(QColor(ATLAN_MEDIUM))
                item.setForeground(QColor(ATLAN_GOLD))
            elif task.status == TaskStatus.COMPLETED:
                item.setBackground(QColor("#0a1a0a"))
                item.setForeground(QColor(ATLAN_GREEN))
            elif task.status == TaskStatus.FAILED:
                item.setBackground(QColor("#1a0a0a"))
                item.setForeground(QColor(ATLAN_RED))
            elif task.status == TaskStatus.PENDING:
                item.setForeground(QColor("#888888"))
            
            self.task_list.addItem(item)
        
        self.pending_label.setText(f"Pending: {status['pending']}")
        self.running_label.setText(f"Running: {status['running']}")
        self.completed_label.setText(f"Done: {status['completed']}")


class ReasoningPanelWidget(QWidget):
    """Panel displaying real-time agent reasoning chains and coherence metrics."""
    
    REASONING_COLORS = {
        "observation": ATLAN_CYAN,
        "analysis": ATLAN_GOLD,
        "hypothesis": ATLAN_PURPLE,
        "decision": ATLAN_GREEN,
        "action": ATLAN_BLUE,
        "reflection": ATLAN_ORANGE,
        "correction": ATLAN_RED,
        "inference": "#FF69B4",
    }
    
    def __init__(self, gui_ref: Any = None):
        super().__init__()
        self.gui = gui_ref
        self.reasoning_engine = get_reasoning_engine() if REASONING_AVAILABLE else None
        self.agent_items: Dict[str, QTreeWidgetItem] = {}
        self.max_events = 50
        self.init_ui()
        self._register_callback()
        
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.refresh_coherence)
        self.update_timer.start(2000)
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        # Header
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        header_lbl = QLabel("REASONING")
        header_lbl.setStyleSheet(f"font-weight: bold; color: {ATLAN_PURPLE}; padding: 2px;")
        header_layout.addWidget(header_lbl)
        
        self.coherence_lbl = QLabel("C: 1.00")
        self.coherence_lbl.setStyleSheet(f"color: {ATLAN_GREEN}; font-size: 10px; font-weight: bold;")
        self.coherence_lbl.setToolTip("Cross-agent coherence score")
        header_layout.addWidget(self.coherence_lbl)
        
        layout.addWidget(header)
        
        # Coherence bar
        self.coherence_bar = QProgressBar()
        self.coherence_bar.setRange(0, 100)
        self.coherence_bar.setValue(100)
        self.coherence_bar.setFixedHeight(6)
        self.coherence_bar.setTextVisible(False)
        self.coherence_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {ATLAN_DARK};
                border: 1px solid {ATLAN_BORDER};
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background-color: {ATLAN_GREEN};
                border-radius: 2px;
            }}
        """)
        layout.addWidget(self.coherence_bar)
        
        # Agent reasoning tree
        self.reasoning_tree = QTreeWidget()
        self.reasoning_tree.setHeaderHidden(True)
        self.reasoning_tree.setToolTip("Agent reasoning chains - double-click to expand")
        self.reasoning_tree.setStyleSheet(f"""
            QTreeWidget {{
                background-color: {ATLAN_DARK};
                border: 1px solid {ATLAN_BORDER};
                border-radius: 4px;
                color: {ATLAN_GREEN};
                font-size: 10px;
            }}
            QTreeWidget::item {{
                padding: 2px;
            }}
            QTreeWidget::item:hover {{
                background-color: {ATLAN_MEDIUM};
            }}
        """)
        layout.addWidget(self.reasoning_tree)
        
        # Recent events list
        events_header = QLabel("Recent Events")
        events_header.setStyleSheet(f"color: {ATLAN_GOLD}; font-size: 10px; font-weight: bold;")
        layout.addWidget(events_header)
        
        self.events_list = QListWidget()
        self.events_list.setMaximumHeight(120)
        self.events_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {ATLAN_DARK};
                border: 1px solid {ATLAN_BORDER};
                border-radius: 4px;
                color: {ATLAN_GREEN};
                font-size: 9px;
            }}
        """)
        layout.addWidget(self.events_list)
    
    def _register_callback(self):
        """Register with reasoning engine for live updates."""
        if self.reasoning_engine:
            self.reasoning_engine.add_callback(self._on_reasoning_event)
    
    def _on_reasoning_event(self, event: Dict[str, Any]):
        """Handle reasoning events from the engine."""
        event_type = event.get("type", "unknown")
        data = event.get("data", {})
        agent_id = data.get("agent_id", "system")
        
        # Stream to terminal if GUI reference available
        if self.gui and hasattr(self.gui, 'term'):
            if event_type == "chain_started":
                self.gui.term(f"[🧠 {agent_id}] Starting: {data.get('title', 'reasoning')}", level="reasoning")
            elif event_type == "chain_completed":
                self.gui.term(f"[🧠 {agent_id}] Decision: {data.get('decision', 'completed')[:60]}...", level="reasoning")
        
        # Add to recent events
        self._add_event(event)
    
    def _add_event(self, event: Dict[str, Any]):
        """Add event to the recent events list."""
        event_type = event.get("type", "unknown")
        data = event.get("data", {})
        agent_id = data.get("agent_id", "system")
        
        color = self.REASONING_COLORS.get(event_type.replace("_", ""), ATLAN_GREEN)
        
        if event_type == "chain_started":
            text = f"🧠 {agent_id}: {data.get('title', 'chain')}"
        elif event_type == "chain_completed":
            text = f"✓ {agent_id}: {data.get('decision', 'done')[:40]}"
        else:
            text = f"• {agent_id}: {event_type}"
        
        item = QListWidgetItem(text)
        item.setForeground(QColor(color))
        self.events_list.insertItem(0, item)
        
        while self.events_list.count() > self.max_events:
            self.events_list.takeItem(self.events_list.count() - 1)
    
    def refresh_coherence(self):
        """Refresh coherence metrics and agent reasoning display."""
        if not self.reasoning_engine:
            return
        
        try:
            report = self.reasoning_engine.get_coherence_report()
            coherence = report.get("cross_agent_coherence", {})
            overall = coherence.get("overall_coherence", 1.0)
            
            # Update coherence display
            self.coherence_lbl.setText(f"C: {overall:.2f}")
            self.coherence_bar.setValue(int(overall * 100))
            
            # Color-code coherence
            if overall >= 0.8:
                color = ATLAN_GREEN
            elif overall >= 0.6:
                color = ATLAN_GOLD
            elif overall >= 0.4:
                color = ATLAN_ORANGE
            else:
                color = ATLAN_RED
            
            self.coherence_lbl.setStyleSheet(f"color: {color}; font-size: 10px; font-weight: bold;")
            self.coherence_bar.setStyleSheet(f"""
                QProgressBar {{
                    background-color: {ATLAN_DARK};
                    border: 1px solid {ATLAN_BORDER};
                    border-radius: 3px;
                }}
                QProgressBar::chunk {{
                    background-color: {color};
                    border-radius: 2px;
                }}
            """)
            
            # Update agent tree
            self._update_agent_tree(report.get("agents", {}))
            
        except Exception as e:
            logger.warning(f"Reasoning panel refresh error: {e}")
    
    def _update_agent_tree(self, agents: Dict[str, Any]):
        """Update the agent reasoning tree."""
        current_agents = set(agents.keys())
        existing_agents = set(self.agent_items.keys())
        
        # Remove old agents
        for agent_id in existing_agents - current_agents:
            item = self.agent_items.pop(agent_id)
            root = self.reasoning_tree.invisibleRootItem()
            root.removeChild(item)
        
        # Add/update agents
        for agent_id, data in agents.items():
            if agent_id not in self.agent_items:
                item = QTreeWidgetItem()
                item.setText(0, f"{data.get('role', 'agent')} ({agent_id[:8]})")
                self.reasoning_tree.addTopLevelItem(item)
                self.agent_items[agent_id] = item
            else:
                item = self.agent_items[agent_id]
            
            # Update agent info
            coherence = data.get("coherence", 0.0)
            chains = data.get("chains", 0)
            steps = data.get("steps", 0)
            
            item.setText(0, f"{data.get('role', 'agent')} | C:{coherence:.2f} | {chains}ch {steps}st")
            
            # Color based on coherence
            if coherence >= 0.8:
                item.setForeground(0, QColor(ATLAN_GREEN))
            elif coherence >= 0.5:
                item.setForeground(0, QColor(ATLAN_GOLD))
            else:
                item.setForeground(0, QColor(ATLAN_RED))
            
            # Add recent decisions as children
            recent = data.get("recent_decisions", [])
            # Clear old children
            while item.childCount() > 0:
                item.removeChild(item.child(0))
            
            for dec in recent[-3:]:
                child = QTreeWidgetItem()
                child.setText(0, f"→ {dec.get('decision', '')[:30]} ({dec.get('confidence', 0):.2f})")
                conf = dec.get("confidence", 0)
                if conf >= 0.7:
                    child.setForeground(0, QColor(ATLAN_GREEN))
                elif conf >= 0.4:
                    child.setForeground(0, QColor(ATLAN_GOLD))
                else:
                    child.setForeground(0, QColor(ATLAN_RED))
                item.addChild(child)
        
        self.reasoning_tree.expandAll()


class ToolLogWidget(QWidget):
    """Panel displaying live tool execution log with expand/collapse details."""
    
    def __init__(self, gui_ref: Any = None):
        super().__init__()
        self.gui = gui_ref
        self.tool_registry = get_tool_registry() if TOOLS_AVAILABLE else None
        self.seen_count = 0
        self.init_ui()
        
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.refresh_log)
        self.update_timer.start(1500)
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        # Header
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        header_lbl = QLabel("TOOL LOG")
        header_lbl.setStyleSheet(f"font-weight: bold; color: {ATLAN_GOLD}; padding: 2px;")
        header_layout.addWidget(header_lbl)
        
        self.stats_lbl = QLabel("0 calls")
        self.stats_lbl.setStyleSheet(f"color: {ATLAN_GREEN}; font-size: 10px;")
        header_layout.addWidget(self.stats_lbl)
        header_layout.addStretch()
        
        # Permissions button
        perm_btn = QPushButton("PERMISSIONS")
        perm_btn.setToolTip("Toggle tool permissions")
        perm_btn.setFixedHeight(22)
        perm_btn.setStyleSheet(f"font-size: 9px; padding: 2px 6px;")
        perm_btn.clicked.connect(self.show_permissions_dialog)
        header_layout.addWidget(perm_btn)
        
        layout.addWidget(header)
        
        # Tool log tree
        self.log_tree = QTreeWidget()
        self.log_tree.setHeaderLabels(["Time", "Tool", "Status", "Duration"])
        self.log_tree.setColumnWidth(0, 70)
        self.log_tree.setColumnWidth(1, 110)
        self.log_tree.setColumnWidth(2, 60)
        self.log_tree.setColumnWidth(3, 55)
        self.log_tree.setToolTip("Tool execution log - double-click to expand details")
        self.log_tree.setStyleSheet(f"""
            QTreeWidget {{
                background-color: {ATLAN_DARK};
                border: 1px solid {ATLAN_BORDER};
                border-radius: 4px;
                color: {ATLAN_GREEN};
                font-size: 10px;
            }}
            QTreeWidget::item {{
                padding: 2px;
            }}
            QTreeWidget::item:hover {{
                background-color: {ATLAN_MEDIUM};
            }}
            QHeaderView::section {{
                background-color: {ATLAN_DARK};
                color: {ATLAN_GOLD};
                padding: 2px;
                font-size: 9px;
                border: 1px solid {ATLAN_BORDER};
            }}
        """)
        layout.addWidget(self.log_tree)
    
    def refresh_log(self):
        """Poll registry execution log and update tree."""
        if not self.tool_registry:
            return
        
        try:
            log = self.tool_registry.get_execution_log(limit=50)
            if len(log) == self.seen_count:
                return
            
            self.seen_count = len(log)
            self.log_tree.clear()
            
            for entry in reversed(log):
                success = entry.get("success", False)
                tool_name = entry.get("tool_name", "unknown")
                duration = entry.get("duration", 0.0)
                timestamp = entry.get("timestamp", 0)
                result = entry.get("result", {})
                error = entry.get("error", "")
                observation = entry.get("observation", "")
                
                time_str = time.strftime("%H:%M:%S", time.localtime(timestamp))
                
                item = QTreeWidgetItem()
                item.setText(0, time_str)
                item.setText(1, tool_name)
                item.setText(2, "OK" if success else "FAIL")
                item.setText(3, f"{duration:.2f}s")
                
                if success:
                    item.setForeground(2, QColor(ATLAN_GREEN))
                else:
                    item.setForeground(2, QColor(ATLAN_RED))
                
                self.log_tree.addTopLevelItem(item)
                
                # Add details as child
                if observation:
                    child = QTreeWidgetItem()
                    child.setText(0, f"📋 {observation[:100]}")
                    child.setForeground(0, QColor(ATLAN_CYAN))
                    item.addChild(child)
                
                if error:
                    child = QTreeWidgetItem()
                    child.setText(0, f"⚠ {error[:100]}")
                    child.setForeground(0, QColor(ATLAN_RED))
                    item.addChild(child)
                
                if isinstance(result, dict) and result:
                    for key, val in list(result.items())[:4]:
                        child = QTreeWidgetItem()
                        preview = str(val)[:80]
                        child.setText(0, f"  {key}: {preview}")
                        child.setForeground(0, QColor(ATLAN_GOLD))
                        item.addChild(child)
            
            # Update stats
            stats = self.tool_registry.get_stats()
            self.stats_lbl.setText(f"{stats.get('total_executions', 0)} calls")
            
        except Exception as e:
            logger.warning(f"Tool log refresh error: {e}")
    
    def show_permissions_dialog(self):
        """Show dialog to toggle tool permissions."""
        if not self.tool_registry:
            QMessageBox.information(self, "Tools", "Tool framework not available")
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Tool Permissions")
        dialog.setMinimumSize(350, 400)
        
        layout = QVBoxLayout(dialog)
        
        info = QLabel("Toggle permission for each tool. DANGEROUS tools are blocked by default.")
        info.setWordWrap(True)
        info.setStyleSheet(f"color: {ATLAN_GOLD}; font-size: 10px;")
        layout.addWidget(info)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        cl = QVBoxLayout(container)
        cl.setSpacing(2)
        
        for tool in self.tool_registry.list_tools():
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(2, 2, 2, 2)
            
            name_lbl = QLabel(tool.name)
            name_lbl.setStyleSheet(f"color: {ATLAN_GREEN}; font-size: 10px; min-width: 120px;")
            rl.addWidget(name_lbl)
            
            perm_lbl = QLabel(tool.permission.value.upper())
            perm_color = {
                "read": ATLAN_GREEN,
                "write": ATLAN_GOLD,
                "execute": ATLAN_ORANGE,
                "dangerous": ATLAN_RED,
            }.get(tool.permission.value, ATLAN_GREEN)
            perm_lbl.setStyleSheet(f"color: {perm_color}; font-size: 9px; min-width: 70px;")
            rl.addWidget(perm_lbl)
            
            cb = QCheckBox()
            cb.setChecked(self.tool_registry.is_allowed(tool.name))
            cb.stateChanged.connect(lambda state, tn=tool.name: self.tool_registry.set_permission(tn, bool(state)))
            rl.addWidget(cb)
            
            cl.addWidget(row)
        
        cl.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)
        
        close_btn = QPushButton("CLOSE")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        
        dialog.exec()


class AgentPanelWidget(QWidget):
    def __init__(self, orchestrator: AgentOrchestrator):
        super().__init__()
        self.orchestrator = orchestrator
        self.status_labels = {}
        self.pulse_indicators = {}
        self.init_ui()
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.refresh)
        self.update_timer.start(500)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        header = QLabel("AGENTS")
        header.setStyleSheet(f"font-weight: bold; color: {ATLAN_GOLD}; padding: 2px;")
        layout.addWidget(header)
        
        self.agent_widgets = {}
        for name, data in self.orchestrator.agents.items():
            agent_frame = self.create_agent_widget(name, data)
            self.agent_widgets[name] = agent_frame
            layout.addWidget(agent_frame)
        
        layout.addStretch()

    def create_agent_widget(self, name: str, data: Dict) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {ATLAN_MEDIUM};
                border: 1px solid {ATLAN_BORDER};
                border-radius: 6px;
                padding: 6px;
                margin: 2px;
            }}
            QFrame:hover {{
                border-color: {data['color']};
            }}
        """)
        
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(8, 4, 8, 4)
        
        icon_label = QLabel(data["icon"])
        icon_label.setStyleSheet(f"""
            background-color: {data["color"]};
            color: {ATLAN_DARK};
            font-weight: bold;
            border-radius: 12px;
            min-width: 24px;
            min-height: 24px;
            max-width: 24px;
            max-height: 24px;
            qproperty-alignment: AlignCenter;
        """)
        layout.addWidget(icon_label)
        
        info = QWidget()
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)
        
        name_label = QLabel(name)
        name_label.setStyleSheet(f"font-weight: bold; color: {data['color']};")
        info_layout.addWidget(name_label)
        
        status_row = QWidget()
        status_layout = QHBoxLayout(status_row)
        status_layout.setContentsMargins(0, 0, 0, 0)
        
        pulse = PulseIndicator(data["color"] if data["status"] == "active" else "#555555")
        self.pulse_indicators[name] = pulse
        status_layout.addWidget(pulse)
        
        self.status_labels[name] = QLabel(data["status"])
        self.status_labels[name].setStyleSheet(f"color: #888; font-size: 10px;")
        status_layout.addWidget(self.status_labels[name])
        
        status_layout.addStretch()
        
        info_layout.addWidget(status_row)
        
        tasks_lbl = QLabel(f"Done: {data.get('tasks_completed', 0)}")
        tasks_lbl.setStyleSheet("color: #666; font-size: 9px;")
        info_layout.addWidget(tasks_lbl)
        
        layout.addWidget(info)
        layout.addStretch()
        
        return frame

    def refresh(self):
        for name, data in self.orchestrator.agents.items():
            if name in self.status_labels:
                self.status_labels[name].setText(f"{data['status']} ({', '.join(data['capabilities'][:2])})")
            
            if name in self.pulse_indicators:
                color = data["color"] if data["status"] == "active" else "#555555"
                self.pulse_indicators[name].setStyleSheet(f"""
                    PulseIndicator {{
                        background-color: {color};
                        border-radius: 6px;
                    }}
                """)


class SearchableTerminal(QTextEdit):
    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        self.search_visible = False
        self.search_bar = None
        self.init_search()
        
    def init_search(self):
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search terminal... (Esc to close)")
        self.search_bar.setStyleSheet(f"""
            QLineEdit {{
                background-color: {ATLAN_LIGHT};
                color: {ATLAN_GREEN};
                border: 1px solid {ATLAN_GREEN};
                padding: 4px;
                border-radius: 4px;
                font-family: Consolas;
                font-size: 11px;
            }}
        """)
        self.search_bar.textChanged.connect(self.highlight_search)
        self.search_bar.setVisible(False)
        
    def toggle_search(self):
        self.search_visible = not self.search_visible
        self.search_bar.setVisible(self.search_visible)
        if self.search_visible:
            self.search_bar.setFocus()
            self.search_bar.clear()
        else:
            self.clear_highlights()
            
    def highlight_search(self, text: str):
        self.clear_highlights()
        if not text:
            return
            
        content = self.toPlainText()
        cursor = self.textCursor()
        cursor.beginEditBlock()
        
        format = QTextCharFormat()
        format.setBackground(QColor(ATLAN_GOLD))
        format.setForeground(QColor(ATLAN_DARK))
        
        start = 0
        while True:
            pos = content.find(text, start, Qt.CaseSensitivity.CaseInsensitive)
            if pos == -1:
                break
            cursor.setPosition(pos)
            cursor.setPosition(pos + len(text), QTextCursor.MoveMode.KeepAnchor)
            cursor.setCharFormat(format)
            start = pos + len(text)
            
        cursor.endEditBlock()
        
    def clear_highlights(self):
        cursor = self.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        format = QTextCharFormat()
        format.setBackground(QColor("transparent"))
        format.setForeground(QColor(ATLAN_GREEN))
        cursor.setCharFormat(format)


class CrackedCodeGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = {}
        self.settings = QSettings("SeraphonixStudios", "CrackedCode")
        self.engine = None
        self.voice: Optional[Any] = None
        self.voice_recording = False
        self.project_path: Optional[Path] = None
        self.status_labels = {}
        self.current_file: Optional[Path] = None
        self.open_files: Dict[str, QTextEdit] = {}
        self.modified_tabs = set()
        self.streaming_active = False
        self.notification_queue = []
        self.matrix_visible = False
        self.file_watcher: Optional[Any] = None
        self._auto_save_timer = QTimer(self)
        self._auto_save_timer.setSingleShot(True)
        self._auto_save_timer.timeout.connect(self._auto_save_current_file)
        self._externally_modified_files: Set[str] = set()
        
        self.load_config()
        self.setup_atlan_theme()
        self.init_engine()
        self.init_orchestrator()
        self.init_ui()
        self.init_voice()
        self.init_matrix()
        self.init_clipboard()
        self.init_file_watcher()
        self.restore_state()
        self.setup_paste_handler()
        
        logger.info("CrackedCode GUI v2.6.4 started")

    def init_orchestrator(self):
        self.orchestrator = AgentOrchestrator(gui_ref=self)
        self.update_orchestrator_display()
        logger.info("Agent orchestrator initialized")

    def update_orchestrator_display(self):
        if hasattr(self, 'agent_panel'):
            self.agent_panel.refresh()
        if hasattr(self, 'task_queue'):
            self.task_queue.refresh()

    def init_clipboard(self):
        self.clipboard = QGuiApplication.clipboard()
        self.pending_image: Optional[QImage] = None
        self.last_paste_hash = ""

    def init_file_watcher(self):
        """Initialize file watcher for project directory monitoring."""
        if not FILEWATCHER_AVAILABLE:
            logger.info("FileWatcher not available")
            return
        self.file_watcher = None
        logger.info("FileWatcher ready (will activate when project opens)")

    def _start_watching_project(self, path: str):
        """Start watching a project directory for external changes."""
        if not FILEWATCHER_AVAILABLE:
            return
        if self.file_watcher:
            self.file_watcher.stop()
        self.file_watcher = FileWatcher(
            root=path,
            debounce=2.0,
            on_change=self._on_external_file_change
        )
        self.file_watcher.start()
        logger.info(f"FileWatcher started: {path}")

    def _on_external_file_change(self, change: FileChange):
        """Handle external file changes detected by watcher."""
        filepath = str(change.path)
        filename = change.path.name
        
        if change.change_type == ChangeType.MODIFIED:
            # Check if file is open in editor
            if filename in self.open_files:
                editor = self.open_files[filename]
                # Mark as externally modified
                self._externally_modified_files.add(filename)
                self.term(f"External change detected: {filename}", level="warning")
                self.show_toast(f"Externally modified: {filename}", ToastType.WARNING)
            else:
                # Just refresh file tree
                self.refresh_file_tree()
        elif change.change_type == ChangeType.CREATED:
            self.refresh_file_tree()
            self.term(f"New file: {filename}", level="info")
        elif change.change_type == ChangeType.DELETED:
            self.refresh_file_tree()
            self.term(f"File deleted: {filename}", level="warning")

    def _trigger_auto_save(self):
        """Trigger auto-save after idle period."""
        auto_save_enabled = self.config.get("auto_save", True)
        auto_save_delay = self.config.get("auto_save_delay_ms", 3000)
        if auto_save_enabled and self.current_file:
            self._auto_save_timer.stop()
            self._auto_save_timer.setInterval(auto_save_delay)
            self._auto_save_timer.start()

    def _auto_save_current_file(self):
        """Perform auto-save of current file."""
        if self.current_file and self.current_file.exists():
            try:
                content = self.editor.toPlainText()
                self.current_file.write_text(content)
                self.term(f"Auto-saved {self.current_file.name}", level="success")
                # Remove modified indicator
                current = self.tab_widget.currentIndex()
                tab_name = self.tab_widget.tabText(current)
                if tab_name.startswith("*"):
                    self.tab_widget.setTabText(current, tab_name[1:])
                if tab_name in self.modified_tabs:
                    self.modified_tabs.remove(tab_name)
            except Exception as e:
                logger.error(f"Auto-save failed: {e}")

    def setup_paste_handler(self):
        if hasattr(self, 'editor'):
            self.editor.installEventFilter(self)

    def init_engine(self):
        try:
            self.engine = get_engine(self.config)
            logger.info(f"Engine model: {self.engine.model}")
            status = self.engine.get_status()
            self.update_status(status)
        except Exception as e:
            logger.error(f"Engine init failed: {e}")

    def init_voice(self):
        if not VOICE_AVAILABLE:
            if hasattr(self, 'terminal'):
                self.term("[VOICE: not available - install dependencies]")
            if hasattr(self, 'voice_btn'):
                self.voice_btn.setEnabled(False)
            return

        try:
            voice_cfg = VoiceConfig(
                stt_model_size=self.config.get("whisper_size", "base"),
                tts_voice=self.config.get("tts_voice", "default"),
                tts_gender=self.config.get("tts_gender", "female"),
                tts_rate=self.config.get("tts_rate", 175),
            )
            self.voice = UnifiedVoiceEngine(voice_cfg)
            self.voice.initialize(load_stt=True, load_tts=True)

            # Register command handlers that map to GUI actions
            self._register_voice_command_handlers()

            status = self.voice.status
            backend = status.get("tts_backend", "fallback")
            if hasattr(self, 'terminal'):
                self.term(f"[VOICE: ready | TTS={backend}]")
            logger.info(f"Voice engine initialized: {status}")
        except Exception as e:
            logger.error(f"Voice init failed: {e}")
            if hasattr(self, 'terminal'):
                self.term(f"[VOICE ERROR: {e}]")
            if hasattr(self, 'voice_btn'):
                self.voice_btn.setEnabled(False)

    def _register_voice_command_handlers(self):
        """Register voice command handlers that execute real GUI operations."""
        if not self.voice:
            return
        handlers = {
            CommandType.STOP: lambda cmd: self.stop_current_operation(),
            CommandType.EXECUTE: lambda cmd: self.exec_code(),
            CommandType.SAVE: lambda cmd: self.save_current_file(),
            CommandType.COPY: lambda cmd: self.copy_output(),
            CommandType.CLEAR: lambda cmd: self.clear_terminal(),
            CommandType.VOICE: lambda cmd: self.toggle_voice(),
            CommandType.PLAN: lambda cmd: self.plan_btn.setChecked(True),
            CommandType.BUILD: lambda cmd: self.build_btn.setChecked(True),
            CommandType.NEW_TAB: lambda cmd: self.new_file(),
            CommandType.CLOSE_TAB: lambda cmd: self.close_current_tab(),
            CommandType.HELP: lambda cmd: self.show_help(),
        }
        for cmd_type, handler in handlers.items():
            self.voice.register_command_handler(cmd_type, handler)
        logger.info(f"Registered {len(handlers)} voice command handlers")

    def load_config(self):
        config_path = Path("config.json")
        if config_path.exists():
            with open(config_path) as f:
                self.config = json.load(f)
        else:
            self.config = {"model": "qwen3:8b-gpu", "project_root": "."}

    def setup_atlan_theme(self):
        self.setWindowTitle("CRACKEDCODE v2.6.4 // AUTONOMOUS NEURAL SYSTEM")
        self.setMinimumSize(1400, 900)
        
        self.atlan_font = QFont("Consolas", 11)
        self.atlan_header = QFont("Consolas", 14, QFont.Weight.Bold)
        
        self.setStyleSheet(f"""
            QMainWindow {{ background-color: {ATLAN_DARK}; }}
            QWidget {{ background-color: {ATLAN_DARK}; color: {ATLAN_GREEN}; font-family: Consolas; font-size: 11px; }}
            QToolTip {{
                background-color: {ATLAN_MEDIUM};
                color: {ATLAN_GREEN};
                border: 1px solid {ATLAN_GREEN};
                border-radius: 4px;
                padding: 4px 8px;
                font-family: Consolas;
                font-size: 11px;
            }}
            QMenuBar {{ background-color: {ATLAN_MEDIUM}; color: {ATLAN_GREEN}; border-bottom: 2px solid {ATLAN_GREEN}; }}
            QMenuBar::item:selected {{ background-color: {ATLAN_GREEN}; color: {ATLAN_DARK}; }}
            QMenu {{ background-color: {ATLAN_MEDIUM}; color: {ATLAN_GREEN}; border: 1px solid {ATLAN_BORDER}; }}
            QMenu::item:selected {{ background-color: {ATLAN_GREEN}; color: {ATLAN_DARK}; }}
            QToolBar {{ background-color: {ATLAN_MEDIUM}; border-bottom: 2px solid {ATLAN_GREEN}; spacing: 4px; padding: 4px; }}
            QPushButton {{
                background-color: {ATLAN_LIGHT};
                color: {ATLAN_GREEN};
                border: 1px solid {ATLAN_GREEN};
                padding: 8px 16px;
                font-family: Consolas;
                font-weight: bold;
                border-radius: 6px;
                min-height: 28px;
            }}
            QPushButton:hover {{
                background-color: {ATLAN_GREEN};
                color: {ATLAN_DARK};
                border: 1px solid {ATLAN_CYAN};
            }}
            QPushButton:checked {{
                background-color: {ATLAN_GREEN};
                color: {ATLAN_DARK};
                border: 1px solid {ATLAN_CYAN};
            }}
            QPushButton:pressed {{ background-color: {ATLAN_CYAN}; color: {ATLAN_DARK}; }}
            QPushButton:disabled {{ color: #555; border-color: #555; background-color: {ATLAN_DARK}; }}
            QTextEdit {{
                background-color: #050505;
                color: {ATLAN_GREEN};
                border: 1px solid {ATLAN_BORDER};
                font-family: Consolas;
                border-radius: 6px;
                padding: 4px;
                selection-background-color: {ATLAN_GREEN};
                selection-color: {ATLAN_DARK};
            }}
            QTextEdit:focus {{ border: 1px solid {ATLAN_GREEN}; }}
            QLineEdit {{
                background-color: #050505;
                color: {ATLAN_GREEN};
                border: 1px solid {ATLAN_GREEN};
                font-family: Consolas;
                padding: 6px;
                border-radius: 6px;
                selection-background-color: {ATLAN_GREEN};
                selection-color: {ATLAN_DARK};
            }}
            QLineEdit:focus {{ border: 2px solid {ATLAN_CYAN}; }}
            QListWidget {{
                background-color: #050505;
                color: {ATLAN_GREEN};
                border: 1px solid {ATLAN_BORDER};
                border-radius: 6px;
                outline: none;
            }}
            QListWidget::item:selected {{
                background-color: {ATLAN_GREEN};
                color: {ATLAN_DARK};
                border-radius: 3px;
            }}
            QListWidget::item:hover {{ background-color: {ATLAN_LIGHT}; border-radius: 3px; }}
            QTabWidget::pane {{ border: 1px solid {ATLAN_GREEN}; border-radius: 6px; }}
            QTabBar::tab {{
                background-color: {ATLAN_MEDIUM};
                color: {ATLAN_GREEN};
                border: 1px solid {ATLAN_BORDER};
                padding: 8px 16px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background-color: {ATLAN_GREEN};
                color: {ATLAN_DARK};
                font-weight: bold;
            }}
            QTabBar::tab:hover {{ background-color: {ATLAN_LIGHT}; }}
            QGroupBox {{
                border: 2px solid {ATLAN_GREEN};
                margin-top: 10px;
                font-weight: bold;
                border-radius: 6px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                color: {ATLAN_GOLD};
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }}
            QStatusBar {{
                background-color: {ATLAN_MEDIUM};
                color: {ATLAN_GREEN};
                border-top: 2px solid {ATLAN_GREEN};
            }}
            QLabel {{ color: {ATLAN_GREEN}; }}
            QComboBox {{
                background-color: {ATLAN_LIGHT};
                color: {ATLAN_GREEN};
                border: 1px solid {ATLAN_GREEN};
                padding: 4px 8px;
                border-radius: 6px;
                min-width: 80px;
            }}
            QComboBox:hover {{ border: 1px solid {ATLAN_CYAN}; }}
            QComboBox::drop-down {{ border: none; width: 20px; }}
            QComboBox::down-arrow {{ image: none; border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 6px solid {ATLAN_GREEN}; }}
            QComboBox QAbstractItemView {{
                background-color: {ATLAN_MEDIUM};
                color: {ATLAN_GREEN};
                border: 1px solid {ATLAN_GREEN};
                selection-background-color: {ATLAN_GREEN};
                selection-color: {ATLAN_DARK};
            }}
            QSpinBox {{
                background-color: {ATLAN_LIGHT};
                color: {ATLAN_GREEN};
                border: 1px solid {ATLAN_GREEN};
                padding: 4px;
                border-radius: 6px;
            }}
            QSpinBox::up-button, QSpinBox::down-button {{ width: 16px; background: {ATLAN_MEDIUM}; border: 1px solid {ATLAN_BORDER}; }}
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {{ background: {ATLAN_GREEN}; }}
            QSlider::groove:horizontal {{ height: 6px; background: {ATLAN_MEDIUM}; border-radius: 3px; }}
            QSlider::handle:horizontal {{
                background: {ATLAN_GREEN};
                width: 14px;
                height: 14px;
                border-radius: 7px;
                margin: -4px 0;
            }}
            QSlider::handle:horizontal:hover {{ background: {ATLAN_CYAN}; }}
            QSplitter::handle {{ background-color: {ATLAN_GREEN}; width: 3px; }}
            QSplitter::handle:hover {{ background-color: {ATLAN_CYAN}; }}
            QProgressBar {{
                border: 1px solid {ATLAN_GREEN};
                border-radius: 6px;
                background-color: {ATLAN_DARK};
                text-align: center;
                color: {ATLAN_GREEN};
                height: 20px;
            }}
            QProgressBar::chunk {{
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {ATLAN_GREEN}, stop:1 {ATLAN_CYAN});
                border-radius: 5px;
            }}
            QScrollBar:vertical {{
                background: {ATLAN_DARK};
                width: 12px;
                border: none;
            }}
            QScrollBar::handle:vertical {{
                background: {ATLAN_GREEN};
                border-radius: 6px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{ background: {ATLAN_CYAN}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
            QScrollBar:horizontal {{
                background: {ATLAN_DARK};
                height: 12px;
                border: none;
            }}
            QScrollBar::handle:horizontal {{
                background: {ATLAN_GREEN};
                border-radius: 6px;
                min-width: 20px;
            }}
            QScrollBar::handle:horizontal:hover {{ background: {ATLAN_CYAN}; }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0px; }}
            QDockWidget::title {{
                background-color: {ATLAN_MEDIUM};
                color: {ATLAN_GOLD};
                padding: 6px;
                font-weight: bold;
            }}
            QDialog {{
                background-color: {ATLAN_DARK};
                border: 2px solid {ATLAN_GREEN};
                border-radius: 8px;
            }}
            QDialog QPushButton {{
                background-color: {ATLAN_LIGHT};
                color: {ATLAN_GREEN};
                border: 1px solid {ATLAN_GREEN};
                padding: 8px 20px;
                border-radius: 6px;
                font-weight: bold;
            }}
            QDialog QPushButton:hover {{
                background-color: {ATLAN_GREEN};
                color: {ATLAN_DARK};
            }}
            QDialog QTextEdit {{
                background-color: #050505;
                color: {ATLAN_GREEN};
                border: 1px solid {ATLAN_BORDER};
                border-radius: 6px;
            }}
            QDialog QLineEdit {{
                background-color: #050505;
                color: {ATLAN_GREEN};
                border: 1px solid {ATLAN_GREEN};
                border-radius: 6px;
                padding: 6px;
            }}
            QDialog QLabel {{ color: {ATLAN_GREEN}; font-weight: bold; }}
            QTreeWidget {{
                background-color: #050505;
                color: {ATLAN_GREEN};
                border: 1px solid {ATLAN_BORDER};
                border-radius: 6px;
                outline: none;
            }}
            QTreeWidget::item:selected {{
                background-color: {ATLAN_GREEN};
                color: {ATLAN_DARK};
                border-radius: 3px;
            }}
            QTreeWidget::item:hover {{ background-color: {ATLAN_LIGHT}; border-radius: 3px; }}
            QHeaderView::section {{
                background-color: {ATLAN_MEDIUM};
                color: {ATLAN_GOLD};
                padding: 4px;
                border: 1px solid {ATLAN_BORDER};
                font-weight: bold;
            }}
            QCheckBox {{ color: {ATLAN_GREEN}; spacing: 6px; }}
            QCheckBox::indicator {{
                width: 14px;
                height: 14px;
                border: 1px solid {ATLAN_GREEN};
                border-radius: 3px;
                background: {ATLAN_DARK};
            }}
            QCheckBox::indicator:checked {{ background: {ATLAN_GREEN}; }}
            QCheckBox::indicator:hover {{ border: 1px solid {ATLAN_CYAN}; }}
        """)

    def init_ui(self):
        # Create terminal first (menu bar references it)
        self.terminal = SearchableTerminal()
        self.terminal.setToolTip("Terminal output - Ctrl+F to search")
        
        self.create_menu_bar()
        
        central = QWidget()
        self.setCentralWidget(central)
        main = QHBoxLayout(central)
        main.setContentsMargins(4, 4, 4, 4)
        main.setSpacing(4)
        
        left_panel = self.create_left_panel()
        main.addWidget(left_panel, 1)
        
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(4)
        
        self.create_toolbar()
        
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setMovable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        self.tab_widget.tabBarDoubleClicked.connect(self.rename_tab)
        
        self.editor = QTextEdit()
        self.editor.setPlaceholderText("Enter code here...")
        self.editor.setToolTip("Code editor - type or paste code here")
        self.editor.document().modificationChanged.connect(self.on_modification_changed)
        self.tab_widget.addTab(self.editor, "untitled")
        self.open_files["untitled"] = self.editor
        
        rl.addWidget(self.tab_widget, 3)
        
        term_group = QGroupBox("TERMINAL")
        term_layout = QVBoxLayout(term_group)
        term_layout.setContentsMargins(4, 4, 4, 4)
        term_layout.addWidget(self.terminal)
        term_layout.addWidget(self.terminal.search_bar)
        
        tin = QHBoxLayout()
        prompt_label = QLabel(">")
        prompt_label.setStyleSheet(f"color: {ATLAN_CYAN}; font-weight: bold; font-size: 14px;")
        tin.addWidget(prompt_label)
        
        self.term_input = QLineEdit()
        self.term_input.setPlaceholderText("Enter prompt or command... (Up/Down for history)")
        self.term_input.setToolTip("Command input - press Enter to send")
        self.term_input.returnPressed.connect(self.run_term)
        self.term_input.installEventFilter(self)
        tin.addWidget(self.term_input)
        
        send_btn = QPushButton("SEND")
        send_btn.setToolTip("Send command (Enter)")
        send_btn.clicked.connect(self.run_term)
        send_btn.setFixedWidth(80)
        tin.addWidget(send_btn)
        
        term_layout.addLayout(tin)
        rl.addWidget(term_group, 2)
        
        main.addWidget(right, 3)
        
        self.create_status()
        
        QTimer.singleShot(1000, self.post_init)

    def post_init(self):
        status = self.engine.get_status() if self.engine else {}
        if hasattr(self, 'terminal'):
            self.term(f"[ENGINE v{status.get('version', '?')} loaded]")
            self.term(f"[OLLAMA: {len(status.get('ollama_models', []))} models]")
            self.term("[READY] Type your prompt below...")
        
        # Load plugins
        if PLUGINS_AVAILABLE:
            try:
                registry = get_plugin_registry()
                plugins_dir = Path(__file__).parent.parent / "plugins"
                registry.load_plugins_from_directory(str(plugins_dir))
                stats = registry.get_stats()
                self.term(f"[PLUGINS] Loaded {stats['enabled']}/{stats['total_plugins']} plugins")
                
                # Startup hook
                results = execute_hook(HookPoint.SYSTEM_STARTUP)
                for r in results:
                    if r:
                        self.term(f"[PLUGIN] {r}")
            except Exception as e:
                logger.warning(f"Plugin loading failed: {e}")
        
        # Setup quick actions / command palette
        if ENHANCEMENTS_AVAILABLE:
            self._setup_quick_actions()
            self._setup_keyboard_shortcuts()
            
            # Show welcome screen on first launch
            show_welcome = self.settings.value("show_welcome", True)
            if show_welcome:
                self.welcome = WelcomeWidget(self)
                self.welcome.dismissed.connect(lambda: self.settings.setValue("show_welcome", False))
                self.welcome.show()
        
        # Update status bar
        if ENHANCEMENTS_AVAILABLE and hasattr(self, 'statusBar') and isinstance(self.statusBar(), EnhancedStatusBar):
            sb = self.statusBar()
            sb.set_model(self.config.get("model", "unknown"))
            sb.set_files_count(0)
    
    def _setup_quick_actions(self):
        """Setup command palette with all available actions."""
        self.quick_actions = QuickActionsDialog(self)
        actions = [
            QuickActionItem("New File", "Ctrl+N", self.new_file, "File"),
            QuickActionItem("Open Project", "Ctrl+O", self.open_proj, "File"),
            QuickActionItem("Save File", "Ctrl+S", self.save_current_file, "File"),
            QuickActionItem("Execute Code", "Ctrl+Enter", self.exec_code, "Run"),
            QuickActionItem("Toggle Plan Mode", "Ctrl+P", lambda: self.plan_btn.setChecked(not self.plan_btn.isChecked()), "Mode"),
            QuickActionItem("Toggle Build Mode", "Ctrl+B", lambda: self.build_btn.setChecked(not self.build_btn.isChecked()), "Mode"),
            QuickActionItem("Toggle Voice", "Ctrl+Shift+V", self.toggle_voice, "Voice"),
            QuickActionItem("Autonomous Produce", "Ctrl+A", self.show_autonomous_dialog, "AI"),
            QuickActionItem("Search Codebase", "Ctrl+Shift+F", self.show_codebase_search, "Search"),
            QuickActionItem("Index Codebase", "", self.index_codebase, "Search"),
            QuickActionItem("Clear Terminal", "", self.clear_terminal, "Terminal"),
            QuickActionItem("Copy Output", "", self.copy_output, "Terminal"),
            QuickActionItem("Show Help", "F1", self.show_help, "Help"),
            QuickActionItem("Toggle Fullscreen", "F11", self.toggle_full, "View"),
            QuickActionItem("New Project", "", self.new_proj, "Project"),
        ]
        
        # Plugin command palette hook
        if PLUGINS_AVAILABLE:
            try:
                plugin_actions = execute_hook(HookPoint.GUI_COMMAND_PALETTE)
                for action_list in plugin_actions:
                    if isinstance(action_list, list):
                        actions.extend(action_list)
            except Exception as e:
                logger.warning(f"Plugin command palette hook error: {e}")
        
        self.quick_actions.register_actions(actions)
    
    def _setup_keyboard_shortcuts(self):
        """Register global keyboard shortcuts."""
        from PyQt6.QtGui import QShortcut
        
        # Command palette
        palette_shortcut = QShortcut(QKeySequence("Ctrl+Shift+P"), self)
        palette_shortcut.activated.connect(self.show_quick_actions)
        
        # Toggle fullscreen
        full_shortcut = QShortcut(QKeySequence("F11"), self)
        full_shortcut.activated.connect(self.toggle_full)
        
        # Help
        help_shortcut = QShortcut(QKeySequence("F1"), self)
        help_shortcut.activated.connect(self.show_help)
        
        # Close tab
        close_tab_shortcut = QShortcut(QKeySequence("Ctrl+W"), self)
        close_tab_shortcut.activated.connect(self.close_current_tab)
    
    def show_quick_actions(self):
        """Show the command palette."""
        if ENHANCEMENTS_AVAILABLE and hasattr(self, 'quick_actions'):
            self.quick_actions.show()
            self.quick_actions.raise_()
            self.quick_actions.activateWindow()
    
    def show_toast(self, text: str, toast_type=None, duration: int = 3000):
        """Show a toast notification."""
        if ENHANCEMENTS_AVAILABLE and self.toast:
            if toast_type is None:
                toast_type = ToastType.INFO
            self.toast.show_message(text, toast_type, duration)
        else:
            # Fallback to terminal
            self.term(f"[NOTIFY] {text}")

    def create_menu_bar(self):
        menubar = self.menuBar()
        
        file_menu = menubar.addMenu("FILE")
        
        new_action = QAction("NEW PROJECT", self)
        new_action.setShortcut(QKeySequence("Ctrl+N"))
        new_action.setToolTip("Create new project (Ctrl+N)")
        new_action.triggered.connect(self.new_proj)
        file_menu.addAction(new_action)
        
        open_action = QAction("OPEN PROJECT", self)
        open_action.setShortcut(QKeySequence("Ctrl+O"))
        open_action.setToolTip("Open project folder (Ctrl+O)")
        open_action.triggered.connect(self.open_proj)
        file_menu.addAction(open_action)
        
        file_menu.addSeparator()
        
        new_tab_action = QAction("NEW TAB", self)
        new_tab_action.setShortcut(QKeySequence("Ctrl+T"))
        new_tab_action.setToolTip("Create new editor tab (Ctrl+T)")
        new_tab_action.triggered.connect(lambda: self.new_tab())
        file_menu.addAction(new_tab_action)
        
        save_action = QAction("SAVE", self)
        save_action.setShortcut(QKeySequence("Ctrl+S"))
        save_action.setToolTip("Save current file (Ctrl+S)")
        save_action.triggered.connect(self.save_current_file)
        file_menu.addAction(save_action)
        
        save_as_action = QAction("SAVE AS", self)
        save_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        save_as_action.setToolTip("Save as new file (Ctrl+Shift+S)")
        save_as_action.triggered.connect(self.save_file_as)
        file_menu.addAction(save_as_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("EXIT", self)
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        exit_action.setToolTip("Exit application (Ctrl+Q)")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        edit_menu = menubar.addMenu("EDIT")
        
        copy_action = QAction("COPY OUTPUT", self)
        copy_action.setShortcut(QKeySequence("Ctrl+Shift+C"))
        copy_action.setToolTip("Copy terminal output")
        copy_action.triggered.connect(self.copy_output)
        edit_menu.addAction(copy_action)
        
        clear_action = QAction("CLEAR TERMINAL", self)
        clear_action.setShortcut(QKeySequence("Ctrl+L"))
        clear_action.setToolTip("Clear terminal output")
        clear_action.triggered.connect(self.clear_terminal)
        edit_menu.addAction(clear_action)
        
        edit_menu.addSeparator()
        
        find_action = QAction("FIND IN TERMINAL", self)
        find_action.setShortcut(QKeySequence("Ctrl+F"))
        find_action.setToolTip("Search terminal output (Ctrl+F)")
        find_action.triggered.connect(self.terminal.toggle_search)
        edit_menu.addAction(find_action)
        
        view_menu = menubar.addMenu("VIEW")
        
        palette_action = QAction("COMMAND PALETTE", self)
        palette_action.setShortcut(QKeySequence("Ctrl+Shift+P"))
        palette_action.setToolTip("Open command palette (Ctrl+Shift+P)")
        palette_action.triggered.connect(self.show_quick_actions)
        view_menu.addAction(palette_action)
        
        view_menu.addSeparator()
        
        matrix_action = QAction("TOGGLE MATRIX", self)
        matrix_action.setShortcut(QKeySequence("Ctrl+M"))
        matrix_action.setToolTip("Toggle matrix rain effect (Ctrl+M)")
        matrix_action.triggered.connect(self.toggle_matrix)
        view_menu.addAction(matrix_action)
        
        autonomous_action = QAction("AUTONOMOUS PRODUCTION", self)
        autonomous_action.setShortcut(QKeySequence("Ctrl+A"))
        autonomous_action.setToolTip("Open autonomous production dialog (Ctrl+A)")
        autonomous_action.triggered.connect(self.show_autonomous_dialog)
        view_menu.addAction(autonomous_action)
        
        full_action = QAction("TOGGLE FULLSCREEN", self)
        full_action.setShortcut(QKeySequence("F11"))
        full_action.setToolTip("Toggle fullscreen (F11)")
        full_action.triggered.connect(self.toggle_full)
        view_menu.addAction(full_action)
        
        dev_action = QAction("DEV CONSOLE", self)
        dev_action.setShortcut(QKeySequence("F12"))
        dev_action.setToolTip("Open dev console (F12)")
        dev_action.triggered.connect(self.toggle_dev_console)
        view_menu.addAction(dev_action)
        
        help_menu = menubar.addMenu("HELP")
        
        settings_action = QAction("SETTINGS", self)
        settings_action.setShortcut(QKeySequence("Ctrl+,"))
        settings_action.setToolTip("Open settings (Ctrl+,)")
        settings_action.triggered.connect(self.show_settings)
        help_menu.addAction(settings_action)
        
        help_menu.addSeparator()
        
        docs_action = QAction("DOCUMENTATION", self)
        docs_action.setToolTip("Open documentation")
        docs_action.triggered.connect(self.show_docs)
        help_menu.addAction(docs_action)
        
        about_action = QAction("ABOUT", self)
        about_action.setToolTip("About CrackedCode")
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
        # Plugins menu
        if PLUGINS_AVAILABLE:
            plugins_menu = menubar.addMenu("PLUGINS")
            
            reload_action = QAction("RELOAD PLUGINS", self)
            reload_action.setToolTip("Hot-reload all plugins")
            reload_action.triggered.connect(self.reload_plugins)
            plugins_menu.addAction(reload_action)
            
            plugins_menu.addSeparator()
            
            manage_action = QAction("MANAGE PLUGINS", self)
            manage_action.setToolTip("Enable/disable plugins")
            manage_action.triggered.connect(self.show_plugins_dialog)
            plugins_menu.addAction(manage_action)
        
        # Plugin hook: menu ready
        if PLUGINS_AVAILABLE:
            execute_hook(HookPoint.GUI_MENU_READY, menubar)

    def reload_plugins(self):
        """Hot-reload all plugins from the plugins directory."""
        if not PLUGINS_AVAILABLE:
            self.term("[PLUGINS] Plugin system not available")
            return
        
        try:
            registry = get_plugin_registry()
            registry.check_hot_reload()
            stats = registry.get_stats()
            self.term(f"[PLUGINS] Reloaded. Active: {stats['enabled']}/{stats['total_plugins']}")
        except Exception as e:
            self.term(f"[PLUGINS] Reload failed: {e}")
    
    def show_plugins_dialog(self):
        """Show dialog to manage plugin enable/disable state."""
        if not PLUGINS_AVAILABLE:
            QMessageBox.information(self, "Plugins", "Plugin system not available")
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Plugin Manager")
        dialog.setMinimumSize(400, 300)
        
        layout = QVBoxLayout(dialog)
        
        info = QLabel("Toggle plugins on/off. Changes take effect immediately.")
        info.setWordWrap(True)
        info.setStyleSheet(f"color: {ATLAN_GOLD}; font-size: 10px;")
        layout.addWidget(info)
        
        registry = get_plugin_registry()
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        cl = QVBoxLayout(container)
        cl.setSpacing(2)
        
        for p in registry.list_plugins():
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(2, 2, 2, 2)
            
            name_lbl = QLabel(f"{p.name} v{p.version}")
            name_lbl.setStyleSheet(f"color: {ATLAN_GREEN}; font-size: 10px; min-width: 140px;")
            rl.addWidget(name_lbl)
            
            desc_lbl = QLabel(p.description[:40])
            desc_lbl.setStyleSheet(f"color: {ATLAN_CYAN}; font-size: 9px;")
            rl.addWidget(desc_lbl)
            rl.addStretch()
            
            cb = QCheckBox()
            cb.setChecked(p.enabled)
            cb.stateChanged.connect(lambda state, pn=p.name: registry.set_enabled(pn, bool(state)))
            rl.addWidget(cb)
            
            cl.addWidget(row)
        
        cl.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)
        
        close_btn = QPushButton("CLOSE")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        
        dialog.exec()

    def create_left_panel(self):
        dock = QDockWidget("CONTROL CENTER", self)
        dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        project_group = QGroupBox("PROJECT")
        project_layout = QVBoxLayout(project_group)
        project_layout.setContentsMargins(4, 10, 4, 4)
        
        self.files_tree = QTreeWidget()
        self.files_tree.setHeaderLabel("Files")
        self.files_tree.itemDoubleClicked.connect(self.on_file_clicked)
        self.files_tree.setToolTip("Project files - double-click to open")
        self.files_tree.setSortingEnabled(True)
        project_layout.addWidget(self.files_tree)
        
        btn_layout = QHBoxLayout()
        new_btn = QPushButton("NEW")
        new_btn.setToolTip("Create new project")
        new_btn.clicked.connect(self.new_proj)
        open_btn = QPushButton("OPEN")
        open_btn.setToolTip("Open project folder")
        open_btn.clicked.connect(self.open_proj)
        refresh_btn = QPushButton("REFRESH")
        refresh_btn.setToolTip("Refresh file tree")
        refresh_btn.clicked.connect(self.refresh_file_tree)
        btn_layout.addWidget(new_btn)
        btn_layout.addWidget(open_btn)
        btn_layout.addWidget(refresh_btn)
        project_layout.addLayout(btn_layout)
        
        layout.addWidget(project_group)
        
        # Git panel
        if GIT_PANEL_AVAILABLE:
            self.git_panel = GitPanelWidget(parent=self)
            self.git_panel.file_clicked.connect(self.open_file_from_git)
            layout.addWidget(self.git_panel, 1)
        else:
            self.git_panel = None
        
        self.agent_panel = AgentPanelWidget(self.orchestrator)
        layout.addWidget(self.agent_panel)
        
        self.task_queue = TaskQueueWidget(self.orchestrator)
        layout.addWidget(self.task_queue)
        
        # Reasoning panel
        self.reasoning_panel = ReasoningPanelWidget(gui_ref=self)
        layout.addWidget(self.reasoning_panel)
        
        # Tool execution log
        if TOOLS_AVAILABLE:
            self.tool_log = ToolLogWidget(gui_ref=self)
            layout.addWidget(self.tool_log)
        else:
            self.tool_log = None
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setToolTip("Task progress")
        self.progress_bar.setFixedHeight(20)
        layout.addWidget(self.progress_bar)
        
        dock.setWidget(container)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)
        
        return dock

    def refresh_file_tree(self):
        if self.project_path:
            self.scan_project_files(str(self.project_path))
            self.term("[REFRESHED] File tree updated")

    def create_toolbar(self):
        tb = QToolBar()
        tb.setMovable(False)
        tb.setIconSize(QSize(24, 24))
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.addToolBar(tb)
        
        self.plan_btn = QPushButton("PLAN")
        self.plan_btn.setCheckable(True)
        self.plan_btn.setChecked(True)
        self.plan_btn.setToolTip("Toggle PLAN mode (Ctrl+P)")
        self.plan_btn.clicked.connect(lambda: self.set_mode("plan"))
        tb.addWidget(self.plan_btn)
        
        self.build_btn = QPushButton("BUILD")
        self.build_btn.setCheckable(True)
        self.build_btn.setChecked(True)
        self.build_btn.setToolTip("Toggle BUILD mode (Ctrl+B)")
        self.build_btn.clicked.connect(lambda: self.set_mode("build"))
        tb.addWidget(self.build_btn)
        
        tb.addSeparator()
        
        exec_btn = QPushButton("EXECUTE")
        exec_btn.setToolTip("Execute code in editor (Ctrl+Enter)")
        exec_btn.clicked.connect(self.exec_code)
        tb.addWidget(exec_btn)
        
        self.voice_btn = QPushButton("VOICE")
        self.voice_btn.setCheckable(True)
        self.voice_btn.setToolTip("Toggle voice input (Ctrl+Shift+V)")
        self.voice_btn.clicked.connect(self.toggle_voice)
        tb.addWidget(self.voice_btn)
        
        tb.addSeparator()
        
        copy_btn = QPushButton("COPY")
        copy_btn.setToolTip("Copy terminal output")
        copy_btn.clicked.connect(self.copy_output)
        tb.addWidget(copy_btn)
        
        clear_btn = QPushButton("CLEAR")
        clear_btn.setToolTip("Clear terminal")
        clear_btn.clicked.connect(self.clear_terminal)
        tb.addWidget(clear_btn)
        
        tb.addSeparator()
        
        stop_btn = QPushButton("STOP")
        stop_btn.setToolTip("Stop current operation (Esc)")
        stop_btn.clicked.connect(self.stop_current_operation)
        stop_btn.setStyleSheet(f"""
            QPushButton {{
                color: {ATLAN_RED}; 
                border-color: {ATLAN_RED};
            }}
            QPushButton:hover {{
                background-color: {ATLAN_RED};
                color: {ATLAN_DARK};
            }}
        """)
        tb.addWidget(stop_btn)

        tb.addSeparator()

        self.unified_btn = QPushButton("UNIFIED")
        self.unified_btn.setCheckable(True)
        self.unified_btn.setChecked(self.config.get("unified_mode", False))
        self.unified_btn.setToolTip("Toggle Unified Intelligence Mode (all models combined)")
        self.unified_btn.clicked.connect(self.toggle_unified_mode)
        tb.addWidget(self.unified_btn)

        tb.addSeparator()

        self.stream_btn = QPushButton("STREAM")
        self.stream_btn.setCheckable(True)
        self.stream_btn.setChecked(self.config.get("streaming_enabled", True))
        self.stream_btn.setToolTip("Toggle streaming responses (character by character)")
        self.stream_btn.clicked.connect(self.toggle_streaming)
        tb.addWidget(self.stream_btn)
        
        tb.addSeparator()
        
        self.autonomous_btn = QPushButton("AUTONOMOUS")
        self.autonomous_btn.setCheckable(True)
        self.autonomous_btn.setChecked(self.config.get("autonomous_enabled", True))
        self.autonomous_btn.setToolTip("Toggle autonomous production mode (Ctrl+A)")
        self.autonomous_btn.clicked.connect(self.toggle_autonomous_mode)
        tb.addWidget(self.autonomous_btn)
        
        tb.addSeparator()
        
        self.matrix_btn = QPushButton("MATRIX")
        self.matrix_btn.setCheckable(True)
        self.matrix_btn.setChecked(False)
        self.matrix_btn.setToolTip("Toggle matrix rain effect (Ctrl+M)")
        self.matrix_btn.clicked.connect(self.toggle_matrix)
        tb.addWidget(self.matrix_btn)

    def create_status(self):
        if ENHANCEMENTS_AVAILABLE:
            sb = EnhancedStatusBar(self)
            self.setStatusBar(sb)
            self.status_lbl = sb.status_label  # Compatibility
            # Will be updated via sb methods
        else:
            sb = QStatusBar()
            self.setStatusBar(sb)
            self.status_lbl = QLabel("READY")
            sb.addWidget(self.status_lbl)
        
        self.cache_lbl = QLabel("Cache: 0")
        self.cache_lbl.setToolTip("Response cache size")
        self.statusBar().addPermanentWidget(self.cache_lbl)
        
        self.ollama_lbl = QLabel("OLLAMA: ...")
        self.ollama_lbl.setToolTip("Ollama connection status")
        self.statusBar().addPermanentWidget(self.ollama_lbl)
        
        self.model_lbl = QLabel("MODEL: none")
        self.model_lbl.setToolTip("Current AI model")
        self.statusBar().addPermanentWidget(self.model_lbl)
        
        self.task_status_lbl = QLabel("Tasks: 0")
        self.task_status_lbl.setToolTip("Task count")
        self.statusBar().addPermanentWidget(self.task_status_lbl)
        
        self.coherence_status_lbl = QLabel("C: 1.00")
        self.coherence_status_lbl.setToolTip("Cross-agent coherence")
        self.coherence_status_lbl.setStyleSheet(f"color: {ATLAN_GREEN};")
        self.statusBar().addPermanentWidget(self.coherence_status_lbl)
        
        self.time_lbl = QLabel("")
        self.statusBar().addPermanentWidget(self.time_lbl)
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)
        
        # Toast notification
        if ENHANCEMENTS_AVAILABLE:
            self.toast = ToastNotification(self)
        else:
            self.toast = None
        self.update_time()
        
        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self.update_stats)
        self.stats_timer.start(5000)

    def update_time(self):
        current_time = time.strftime("%H:%M:%S")
        self.time_lbl.setText(current_time)
        
        # Update coherence status
        if REASONING_AVAILABLE and hasattr(self, 'coherence_status_lbl'):
            try:
                report = get_reasoning_engine().get_coherence_report()
                coherence = report.get("cross_agent_coherence", {}).get("overall_coherence", 1.0)
                self.coherence_status_lbl.setText(f"C: {coherence:.2f}")
                if coherence >= 0.8:
                    self.coherence_status_lbl.setStyleSheet(f"color: {ATLAN_GREEN};")
                elif coherence >= 0.5:
                    self.coherence_status_lbl.setStyleSheet(f"color: {ATLAN_GOLD};")
                else:
                    self.coherence_status_lbl.setStyleSheet(f"color: {ATLAN_RED};")
            except Exception:
                pass
        
    def update_stats(self):
        if self.engine and hasattr(self.engine, 'ollama'):
            stats = self.engine.ollama.get_cache_stats()
            self.cache_lbl.setText(f"Cache: {stats['size']}")

    def update_status(self, status: Dict):
        if hasattr(self, 'ollama_lbl'):
            ollama_on = status.get('ollama_available', False)
            self.ollama_lbl.setText(f"OLLAMA: {'ON' if ollama_on else 'OFF'}")
            self.ollama_lbl.setStyleSheet(f"color: {ATLAN_GREEN if ollama_on else ATLAN_RED};")
        if hasattr(self, 'model_lbl'):
            self.model_lbl.setText(f"MODEL: {status.get('model', 'none')}")

    def toggle_unified_mode(self):
        if hasattr(self, 'engine') and self.engine:
            enabled = self.unified_btn.isChecked()
            self.engine.set_unified_mode(enabled)
            self.config["unified_mode"] = enabled
            mode_text = "UNIFIED BRAIN" if enabled else "SINGLE MODEL"
            self.set_status(mode_text)
            self.term(f"[MODE] {mode_text} {'(All models combined)' if enabled else '(Specialized models)'}")
            self.show_notification(f"Unified mode: {mode_text}", NotificationType.INFO)

    def toggle_streaming(self):
        enabled = self.stream_btn.isChecked()
        self.config["streaming_enabled"] = enabled
        mode_text = "STREAMING ON" if enabled else "STREAMING OFF"
        self.set_status(mode_text)
        self.term(f"[STREAM] {mode_text}")
        self.show_notification(mode_text, NotificationType.INFO)

    def toggle_matrix(self):
        if hasattr(self, 'matrix'):
            self.matrix.toggle()
            self.matrix_visible = not self.matrix_visible
            self.term(f"[MATRIX] {'ON' if self.matrix_visible else 'OFF'}")

    def toggle_autonomous_mode(self):
        enabled = self.autonomous_btn.isChecked()
        self.config["autonomous_enabled"] = enabled
        if self.engine:
            self.engine.autonomous_enabled = enabled
        self.term(f"[AUTONOMOUS] {'ENABLED' if enabled else 'DISABLED'}")
        if enabled:
            self.show_autonomous_dialog()

    def show_autonomous_dialog(self):
        """Show autonomous production dialog."""
        from src.autonomous import ArchitecturePattern, ARCHITECTURE_TEMPLATES
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Autonomous Application Producer")
        dialog.setMinimumSize(600, 500)
        dialog.setModal(True)
        
        layout = QVBoxLayout(dialog)
        
        title = QLabel("Autonomous Application Producer")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #00ff41;")
        layout.addWidget(title)
        
        desc = QLabel("Describe your application in natural language. The AI will autonomously design, code, test, and deliver a complete project.")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        layout.addWidget(QLabel("Specification:"))
        spec_edit = QTextEdit()
        spec_edit.setPlaceholderText("e.g., Build a todo list application with a web API, user authentication, and SQLite storage...")
        spec_edit.setMinimumHeight(100)
        layout.addWidget(spec_edit)
        
        arch_layout = QHBoxLayout()
        arch_layout.addWidget(QLabel("Architecture:"))
        arch_combo = QComboBox()
        for pattern in ArchitecturePattern:
            arch_combo.addItem(f"{pattern.value} - {ARCHITECTURE_TEMPLATES[pattern]['description']}")
        arch_layout.addWidget(arch_combo)
        layout.addLayout(arch_layout)
        
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Project name (optional):"))
        name_edit = QLineEdit()
        name_edit.setPlaceholderText("Auto-generated from specification")
        name_layout.addWidget(name_edit)
        layout.addLayout(name_layout)
        
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("Output directory (optional):"))
        output_edit = QLineEdit()
        output_edit.setPlaceholderText("./projects/{project_name}")
        output_layout.addWidget(output_edit)
        layout.addLayout(output_layout)
        
        progress_bar = QProgressBar()
        progress_bar.setVisible(False)
        layout.addWidget(progress_bar)
        
        progress_label = QLabel("")
        progress_label.setVisible(False)
        layout.addWidget(progress_label)
        
        button_layout = QHBoxLayout()
        produce_btn = QPushButton("PRODUCE")
        produce_btn.setStyleSheet("""
            QPushButton {
                background-color: #00ff41;
                color: #0a0a0a;
                font-weight: bold;
                padding: 8px 24px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #00cc33;
            }
        """)
        cancel_btn = QPushButton("Cancel")
        button_layout.addStretch()
        button_layout.addWidget(produce_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
        
        self._autonomous_producing = False
        
        def on_produce():
            if self._autonomous_producing:
                return
            self._autonomous_producing = True
            
            spec = spec_edit.toPlainText().strip()
            if not spec:
                progress_label.setText("Please enter a specification.")
                progress_label.setVisible(True)
                self._autonomous_producing = False
                return
            
            project_name = name_edit.text().strip() or None
            output_dir = output_edit.text().strip() or None
            arch_value = arch_combo.currentText().split(" - ")[0]
            
            progress_bar.setVisible(True)
            progress_label.setVisible(True)
            progress_bar.setValue(0)
            progress_label.setText("Starting autonomous production...")
            produce_btn.setEnabled(False)
            cancel_btn.setText("Cancel")
            
            def progress_cb(message, progress):
                progress_bar.setValue(int(progress * 100))
                progress_label.setText(message)
            
            def phase_cb(phase, message):
                progress_label.setText(f"[{phase.value.upper()}] {message}")
            
            def run_production():
                try:
                    from src.autonomous import ArchitecturePattern
                    arch_enum = ArchitecturePattern(arch_value)
                except ValueError:
                    arch_enum = None
                
                result = self.engine.autonomous_produce(
                    spec=spec,
                    project_name=project_name,
                    architecture=arch_enum.value if arch_enum else None,
                    output_dir=output_dir,
                    progress_callback=progress_cb,
                    phase_callback=phase_cb,
                )
                
                self._autonomous_producing = False
                
                if result.success:
                    progress_label.setText(f"SUCCESS: {result.summary}")
                    self.term(f"[AUTONOMOUS] {result.summary}")
                    self.show_notification(f"Project produced: {result.files_created} files", NotificationType.SUCCESS)
                else:
                    progress_label.setText(f"COMPLETED WITH ISSUES: {result.summary}")
                    self.term(f"[AUTONOMOUS] {result.summary}")
                    if result.errors:
                        for err in result.errors[:3]:
                            self.term(f"  ERROR: {err}")
                    self.show_notification(f"Production completed with issues", NotificationType.WARNING)
                
                produce_btn.setEnabled(True)
                cancel_btn.setText("Close")
            
            thread = threading.Thread(target=run_production, daemon=True)
            thread.start()
        
        def on_cancel():
            if self._autonomous_producing:
                if self.engine and self.engine._autonomous_producer:
                    self.engine._autonomous_producer.cancel()
                    progress_label.setText("Cancelling...")
            else:
                dialog.close()
        
        produce_btn.clicked.connect(on_produce)
        cancel_btn.clicked.connect(on_cancel)

    def show_codebase_search(self):
        """Show semantic codebase search dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Semantic Codebase Search")
        dialog.setMinimumSize(700, 500)
        dialog.setModal(True)
        
        layout = QVBoxLayout(dialog)
        
        title = QLabel("Semantic Codebase Search")
        title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {ATLAN_GREEN};")
        layout.addWidget(title)
        
        desc = QLabel("Search your codebase using natural language. The AI finds semantically relevant code, not just keyword matches.")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        search_layout = QHBoxLayout()
        search_input = QLineEdit()
        search_input.setPlaceholderText("e.g., 'Where is user authentication handled?' or 'Find the database connection logic'")
        search_layout.addWidget(search_input)
        
        search_btn = QPushButton("SEARCH")
        search_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ATLAN_GREEN};
                color: {ATLAN_DARK};
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 4px;
            }}
        """)
        search_layout.addWidget(search_btn)
        layout.addLayout(search_layout)
        
        results_area = QTextEdit()
        results_area.setReadOnly(True)
        results_area.setPlaceholderText("Search results will appear here...")
        layout.addWidget(results_area)
        
        def do_search():
            query = search_input.text().strip()
            if not query:
                return
            
            results_area.setText(f"Searching: {query}...\n")
            
            if not self.engine or not self.engine.codebase_indexer:
                results_area.setText("Codebase indexer not available. Make sure the project is indexed (Ctrl+Shift+F > Index Codebase).")
                return
            
            try:
                indexer = self.engine.codebase_indexer
                if not indexer._indexed:
                    indexer.index()
                
                results = indexer.search(query, top_k=5)
                if not results:
                    results_area.setText(f"No semantically relevant results for: {query}\n\nTry rephrasing or indexing the codebase first.")
                    return
                
                lines = [f"Results for: '{query}'\n{'='*60}\n"]
                for r in results:
                    chunk = r.chunk
                    name = chunk.metadata.get("name", "")
                    type_label = f" [{chunk.chunk_type}: {name}]" if name else f" [{chunk.chunk_type}]"
                    lines.append(f"\nRank {r.rank} | Score: {r.score:.3f} | {chunk.file_path}{type_label}")
                    lines.append(f"Lines {chunk.start_line}-{chunk.end_line} | Language: {chunk.language}")
                    if r.reasoning:
                        lines.append(f"Why: {r.reasoning}")
                    lines.append("-" * 40)
                    lines.append(chunk.content[:1000])
                    lines.append("-" * 40)
                    lines.append("")
                
                stats = indexer.get_stats()
                lines.append(f"\nIndexed: {stats['chunks']} chunks | Backend: {stats['backend']} | Duration: {stats['index_time']}s")
                results_area.setText("\n".join(lines))
                
                self.term(f"[SEARCH] '{query}' → {len(results)} results", level="success")
            except Exception as e:
                results_area.setText(f"Search error: {e}")
                self.term(f"[SEARCH ERROR] {e}", level="error")
        
        search_btn.clicked.connect(do_search)
        search_input.returnPressed.connect(do_search)
        dialog.show()

    def index_codebase(self):
        """Index the current project for semantic search."""
        if not self.project_path:
            self.term("[SEARCH] No project open. Open a project first.", level="warning")
            return
        
        if not self.engine:
            self.term("[SEARCH] Engine not initialized.", level="error")
            return
        
        self.term(f"[SEARCH] Indexing codebase: {self.project_path}...", level="info")
        
        try:
            indexer = self.engine.codebase_indexer
            if indexer:
                result = indexer.index(force=True)
                self.term(
                    f"[SEARCH] Indexed {result.get('files', 0)} files → {result.get('chunks', 0)} chunks "
                    f"({result.get('duration', 0)}s) via {result.get('backend', 'unknown')}",
                    level="success"
                )
        except Exception as e:
            self.term(f"[SEARCH ERROR] {e}", level="error")

    def show_notification(self, message: str, ntype: NotificationType = NotificationType.INFO):
        if not hasattr(self, 'notification_area'):
            self.notification_area = QVBoxLayout()
            self.notification_area.setContentsMargins(10, 10, 10, 10)
            self.notification_area.addStretch()
            
            notif_widget = QWidget()
            notif_widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            notif_widget.setLayout(self.notification_area)
            notif_widget.setFixedWidth(300)
            
            stack = self.findChild(QStackedWidget)
            if not stack:
                self.setCentralWidget(notif_widget)
        
        notif = NotificationWidget(message, ntype)
        self.notification_area.insertWidget(0, notif)
        
        if self.notification_area.count() > 5:
            self.notification_area.takeAt(0)

    def close_tab(self, index):
        if self.tab_widget.count() > 1:
            tab_name = self.tab_widget.tabText(index)
            if tab_name in self.open_files:
                del self.open_files[tab_name]
            if tab_name in self.modified_tabs:
                self.modified_tabs.remove(tab_name)
            self.tab_widget.removeTab(index)
            self.term(f"[TAB] Closed {tab_name}")

    def rename_tab(self, index):
        tab_name = self.tab_widget.tabText(index)
        new_name, ok = QInputDialog.getText(self, "Rename Tab", "New name:", text=tab_name)
        if ok and new_name:
            self.tab_widget.setTabText(index, new_name)
            if tab_name in self.open_files:
                self.open_files[new_name] = self.open_files.pop(tab_name)
            if tab_name in self.modified_tabs:
                self.modified_tabs.remove(tab_name)
                self.modified_tabs.add(new_name)
            self.term(f"[TAB] Renamed to {new_name}")

    def on_tab_changed(self, index):
        tab_name = self.tab_widget.tabText(index)
        self.editor = self.tab_widget.widget(index)
        if self.editor and not hasattr(self.editor, '_has_event_filter'):
            self.editor.installEventFilter(self)
            self.editor._has_event_filter = True
        self.set_status(f"Editing: {tab_name}")

    def on_modification_changed(self, modified: bool):
        current = self.tab_widget.currentIndex()
        tab_name = self.tab_widget.tabText(current)
        
        if modified:
            if tab_name not in self.modified_tabs:
                self.modified_tabs.add(tab_name)
                self.tab_widget.setTabText(current, f"*{tab_name}")
            # Trigger auto-save on modification
            self._trigger_auto_save()
        else:
            if tab_name in self.modified_tabs:
                self.modified_tabs.remove(tab_name)
                if tab_name.startswith("*"):
                    self.tab_widget.setTabText(current, tab_name[1:])

    def new_tab(self, name: str = None):
        if name is None:
            name = f"file_{self.tab_widget.count()}"
        editor = QTextEdit()
        editor.setPlaceholderText("Enter code here...")
        editor.document().modificationChanged.connect(self.on_modification_changed)
        self.tab_widget.addTab(editor, name)
        self.open_files[name] = editor
        self.tab_widget.setCurrentWidget(editor)
        self.editor = editor
        self.term(f"[TAB] Created {name}")

    def open_file_in_tab(self, filepath: Path):
        name = filepath.name
        if name in self.open_files:
            self.tab_widget.setCurrentWidget(self.open_files[name])
            return
        
        try:
            content = filepath.read_text(errors='ignore')
            editor = QTextEdit()
            editor.setPlainText(content)
            editor.document().modificationChanged.connect(self.on_modification_changed)
            
            # Apply syntax highlighting
            if SYNTAX_AVAILABLE:
                ext = filepath.suffix.lower()
                if ext in HIGHLIGHTERS:
                    get_highlighter(ext, editor.document())
                    logger.info(f"Applied {ext} syntax highlighting to {name}")
            
            self.tab_widget.addTab(editor, name)
            self.open_files[name] = editor
            self.tab_widget.setCurrentWidget(editor)
            self.editor = editor
            self.current_file = filepath
            self.term(f"Opened {filepath.name}", level="success")
            self.show_notification(f"Opened {filepath.name}", NotificationType.SUCCESS)
        except Exception as e:
            self.term(f"Cannot open {filepath.name}: {e}", level="error")

    def open_file_from_git(self, filepath: str):
        """Open a file clicked in the git panel."""
        if self.project_path:
            full_path = self.project_path / filepath
            if full_path.exists():
                self.open_file_in_tab(full_path)
            else:
                self.term(f"File not found: {filepath}", level="warning")

    def toggle_dev_console(self):
        status = self.engine.get_status() if self.engine else {}
        
        if hasattr(self, 'dev_console') and self.dev_console.isVisible():
            self.dev_console.hide()
        else:
            if not hasattr(self, 'dev_console'):
                self.dev_console = QDialog(self)
                self.dev_console.setWindowTitle("Dev Console (F12)")
                self.dev_console.setGeometry(100, 100, 600, 500)
                self.dev_console.setStyleSheet("background-color: #0a0a0a;")
                
                dev_layout = QVBoxLayout(self.dev_console)
                
                self.dev_text = QTextEdit()
                self.dev_text.setStyleSheet("background-color: #0a0a0a; color: #00FF41; font-family: Consolas;")
                dev_layout.addWidget(self.dev_text)
                
                btn_row = QHBoxLayout()
                refresh_btn = QPushButton("REFRESH")
                refresh_btn.clicked.connect(self.update_dev_console)
                btn_row.addWidget(refresh_btn)
                close_btn = QPushButton("CLOSE")
                close_btn.clicked.connect(self.dev_console.hide)
                btn_row.addWidget(close_btn)
                dev_layout.addLayout(btn_row)
            
            self.update_dev_console()
            self.dev_console.show()
            self.dev_console.raise_()
            self.dev_console.activateWindow()

    def update_dev_console(self):
        status = self.engine.get_status() if self.engine else {}
        self.dev_text.setPlainText("")
        self.dev_text.append("=" * 50)
        self.dev_text.append(f"CRACKEDCODE DEV CONSOLE v{status.get('version', '?')}")
        self.dev_text.append("=" * 50)
        self.dev_text.append(f"Ollama Available: {status.get('ollama_available', False)}")
        self.dev_text.append(f"Models: {status.get('ollama_models', [])}")
        self.dev_text.append(f"Selected Model: {status.get('model', 'none')}")
        self.dev_text.append(f"Unified Mode: {status.get('unified_mode', False)}")
        self.dev_text.append(f"Streaming: {self.config.get('streaming_enabled', True)}")
        self.dev_text.append(f"Cache Size: {status.get('cache_size', 0)}")
        self.dev_text.append(f"Context Length: {status.get('context_length', 0)}")
        self.dev_text.append(f"Plan Mode: {status.get('plan', False)}")
        self.dev_text.append(f"Build Mode: {status.get('build', False)}")
        self.dev_text.append(f"History Length: {status.get('history_length', 0)}")
        self.dev_text.append("")
        self.dev_text.append("MODEL ROLES:")
        for model, info in status.get('model_roles', {}).items():
            self.dev_text.append(f"  {model}: {info.get('role', 'unknown')} ({info.get('strength', '')})")
        self.dev_text.append("")
        self.dev_text.append("ORCHESTRATOR STATUS:")
        if hasattr(self, 'orchestrator'):
            qstatus = self.orchestrator.get_queue_status()
            self.dev_text.append(f"  Pending: {qstatus['pending']}")
            self.dev_text.append(f"  Running: {qstatus['running']}")
            self.dev_text.append(f"  Completed: {qstatus['completed']}")
            self.dev_text.append(f"  Failed: {qstatus['failed']}")
            self.dev_text.append(f"  Active Agents: {qstatus['active_agents']}")
        self.dev_text.append("=" * 50)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F12:
            self.toggle_dev_console()
        elif event.key() == Qt.Key.Key_F11:
            self.toggle_full()
        elif event.key() == Qt.Key.Key_Escape:
            self.stop_current_operation()
        elif event.matches(QKeySequence.StandardKey.Copy):
            self.copy_output()
        elif event.matches(QKeySequence.StandardKey.Paste):
            self.handle_paste()
        elif event.matches(QKeySequence.StandardKey.SelectAll):
            self.editor.selectAll()
        elif event.key() == Qt.Key.Key_Return and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self.run_term()
        elif event.key() == Qt.Key.Key_M and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self.toggle_matrix()
        elif event.key() == Qt.Key.Key_L and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self.clear_terminal()
        elif event.key() == Qt.Key.Key_T and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self.new_tab()
        elif event.key() == Qt.Key.Key_F and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self.terminal.toggle_search()
        else:
            super().keyPressEvent(event)

    def eventFilter(self, obj, event):
        if obj == self.term_input:
            if event.type() == event.Type.KeyPress:
                global COMMAND_HISTORY, HISTORY_INDEX
                if event.key() == Qt.Key.Key_Up:
                    if COMMAND_HISTORY and HISTORY_INDEX < len(COMMAND_HISTORY) - 1:
                        HISTORY_INDEX += 1
                        self.term_input.setText(COMMAND_HISTORY[-(HISTORY_INDEX + 1)])
                    return True
                elif event.key() == Qt.Key.Key_Down:
                    if HISTORY_INDEX > 0:
                        HISTORY_INDEX -= 1
                        self.term_input.setText(COMMAND_HISTORY[-(HISTORY_INDEX + 1)])
                    else:
                        HISTORY_INDEX = -1
                        self.term_input.clear()
                    return True
                    
        if obj == self.editor and event.type() == event.Type.KeyPress:
            if event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_V:
                self.handle_paste()
                return True
        return super().eventFilter(obj, event)

    def handle_paste(self):
        mime = self.clipboard.mimeData()
        if mime.hasImage():
            image = self.clipboard.image()
            if image:
                self.handle_dropped_image(image)
                self.term("[IMAGE: pasted from clipboard]")
                return
        if mime.hasText():
            text = mime.text()
            if text:
                if self._is_code_snippet(text):
                    self.editor.append(text)
                    self.term(f"[PASTE: {len(text)} chars added to editor]")
                else:
                    self.term_input.setText(text)
                    self.term("[PASTE: text to command input]")

    def handle_dropped_image(self, image: QImage or QPixmap):
        buffer = io.BytesIO()
        if isinstance(image, QPixmap):
            image = image.toImage()
        image.save(buffer, "PNG")
        img_bytes = buffer.getvalue()
        img_hash = hashlib.md5(img_bytes).hexdigest()[:8]

        if img_hash == self.last_paste_hash:
            return
        self.last_paste_hash = img_hash

        self.pending_image = img_bytes

        self.term(f"[IMAGE: {image.width()}x{image.height()}, {len(img_bytes)} bytes]")

        if self.engine and hasattr(self.engine, 'vision'):
            try:
                import asyncio
                result = asyncio.run(self.engine.vision.analyze_image(img_bytes))
                self.term(f"[VISION ANALYSIS]:\n{result[:500]}")
            except Exception as e:
                self.term(f"[VISION ERROR: {e}]")

    def _is_code_snippet(self, text: str) -> bool:
        code_indicators = ['def ', 'class ', 'function ', 'import ', 'from ', 'const ', 'let ', 'var ',
                         'if (', 'if(', 'for (', 'for(', 'while (', 'while(', 'print(', 'return ', 'async ', 'await ']
        return any(text.lstrip().startswith(ind) for ind in code_indicators) or text.count('\n') > 2

    def copy_output(self):
        text = self.terminal.toPlainText()
        if text:
            self.clipboard.setText(text)
            self.term("Terminal content copied to clipboard", level="success")
            self.show_toast("Copied to clipboard", ToastType.SUCCESS)
        else:
            self.show_toast("Nothing to copy", ToastType.WARNING)

    def clear_terminal(self):
        self.terminal.clear()
        self.terminal.clear_highlights()
        self.term("Terminal cleared", level="info")
        self.show_toast("Terminal cleared", ToastType.INFO)

    def stop_current_operation(self):
        self.voice_recording = False
        if hasattr(self, 'voice_btn'):
            self.voice_btn.setChecked(False)
        self.set_status("STOPPED")
        self.progress_bar.setValue(0)
        self.term("Operation stopped", level="warning")
        self.show_notification("Operation stopped", NotificationType.WARNING)
        self.show_toast("Operation stopped", ToastType.WARNING)

    def set_status(self, text: str):
        if hasattr(self, 'status_lbl'):
            self.status_lbl.setText(text)

    def update_task_status(self):
        if hasattr(self, 'orchestrator'):
            status = self.orchestrator.get_queue_status()
            total = len(self.orchestrator.tasks)
            self.task_status_lbl.setText(f"Tasks: {status['completed']}/{total}")

    def init_matrix(self):
        self.matrix = MatrixOverlay(self)
        self.matrix.setGeometry(self.rect())
        self.matrix.lower()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'matrix'):
            self.matrix.setGeometry(self.rect())

    def new_proj(self):
        f = QFileDialog.getExistingDirectory(self, "NEW PROJECT")
        if f:
            self.config["project_root"] = f
            self.term(f"New project: {f}", level="success")
            self.scan_project_files(f)
            self._start_watching_project(f)
            self.show_notification(f"New project: {Path(f).name}", NotificationType.SUCCESS)

    def open_proj(self):
        f = QFileDialog.getExistingDirectory(self, "OPEN PROJECT")
        if f:
            self.config["project_root"] = f
            self.term(f"Opened project: {f}", level="success")
            self.scan_project_files(f)
            self._start_watching_project(f)
            # Update git panel
            if self.git_panel:
                self.git_panel.set_repo(f)
            self.show_notification(f"Opened project: {Path(f).name}", NotificationType.SUCCESS)
            self.show_toast(f"Opened {Path(f).name}", ToastType.SUCCESS)

    def scan_project_files(self, root):
        self.files_tree.clear()
        self.project_path = Path(root)
        
        if not self.project_path.exists():
            self.term(f"[ERROR: Path not found: {root}]")
            return
        
        self.term(f"[SCANNING: {root}]")
        
        root_item = QTreeWidgetItem([root])
        root_icon = self.get_folder_icon()
        root_item.setIcon(0, root_icon)
        self.files_tree.addTopLevelItem(root_item)
        
        count = [0]
        try:
            def add_items(parent_item, path):
                try:
                    for p in sorted(path.iterdir()):
                        if count[0] > 100:
                            return
                        if p.is_file() and not p.name.startswith('.'):
                            child = QTreeWidgetItem([p.name])
                            child.setData(0, Qt.ItemDataRole.UserRole, str(p))
                            child.setIcon(0, self.get_file_icon(p))
                            parent_item.addChild(child)
                            count[0] += 1
                        elif p.is_dir() and not p.name.startswith('.') and not p.name.startswith('__'):
                            child = QTreeWidgetItem([p.name])
                            child.setIcon(0, self.get_folder_icon())
                            parent_item.addChild(child)
                            add_items(child, p)
                except PermissionError as e:
                    logger.warning(f"Permission denied scanning {p}: {e}")
            
            add_items(root_item, self.project_path)
            root_item.setExpanded(True)
            
        except Exception as e:
            self.term(f"[ERROR: {e}]")
        
        self.term(f"[FILES: {count[0]} loaded]")
        self.set_status(f"{count[0]} files")

    def get_file_icon(self, path: Path) -> QIcon:
        ext = path.suffix.lower()
        color = EXT_COLORS.get(ext, "#888888")
        
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QColor(color))
        painter.setBrush(QColor(color))
        painter.drawRoundedRect(2, 2, 12, 12, 2, 2)
        painter.end()
        
        return QIcon(pixmap)

    def get_folder_icon(self) -> QIcon:
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QColor(ATLAN_GOLD))
        painter.setBrush(QColor(ATLAN_GOLD))
        painter.drawRect(2, 6, 12, 8)
        painter.drawRect(2, 4, 5, 3)
        painter.end()
        
        return QIcon(pixmap)

    def on_file_clicked(self, item):
        file_path = item.data(0, Qt.ItemDataRole.UserRole)
        if file_path:
            path = Path(file_path)
            if path.exists():
                self.open_file_in_tab(path)

    def save_current_file(self):
        if hasattr(self, 'current_file') and self.current_file:
            try:
                content = self.editor.toPlainText()
                self.current_file.write_text(content)
                self.term(f"Saved {self.current_file.name}", level="success")
                self.show_notification(f"Saved {self.current_file.name}", NotificationType.SUCCESS)
                self.show_toast(f"Saved {self.current_file.name}", ToastType.SUCCESS)
                
                current = self.tab_widget.currentIndex()
                tab_name = self.tab_widget.tabText(current)
                if tab_name in self.modified_tabs:
                    self.modified_tabs.remove(tab_name)
                    if tab_name.startswith("*"):
                        self.tab_widget.setTabText(current, tab_name[1:])
            except Exception as e:
                self.term(f"Cannot save - {e}", level="error")
                self.show_toast(f"Save failed: {e}", ToastType.ERROR)
        else:
            filename, _ = QFileDialog.getSaveFileName(self, "SAVE FILE", "", "Python Files (*.py);;All Files (*)")
            if filename:
                try:
                    content = self.editor.toPlainText()
                    Path(filename).write_text(content)
                    self.current_file = Path(filename)
                    self.term(f"Saved {filename}", level="success")
                    self.show_notification(f"Saved {filename}", NotificationType.SUCCESS)
                    self.show_toast(f"Saved {filename}", ToastType.SUCCESS)
                except Exception as e:
                    self.term(f"Cannot save - {e}", level="error")
                    self.show_toast(f"Save failed: {e}", ToastType.ERROR)

    def save_file_as(self):
        """Save current editor content to a new file (always prompts)."""
        default_name = self.current_file.name if hasattr(self, 'current_file') and self.current_file else "untitled.py"
        filename, _ = QFileDialog.getSaveFileName(
            self, "SAVE AS", default_name,
            "Python Files (*.py);;All Files (*)"
        )
        if filename:
            try:
                content = self.editor.toPlainText()
                path = Path(filename)
                path.write_text(content, encoding="utf-8")
                self.current_file = path
                current = self.tab_widget.currentIndex()
                self.tab_widget.setTabText(current, path.name)
                self.term(f"[SAVED AS: {path.name}]")
                self.show_notification(f"Saved as {path.name}", NotificationType.SUCCESS)
            except Exception as e:
                self.term(f"[ERROR: Cannot save - {e}]")
                self.show_notification(f"Save failed: {e}", NotificationType.ERROR)

    def show_docs(self):
        QDesktopServices.openUrl(QUrl("https://github.com/seraphonixstudios/CrackedCodev2"))

    def show_about(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("ABOUT CRACKEDCODE")
        dialog.setMinimumSize(450, 520)
        dialog.setModal(True)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("CRACKEDCODE")
        title.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {ATLAN_GREEN}; font-family: Consolas;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("AUTONOMOUS NEURAL SYSTEM v2.6.4")
        subtitle.setStyleSheet(f"font-size: 12px; color: {ATLAN_GOLD}; font-family: Consolas;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        desc = QLabel("Local AI Coding Assistant\n100% Offline - No Cloud Required")
        desc.setStyleSheet("font-size: 11px; color: #888; font-family: Consolas;")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"background-color: {ATLAN_GREEN};")
        line.setFixedHeight(1)
        layout.addWidget(line)

        features_text = (
            "<b style='color:#FFD700'>Core Features:</b><br>"
            "- Autonomous Application Production (OpenClaw-style)<br>"
            "- Agent Orchestration & Multi-Agent Swarm<br>"
            "- Voice Commands & Voice Typing<br>"
            "- Image Analysis & Vision Processing<br>"
            "- Code Generation & Execution<br>"
            "- Task Queue & Pipeline Processing<br>"
            "<br>"
            "<b style='color:#FFD700'>Engine Features:</b><br>"
            "- Streaming Responses<br>"
            "- Response Caching with SHA256<br>"
            "- Context Management (20 turns)<br>"
            "- Retry Logic with Exponential Backoff<br>"
            "- Unified Intelligence Mode<br>"
            "<br>"
            "<b style='color:#FFD700'>UI Features:</b><br>"
            "- Tabbed Editor with Syntax Highlighting<br>"
            "- Searchable Terminal (Ctrl+F)<br>"
            "- Command History & Autocomplete<br>"
            "- Toast Notifications<br>"
            "- Matrix Rain Effect<br>"
            "- File Tree with Icons<br>"
            "- Pulse Indicators & Task Filtering"
        )

        features = QLabel(features_text)
        features.setStyleSheet("font-size: 11px; color: #00FF41; font-family: Consolas; line-height: 1.6;")
        features.setWordWrap(True)
        layout.addWidget(features)

        line2 = QFrame()
        line2.setFrameShape(QFrame.Shape.HLine)
        line2.setStyleSheet(f"background-color: {ATLAN_GREEN};")
        line2.setFixedHeight(1)
        layout.addWidget(line2)

        tech = QLabel("Built with PyQt6 + Ollama | MIT License")
        tech.setStyleSheet("font-size: 10px; color: #666; font-family: Consolas;")
        tech.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(tech)

        close_btn = QPushButton("CLOSE")
        close_btn.clicked.connect(dialog.close)
        layout.addWidget(close_btn)

        dialog.exec()

    def show_settings(self):
        """Open the settings/preferences dialog."""
        if not SETTINGS_AVAILABLE:
            QMessageBox.warning(self, "Settings", "Settings dialog not available")
            return
        dlg = SettingsDialog(self.config, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            # Reload config
            self.load_config()
            # Re-initialize affected subsystems
            if self.engine:
                self.engine.config = self.config
            self.term("Settings updated", level="success")
            self.show_toast("Settings saved", ToastType.SUCCESS)

    def set_mode(self, mode):
        if mode == "plan":
            state = "ON" if self.plan_btn.isChecked() else "OFF"
            if self.engine:
                self.engine.plan_enabled = self.plan_btn.isChecked()
            self.set_status(f"PLAN: {state}")
            self.term(f"[MODE] PLAN: {state}")
        elif mode == "build":
            state = "ON" if self.build_btn.isChecked() else "OFF"
            if self.engine:
                self.engine.build_enabled = self.build_btn.isChecked()
            self.set_status(f"BUILD: {state}")
            self.term(f"[MODE] BUILD: {state}")

    def exec_code(self):
        code = self.editor.toPlainText()
        if not code.strip():
            self.term("No code to run", level="warning")
            self.show_toast("No code to execute", ToastType.WARNING)
            return
        
        self.term(f"Executing {len(code)} chars...", level="info")
        self.set_status("EXECUTING...")
        self.progress_bar.setValue(10)
        
        # Activity indicator
        if ENHANCEMENTS_AVAILABLE and isinstance(self.statusBar(), EnhancedStatusBar):
            self.statusBar().start_activity()
        
        try:
            import tempfile
            import subprocess
            import os
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
                f.write(code)
                tmp_path = f.name
            
            self.progress_bar.setValue(30)
            
            result = subprocess.run(
                [sys.executable, tmp_path],
                capture_output=True,
                text=True,
                timeout=60,
                encoding='utf-8'
            )
            
            self.progress_bar.setValue(80)
            
            try:
                os.unlink(tmp_path)
            except Exception as e:
                logger.warning(f"Could not remove temp file {tmp_path}: {e}")
            
            if result.stdout:
                self.term(f"Output:\n{result.stdout}", level="success")
            if result.stderr:
                self.term(f"Error:\n{result.stderr}", level="error")
            
            if result.returncode == 0:
                self.term("Execution successful", level="success")
                self.set_status("READY")
                self.show_notification("Execution successful", NotificationType.SUCCESS)
            else:
                self.term(f"Exit code: {result.returncode}", level="error")
                self.set_status("ERROR")
                self.show_notification("Execution failed", NotificationType.ERROR)
                
        except subprocess.TimeoutExpired:
            self.term("Execution timed out (60s)", level="error")
            self.show_toast("Execution timed out", ToastType.ERROR)
            self.set_status("TIMEOUT")
        except Exception as e:
            self.term(f"{type(e).__name__}: {e}", level="error")
            self.show_toast(f"Execution error: {e}", ToastType.ERROR)
            self.set_status("ERROR")
        finally:
            self.progress_bar.setValue(100)
            QTimer.singleShot(500, lambda: self.progress_bar.setValue(0))
            if ENHANCEMENTS_AVAILABLE and isinstance(self.statusBar(), EnhancedStatusBar):
                self.statusBar().stop_activity()

    def toggle_voice(self):
        if not self.voice or not self.voice.is_ready:
            self.term("[VOICE: not available]")
            return

        if self.voice_recording:
            self.voice_recording = False
            self.voice_btn.setChecked(False)
            self.set_status("READY")
            self.term("[VOICE] Recording stopped")
            self.voice.stop_session()
        else:
            self.voice_recording = True
            self.voice_btn.setChecked(True)
            self.set_status("RECORDING...")
            self.term("[VOICE] Recording... Speak now!")
            self._record_voice()

    def _record_voice(self):
        if not self.voice_recording or not self.voice:
            return

        try:
            # Use the unified engine's listen method
            result = self.voice.listen(duration=5.0, use_vad=False)
            if result.success and result.text:
                transcribed = result.text.strip()
                self.term(f"[VOICE] '{transcribed}'")

                # Use unified command processor
                command = self.voice.processor.parse(transcribed)
                if command.command_type.value != "unknown":
                    self.term(f"[CMD] {command.command_type.value} (conf={command.confidence:.2f})")
                    executed = self.voice.processor.execute(command)
                    if executed:
                        self.voice.speak(f"Executed {command.command_type.value}")
                    else:
                        self.voice.speak(f"Recognized {command.command_type.value}")
                else:
                    # No command detected - treat as input text
                    self.term_input.setText(transcribed)
                    if self.orchestrator:
                        intent = self.engine.parse_intent(transcribed)
                        agent, task = self.orchestrator.delegate(intent, transcribed)
                        self.term(f"[DELEGATED] -> {agent}")
                        self.update_orchestrator_display()
            elif result.error:
                self.term(f"[VOICE ERROR] {result.error}")

            if self.voice_recording:
                QTimer.singleShot(300, self._record_voice)
        except Exception as e:
            logger.error(f"Voice recording error: {e}")
            self.term(f"[VOICE ERROR] {e}")
            self.voice_recording = False
            self.voice_btn.setChecked(False)
            self.set_status("READY")

    def process_voice_command(self, text: str) -> bool:
        """Process voice text using the unified engine's command processor."""
        if not self.voice:
            return False
        command = self.voice.processor.parse(text)
        if command.command_type.value != "unknown":
            return self.voice.processor.execute(command)
        return False

    def run_term(self):
        cmd = self.term_input.text().strip()
        if not cmd:
            return
        
        global COMMAND_HISTORY, HISTORY_INDEX
        if cmd not in COMMAND_HISTORY:
            COMMAND_HISTORY.append(cmd)
        HISTORY_INDEX = -1
        
        self.term(f"> {cmd}")
        self.term_input.clear()
        self.process_prompt(cmd)

    def process_prompt(self, text):
        self.set_status("PROCESSING...")
        self.progress_bar.setValue(10)

        if not self.plan_btn.isChecked():
            self.term("[PLAN MODE OFF - processing skipped]")
            self.set_status("WAITING")
            self.progress_bar.setValue(0)
            return

        if not self.engine:
            self.term("[ERROR] No engine available")
            self.set_status("ERROR")
            self.progress_bar.setValue(0)
            return

        try:
            import asyncio
            
            intent = self.engine.parse_intent(text)
            self.progress_bar.setValue(20)
            
            if self.orchestrator:
                agent, task = self.orchestrator.delegate(intent, text)
                self.term(f"[INTENT] {intent.value} -> [AGENT] {agent}")
                self.update_orchestrator_display()

            self.progress_bar.setValue(40)
            
            streaming = self.config.get("streaming_enabled", True)
            full_response = ""
            
            if streaming:
                self.term("< ", end="")
                
                def stream_callback(chunk):
                    nonlocal full_response
                    full_response += chunk
                    self.terminal.insertPlainText(chunk)
                    self.terminal.moveCursor(QTextCursor.MoveOperation.End)
                    QApplication.processEvents()
                
                response = asyncio.run(self.engine.process(text, streaming=True, callback=stream_callback))
                self.term("")
            else:
                response = asyncio.run(self.engine.process(text))
                full_response = response.text
            
            self.progress_bar.setValue(80)
            
            if response.success:
                if not streaming:
                    self.term(f"< {response.text[:800]}")
                    if len(response.text) > 800:
                        self.term(f"< ... [{len(response.text) - 800} more chars]")
                self.show_notification("Response complete", NotificationType.SUCCESS)
            else:
                self.term(f"[ERROR] {response.error}")
                self.show_notification(f"Error: {response.error}", NotificationType.ERROR)
            
            self.term(f"[COMPLETED in {response.execution_time:.2f}s]")
            
            if self.orchestrator and 'task' in locals():
                self.orchestrator.complete_task(task.task_id, full_response or response.text)
                self.update_orchestrator_display()
            
            self.set_status("READY")
            
        except Exception as e:
            self.term(f"[ERROR] {type(e).__name__}: {e}")
            self.set_status("ERROR")
            self.show_notification(f"Error: {e}", NotificationType.ERROR)
            if 'task' in locals():
                self.orchestrator.fail_task(task.task_id, str(e))
                self.update_orchestrator_display()
        
        self.progress_bar.setValue(100)
        QTimer.singleShot(500, lambda: self.progress_bar.setValue(0))
        self.update_task_status()

    def term(self, text: str, end: str = "\n", level: str = "info"):
        """Enhanced terminal output with timestamps and color coding."""
        if hasattr(self, 'terminal'):
            import time
            timestamp = time.strftime("%H:%M:%S")
            
            # Color-code based on level
            prefixes = {
                "info":      f"[{timestamp}]",
                "success":   f"[{timestamp}] ✓",
                "warning":   f"[{timestamp}] ⚠",
                "error":     f"[{timestamp}] ✗",
                "voice":     f"[{timestamp}] 🎤",
                "ai":        f"[{timestamp}] 🤖",
                "reasoning": f"[{timestamp}] 🧠",
            }
            prefix = prefixes.get(level, f"[{timestamp}]")
            
            self.terminal.append(f"{prefix} {text}")
            self.terminal.moveCursor(QTextCursor.MoveOperation.End)

    def toggle_full(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def restore_state(self):
        g = self.settings.value("geometry")
        if g:
            self.restoreGeometry(g)
        s = self.settings.value("windowState")
        if s:
            self.restoreState(s)

    def closeEvent(self, e):
        # Plugin shutdown hook
        if PLUGINS_AVAILABLE:
            try:
                execute_hook(HookPoint.SYSTEM_SHUTDOWN)
            except Exception as ex:
                logger.warning(f"Plugin shutdown hook error: {ex}")
        
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        
        # Stop file watcher
        if self.file_watcher:
            self.file_watcher.stop()
            logger.info("FileWatcher stopped")
        
        # Stop git panel refresh
        if self.git_panel:
            self.git_panel.shutdown()
        
        # Stop voice engine
        if self.voice:
            self.voice.shutdown()
        
        logger.info("CrackedCode GUI closing")
        e.accept()


def main():
    try:
        app = QApplication(sys.argv)
        app.setApplicationName("CrackedCode")
        app.setOrganizationName("SeraphonixStudios")
        
        # Check single instance AFTER QApplication exists
        sock = QLocalSocket()
        sock.connectToServer("CrackedCode_SingleInstance")
        if sock.state() == QLocalSocket.LocalSocketState.ConnectedState:
            QMessageBox.warning(None, "CrackedCode", "Already running!")
            return
        
        # Clean up stale socket from previous crash, then create server
        QLocalServer.removeServer("CrackedCode_SingleInstance")
        server = QLocalServer()
        if not server.listen("CrackedCode_SingleInstance"):
            logger.warning(f"Single instance server failed: {server.errorString()}")
        
        win = CrackedCodeGUI()
        win.show()
        
        app.exec()
    except Exception as e:
        print(f"GUI Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
