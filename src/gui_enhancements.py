#!/usr/bin/env python3
"""
CrackedCode GUI Enhancements v2.6.0
UX Improvements: Toast notifications, Command Palette, Welcome Screen,
Enhanced Status Bar, Animated transitions, Quick Actions
"""

from __future__ import annotations

import time
from typing import Optional, List, Dict, Callable, Any
from dataclasses import dataclass
from enum import Enum

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QDialog, QGraphicsOpacityEffect,
    QApplication, QMainWindow, QStatusBar, QPushButton, QFrame,
    QScrollArea, QGridLayout, QSizePolicy, QSpacerItem
)
from PyQt6.QtCore import (
    Qt, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve,
    QRect, QSize, QPoint
)
from PyQt6.QtGui import QFont, QColor, QPainter, QBrush, QPen, QKeySequence


class ToastType(Enum):
    INFO = "#00FF41"
    SUCCESS = "#00FF41"
    WARNING = "#FFD700"
    ERROR = "#FF3333"
    NEUTRAL = "#00FFFF"


@dataclass
class ToastMessage:
    text: str
    toast_type: ToastType = ToastType.INFO
    duration: int = 3000  # ms


class ToastNotification(QWidget):
    """Non-intrusive toast notification that auto-dismisses with fade animation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity_effect)
        
        self._anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._anim.setDuration(300)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fade_out)
        
        self._init_ui()
        self.hide()
    
    def _init_ui(self):
        from src.gui import ATLAN_DARK, ATLAN_GREEN
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(16, 10, 16, 10)
        self.layout.setSpacing(8)
        
        self.icon_label = QLabel(self)
        self.icon_label.setFixedSize(20, 20)
        self.layout.addWidget(self.icon_label)
        
        self.text_label = QLabel(self)
        self.text_label.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
        self.text_label.setWordWrap(True)
        self.layout.addWidget(self.text_label)
        
        self.setStyleSheet(f"""
            ToastNotification {{
                background-color: #0f0f0f;
                border: 1px solid {ATLAN_GREEN};
                border-radius: 8px;
            }}
            QLabel {{ color: {ATLAN_GREEN}; }}
        """)
        self.setMinimumWidth(280)
        self.setMaximumWidth(480)
    
    def show_message(self, text: str, toast_type: ToastType = ToastType.INFO, duration: int = 3000):
        """Show a toast message."""
        icons = {
            ToastType.INFO: "ℹ",
            ToastType.SUCCESS: "✓",
            ToastType.WARNING: "⚠",
            ToastType.ERROR: "✗",
            ToastType.NEUTRAL: "→",
        }
        self.icon_label.setText(icons.get(toast_type, "→"))
        self.text_label.setText(text)
        
        color = toast_type.value
        self.setStyleSheet(f"""
            ToastNotification {{
                background-color: #0f0f0f;
                border: 1px solid {color};
                border-radius: 8px;
            }}
            QLabel {{ color: {color}; }}
        """)
        
        # Position at bottom-right of parent
        if self.parent():
            parent_rect = self.parent().rect()
            self.move(
                parent_rect.width() - self.width() - 20,
                parent_rect.height() - self.height() - 60
            )
        
        self._opacity_effect.setOpacity(0.0)
        self.show()
        self.raise_()
        
        # Fade in
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()
        
        # Auto dismiss
        self._timer.stop()
        self._timer.setInterval(duration)
        self._timer.start()
    
    def _fade_out(self):
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.finished.connect(self.hide)
        self._anim.start()


class QuickActionItem:
    """Represents a quick action in the command palette."""
    def __init__(self, name: str, shortcut: str, callback: Callable, category: str = "General"):
        self.name = name
        self.shortcut = shortcut
        self.callback = callback
        self.category = category


class QuickActionsDialog(QDialog):
    """Command palette (Ctrl+Shift+P) for quick access to all actions."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumWidth(600)
        self.setMaximumWidth(700)
        
        self.actions_list: List[QuickActionItem] = []
        self._init_ui()
    
    def _init_ui(self):
        from src.gui import ATLAN_DARK, ATLAN_GREEN, ATLAN_MEDIUM, ATLAN_GOLD, ATLAN_BORDER
        
        container = QFrame(self)
        container.setStyleSheet(f"""
            QFrame {{
                background-color: {ATLAN_DARK};
                border: 2px solid {ATLAN_GREEN};
                border-radius: 12px;
            }}
            QLineEdit {{
                background-color: #050505;
                color: {ATLAN_GREEN};
                border: 1px solid {ATLAN_BORDER};
                border-radius: 8px;
                padding: 12px;
                font-family: Consolas;
                font-size: 13px;
            }}
            QLineEdit:focus {{ border: 1px solid {ATLAN_GREEN}; }}
            QListWidget {{
                background-color: transparent;
                border: none;
                outline: none;
                font-family: Consolas;
            }}
            QListWidget::item {{
                color: {ATLAN_GREEN};
                padding: 10px 12px;
                border-radius: 6px;
                margin: 2px 4px;
            }}
            QListWidget::item:selected {{
                background-color: {ATLAN_GREEN};
                color: {ATLAN_DARK};
            }}
            QListWidget::item:hover {{
                background-color: {ATLAN_MEDIUM};
            }}
            QLabel {{
                color: {ATLAN_GOLD};
                font-family: Consolas;
                font-size: 11px;
                padding: 4px 12px;
            }}
        """)
        
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        
        # Search input
        self.search_input = QLineEdit(container)
        self.search_input.setPlaceholderText("Type a command... (Esc to close)")
        self.search_input.textChanged.connect(self._filter_actions)
        layout.addWidget(self.search_input)
        
        # Results list
        self.results_list = QListWidget(container)
        self.results_list.itemActivated.connect(self._on_item_activated)
        self.results_list.itemClicked.connect(self._on_item_activated)
        layout.addWidget(self.results_list)
        
        # Shortcut hint
        hint = QLabel("↑↓ Navigate  |  Enter Execute  |  Esc Close", container)
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)
        
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(container)
        main_layout.setContentsMargins(0, 0, 0, 0)
    
    def register_actions(self, actions: List[QuickActionItem]):
        self.actions_list = actions
        self._filter_actions("")
    
    def _filter_actions(self, text: str):
        self.results_list.clear()
        text_lower = text.lower()
        
        # Group by category
        categories: Dict[str, List[QuickActionItem]] = {}
        for action in self.actions_list:
            if text_lower in action.name.lower() or text_lower in action.category.lower():
                categories.setdefault(action.category, []).append(action)
        
        for category, items in sorted(categories.items()):
            # Category header
            header = QListWidgetItem(f"  {category.upper()}")
            header.setFlags(Qt.ItemFlag.NoItemFlags)
            header.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
            from src.gui import ATLAN_GOLD
            header.setForeground(QBrush(QColor(ATLAN_GOLD)))
            self.results_list.addItem(header)
            
            for item in items:
                display = f"  {item.name:<30}  {item.shortcut}"
                list_item = QListWidgetItem(display)
                list_item.setData(Qt.ItemDataRole.UserRole, item)
                self.results_list.addItem(list_item)
        
        if self.results_list.count() > 0:
            # Skip header
            for i in range(self.results_list.count()):
                if self.results_list.item(i).flags() & Qt.ItemFlag.ItemIsSelectable:
                    self.results_list.setCurrentRow(i)
                    break
    
    def _on_item_activated(self, item: QListWidgetItem):
        action = item.data(Qt.ItemDataRole.UserRole)
        if action and isinstance(action, QuickActionItem):
            self.hide()
            action.callback()
    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            return
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            current = self.results_list.currentItem()
            if current:
                self._on_item_activated(current)
            return
        elif event.key() == Qt.Key.Key_Down:
            self.results_list.setCurrentRow(
                min(self.results_list.currentRow() + 1, self.results_list.count() - 1)
            )
            return
        elif event.key() == Qt.Key.Key_Up:
            self.results_list.setCurrentRow(max(self.results_list.currentRow() - 1, 0))
            return
        super().keyPressEvent(event)
    
    def showEvent(self, event):
        super().showEvent(event)
        self.search_input.clear()
        self.search_input.setFocus()
        # Center on parent
        if self.parent():
            geo = self.geometry()
            parent_geo = self.parent().geometry()
            geo.moveCenter(parent_geo.center())
            self.setGeometry(geo)


class WelcomeWidget(QWidget):
    """Welcome screen shown on first launch with tips and shortcuts."""

    dismissed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
    
    def _init_ui(self):
        from src.gui import ATLAN_DARK, ATLAN_GREEN, ATLAN_GOLD, ATLAN_CYAN, ATLAN_PURPLE, ATLAN_BORDER
        
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {ATLAN_DARK};
                color: {ATLAN_GREEN};
                font-family: Consolas;
            }}
            QPushButton {{
                background-color: {ATLAN_GREEN};
                color: {ATLAN_DARK};
                border: none;
                padding: 12px 24px;
                border-radius: 8px;
                font-weight: bold;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {ATLAN_CYAN};
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)
        
        # Title
        title = QLabel("⚡ CRACKEDCODE v2.6.0", self)
        title.setFont(QFont("Consolas", 24, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color: {ATLAN_GREEN};")
        layout.addWidget(title)
        
        subtitle = QLabel("Autonomous AI Coding Agent", self)
        subtitle.setFont(QFont("Consolas", 14))
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet(f"color: {ATLAN_GOLD};")
        layout.addWidget(subtitle)
        
        # Features grid
        features = QGridLayout()
        features.setSpacing(16)
        
        feature_data = [
            ("🎯", "PLAN MODE", "Design before you build", ATLAN_CYAN),
            ("🏗", "BUILD MODE", "Generate code instantly", ATLAN_GREEN),
            ("🎤", "VOICE CONTROL", "Speak to code", ATLAN_PURPLE),
            ("🤖", "AUTO PRODUCE", "Full apps from specs", ATLAN_GOLD),
        ]
        
        for i, (icon, title, desc, color) in enumerate(feature_data):
            card = self._create_feature_card(icon, title, desc, color)
            features.addWidget(card, i // 2, i % 2)
        
        layout.addLayout(features)
        
        # Shortcuts
        shortcuts_label = QLabel("QUICK SHORTCUTS", self)
        shortcuts_label.setFont(QFont("Consolas", 12, QFont.Weight.Bold))
        shortcuts_label.setStyleSheet(f"color: {ATLAN_GOLD}; margin-top: 10px;")
        layout.addWidget(shortcuts_label)
        
        shortcuts_text = QLabel("""
Ctrl+P          Toggle Plan Mode      Ctrl+B          Toggle Build Mode
Ctrl+Enter      Execute Code          Ctrl+Shift+P    Command Palette
Ctrl+N          New File              Ctrl+O          Open Project
Ctrl+S          Save File             Ctrl+Shift+V    Voice Input
Ctrl+A          Autonomous Produce    F1              Help
        """)
        shortcuts_text.setFont(QFont("Consolas", 10))
        shortcuts_text.setStyleSheet(f"color: {ATLAN_GREEN}; background-color: #0a0a0a; padding: 12px; border-radius: 6px;")
        shortcuts_text.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(shortcuts_text)
        
        layout.addStretch()
        
        # Dismiss button
        dismiss_btn = QPushButton("GET STARTED →", self)
        dismiss_btn.clicked.connect(self._dismiss)
        layout.addWidget(dismiss_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Don't show again checkbox (simplified)
        self.setMinimumSize(700, 500)
    
    def _create_feature_card(self, icon: str, title: str, desc: str, color: str) -> QFrame:
        from src.gui import ATLAN_MEDIUM
        card = QFrame(self)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {ATLAN_MEDIUM};
                border: 1px solid {color};
                border-radius: 8px;
                padding: 12px;
            }}
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        
        icon_label = QLabel(icon, card)
        icon_label.setFont(QFont("Consolas", 24))
        layout.addWidget(icon_label)
        
        title_label = QLabel(title, card)
        title_label.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
        title_label.setStyleSheet(f"color: {color};")
        layout.addWidget(title_label)
        
        desc_label = QLabel(desc, card)
        desc_label.setFont(QFont("Consolas", 9))
        desc_label.setStyleSheet("color: #888;")
        layout.addWidget(desc_label)
        
        return card
    
    def _dismiss(self):
        self.dismissed.emit()
        self.hide()


class EnhancedStatusBar(QStatusBar):
    """Status bar with multiple info panels and activity indicator."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._activity_timer = QTimer(self)
        self._activity_timer.timeout.connect(self._pulse_activity)
        self._activity_counter = 0
    
    def _init_ui(self):
        from src.gui import ATLAN_GREEN, ATLAN_DARK
        
        # Left: Status message
        self.status_label = QLabel("READY", self)
        self.status_label.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
        self.addWidget(self.status_label)
        
        self.addStretch()
        
        # Center: Info panels
        self.model_label = QLabel("Model: —", self)
        self.model_label.setFont(QFont("Consolas", 9))
        self.addWidget(self.model_label)
        
        self.mode_label = QLabel("Mode: PLAN+BUILD", self)
        self.mode_label.setFont(QFont("Consolas", 9))
        self.addWidget(self.mode_label)
        
        self.files_label = QLabel("Files: 0", self)
        self.files_label.setFont(QFont("Consolas", 9))
        self.addWidget(self.files_label)
        
        self.voice_label = QLabel("🎤", self)
        self.voice_label.setFont(QFont("Consolas", 9))
        self.voice_label.setToolTip("Voice status")
        self.addWidget(self.voice_label)
        
        self.addStretch()
        
        # Right: Activity indicator
        self.activity_label = QLabel("●", self)
        self.activity_label.setFont(QFont("Consolas", 10))
        self.activity_label.setStyleSheet(f"color: {ATLAN_GREEN};")
        self.addWidget(self.activity_label)
        
        self.cursor_label = QLabel("Ln 1, Col 1", self)
        self.cursor_label.setFont(QFont("Consolas", 9))
        self.addWidget(self.cursor_label)
    
    def set_status(self, text: str, color: str = None):
        self.status_label.setText(text.upper())
        if color:
            self.status_label.setStyleSheet(f"color: {color}; font-weight: bold;")
        else:
            from src.gui import ATLAN_GREEN
            self.status_label.setStyleSheet(f"color: {ATLAN_GREEN}; font-weight: bold;")
    
    def set_model(self, model: str):
        self.model_label.setText(f"Model: {model}")
    
    def set_mode(self, mode: str):
        self.mode_label.setText(f"Mode: {mode}")
    
    def set_files_count(self, count: int):
        self.files_label.setText(f"Files: {count}")
    
    def set_voice_status(self, active: bool):
        color = "#00FF41" if active else "#555"
        self.voice_label.setStyleSheet(f"color: {color};")
    
    def set_cursor_position(self, line: int, col: int):
        self.cursor_label.setText(f"Ln {line}, Col {col}")
    
    def start_activity(self):
        self._activity_counter = 0
        self._activity_timer.start(500)
    
    def stop_activity(self):
        self._activity_timer.stop()
        from src.gui import ATLAN_GREEN
        self.activity_label.setStyleSheet(f"color: {ATLAN_GREEN};")
    
    def _pulse_activity(self):
        colors = ["#00FF41", "#00CC33", "#009926", "#00CC33"]
        self.activity_label.setStyleSheet(f"color: {colors[self._activity_counter % len(colors)]};")
        self._activity_counter += 1


class FloatingActionButton(QPushButton):
    """Floating action button with pulse animation."""
    
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setFixedSize(48, 48)
        self.setFont(QFont("Consolas", 16, QFont.Weight.Bold))
        self._setup_style()
        
        self._pulse_anim = QPropertyAnimation(self, b"geometry")
        self._pulse_anim.setDuration(2000)
        self._pulse_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
    
    def _setup_style(self):
        from src.gui import ATLAN_GREEN, ATLAN_DARK
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {ATLAN_GREEN};
                color: {ATLAN_DARK};
                border: none;
                border-radius: 24px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #00CC33;
            }}
            QPushButton:pressed {{
                background-color: #009926;
            }}
        """)
    
    def start_pulse(self):
        base = self.geometry()
        self._pulse_anim.setStartValue(base)
        grown = base.adjusted(-2, -2, 2, 2)
        self._pulse_anim.setEndValue(grown)
        self._pulse_anim.setDirection(QPropertyAnimation.Direction.Forward)
        self._pulse_anim.finished.connect(lambda: self._pulse_anim.setDirection(
            QPropertyAnimation.Direction.Backward if self._pulse_anim.direction() == QPropertyAnimation.Direction.Forward 
            else QPropertyAnimation.Direction.Forward
        ))
        self._pulse_anim.start()
    
    def stop_pulse(self):
        self._pulse_anim.stop()


class KeyboardShortcutHelper:
    """Helper to create shortcuts with visual hints."""
    
    SHORTCUTS: Dict[str, str] = {
        "new_file": "Ctrl+N",
        "open_project": "Ctrl+O",
        "save_file": "Ctrl+S",
        "execute_code": "Ctrl+Return",
        "toggle_plan": "Ctrl+P",
        "toggle_build": "Ctrl+B",
        "voice_input": "Ctrl+Shift+V",
        "autonomous": "Ctrl+A",
        "command_palette": "Ctrl+Shift+P",
        "help": "F1",
        "close_tab": "Ctrl+W",
        "next_tab": "Ctrl+Tab",
        "prev_tab": "Ctrl+Shift+Tab",
    }
    
    @classmethod
    def get_hint(cls, action: str) -> str:
        shortcut = cls.SHORTCUTS.get(action, "")
        return f" [{shortcut}]" if shortcut else ""
    
    @classmethod
    def apply_to_button(cls, button: QPushButton, action: str):
        shortcut = cls.SHORTCUTS.get(action, "")
        if shortcut:
            existing = button.toolTip()
            if shortcut not in existing:
                button.setToolTip(f"{existing} ({shortcut})")


# Compatibility re-exports for existing code
__all__ = [
    "ToastNotification",
    "ToastType",
    "ToastMessage",
    "QuickActionsDialog",
    "QuickActionItem",
    "WelcomeWidget",
    "EnhancedStatusBar",
    "FloatingActionButton",
    "KeyboardShortcutHelper",
]
