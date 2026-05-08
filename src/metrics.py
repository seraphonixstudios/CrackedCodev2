"""Metrics & Analytics - Request tracking and performance monitoring.

Tracks request counts, latency, token estimates, model usage, agent tasks,
and intent distribution. Persists to JSON for historical analysis.

Usage:
    from src.metrics import MetricsCollector, get_metrics_collector
    metrics = get_metrics_collector()
    metrics.record_request(intent="code", model="qwen3:8b-gpu", latency_ms=2340)
"""

import json
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.logger_config import get_logger

logger = get_logger("Metrics")


# â”€â”€ Data Models â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@dataclass
class RequestMetrics:
    """Metrics for a single request."""
    timestamp: float
    intent: str
    model: str
    latency_ms: float
    success: bool
    processing_path: str = ""
    token_estimate: int = 0


@dataclass
class AggregatedMetrics:
    """Aggregated metrics snapshot."""
    requests_total: int = 0
    requests_success: int = 0
    requests_failed: int = 0
    total_latency_ms: float = 0.0
    avg_latency_ms: float = 0.0
    min_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    tokens_generated: int = 0
    tokens_per_second: float = 0.0
    model_usage: Dict[str, int] = field(default_factory=dict)
    intent_distribution: Dict[str, int] = field(default_factory=dict)
    agent_tasks: Dict[str, int] = field(default_factory=dict)
    processing_paths: Dict[str, int] = field(default_factory=dict)
    hourly_requests: Dict[str, int] = field(default_factory=dict)
    daily_requests: Dict[str, int] = field(default_factory=dict)


# â”€â”€ Metrics Collector â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class MetricsCollector:
    """Collect and aggregate performance metrics."""
    
    def __init__(self, data_dir: str = ".crackedcode/metrics", max_history: int = 10000):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.max_history = max_history
        self._lock = threading.Lock()
        self._requests: List[RequestMetrics] = []
        self._load()
    
    def _load(self):
        """Load persisted metrics from disk."""
        path = self.data_dir / "metrics.json"
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data[-self.max_history:]:
                    self._requests.append(RequestMetrics(**item))
                logger.info(f"Loaded {len(self._requests)} metrics records")
            except Exception as e:
                logger.warning(f"Failed to load metrics: {e}")
    
    def _save(self):
        """Persist metrics to disk."""
        try:
            path = self.data_dir / "metrics.json"
            data = [asdict(r) for r in self._requests[-self.max_history:]]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save metrics: {e}")
    
    def record_request(self, intent: str, model: str, latency_ms: float,
                       success: bool = True, processing_path: str = "",
                       token_estimate: int = 0, agent: str = ""):
        """Record a single request's metrics."""
        with self._lock:
            metric = RequestMetrics(
                timestamp=time.time(),
                intent=intent,
                model=model,
                latency_ms=latency_ms,
                success=success,
                processing_path=processing_path,
                token_estimate=token_estimate,
            )
            self._requests.append(metric)
            
            # Trim history
            if len(self._requests) > self.max_history:
                self._requests = self._requests[-self.max_history:]
            
            # Periodic save (every 10 requests)
            if len(self._requests) % 10 == 0:
                self._save()
    
    def get_snapshot(self, hours: Optional[int] = None) -> AggregatedMetrics:
        """Get aggregated metrics, optionally filtered by hours."""
        with self._lock:
            now = time.time()
            if hours:
                cutoff = now - (hours * 3600)
                requests = [r for r in self._requests if r.timestamp >= cutoff]
            else:
                requests = self._requests
            
            if not requests:
                return AggregatedMetrics()
            
            latencies = [r.latency_ms for r in requests]
            total_latency = sum(latencies)
            
            snapshot = AggregatedMetrics(
                requests_total=len(requests),
                requests_success=sum(1 for r in requests if r.success),
                requests_failed=sum(1 for r in requests if not r.success),
                total_latency_ms=total_latency,
                avg_latency_ms=total_latency / len(requests),
                min_latency_ms=min(latencies),
                max_latency_ms=max(latencies),
                tokens_generated=sum(r.token_estimate for r in requests),
            )
            
            # Tokens per second
            if total_latency > 0:
                snapshot.tokens_per_second = (snapshot.tokens_generated / total_latency) * 1000
            
            # Model usage
            for r in requests:
                snapshot.model_usage[r.model] = snapshot.model_usage.get(r.model, 0) + 1
            
            # Intent distribution
            for r in requests:
                snapshot.intent_distribution[r.intent] = snapshot.intent_distribution.get(r.intent, 0) + 1
            
            # Processing paths
            for r in requests:
                if r.processing_path:
                    snapshot.processing_paths[r.processing_path] = snapshot.processing_paths.get(r.processing_path, 0) + 1
            
            # Hourly requests (last 24 hours)
            for r in requests:
                hour_key = datetime.fromtimestamp(r.timestamp).strftime("%Y-%m-%d %H:00")
                snapshot.hourly_requests[hour_key] = snapshot.hourly_requests.get(hour_key, 0) + 1
            
            # Daily requests
            for r in requests:
                day_key = datetime.fromtimestamp(r.timestamp).strftime("%Y-%m-%d")
                snapshot.daily_requests[day_key] = snapshot.daily_requests.get(day_key, 0) + 1
            
            return snapshot
    
    def get_uptime_seconds(self) -> float:
        """Get system uptime based on first metric timestamp."""
        with self._lock:
            if not self._requests:
                return 0.0
            return time.time() - self._requests[0].timestamp
    
    def get_recent_requests(self, n: int = 10) -> List[Dict[str, Any]]:
        """Get the N most recent requests."""
        with self._lock:
            return [asdict(r) for r in self._requests[-n:]]
    
    def reset(self):
        """Clear all metrics."""
        with self._lock:
            self._requests.clear()
            self._save()
        logger.info("Metrics reset")
    
    def export_to_json(self, path: str):
        """Export metrics to a JSON file."""
        with self._lock:
            data = {
                "exported_at": datetime.now().isoformat(),
                "snapshot": asdict(self.get_snapshot()),
                "recent_requests": self.get_recent_requests(100),
            }
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Metrics exported to {path}")


# â”€â”€ Singleton â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector(data_dir: str = ".crackedcode/metrics") -> MetricsCollector:
    """Get or create the global metrics collector."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector(data_dir=data_dir)
    return _metrics_collector


# â”€â”€ Context Manager for Timing â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class timed_request:
    """Context manager that times a request and records metrics.
    
    Usage:
        with timed_request(metrics, intent="code", model="qwen3:8b-gpu") as recorder:
            response = engine.process(...)
            recorder.success = response.success
            recorder.processing_path = response.processing_path
    """
    
    def __init__(self, metrics: MetricsCollector, intent: str, model: str):
        self.metrics = metrics
        self.intent = intent
        self.model = model
        self.start_time = 0.0
        self.success = True
        self.processing_path = ""
        self.token_estimate = 0
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        latency_ms = (time.time() - self.start_time) * 1000
        if exc_type is not None:
            self.success = False
        
        self.metrics.record_request(
            intent=self.intent,
            model=self.model,
            latency_ms=latency_ms,
            success=self.success,
            processing_path=self.processing_path,
            token_estimate=self.token_estimate,
        )
        return False  # Don't suppress exceptions

