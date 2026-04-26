import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import logging
import random
import time
import traceback
import io
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

from src.engine import get_engine, CrackedCodeEngine, Intent

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
        self.load_config()
        self.setup_atlan_theme()
        self.init_ui()
        self.init_engine()
        self.init_matrix()
        self.restore_state()
        logger.info("CrackedCode GUI started")

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
        if event.key() == Qt.Key.Key_F12:
            self.toggle_dev_console()
        else:
            super().keyPressEvent(event)

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
            self.term("[PLAN MODE OFF]")
            self.status_lbl.setText("WAITING")
            return
        
        import asyncio
        
        if self.engine:
            try:
                response = asyncio.run(self.engine.process(text))
                self.term(f"<<< {response.text[:500]}")
                if response.error:
                    self.term(f"[ERROR: {response.error}]")
                self.term(f"[took {response.execution_time:.2f}s]")
            except Exception as e:
                self.term(f"[PROCESS ERROR: {e}]")
                logger.exception("Process failed")
        else:
            self.term("[NO ENGINE]")
        
        self.status_lbl.setText("WAITING")

    def toggle_voice(self):
        if self.mic_btn.isChecked():
            self.start_voice_recording()
        else:
            self.stop_voice_recording()

    def start_voice_recording(self):
        self.term("[VOICE: Press SPACE to record]")
        self.status_lbl.setText("VOICE READY")
        try:
            self.voice_enabled = True
            self.term("[VOICE: Ready]")
        except Exception as e:
            self.term(f"[VOICE ERROR: {e}]")
            self.mic_btn.setChecked(False)

    def stop_voice_recording(self):
        self.term("[VOICE: Off]")
        self.status_lbl.setText("WAITING")
        self.voice_enabled = False

    def process_voice(self):
        try:
            import sounddevice as sd
            import numpy as np
            import wave
            
            self.term("[RECORDING 3s...]")
            self.status_lbl.setText("RECORDING...")
            
            audio = sd.rec(int(3000), samplerate=16000, channels=1, dtype=np.int16)
            sd.wait()
            
            buffer = io.BytesIO()
            with wave.open(buffer, 'wb') as f:
                f.setnchannels(1); f.setsampwidth(2); f.setframerate(16000)
                f.writeframes(audio.tobytes())
            buffer.seek(0)
            
            if self.engine and self.engine.voice:
                self.engine.voice.load()
                result = self.engine.voice.whisper.transcribe(buffer)
                text = result[0].strip()
                
                if text:
                    self.term(f">>> {text}")
                    self.term_input.setText(text)
                    self.process_prompt(text)
                else:
                    self.term("[NO SPEECH]")
            else:
                self.term("[VOICE: Engine not ready]")
                
        except ImportError:
            self.term("[VOICE: pip install sounddevice numpy faster-whisper]")
        except Exception as e:
            self.term(f"[ERROR: {e}]")
            logger.exception("Voice")
            logger.exception("Voice")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F12:
            self.toggle_dev_console()
        elif event.key() == Qt.Key.Key_Space and self.mic_btn.isChecked():
            self.process_voice()
            event.accept()
        else:
            super().keyPressEvent(event)

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