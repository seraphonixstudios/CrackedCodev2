"""CrackedCode Python SDK v2.9.1 - Official client for the CrackedCode API.

Provides a clean, typed interface to all API endpoints with automatic
retries, error handling, and both sync/async support.

Installation:
    pip install crackedcode  # (when published)

Usage:
    from crackedcode import Client

    client = Client(api_key="your-key", base_url="http://localhost:8080")

    # Chat
    response = client.chat("Write a function to sort a list")
    print(response.text)

    # Code review
    review = client.review.commit("HEAD", repo_path=".")
    print(review.verdict, review.score)

    # Workflows
    result = client.workflows.run("security_audit", {"repo": "myapp"})

    # Agent collaboration
    debate = client.agents.debate("Should we use microservices?")
    print(debate.consensus)

    # Knowledge base
    doc = client.knowledge.upload("design_spec.pdf")
    results = client.knowledge.search("authentication flow")

    # Benchmarks
    report = client.benchmarks.run("humaneval")
    print(report.score)

    # Self-healing
    client.healing.watch("app.log")
    fix = client.healing.fix_last_error()
"""

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin

import requests

from src.logger_config import get_logger

logger = get_logger("SDK")


# ── Response Models ────────────────────────────────────────────────────────

@dataclass
class ChatResponse:
    """Response from a chat request."""
    text: str
    model_used: str = ""
    intent: str = ""
    success: bool = True
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass
class ReviewResponse:
    """Response from a code review request."""
    commit: str
    verdict: str
    score: float
    issues_count: int
    summary: str
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass
class WorkflowResponse:
    """Response from a workflow execution."""
    success: bool
    workflow: str
    steps: List[Dict[str, Any]] = field(default_factory=list)
    duration: float = 0.0
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass
class DebateResponse:
    """Response from a multi-agent debate."""
    topic: str
    consensus: str
    consensus_score: float
    action_items: List[str] = field(default_factory=list)
    duration: float = 0.0
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass
class DocumentResponse:
    """Response from a document upload."""
    success: bool
    document_id: str = ""
    title: str = ""
    chunks: int = 0
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass
class BenchmarkResponse:
    """Response from a benchmark run."""
    name: str
    score: float
    passed: int
    failed: int
    total: int
    duration: float
    details: List[Dict[str, Any]] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass
class HealingResponse:
    """Response from a self-healing operation."""
    success: bool
    error_detected: str = ""
    fix_applied: bool = False
    fix_diff: str = ""
    tests_passed: bool = False
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)


# ── Client ─────────────────────────────────────────────────────────────────

class Client:
    """Official CrackedCode API client."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "http://localhost:8080",
        timeout: int = 120,
        max_retries: int = 3,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()

        if api_key:
            self.session.headers["X-API-Key"] = api_key

        # Sub-clients for different API areas
        self.workflows = _WorkflowClient(self)
        self.agents = _AgentClient(self)
        self.knowledge = _KnowledgeClient(self)
        self.benchmarks = _BenchmarkClient(self)
        self.healing = _HealingClient(self)
        self.review = _ReviewClient(self)
        self.tools = _ToolClient(self)

    def _request(
        self,
        method: str,
        path: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Make an HTTP request with retries."""
        url = urljoin(self.base_url + "/", path.lstrip("/"))
        kwargs.setdefault("timeout", self.timeout)

        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = self.session.request(method, url, **kwargs)
                response.raise_for_status()
                return response.json()
            except requests.HTTPError as e:
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 2 ** attempt))
                    logger.warning(f"Rate limited, retrying in {retry_after}s")
                    time.sleep(retry_after)
                    continue
                raise
            except (requests.ConnectionError, requests.Timeout) as e:
                last_error = e
                wait = 2 ** attempt
                logger.warning(f"Request failed, retrying in {wait}s: {e}")
                time.sleep(wait)

        raise last_error or requests.RequestException("Max retries exceeded")

    # ── Core API ───────────────────────────────────────────────────────────

    def chat(
        self,
        prompt: str,
        intent: str = "chat",
        streaming: bool = False,
        system_prompt: str = "",
    ) -> ChatResponse:
        """Send a chat message to CrackedCode."""
        payload = {
            "prompt": prompt,
            "intent": intent,
            "streaming": streaming,
        }
        if system_prompt:
            payload["system_prompt"] = system_prompt

        data = self._request("POST", "/process", json=payload)
        return ChatResponse(
            text=data.get("text", ""),
            model_used=data.get("model_used", ""),
            intent=data.get("intent", intent),
            success=data.get("success", True),
            raw=data,
        )

    def status(self) -> Dict[str, Any]:
        """Get system status."""
        return self._request("GET", "/status")

    def list_models(self) -> List[str]:
        """List available Ollama models."""
        data = self._request("GET", "/models")
        return data.get("models", [])

    def list_agents(self) -> List[Dict[str, Any]]:
        """List available agents."""
        data = self._request("GET", "/agents")
        return data.get("agents", [])

    def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools."""
        data = self._request("GET", "/tools")
        return data.get("tools", [])

    def get_metrics(self) -> Dict[str, Any]:
        """Get system metrics."""
        return self._request("GET", "/metrics")

    def export_data(self, items: Optional[List[str]] = None) -> bytes:
        """Export all CrackedCode data as a ZIP archive."""
        params = {}
        if items:
            params["items"] = ",".join(items)

        url = urljoin(self.base_url + "/", "export")
        response = self.session.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.content

    def import_data(self, file_path: str, overwrite: bool = False) -> Dict[str, Any]:
        """Import CrackedCode data from a ZIP archive."""
        with open(file_path, "rb") as f:
            files = {"file": f}
            data = {"overwrite": str(overwrite).lower()}
            return self._request("POST", "/import", files=files, data=data)


# ── Sub-clients ────────────────────────────────────────────────────────────

class _WorkflowClient:
    def __init__(self, client: Client):
        self._client = client

    def list(self) -> List[Dict[str, Any]]:
        """List all available workflows."""
        return self._client._request("GET", "/workflows")

    def run(self, name: str, context: Optional[Dict[str, Any]] = None) -> WorkflowResponse:
        """Execute a workflow."""
        payload = {"name": name, "context": context or {}}
        data = self._client._request("POST", "/workflows/execute", json=payload)
        return WorkflowResponse(
            success=data.get("success", False),
            workflow=data.get("workflow", name),
            steps=data.get("steps", []),
            duration=data.get("duration", 0.0),
            raw=data,
        )


class _AgentClient:
    def __init__(self, client: Client):
        self._client = client

    def debate(
        self,
        topic: str,
        agents: Optional[List[str]] = None,
        rounds: int = 3,
        context: Optional[Dict[str, Any]] = None,
    ) -> DebateResponse:
        """Run a multi-agent debate."""
        payload = {
            "topic": topic,
            "agents": agents or ["architect", "security", "coder"],
            "rounds": rounds,
            "context": context or {},
        }
        data = self._client._request("POST", "/debate", json=payload)
        return DebateResponse(
            topic=data.get("topic", topic),
            consensus=data.get("consensus", ""),
            consensus_score=data.get("consensus_score", 0.0),
            action_items=data.get("action_items", []),
            duration=data.get("duration", 0.0),
            raw=data,
        )


class _ReviewClient:
    def __init__(self, client: Client):
        self._client = client

    def commit(
        self,
        commit: str = "HEAD",
        repo_path: str = ".",
        files: Optional[List[str]] = None,
    ) -> ReviewResponse:
        """Run automated code review on a commit."""
        payload = {"commit": commit, "repo_path": repo_path}
        if files:
            payload["files"] = files

        data = self._client._request("POST", "/review", json=payload)
        return ReviewResponse(
            commit=data.get("commit", commit),
            verdict=data.get("verdict", "error"),
            score=data.get("score", 0.0),
            issues_count=data.get("issues_count", 0),
            summary=data.get("summary", ""),
            raw=data,
        )

    def pr(self, repo: str, pr_number: int) -> ReviewResponse:
        """Review a GitHub pull request (requires GitHub integration)."""
        # Use the review endpoint with special handling
        payload = {"commit": f"PR #{pr_number}", "repo_path": repo}
        data = self._client._request("POST", "/review", json=payload)
        return ReviewResponse(
            commit=data.get("commit", f"PR #{pr_number}"),
            verdict=data.get("verdict", "error"),
            score=data.get("score", 0.0),
            issues_count=data.get("issues_count", 0),
            summary=data.get("summary", ""),
            raw=data,
        )


class _KnowledgeClient:
    def __init__(self, client: Client):
        self._client = client

    def upload(self, file_path: str, title: Optional[str] = None) -> DocumentResponse:
        """Upload a document to the knowledge base."""
        with open(file_path, "rb") as f:
            files = {"file": f}
            data = self._client._request("POST", "/knowledge/upload", files=files)

        return DocumentResponse(
            success=data.get("success", False),
            document_id=data.get("document_id", ""),
            title=data.get("title", title or ""),
            chunks=data.get("chunks", 0),
            raw=data,
        )

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search the knowledge base."""
        params = {"query": query, "top_k": top_k}
        data = self._client._request("GET", "/knowledge/search", params=params)
        return data.get("results", [])

    def list_documents(self) -> List[Dict[str, Any]]:
        """List all documents in the knowledge base."""
        return self._client._request("GET", "/knowledge/documents")


class _BenchmarkClient:
    def __init__(self, client: Client):
        self._client = client

    def list(self) -> List[str]:
        """List available benchmark suites."""
        data = self._client._request("GET", "/benchmarks")
        return data.get("benchmarks", [])

    def run(self, name: str, model: Optional[str] = None) -> BenchmarkResponse:
        """Run a benchmark suite."""
        payload = {"name": name}
        if model:
            payload["model"] = model

        data = self._client._request("POST", "/benchmarks/run", json=payload)
        return BenchmarkResponse(
            name=data.get("name", name),
            score=data.get("score", 0.0),
            passed=data.get("passed", 0),
            failed=data.get("failed", 0),
            total=data.get("total", 0),
            duration=data.get("duration", 0.0),
            details=data.get("details", []),
            raw=data,
        )

    def history(self, name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get benchmark history."""
        params = {}
        if name:
            params["name"] = name

        data = self._client._request("GET", "/benchmarks/history", params=params)
        return data.get("history", [])


class _HealingClient:
    def __init__(self, client: Client):
        self._client = client

    def watch(self, log_file: str, auto_fix: bool = False) -> Dict[str, Any]:
        """Start watching a log file for errors."""
        payload = {"log_file": log_file, "auto_fix": auto_fix}
        return self._client._request("POST", "/healing/watch", json=payload)

    def status(self) -> Dict[str, Any]:
        """Get self-healing status."""
        return self._client._request("GET", "/healing/status")

    def fix_last_error(self) -> HealingResponse:
        """Attempt to fix the last detected error."""
        data = self._client._request("POST", "/healing/fix")
        return HealingResponse(
            success=data.get("success", False),
            error_detected=data.get("error_detected", ""),
            fix_applied=data.get("fix_applied", False),
            fix_diff=data.get("fix_diff", ""),
            tests_passed=data.get("tests_passed", False),
            raw=data,
        )

    def list_fixes(self) -> List[Dict[str, Any]]:
        """List all applied fixes."""
        data = self._client._request("GET", "/healing/fixes")
        return data.get("fixes", [])


class _ToolClient:
    def __init__(self, client: Client):
        self._client = client

    def list(self) -> List[Dict[str, Any]]:
        """List custom tools."""
        return self._client._request("GET", "/custom-tools")

    def execute(self, name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a custom tool."""
        payload = {"name": name, "parameters": parameters}
        return self._client._request("POST", "/custom-tools/execute", json=payload)


# ── Convenience functions ──────────────────────────────────────────────────

def create_client(
    api_key: Optional[str] = None,
    base_url: str = "http://localhost:8080",
) -> Client:
    """Create a new CrackedCode client."""
    return Client(api_key=api_key, base_url=base_url)
