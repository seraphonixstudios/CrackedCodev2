"""Notification System v2.8.1 - Multi-backend alerts for CrackedCode.

Backends:
  - Email (SMTP)
  - Webhook (HTTP POST to Slack/Discord/generic)
  - Desktop (Windows toast notifications)
  - Log (structured logging)

Usage:
    from src.notifications import NotificationManager, create_notification_manager
    nm = create_notification_manager(config)
    nm.notify("Task Complete", "Weekly security scan finished with 0 issues.")
"""

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.logger_config import get_logger

logger = get_logger("Notifications")


# ── Data Models ────────────────────────────────────────────────────────────

@dataclass
class Notification:
    """A notification message."""
    title: str
    message: str
    level: str = "info"  # info, warning, error, success
    source: str = "crackedcode"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


# ── Backends ───────────────────────────────────────────────────────────────

class EmailBackend:
    """Send notifications via SMTP email."""
    
    def __init__(self, smtp_host: str = "localhost", smtp_port: int = 587,
                 username: Optional[str] = None, password: Optional[str] = None,
                 from_addr: str = "crackedcode@localhost", to_addrs: List[str] = None,
                 use_tls: bool = True):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_addr = from_addr
        self.to_addrs = to_addrs or []
        self.use_tls = use_tls
    
    def send(self, notification: Notification) -> bool:
        """Send email notification."""
        if not self.to_addrs:
            return False
        
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            msg = MIMEMultipart()
            msg["From"] = self.from_addr
            msg["To"] = ", ".join(self.to_addrs)
            msg["Subject"] = f"[{notification.level.upper()}] {notification.title}"
            
            body = f"""CrackedCode Notification
========================

Title: {notification.title}
Level: {notification.level}
Time:  {notification.timestamp}
Source: {notification.source}

{notification.message}
"""
            if notification.metadata:
                body += f"\nMetadata:\n{json.dumps(notification.metadata, indent=2)}\n"
            
            msg.attach(MIMEText(body, "plain"))
            
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                if self.username and self.password:
                    server.login(self.username, self.password)
                server.send_message(msg)
            
            logger.info(f"Email notification sent: {notification.title}")
            return True
        except Exception as e:
            logger.error(f"Email notification failed: {e}")
            return False


class WebhookBackend:
    """Send notifications via HTTP POST webhook."""
    
    def __init__(self, url: str, headers: Optional[Dict[str, str]] = None,
                 timeout: int = 10):
        self.url = url
        self.headers = headers or {"Content-Type": "application/json"}
        self.timeout = timeout
    
    def send(self, notification: Notification) -> bool:
        """Send webhook notification."""
        if not self.url:
            return False
        
        try:
            import requests
            
            payload = {
                "title": notification.title,
                "message": notification.message,
                "level": notification.level,
                "source": notification.source,
                "timestamp": notification.timestamp,
                "metadata": notification.metadata,
            }
            
            response = requests.post(
                self.url,
                json=payload,
                headers=self.headers,
                timeout=self.timeout,
            )
            
            if response.status_code < 400:
                logger.info(f"Webhook notification sent: {notification.title}")
                return True
            else:
                logger.warning(f"Webhook returned {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Webhook notification failed: {e}")
            return False


class DesktopBackend:
    """Show desktop toast notifications."""
    
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
    
    def send(self, notification: Notification) -> bool:
        """Show desktop notification."""
        if not self.enabled:
            return False
        
        try:
            # Try win10toast on Windows
            try:
                from win10toast import ToastNotifier
                toaster = ToastNotifier()
                toaster.show_toast(
                    notification.title,
                    notification.message,
                    duration=10,
                    threaded=True,
                )
                return True
            except ImportError:
                pass
            
            # Try plyer as fallback
            try:
                from plyer import notification as plyer_notify
                plyer_notify.notify(
                    title=notification.title,
                    message=notification.message,
                    timeout=10,
                )
                return True
            except ImportError:
                pass
            
            logger.debug("No desktop notification backend available")
            return False
        except Exception as e:
            logger.error(f"Desktop notification failed: {e}")
            return False


class LogBackend:
    """Log notifications to the structured log."""
    
    def send(self, notification: Notification) -> bool:
        """Log notification."""
        log_method = getattr(logger, notification.level, logger.info)
        log_method(f"[NOTIFY] {notification.title}: {notification.message}")
        return True


# ── Notification Manager ───────────────────────────────────────────────────

class NotificationManager:
    """Orchestrates multiple notification backends."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.backends: List[Any] = []
        self.enabled = self.config.get("enabled", True)
        self.min_level = self.config.get("min_level", "info")
        self._init_backends()
    
    def _init_backends(self):
        """Initialize backends from config."""
        if not self.enabled:
            return
        
        # Always add log backend
        self.backends.append(LogBackend())
        
        # Email backend
        email_config = self.config.get("email", {})
        if email_config.get("enabled", False):
            self.backends.append(EmailBackend(
                smtp_host=email_config.get("smtp_host", "localhost"),
                smtp_port=email_config.get("smtp_port", 587),
                username=email_config.get("username"),
                password=email_config.get("password"),
                from_addr=email_config.get("from", "crackedcode@localhost"),
                to_addrs=email_config.get("to", []),
                use_tls=email_config.get("use_tls", True),
            ))
        
        # Webhook backend
        webhook_config = self.config.get("webhook", {})
        if webhook_config.get("enabled", False):
            self.backends.append(WebhookBackend(
                url=webhook_config.get("url", ""),
                headers=webhook_config.get("headers", {"Content-Type": "application/json"}),
                timeout=webhook_config.get("timeout", 10),
            ))
        
        # Desktop backend
        desktop_config = self.config.get("desktop", {})
        if desktop_config.get("enabled", False):
            self.backends.append(DesktopBackend(
                enabled=desktop_config.get("enabled", True),
            ))
        
        logger.info(f"NotificationManager initialized with {len(self.backends)} backends")
    
    def notify(self, title: str, message: str, level: str = "info",
               source: str = "crackedcode", metadata: Optional[Dict[str, Any]] = None) -> Dict[str, bool]:
        """Send a notification through all enabled backends.
        
        Returns dict of backend_name -> success_bool.
        """
        if not self.enabled:
            return {}
        
        # Check level threshold
        levels = {"debug": 0, "info": 1, "success": 1, "warning": 2, "error": 3}
        if levels.get(level, 1) < levels.get(self.min_level, 1):
            return {}
        
        notification = Notification(
            title=title,
            message=message,
            level=level,
            source=source,
            metadata=metadata or {},
        )
        
        results = {}
        for backend in self.backends:
            backend_name = type(backend).__name__
            try:
                success = backend.send(notification)
                results[backend_name] = success
            except Exception as e:
                logger.error(f"Backend {backend_name} failed: {e}")
                results[backend_name] = False
        
        return results
    
    def info(self, title: str, message: str, **kwargs):
        """Send info notification."""
        return self.notify(title, message, level="info", **kwargs)
    
    def success(self, title: str, message: str, **kwargs):
        """Send success notification."""
        return self.notify(title, message, level="success", **kwargs)
    
    def warning(self, title: str, message: str, **kwargs):
        """Send warning notification."""
        return self.notify(title, message, level="warning", **kwargs)
    
    def error(self, title: str, message: str, **kwargs):
        """Send error notification."""
        return self.notify(title, message, level="error", **kwargs)


def create_notification_manager(config: Optional[Dict[str, Any]] = None) -> NotificationManager:
    """Create a NotificationManager from config dict."""
    return NotificationManager(config=config)


# ── Singleton ──────────────────────────────────────────────────────────────

_notification_manager: Optional[NotificationManager] = None


def get_notification_manager(config: Optional[Dict[str, Any]] = None) -> NotificationManager:
    """Get or create the global notification manager."""
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = create_notification_manager(config)
    return _notification_manager
