import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import logging
import random
import time
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
    QListWidget, QSplitter, QGroupBox, QCheckBox, QComboBox, QSpinBox,
    QScrollArea, QFrame, QDialog, QProgressBar, QSlider, QTreeWidget,
    QTreeWidgetItem, QStackedWidget, QSizePolicy, QDockWidget
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QSettings, QUrl, QMimeData, QSize
from PyQt6.QtGui import (
    QAction, QIcon, QFont, QColor, QTextCursor, QKeySequence,
    QGuiApplication, QDesktopServices, QPainter, QDragEnterEvent, QDropEvent, QPixmap, QImage, QPalette
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
ATLAN_DARK = "#0a0a0a"
ATLAN_MEDIUM = "#1a1a1a"
ATLAN_LIGHT = "#2a2a2a"


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


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


class AgentOrchestrator:
    def __init__(self, gui_ref: Any = None):
        self.gui = gui_ref
        self.agents = {
            "Supervisor": {
                "role": "coordinates", 
                "status": "idle", 
                "capabilities": ["all", "delegate", "manage"],
                "icon": "S",
                "color": ATLAN_PURPLE
            },
            "Architect": {
                "role": "design", 
                "status": "idle", 
                "capabilities": ["planning", "architecture", "blueprint"],
                "icon": "A",
                "color": ATLAN_CYAN
            },
            "Coder": {
                "role": "implementation", 
                "status": "idle", 
                "capabilities": ["code", "write", "modify", "create"],
                "icon": "C",
                "color": ATLAN_GREEN
            },
            "Executor": {
                "role": "execution", 
                "status": "idle", 
                "capabilities": ["run", "execute", "test", "deploy"],
                "icon": "E",
                "color": ATLAN_GOLD
            },
            "Reviewer": {
                "role": "analysis", 
                "status": "idle", 
                "capabilities": ["review", "debug", "optimize", "fix"],
                "icon": "R",
                "color": ATLAN_RED
            },
            "Searcher": {
                "role": "discovery", 
                "status": "idle", 
                "capabilities": ["search", "find", "grep", "analyze"],
                "icon": "F",
                "color": ATLAN_GREEN
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

    def update_rain(self):
        for drop in self.drops:
            drop["y"] += drop["speed"]
            if drop["y"] > self.height():
                drop["y"] = random.randint(-20, 0)
        self.update()

    def paintEvent(self, event):
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


class TaskQueueWidget(QWidget):
    task_selected = pyqtSignal(str)
    
    def __init__(self, orchestrator: AgentOrchestrator):
        super().__init__()
        self.orchestrator = orchestrator
        self.init_ui()
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.refresh)
        self.update_timer.start(500)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        header = QLabel("TASK QUEUE")
        header.setStyleSheet(f"font-weight: bold; color: {ATLAN_GOLD}; padding: 4px;")
        layout.addWidget(header)
        
        self.task_list = QListWidget()
        self.task_list.itemClicked.connect(lambda item: self.task_selected.emit(item.data(Qt.ItemDataRole.UserRole)))
        layout.addWidget(self.task_list)
        
        stats_layout = QHBoxLayout()
        self.pending_label = QLabel("Pending: 0")
        self.running_label = QLabel("Running: 0")
        self.completed_label = QLabel("Done: 0")
        stats_layout.addWidget(self.pending_label)
        stats_layout.addWidget(self.running_label)
        stats_layout.addWidget(self.completed_label)
        layout.addLayout(stats_layout)

    def refresh(self):
        self.task_list.clear()
        status = self.orchestrator.get_queue_status()
        
        for task in self.orchestrator.tasks[-10:]:
            status_icon = {
                TaskStatus.PENDING: "○",
                TaskStatus.RUNNING: "◐",
                TaskStatus.COMPLETED: "●",
                TaskStatus.FAILED: "✕",
                TaskStatus.CANCELLED: "⊘",
            }.get(task.status, "?")
            
            item_text = f"{status_icon} {task.agent}: {task.prompt[:30]}..."
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, task.task_id)
            
            if task.status == TaskStatus.RUNNING:
                item.setBackground(QColor(ATLAN_MEDIUM))
            elif task.status == TaskStatus.COMPLETED:
                item.setBackground(QColor("#0a1a0a"))
            elif task.status == TaskStatus.FAILED:
                item.setBackground(QColor("#1a0a0a"))
            
            self.task_list.addItem(item)
        
        self.pending_label.setText(f"Pending: {status['pending']}")
        self.running_label.setText(f"Running: {status['running']}")
        self.completed_label.setText(f"Done: {status['completed']}")


class AgentPanelWidget(QWidget):
    def __init__(self, orchestrator: AgentOrchestrator):
        super().__init__()
        self.orchestrator = orchestrator
        self.status_labels = {}
        self.init_ui()
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.refresh)
        self.update_timer.start(500)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        header = QLabel("AGENTS")
        header.setStyleSheet(f"font-weight: bold; color: {ATLAN_GOLD}; padding: 4px;")
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
                border: 1px solid #333;
                border-radius: 4px;
                padding: 4px;
                margin: 2px;
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
        info_layout.setSpacing(0)
        
        name_label = QLabel(name)
        name_label.setStyleSheet("font-weight: bold;")
        info_layout.addWidget(name_label)
        
        self.status_labels[name] = QLabel(data["status"])
        self.status_labels[name].setStyleSheet(f"color: #888; font-size: 10px;")
        info_layout.addWidget(self.status_labels[name])
        
        layout.addWidget(info)
        layout.addStretch()
        
        return frame

    def refresh(self):
        for name, data in self.orchestrator.agents.items():
            if name in self.status_labels:
                self.status_labels[name].setText(f"{data['status']} ({', '.join(data['capabilities'][:2])})")


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
        self.streaming_active = False
        self.notification_queue = []
        
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
        
        logger.info("CrackedCode GUI v2.4.0 started")

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
        self.editor.installEventFilter(self)

    def init_engine(self):
        try:
            self.engine = get_engine(self.config)
            logger.info(f"Engine model: {self.engine.model}")
            status = self.engine.get_status()
            self.update_status(status)
            if hasattr(self, 'terminal'):
                self.term(f"[ENGINE v{status['version']} loaded]")
                self.term(f"[OLLAMA: {len(status['ollama_models'])} models]")
                self.term("[READY] Type your prompt below...")
        except Exception as e:
            logger.error(f"Engine init failed: {e}")
            self.term(f"[ERROR: Engine failed - {e}]")

    def init_voice(self):
        if not VOICE_AVAILABLE:
            self.term("[VOICE: not available - install sounddevice]")
            if hasattr(self, 'voice_btn'):
                self.voice_btn.setEnabled(False)
            return
        
        try:
            self.voice = VoiceTyping(model_size="base")
            if self.voice.is_available:
                self.term("[VOICE: ready]")
                logger.info("Voice typing initialized")
            else:
                self.term("[VOICE: model failed to load]")
                if hasattr(self, 'voice_btn'):
                    self.voice_btn.setEnabled(False)
        except Exception as e:
            logger.error(f"Voice init failed: {e}")
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
        self.setWindowTitle("CRACKEDCODE v2.4.0 // ATLANTEAN NEURAL SYSTEM")
        self.setMinimumSize(1400, 900)
        
        self.atlan_font = QFont("Consolas", 11)
        self.atlan_header = QFont("Consolas", 14, QFont.Weight.Bold)
        
        self.setStyleSheet(f"""
            QMainWindow {{ background-color: {ATLAN_DARK}; }}
            QWidget {{ background-color: {ATLAN_DARK}; color: {ATLAN_GREEN}; font-family: Consolas; font-size: 11px; }}
            QMenuBar {{ background-color: {ATLAN_MEDIUM}; color: {ATLAN_GREEN}; border-bottom: 2px solid {ATLAN_GREEN}; }}
            QMenuBar::item:selected {{ background-color: {ATLAN_GREEN}; color: {ATLAN_DARK}; }}
            QMenu {{ background-color: {ATLAN_MEDIUM}; color: {ATLAN_GREEN}; border: 1px solid #333; }}
            QMenu::item:selected {{ background-color: {ATLAN_GREEN}; color: {ATLAN_DARK}; }}
            QToolBar {{ background-color: {ATLAN_MEDIUM}; border-bottom: 2px solid {ATLAN_GREEN}; spacing: 4px; padding: 4px; }}
            QPushButton {{ 
                background-color: {ATLAN_LIGHT}; 
                color: {ATLAN_GREEN}; 
                border: 1px solid {ATLAN_GREEN}; 
                padding: 8px 16px;
                font-family: Consolas;
                font-weight: bold;
                border-radius: 4px;
            }}
            QPushButton:hover {{ background-color: {ATLAN_GREEN}; color: {ATLAN_DARK}; }}
            QPushButton:checked {{ background-color: {ATLAN_GREEN}; color: {ATLAN_DARK}; }}
            QPushButton:pressed {{ background-color: {ATLAN_CYAN}; }}
            QPushButton:disabled {{ color: #555; border-color: #555; }}
            QTextEdit {{ 
                background-color: #050505; 
                color: {ATLAN_GREEN}; 
                border: 1px solid #333; 
                font-family: Consolas;
                border-radius: 4px;
            }}
            QTextEdit:focus {{ border: 1px solid {ATLAN_GREEN}; }}
            QLineEdit {{ 
                background-color: #050505; 
                color: {ATLAN_GREEN}; 
                border: 1px solid {ATLAN_GREEN}; 
                font-family: Consolas;
                padding: 6px;
                border-radius: 4px;
            }}
            QLineEdit:focus {{ border: 2px solid {ATLAN_GREEN}; }}
            QListWidget {{ 
                background-color: #050505; 
                color: {ATLAN_GREEN}; 
                border: 1px solid #333; 
                border-radius: 4px;
            }}
            QListWidget::item:selected {{ background-color: {ATLAN_GREEN}; color: {ATLAN_DARK}; }}
            QListWidget::item:hover {{ background-color: {ATLAN_LIGHT}; }}
            QTabWidget::pane {{ border: 1px solid {ATLAN_GREEN}; border-radius: 4px; }}
            QTabBar::tab {{ 
                background-color: {ATLAN_MEDIUM}; 
                color: {ATLAN_GREEN}; 
                border: 1px solid #333; 
                padding: 8px 16px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }}
            QTabBar::tab:selected {{ 
                background-color: {ATLAN_GREEN}; 
                color: {ATLAN_DARK}; 
            }}
            QGroupBox {{ 
                border: 2px solid {ATLAN_GREEN}; 
                margin-top: 10px;
                font-weight: bold;
                border-radius: 4px;
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
                padding: 4px;
                border-radius: 4px;
            }}
            QSplitter::handle {{ background-color: {ATLAN_GREEN}; }}
            QProgressBar {{
                border: 1px solid {ATLAN_GREEN};
                border-radius: 4px;
                background-color: {ATLAN_DARK};
                text-align: center;
                color: {ATLAN_GREEN};
            }}
            QProgressBar::chunk {{
                background-color: {ATLAN_GREEN};
                border-radius: 3px;
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
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QDockWidget::title {{
                background-color: {ATLAN_MEDIUM};
                color: {ATLAN_GOLD};
                padding: 4px;
            }}
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
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        
        self.editor = QTextEdit()
        self.editor.setPlaceholderText("Enter code here...")
        self.editor.setToolTip("Code editor - type or paste code here")
        self.tab_widget.addTab(self.editor, "untitled")
        self.open_files["untitled"] = self.editor
        
        rl.addWidget(self.tab_widget, 3)
        
        self.terminal = QTextEdit()
        self.terminal.setReadOnly(True)
        self.terminal.setToolTip("Terminal output")
        
        term_group = QGroupBox("TERMINAL")
        term_layout = QVBoxLayout(term_group)
        term_layout.setContentsMargins(4, 4, 4, 4)
        term_layout.addWidget(self.terminal)
        
        tin = QHBoxLayout()
        prompt_label = QLabel(">")
        prompt_label.setStyleSheet(f"color: {ATLAN_CYAN}; font-weight: bold;")
        tin.addWidget(prompt_label)
        
        self.term_input = QLineEdit()
        self.term_input.setPlaceholderText("Enter prompt or command...")
        self.term_input.setToolTip("Command input - press Enter to send")
        self.term_input.returnPressed.connect(self.run_term)
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
        
        save_action = QAction("SAVE", self)
        save_action.setShortcut(QKeySequence("Ctrl+S"))
        save_action.setToolTip("Save current file (Ctrl+S)")
        save_action.triggered.connect(self.save_current_file)
        file_menu.addAction(save_action)
        
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
        clear_action.setToolTip("Clear terminal output")
        clear_action.triggered.connect(self.clear_terminal)
        edit_menu.addAction(clear_action)
        
        view_menu = menubar.addMenu("VIEW")
        
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
        project_layout.addWidget(self.files_tree)
        
        btn_layout = QHBoxLayout()
        new_btn = QPushButton("NEW")
        new_btn.setToolTip("Create new project")
        new_btn.clicked.connect(self.new_proj)
        open_btn = QPushButton("OPEN")
        open_btn.setToolTip("Open project folder")
        open_btn.clicked.connect(self.open_proj)
        btn_layout.addWidget(new_btn)
        btn_layout.addWidget(open_btn)
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

    def create_toolbar(self):
        tb = QToolBar()
        tb.setMovable(False)
        tb.setIconSize(QSize(24, 24))
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
        stop_btn.setToolTip("Stop current operation")
        stop_btn.clicked.connect(self.stop_current_operation)
        stop_btn.setStyleSheet(f"color: {ATLAN_RED}; border-color: {ATLAN_RED};")
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

    def create_status(self):
        sb = QStatusBar()
        self.setStatusBar(sb)
        
        self.status_lbl = QLabel("READY")
        self.status_lbl.setToolTip("Current status")
        sb.addWidget(self.status_lbl)
        
        self.ollama_lbl = QLabel("OLLAMA: ...")
        self.ollama_lbl.setToolTip("Ollama connection status")
        sb.addPermanentWidget(self.ollama_lbl)
        
        self.model_lbl = QLabel("MODEL: none")
        self.model_lbl.setToolTip("Current AI model")
        sb.addPermanentWidget(self.model_lbl)
        
        self.task_status_lbl = QLabel("Tasks: 0")
        self.task_status_lbl.setToolTip("Task count")
        sb.addPermanentWidget(self.task_status_lbl)
        
        self.time_lbl = QLabel("")
        sb.addPermanentWidget(self.time_lbl)
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)
        self.update_time()

    def update_time(self):
        current_time = time.strftime("%H:%M:%S")
        self.time_lbl.setText(current_time)

    def update_status(self, status: Dict):
        if hasattr(self, 'ollama_lbl'):
            ollama_on = status.get('ollama_available', False)
            self.ollama_lbl.setText(f"OLLAMA: {'ON' if ollama_on else 'OFF'}")
            self.ollama_lbl.setStyleSheet(f"color: {'{ATLAN_GREEN}' if ollama_on else '{ATLAN_RED}'};")
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

    def toggle_streaming(self):
        enabled = self.stream_btn.isChecked()
        self.config["streaming_enabled"] = enabled
        mode_text = "STREAMING ON" if enabled else "STREAMING OFF"
        self.set_status(mode_text)
        self.term(f"[STREAM] {mode_text}")

    def close_tab(self, index):
        if self.tab_widget.count() > 1:
            tab_name = self.tab_widget.tabText(index)
            if tab_name in self.open_files:
                del self.open_files[tab_name]
            self.tab_widget.removeTab(index)
            self.term(f"[TAB] Closed {tab_name}")

    def on_tab_changed(self, index):
        tab_name = self.tab_widget.tabText(index)
        self.editor = self.tab_widget.widget(index)
        self.set_status(f"Editing: {tab_name}")

    def new_tab(self, name: str = None):
        if name is None:
            name = f"file_{self.tab_widget.count()}"
        editor = QTextEdit()
        editor.setPlaceholderText("Enter code here...")
        editor.setStyleSheet(self.editor.styleSheet())
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
            editor.setStyleSheet(self.editor.styleSheet())
            self.tab_widget.addTab(editor, name)
            self.open_files[name] = editor
            self.tab_widget.setCurrentWidget(editor)
            self.editor = editor
            self.current_file = filepath
            self.term(f"[OPENED] {filepath.name}")
        except Exception as e:
            self.term(f"[ERROR] Cannot open {filepath.name}: {e}")

    def toggle_dev_console(self):
        status = self.engine.get_status() if self.engine else {}
        
        if hasattr(self, 'dev_console') and self.dev_console.isVisible():
            self.dev_console.hide()
        else:
            if not hasattr(self, 'dev_console'):
                self.dev_console = QTextEdit()
                self.dev_console.setWindowTitle("Dev Console (F12)")
                self.dev_console.setGeometry(100, 100, 500, 400)
                self.dev_console.setStyleSheet("background-color: #0a0a0a; color: #00FF41; font-family: Consolas;")
            
            self.dev_console.setPlainText("")
            self.dev_console.append("=" * 50)
            self.dev_console.append(f"CRACKEDCODE DEV CONSOLE v{status.get('version', '?')}")
            self.dev_console.append("=" * 50)
            self.dev_console.append(f"Ollama Available: {status.get('ollama_available', False)}")
            self.dev_console.append(f"Models: {status.get('ollama_models', [])}")
            self.dev_console.append(f"Selected Model: {status.get('model', 'none')}")
            self.dev_console.append(f"Unified Mode: {status.get('unified_mode', False)}")
            self.dev_console.append(f"Streaming: {self.config.get('streaming_enabled', True)}")
            self.dev_console.append(f"Cache Size: {status.get('cache_size', 0)}")
            self.dev_console.append(f"Context Length: {status.get('context_length', 0)}")
            self.dev_console.append(f"Plan Mode: {status.get('plan', False)}")
            self.dev_console.append(f"Build Mode: {status.get('build', False)}")
            self.dev_console.append(f"History Length: {status.get('history_length', 0)}")
            self.dev_console.append("")
            self.dev_console.append("MODEL ROLES:")
            for model, info in status.get('model_roles', {}).items():
                self.dev_console.append(f"  {model}: {info.get('role', 'unknown')} ({info.get('strength', '')})")
            self.dev_console.append("")
            self.dev_console.append("ORCHESTRATOR STATUS:")
            if hasattr(self, 'orchestrator'):
                qstatus = self.orchestrator.get_queue_status()
                self.dev_console.append(f"  Pending: {qstatus['pending']}")
                self.dev_console.append(f"  Running: {qstatus['running']}")
                self.dev_console.append(f"  Completed: {qstatus['completed']}")
                self.dev_console.append(f"  Failed: {qstatus['failed']}")
                self.dev_console.append(f"  Active Agents: {qstatus['active_agents']}")
            self.dev_console.append("=" * 50)
            self.dev_console.show()
            self.dev_console.raise_()
            self.dev_console.activateWindow()

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
        else:
            super().keyPressEvent(event)

    def eventFilter(self, obj, event):
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
        self.term("[TERMINAL CLEARED]")

    def stop_current_operation(self):
        self.voice_recording = False
        if hasattr(self, 'voice_btn'):
            self.voice_btn.setChecked(False)
        self.set_status("STOPPED")
        self.progress_bar.setValue(0)
        self.term("[OPERATION STOPPED]")

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

    def open_proj(self):
        f = QFileDialog.getExistingDirectory(self, "OPEN PROJECT")
        if f:
            self.config["project_root"] = f
            self.term(f"[OPENED: {f}]")
            self.scan_project_files(f)

    def scan_project_files(self, root):
        self.files_tree.clear()
        self.project_path = Path(root)
        
        if not self.project_path.exists():
            self.term(f"[ERROR: Path not found: {root}]")
            return
        
        self.term(f"[SCANNING: {root}]")
        
        root_item = QTreeWidgetItem([root])
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
                            parent_item.addChild(child)
                            count[0] += 1
                        elif p.is_dir() and not p.name.startswith('.') and not p.name.startswith('__'):
                            child = QTreeWidgetItem([p.name])
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
                except Exception as e:
                    self.term(f"[ERROR: Cannot save - {e}]")

    def show_docs(self):
        QDesktopServices.openUrl(QUrl("https://github.com/seraphonixstudios/CrackedCodev2"))

    def show_about(self):
        QMessageBox.about(self, "ABOUT CRACKEDCODE",
            f"CRACKEDCODE v2.4.0\n"
            "ATLANTEAN NEURAL SYSTEM\n\n"
            "Local AI Coding Assistant\n"
            "100% Offline - No Cloud Required\n\n"
            "Built with PyQt6 + Ollama\n"
            "MIT License\n\n"
            "Features:\n"
            "- Agent Orchestration\n"
            "- Voice Commands\n"
            "- Image Analysis\n"
            "- Code Generation\n"
            "- Task Queue\n"
            "- Streaming Responses\n"
            "- Tabbed Editor\n"
            "- Response Caching\n"
            "- Unified Intelligence Mode"
        )

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
            else:
                self.term(f"[FAILED] Exit code: {result.returncode}")
                self.set_status("ERROR")
                
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
            else:
                self.term(f"[ERROR] {response.error}")
            
            self.term(f"[COMPLETED in {response.execution_time:.2f}s]")
            
            if self.orchestrator and 'task' in locals():
                self.orchestrator.complete_task(task.task_id, full_response or response.text)
                self.update_orchestrator_display()
            
            self.set_status("READY")
            
        except Exception as e:
            self.term(f"[ERROR] {type(e).__name__}: {e}")
            self.set_status("ERROR")
            if 'task' in locals():
                self.orchestrator.fail_task(task.task_id, str(e))
                self.update_orchestrator_display()
        
        self.progress_bar.setValue(100)
        QTimer.singleShot(500, lambda: self.progress_bar.setValue(0))
        self.update_task_status()

    def term(self, text: str, end: str = "\n"):
        if hasattr(self, 'terminal'):
            self.terminal.append(text)
            if end == "":
                pass
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
