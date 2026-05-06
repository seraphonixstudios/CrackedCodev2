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
    from fastapi import FastAPI, HTTPException, Depends, Security, WebSocket, WebSocketDisconnect, UploadFile
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import StreamingResponse, FileResponse
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


class GitHubReviewRequest(BaseModel):
    repo: str
    pr_number: int
    post_comment: bool = False


class GitHubIssueRequest(BaseModel):
    repo: str
    issue_number: int


class GitHubReviewResponse(BaseModel):
    repo: str
    pr_number: int
    title: str
    author: str
    files_changed: int
    security_issues_count: int
    code_issues_count: int
    summary: str
    verdict: str
    confidence: float


class GitHubIssueResponse(BaseModel):
    repo: str
    issue_number: int
    title: str
    summary: str
    suggested_fix: str
    related_files: List[str]
    confidence: float


class CustomToolInfo(BaseModel):
    name: str
    description: str = ""
    version: str = "1.0"
    permission: str = "read"
    category: str = "custom"
    parameters: List[Dict[str, Any]] = []
    examples: List[str] = []
    enabled: bool = True
    author: str = ""
    tags: List[str] = []


class CustomToolExecuteRequest(BaseModel):
    name: str
    parameters: Dict[str, Any] = {}


class CustomToolExecuteResponse(BaseModel):
    success: bool
    tool: str
    results: List[Dict[str, Any]] = []
    error: str = ""


class WorkflowExecuteRequest(BaseModel):
    name: str
    context: Dict[str, Any] = {}


class WorkflowExecuteResponse(BaseModel):
    success: bool
    workflow: str
    steps: List[Dict[str, Any]] = []
    duration: float = 0.0
    error: str = ""


class DebateRequest(BaseModel):
    topic: str
    agents: List[str] = ["architect", "security", "coder"]
    rounds: int = 3
    context: Dict[str, Any] = {}


class DebateResponse(BaseModel):
    topic: str
    consensus: str = ""
    consensus_score: float = 0.0
    action_items: List[str] = []
    duration: float = 0.0


class ReviewRequest(BaseModel):
    commit: str = "HEAD"
    repo_path: str = "."
    files: Optional[List[str]] = None


class ReviewResponse(BaseModel):
    commit: str
    verdict: str
    score: float
    issues_count: int
    summary: str


class DocumentUploadResponse(BaseModel):
    success: bool
    document_id: str = ""
    title: str = ""
    chunks: int = 0
    error: str = ""


class FinetuneRequest(BaseModel):
    model_name: str
    base_model: str = "qwen3:8b"
    source: str = "conversations"  # conversations, codebase
    system_prompt: str = ""


class FinetuneResponse(BaseModel):
    success: bool
    job_id: str = ""
    status: str = ""
    error: str = ""


class BenchmarkRunRequest(BaseModel):
    name: str
    model: Optional[str] = None


class BenchmarkRunResponse(BaseModel):
    name: str
    score: float
    passed: int
    failed: int
    total: int
    duration: float
    details: List[Dict[str, Any]] = []


class HealingWatchRequest(BaseModel):
    log_file: str
    auto_fix: bool = False


class HealingFixResponse(BaseModel):
    success: bool
    error_detected: str = ""
    fix_applied: bool = False
    fix_diff: str = ""
    tests_passed: bool = False


class AgentMemoryStoreRequest(BaseModel):
    agent: str
    category: str = "fact"
    content: Dict[str, Any]
    importance: float = 1.0
    confidence: float = 1.0
    tags: List[str] = []


class AgentMemoryQueryRequest(BaseModel):
    agent: str
    query: str = ""
    category: Optional[str] = None
    limit: int = 10


class AgentMemoryResponse(BaseModel):
    success: bool
    entries: List[Dict[str, Any]] = []
    count: int = 0
    error: str = ""


# ── Rate Limiting ──────────────────────────────────────────────────────────

class RateLimiter:
    """Simple in-memory rate limiter."""
    
    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: Dict[str, List[float]] = {}
        self._lock = threading.Lock()
    
    def is_allowed(self, key: str) -> bool:
        """Check if a request is allowed for the given key."""
        now = time.time()
        with self._lock:
            if key not in self._requests:
                self._requests[key] = []
            
            # Remove old requests outside the window
            self._requests[key] = [
                ts for ts in self._requests[key]
                if now - ts < self.window_seconds
            ]
            
            if len(self._requests[key]) < self.max_requests:
                self._requests[key].append(now)
                return True
            
            return False
    
    def get_remaining(self, key: str) -> int:
        """Get remaining requests for the given key."""
        now = time.time()
        with self._lock:
            if key not in self._requests:
                return self.max_requests
            
            self._requests[key] = [
                ts for ts in self._requests[key]
                if now - ts < self.window_seconds
            ]
            
            return max(0, self.max_requests - len(self._requests[key]))
    
    def get_reset_time(self, key: str) -> float:
        """Get time until rate limit resets."""
        now = time.time()
        with self._lock:
            if key not in self._requests or not self._requests[key]:
                return 0.0
            
            oldest = min(self._requests[key])
            reset = oldest + self.window_seconds - now
            return max(0.0, reset)


# ── API Server ─────────────────────────────────────────────────────────────

class CrackedCodeAPI:
    """REST API server for CrackedCode."""
    
    def __init__(self, engine=None, host: str = "0.0.0.0", port: int = 8080, api_key: Optional[str] = None,
                 rate_limit_enabled: bool = True, rate_limit_max: int = 60, rate_limit_window: int = 60):
        self.engine = engine
        self.host = host
        self.port = port
        self.api_key = api_key
        self.rate_limit_enabled = rate_limit_enabled
        self.rate_limiter = RateLimiter(max_requests=rate_limit_max, window_seconds=rate_limit_window) if rate_limit_enabled else None
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
            version="2.9.2",
        )
        
        # CORS
        self._app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Rate limiting middleware
        if self.rate_limit_enabled and self.rate_limiter:
            @self._app.middleware("http")
            async def rate_limit_middleware(request, call_next):
                """Apply rate limiting to all requests."""
                client_ip = request.client.host if request.client else "unknown"
                api_key = request.headers.get("X-API-Key", "")
                limit_key = f"{client_ip}:{api_key}"
                
                if not self.rate_limiter.is_allowed(limit_key):
                    remaining = self.rate_limiter.get_remaining(limit_key)
                    reset_time = self.rate_limiter.get_reset_time(limit_key)
                    
                    raise HTTPException(
                        status_code=429,
                        detail="Rate limit exceeded. Try again later.",
                        headers={
                            "X-RateLimit-Limit": str(self.rate_limiter.max_requests),
                            "X-RateLimit-Remaining": str(remaining),
                            "X-RateLimit-Reset": str(int(reset_time)),
                            "Retry-After": str(int(reset_time)),
                        },
                    )
                
                response = await call_next(request)
                
                # Add rate limit headers
                remaining = self.rate_limiter.get_remaining(limit_key)
                reset_time = self.rate_limiter.get_reset_time(limit_key)
                response.headers["X-RateLimit-Limit"] = str(self.rate_limiter.max_requests)
                response.headers["X-RateLimit-Remaining"] = str(remaining)
                response.headers["X-RateLimit-Reset"] = str(int(reset_time))
                
                return response
        
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
                "version": "2.9.2",
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
                    "/github/review-pr",
                    "/github/analyze-issue",
                    "/github/repos",
                    "/custom-tools",
                    "/custom-tools/execute",
                    "/workflows",
                    "/workflows/execute",
                    "/debate",
                    "/review",
                    "/knowledge/upload",
                    "/knowledge/search",
                    "/knowledge/documents",
                    "/finetune",
                    "/finetune/jobs",
                    "/benchmarks",
                    "/benchmarks/run",
                    "/benchmarks/history",
                    "/healing/watch",
                    "/healing/status",
                    "/healing/fix",
                    "/healing/fixes",
                    "/agent-memory/agents",
                    "/agent-memory/{agent}/profile",
                    "/agent-memory/{agent}/remember",
                    "/agent-memory/{agent}/recall",
                    "/agent-memory/{agent}/summarize",
                    "/agent-memory/stats",
                    "/export",
                    "/import",
                    "/export/items",
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
                return StatusResponse(version="2.9.2")
            
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
                    version=status_data.get('version', '2.9.2'),
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
        
        @self._app.post("/github/review-pr", response_model=GitHubReviewResponse, dependencies=[Depends(self._verify_api_key)])
        async def github_review_pr(request: GitHubReviewRequest):
            """Review a GitHub pull request using AI analysis."""
            try:
                from src.github_integration import create_github_client
                
                token = None
                if self.engine and hasattr(self.engine, 'config'):
                    token = self.engine.config.get("github", {}).get("token")
                
                gh = create_github_client(token=token)
                review = gh.review_pr(
                    repo=request.repo,
                    pr_number=request.pr_number,
                    engine=self.engine,
                    post_comment=request.post_comment,
                )
                
                return GitHubReviewResponse(
                    repo=review.repo,
                    pr_number=review.pr_number,
                    title=review.title,
                    author=review.author,
                    files_changed=review.files_changed,
                    security_issues_count=len(review.security_issues),
                    code_issues_count=len(review.code_issues),
                    summary=review.summary,
                    verdict=review.overall_verdict,
                    confidence=review.confidence,
                )
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            except Exception as e:
                logger.error(f"GitHub review error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self._app.post("/github/analyze-issue", response_model=GitHubIssueResponse, dependencies=[Depends(self._verify_api_key)])
        async def github_analyze_issue(request: GitHubIssueRequest):
            """Analyze a GitHub issue and suggest fixes."""
            try:
                from src.github_integration import create_github_client
                
                token = None
                if self.engine and hasattr(self.engine, 'config'):
                    token = self.engine.config.get("github", {}).get("token")
                
                gh = create_github_client(token=token)
                analysis = gh.analyze_issue(
                    repo=request.repo,
                    issue_number=request.issue_number,
                    engine=self.engine,
                )
                
                return GitHubIssueResponse(
                    repo=analysis.repo,
                    issue_number=analysis.issue_number,
                    title=analysis.title,
                    summary=analysis.summary,
                    suggested_fix=analysis.suggested_fix,
                    related_files=analysis.related_files,
                    confidence=analysis.confidence,
                )
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            except Exception as e:
                logger.error(f"GitHub issue analysis error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self._app.get("/github/repos", dependencies=[Depends(self._verify_api_key)])
        async def github_repos(username: str):
            """List repositories for a GitHub user."""
            try:
                from src.github_integration import create_github_client
                
                token = None
                if self.engine and hasattr(self.engine, 'config'):
                    token = self.engine.config.get("github", {}).get("token")
                
                gh = create_github_client(token=token)
                repos = gh.list_repos(username)
                
                return {
                    "username": username,
                    "repos": [{"name": r.get("name"), "url": r.get("html_url")} for r in repos],
                }
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            except Exception as e:
                logger.error(f"GitHub repos error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self._app.get("/custom-tools", dependencies=[Depends(self._verify_api_key)])
        async def list_custom_tools():
            """List all custom tools."""
            try:
                from src.custom_tools import get_custom_tool_registry
                registry = get_custom_tool_registry()
                tools = registry.list_tools()
                
                return [
                    {
                        "name": t.name,
                        "description": t.description,
                        "version": t.version,
                        "permission": t.permission,
                        "category": t.category,
                        "parameters": [{"name": p.name, "type": p.type, "required": p.required, "description": p.description} for p in t.parameters],
                        "examples": t.examples,
                        "enabled": t.enabled,
                        "author": t.author,
                        "tags": t.tags,
                    }
                    for t in tools
                ]
            except Exception as e:
                logger.error(f"Custom tools list error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self._app.post("/custom-tools/execute", response_model=CustomToolExecuteResponse, dependencies=[Depends(self._verify_api_key)])
        async def execute_custom_tool(request: CustomToolExecuteRequest):
            """Execute a custom tool."""
            try:
                from src.custom_tools import get_custom_tool_registry
                registry = get_custom_tool_registry()
                result = registry.execute(request.name, request.parameters)
                
                return CustomToolExecuteResponse(
                    success=result.get("success", False),
                    tool=result.get("tool", request.name),
                    results=result.get("results", []),
                    error=result.get("error", ""),
                )
            except Exception as e:
                logger.error(f"Custom tool execution error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self._app.get("/workflows", dependencies=[Depends(self._verify_api_key)])
        async def list_workflows():
            """List all available workflows."""
            try:
                from src.workflows import get_workflow_engine
                engine = get_workflow_engine()
                workflows = engine.list_workflows()
                
                return [
                    {
                        "name": w.name,
                        "description": w.description,
                        "version": w.version,
                        "steps": len(w.steps),
                        "triggers": [t.type for t in w.triggers],
                        "enabled": w.enabled,
                        "tags": w.tags,
                    }
                    for w in workflows
                ]
            except Exception as e:
                logger.error(f"Workflow list error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self._app.post("/workflows/execute", response_model=WorkflowExecuteResponse, dependencies=[Depends(self._verify_api_key)])
        async def execute_workflow(request: WorkflowExecuteRequest):
            """Execute a workflow."""
            try:
                from src.workflows import get_workflow_engine
                engine = get_workflow_engine()
                
                result = engine.execute(request.name, context=request.context)
                
                return WorkflowExecuteResponse(
                    success=result.success,
                    workflow=result.workflow,
                    steps=[
                        {
                            "name": s.step_name,
                            "status": s.status.value,
                            "error": s.error,
                            "duration": s.duration,
                        }
                        for s in result.steps
                    ],
                    duration=result.duration,
                    error="",
                )
            except Exception as e:
                logger.error(f"Workflow execution error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self._app.post("/debate", response_model=DebateResponse, dependencies=[Depends(self._verify_api_key)])
        async def run_debate(request: DebateRequest):
            """Run a multi-agent debate."""
            try:
                from src.agent_collaboration import get_agent_parliament
                parliament = get_agent_parliament(engine=self.engine)
                
                result = parliament.debate(
                    topic=request.topic,
                    agents=request.agents,
                    rounds=request.rounds,
                    context=request.context,
                )
                
                return DebateResponse(
                    topic=result.topic,
                    consensus=result.final_consensus,
                    consensus_score=result.consensus_score,
                    action_items=result.action_items,
                    duration=result.duration,
                )
            except Exception as e:
                logger.error(f"Debate error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self._app.post("/review", response_model=ReviewResponse, dependencies=[Depends(self._verify_api_key)])
        async def run_code_review(request: ReviewRequest):
            """Run automated code review."""
            try:
                from src.code_review_bot import get_review_bot
                bot = get_review_bot(engine=self.engine)
                
                report = bot.review_commit(
                    commit=request.commit,
                    repo_path=request.repo_path,
                    files=request.files,
                )
                
                return ReviewResponse(
                    commit=report.commit,
                    verdict=report.verdict,
                    score=report.score,
                    issues_count=len(report.issues),
                    summary=report.summary,
                )
            except Exception as e:
                logger.error(f"Code review error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self._app.post("/knowledge/upload", dependencies=[Depends(self._verify_api_key)])
        async def upload_document(file: UploadFile = None):
            """Upload a document to the knowledge base."""
            try:
                from src.knowledge_base import get_knowledge_base
                import tempfile
                
                if not file:
                    raise HTTPException(status_code=400, detail="No file provided")
                
                kb = get_knowledge_base()
                
                # Save uploaded file temporarily
                suffix = Path(file.filename).suffix
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                    content = await file.read()
                    tmp.write(content)
                    tmp_path = tmp.name
                
                # Upload to knowledge base
                doc = kb.upload_document(
                    tmp_path,
                    title=file.filename,
                )
                
                # Clean up temp file
                os.unlink(tmp_path)
                
                return DocumentUploadResponse(
                    success=True,
                    document_id=doc.id,
                    title=doc.title,
                    chunks=len(doc.chunks),
                )
            except Exception as e:
                logger.error(f"Document upload error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self._app.get("/knowledge/search", dependencies=[Depends(self._verify_api_key)])
        async def search_knowledge(query: str, top_k: int = 5):
            """Search the knowledge base."""
            try:
                from src.knowledge_base import get_knowledge_base
                kb = get_knowledge_base()
                
                results = kb.search(query, top_k=top_k)
                
                return {
                    "query": query,
                    "results": [
                        {
                            "document_id": r.document_id,
                            "title": r.title,
                            "content": r.content,
                            "score": r.score,
                        }
                        for r in results
                    ],
                }
            except Exception as e:
                logger.error(f"Knowledge search error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self._app.get("/knowledge/documents", dependencies=[Depends(self._verify_api_key)])
        async def list_documents():
            """List all documents in the knowledge base."""
            try:
                from src.knowledge_base import get_knowledge_base
                kb = get_knowledge_base()
                
                docs = kb.list_documents()
                
                return [
                    {
                        "id": d.id,
                        "title": d.title,
                        "type": d.content_type,
                        "chunks": len(d.chunks),
                        "uploaded_at": d.uploaded_at,
                        "metadata": d.metadata,
                    }
                    for d in docs
                ]
            except Exception as e:
                logger.error(f"Document list error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self._app.post("/finetune", response_model=FinetuneResponse, dependencies=[Depends(self._verify_api_key)])
        async def start_finetune(request: FinetuneRequest):
            """Start a model fine-tuning job."""
            try:
                from src.model_finetune import get_finetune_pipeline
                pipeline = get_finetune_pipeline()
                
                # Prepare dataset
                if request.source == "conversations":
                    dataset = pipeline.prepare_from_conversations(".crackedcode/memory")
                elif request.source == "codebase":
                    dataset = pipeline.prepare_from_codebase()
                else:
                    raise HTTPException(status_code=400, detail=f"Unknown source: {request.source}")
                
                # Export dataset
                dataset_path = pipeline.export_dataset(dataset, format="jsonl")
                
                # Start fine-tuning job
                job = pipeline.create_model(
                    model_name=request.model_name,
                    base_model=request.base_model,
                    dataset_path=dataset_path,
                    system_prompt=request.system_prompt or None,
                )
                
                return FinetuneResponse(
                    success=job.status == "completed",
                    job_id=job.id,
                    status=job.status,
                    error=job.error,
                )
            except Exception as e:
                logger.error(f"Fine-tuning error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self._app.get("/finetune/jobs", dependencies=[Depends(self._verify_api_key)])
        async def list_finetune_jobs():
            """List all fine-tuning jobs."""
            try:
                from src.model_finetune import get_finetune_pipeline
                pipeline = get_finetune_pipeline()
                
                jobs = pipeline.list_jobs()
                
                return [
                    {
                        "id": j.id,
                        "model_name": j.model_name,
                        "base_model": j.base_model,
                        "status": j.status,
                        "started_at": j.started_at,
                        "completed_at": j.completed_at,
                        "error": j.error,
                    }
                    for j in jobs
                ]
            except Exception as e:
                logger.error(f"Finetune jobs list error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self._app.get("/benchmarks", dependencies=[Depends(self._verify_api_key)])
        async def list_benchmarks():
            """List available benchmark suites."""
            try:
                from src.benchmarks import get_benchmark_runner
                runner = get_benchmark_runner()
                return {"benchmarks": runner.list_benchmarks()}
            except Exception as e:
                logger.error(f"Benchmark list error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self._app.post("/benchmarks/run", response_model=BenchmarkRunResponse, dependencies=[Depends(self._verify_api_key)])
        async def run_benchmark(request: BenchmarkRunRequest):
            """Run a benchmark suite."""
            try:
                from src.benchmarks import get_benchmark_runner
                from src.engine import CrackedCodeEngine
                
                runner = get_benchmark_runner()
                engine = self.engine or CrackedCodeEngine()
                
                report = runner.run(request.name, engine, model=request.model)
                
                return BenchmarkRunResponse(
                    name=report.name,
                    score=report.total_score,
                    passed=sum(1 for r in report.results if r.passed),
                    failed=sum(1 for r in report.results if not r.passed),
                    total=len(report.results),
                    duration=report.duration,
                    details=[
                        {
                            "case": r.case,
                            "category": r.category,
                            "passed": r.passed,
                            "score": r.score,
                            "duration": r.duration,
                        }
                        for r in report.results
                    ],
                )
            except Exception as e:
                logger.error(f"Benchmark run error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self._app.get("/benchmarks/history", dependencies=[Depends(self._verify_api_key)])
        async def get_benchmark_history(name: Optional[str] = None):
            """Get benchmark history."""
            try:
                from src.benchmarks import get_benchmark_runner
                runner = get_benchmark_runner()
                return {"history": runner.get_history(name)}
            except Exception as e:
                logger.error(f"Benchmark history error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self._app.post("/healing/watch", dependencies=[Depends(self._verify_api_key)])
        async def start_healing_watch(request: HealingWatchRequest):
            """Start watching a log file for errors."""
            try:
                from src.self_healing import get_healing_agent
                from src.engine import CrackedCodeEngine
                
                agent = get_healing_agent(
                    engine=self.engine or CrackedCodeEngine(),
                )
                success = agent.watch(request.log_file, auto_fix=request.auto_fix)
                
                return {"success": success, "status": agent.get_status()}
            except Exception as e:
                logger.error(f"Healing watch error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self._app.get("/healing/status", dependencies=[Depends(self._verify_api_key)])
        async def get_healing_status():
            """Get self-healing agent status."""
            try:
                from src.self_healing import get_healing_agent
                agent = get_healing_agent()
                return agent.get_status()
            except Exception as e:
                logger.error(f"Healing status error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self._app.post("/healing/fix", response_model=HealingFixResponse, dependencies=[Depends(self._verify_api_key)])
        async def fix_last_error():
            """Attempt to fix the last detected error."""
            try:
                from src.self_healing import get_healing_agent
                from src.engine import CrackedCodeEngine
                
                agent = get_healing_agent(engine=self.engine or CrackedCodeEngine())
                
                errors = agent.get_errors()
                if not errors:
                    return HealingFixResponse(success=False, error_detected="No errors to fix")
                
                fix = agent.fix_error(errors[-1])
                
                if fix:
                    return HealingFixResponse(
                        success=True,
                        error_detected=errors[-1].error_type,
                        fix_applied=True,
                        fix_diff=fix.diff,
                        tests_passed=fix.tests_passed,
                    )
                else:
                    return HealingFixResponse(success=False, error_detected=errors[-1].error_type)
            except Exception as e:
                logger.error(f"Healing fix error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self._app.get("/healing/fixes", dependencies=[Depends(self._verify_api_key)])
        async def list_healing_fixes():
            """List all applied fixes."""
            try:
                from src.self_healing import get_healing_agent
                agent = get_healing_agent()
                fixes = agent.get_fixes()
                
                return {
                    "fixes": [
                        {
                            "id": f.id,
                            "error_id": f.error_id,
                            "file": f.file,
                            "tests_passed": f.tests_passed,
                            "applied_at": f.applied_at,
                            "reverted": f.reverted,
                        }
                        for f in fixes
                    ]
                }
            except Exception as e:
                logger.error(f"Healing fixes list error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self._app.get("/agent-memory/agents", dependencies=[Depends(self._verify_api_key)])
        async def list_memory_agents():
            """List all agents with memories."""
            try:
                from src.agent_memory import get_agent_memory_system
                memory = get_agent_memory_system()
                return {"agents": memory.list_agents()}
            except Exception as e:
                logger.error(f"Agent memory list error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self._app.get("/agent-memory/{agent}/profile", dependencies=[Depends(self._verify_api_key)])
        async def get_agent_profile(agent: str):
            """Get an agent's memory profile."""
            try:
                from src.agent_memory import get_agent_memory_system
                memory = get_agent_memory_system()
                profile = memory.get_profile(agent)
                
                if not profile:
                    raise HTTPException(status_code=404, detail=f"Agent not found: {agent}")
                
                return {
                    "agent": profile.agent,
                    "total_interactions": profile.total_interactions,
                    "success_rate": profile.success_rate,
                    "expertise_areas": profile.expertise_areas,
                    "preferred_tools": profile.preferred_tools,
                    "common_mistakes": profile.common_mistakes,
                    "summary": profile.summary,
                    "last_summarized": profile.last_summarized,
                }
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Agent profile error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self._app.post("/agent-memory/{agent}/remember", dependencies=[Depends(self._verify_api_key)])
        async def store_agent_memory(agent: str, request: AgentMemoryStoreRequest):
            """Store a memory for an agent."""
            try:
                from src.agent_memory import get_agent_memory_system
                memory = get_agent_memory_system()
                
                entry = memory.remember(
                    agent=agent,
                    category=request.category,
                    content=request.content,
                    importance=request.importance,
                    confidence=request.confidence,
                    tags=request.tags,
                )
                
                return {
                    "success": True,
                    "entry_id": entry.id,
                    "agent": entry.agent,
                    "category": entry.category,
                    "timestamp": entry.timestamp,
                }
            except Exception as e:
                logger.error(f"Store agent memory error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self._app.post("/agent-memory/{agent}/recall", response_model=AgentMemoryResponse, dependencies=[Depends(self._verify_api_key)])
        async def recall_agent_memory(agent: str, request: AgentMemoryQueryRequest):
            """Recall memories for an agent."""
            try:
                from src.agent_memory import get_agent_memory_system
                memory = get_agent_memory_system()
                
                entries = memory.recall(
                    agent=agent,
                    query=request.query,
                    category=request.category,
                    limit=request.limit,
                )
                
                return AgentMemoryResponse(
                    success=True,
                    entries=[
                        {
                            "id": e.id,
                            "category": e.category,
                            "content": e.content,
                            "importance": e.importance,
                            "confidence": e.confidence,
                            "timestamp": e.timestamp,
                            "tags": e.tags,
                        }
                        for e in entries
                    ],
                    count=len(entries),
                )
            except Exception as e:
                logger.error(f"Recall agent memory error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self._app.get("/agent-memory/{agent}/summarize", dependencies=[Depends(self._verify_api_key)])
        async def summarize_agent_memory(agent: str):
            """Generate a summary of an agent's experience."""
            try:
                from src.agent_memory import get_agent_memory_system
                memory = get_agent_memory_system()
                
                summary = memory.summarize(agent, engine=self.engine)
                
                return {
                    "agent": agent,
                    "summary": summary,
                }
            except Exception as e:
                logger.error(f"Summarize agent memory error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self._app.get("/agent-memory/stats", dependencies=[Depends(self._verify_api_key)])
        async def get_agent_memory_stats():
            """Get agent memory system statistics."""
            try:
                from src.agent_memory import get_agent_memory_system
                memory = get_agent_memory_system()
                return memory.get_stats()
            except Exception as e:
                logger.error(f"Agent memory stats error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self._app.delete("/agent-memory/{agent}/entries/{entry_id}", dependencies=[Depends(self._verify_api_key)])
        async def forget_agent_memory(agent: str, entry_id: str):
            """Remove a specific memory entry."""
            try:
                from src.agent_memory import get_agent_memory_system
                memory = get_agent_memory_system()
                
                success = memory.forget(agent, entry_id)
                if not success:
                    raise HTTPException(status_code=404, detail="Entry not found")
                
                return {"success": True, "deleted": entry_id}
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Forget agent memory error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self._app.get("/export", dependencies=[Depends(self._verify_api_key)])
        async def export_data(items: Optional[str] = None):
            """Export all CrackedCode data to a ZIP archive."""
            try:
                from src.import_export import create_import_export_manager
                import tempfile
                
                mgr = create_import_export_manager()
                item_list = items.split(",") if items else None
                
                with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
                    result = mgr.export_all(tmp.name, items=item_list)
                
                if result["success"]:
                    from fastapi.responses import FileResponse
                    return FileResponse(
                        result["path"],
                        filename=f"crackedcode-backup-{int(time.time())}.zip",
                        media_type="application/zip",
                    )
                else:
                    raise HTTPException(status_code=500, detail=result.get("error", "Export failed"))
            except Exception as e:
                logger.error(f"Export error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self._app.post("/import", dependencies=[Depends(self._verify_api_key)])
        async def import_data(file: UploadFile = None, overwrite: bool = False):
            """Import data from a ZIP archive."""
            try:
                from src.import_export import create_import_export_manager
                import tempfile
                
                if not file:
                    raise HTTPException(status_code=400, detail="No file provided")
                
                mgr = create_import_export_manager()
                
                with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
                    content = await file.read()
                    tmp.write(content)
                    tmp.flush()
                    result = mgr.import_all(tmp.name, overwrite=overwrite)
                
                return result
            except Exception as e:
                logger.error(f"Import error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self._app.get("/export/items", dependencies=[Depends(self._verify_api_key)])
        async def export_items():
            """List exportable items."""
            try:
                from src.import_export import create_import_export_manager
                mgr = create_import_export_manager()
                return {"items": mgr.get_exportable_items()}
            except Exception as e:
                logger.error(f"Export items error: {e}")
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
    
    print(f"Starting CrackedCode API Server v2.9.2")
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
