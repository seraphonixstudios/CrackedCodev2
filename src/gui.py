import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import logging
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
    from src.voice_typing import VoiceTyping
    VOICE_AVAILABLE = True
except ImportError:
    VOICE_AVAILABLE = False

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s'
)
logger = logging.getLogger("CrackedCodeGUI")

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
    def __init__(self, gui_ref: Any = None):
        self.gui = gui_ref
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

    def delegate(self, intent: Intent, prompt: str) -> Tuple[str, AgentTask]:
        agent_name = self.delegation_rules.get(intent, "Coder")
        task = AgentTask(intent.value, prompt, agent_name)
        self.tasks.append(task)
        self.task_queue.append(task)
        self.agents[agent_name]["status"] = "active"
        self._process_queue()
        return agent_name, task

    def _process_queue(self):
        if self.current_task and self.current_task.status == TaskStatus.RUNNING:
            return
        
        if self.task_queue:
            task = self.task_queue.pop(0)
            task.start()
            self.current_task = task
            self._update_gui()

    def complete_task(self, task_id: str, result: str):
        for task in self.tasks:
            if task.task_id == task_id:
                task.complete(result)
                if task.agent in self.agents:
                    self.agents[task.agent]["status"] = "idle"
                    self.agents[task.agent]["tasks_completed"] += 1
                self.current_task = None
                self._process_queue()
                break

    def fail_task(self, task_id: str, error: str):
        for task in self.tasks:
            if task.task_id == task_id:
                task.fail(error)
                if task.agent in self.agents:
                    self.agents[task.agent]["status"] = "idle"
                self.current_task = None
                self._process_queue()
                break

    def cancel_task(self, task_id: str):
        for task in self.tasks:
            if task.task_id == task_id:
                task.cancel()
                if task.agent in self.agents:
                    self.agents[task.agent]["status"] = "idle"
                if self.current_task and self.current_task.task_id == task_id:
                    self.current_task = None
                    self._process_queue()
                break

    def get_active_agents(self) -> List[str]:
        return [name for name, data in self.agents.items() if data["status"] == "active"]

    def get_queue_status(self) -> Dict:
        return {
            "pending": len([t for t in self.tasks if t.status == TaskStatus.PENDING]),
            "running": len([t for t in self.tasks if t.status == TaskStatus.RUNNING]),
            "completed": len([t for t in self.tasks if t.status == TaskStatus.COMPLETED]),
            "failed": len([t for t in self.tasks if t.status == TaskStatus.FAILED]),
            "active_agents": self.get_active_agents(),
            "current_task": self.current_task.to_dict() if self.current_task else None,
        }

    def clear_completed(self):
        self.tasks = [t for t in self.tasks if t.status in [TaskStatus.PENDING, TaskStatus.RUNNING]]

    def _update_gui(self):
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
        
        self.load_config()
        self.setup_atlan_theme()
        self.init_engine()
        self.init_orchestrator()
        self.init_ui()
        self.init_voice()
        self.init_matrix()
        self.init_clipboard()
        self.restore_state()
        self.setup_paste_handler()
        
        logger.info("CrackedCode GUI v2.6.0 started")

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
                self.term("[VOICE: not available - install sounddevice]")
            if hasattr(self, 'voice_btn'):
                self.voice_btn.setEnabled(False)
            return
        
        try:
            self.voice = VoiceTyping(model_size="base")
            if self.voice.is_available:
                if hasattr(self, 'terminal'):
                    self.term("[VOICE: ready]")
                logger.info("Voice typing initialized")
            else:
                if hasattr(self, 'terminal'):
                    self.term("[VOICE: model failed to load]")
                if hasattr(self, 'voice_btn'):
                    self.voice_btn.setEnabled(False)
        except Exception as e:
            logger.error(f"Voice init failed: {e}")
            if hasattr(self, 'terminal'):
                self.term(f"[VOICE ERROR: {e}]")
            if hasattr(self, 'voice_btn'):
                self.voice_btn.setEnabled(False)

    def load_config(self):
        config_path = Path("config.json")
        if config_path.exists():
            with open(config_path) as f:
                self.config = json.load(f)
        else:
            self.config = {"model": "qwen3:8b-gpu", "project_root": "."}

    def setup_atlan_theme(self):
        self.setWindowTitle("CRACKEDCODE v2.6.0 // AUTONOMOUS NEURAL SYSTEM")
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
        
        self.terminal = SearchableTerminal()
        self.terminal.setToolTip("Terminal output - Ctrl+F to search")
        
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
        save_as_action.triggered.connect(self.save_current_file)
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
        
        docs_action = QAction("DOCUMENTATION", self)
        docs_action.setToolTip("Open documentation")
        docs_action.triggered.connect(self.show_docs)
        help_menu.addAction(docs_action)
        
        about_action = QAction("ABOUT", self)
        about_action.setToolTip("About CrackedCode")
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

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
        
        self.agent_panel = AgentPanelWidget(self.orchestrator)
        layout.addWidget(self.agent_panel)
        
        self.task_queue = TaskQueueWidget(self.orchestrator)
        layout.addWidget(self.task_queue)
        
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
        self.plan_btn.setToolTip("Toggle PLAN mode")
        self.plan_btn.clicked.connect(lambda: self.set_mode("plan"))
        tb.addWidget(self.plan_btn)
        
        self.build_btn = QPushButton("BUILD")
        self.build_btn.setCheckable(True)
        self.build_btn.setChecked(True)
        self.build_btn.setToolTip("Toggle BUILD mode")
        self.build_btn.clicked.connect(lambda: self.set_mode("build"))
        tb.addWidget(self.build_btn)
        
        tb.addSeparator()
        
        exec_btn = QPushButton("EXECUTE")
        exec_btn.setToolTip("Execute code in editor")
        exec_btn.clicked.connect(self.exec_code)
        tb.addWidget(exec_btn)
        
        self.voice_btn = QPushButton("VOICE")
        self.voice_btn.setCheckable(True)
        self.voice_btn.setToolTip("Toggle voice input")
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
        sb = QStatusBar()
        self.setStatusBar(sb)
        
        self.status_lbl = QLabel("READY")
        self.status_lbl.setToolTip("Current status")
        sb.addWidget(self.status_lbl)
        
        sb.addSeparator()
        
        self.cache_lbl = QLabel("Cache: 0")
        self.cache_lbl.setToolTip("Response cache size")
        sb.addPermanentWidget(self.cache_lbl)
        
        sb.addSeparator()
        
        self.ollama_lbl = QLabel("OLLAMA: ...")
        self.ollama_lbl.setToolTip("Ollama connection status")
        sb.addPermanentWidget(self.ollama_lbl)
        
        self.model_lbl = QLabel("MODEL: none")
        self.model_lbl.setToolTip("Current AI model")
        sb.addPermanentWidget(self.model_lbl)
        
        self.task_status_lbl = QLabel("Tasks: 0")
        self.task_status_lbl.setToolTip("Task count")
        sb.addPermanentWidget(self.task_status_lbl)
        
        sb.addSeparator()
        
        self.time_lbl = QLabel("")
        sb.addPermanentWidget(self.time_lbl)
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)
        self.update_time()
        
        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self.update_stats)
        self.stats_timer.start(5000)

    def update_time(self):
        current_time = time.strftime("%H:%M:%S")
        self.time_lbl.setText(current_time)
        
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
        if not self.editor.eventFilter:
            self.editor.installEventFilter(self)
        self.set_status(f"Editing: {tab_name}")

    def on_modification_changed(self, modified: bool):
        current = self.tab_widget.currentIndex()
        tab_name = self.tab_widget.tabText(current)
        
        if modified:
            if tab_name not in self.modified_tabs:
                self.modified_tabs.add(tab_name)
                self.tab_widget.setTabText(current, f"*{tab_name}")
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
            self.tab_widget.addTab(editor, name)
            self.open_files[name] = editor
            self.tab_widget.setCurrentWidget(editor)
            self.editor = editor
            self.current_file = filepath
            self.term(f"[OPENED] {filepath.name}")
            self.show_notification(f"Opened {filepath.name}", NotificationType.SUCCESS)
        except Exception as e:
            self.term(f"[ERROR] Cannot open {filepath.name}: {e}")

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
            self.term("[COPIED: terminal content to clipboard]")

    def clear_terminal(self):
        self.terminal.clear()
        self.terminal.clear_highlights()
        self.term("[TERMINAL CLEARED]")

    def stop_current_operation(self):
        self.voice_recording = False
        if hasattr(self, 'voice_btn'):
            self.voice_btn.setChecked(False)
        self.set_status("STOPPED")
        self.progress_bar.setValue(0)
        self.term("[OPERATION STOPPED]")
        self.show_notification("Operation stopped", NotificationType.WARNING)

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
            self.term(f"[NEW PROJECT: {f}]")
            self.scan_project_files(f)
            self.show_notification(f"New project: {Path(f).name}", NotificationType.SUCCESS)

    def open_proj(self):
        f = QFileDialog.getExistingDirectory(self, "OPEN PROJECT")
        if f:
            self.config["project_root"] = f
            self.term(f"[OPENED: {f}]")
            self.scan_project_files(f)
            self.show_notification(f"Opened project: {Path(f).name}", NotificationType.SUCCESS)

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
                except PermissionError:
                    pass
            
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
                self.term(f"[SAVED: {self.current_file.name}]")
                self.show_notification(f"Saved {self.current_file.name}", NotificationType.SUCCESS)
                
                current = self.tab_widget.currentIndex()
                tab_name = self.tab_widget.tabText(current)
                if tab_name in self.modified_tabs:
                    self.modified_tabs.remove(tab_name)
                    if tab_name.startswith("*"):
                        self.tab_widget.setTabText(current, tab_name[1:])
            except Exception as e:
                self.term(f"[ERROR: Cannot save - {e}]")
        else:
            filename, _ = QFileDialog.getSaveFileName(self, "SAVE FILE", "", "Python Files (*.py);;All Files (*)")
            if filename:
                try:
                    content = self.editor.toPlainText()
                    Path(filename).write_text(content)
                    self.current_file = Path(filename)
                    self.term(f"[SAVED: {filename}]")
                    self.show_notification(f"Saved {filename}", NotificationType.SUCCESS)
                except Exception as e:
                    self.term(f"[ERROR: Cannot save - {e}]")

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

        subtitle = QLabel("AUTONOMOUS NEURAL SYSTEM v2.6.0")
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

    def set_mode(self, mode):
        if mode == "plan":
            state = "ON" if self.plan_btn.isChecked() else "OFF"
            self.set_status(f"PLAN: {state}")
            self.term(f"[MODE] PLAN: {state}")
        elif mode == "build":
            state = "ON" if self.build_btn.isChecked() else "OFF"
            self.set_status(f"BUILD: {state}")
            self.term(f"[MODE] BUILD: {state}")

    def exec_code(self):
        code = self.editor.toPlainText()
        if not code.strip():
            self.term("[EXECUTE: No code to run]")
            return
        
        self.term(f">[EXECUTING] {len(code)} chars...")
        self.set_status("EXECUTING...")
        self.progress_bar.setValue(10)
        
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
            except Exception:
                pass
            
            if result.stdout:
                self.term(f"[OUTPUT]:\n{result.stdout}")
            if result.stderr:
                self.term(f"[ERROR]:\n{result.stderr}")
            
            if result.returncode == 0:
                self.term("[DONE] Execution successful")
                self.set_status("READY")
                self.show_notification("Execution successful", NotificationType.SUCCESS)
            else:
                self.term(f"[FAILED] Exit code: {result.returncode}")
                self.set_status("ERROR")
                self.show_notification("Execution failed", NotificationType.ERROR)
                
        except subprocess.TimeoutExpired:
            self.term("[ERROR] Execution timed out (60s)")
            self.set_status("TIMEOUT")
        except Exception as e:
            self.term(f"[ERROR] {type(e).__name__}: {e}")
            self.set_status("ERROR")
        finally:
            self.progress_bar.setValue(100)
            QTimer.singleShot(500, lambda: self.progress_bar.setValue(0))

    def toggle_voice(self):
        if not self.voice or not self.voice.is_available:
            self.term("[VOICE: not available]")
            return

        if self.voice_recording:
            self.voice_recording = False
            self.voice_btn.setChecked(False)
            self.set_status("READY")
            self.term("[VOICE] Recording stopped")
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
            result = self.voice.listen_and_transcribe(duration=5.0)
            if result.success and result.text:
                transcribed = result.text.strip()
                self.term(f"[VOICE] '{transcribed}'")
                
                if not self.process_voice_command(transcribed):
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

    VOICE_COMMANDS = {
        "stop": ["stop", "cancel", "abort", "exit", "quit", "halt"],
        "execute": ["run", "execute", "start", "go", "do it"],
        "save": ["save", "store", "write to file"],
        "copy": ["copy", "clipboard", "copy output"],
        "clear": ["clear", "wipe", "reset"],
        "voice": ["voice", "speech", "record", "listen"],
    }

    def process_voice_command(self, text: str) -> bool:
        text_lower = text.lower().strip()
        
        for cmd, keywords in self.VOICE_COMMANDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    self.term(f"[CMD] Detected: {cmd}")
                    if cmd == "stop":
                        self.stop_current_operation()
                    elif cmd == "execute":
                        self.exec_code()
                    elif cmd == "save":
                        self.save_current_file()
                    elif cmd == "copy":
                        self.copy_output()
                    elif cmd == "clear":
                        self.clear_terminal()
                    elif cmd == "voice":
                        self.toggle_voice()
                    return True
        
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

    def term(self, text: str, end: str = "\n"):
        if hasattr(self, 'terminal'):
            self.terminal.append(text)
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
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        logger.info("CrackedCode GUI closing")
        e.accept()


def check_single():
    sock = QLocalSocket()
    sock.connectToServer("CrackedCode_SingleInstance")
    if sock.state() == QLocalSocket.LocalSocketState.ConnectedState:
        return False
    return True


def main():
    try:
        if not check_single():
            QMessageBox.warning(None, "CrackedCode", "Already running!")
            return
        
        server = QLocalServer()
        try:
            server.listen("CrackedCode_SingleInstance")
        except Exception:
            pass
        
        app = QApplication(sys.argv)
        app.setApplicationName("CrackedCode")
        app.setOrganizationName("SeraphonixStudios")
        
        win = CrackedCodeGUI()
        win.show()
        
        sys.exit(app.exec())
    except Exception as e:
        print(f"GUI Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
