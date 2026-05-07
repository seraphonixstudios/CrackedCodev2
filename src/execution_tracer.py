"""Execution Tracer v2.9.5 - Capture and replay every system decision.

Trace every engine call, agent decision, tool invocation, memory injection,
and reasoning step. Searchable, filterable, and replayable.

Usage:
    from src.execution_tracer import get_tracer
    tracer = get_tracer()
    
    # Start tracing
    with tracer.trace("engine.process", {"prompt": "hello"}):
        result = engine.process("hello")
    
    # Query traces
    traces = tracer.search(agent="security", since="1h")
    
    # Show tree view
    tracer.print_tree(trace_id="abc123")
    
    # Replay a trace
    tracer.replay(trace_id="abc123")
"""

import hashlib
import json
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from src.logger_config import get_logger

logger = get_logger("ExecutionTracer")


# ── Data Models ────────────────────────────────────────────────────────────

@dataclass
class TraceSpan:
    """A single span in an execution trace."""
    id: str
    parent_id: str = ""
    name: str = ""
    component: str = ""  # engine, agent, tool, memory, api, workflow
    agent: str = ""
    intent: str = ""
    model: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    duration_ms: float = 0.0
    input_data: Dict[str, Any] = field(default_factory=dict, repr=False)
    output_data: Dict[str, Any] = field(default_factory=dict, repr=False)
    context_before: str = ""
    context_after: str = ""
    reasoning: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    trace_id: str = ""


@dataclass
class ExecutionTrace:
    """A complete execution trace."""
    id: str
    root_span: str = ""
    spans: List[TraceSpan] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0
    total_duration_ms: float = 0.0
    success: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


# ── Execution Tracer ───────────────────────────────────────────────────────

class ExecutionTracer:
    """Capture and query execution traces."""
    
    ACTIVE_TRACES: Dict[str, "ExecutionTracer"] = {}
    
    def __init__(self, storage_dir: str = ".crackedcode/traces"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.traces: Dict[str, ExecutionTrace] = {}
        self.active_spans: Dict[str, TraceSpan] = {}
        self._load_recent()
    
    def _load_recent(self, max_age_hours: int = 24):
        """Load recent traces from disk."""
        cutoff = time.time() - (max_age_hours * 3600)
        for trace_file in self.storage_dir.glob("*.json"):
            try:
                mtime = trace_file.stat().st_mtime
                if mtime < cutoff:
                    continue
                with open(trace_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                trace = self._deserialize_trace(data)
                self.traces[trace.id] = trace
            except Exception as e:
                logger.debug(f"Failed to load trace {trace_file}: {e}")
    
    def _deserialize_trace(self, data: Dict[str, Any]) -> ExecutionTrace:
        """Deserialize a trace from JSON."""
        spans = [
            TraceSpan(
                id=s["id"],
                parent_id=s.get("parent_id", ""),
                name=s.get("name", ""),
                component=s.get("component", ""),
                agent=s.get("agent", ""),
                intent=s.get("intent", ""),
                model=s.get("model", ""),
                start_time=s.get("start_time", 0.0),
                end_time=s.get("end_time", 0.0),
                duration_ms=s.get("duration_ms", 0.0),
                input_data=s.get("input_data", {}),
                output_data=s.get("output_data", {}),
                context_before=s.get("context_before", ""),
                context_after=s.get("context_after", ""),
                reasoning=s.get("reasoning", []),
                errors=s.get("errors", []),
                tags=s.get("tags", []),
                trace_id=s.get("trace_id", ""),
            )
            for s in data.get("spans", [])
        ]
        return ExecutionTrace(
            id=data["id"],
            root_span=data.get("root_span", ""),
            spans=spans,
            start_time=data.get("start_time", 0.0),
            end_time=data.get("end_time", 0.0),
            total_duration_ms=data.get("total_duration_ms", 0.0),
            success=data.get("success", True),
            metadata=data.get("metadata", {}),
        )
    
    def _serialize_trace(self, trace: ExecutionTrace) -> Dict[str, Any]:
        """Serialize a trace to JSON."""
        return {
            "id": trace.id,
            "root_span": trace.root_span,
            "spans": [
                {
                    "id": s.id,
                    "parent_id": s.parent_id,
                    "name": s.name,
                    "component": s.component,
                    "agent": s.agent,
                    "intent": s.intent,
                    "model": s.model,
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "duration_ms": s.duration_ms,
                    "input_data": s.input_data,
                    "output_data": s.output_data,
                    "context_before": s.context_before,
                    "context_after": s.context_after,
                    "reasoning": s.reasoning,
                    "errors": s.errors,
                    "tags": s.tags,
                    "trace_id": s.trace_id,
                }
                for s in trace.spans
            ],
            "start_time": trace.start_time,
            "end_time": trace.end_time,
            "total_duration_ms": trace.total_duration_ms,
            "success": trace.success,
            "metadata": trace.metadata,
        }
    
    def _save_trace(self, trace: ExecutionTrace):
        """Save a trace to disk."""
        trace_file = self.storage_dir / f"{trace.id}.json"
        with open(trace_file, "w", encoding="utf-8") as f:
            json.dump(self._serialize_trace(trace), f, indent=2)
    
    def start_trace(self, name: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Start a new execution trace."""
        trace_id = hashlib.md5(f"{name}:{time.time()}".encode()).hexdigest()[:12]
        trace = ExecutionTrace(
            id=trace_id,
            start_time=time.time(),
            metadata=metadata or {},
        )
        self.traces[trace_id] = trace
        return trace_id
    
    def start_span(
        self,
        trace_id: str,
        name: str,
        component: str = "",
        agent: str = "",
        intent: str = "",
        model: str = "",
        parent_id: str = "",
        input_data: Optional[Dict[str, Any]] = None,
        context_before: str = "",
        tags: Optional[List[str]] = None,
    ) -> str:
        """Start a span within a trace."""
        span_id = hashlib.md5(f"{trace_id}:{name}:{time.time()}".encode()).hexdigest()[:12]
        span = TraceSpan(
            id=span_id,
            parent_id=parent_id,
            name=name,
            component=component,
            agent=agent,
            intent=intent,
            model=model,
            start_time=time.time(),
            input_data=input_data or {},
            context_before=context_before,
            tags=tags or [],
            trace_id=trace_id,
        )
        self.active_spans[span_id] = span
        
        if trace_id in self.traces:
            self.traces[trace_id].spans.append(span)
            if not self.traces[trace_id].root_span:
                self.traces[trace_id].root_span = span_id
        
        return span_id
    
    def end_span(
        self,
        span_id: str,
        output_data: Optional[Dict[str, Any]] = None,
        context_after: str = "",
        reasoning: Optional[List[Dict[str, Any]]] = None,
        errors: Optional[List[str]] = None,
        success: bool = True,
    ):
        """End a span."""
        span = self.active_spans.pop(span_id, None)
        if not span:
            return
        
        span.end_time = time.time()
        span.duration_ms = (span.end_time - span.start_time) * 1000
        span.output_data = output_data or {}
        span.context_after = context_after
        span.reasoning = reasoning or []
        span.errors = errors or []
        
        # Update trace
        trace = self.traces.get(span.trace_id)
        if trace:
            trace.end_time = span.end_time
            trace.total_duration_ms = (trace.end_time - trace.start_time) * 1000
            if not success:
                trace.success = False
            self._save_trace(trace)
    
    def end_trace(self, trace_id: str, success: bool = True):
        """End a trace."""
        trace = self.traces.get(trace_id)
        if trace:
            trace.end_time = time.time()
            trace.total_duration_ms = (trace.end_time - trace.start_time) * 1000
            trace.success = success
            self._save_trace(trace)
    
    @contextmanager
    def trace(
        self,
        name: str,
        input_data: Optional[Dict[str, Any]] = None,
        component: str = "",
        agent: str = "",
        intent: str = "",
        model: str = "",
        parent_span: str = "",
        tags: Optional[List[str]] = None,
    ) -> Iterator[str]:
        """Context manager for tracing a block of code."""
        # Auto-create trace if needed
        trace_id = None
        for tid, trace in self.traces.items():
            if not trace.end_time:
                trace_id = tid
                break
        
        if not trace_id:
            trace_id = self.start_trace(name)
        
        span_id = self.start_span(
            trace_id=trace_id,
            name=name,
            component=component,
            agent=agent,
            intent=intent,
            model=model,
            parent_id=parent_span,
            input_data=input_data,
            tags=tags,
        )
        
        try:
            yield span_id
        except Exception as e:
            self.end_span(span_id, errors=[str(e)], success=False)
            raise
        else:
            self.end_span(span_id, success=True)
    
    def search(
        self,
        query: str = "",
        agent: str = "",
        component: str = "",
        intent: str = "",
        since: str = "",
        success_only: bool = False,
        error_only: bool = False,
        limit: int = 20,
    ) -> List[ExecutionTrace]:
        """Search traces."""
        results = []
        now = time.time()
        
        # Parse since
        since_seconds = 0
        if since:
            if since.endswith("h"):
                since_seconds = int(since[:-1]) * 3600
            elif since.endswith("m"):
                since_seconds = int(since[:-1]) * 60
            elif since.endswith("d"):
                since_seconds = int(since[:-1]) * 86400
        
        for trace in self.traces.values():
            # Time filter
            if since_seconds and (now - trace.start_time) > since_seconds:
                continue
            
            # Success/error filter
            if success_only and not trace.success:
                continue
            if error_only and trace.success:
                continue
            
            # Component filter
            if component and not any(s.component == component for s in trace.spans):
                continue
            
            # Agent filter
            if agent and not any(s.agent == agent for s in trace.spans):
                continue
            
            # Intent filter
            if intent and not any(s.intent == intent for s in trace.spans):
                continue
            
            # Text search
            if query:
                query_lower = query.lower()
                match = False
                for span in trace.spans:
                    if (query_lower in span.name.lower() or
                        query_lower in span.component.lower() or
                        query_lower in span.agent.lower() or
                        query_lower in span.intent.lower() or
                        query_lower in json.dumps(span.input_data).lower() or
                        query_lower in json.dumps(span.output_data).lower()):
                        match = True
                        break
                if not match:
                    continue
            
            results.append(trace)
        
        # Sort by start time (newest first)
        results.sort(key=lambda t: t.start_time, reverse=True)
        return results[:limit]
    
    def get_trace(self, trace_id: str) -> Optional[ExecutionTrace]:
        """Get a specific trace."""
        return self.traces.get(trace_id)
    
    def get_span(self, span_id: str) -> Optional[TraceSpan]:
        """Get a specific span."""
        for trace in self.traces.values():
            for span in trace.spans:
                if span.id == span_id:
                    return span
        return None
    
    def get_tree(self, trace_id: str) -> Dict[str, Any]:
        """Build a tree representation of a trace."""
        trace = self.traces.get(trace_id)
        if not trace:
            return {}
        
        # Build parent-child relationships
        by_parent: Dict[str, List[TraceSpan]] = {}
        for span in trace.spans:
            parent = span.parent_id or "root"
            by_parent.setdefault(parent, []).append(span)
        
        def build_node(span: TraceSpan) -> Dict[str, Any]:
            children = by_parent.get(span.id, [])
            return {
                "id": span.id,
                "name": span.name,
                "component": span.component,
                "agent": span.agent,
                "duration_ms": round(span.duration_ms, 2),
                "success": not span.errors,
                "errors": span.errors,
                "children": [build_node(c) for c in sorted(children, key=lambda x: x.start_time)],
            }
        
        root_spans = by_parent.get("root", [])
        if trace.root_span:
            root = next((s for s in trace.spans if s.id == trace.root_span), None)
            if root:
                root_spans = [root]
        
        return {
            "trace_id": trace.id,
            "total_duration_ms": round(trace.total_duration_ms, 2),
            "success": trace.success,
            "spans": [build_node(s) for s in sorted(root_spans, key=lambda x: x.start_time)],
        }
    
    def print_tree(self, trace_id: str):
        """Print a trace as an ASCII tree."""
        tree = self.get_tree(trace_id)
        if not tree:
            print(f"Trace not found: {trace_id}")
            return
        
        print(f"\nTrace: {tree['trace_id']}")
        print(f"Duration: {tree['total_duration_ms']}ms | Success: {'✅' if tree['success'] else '❌'}")
        print()
        
        def print_node(node: Dict[str, Any], indent: int = 0, is_last: bool = True):
            prefix = "    " * (indent - 1) if indent > 0 else ""
            if indent > 0:
                prefix += "└── " if is_last else "├── "
            
            status = "✅" if node.get("success") else "❌"
            component = f"[{node.get('component', '')}]" if node.get("component") else ""
            agent = f"({node.get('agent', '')})" if node.get("agent") else ""
            duration = f"{node.get('duration_ms', 0)}ms"
            
            print(f"{prefix}{status} {node.get('name', '')} {component} {agent} - {duration}")
            
            if node.get("errors"):
                for error in node["errors"]:
                    print(f"{'    ' * indent}    ⚠️  {error}")
            
            children = node.get("children", [])
            for i, child in enumerate(children):
                print_node(child, indent + 1, is_last=(i == len(children) - 1))
        
        for span in tree.get("spans", []):
            print_node(span)
        print()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get tracer statistics."""
        total = len(self.traces)
        successful = sum(1 for t in self.traces.values() if t.success)
        failed = total - successful
        
        by_component = {}
        by_agent = {}
        by_intent = {}
        
        for trace in self.traces.values():
            for span in trace.spans:
                if span.component:
                    by_component[span.component] = by_component.get(span.component, 0) + 1
                if span.agent:
                    by_agent[span.agent] = by_agent.get(span.agent, 0) + 1
                if span.intent:
                    by_intent[span.intent] = by_intent.get(span.intent, 0) + 1
        
        avg_duration = sum(t.total_duration_ms for t in self.traces.values()) / total if total else 0
        
        return {
            "total_traces": total,
            "successful": successful,
            "failed": failed,
            "success_rate": round(successful / total, 3) if total else 0,
            "avg_duration_ms": round(avg_duration, 2),
            "by_component": by_component,
            "by_agent": by_agent,
            "by_intent": by_intent,
            "storage_dir": str(self.storage_dir),
        }
    
    def replay(self, trace_id: str) -> Dict[str, Any]:
        """Replay a trace showing what happened step by step."""
        trace = self.traces.get(trace_id)
        if not trace:
            return {"error": f"Trace not found: {trace_id}"}
        
        replay_log = []
        for span in sorted(trace.spans, key=lambda s: s.start_time):
            replay_log.append({
                "time": datetime.fromtimestamp(span.start_time).isoformat(),
                "component": span.component,
                "name": span.name,
                "agent": span.agent,
                "intent": span.intent,
                "model": span.model,
                "duration_ms": round(span.duration_ms, 2),
                "input": span.input_data,
                "output": span.output_data,
                "reasoning": span.reasoning,
                "errors": span.errors,
                "context_diff": {
                    "before": span.context_before[:200] if span.context_before else "",
                    "after": span.context_after[:200] if span.context_after else "",
                },
            })
        
        return {
            "trace_id": trace_id,
            "success": trace.success,
            "total_duration_ms": round(trace.total_duration_ms, 2),
            "span_count": len(trace.spans),
            "replay": replay_log,
        }


def get_tracer(storage_dir: str = ".crackedcode/traces") -> ExecutionTracer:
    """Get the global execution tracer."""
    return ExecutionTracer(storage_dir=storage_dir)
