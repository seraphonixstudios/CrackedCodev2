#!/usr/bin/env python3
"""
CrackedCode Syntax Highlighter - Code highlighting for the editor
Supports Python, JavaScript, JSON, HTML, CSS with extensible architecture.
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple, Optional

from PyQt6.QtCore import Qt, QRegularExpression
from PyQt6.QtGui import (
    QSyntaxHighlighter, QTextCharFormat, QColor, QFont
)

# Atlantean theme colors
ATLAN_GREEN = QColor("#00FF41")
ATLAN_CYAN = QColor("#00FFFF")
ATLAN_GOLD = QColor("#FFD700")
ATLAN_PURPLE = QColor("#9D00FF")
ATLAN_ORANGE = QColor("#FF8C00")
ATLAN_RED = QColor("#FF3333")
ATLAN_BLUE = QColor("#0080FF")
ATLAN_GRAY = QColor("#888888")
ATLAN_COMMENT = QColor("#555555")


class SyntaxRule:
    """A single syntax highlighting rule."""
    def __init__(self, pattern: str, fmt: QTextCharFormat):
        self.pattern = QRegularExpression(pattern)
        self.format = fmt


class PythonHighlighter(QSyntaxHighlighter):
    """Python syntax highlighter."""

    KEYWORDS = [
        "and", "as", "assert", "async", "await", "break", "class", "continue",
        "def", "del", "elif", "else", "except", "False", "finally", "for",
        "from", "global", "if", "import", "in", "is", "lambda", "None",
        "nonlocal", "not", "or", "pass", "raise", "return", "True", "try",
        "while", "with", "yield", "self", "cls",
    ]

    BUILTINS = [
        "abs", "all", "any", "bin", "bool", "bytearray", "bytes", "callable",
        "chr", "classmethod", "compile", "complex", "delattr", "dict", "dir",
        "divmod", "enumerate", "eval", "exec", "filter", "float", "format",
        "frozenset", "getattr", "globals", "hasattr", "hash", "help", "hex",
        "id", "input", "int", "isinstance", "issubclass", "iter", "len",
        "list", "locals", "map", "max", "memoryview", "min", "next", "object",
        "oct", "open", "ord", "pow", "print", "property", "range", "repr",
        "reversed", "round", "set", "setattr", "slice", "sorted", "staticmethod",
        "str", "sum", "super", "tuple", "type", "vars", "zip", "__import__",
    ]

    def __init__(self, document):
        super().__init__(document)
        self._init_formats()
        self._init_rules()

    def _init_formats(self):
        """Initialize text formats for different token types."""
        # Keywords
        self.keyword_fmt = QTextCharFormat()
        self.keyword_fmt.setForeground(ATLAN_PURPLE)
        self.keyword_fmt.setFontWeight(QFont.Weight.Bold)

        # Builtins
        self.builtin_fmt = QTextCharFormat()
        self.builtin_fmt.setForeground(ATLAN_CYAN)

        # Strings
        self.string_fmt = QTextCharFormat()
        self.string_fmt.setForeground(ATLAN_GREEN)

        # Comments
        self.comment_fmt = QTextCharFormat()
        self.comment_fmt.setForeground(ATLAN_COMMENT)
        self.comment_fmt.setFontItalic(True)

        # Numbers
        self.number_fmt = QTextCharFormat()
        self.number_fmt.setForeground(ATLAN_GOLD)

        # Functions/Classes
        self.def_fmt = QTextCharFormat()
        self.def_fmt.setForeground(ATLAN_ORANGE)
        self.def_fmt.setFontWeight(QFont.Weight.Bold)

        # Decorators
        self.decorator_fmt = QTextCharFormat()
        self.decorator_fmt.setForeground(ATLAN_BLUE)

        # Self/Cls
        self.self_fmt = QTextCharFormat()
        self.self_fmt.setForeground(ATLAN_RED)
        self.self_fmt.setFontItalic(True)

    def _init_rules(self):
        """Initialize highlighting rules."""
        self.rules: List[SyntaxRule] = []

        # Keywords
        keyword_pattern = r'\b(' + '|'.join(self.KEYWORDS) + r')\b'
        self.rules.append(SyntaxRule(keyword_pattern, self.keyword_fmt))

        # Builtins
        builtin_pattern = r'\b(' + '|'.join(self.BUILTINS) + r')\b'
        self.rules.append(SyntaxRule(builtin_pattern, self.builtin_fmt))

        # Decorators
        self.rules.append(SyntaxRule(r'@[\w\.]+', self.decorator_fmt))

        # Strings (single quoted)
        self.rules.append(SyntaxRule(r"'[^'\\]*(\\.[^'\\]*)*'", self.string_fmt))
        # Strings (double quoted)
        self.rules.append(SyntaxRule(r'"[^"\\]*(\\.[^"\\]*)*"', self.string_fmt))
        # f-strings
        self.rules.append(SyntaxRule(r'f"[^"\\]*(\\.[^"\\]*)*"', self.string_fmt))
        self.rules.append(SyntaxRule(r"f'[^'\\]*(\\.[^'\\]*)*'", self.string_fmt))

        # Numbers
        self.rules.append(SyntaxRule(r'\b[0-9]+\b', self.number_fmt))
        self.rules.append(SyntaxRule(r'\b0[xX][0-9a-fA-F]+\b', self.number_fmt))
        self.rules.append(SyntaxRule(r'\b[0-9]+\.[0-9]*([eE][+-]?[0-9]+)?\b', self.number_fmt))

        # Function definitions
        self.rules.append(SyntaxRule(r'\bdef\s+(\w+)', self.def_fmt))
        self.rules.append(SyntaxRule(r'\bclass\s+(\w+)', self.def_fmt))

        # Self/cls
        self.rules.append(SyntaxRule(r'\bself\b', self.self_fmt))
        self.rules.append(SyntaxRule(r'\bcls\b', self.self_fmt))

        # Comments
        self.rules.append(SyntaxRule(r'#[^\n]*', self.comment_fmt))

    def highlightBlock(self, text: str):
        """Highlight a block of text."""
        for rule in self.rules:
            match_iter = rule.pattern.globalMatch(text)
            while match_iter.hasNext():
                match = match_iter.next()
                # Check if this is a capture group rule (def/class)
                if match.lastCapturedIndex() > 0:
                    start = match.capturedStart(1)
                    length = match.capturedLength(1)
                else:
                    start = match.capturedStart()
                    length = match.capturedLength()
                self.setFormat(start, length, rule.format)

        # Multi-line strings
        self._match_multiline(text, '"""', self.string_fmt)
        self._match_multiline(text, "'''", self.string_fmt)

    def _match_multiline(self, text: str, delimiter: str, fmt: QTextCharFormat):
        """Match multi-line strings."""
        state = self.previousBlockState()
        start = 0
        add = 0

        if state == 1:
            start = text.find(delimiter)
            if start >= 0:
                add = start + len(delimiter)
                self.setFormat(0, start + len(delimiter), fmt)
                self.setCurrentBlockState(0)
            else:
                self.setFormat(0, len(text), fmt)
                self.setCurrentBlockState(1)
                return

        while True:
            start = text.find(delimiter, start)
            if start >= 0:
                end = text.find(delimiter, start + len(delimiter))
                if end >= 0:
                    self.setFormat(start, end - start + len(delimiter), fmt)
                    start = end + len(delimiter)
                else:
                    self.setFormat(start, len(text) - start, fmt)
                    self.setCurrentBlockState(1)
                    return
            else:
                return


class JSONHighlighter(QSyntaxHighlighter):
    """JSON syntax highlighter."""

    def __init__(self, document):
        super().__init__(document)
        self._init_formats()
        self._init_rules()

    def _init_formats(self):
        self.key_fmt = QTextCharFormat()
        self.key_fmt.setForeground(ATLAN_CYAN)

        self.string_fmt = QTextCharFormat()
        self.string_fmt.setForeground(ATLAN_GREEN)

        self.number_fmt = QTextCharFormat()
        self.number_fmt.setForeground(ATLAN_GOLD)

        self.bool_fmt = QTextCharFormat()
        self.bool_fmt.setForeground(ATLAN_PURPLE)

        self.null_fmt = QTextCharFormat()
        self.null_fmt.setForeground(ATLAN_RED)

    def _init_rules(self):
        self.rules: List[SyntaxRule] = []
        # JSON keys (strings before colon)
        self.rules.append(SyntaxRule(r'"[^"]*"\s*:', self.key_fmt))
        # Strings
        self.rules.append(SyntaxRule(r'"[^"]*"', self.string_fmt))
        # Numbers
        self.rules.append(SyntaxRule(r'-?\d+\.?\d*([eE][+-]?\d+)?', self.number_fmt))
        # Booleans
        self.rules.append(SyntaxRule(r'\b(true|false)\b', self.bool_fmt))
        # Null
        self.rules.append(SyntaxRule(r'\bnull\b', self.null_fmt))

    def highlightBlock(self, text: str):
        for rule in self.rules:
            match_iter = rule.pattern.globalMatch(text)
            while match_iter.hasNext():
                match = match_iter.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), rule.format)


class PlainHighlighter(QSyntaxHighlighter):
    """Plain text (no highlighting)."""
    def __init__(self, document):
        super().__init__(document)

    def highlightBlock(self, text: str):
        pass


# Mapping of file extensions to highlighters
HIGHLIGHTERS = {
    ".py": PythonHighlighter,
    ".json": JSONHighlighter,
}


def get_highlighter(ext: str, document) -> QSyntaxHighlighter:
    """Get the appropriate highlighter for a file extension."""
    highlighter_class = HIGHLIGHTERS.get(ext.lower(), PlainHighlighter)
    return highlighter_class(document)


__all__ = [
    "PythonHighlighter",
    "JSONHighlighter",
    "PlainHighlighter",
    "get_highlighter",
    "HIGHLIGHTERS",
]
