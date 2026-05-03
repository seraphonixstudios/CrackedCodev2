"""Centralized logging configuration for CrackedCode.

Provides colored console output, rotating file handlers, and structured JSON logging.
All modules should use `get_logger(name)` instead of `logging.getLogger()` directly.
"""

import sys
import logging
import logging.handlers
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any


# ANSI color codes for terminal output
_COLORS = {
    "DEBUG": "\033[36m",      # Cyan
    "INFO": "\033[32m",       # Green
    "WARNING": "\033[33m",    # Yellow
    "ERROR": "\033[31m",      # Red
    "CRITICAL": "\033[35m",   # Magenta
    "RESET": "\033[0m",       # Reset
    "DIM": "\033[90m",        # Gray
    "BOLD": "\033[1m",        # Bold
}


class ColoredFormatter(logging.Formatter):
    """Formatter that adds ANSI color codes to log output."""

    def __init__(
        self,
        fmt: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt: str = "%H:%M:%S",
        use_colors: bool = True,
    ):
        super().__init__(fmt, datefmt)
        self.use_colors = use_colors and sys.stdout.isatty()

    def format(self, record: logging.LogRecord) -> str:
        if self.use_colors:
            color = _COLORS.get(record.levelname, _COLORS["RESET"])
            reset = _COLORS["RESET"]
            dim = _COLORS["DIM"]
            record.levelname = f"{color}{_COLORS['BOLD']}{record.levelname}{reset}"
            record.name = f"{dim}{record.name}{reset}"
        return super().format(record)


class JsonFormatter(logging.Formatter):
    """JSON structured logging formatter."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, default=str)


class CrackedCodeLogger:
    """Centralized logging manager for CrackedCode."""

    _instance: Optional["CrackedCodeLogger"] = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        log_level: str = "INFO",
        log_dir: str = "logs",
        max_bytes: int = 5_000_000,
        backup_count: int = 5,
        use_colors: bool = True,
        use_json: bool = False,
        console_output: bool = True,
    ):
        if CrackedCodeLogger._initialized:
            return

        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_level = getattr(logging, log_level.upper(), logging.INFO)
        self.use_colors = use_colors
        self.use_json = use_json
        self.console_output = console_output

        # Create handlers
        self.handlers: list[logging.Handler] = []

        # Console handler with colors
        if console_output:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(self.log_level)
            if use_json:
                console_handler.setFormatter(JsonFormatter())
            else:
                console_handler.setFormatter(
                    ColoredFormatter(
                        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                        datefmt="%H:%M:%S",
                        use_colors=use_colors,
                    )
                )
            self.handlers.append(console_handler)

        # Rotating file handler
        log_file = self.log_dir / "crackedcode.log"
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)  # File always gets DEBUG
        if use_json:
            file_handler.setFormatter(JsonFormatter())
        else:
            file_handler.setFormatter(
                logging.Formatter(
                    fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                )
            )
        self.handlers.append(file_handler)

        # Error file handler (errors only)
        error_file = self.log_dir / "crackedcode_errors.log"
        error_handler = logging.handlers.RotatingFileHandler(
            error_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        self.handlers.append(error_handler)

        CrackedCodeLogger._initialized = True

    def get_logger(self, name: str) -> logging.Logger:
        """Get a logger with the centralized configuration."""
        logger = logging.getLogger(name)
        logger.setLevel(self.log_level)

        # Remove existing handlers to avoid duplicates
        logger.handlers = []

        # Add our handlers
        for handler in self.handlers:
            logger.addHandler(handler)

        # Don't propagate to root to avoid duplicate messages
        logger.propagate = False

        return logger

    def set_level(self, level: str):
        """Change log level at runtime."""
        self.log_level = getattr(logging, level.upper(), logging.INFO)
        for handler in self.handlers:
            if not isinstance(handler, logging.handlers.RotatingFileHandler) or handler.baseFilename.endswith("errors.log"):
                handler.setLevel(self.log_level)


def setup_logging(config: Optional[Dict] = None) -> CrackedCodeLogger:
    """Initialize centralized logging from configuration.

    Args:
        config: Configuration dict with keys: log_level, log_dir, max_bytes,
                backup_count, use_colors, use_json, console_output

    Returns:
        CrackedCodeLogger instance
    """
    if config is None:
        config = {}

    return CrackedCodeLogger(
        log_level=config.get("log_level", "INFO"),
        log_dir=config.get("log_dir", "logs"),
        max_bytes=config.get("max_log_bytes", 5_000_000),
        backup_count=config.get("log_backup_count", 5),
        use_colors=config.get("use_colored_logs", True),
        use_json=config.get("use_json_logs", False),
        console_output=config.get("console_logging", True),
    )


def get_logger(name: str) -> logging.Logger:
    """Get a properly configured logger.

    If setup_logging() hasn't been called yet, creates a default instance.
    """
    if not CrackedCodeLogger._initialized:
        setup_logging()
    return CrackedCodeLogger._instance.get_logger(name)
