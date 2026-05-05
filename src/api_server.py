"""REST API Server - Expose CrackedCode capabilities via HTTP.

Endpoints:
- POST /process      - Process a prompt with the engine
- POST /process/stream - Stream a prompt response via SSE
- WS   /ws           - Bidirectional WebSocket for real-time chat
- GET  /status       - System status and configuration
- GET  /agents       - List all agents (built-in + custom)
- GET  /tools        - List available tools with schemas
- GET  /conversations - List conversation history
- POST /conversations - Create a new conversation
- GET  /models       - List available Ollama models
- GET  /docs         - OpenAPI/Swagger documentation (auto-generated)

Authentication (optional):
  Set "api_key" in config.json or pass to create_api_server().
  All endpoints except / and /docs require X-API-Key header.

Usage:
    python src/api_server.py
    
    curl -X POST http://localhost:8080/process \
         -H "Content-Type: application/json" \
         -H "X-API-Key: your-key" \
         -d '{"prompt": "Write a Python function to add numbers", "intent": "code"}'
"""

import asyncio
import json
import threading
import time
from dataclasses import dataclass, asdict
from typing import Any, AsyncGenerator, Dict, List, Optional

from src.logger_config import get_logger

try:
    from fastapi import FastAPI, HTTPException, Depends, Security, WebSocket, WebSocketDisconnect
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import StreamingResponse
    from fastapi.security import APIKeyHeader
    from pydantic import BaseModel
    import uvicorn
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

logger = get_logger("APIServer")

# API key header scheme
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


# ── Request/Response Models ────────────────────────────────────────────────

class ProcessRequest(BaseModel):
    prompt: str
    intent: Optional[str] = "chat"
    streaming: Optional[bool] = False
    context: Optional[Dict[str, Any]] = None


class ProcessResponse(BaseModel):
    success: bool
    text: str = ""
    error: str = ""
    intent: str = ""
    model_used: str = ""
    execution_time: float = 0.0
    processing_path: str = ""


class StreamResponse(BaseModel):
    token: str = ""
    done: bool = False
    full_text: str = ""
    intent: str = ""
    model_used: str = ""
    error: str = ""


class StatusResponse(BaseModel):
    version: str = ""
    model: str = ""
    vision_model: str = ""
    secondary_model: str = ""
    ollama_available: bool = False
    ollama_models: List[str] = []
    total_tools: int = 0
    total_agents: int = 0
    total_conversations: int = 0


class AgentInfo(BaseModel):
    name: str
    role: str
    capabilities: List[str] = []
    description: str = ""
    enabled: bool = True


class ToolInfo(BaseModel):
    name: str
    description: str = ""
    permission: str = ""
    category: str = ""


class ConversationInfo(BaseModel):
    id: str
    name: str
    created_at: float
    updated_at: float
    turn_count: int
    tags: List[str] = []


# ── API Server ─────────────────────────────────────────────────────────────

class CrackedCodeAPI:
    """REST API server for CrackedCode."""
    
    def __init__(self, engine=None, host: str = "0.0.0.0", port: int = 8080, api_key: Optional[str] = None):
        self.engine = engine
        self.host = host
        self.port = port
        self.api_key = api_key
        self._app: Optional[Any] = None
        self._server_thread: Optional[threading.Thread] = None
        self._running = False
        
        if FASTAPI_AVAILABLE:
            self._init_fastapi()
    
    def _init_fastapi(self):
        """Initialize FastAPI application."""
        self._app = FastAPI(
            title="CrackedCode API",
            description="REST API for the CrackedCode local AI coding assistant",
            version="2.7.8",
        )
        
        # CORS
        self._app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        self._register_routes()
    
    def _verify_api_key(self, api_key: Optional[str] = Security(api_key_header)):
        """Verify API key if one is configured."""
        if not self.api_key:
            # No API key configured — auth disabled
            return True
        
        if not api_key:
            raise HTTPException(
                status_code=401,
                detail="API key required. Provide X-API-Key header.",
            )
        
        if api_key != self.api_key:
            raise HTTPException(
                status_code=401,
                detail="Invalid API key.",
            )
        
        return True
    
    def _register_routes(self):
        """Register API routes."""
        
        @self._app.get("/")
        async def root():
            return {
                "name": "CrackedCode API",
                "version": "2.7.8",
                "docs": "/docs",
                "auth_required": bool(self.api_key),
                "endpoints": [
                    "/process",
                    "/process/stream",
                    "/ws",
                    "/status",
                    "/agents",
                    "/tools",
                    "/conversations",
                    "/models",
                    "/metrics",
                ],
            }
        
        @self._app.post("/process", response_model=ProcessResponse, dependencies=[Depends(self._verify_api_key)])
        async def process(request: ProcessRequest):
            """Process a prompt with the CrackedCode engine."""
            if not self.engine:
                raise HTTPException(status_code=503, detail="Engine not initialized")
            
            try:
                start = time.time()
                response = await self.engine.process(
                    prompt=request.prompt,
                    intent=request.intent,
                )
                
                return ProcessResponse(
                    success=response.success,
                    text=response.text,
                    error=response.error or "",
                    intent=request.intent,
                    model_used=getattr(response, 'model_used', ''),
                    execution_time=time.time() - start,
                    processing_path=getattr(response, 'processing_path', ''),
                )
            except Exception as e:
                logger.error(f"API process error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self._app.post("/process/stream", dependencies=[Depends(self._verify_api_key)])
        async def process_stream(request: ProcessRequest):
            """Process a prompt with streaming (Server-Sent Events)."""
            if not self.engine:
                raise HTTPException(status_code=503, detail="Engine not initialized")
            
            async def event_generator() -> AsyncGenerator[str, None]:
                """Async generator that yields SSE events from the engine stream."""
                queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
                
                def token_callback(token: str) -> None:
                    """Callback called by the engine for each token."""
                    try:
                        queue.put_nowait({"type": "token", "token": token})
                    except Exception:
                        pass
                
                # Run the engine in a background task
                async def run_engine() -> None:
                    try:
                        response = await self.engine.process(
                            prompt=request.prompt,
                            intent=request.intent,
                            streaming=True,
                            callback=token_callback,
                        )
                        queue.put_nowait({
                            "type": "done",
                            "success": response.success,
                            "full_text": response.text,
                            "model_used": getattr(response, 'model_used', ''),
                            "processing_path": getattr(response, 'processing_path', ''),
                            "error": response.error or "",
                        })
                    except Exception as e:
                        logger.error(f"Streaming engine error: {e}")
                        queue.put_nowait({"type": "error", "error": str(e)})
                
                # Start engine in background
                task = asyncio.create_task(run_engine())
                
                try:
                    while True:
                        event = await queue.get()
                        
                        if event["type"] == "token":
                            data = json.dumps({
                                "token": event["token"],
                                "done": False,
                            })
                            yield f"data: {data}\n\n"
                        
                        elif event["type"] == "done":
                            data = json.dumps({
                                "token": "",
                                "done": True,
                                "full_text": event.get("full_text", ""),
                                "intent": request.intent,
                                "model_used": event.get("model_used", ""),
                                "processing_path": event.get("processing_path", ""),
                                "success": event.get("success", True),
                            })
                            yield f"data: {data}\n\n"
                            break
                        
                        elif event["type"] == "error":
                            data = json.dumps({
                                "token": "",
                                "done": True,
                                "error": event.get("error", "Unknown error"),
                                "success": False,
                            })
                            yield f"data: {data}\n\n"
                            break
                finally:
                    if not task.done():
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass
            
            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )
        
        @self._app.get("/status", response_model=StatusResponse, dependencies=[Depends(self._verify_api_key)])
        async def status():
            """Get system status."""
            if not self.engine:
                return StatusResponse(version="2.7.8")
            
            try:
                status_data = self.engine.get_status()
                
                # Count tools
                try:
                    from src.tool_framework import get_tool_registry
                    registry = get_tool_registry()
                    tool_count = len(registry.list_tools())
                except Exception:
                    tool_count = 0
                
                # Count conversations
                conv_count = 0
                if hasattr(self.engine, 'conversation_manager') and self.engine.conversation_manager:
                    conv_count = self.engine.conversation_manager.get_stats().get('total_conversations', 0)
                
                return StatusResponse(
                    version=status_data.get('version', '2.7.8'),
                    model=status_data.get('model', ''),
                    vision_model=status_data.get('vision_model', ''),
                    secondary_model=status_data.get('secondary_model', ''),
                    ollama_available=status_data.get('ollama_available', False),
                    ollama_models=status_data.get('ollama_models', []),
                    total_tools=tool_count,
                    total_agents=12,  # Built-in agents
                    total_conversations=conv_count,
                )
            except Exception as e:
                logger.error(f"API status error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self._app.get("/agents", response_model=List[AgentInfo], dependencies=[Depends(self._verify_api_key)])
        async def agents():
            """List all agents."""
            agents_list = []
            
            # Built-in agents
            try:
                from src.orchestrator import AGENT_CAPABILITIES, AgentRole
                for role in AgentRole:
                    agents_list.append(AgentInfo(
                        name=role.value,
                        role=role.value,
                        capabilities=AGENT_CAPABILITIES.get(role, []),
                        description=f"Built-in {role.value} agent",
                        enabled=True,
                    ))
            except Exception as e:
                logger.warning(f"Failed to list built-in agents: {e}")
            
            # Custom agents
            try:
                from src.custom_agents import get_custom_agent_registry
                registry = get_custom_agent_registry()
                for custom in registry.list_enabled():
                    agents_list.append(AgentInfo(
                        name=custom.name,
                        role=custom.role,
                        capabilities=custom.capabilities,
                        description=custom.description,
                        enabled=custom.enabled,
                    ))
            except Exception as e:
                logger.warning(f"Failed to list custom agents: {e}")
            
            return agents_list
        
        @self._app.get("/tools", response_model=List[ToolInfo], dependencies=[Depends(self._verify_api_key)])
        async def tools():
            """List available tools."""
            tools_list = []
            
            try:
                from src.tool_framework import get_tool_registry
                registry = get_tool_registry()
                for tool in registry.list_tools():
                    tools_list.append(ToolInfo(
                        name=tool.name,
                        description=tool.description,
                        permission=tool.permission.value,
                        category=tool.category.value,
                    ))
            except Exception as e:
                logger.warning(f"Failed to list tools: {e}")
            
            return tools_list
        
        @self._app.get("/conversations", response_model=List[ConversationInfo], dependencies=[Depends(self._verify_api_key)])
        async def conversations():
            """List conversation history."""
            if not self.engine or not hasattr(self.engine, 'conversation_manager') or not self.engine.conversation_manager:
                return []
            
            try:
                convs = self.engine.conversation_manager.list_conversations(limit=50)
                return [
                    ConversationInfo(
                        id=c.id,
                        name=c.name,
                        created_at=c.created_at,
                        updated_at=c.updated_at,
                        turn_count=c.turn_count,
                        tags=c.tags,
                    )
                    for c in convs
                ]
            except Exception as e:
                logger.error(f"API conversations error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self._app.post("/conversations", dependencies=[Depends(self._verify_api_key)])
        async def create_conversation(name: Optional[str] = None):
            """Create a new conversation."""
            if not self.engine or not hasattr(self.engine, 'conversation_manager') or not self.engine.conversation_manager:
                raise HTTPException(status_code=503, detail="Conversation manager not available")
            
            try:
                conv = self.engine.conversation_manager.create_conversation(name=name)
                return {"id": conv.id, "name": conv.name, "created_at": conv.created_at}
            except Exception as e:
                logger.error(f"API create conversation error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self._app.get("/models", dependencies=[Depends(self._verify_api_key)])
        async def models():
            """List available Ollama models."""
            if not self.engine:
                return {"models": []}
            
            try:
                status = self.engine.get_status()
                return {
                    "models": status.get('ollama_models', []),
                    "selected": status.get('model', ''),
                    "vision_model": status.get('vision_model', ''),
                    "secondary_model": status.get('secondary_model', ''),
                }
            except Exception as e:
                logger.error(f"API models error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self._app.get("/metrics", dependencies=[Depends(self._verify_api_key)])
        async def metrics(hours: Optional[int] = None):
            """Get performance metrics and analytics."""
            try:
                from src.metrics import get_metrics_collector
                collector = get_metrics_collector()
                snapshot = collector.get_snapshot(hours=hours)
                
                return {
                    "requests_total": snapshot.requests_total,
                    "requests_success": snapshot.requests_success,
                    "requests_failed": snapshot.requests_failed,
                    "avg_latency_ms": round(snapshot.avg_latency_ms, 2),
                    "min_latency_ms": round(snapshot.min_latency_ms, 2),
                    "max_latency_ms": round(snapshot.max_latency_ms, 2),
                    "tokens_generated": snapshot.tokens_generated,
                    "tokens_per_second": round(snapshot.tokens_per_second, 2),
                    "model_usage": snapshot.model_usage,
                    "intent_distribution": snapshot.intent_distribution,
                    "processing_paths": snapshot.processing_paths,
                    "hourly_requests": snapshot.hourly_requests,
                    "daily_requests": snapshot.daily_requests,
                    "uptime_seconds": round(collector.get_uptime_seconds(), 0),
                }
            except Exception as e:
                logger.error(f"API metrics error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self._app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """Bidirectional WebSocket for real-time AI chat."""
            await websocket.accept()
            logger.info(f"WebSocket client connected: {websocket.client}")
            
            try:
                while True:
                    # Receive message from client
                    data = await websocket.receive_text()
                    message = json.loads(data)
                    
                    prompt = message.get("prompt", "")
                    intent = message.get("intent", "chat")
                    streaming = message.get("streaming", True)
                    
                    if not prompt:
                        await websocket.send_json({"error": "Missing prompt"})
                        continue
                    
                    if not self.engine:
                        await websocket.send_json({"error": "Engine not initialized"})
                        continue
                    
                    if streaming:
                        # Stream tokens via WebSocket
                        tokens = []
                        
                        def token_callback(token: str) -> None:
                            tokens.append(token)
                        
                        try:
                            response = await self.engine.process(
                                prompt=prompt,
                                intent=intent,
                                streaming=True,
                                callback=token_callback,
                            )
                            
                            await websocket.send_json({
                                "type": "complete",
                                "text": response.text,
                                "model_used": getattr(response, 'model_used', ''),
                                "success": response.success,
                            })
                        except Exception as e:
                            logger.error(f"WebSocket stream error: {e}")
                            await websocket.send_json({"error": str(e)})
                    else:
                        # Non-streaming response
                        try:
                            response = await self.engine.process(
                                prompt=prompt,
                                intent=intent,
                            )
                            
                            await websocket.send_json({
                                "type": "response",
                                "text": response.text,
                                "model_used": getattr(response, 'model_used', ''),
                                "success": response.success,
                            })
                        except Exception as e:
                            logger.error(f"WebSocket process error: {e}")
                            await websocket.send_json({"error": str(e)})
            
            except WebSocketDisconnect:
                logger.info(f"WebSocket client disconnected: {websocket.client}")
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                try:
                    await websocket.close()
                except Exception:
                    pass
    
    def start(self) -> bool:
        """Start the API server in a background thread."""
        if not FASTAPI_AVAILABLE:
            logger.error("FastAPI not available - cannot start API server")
            return False
        
        if self._running:
            logger.info("API server already running")
            return True
        
        try:
            self._server_thread = threading.Thread(
                target=self._run_server,
                daemon=True,
            )
            self._server_thread.start()
            self._running = True
            logger.info(f"API server started on http://{self.host}:{self.port}")
            if self.api_key:
                logger.info("API authentication enabled")
            else:
                logger.info("API authentication disabled (no api_key configured)")
            logger.info(f"API docs available at http://{self.host}:{self.port}/docs")
            return True
        except Exception as e:
            logger.error(f"Failed to start API server: {e}")
            return False
    
    def _run_server(self):
        """Run the uvicorn server."""
        uvicorn.run(self._app, host=self.host, port=self.port, log_level="warning")
    
    def stop(self):
        """Stop the API server."""
        self._running = False
        logger.info("API server stopped")
    
    @property
    def is_running(self) -> bool:
        return self._running
    
    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"


def create_api_server(engine=None, host: str = "0.0.0.0", port: int = 8080, api_key: Optional[str] = None) -> CrackedCodeAPI:
    """Create a CrackedCodeAPI instance."""
    return CrackedCodeAPI(engine=engine, host=host, port=port, api_key=api_key)


# ── CLI Entry Point ────────────────────────────────────────────────────────

if __name__ == "__main__":
    from src.engine import CrackedCodeEngine
    
    engine = CrackedCodeEngine()
    api_key = engine.config.get("api_key") if hasattr(engine, 'config') else None
    api = create_api_server(engine=engine, api_key=api_key)
    
    print(f"Starting CrackedCode API Server v2.7.8")
    print(f"URL: {api.url}")
    print(f"Docs: {api.url}/docs")
    if api.api_key:
        print("Auth: API key required (X-API-Key header)")
    else:
        print("Auth: None (set api_key in config.json to enable)")
    print(f"Press Ctrl+C to stop")
    
    api.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        api.stop()
        print("\nAPI server stopped")
