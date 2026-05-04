#!/usr/bin/env python3
"""
CrackedCode Settings Dialog - GUI preferences editor
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, List, Dict, Any

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QSpinBox, QCheckBox, QPushButton, QTabWidget,
    QWidget, QGroupBox, QFormLayout, QSlider, QFileDialog,
    QMessageBox, QScrollArea, QFrame, QTextEdit, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor

from src.logger_config import get_logger

logger = get_logger("SettingsDialog")

ATLAN_GREEN = "#00FF41"
ATLAN_DARK = "#0a0a0a"
ATLAN_MEDIUM = "#1a1a1a"
ATLAN_GOLD = "#FFD700"
ATLAN_CYAN = "#00FFFF"


class SettingsDialog(QDialog):
    """Comprehensive settings dialog with tabs."""

    def __init__(self, config: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.config = config
        self.original_config = json.dumps(config, indent=2)
        self.setWindowTitle("SETTINGS // CRACKEDCODE")
        self.setMinimumSize(600, 500)
        self._init_ui()
        self._load_values()

    def _init_ui(self):
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {ATLAN_DARK};
                color: {ATLAN_GREEN};
                font-family: Consolas;
            }}
            QTabWidget::pane {{
                border: 1px solid {ATLAN_GREEN};
                background-color: {ATLAN_DARK};
            }}
            QTabBar::tab {{
                background-color: {ATLAN_MEDIUM};
                color: {ATLAN_GREEN};
                padding: 8px 16px;
                border: 1px solid #333;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }}
            QTabBar::tab:selected {{
                background-color: {ATLAN_GREEN};
                color: {ATLAN_DARK};
                font-weight: bold;
            }}
            QGroupBox {{
                border: 1px solid {ATLAN_GREEN};
                margin-top: 10px;
                font-weight: bold;
                border-radius: 6px;
                padding-top: 10px;
                color: {ATLAN_GOLD};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }}
            QLabel {{
                color: {ATLAN_GREEN};
                font-family: Consolas;
            }}
            QLineEdit {{
                background-color: #050505;
                color: {ATLAN_GREEN};
                border: 1px solid #333;
                padding: 6px;
                border-radius: 4px;
            }}
            QComboBox {{
                background-color: {ATLAN_MEDIUM};
                color: {ATLAN_GREEN};
                border: 1px solid #333;
                padding: 4px;
                border-radius: 4px;
            }}
            QSpinBox {{
                background-color: {ATLAN_MEDIUM};
                color: {ATLAN_GREEN};
                border: 1px solid #333;
                padding: 4px;
                border-radius: 4px;
            }}
            QSlider::groove:horizontal {{
                height: 6px;
                background: {ATLAN_MEDIUM};
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: {ATLAN_GREEN};
                width: 14px;
                height: 14px;
                border-radius: 7px;
            }}
            QCheckBox {{
                color: {ATLAN_GREEN};
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 1px solid {ATLAN_GREEN};
                border-radius: 3px;
            }}
            QCheckBox::indicator:checked {{
                background-color: {ATLAN_GREEN};
            }}
            QPushButton {{
                background-color: {ATLAN_MEDIUM};
                color: {ATLAN_GREEN};
                border: 1px solid {ATLAN_GREEN};
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {ATLAN_GREEN};
                color: {ATLAN_DARK};
            }}
            QTextEdit {{
                background-color: #050505;
                color: {ATLAN_GREEN};
                border: 1px solid #333;
                border-radius: 4px;
                font-family: Consolas;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Tabs
        self.tabs = QTabWidget(self)
        self.tabs.addTab(self._create_general_tab(), "GENERAL")
        self.tabs.addTab(self._create_voice_tab(), "VOICE")
        self.tabs.addTab(self._create_appearance_tab(), "APPEARANCE")
        self.tabs.addTab(self._create_autonomous_tab(), "AUTONOMOUS")
        self.tabs.addTab(self._create_shortcuts_tab(), "SHORTCUTS")
        layout.addWidget(self.tabs)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.discover_btn = QPushButton("DISCOVER MODELS", self)
        self.discover_btn.setToolTip("Query Ollama for available models")
        self.discover_btn.clicked.connect(self._discover_models)
        btn_layout.addWidget(self.discover_btn)

        self.reset_btn = QPushButton("RESET", self)
        self.reset_btn.setToolTip("Reset to defaults")
        self.reset_btn.clicked.connect(self._reset)
        btn_layout.addWidget(self.reset_btn)

        self.save_btn = QPushButton("SAVE", self)
        self.save_btn.setToolTip("Save settings to config.json")
        self.save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ATLAN_GREEN};
                color: {ATLAN_DARK};
                border: none;
            }}
            QPushButton:hover {{ background-color: #00CC33; }}
        """)
        self.save_btn.clicked.connect(self._save)
        btn_layout.addWidget(self.save_btn)

        self.cancel_btn = QPushButton("CANCEL", self)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)

    def _create_general_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # AI Model group
        model_group = QGroupBox("AI MODEL", tab)
        model_layout = QFormLayout(model_group)
        model_layout.setContentsMargins(8, 16, 8, 8)

        self.model_combo = QComboBox(model_group)
        self.model_combo.setEditable(True)
        self.model_combo.addItems([
            "qwen3:8b-gpu",
            "qwen3:14b-gpu",
            "llava:13b-gpu",
            "dolphin-llama3:8b-gpu",
            "codellama:7b",
            "codellama:13b",
            "deepseek-coder:6.7b",
            "mistral:7b",
        ])
        model_layout.addRow("Primary Model:", self.model_combo)

        self.vision_combo = QComboBox(model_group)
        self.vision_combo.setEditable(True)
        self.vision_combo.addItems([
            "llava:13b-gpu",
            "llava:7b",
        ])
        model_layout.addRow("Vision Model:", self.vision_combo)

        self.secondary_combo = QComboBox(model_group)
        self.secondary_combo.setEditable(True)
        self.secondary_combo.addItems([
            "dolphin-llama3:8b-gpu",
            "qwen3:8b-gpu",
            "mistral:7b",
        ])
        model_layout.addRow("Secondary Model:", self.secondary_combo)

        self.ollama_host = QLineEdit(model_group)
        model_layout.addRow("Ollama Host:", self.ollama_host)

        layout.addWidget(model_group)

        # Behavior group
        behavior_group = QGroupBox("BEHAVIOR", tab)
        behavior_layout = QFormLayout(behavior_group)
        behavior_layout.setContentsMargins(8, 16, 8, 8)

        self.streaming_check = QCheckBox("Enable streaming responses", behavior_group)
        behavior_layout.addRow(self.streaming_check)

        self.cache_check = QCheckBox("Enable response caching", behavior_group)
        behavior_layout.addRow(self.cache_check)

        self.unified_check = QCheckBox("Unified mode (all models)", behavior_group)
        behavior_layout.addRow(self.unified_check)

        self.autonomous_check = QCheckBox("Enable autonomous production", behavior_group)
        behavior_layout.addRow(self.autonomous_check)

        self.max_ctx_spin = QSpinBox(behavior_group)
        self.max_ctx_spin.setRange(5, 50)
        self.max_ctx_spin.setSuffix(" exchanges")
        behavior_layout.addRow("Max Context:", self.max_ctx_spin)

        self.temp_spin = QSpinBox(behavior_group)
        self.temp_spin.setRange(0, 100)
        self.temp_spin.setSuffix("%")
        behavior_layout.addRow("Temperature:", self.temp_spin)

        layout.addWidget(behavior_group)
        layout.addStretch()
        return tab

    def _create_voice_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # STT group
        stt_group = QGroupBox("SPEECH-TO-TEXT", tab)
        stt_layout = QFormLayout(stt_group)
        stt_layout.setContentsMargins(8, 16, 8, 8)

        self.stt_combo = QComboBox(stt_group)
        self.stt_combo.addItems(["tiny", "base", "small", "medium", "large"])
        stt_layout.addRow("Whisper Model:", self.stt_combo)

        self.stt_lang = QLineEdit(stt_group)
        self.stt_lang.setPlaceholderText("en")
        stt_layout.addRow("Language:", self.stt_lang)

        layout.addWidget(stt_group)

        # TTS group
        tts_group = QGroupBox("TEXT-TO-SPEECH", tab)
        tts_layout = QFormLayout(tts_group)
        tts_layout.setContentsMargins(8, 16, 8, 8)

        self.tts_backend_combo = QComboBox(tts_group)
        self.tts_backend_combo.addItems(["pyttsx3", "edge-tts", "fallback"])
        tts_layout.addRow("Backend:", self.tts_backend_combo)

        self.tts_voice = QLineEdit(tts_group)
        self.tts_voice.setPlaceholderText("default")
        tts_layout.addRow("Voice:", self.tts_voice)

        self.tts_gender_combo = QComboBox(tts_group)
        self.tts_gender_combo.addItems(["female", "male"])
        tts_layout.addRow("Gender:", self.tts_gender_combo)

        self.tts_rate_slider = QSlider(Qt.Orientation.Horizontal, tts_group)
        self.tts_rate_slider.setRange(50, 300)
        tts_layout.addRow("Rate (WPM):", self.tts_rate_slider)

        self.tts_rate_label = QLabel("175", tts_group)
        tts_layout.addRow("Current Rate:", self.tts_rate_label)
        self.tts_rate_slider.valueChanged.connect(
            lambda v: self.tts_rate_label.setText(str(v))
        )

        layout.addWidget(tts_group)

        # Voice mode group
        mode_group = QGroupBox("VOICE MODE", tab)
        mode_layout = QFormLayout(mode_group)
        mode_layout.setContentsMargins(8, 16, 8, 8)

        self.voice_enabled_check = QCheckBox("Enable voice features", mode_group)
        mode_layout.addRow(self.voice_enabled_check)

        self.push_to_talk_check = QCheckBox("Push-to-talk mode", mode_group)
        mode_layout.addRow(self.push_to_talk_check)

        self.hotword_input = QLineEdit(mode_group)
        self.hotword_input.setPlaceholderText("cracked code")
        mode_layout.addRow("Hotword:", self.hotword_input)

        layout.addWidget(mode_group)
        layout.addStretch()
        return tab

    def _create_appearance_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        theme_group = QGroupBox("THEME", tab)
        theme_layout = QFormLayout(theme_group)
        theme_layout.setContentsMargins(8, 16, 8, 8)

        self.theme_combo = QComboBox(theme_group)
        self.theme_combo.addItems(["Atlantean (Green)", "Matrix (Dark)", "Ocean (Blue)"])
        theme_layout.addRow("Color Theme:", self.theme_combo)

        self.font_size_spin = QSpinBox(theme_group)
        self.font_size_spin.setRange(8, 20)
        self.font_size_spin.setSuffix(" pt")
        theme_layout.addRow("Editor Font Size:", self.font_size_spin)

        layout.addWidget(theme_group)

        editor_group = QGroupBox("EDITOR", tab)
        editor_layout = QFormLayout(editor_group)
        editor_layout.setContentsMargins(8, 16, 8, 8)

        self.auto_save_check = QCheckBox("Enable auto-save", editor_group)
        editor_layout.addRow(self.auto_save_check)

        self.auto_save_delay = QSpinBox(editor_group)
        self.auto_save_delay.setRange(500, 30000)
        self.auto_save_delay.setSingleStep(500)
        self.auto_save_delay.setSuffix(" ms")
        editor_layout.addRow("Auto-save Delay:", self.auto_save_delay)

        self.line_numbers_check = QCheckBox("Show line numbers", editor_group)
        editor_layout.addRow(self.line_numbers_check)

        layout.addWidget(editor_group)
        layout.addStretch()
        return tab

    def _create_autonomous_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        ws_group = QGroupBox("WORKSPACE", tab)
        ws_layout = QFormLayout(ws_group)
        ws_layout.setContentsMargins(8, 16, 8, 8)

        self.ws_path = QLineEdit(ws_group)
        ws_layout.addRow("Workspace Path:", self.ws_path)

        self.ws_browse = QPushButton("BROWSE", ws_group)
        self.ws_browse.clicked.connect(self._browse_workspace)
        ws_layout.addRow(self.ws_browse)

        layout.addWidget(ws_group)

        limits_group = QGroupBox("LIMITS", tab)
        limits_layout = QFormLayout(limits_group)
        limits_layout.setContentsMargins(8, 16, 8, 8)

        self.max_corr_spin = QSpinBox(limits_group)
        self.max_corr_spin.setRange(1, 10)
        limits_layout.addRow("Max Corrections:", self.max_corr_spin)

        self.debate_spin = QSpinBox(limits_group)
        self.debate_spin.setRange(1, 10)
        limits_layout.addRow("Debate Rounds:", self.debate_spin)

        layout.addWidget(limits_group)
        layout.addStretch()
        return tab

    def _create_shortcuts_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        shortcuts_text = QTextEdit(tab)
        shortcuts_text.setReadOnly(True)
        shortcuts_text.setPlainText("""
FILE OPERATIONS
  Ctrl+N          New File
  Ctrl+O          Open Project
  Ctrl+S          Save File
  Ctrl+Shift+S    Save As
  Ctrl+W          Close Tab

EDITING
  Ctrl+Z          Undo
  Ctrl+Shift+Z    Redo
  Ctrl+X          Cut
  Ctrl+C          Copy
  Ctrl+V          Paste
  Ctrl+F          Find in Terminal

EXECUTION
  Ctrl+Enter      Execute Code
  Ctrl+Shift+V    Toggle Voice
  Esc             Stop Operation

MODES
  Ctrl+P          Toggle Plan Mode
  Ctrl+B          Toggle Build Mode
  Ctrl+U          Toggle Unified Mode
  Ctrl+A          Autonomous Production

VIEW
  Ctrl+M          Toggle Matrix
  F11             Toggle Fullscreen
  F1              Help
  Ctrl+Shift+P    Command Palette
  F12             Dev Console

AGENTS
  Ctrl+Shift+A    Agent Panel
  Ctrl+Shift+T    Task Queue

NAVIGATION
  Ctrl+Tab        Next Tab
  Ctrl+Shift+Tab  Previous Tab
  Up/Down         Command History
        """)
        layout.addWidget(shortcuts_text)
        return tab

    def _load_values(self):
        """Load current config values into UI."""
        # General
        self.model_combo.setCurrentText(self.config.get("model", "qwen3:8b-gpu"))
        self.vision_combo.setCurrentText(self.config.get("vision_model", "llava:13b-gpu"))
        self.secondary_combo.setCurrentText(self.config.get("secondary_model", "dolphin-llama3:8b-gpu"))
        self.ollama_host.setText(self.config.get("ollama_host", "http://localhost:11434"))
        self.streaming_check.setChecked(self.config.get("streaming_enabled", True))
        self.cache_check.setChecked(self.config.get("cache_enabled", True))
        self.unified_check.setChecked(self.config.get("unified_mode", False))
        self.autonomous_check.setChecked(self.config.get("autonomous_enabled", True))
        self.max_ctx_spin.setValue(self.config.get("max_context", 20))
        temp = self.config.get("temperature", 0.1)
        self.temp_spin.setValue(int(temp * 100))

        # Voice
        self.stt_combo.setCurrentText(self.config.get("whisper_size", "base"))
        self.stt_lang.setText(self.config.get("stt_language", "en"))
        self.tts_backend_combo.setCurrentText(self.config.get("tts_backend", "pyttsx3"))
        self.tts_voice.setText(self.config.get("tts_voice", "default"))
        self.tts_gender_combo.setCurrentText(self.config.get("tts_gender", "female"))
        self.tts_rate_slider.setValue(self.config.get("tts_rate", 175))
        self.voice_enabled_check.setChecked(self.config.get("voice_enabled", True))
        self.push_to_talk_check.setChecked(self.config.get("push_to_talk", False))
        self.hotword_input.setText(self.config.get("hotword", "cracked code"))

        # Appearance
        self.font_size_spin.setValue(self.config.get("font_size", 11))
        self.auto_save_check.setChecked(self.config.get("auto_save", True))
        self.auto_save_delay.setValue(self.config.get("auto_save_delay_ms", 3000))
        self.line_numbers_check.setChecked(self.config.get("line_numbers", False))

        # Autonomous
        self.ws_path.setText(self.config.get("autonomous_workspace", ".autonomous"))
        self.max_corr_spin.setValue(self.config.get("autonomous_max_corrections", 3))
        self.debate_spin.setValue(self.config.get("debate_rounds", 3))

    def _discover_models(self):
        """Query Ollama for available models."""
        try:
            import subprocess
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                models = []
                for line in result.stdout.strip().split("\n")[1:]:
                    parts = line.split()
                    if parts:
                        models.append(parts[0])
                if models:
                    self.model_combo.clear()
                    self.model_combo.addItems(models)
                    self.vision_combo.clear()
                    self.vision_combo.addItems(models)
                    self.secondary_combo.clear()
                    self.secondary_combo.addItems(models)
                    QMessageBox.information(self, "Models", f"Found {len(models)} models")
                else:
                    QMessageBox.warning(self, "Models", "No models found")
            else:
                QMessageBox.warning(self, "Error", "Ollama not responding")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not discover models: {e}")

    def _browse_workspace(self):
        path = QFileDialog.getExistingDirectory(self, "Select Workspace")
        if path:
            self.ws_path.setText(path)

    def _reset(self):
        """Reset to default values."""
        reply = QMessageBox.question(
            self, "Reset",
            "Reset all settings to defaults?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.config = {
                "model": "qwen3:8b-gpu",
                "vision_model": "llava:13b-gpu",
                "secondary_model": "dolphin-llama3:8b-gpu",
                "streaming_enabled": True,
                "cache_enabled": True,
                "unified_mode": False,
                "autonomous_enabled": True,
                "voice_enabled": True,
                "auto_save": True,
                "ollama_host": "http://localhost:11434",
            }
            self._load_values()

    def _save(self):
        """Save settings to config.json."""
        # General
        self.config["model"] = self.model_combo.currentText()
        self.config["vision_model"] = self.vision_combo.currentText()
        self.config["secondary_model"] = self.secondary_combo.currentText()
        self.config["ollama_host"] = self.ollama_host.text()
        self.config["streaming_enabled"] = self.streaming_check.isChecked()
        self.config["cache_enabled"] = self.cache_check.isChecked()
        self.config["unified_mode"] = self.unified_check.isChecked()
        self.config["autonomous_enabled"] = self.autonomous_check.isChecked()
        self.config["max_context"] = self.max_ctx_spin.value()
        self.config["temperature"] = self.temp_spin.value() / 100.0

        # Voice
        self.config["whisper_size"] = self.stt_combo.currentText()
        self.config["stt_language"] = self.stt_lang.text() or "en"
        self.config["tts_backend"] = self.tts_backend_combo.currentText()
        self.config["tts_voice"] = self.tts_voice.text() or "default"
        self.config["tts_gender"] = self.tts_gender_combo.currentText()
        self.config["tts_rate"] = self.tts_rate_slider.value()
        self.config["voice_enabled"] = self.voice_enabled_check.isChecked()
        self.config["push_to_talk"] = self.push_to_talk_check.isChecked()
        self.config["hotword"] = self.hotword_input.text() or "cracked code"

        # Appearance
        self.config["font_size"] = self.font_size_spin.value()
        self.config["auto_save"] = self.auto_save_check.isChecked()
        self.config["auto_save_delay_ms"] = self.auto_save_delay.value()
        self.config["line_numbers"] = self.line_numbers_check.isChecked()

        # Autonomous
        self.config["autonomous_workspace"] = self.ws_path.text()
        self.config["autonomous_max_corrections"] = self.max_corr_spin.value()
        self.config["debate_rounds"] = self.debate_spin.value()

        try:
            with open("config.json", "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2)
            logger.info("Settings saved to config.json")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save: {e}")


__all__ = ["SettingsDialog"]
