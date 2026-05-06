"""Web Dashboard v2.9.1 - Browser-based UI for CrackedCode.

A lightweight web interface that works on any device.
Access via http://localhost:8080/dashboard

Usage:
    python src/web_dashboard.py
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.logger_config import get_logger

try:
    from flask import Flask, render_template_string, request, jsonify
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False

logger = get_logger("WebDashboard")

# ── HTML Templates ─────────────────────────────────────────────────────────

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CrackedCode Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0a0a0a;
            color: #e0e0e0;
            min-height: 100vh;
        }
        .header {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            padding: 2rem;
            border-bottom: 2px solid #00FF41;
        }
        .header h1 {
            color: #00FF41;
            font-size: 2rem;
            margin-bottom: 0.5rem;
        }
        .header p { color: #888; }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 1.5rem;
            margin-top: 2rem;
        }
        .card {
            background: #1a1a2e;
            border: 1px solid #333;
            border-radius: 8px;
            padding: 1.5rem;
            transition: border-color 0.2s;
        }
        .card:hover { border-color: #00FF41; }
        .card h3 {
            color: #00FF41;
            margin-bottom: 1rem;
            font-size: 1.2rem;
        }
        .stat {
            display: flex;
            justify-content: space-between;
            padding: 0.5rem 0;
            border-bottom: 1px solid #333;
        }
        .stat:last-child { border-bottom: none; }
        .stat-value { color: #00FF41; font-weight: bold; }
        .chat-container {
            background: #1a1a2e;
            border: 1px solid #333;
            border-radius: 8px;
            height: 500px;
            display: flex;
            flex-direction: column;
        }
        .chat-messages {
            flex: 1;
            overflow-y: auto;
            padding: 1rem;
        }
        .chat-input {
            display: flex;
            padding: 1rem;
            border-top: 1px solid #333;
        }
        .chat-input input {
            flex: 1;
            background: #0a0a0a;
            border: 1px solid #333;
            color: #e0e0e0;
            padding: 0.75rem;
            border-radius: 4px;
            margin-right: 0.5rem;
        }
        .chat-input button {
            background: #00FF41;
            color: #0a0a0a;
            border: none;
            padding: 0.75rem 1.5rem;
            border-radius: 4px;
            cursor: pointer;
            font-weight: bold;
        }
        .chat-input button:hover { background: #00cc33; }
        .message {
            margin-bottom: 1rem;
            padding: 0.75rem;
            border-radius: 4px;
        }
        .message.user {
            background: #16213e;
            margin-left: 2rem;
        }
        .message.assistant {
            background: #1a1a2e;
            border: 1px solid #333;
            margin-right: 2rem;
        }
        .message .role {
            font-size: 0.8rem;
            color: #00FF41;
            margin-bottom: 0.25rem;
        }
        .nav {
            display: flex;
            gap: 1rem;
            margin-bottom: 2rem;
            flex-wrap: wrap;
        }
        .nav a {
            color: #888;
            text-decoration: none;
            padding: 0.5rem 1rem;
            border: 1px solid #333;
            border-radius: 4px;
            transition: all 0.2s;
        }
        .nav a:hover, .nav a.active {
            color: #00FF41;
            border-color: #00FF41;
        }
        pre {
            background: #0a0a0a;
            padding: 1rem;
            border-radius: 4px;
            overflow-x: auto;
            font-size: 0.9rem;
        }
        .status-indicator {
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            margin-right: 0.5rem;
        }
        .status-online { background: #00FF41; }
        .status-offline { background: #ff4444; }
    </style>
</head>
<body>
    <div class="header">
        <h1>⚡ CrackedCode Dashboard</h1>
        <p>Local AI Coding Assistant v2.9.1</p>
    </div>
    
    <div class="container">
        <div class="nav">
            <a href="#overview" class="active">Overview</a>
            <a href="#chat">Chat</a>
            <a href="#agents">Agents</a>
            <a href="#metrics">Metrics</a>
            <a href="#docs">API Docs</a>
        </div>
        
        <div class="grid">
            <div class="card">
                <h3>🤖 System Status</h3>
                <div class="stat">
                    <span>Ollama</span>
                    <span class="stat-value"><span class="status-indicator status-{{ 'online' if status.ollama_available else 'offline' }}"></span>{{ 'Online' if status.ollama_available else 'Offline' }}</span>
                </div>
                <div class="stat">
                    <span>Model</span>
                    <span class="stat-value">{{ status.model }}</span>
                </div>
                <div class="stat">
                    <span>Agents</span>
                    <span class="stat-value">{{ status.total_agents }}</span>
                </div>
                <div class="stat">
                    <span>Tools</span>
                    <span class="stat-value">{{ status.total_tools }}</span>
                </div>
            </div>
            
            <div class="card">
                <h3>📊 Today's Activity</h3>
                <div class="stat">
                    <span>Requests</span>
                    <span class="stat-value">{{ metrics.requests_total }}</span>
                </div>
                <div class="stat">
                    <span>Avg Latency</span>
                    <span class="stat-value">{{ '%.0f' % metrics.avg_latency_ms }}ms</span>
                </div>
                <div class="stat">
                    <span>Success Rate</span>
                    <span class="stat-value">{{ '%.0f' % success_rate }}%</span>
                </div>
                <div class="stat">
                    <span>Tokens</span>
                    <span class="stat-value">{{ metrics.tokens_generated }}</span>
                </div>
            </div>
            
            <div class="card">
                <h3>🎯 Quick Actions</h3>
                <div class="stat">
                    <a href="/docs" target="_blank" style="color: #00FF41;">📚 Open API Docs</a>
                </div>
                <div class="stat">
                    <a href="/export" style="color: #00FF41;">💾 Export Data</a>
                </div>
                <div class="stat">
                    <span style="color: #888;">🔑 Auth: {{ 'Enabled' if status.auth_required else 'Disabled' }}</span>
                </div>
                <div class="stat">
                    <span style="color: #888;">📡 API: {{ status.api_url }}</span>
                </div>
            </div>
        </div>
        
        <div class="chat-container" style="margin-top: 2rem;">
            <div class="chat-messages" id="messages">
                <div class="message assistant">
                    <div class="role">CrackedCode</div>
                    <div>Welcome to the CrackedCode dashboard! Enter a prompt below to start coding.</div>
                </div>
            </div>
            <div class="chat-input">
                <input type="text" id="prompt" placeholder="Enter your prompt..." onkeypress="handleKeyPress(event)">
                <button onclick="sendMessage()">Send</button>
            </div>
        </div>
    </div>
    
    <script>
        async function sendMessage() {
            const input = document.getElementById('prompt');
            const messages = document.getElementById('messages');
            const prompt = input.value.trim();
            
            if (!prompt) return;
            
            // Add user message
            messages.innerHTML += `<div class="message user"><div class="role">You</div><div>${escapeHtml(prompt)}</div></div>`;
            input.value = '';
            messages.scrollTop = messages.scrollHeight;
            
            // Send to API
            try {
                const response = await fetch('/process', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ prompt: prompt, intent: 'chat' })
                });
                const data = await response.json();
                
                messages.innerHTML += `<div class="message assistant"><div class="role">CrackedCode</div><div>${escapeHtml(data.text || data.error || 'No response')}</div></div>`;
                messages.scrollTop = messages.scrollHeight;
            } catch (e) {
                messages.innerHTML += `<div class="message assistant"><div class="role">Error</div><div>Failed to send: ${escapeHtml(e.message)}</div></div>`;
                messages.scrollTop = messages.scrollHeight;
            }
        }
        
        function handleKeyPress(event) {
            if (event.key === 'Enter') sendMessage();
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
    </script>
</body>
</html>
"""


class WebDashboard:
    """Web dashboard for CrackedCode."""
    
    def __init__(self, engine=None, host: str = "0.0.0.0", port: int = 3000):
        self.engine = engine
        self.host = host
        self.port = port
        self.app = None
        
        if FLASK_AVAILABLE:
            self._init_flask()
    
    def _init_flask(self):
        """Initialize Flask app."""
        self.app = Flask(__name__)
        self._register_routes()
    
    def _register_routes(self):
        """Register Flask routes."""
        
        @self.app.route("/")
        def index():
            return render_template_string("<script>window.location.href='/dashboard'</script>")
        
        @self.app.route("/dashboard")
        def dashboard():
            """Render the main dashboard."""
            status = self._get_status()
            metrics = self._get_metrics()
            
            total = metrics.get("requests_total", 1)
            success = metrics.get("requests_success", 0)
            success_rate = (success / total * 100) if total > 0 else 0
            
            return render_template_string(
                DASHBOARD_HTML,
                status=status,
                metrics=metrics,
                success_rate=success_rate,
            )
        
        @self.app.route("/api/status")
        def api_status():
            """Get system status as JSON."""
            return jsonify(self._get_status())
        
        @self.app.route("/api/metrics")
        def api_metrics():
            """Get metrics as JSON."""
            return jsonify(self._get_metrics())
    
    def _get_status(self) -> Dict[str, Any]:
        """Get system status."""
        status = {
            "ollama_available": False,
            "model": "unknown",
            "total_agents": 12,
            "total_tools": 0,
            "auth_required": False,
            "api_url": f"http://{self.host}:{self.port}",
        }
        
        if self.engine:
            try:
                engine_status = self.engine.get_status()
                status.update(engine_status)
            except Exception:
                pass
        
        return status
    
    def _get_metrics(self) -> Dict[str, Any]:
        """Get metrics."""
        metrics = {
            "requests_total": 0,
            "requests_success": 0,
            "avg_latency_ms": 0,
            "tokens_generated": 0,
        }
        
        try:
            from src.metrics import get_metrics_collector
            collector = get_metrics_collector()
            snapshot = collector.get_snapshot(hours=24)
            metrics["requests_total"] = snapshot.requests_total
            metrics["requests_success"] = snapshot.requests_success
            metrics["avg_latency_ms"] = round(snapshot.avg_latency_ms, 2)
            metrics["tokens_generated"] = snapshot.tokens_generated
        except Exception:
            pass
        
        return metrics
    
    def start(self) -> bool:
        """Start the web dashboard."""
        if not FLASK_AVAILABLE:
            logger.error("Flask not available - cannot start web dashboard")
            return False
        
        try:
            logger.info(f"Web dashboard starting on http://{self.host}:{self.port}")
            self.app.run(host=self.host, port=self.port, debug=False, threaded=True)
            return True
        except Exception as e:
            logger.error(f"Failed to start web dashboard: {e}")
            return False


def create_web_dashboard(engine=None, host: str = "0.0.0.0", port: int = 3000) -> WebDashboard:
    """Create a WebDashboard instance."""
    return WebDashboard(engine=engine, host=host, port=port)


if __name__ == "__main__":
    dashboard = create_web_dashboard()
    dashboard.start()
