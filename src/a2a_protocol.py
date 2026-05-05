"""A2A (Agent-to-Agent) Protocol - Multi-agent communication.

Lightweight implementation of Google's A2A protocol for agent interoperability.

Features:
- Agent discovery and capability negotiation
- Task delegation between agents
- Message passing with structured content
- Local and remote agent communication

Protocol: JSON-RPC 2.0 over HTTP/stdio
"""

import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from src.logger_config import get_logger

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

try:
    from http.server import HTTPServer, BaseHTTPRequestHandler
    HTTP_SERVER_AVAILABLE = True
except ImportError:
    HTTP_SERVER_AVAILABLE = False

logger = get_logger("A2AProtocol")


class A2ATaskState(Enum):
    """Task lifecycle states in A2A."""
    SUBMITTED = "submitted"
    WORKING = "working"
    INPUT_REQUIRED = "input_required"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass
class A2AAgentCard:
    """Agent capability card for discovery."""
    name: str
    description: str
    version: str
    capabilities: List[str] = field(default_factory=list)
    skills: List[Dict[str, Any]] = field(default_factory=list)
    endpoint: str = ""  # URL or "stdio"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "capabilities": self.capabilities,
            "skills": self.skills,
            "endpoint": self.endpoint,
        }


@dataclass
class A2AMessage:
    """A message in an A2A conversation."""
    role: str  # user, agent
    parts: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class A2ATask:
    """A task delegated via A2A."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    session_id: str = ""
    state: A2ATaskState = A2ATaskState.SUBMITTED
    messages: List[A2AMessage] = field(default_factory=list)
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "state": self.state.value,
            "messages": [{"role": m.role, "parts": m.parts} for m in self.messages],
            "artifacts": self.artifacts,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class A2AClient:
    """Client for communicating with external A2A agents."""
    
    def __init__(self, agent_card: A2AAgentCard = None):
        self.agent_card = agent_card
        self.client = httpx.Client(timeout=60) if HTTPX_AVAILABLE else None
    
    def discover(self, endpoint: str) -> Optional[A2AAgentCard]:
        """Discover agent capabilities from endpoint."""
        if not self.client:
            logger.error("httpx not available for A2A discovery")
            return None
        
        try:
            response = self.client.get(f"{endpoint}/.well-known/agent.json")
            response.raise_for_status()
            data = response.json()
            
            card = A2AAgentCard(
                name=data.get("name", "unknown"),
                description=data.get("description", ""),
                version=data.get("version", "1.0"),
                capabilities=data.get("capabilities", []),
                skills=data.get("skills", []),
                endpoint=endpoint,
            )
            self.agent_card = card
            return card
        except Exception as e:
            logger.error(f"A2A discovery failed: {e}")
            return None
    
    def send_task(self, message: str, session_id: str = None) -> Optional[A2ATask]:
        """Send a task to the remote agent."""
        if not self.agent_card or not self.client:
            logger.error("No agent card or HTTP client available")
            return None
        
        task = A2ATask(session_id=session_id or str(uuid.uuid4())[:8])
        task.messages.append(A2AMessage(role="user", parts=[{"type": "text", "text": message}]))
        
        try:
            response = self.client.post(
                f"{self.agent_card.endpoint}/tasks/send",
                json={
                    "id": task.id,
                    "session_id": task.session_id,
                    "message": {
                        "role": "user",
                        "parts": [{"type": "text", "text": message}],
                    },
                },
            )
            response.raise_for_status()
            result = response.json()
            
            task.state = A2ATaskState(result.get("state", "completed"))
            if "result" in result:
                task.artifacts.append(result["result"])
            
            return task
        except Exception as e:
            logger.error(f"A2A task send failed: {e}")
            task.state = A2ATaskState.FAILED
            return task
    
    def close(self):
        if self.client:
            self.client.close()


class A2AServer:
    """HTTP server for receiving A2A requests from other agents."""
    
    def __init__(self, agent_card: A2AAgentCard, port: int = 8000):
        self.agent_card = agent_card
        self.port = port
        self._handler_class = self._make_handler()
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._task_handler: Optional[Callable[[str], str]] = None
    
    def _make_handler(self):
        """Create request handler class."""
        card = self.agent_card
        task_handler = self._task_handler
        
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                logger.info(f"A2A Server: {args[0]}")
            
            def do_GET(self):
                if self.path == "/.well-known/agent.json":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(card.to_dict()).encode())
                else:
                    self.send_response(404)
                    self.end_headers()
            
            def do_POST(self):
                if self.path == "/tasks/send":
                    content_length = int(self.headers.get("Content-Length", 0))
                    body = self.rfile.read(content_length)
                    data = json.loads(body)
                    
                    message = data.get("message", {})
                    parts = message.get("parts", [])
                    text = parts[0].get("text", "") if parts else ""
                    
                    # Handle task
                    if task_handler:
                        result_text = task_handler(text)
                    else:
                        result_text = "Task received but no handler configured"
                    
                    response = {
                        "id": data.get("id", ""),
                        "session_id": data.get("session_id", ""),
                        "state": "completed",
                        "result": {
                            "parts": [{"type": "text", "text": result_text}],
                        },
                    }
                    
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(response).encode())
                else:
                    self.send_response(404)
                    self.end_headers()
        
        return Handler
    
    def set_task_handler(self, handler: Callable[[str], str]):
        """Set the function that handles incoming tasks."""
        self._task_handler = handler
        self._handler_class = self._make_handler()
    
    def start(self):
        """Start the A2A server in a background thread."""
        if not HTTP_SERVER_AVAILABLE:
            logger.error("HTTP server not available")
            return False
        
        try:
            self._server = HTTPServer(("localhost", self.port), self._handler_class)
            self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
            self._thread.start()
            logger.info(f"A2A server started on port {self.port}")
            return True
        except Exception as e:
            logger.error(f"A2A server failed to start: {e}")
            return False
    
    def stop(self):
        """Stop the A2A server."""
        if self._server:
            self._server.shutdown()
            self._server = None
            logger.info("A2A server stopped")


class A2ARegistry:
    """Registry of known A2A agents."""
    
    def __init__(self):
        self.agents: Dict[str, A2AAgentCard] = {}
        self.clients: Dict[str, A2AClient] = {}
    
    def register(self, card: A2AAgentCard) -> A2AClient:
        """Register an agent and create a client."""
        self.agents[card.name] = card
        client = A2AClient(card)
        self.clients[card.name] = client
        logger.info(f"Registered A2A agent: {card.name}")
        return client
    
    def discover(self, name: str, endpoint: str) -> Optional[A2AAgentCard]:
        """Discover and register an agent from endpoint."""
        client = A2AClient()
        card = client.discover(endpoint)
        if card:
            self.register(card)
        return card
    
    def get_client(self, name: str) -> Optional[A2AClient]:
        """Get client for a registered agent."""
        return self.clients.get(name)
    
    def list_agents(self) -> List[str]:
        """List registered agent names."""
        return list(self.agents.keys())
    
    def get_agent_card(self, name: str) -> Optional[A2AAgentCard]:
        """Get agent card by name."""
        return self.agents.get(name)
    
    def unregister(self, name: str):
        """Remove an agent from registry."""
        if name in self.clients:
            self.clients[name].close()
            del self.clients[name]
        if name in self.agents:
            del self.agents[name]


# Singleton
_a2a_registry: Optional[A2ARegistry] = None

def get_a2a_registry() -> A2ARegistry:
    """Get the global A2A registry."""
    global _a2a_registry
    if _a2a_registry is None:
        _a2a_registry = A2ARegistry()
    return _a2a_registry
