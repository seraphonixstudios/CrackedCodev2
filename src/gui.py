import sys
import os
import json
import logging
import random
import time
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QMenuBar, QMenu, QToolBar,
    QStatusBar, QLabel, QFileDialog, QMessageBox, QTabWidget,
    QListWidget, QSplitter, QGroupBox, QCheckBox, QComboBox, QSpinBox,
    QScrollArea, QFrame, QDialog
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QSettings, QUrl
from PyQt6.QtGui import (
    QAction, QIcon, QFont, QColor, QTextCursor, QKeySequence,
    QGuiApplication, QDesktopServices, QPainter
)
from PyQt6.QtNetwork import QLocalSocket, QLocalServer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s'
)
logger = logging.getLogger("CrackedCodeGUI")

ATLAN_GREEN = "#00FF41"
ATLAN_CYAN = "#00FFFF"
ATLAN_GOLD = "#FFD700"
ATLAN_RED = "#FF3333"
ATLAN_PURPLE = "#9D00FF"


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
        self.load_config()
        self.setup_atlan_theme()
        self.init_ui()
        self.init_matrix()
        self.restore_state()
        logger.info("CrackedCode GUI started")

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
        main = QVBoxLayout(central)
        main.setContentsMargins(0, 0, 0, 0)
        
        self.create_menu()
        self.create_toolbar()
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.create_left())
        splitter.addWidget(self.create_right())
        splitter.setSizes([300, 900])
        main.addWidget(splitter)
        
        self.create_status()

    def create_menu(self):
        mb = self.menuBar()
        
        m_file = mb.addMenu("FILE")
        m_file.addAction("NEW PROJECT", self.new_proj)
        m_file.addAction("OPEN PROJECT", self.open_proj)
        m_file.addSeparator()
        m_file.addAction("SETTINGS", self.show_settings)
        m_file.addSeparator()
        m_file.addAction("EXIT", self.close)
        
        m_edit = mb.addMenu("EDIT")
        m_edit.addAction("UNDO")
        m_edit.addAction("REDO")
        m_edit.addSeparator()
        m_edit.addAction("CUT")
        m_edit.addAction("COPY")
        m_edit.addAction("PASTE")
        
        m_view = mb.addMenu("VIEW")
        m_view.addAction("TOGGLE LEFT PANEL")
        m_view.addAction("TOGGLE TERMINAL")
        m_view.addSeparator()
        m_view.addAction("FULLSCREEN", self.toggle_full)
        
        m_run = mb.addMenu("RUN")
        m_run.addAction("EXECUTE CODE", self.exec_code)
        m_run.addAction("DEBUG", self.debug_code)
        m_run.addSeparator()
        m_run.addAction("PLAN MODE", lambda: self.set_mode("plan"))
        m_run.addAction("BUILD MODE", lambda: self.set_mode("build"))
        
        m_help = mb.addMenu("HELP")
        m_help.addAction("DOCS", self.show_docs)
        m_help.addAction("ABOUT", self.show_about)

    def create_toolbar(self):
        tb = QToolBar("MAIN")
        tb.setMovable(False)
        self.addToolBar(tb)
        
        self.plan_btn = QPushButton("[PLAN]")
        self.plan_btn.setCheckable(True)
        self.plan_btn.setChecked(True)
        self.plan_btn.clicked.connect(lambda: self.set_mode("plan"))
        tb.addWidget(self.plan_btn)
        
        self.build_btn = QPushButton("[BUILD]")
        self.build_btn.setCheckable(True)
        self.build_btn.setChecked(True)
        self.build_btn.clicked.connect(lambda: self.set_mode("build"))
        tb.addWidget(self.build_btn)
        
        tb.addSeparator()
        
        exec_btn = QPushButton(">> EXECUTE")
        exec_btn.clicked.connect(self.exec_code)
        tb.addWidget(exec_btn)
        
        tb.addSeparator()
        
        tb.addWidget(QLabel("MODEL:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems(["qwen3:8b-gpu", "dolphin-llama3:8b-gpu", "llava:13b-gpu"])
        self.model_combo.setCurrentText(self.config.get("model", "qwen3:8b-gpu"))
        tb.addWidget(self.model_combo)

    def create_left(self):
        panel = QFrame()
        panel.setFrameShape(QFrame.Shape.StyledPanel)
        l = QVBoxLayout(panel)
        
        self.tabs = QTabWidget()
        
        files = QWidget()
        fl = QVBoxLayout(files)
        self.files_list = QListWidget()
        fl.addWidget(QLabel("PROJECT FILES"))
        fl.addWidget(self.files_list)
        self.tabs.addTab(files, "FILES")
        
        agents = QWidget()
        al = QVBoxLayout(agents)
        self.agents_list = QListWidget()
        self.agents_list.addItems([
            "SUPERVISOR - Orchestrates",
            "ARCHITECT - Designs structure",
            "CODER - Writes code",
            "EXECUTOR - Runs safely",
            "REVIEWER - Analyzes"
        ])
        al.addWidget(QLabel("AGENTS"))
        al.addWidget(self.agents_list)
        self.tabs.addTab(agents, "AGENTS")
        
        l.addWidget(self.tabs)
        return panel

    def create_right(self):
        panel = QFrame()
        l = QVBoxLayout(panel)
        l.setContentsMargins(4, 4, 4, 4)
        
        self.editor = QTextEdit()
        self.editor.setPlaceholderText("// Enter code here...\n// Press >> EXECUTE or Ctrl+Return to run")
        l.addWidget(self.editor, 3)
        
        term_group = QGroupBox("TERMINAL OUTPUT")
        tl = QVBoxLayout(term_group)
        
        self.terminal = QTextEdit()
        self.terminal.setReadOnly(True)
        tl.addWidget(self.terminal)
        
        tin = QHBoxLayout()
        tin.addWidget(QLabel(">"))
        self.term_input = QLineEdit()
        self.term_input.setPlaceholderText("enter command...")
        self.term_input.returnPressed.connect(self.run_term)
        tin.addWidget(self.term_input)
        tl.addLayout(tin)
        
        l.addWidget(term_group, 2)
        return panel

    def create_status(self):
        sb = QStatusBar()
        self.setStatusBar(sb)
        self.status_lbl = QLabel("SYSTEM ONLINE // WAITING FOR INPUT")
        sb.addWidget(self.status_lbl)
        sb.addPermanentWidget(QLabel(f"MODEL: {self.config.get('model', 'qwen3:8b-gpu')}"))
        sb.addPermanentWidget(QLabel("PLAN: ON | BUILD: ON"))

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
            self.term(f"PROJECT: {f}")

    def open_proj(self):
        f = QFileDialog.getExistingDirectory(self, "OPEN PROJECT")
        if f:
            self.config["project_root"] = f
            self.term(f"OPENED: {f}")

    def show_settings(self):
        self.term("SETTINGS: Coming soon...")

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
        if code.strip():
            self.term(f">>> EXECUTING...\n{code}")
            self.status_lbl.setText("EXECUTING...")

    def debug_code(self):
        self.term(">>> DEBUG MODE...")

    def run_term(self):
        cmd = self.term_input.text()
        if cmd:
            self.term(f"$ {cmd}")
            self.term_input.clear()

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