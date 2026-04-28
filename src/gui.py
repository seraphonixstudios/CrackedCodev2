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
from typing import Optional, Dict, List, Any, Tuple
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QMenuBar, QMenu, QToolBar,
    QStatusBar, QLabel, QFileDialog, QMessageBox, QTabWidget,
    QListWidget, QSplitter, QGroupBox, QCheckBox, QComboBox, QSpinBox,
    QScrollArea, QFrame, QDialog, QProgressBar, QSlider
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QSettings, QUrl, QMimeData
from PyQt6.QtGui import (
    QAction, QIcon, QFont, QColor, QTextCursor, QKeySequence,
    QGuiApplication, QDesktopServices, QPainter, QDragEnterEvent, QDropEvent, QPixmap, QImage
)
from PyQt6.QtNetwork import QLocalSocket, QLocalServer
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QGuiApplication

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

VOICE_COMMANDS = {
    "write": ["write", "create", "generate", "make"],
    "execute": ["run", "execute", "start", "launch"],
    "debug": ["fix", "debug", "repair", "error"],
    "review": ["review", "analyze", "check", "audit"],
    "search": ["search", "find", "grep", "look"],
    "save": ["save", "store", "keep", "export"],
    "open": ["open", "load", "read", "import"],
    "copy": ["copy", "duplicate", "clone", "clipboard"],
    "paste": ["paste", "insert", "drop"],
    "voice": ["voice", "speech", "speak", "record"],
    "help": ["help", "assist", "support", "guide"],
    "stop": ["stop", "cancel", "abort", "exit"],
}


class AgentTask:
    def __init__(self, task_id: str, intent: str, prompt: str, agent: str = "Coder"):
        self.task_id = task_id
        self.intent = intent
        self.prompt = prompt
        self.agent = agent
        self.status = "pending"
        self.result = None
        self.error = None
        self.timestamp = time.time()

    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "intent": self.intent,
            "prompt": self.prompt,
            "agent": self.agent,
            "status": self.status,
            "result": self.result,
            "error": self.error,
        }


class AgentOrchestrator:
    def __init__(self):
        self.agents = {
            "Supervisor": {"role": "coordinates", "status": "idle", "capabilities": ["all"]},
            "Architect": {"role": "design", "status": "idle", "capabilities": ["planning", "architecture"]},
            "Coder": {"role": "implementation", "status": "idle", "capabilities": ["code", "write", "modify"]},
            "Executor": {"role": "execution", "status": "idle", "capabilities": ["run", "execute", "test"]},
            "Reviewer": {"role": "analysis", "status": "idle", "capabilities": ["review", "debug", "optimize"]},
            "Searcher": {"role": "discovery", "status": "idle", "capabilities": ["search", "find", "grep"]},
        }
        self.tasks: List[AgentTask] = []
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

    def delegate(self, intent: Intent, prompt: str) -> Tuple[str, str]:
        agent = self.delegation_rules.get(intent, "Coder")
        task_id = f"task_{len(self.tasks)}_{int(time.time())}"
        task = AgentTask(task_id, intent.value, prompt, agent)
        self.tasks.append(task)
        self.agents[agent]["status"] = "active"
        return agent, task_id

    def complete_task(self, task_id: str, result: str):
        for task in self.tasks:
            if task.task_id == task_id:
                task.status = "completed"
                task.result = result
                self.agents[task.agent]["status"] = "idle"
                break

    def fail_task(self, task_id: str, error: str):
        for task in self.tasks:
            if task.task_id == task_id:
                task.status = "failed"
                task.error = error
                self.agents[task.agent]["status"] = "idle"
                break

    def get_active_agents(self) -> List[str]:
        return [name for name, data in self.agents.items() if data["status"] == "active"]

    def get_queue_status(self) -> Dict:
        return {
            "pending": len([t for t in self.tasks if t.status == "pending"]),
            "completed": len([t for t in self.tasks if t.status == "completed"]),
            "failed": len([t for t in self.tasks if t.status == "failed"]),
            "active_agents": self.get_active_agents(),
        }


class ImageDropZone(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.image_callback = None
        self.setMinimumHeight(80)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: #0a0a0a;
                border: 2px dashed {ATLAN_CYAN};
                border-radius: 8px;
            }}
            QFrame:hover {{
                border-color: {ATLAN_GREEN};
            }}
        """)

    def set_callback(self, callback):
        self.image_callback = callback

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasImage() or self._has_image(event.mimeData()):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if self._has_image(event.mimeData()):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        mime = event.mimeData()
        if mime.hasImage():
            image = mime.imageData()
            if self.image_callback:
                self.image_callback(image)
            event.acceptProposedAction()
        elif self._has_image(mime):
            if mime.hasUrls():
                for url in mime.urls():
                    path = url.toLocalFile()
                    if path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                        if self.image_callback:
                            pixmap = QPixmap(path)
                            self.image_callback(pixmap)
                        break
            event.acceptProposedAction()

    def _has_image(self, mime: QMimeData) -> bool:
        return mime.hasUrls() and any(
            url.toLocalFile().lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp'))
            for url in mime.urls()
        )

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Drop Image Here or Paste (Ctrl+V)")


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
        w = self.width() // self.cols
        for i, drop in enumerate(self.drops):
            color = QColor(0, 255, 65, random.randint(100, 200))
            painter.setPen(color)
            font = QFont("Consolas", 10)
            font.setBold(True)
            painter.setFont(font)
            char = random.choice(self.matrix_chars)
            painter.drawText(i * w, int(drop["y"]), w, 20, Qt.AlignmentFlag.AlignCenter, char)


class CrackedCodeGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = {}
        self.settings = QSettings("SeraphonixStudios", "CrackedCode")
        self.engine = None
        self.voice: Optional[Any] = None
        self.voice_recording = False
        self.load_config()
        self.setup_atlan_theme()
        self.init_ui()
        self.init_engine()
        self.init_voice()
        self.init_matrix()
        self.init_orchestrator()
        self.init_clipboard()
        self.restore_state()
        self.setup_paste_handler()
        logger.info("CrackedCode GUI started")

    def init_orchestrator(self):
        self.orchestrator = AgentOrchestrator()
        self.update_agents_list()
        logger.info("Agent orchestrator initialized")

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
        except Exception as e:
            logger.error(f"Engine init failed: {e}")

    def init_voice(self):
        if not VOICE_AVAILABLE:
            self.term("[VOICE: not available]")
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
            self.term("[VOICE: init failed]")
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
        self.setWindowTitle("CRACKEDCODE v2.2.0 // ATLANTEAN NEURAL SYSTEM")
        self.setMinimumSize(1200, 800)
        
        self.atlan_font = QFont("Consolas", 11)
        self.atlan_header = QFont("Consolas", 14, QFont.Weight.Bold)
        
        self.setStyleSheet(f"""
            QMainWindow {{ background-color: #0a0a0a; }}
            QWidget {{ background-color: #0a0a0a; color: {ATLAN_GREEN}; font-family: Consolas; }}
            QMenuBar {{ background-color: #0d0d0d; color: {ATLAN_GREEN}; border-bottom: 2px solid {ATLAN_GREEN}; }}
            QMenuBar::item:selected {{ background-color: {ATLAN_GREEN}; color: #000; }}
            QMenu {{ background-color: #0d0d0d; color: {ATLAN_GREEN}; border: 1px solid {ATLAN_GREEN}; }}
            QMenu::item:selected {{ background-color: {ATLAN_GREEN}; color: #000; }}
            QToolBar {{ background-color: #0d0d0d; border-bottom: 2px solid {ATLAN_GREEN}; }}
            QPushButton {{ 
                background-color: #1a1a1a; 
                color: {ATLAN_GREEN}; 
                border: 1px solid {ATLAN_GREEN}; 
                padding: 6px 12px;
                font-family: Consolas;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {ATLAN_GREEN}; color: #000; }}
            QPushButton:checked {{ background-color: {ATLAN_GREEN}; color: #000; }}
            QTextEdit {{ 
                background-color: #050505; 
                color: {ATLAN_GREEN}; 
                border: 1px solid #333; 
                font-family: Consolas;
            }}
            QLineEdit {{ 
                background-color: #050505; 
                color: {ATLAN_GREEN}; 
                border: 1px solid {ATLAN_GREEN}; 
                font-family: Consolas;
            }}
            QListWidget {{ 
                background-color: #050505; 
                color: {ATLAN_GREEN}; 
                border: 1px solid #333; 
            }}
            QListWidget::item:selected {{ background-color: {ATLAN_GREEN}; color: #000; }}
            QTabWidget::pane {{ border: 1px solid {ATLAN_GREEN}; }}
            QTabBar::tab {{ 
                background-color: #111; 
                color: {ATLAN_GREEN}; 
                border: 1px solid #333; 
                padding: 6px 12px;
            }}
            QTabBar::tab:selected {{ 
                background-color: {ATLAN_GREEN}; 
                color: #000; 
            }}
            QGroupBox {{ 
                border: 2px solid {ATLAN_GREEN}; 
                margin-top: 10px;
                font-weight: bold;
            }}
            QGroupBox::title {{ 
                color: {ATLAN_GOLD}; 
                subcontrol-origin: margin;
                left: 10px;
            }}
            QStatusBar {{ 
                background-color: #0d0d0d; 
                color: {ATLAN_GREEN}; 
                border-top: 2px solid {ATLAN_GREEN}; 
            }}
            QLabel {{ color: {ATLAN_GREEN}; }}
            QComboBox {{ 
                background-color: #1a1a1a; 
                color: {ATLAN_GREEN}; 
                border: 1px solid {ATLAN_GREEN}; 
            }}
            QSplitter::handle {{ background-color: {ATLAN_GREEN}; }}
        """)

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main = QHBoxLayout(central)
        main.setContentsMargins(4, 4, 4, 4)
        main.setSpacing(4)
        
        left = self.create_sidebar()
        main.addWidget(left, 1)
        
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        
        self.create_toolbar()
        
        self.editor = QTextEdit()
        self.editor.setPlaceholderText("// Enter code...")
        rl.addWidget(self.editor, 2)
        
        term = QGroupBox("TERMINAL")
        tl = QVBoxLayout(term)
        self.terminal = QTextEdit()
        self.terminal.setReadOnly(True)
        tl.addWidget(self.terminal)
        
        tin = QHBoxLayout()
        tin.addWidget(QLabel(">"))
        self.term_input = QLineEdit()
        self.term_input.returnPressed.connect(self.run_term)
        tin.addWidget(self.term_input)
        tl.addLayout(tin)
        
        rl.addWidget(term, 1)
        
        main.addWidget(right, 3)
        
        self.create_status()

    def create_sidebar(self):
        panel = QFrame()
        panel.setMaximumWidth(250)
        l = QVBoxLayout(panel)
        l.setSpacing(4)

        lbl = QLabel("PROJECT")
        l.addWidget(lbl)

        self.files_list = QListWidget()
        self.files_list.itemDoubleClicked.connect(self.on_file_clicked)
        self.files_list.setAcceptDrops(True)
        l.addWidget(self.files_list)

        btn_layout = QHBoxLayout()
        new_btn = QPushButton("NEW")
        new_btn.clicked.connect(self.new_proj)
        open_btn = QPushButton("OPEN")
        open_btn.clicked.connect(self.open_proj)
        btn_layout.addWidget(new_btn)
        btn_layout.addWidget(open_btn)
        l.addLayout(btn_layout)

        l.addWidget(QLabel(""))
        l.addWidget(QLabel("AGENTS"))

        self.agents_list = QListWidget()
        self.agents_list.itemClicked.connect(self.on_agent_selected)
        l.addWidget(self.agents_list)

        l.addWidget(QLabel(""))
        l.addWidget(QLabel("TASK"))

        self.task_lbl = QLabel("Idle")
        l.addWidget(self.task_lbl)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumHeight(8)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid {ATLAN_GREEN};
                border-radius: 4px;
                background-color: #0a0a0a;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background-color: {ATLAN_GREEN};
            }}
        """)
        l.addWidget(self.progress_bar)

        return panel

    def create_toolbar(self):
        tb = QToolBar()
        tb.setMovable(False)
        self.addToolBar(tb)

        self.plan_btn = QPushButton("PLAN")
        self.plan_btn.setCheckable(True)
        self.plan_btn.setChecked(True)
        self.plan_btn.clicked.connect(lambda: self.set_mode("plan"))
        tb.addWidget(self.plan_btn)

        self.build_btn = QPushButton("BUILD")
        self.build_btn.setCheckable(True)
        self.build_btn.setChecked(True)
        self.build_btn.clicked.connect(lambda: self.set_mode("build"))
        tb.addWidget(self.build_btn)

        tb.addSeparator()

        exec_btn = QPushButton("EXECUTE")
        exec_btn.clicked.connect(self.exec_code)
        tb.addWidget(exec_btn)

        self.voice_btn = QPushButton("VOICE")
        self.voice_btn.setCheckable(True)
        self.voice_btn.clicked.connect(self.toggle_voice)
        tb.addWidget(self.voice_btn)

        tb.addSeparator()

        copy_btn = QPushButton("COPY")
        copy_btn.clicked.connect(self.copy_output)
        tb.addWidget(copy_btn)

        clear_btn = QPushButton("CLEAR")
        clear_btn.clicked.connect(self.clear_terminal)
        tb.addWidget(clear_btn)

    def create_status(self):
        sb = QStatusBar()
        self.setStatusBar(sb)
        self.status_lbl = QLabel("READY")
        sb.addWidget(self.status_lbl)
        
        self.ollama_lbl = QLabel("OLLAMA: ...")
        sb.addPermanentWidget(self.ollama_lbl)
        
        self.model_lbl = QLabel("MODEL: none")
        sb.addPermanentWidget(self.model_lbl)
        
    def update_status(self, status: Dict):
        if hasattr(self, 'ollama_lbl'):
            self.ollama_lbl.setText(f"OLLAMA: {'ON' if status.get('ollama_available') else 'OFF'}")
        if hasattr(self, 'model_lbl'):
            self.model_lbl.setText(f"MODEL: {status.get('model', 'none')}")
        
    def toggle_dev_console(self):
        status = self.engine.get_status() if self.engine else {}
        
        if hasattr(self, 'dev_console') and self.dev_console.isVisible():
            self.dev_console.hide()
        else:
            if not hasattr(self, 'dev_console'):
                self.dev_console = QTextEdit()
                self.dev_console.setWindowTitle("Dev Console (F12)")
                self.dev_console.setGeometry(100, 100, 400, 300)
            
            self.dev_console.setPlainText("")
            self.dev_console.append("=== DEV CONSOLE v%s ===" % status.get("version", "?"))
            self.dev_console.append(f"Ollama: {status.get('ollama_available', False)}")
            self.dev_console.append(f"Models: {status.get('ollama_models', [])}")
            self.dev_console.append(f"Model: {status.get('model', 'none')}")
            self.dev_console.append(f"Plan: {status.get('plan', False)}")
            self.dev_console.append(f"Build: {status.get('build', False)}")
            self.dev_console.append(f"History: {status.get('history_length', 0)} turns")
            self.dev_console.append("="*30)
            self.dev_console.show()
            self.dev_console.raise_()
            self.dev_console.activateWindow()

    def get_ollama_models(self):
        if self.engine:
            return self.engine.get_status().get("ollama_models", [])
        return []

    def keyPressEvent(self, event):
        modifiers = event.modifiers()

        if event.key() == Qt.Key.Key_F12:
            self.toggle_dev_console()
        elif event.key() == Qt.Key.Key_Escape:
            self.stop_current_operation()
        elif event.matches(QKeySequence.StandardKey.Copy):
            self.copy_output()
        elif event.matches(QKeySequence.StandardKey.Paste):
            self.handle_paste()
        elif event.matches(QKeySequence.StandardKey.SelectAll):
            self.editor.selectAll()
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
                    self.term(f"[PASTE: {len(text)} chars]")
                else:
                    self.term_input.setText(text)
                    self.term(f"[PASTE: text]")

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

        img_base64 = base64.b64encode(img_bytes).decode()
        self.pending_image = img_bytes

        self.term(f"[IMAGE: {image.width()}x{image.height()}, {len(img_bytes)} bytes]")

        if self.engine and hasattr(self.engine, 'vision'):
            try:
                import asyncio
                result = asyncio.run(self.engine.vision.analyze_image(img_bytes))
                self.term(f"[VISION: {result[:200]}...]")
            except Exception as e:
                self.term(f"[VISION ERROR: {e}]")

    def _is_code_snippet(self, text: str) -> bool:
        code_indicators = ['def ', 'class ', 'function ', 'import ', 'from ', 'const ', 'let ', 'var ',
                         'if (', 'if(', 'for (', 'for(', 'while (', 'while(', 'print(', 'return ']
        return any(text.lstrip().startswith(ind) for ind in code_indicators) or text.count('\n') > 2

    def copy_output(self):
        text = self.terminal.toPlainText()
        if text:
            self.clipboard.setText(text)
            self.term("[COPIED: terminal to clipboard]")

    def clear_terminal(self):
        self.terminal.clear()
        self.term("[CLEARED]")

    def stop_current_operation(self):
        self.voice_recording = False
        if hasattr(self, 'voice_btn'):
            self.voice_btn.setChecked(False)
        self.status_lbl.setText("STOPPED")
        self.progress_bar.setValue(0)
        self.term("[STOPPED]")

    def update_agents_list(self):
        if hasattr(self, 'agents_list'):
            self.agents_list.clear()
            active = self.orchestrator.get_active_agents()
            for name, data in self.orchestrator.agents.items():
                status = f"[ACTIVE] " if data["status"] == "active" else ""
                self.agents_list.addItem(f"{status}{name} ({data['role']})")

    def on_agent_selected(self, item):
        agent_name = item.text().split("(")[0].replace("[ACTIVE] ", "").strip()
        self.term(f"[AGENT: selected {agent_name}]")

    def update_progress(self, value: int, text: str = ""):
        self.progress_bar.setValue(value)
        if text:
            self.task_lbl.setText(text)

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
            self.term(f"[PROJECT: {f}]")
            if hasattr(self, 'task_lbl'):
                self.task_lbl.setText("Creating project...")
            self.scan_project_files(f)

    def open_proj(self):
        f = QFileDialog.getExistingDirectory(self, "OPEN PROJECT")
        if f:
            self.config["project_root"] = f
            self.term(f"[OPENED: {f}]")
            if hasattr(self, 'task_lbl'):
                self.task_lbl.setText("Ready")
            self.scan_project_files(f)

    def scan_project_files(self, root):
        self.files_list.clear()
        self.project_path = Path(root)
        
        if not self.project_path.exists():
            self.term(f"[ERROR: Path not found: {root}]")
            return
        
        self.term(f"[LOADING: {root}]")
        
        count = 0
        try:
            for p in self.project_path.rglob("*"):
                if p.is_file():
                    relative = str(p.relative_to(self.project_path))
                    self.files_list.addItem(relative)
                    count += 1
                    if count > 50:
                        break
        except Exception as e:
            self.term(f"[ERROR: {e}]")
        
        self.term(f"[FILES: {count} found]")
        
        if hasattr(self, 'task_lbl'):
            self.task_lbl.setText(f"{count} files")

    def on_file_clicked(self, item):
        if hasattr(self, 'project_path'):
            file_path = self.project_path / item.text()
            if file_path.exists():
                content = file_path.read_text(errors='ignore')
                self.editor.setPlainText(content)
                self.term(f"[OPENED: {item.text()}]")
            else:
                self.term(f"[ERROR: File not found]")

    def show_settings(self):
        self.term("="*50)
        self.term("LOGIN PAGE IMPLEMENTATION PLAN")
        self.term("="*50)
        self.term("")
        self.term("1. AUTHENTICATION SYSTEM")
        self.term("   - User database (JSON file with hashed passwords)")
        self.term("   - Login dialog with username/password fields")
        self.term("   - Session management with tokens")
        self.term("   - Optional: OAuth, 2FA support")
        self.term("")
        self.term("2. LOGIN PAGE (HTML/CSS/JS)")
        self.term("   - Embedded webview or PyQt6 QWebEngineView")
        self.term("   - Atlantean-themed login form")
        self.term("   - Remember me checkbox")
        self.term("   - Password reset flow")
        self.term("")
        self.term("3. SECURITY FEATURES")
        self.term("   - Password hashing (bcrypt/argon2)")
        self.term("   - Rate limiting on login attempts")
        self.term("   - Session timeout")
        self.term("   - Audit logging")
        self.term("")
        self.term("4. INTEGRATION")
        self.term("   - Pre-launch login check in gui.py")
        self.term("   - User context in blackboard")
        self.term("   - Per-user settings persistence")
        self.term("")
        self.term("="*50)
        self.term("Ready to build? Say YES to proceed.")
        self.term("="*50)

    def show_docs(self):
        QDesktopServices.openUrl(QUrl("https://github.com/seraphonixstudios/CrackedCodev2"))

    def show_about(self):
        QMessageBox.about(self, "ABOUT",
            "CRACKEDCODE v2.2.0\n"
            "ATLANTEAN NEURAL SYSTEM\n"
            "Local AI Coding Assistant\n\n"
            "Built with PyQt6 + Matrix Effects\n"
            "MIT License"
        )

    def set_mode(self, mode):
        if mode == "plan":
            self.status_lbl.setText(f"PLAN: {'ON' if self.plan_btn.isChecked() else 'OFF'}")
        elif mode == "build":
            self.status_lbl.setText(f"BUILD: {'ON' if self.build_btn.isChecked() else 'OFF'}")
        self.term(f"MODE: {mode}")

    def exec_code(self):
        code = self.editor.toPlainText()
        if not code.strip():
            return
        self.term(f">>> EXECUTING...\n{code[:200]}{'...' if len(code) > 200 else ''}")
        self.status_lbl.setText("EXECUTING...")
        try:
            import sys
            import tempfile
            import subprocess
            import os
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                tmp_path = f.name
            result = subprocess.run([sys.executable, tmp_path], capture_output=True, text=True, timeout=30)
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
            if result.stdout:
                self.term(f">>> OUTPUT:\n{result.stdout}")
            if result.stderr:
                self.term(f">>> ERROR:\n{result.stderr}")
            self.term(">>> DONE" if result.returncode == 0 else ">>> FAILED")
        except Exception as e:
            self.term(f">>> EXECUTION ERROR: {e}")
        finally:
            self.status_lbl.setText("READY")

    def debug_code(self):
        self.term(">>> DEBUG MODE...")

    def toggle_voice(self):
        if not self.voice or not self.voice.is_available:
            self.term("[VOICE: not available]")
            return

        if self.voice_recording:
            self.voice_recording = False
            self.voice_btn.setChecked(False)
            self.status_lbl.setText("READY")
            self.term("[VOICE: stopped]")
        else:
            self.voice_recording = True
            self.voice_btn.setChecked(True)
            self.status_lbl.setText("RECORDING...")
            self.term("[VOICE: recording - speak now]")
            self._record_voice()

    def detect_voice_command(self, text: str) -> Optional[str]:
        text_lower = text.lower().strip()
        for cmd, keywords in VOICE_COMMANDS.items():
            for keyword in keywords:
                if text_lower.startswith(keyword) or f" {keyword} " in text_lower:
                    return cmd
        return None

    def process_voice_command(self, text: str):
        cmd = self.detect_voice_command(text)
        if cmd:
            self.term(f"[CMD: detected '{cmd}' from '{text[:30]}...']")
            if cmd == "stop":
                self.stop_current_operation()
                return True
            elif cmd == "voice":
                self.toggle_voice()
                return True
            elif cmd == "save":
                self.exec_code()
                return True
            elif cmd == "copy":
                self.copy_output()
                return True
        return False

    def _record_voice(self):
        if not self.voice_recording or not self.voice:
            return

        try:
            result = self.voice.listen_and_transcribe(duration=5.0)
            if result.success and result.text:
                transcribed = result.text
                self.term(f"[VOICE: '{transcribed[:50]}...']")

                if not self.process_voice_command(transcribed):
                    self.term_input.setText(transcribed)
                    if self.orchestrator:
                        agent, task_id = self.orchestrator.delegate(Intent.CHAT, transcribed)
                        self.term(f"[DELEGATED: to {agent}]")
                        self.update_agents_list()
            elif result.error:
                self.term(f"[VOICE ERROR: {result.error}]")

            if self.voice_recording:
                QTimer.singleShot(500, self._record_voice)
        except Exception as e:
            logger.error(f"Voice recording error: {e}")
            self.term(f"[VOICE ERROR: {e}]")
            self.voice_recording = False
            self.voice_btn.setChecked(False)
            self.status_lbl.setText("READY")

    def run_term(self):
        cmd = self.term_input.text().strip()
        if not cmd:
            return
        self.term(f">> {cmd}")
        self.term_input.clear()
        self.process_prompt(cmd)

    def process_prompt(self, text):
        self.update_progress(10, "Processing...")
        self.status_lbl.setText("PROCESSING...")

        if not self.plan_btn.isChecked():
            self.term("[PLAN OFF]")
            self.status_lbl.setText("WAITING")
            self.update_progress(0)
            return

        if not self.engine:
            self.term("[NO ENGINE]")
            self.status_lbl.setText("ERROR")
            self.update_progress(0)
            return

        if self.orchestrator:
            intent = self.engine.parse_intent(text)
            agent, task_id = self.orchestrator.delegate(intent, text)
            self.term(f"[DELEGATED: {text[:30]}... -> {agent}]")
            self.update_agents_list()
            self.update_progress(30)

        try:
            import asyncio
            self.update_progress(50)
            response = asyncio.run(self.engine.process(text))

            self.update_progress(90)
            if response.success:
                self.term("<<< " + response.text[:500])
            else:
                self.term("[ERROR: " + str(response.error) + "]")

            self.term(f"[took {response.execution_time:.2f}s]")

            if self.orchestrator:
                self.orchestrator.complete_task(task_id, response.text)
                self.update_agents_list()

        except Exception as e:
            self.term("[ERROR: " + type(e).__name__ + "]")
            if self.orchestrator and 'task_id' in locals():
                self.orchestrator.fail_task(task_id, str(e))
                self.update_agents_list()

        self.update_progress(100, "Done")
        self.status_lbl.setText("READY")
        QTimer.singleShot(500, lambda: self.update_progress(0))

    def term(self, text):
        self.terminal.append(text)
        self.terminal.moveCursor(QTextCursor.MoveOperation.End)

    def toggle_full(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def restore_state(self):
        g = self.settings.value("geometry")
        if g: self.restoreGeometry(g)
        s = self.settings.value("windowState")
        if s: self.restoreState(s)

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
    if not check_single():
        QMessageBox.warning(None, "CrackedCode", "Already running!")
        return
    
    app = QApplication(sys.argv)
    app.setApplicationName("CrackedCode")
    app.setOrganizationName("SeraphonixStudios")
    
    win = CrackedCodeGUI()
    win.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
