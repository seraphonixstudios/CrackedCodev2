import sys
import os
import json
import logging
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
    QGuiApplication, QDesktopServices
)
from PyQt6.QtNetwork import QLocalSocket, QLocalServer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s'
)
logger = logging.getLogger("CrackedCodeGUI")


class CrackedCodeGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CrackedCode v2.1.9 - Atlantean Neural System")
        self.setMinimumSize(1200, 800)
        self.settings = QSettings("SeraphonixStudios", "CrackedCode")
        self.load_config()
        self.setup_ui()
        self.restore_state()
        logger.info("CrackedCode GUI started")

    def load_config(self):
        config_path = Path("config.json")
        if config_path.exists():
            with open(config_path) as f:
                self.config = json.load(f)
        else:
            self.config = {"model": "qwen3:8b-gpu", "project_root": "."}

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.create_menu_bar()
        self.create_toolbar()
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        left_panel = self.create_left_panel()
        splitter.addWidget(left_panel)
        
        self.right_panel = self.create_right_panel()
        splitter.addWidget(self.right_panel)
        
        splitter.setSizes([300, 900])
        main_layout.addWidget(splitter)
        
        self.create_status_bar()

    def create_menu_bar(self):
        menubar = self.menuBar()
        
        file_menu = menubar.addMenu("&File")
        file_menu.addAction("&New Project", self.new_project)
        file_menu.addAction("&Open Project", self.open_project)
        file_menu.addSeparator()
        file_menu.addAction("&Settings", self.show_settings)
        file_menu.addSeparator()
        file_menu.addAction("E&xit", self.close)
        
        edit_menu = menubar.addMenu("&Edit")
        edit_menu.addAction("&Undo")
        edit_menu.addAction("&Redo")
        edit_menu.addSeparator()
        edit_menu.addAction("Cu&t")
        edit_menu.addAction("&Copy")
        edit_menu.addAction("&Paste")
        
        view_menu = menubar.addMenu("&View")
        view_menu.addAction("&Toggle Left Panel", self.toggle_left_panel)
        view_menu.addAction("&Toggle Terminal", self.toggle_terminal)
        view_menu.addSeparator()
        view_menu.addAction("&Full Screen", self.toggle_fullscreen)
        
        run_menu = menubar.addMenu("&Run")
        run_menu.addAction("&Execute Code", self.execute_code)
        run_menu.addAction("&Debug", self.debug_code)
        run_menu.addSeparator()
        run_menu.addAction("&Plan Mode", lambda: self.set_mode("plan"))
        run_menu.addAction("&Build Mode", lambda: self.set_mode("build"))
        
        help_menu = menubar.addMenu("&Help")
        help_menu.addAction("&Documentation", self.show_docs)
        help_menu.addAction("&About", self.show_about)

    def create_toolbar(self):
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        
        self.plan_btn = QPushButton("Plan")
        self.plan_btn.setCheckable(True)
        self.plan_btn.setChecked(True)
        self.plan_btn.clicked.connect(lambda: self.set_mode("plan"))
        toolbar.addWidget(self.plan_btn)
        
        self.build_btn = QPushButton("Build")
        self.build_btn.setCheckable(True)
        self.build_btn.setChecked(True)
        self.build_btn.clicked.connect(lambda: self.set_mode("build"))
        toolbar.addWidget(self.build_btn)
        
        toolbar.addSeparator()
        
        exec_btn = QPushButton("Execute")
        exec_btn.clicked.connect(self.execute_code)
        toolbar.addWidget(exec_btn)
        
        toolbar.addSeparator()
        
        model_label = QLabel("Model:")
        toolbar.addWidget(model_label)
        
        self.model_combo = QComboBox()
        self.model_combo.addItems(["qwen3:8b-gpu", "dolphin-llama3:8b-gpu", "llava:13b-gpu"])
        self.model_combo.setCurrentText(self.config.get("model", "qwen3:8b-gpu"))
        toolbar.addWidget(self.model_combo)

    def create_left_panel(self):
        panel = QFrame()
        panel.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(panel)
        
        tabs = QTabWidget()
        
        files_tab = QWidget()
        files_layout = QVBoxLayout(files_tab)
        
        self.files_list = QListWidget()
        self.files_list.setHeaderLabel("Project Files")
        files_layout.addWidget(self.files_list)
        
        tabs.addTab(files_tab, "Files")
        
        agents_tab = QWidget()
        agents_layout = QVBoxLayout(agents_tab)
        
        self.agents_list = QListWidget()
        self.agents_list.addItems([
            "Supervisor - Orchestrates workflow",
            "Architect - Designs system structure", 
            "Coder - Writes and modifies code",
            "Executor - Runs commands safely",
            "Reviewer - Analyzes and suggests fixes"
        ])
        agents_layout.addWidget(self.agents_list)
        
        tabs.addTab(agents_tab, "Agents")
        
        layout.addWidget(tabs)
        
        return panel

    def create_right_panel(self):
        panel = QFrame()
        panel.setFrameShape(QFrame.Shape.NoFrame)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        self.code_editor = QTextEdit()
        self.code_editor.setFont(QFont("Consolas", 11))
        self.code_editor.setPlaceholderText("# Enter your code here...\n# Press Ctrl+Return to execute")
        layout.addWidget(self.code_editor, 3)
        
        terminal_group = QGroupBox("Terminal Output")
        terminal_layout = QVBoxLayout(terminal_group)
        
        self.terminal = QTextEdit()
        self.terminal.setFont(QFont("Consolas", 10))
        self.terminal.setReadOnly(True)
        self.terminal.setStyleSheet("background-color: #1e1e1e; color: #00ff00;")
        terminal_layout.addWidget(self.terminal)
        
        terminal_input_layout = QHBoxLayout()
        terminal_input_layout.addWidget(QLabel(">"))
        
        self.terminal_input = QLineEdit()
        self.terminal_input.setPlaceholderText("Enter command...")
        self.terminal_input.returnPressed.connect(self.run_terminal_command)
        terminal_input_layout.addWidget(self.terminal_input)
        
        terminal_layout.addLayout(terminal_input_layout)
        
        layout.addWidget(terminal_group, 2)
        
        return panel

    def create_status_bar(self):
        status = QStatusBar()
        self.setStatusBar(status)
        
        self.status_label = QLabel("Ready")
        status.addWidget(self.status_label)
        
        status.addPermanentWidget(QLabel("Model: " + self.config.get("model", "qwen3:8b-gpu")))
        status.addPermanentWidget(QLabel("Plan: ON | Build: ON"))

    def toggle_left_panel(self):
        pass

    def toggle_terminal(self):
        pass

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def new_project(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Project Folder")
        if folder:
            self.config["project_root"] = folder
            self.append_terminal(f"New project selected: {folder}")

    def open_project(self):
        folder = QFileDialog.getExistingDirectory(self, "Open Project Folder")
        if folder:
            self.config["project_root"] = folder
            self.append_terminal(f"Opened project: {folder}")

    def show_settings(self):
        self.append_terminal("Settings dialog opened")

    def show_docs(self):
        QDesktopServices.openUrl(QUrl("https://github.com/seraphonixstudios/CrackedCodev2"))

    def show_about(self):
        QMessageBox.about(self, "About CrackedCode",
            "CrackedCode v2.1.9\n\n"
            "Atlantean Neural System\n"
            "Local AI Coding Assistant\n\n"
            "Built with PyQt6\n"
            "MIT License"
        )

    def set_mode(self, mode):
        if mode == "plan":
            self.status_label.setText(f"Plan mode: {'ON' if self.plan_btn.isChecked() else 'OFF'}")
        elif mode == "build":
            self.status_label.setText(f"Build mode: {'ON' if self.build_btn.isChecked() else 'OFF'}")
        self.append_terminal(f"Mode changed: {mode}")

    def execute_code(self):
        code = self.code_editor.toPlainText()
        if code.strip():
            self.append_terminal(f"Executing code...\n{code}")
            self.status_label.setText("Executing...")

    def debug_code(self):
        code = self.code_editor.toPlainText()
        if code.strip():
            self.append_terminal(f"Debugging code...\n{code}")

    def run_terminal_command(self):
        cmd = self.terminal_input.text()
        if cmd:
            self.append_terminal(f"$ {cmd}")
            self.terminal_input.clear()

    def append_terminal(self, text):
        self.terminal.append(text)
        cursor = self.terminal.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.terminal.setTextCursor(cursor)

    def restore_state(self):
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        state = self.settings.value("windowState")
        if state:
            self.restoreState(state)

    def closeEvent(self, event):
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        logger.info("CrackedCode GUI closing")
        event.accept()


def check_single_instance():
    socket = QLocalSocket()
    socket.connectToServer("CrackedCode_SingleInstance")
    if socket.state() == QLocalSocket.LocalSocketState.ConnectedState:
        logger.warning("Another instance is already running")
        return False
    return True


def main():
    if not check_single_instance():
        QMessageBox.warning(None, "CrackedCode", "Another instance is already running!")
        return
    
    app = QApplication(sys.argv)
    app.setApplicationName("CrackedCode")
    app.setOrganizationName("SeraphonixStudios")
    app.setStyle("Fusion")
    
    dark_palette = app.palette()
    dark_palette.setColor(dark_palette.ColorRole.Window, QColor(53, 53, 53))
    dark_palette.setColor(dark_palette.ColorRole.WindowText, Qt.GlobalColor.white)
    dark_palette.setColor(dark_palette.ColorRole.Base, QColor(35, 35, 35))
    dark_palette.setColor(dark_palette.ColorRole.AlternateBase, QColor(53, 53, 53))
    dark_palette.setColor(dark_palette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
    dark_palette.setColor(dark_palette.ColorRole.ToolTipText, Qt.GlobalColor.white)
    dark_palette.setColor(dark_palette.ColorRole.Text, Qt.GlobalColor.white)
    dark_palette.setColor(dark_palette.ColorRole.Button, QColor(53, 53, 53))
    dark_palette.setColor(dark_palette.ColorRole.ButtonText, Qt.GlobalColor.white)
    dark_palette.setColor(dark_palette.ColorRole.BrightText, Qt.GlobalColor.red)
    dark_palette.setColor(dark_palette.ColorRole.Link, QColor(42, 130, 218))
    dark_palette.setColor(dark_palette.ColorRole.Highlight, QColor(42, 130, 218))
    dark_palette.setColor(dark_palette.ColorRole.HighlightedText, Qt.GlobalColor.black)
    app.setPalette(dark_palette)
    
    window = CrackedCodeGUI()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()