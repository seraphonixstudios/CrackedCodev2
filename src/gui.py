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
        
        lbl = QLabel("PROJECT FILES")
        l.addWidget(lbl)
        
        self.files_list = QListWidget()
        l.addWidget(self.files_list)
        
        btn_layout = QHBoxLayout()
        new_btn = QPushButton("NEW")
        new_btn.clicked.connect(self.new_proj)
        open_btn = QPushButton("OPEN")
        open_btn.clicked.connect(self.open_proj)
        btn_layout.addWidget(new_btn)
        btn_layout.addWidget(open_btn)
        l.addLayout(btn_layout)
        
        return panel

    def create_toolbar(self):
        tb = QToolBar()
        tb.setMovable(False)
        self.addToolBar(tb)
        
        self.plan_btn = QPushButton("PLAN")
        self.plan_btn.setCheckable(True)
        self.plan_btn.setChecked(True)
        tb.addWidget(self.plan_btn)
        
        self.build_btn = QPushButton("BUILD")
        self.build_btn.setCheckable(True)
        self.build_btn.setChecked(True)
        tb.addWidget(self.build_btn)
        
        tb.addSeparator()
        
        self.mic_btn = QPushButton("VOICE")
        self.mic_btn.setCheckable(True)
        self.mic_btn.clicked.connect(self.toggle_voice)
        tb.addWidget(self.mic_btn)
        
        exec_btn = QPushButton("EXECUTE")
        exec_btn.clicked.connect(self.exec_code)
        tb.addWidget(exec_btn)

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
            self.scan_project_files(f)

    def open_proj(self):
        f = QFileDialog.getExistingDirectory(self, "OPEN PROJECT")
        if f:
            self.config["project_root"] = f
            self.term(f"OPENED: {f}")
            self.scan_project_files(f)

    def scan_project_files(self, root):
        self.files_list.clear()
        path = Path(root)
        if path.exists():
            for p in path.rglob("*"):
                if p.is_file() and p.suffix == ".py":
                    self.files_list.addItem(str(p.relative_to(path)))

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
        if code.strip():
            self.term(f">>> EXECUTING...\n{code}")
            self.status_lbl.setText("EXECUTING...")

    def debug_code(self):
        self.term(">>> DEBUG MODE...")

    def run_term(self):
        cmd = self.term_input.text()
        if cmd:
            self.term(f"$ {cmd}")
            self.process_prompt(cmd)
            self.term_input.clear()

    def process_prompt(self, text):
        self.term(f">>> {text}")
        self.status_lbl.setText("PROCESSING...")
        
        if not self.plan_btn.isChecked():
            self.term("[PLAN MODE OFF - No action taken]")
            self.status_lbl.setText("WAITING")
            return
        
        self.term("")
        self.term("="*40)
        self.term("PROCESSING WITH AI AGENTS...")
        self.term("="*40)

    def toggle_voice(self):
        if self.mic_btn.isChecked():
            self.term("[VOICE INPUT ON - Speak now...]")
            self.status_lbl.setText("LISTENING...")
        else:
            self.term("[VOICE INPUT OFF]")
            self.status_lbl.setText("WAITING")

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