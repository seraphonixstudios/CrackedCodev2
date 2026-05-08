"""MCP (Model Context Protocol) Client - Connect to external MCP servers.

Lightweight implementation of Anthropic's MCP protocol.
Supports stdio and SSE transports.

Features:
- MCP server discovery and connection
- Tool listing and execution
- Resource access
- Integration with CrackedCode ToolRegistry

Protocol: JSON-RPC 2.0
"""

import json
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urljoin

from src.logger_config import get_logger

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

logger = get_logger("MCPClient")


class TransportType(Enum):
    STDIO = "stdio"
    SSE = "sse"


@dataclass
class MCPTool:
    """Represents a tool exposed by an MCP server."""
    name: str
    description: str
    input_schema: Dict[str, Any]
    server_name: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


@dataclass
class MCPResource:
    """Represents a resource exposed by an MCP server."""
    uri: str
    name: str
    mime_type: str = ""
    description: str = ""
    server_name: str = ""


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server connection."""
    name: str
    transport: TransportType
    command: Optional[str] = None
    args: List[str] = field(default_factory=list)
    url: Optional[str] = None
    env: Dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    timeout: int = 30


class MCPTransport:
    """Base class for MCP transports."""
    
    def send(self, message: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError
    
    def close(self):
        pass


class StdioTransport(MCPTransport):
    """JSON-RPC over stdio transport."""
    
    def __init__(self, command: str, args: List[str] = None, env: Dict[str, str] = None, timeout: int = 30):
        self.command = command
        self.args = args or []
        self.env = env or {}
        self.timeout = timeout
        self.process: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        self._init_process()
    
    def _init_process(self):
        """Start the subprocess."""
        try:
            env = {**dict(subprocess.os.environ), **self.env}
            self.process = subprocess.Popen(
                [self.command, *self.args],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
            )
            logger.info(f"StdioTransport started: {self.command} {' '.join(self.args)}")
        except Exception as e:
            logger.error(f"Failed to start MCP server process: {e}")
            raise
    
    def send(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Send a JSON-RPC message and return the response."""
        if not self.process or self.process.poll() is not None:
            logger.warning("MCP process not running, restarting...")
            self._init_process()
        
        with self._lock:
            try:
                # Send message
                line = json.dumps(message) + "\n"
                self.process.stdin.write(line)
                self.process.stdin.flush()
                
                # Read response
                response_line = self.process.stdout.readline()
                if not response_line:
                    return {"jsonrpc": "2.0", "id": message.get("id"), "error": {"code": -32000, "message": "No response from server"}}
                
                return json.loads(response_line)
            except Exception as e:
                logger.error(f"StdioTransport error: {e}")
                return {"jsonrpc": "2.0", "id": message.get("id"), "error": {"code": -32000, "message": str(e)}}
    
    def close(self):
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except Exception:
                self.process.kill()
            self.process = None


class SSETransport(MCPTransport):
    """Server-Sent Events transport for MCP."""
    
    def __init__(self, base_url: str, timeout: int = 30):
        if not HTTPX_AVAILABLE:
            raise ImportError("httpx required for SSE transport")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout)
        self.message_endpoint: Optional[str] = None
        self._session_id: Optional[str] = None
    
    def connect(self) -> bool:
        """Connect and discover message endpoint."""
        try:
            response = self.client.get(f"{self.base_url}/sse", headers={"Accept": "text/event-stream"})
            response.raise_for_status()
            
            # Parse SSE stream for endpoint
            for line in response.text.split("\n"):
                if line.startswith("event: endpoint"):
                    # Next line should be data: <url>
                    pass
                elif line.startswith("data:") and self.message_endpoint is None:
                    data = line[5:].strip()
                    if data.startswith("http") or data.startswith("/"):
                        self.message_endpoint = data if data.startswith("http") else urljoin(self.base_url, data)
            
            if not self.message_endpoint:
                # Fallback: assume direct endpoint
                self.message_endpoint = f"{self.base_url}/message"
            
            logger.info(f"SSETransport connected: {self.message_endpoint}")
            return True
        except Exception as e:
            logger.error(f"SSE connection failed: {e}")
            return False
    
    def send(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Send a JSON-RPC message via HTTP POST."""
        if not self.message_endpoint:
            if not self.connect():
                return {"jsonrpc": "2.0", "id": message.get("id"), "error": {"code": -32000, "message": "Not connected"}}
        
        try:
            headers = {"Content-Type": "application/json"}
            if self._session_id:
                headers["Mcp-Session-Id"] = self._session_id
            
            response = self.client.post(self.message_endpoint, json=message, headers=headers)
            response.raise_for_status()
            
            # Check for session ID in response
            if "Mcp-Session-Id" in response.headers:
                self._session_id = response.headers["Mcp-Session-Id"]
            
            return response.json()
        except Exception as e:
            logger.error(f"SSETransport error: {e}")
            return {"jsonrpc": "2.0", "id": message.get("id"), "error": {"code": -32000, "message": str(e)}}
    
    def close(self):
        if self.client:
            self.client.close()


class MCPClient:
    """Client for connecting to MCP servers and using their tools."""
    
    def __init__(self):
        self.servers: Dict[str, MCPTransport] = {}
        self.tools: Dict[str, MCPTool] = {}
        self.resources: Dict[str, MCPResource] = {}
        self.configs: Dict[str, MCPServerConfig] = {}
        self._initialized: Dict[str, bool] = {}
    
    def add_server(self, config: MCPServerConfig) -> bool:
        """Add and initialize an MCP server."""
        if not config.enabled:
            logger.info(f"MCP server '{config.name}' is disabled, skipping")
            return False
        
        try:
            if config.transport == TransportType.STDIO:
                if not config.command:
                    raise ValueError("STDIO transport requires 'command'")
                transport = StdioTransport(
                    command=config.command,
                    args=config.args,
                    env=config.env,
                    timeout=config.timeout,
                )
            elif config.transport == TransportType.SSE:
                if not config.url:
                    raise ValueError("SSE transport requires 'url'")
                transport = SSETransport(base_url=config.url, timeout=config.timeout)
                if not transport.connect():
                    return False
            else:
                raise ValueError(f"Unknown transport: {config.transport}")
            
            self.servers[config.name] = transport
            self.configs[config.name] = config
            
            # Initialize
            if self._initialize_server(config.name):
                self._initialized[config.name] = True
                self._discover_tools(config.name)
                logger.info(f"MCP server '{config.name}' connected with {len([t for t in self.tools.values() if t.server_name == config.name])} tools")
                return True
            else:
                logger.warning(f"MCP server '{config.name}' initialization failed")
                return False
                
        except Exception as e:
            logger.error(f"Failed to add MCP server '{config.name}': {e}")
            return False
    
    def _initialize_server(self, name: str) -> bool:
        """Send initialize request to server."""
        transport = self.servers.get(name)
        if not transport:
            return False
        
        request = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "crackedcode", "version": "2.6.7"},
            },
        }
        
        response = transport.send(request)
        if "error" in response:
            logger.error(f"MCP initialize error: {response['error']}")
            return False
        
        # Send initialized notification
        transport.send({
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        })
        
        return True
    
    def _discover_tools(self, server_name: str):
        """Discover tools from an MCP server."""
        transport = self.servers.get(server_name)
        if not transport:
            return
        
        request = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "tools/list",
        }
        
        response = transport.send(request)
        if "error" in response:
            logger.warning(f"tools/list failed for {server_name}: {response['error']}")
            return
        
        result = response.get("result", {})
        tools_list = result.get("tools", [])
        
        for tool_data in tools_list:
            tool = MCPTool(
                name=f"{server_name}/{tool_data['name']}",
                description=tool_data.get("description", ""),
                input_schema=tool_data.get("inputSchema", {}),
                server_name=server_name,
            )
            self.tools[tool.name] = tool
        
        logger.info(f"Discovered {len(tools_list)} tools from '{server_name}'")
    
    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call an MCP tool by name."""
        tool = self.tools.get(tool_name)
        if not tool:
            return {"success": False, "error": f"Tool '{tool_name}' not found"}
        
        transport = self.servers.get(tool.server_name)
        if not transport:
            return {"success": False, "error": f"Server '{tool.server_name}' not connected"}
        
        request = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "tools/call",
            "params": {
                "name": tool_name.split("/", 1)[1],  # Remove server prefix
                "arguments": arguments,
            },
        }
        
        start = time.time()
        response = transport.send(request)
        duration = time.time() - start
        
        if "error" in response:
            return {
                "success": False,
                "error": response["error"].get("message", "Unknown error"),
                "duration": duration,
            }
        
        result = response.get("result", {})
        content = result.get("content", [])
        
        # Extract text content
        text_parts = []
        for item in content:
            if item.get("type") == "text":
                text_parts.append(item.get("text", ""))
        
        return {
            "success": True,
            "content": "\n".join(text_parts),
            "raw": result,
            "duration": duration,
            "tool": tool_name,
        }
    
    def list_tools(self) -> List[MCPTool]:
        """List all available MCP tools."""
        return list(self.tools.values())
    
    def list_servers(self) -> List[str]:
        """List connected server names."""
        return [name for name, init in self._initialized.items() if init]
    
    def get_server_status(self, name: str) -> Dict[str, Any]:
        """Get status of a specific server."""
        return {
            "name": name,
            "connected": self._initialized.get(name, False),
            "config": {
                "transport": self.configs.get(name, MCPServerConfig(name=name, transport=TransportType.STDIO)).transport.value,
                "enabled": self.configs.get(name, MCPServerConfig(name=name, transport=TransportType.STDIO)).enabled,
            },
            "tools": len([t for t in self.tools.values() if t.server_name == name]),
        }
    
    def remove_server(self, name: str):
        """Disconnect and remove a server."""
        if name in self.servers:
            self.servers[name].close()
            del self.servers[name]
        
        # Remove associated tools
        self.tools = {k: v for k, v in self.tools.items() if v.server_name != name}
        
        if name in self.configs:
            del self.configs[name]
        if name in self._initialized:
            del self._initialized[name]
        
        logger.info(f"MCP server '{name}' removed")
    
    def close_all(self):
        """Close all server connections."""
        for name, transport in self.servers.items():
            transport.close()
        self.servers.clear()
        self.tools.clear()
        self.resources.clear()
        self._initialized.clear()
        logger.info("All MCP connections closed")


class MCPConfigManager:
    """Manage MCP server configurations from JSON files."""
    
    def __init__(self, config_dir: str = "mcp_servers"):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)
    
    def load_config(self, name: str) -> Optional[MCPServerConfig]:
        """Load a server config from JSON file."""
        path = self.config_dir / f"{name}.json"
        if not path.exists():
            return None
        
        try:
            data = json.loads(path.read_text())
            return MCPServerConfig(
                name=data["name"],
                transport=TransportType(data.get("transport", "stdio")),
                command=data.get("command"),
                args=data.get("args", []),
                url=data.get("url"),
                env=data.get("env", {}),
                enabled=data.get("enabled", True),
                timeout=data.get("timeout", 30),
            )
        except Exception as e:
            logger.error(f"Failed to load MCP config '{name}': {e}")
            return None
    
    def save_config(self, config: MCPServerConfig):
        """Save a server config to JSON file."""
        path = self.config_dir / f"{config.name}.json"
        data = {
            "name": config.name,
            "transport": config.transport.value,
            "command": config.command,
            "args": config.args,
            "url": config.url,
            "env": config.env,
            "enabled": config.enabled,
            "timeout": config.timeout,
        }
        path.write_text(json.dumps(data, indent=2))
    
    def list_configs(self) -> List[str]:
        """List available config names."""
        return [p.stem for p in self.config_dir.glob("*.json")]
    
    def load_all(self) -> List[MCPServerConfig]:
        """Load all configurations."""
        configs = []
        for name in self.list_configs():
            config = self.load_config(name)
            if config:
                configs.append(config)
        return configs


def get_mcp_client() -> MCPClient:
    """Get a global MCPClient instance."""
    if not hasattr(get_mcp_client, "_instance"):
        get_mcp_client._instance = MCPClient()
    return get_mcp_client._instance

