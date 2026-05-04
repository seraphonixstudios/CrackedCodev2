"""Discord Webhook Plugin - Sends notifications to Discord.

Posts system events to a Discord channel via webhook URL.
Configure by setting the WEBHOOK_URL in metadata.
"""

import json
import urllib.request
import urllib.error

from src.plugin_system import plugin, HookPoint


@plugin(
    name="discord_webhook",
    version="1.0.0",
    description="Send notifications to Discord via webhook",
    author="CrackedCode Team"
)
class DiscordWebhookPlugin:
    """Notifies Discord about important system events."""
    
    WEBHOOK_URL = None  # Set this in plugin metadata
    
    def __init__(self):
        self.webhook_url = self.WEBHOOK_URL
    
    def _send(self, message: str, username: str = "CrackedCode") -> str:
        """Send a message to Discord."""
        if not self.webhook_url:
            return "[Discord] No webhook URL configured"
        
        payload = {
            "content": message,
            "username": username,
        }
        
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                self.webhook_url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return f"[Discord] Sent: {message[:50]}..."
        except urllib.error.URLError as e:
            return f"[Discord] Failed to send: {e}"
        except Exception as e:
            return f"[Discord] Error: {e}"
    
    def on_system_startup(self):
        return self._send("CrackedCode agent started", "System")
    
    def on_orchestrator_task_completed(self, task):
        task_id = getattr(task, 'id', '?')[:8]
        return self._send(f"Task {task_id} completed", "Orchestrator")
    
    def on_orchestrator_task_failed(self, task):
        task_id = getattr(task, 'id', '?')[:8]
        return self._send(f"Task {task_id} failed", "Orchestrator")
