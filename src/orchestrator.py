"""Unified Orchestrator - Production-grade multi-agent task orchestration.

Integrates GUI task tracking, parallel execution, CLI swarm, and autonomous
production into a single cohesive system with proper lifecycle management.

Task Lifecycle:
    PENDING -> QUEUED -> RUNNING -> VERIFYING -> COMPLETED
                                    |-> FAILED -> RETRYING -> QUEUED
                                    |-> CANCELLED (terminal)

Features:
- Priority queue with dependency resolution
- Agent capability matching and load balancing
- Task timeout, retry with exponential backoff
- Sub-task spawning (recursive delegation)
- Blackboard shared state
- Pipeline workflows
- Real-time status callbacks
"""

import uuid
import time
import asyncio
import threading
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Callable, Any, Set, Tuple
from datetime import datetime
from queue import PriorityQueue

from src.logger_config import get_logger

logger = get_logger("UnifiedOrchestrator")


class TaskStatus(Enum):
    """Full task lifecycle states."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"
    TIMEDOUT = "timedout"


class TaskPriority(Enum):
    """Task priority levels."""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class AgentRole(Enum):
    """Agent roles with capabilities."""
    SUPERVISOR = "supervisor"
    ARCHITECT = "architect"
    CODER = "coder"
    EXECUTOR = "executor"
    REVIEWER = "reviewer"
    SEARCHER = "searcher"
    TESTER = "tester"
    DEBUGGER = "debugger"
    DOCUMENTER = "documenter"


AGENT_CAPABILITIES = {
    AgentRole.SUPERVISOR: ["plan", "coordinate", "delegate", "summarize"],
    AgentRole.ARCHITECT: ["design", "plan", "structure", "blueprint"],
    AgentRole.CODER: ["code", "write", "generate", "implement", "refactor"],
    AgentRole.EXECUTOR: ["run", "execute", "test", "deploy", "shell"],
    AgentRole.REVIEWER: ["review", "audit", "assess", "critique"],
    AgentRole.SEARCHER: ["search", "find", "grep", "locate"],
    AgentRole.TESTER: ["test", "verify", "validate", "check"],
    AgentRole.DEBUGGER: ["debug", "fix", "trace", "diagnose"],
    AgentRole.DOCUMENTER: ["document", "explain", "comment", "readme"],
}


INTENT_TO_AGENT = {
    "code": AgentRole.CODER,
    "debug": AgentRole.DEBUGGER,
    "review": AgentRole.REVIEWER,
    "build": AgentRole.ARCHITECT,
    "execute": AgentRole.EXECUTOR,
    "search": AgentRole.SEARCHER,
    "chat": AgentRole.CODER,
    "help": AgentRole.SUPERVISOR,
}


@dataclass
class Task:
    """A task in the orchestration system."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    intent: str = "chat"
    prompt: str = ""
    agent: AgentRole = AgentRole.CODER
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.NORMAL
    
    # Lifecycle
    created_at: float = field(default_factory=time.time)
    queued_at: Optional[float] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    # Execution
    result: Any = None
    error: str = ""
    output: str = ""
    
    # Configuration
    timeout: float = 120.0
    max_retries: int = 2
    retries: int = 0
    depends_on: List[str] = field(default_factory=list)
    sub_tasks: List[str] = field(default_factory=list)
    parent_id: Optional[str] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    
    # Callbacks
    on_status_change: Optional[Callable[["Task"], None]] = None
    on_complete: Optional[Callable[["Task"], None]] = None
    on_fail: Optional[Callable[["Task"], None]] = None
    
    def set_status(self, status: TaskStatus, error: str = ""):
        """Update status with timestamp tracking."""
        old = self.status
        self.status = status
        
        if status == TaskStatus.QUEUED and self.queued_at is None:
            self.queued_at = time.time()
        elif status == TaskStatus.RUNNING:
            self.started_at = time.time()
        elif status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.TIMEDOUT):
            self.completed_at = time.time()
        
        if error:
            self.error = error
        
        if self.on_status_change and old != status:
            try:
                self.on_status_change(self)
            except Exception:
                pass
        
        if status == TaskStatus.COMPLETED and self.on_complete:
            try:
                self.on_complete(self)
            except Exception:
                pass
        elif status == TaskStatus.FAILED and self.on_fail:
            try:
                self.on_fail(self)
            except Exception:
                pass
    
    @property
    def duration(self) -> float:
        """Total duration from creation to completion."""
        end = self.completed_at or time.time()
        return end - self.created_at
    
    @property
    def execution_time(self) -> float:
        """Time spent in RUNNING state."""
        if not self.started_at:
            return 0.0
        end = self.completed_at or time.time()
        return end - self.started_at
    
    @property
    @property
    def wait_time(self) -> float:
        """Time spent waiting before execution."""
        if not self.queued_at:
            return 0.0
        start = self.started_at or time.time()
        return start - self.queued_at
    
    @property
    def is_terminal(self) -> bool:
        """Check if task is in a terminal state."""
        return self.status in (
            TaskStatus.COMPLETED, TaskStatus.FAILED,
            TaskStatus.CANCELLED, TaskStatus.TIMEDOUT
        )
    
    @property
    def can_retry(self) -> bool:
        """Check if task can be retried."""
        return self.retries < self.max_retries and self.status == TaskStatus.FAILED
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize task to dictionary."""
        return {
            "id": self.id,
            "intent": self.intent,
            "prompt": self.prompt[:100] + "..." if len(self.prompt) > 100 else self.prompt,
            "agent": self.agent.value,
            "status": self.status.value,
            "priority": self.priority.value,
            "duration": round(self.duration, 2),
            "execution_time": round(self.execution_time, 2),
            "retries": self.retries,
            "max_retries": self.max_retries,
            "depends_on": self.depends_on,
            "sub_tasks": self.sub_tasks,
            "parent_id": self.parent_id,
            "has_result": self.result is not None,
            "has_error": bool(self.error),
        }


@dataclass
class Blackboard:
    """Shared state for agent collaboration."""
    project_context: str = ""
    files: Dict[str, str] = field(default_factory=dict)
    plan: List[Dict] = field(default_factory=list)
    debate_log: List[Dict] = field(default_factory=list)
    consensus: Dict[str, Any] = field(default_factory=dict)
    agent_memory: Dict[str, List[str]] = field(default_factory=dict)
    task_history: List[Dict] = field(default_factory=list)
    code_snippets: Dict[str, str] = field(default_factory=dict)
    test_results: Dict[str, Any] = field(default_factory=dict)
    
    def add_memory(self, agent: str, entry: str):
        if agent not in self.agent_memory:
            self.agent_memory[agent] = []
        self.agent_memory[agent].append(f"[{datetime.now().strftime('%H:%M:%S')}] {entry}")
    
    def get_context(self) -> str:
        parts = [
            f"Project: {self.project_context}",
            f"Files: {len(self.files)}",
            f"Plan steps: {len(self.plan)}",
            f"Code snippets: {len(self.code_snippets)}",
            f"Test results: {len(self.test_results)}",
        ]
        return "\n".join(parts)


class AgentWorker:
    """Represents an agent that can execute tasks."""
    
    def __init__(self, role: AgentRole, engine=None):
        self.role = role
        self.engine = engine
        self.status = "idle"
        self.tasks_completed = 0
        self.tasks_failed = 0
        self.current_task: Optional[str] = None
        self.capabilities = AGENT_CAPABILITIES.get(role, [])
    
    def can_handle(self, intent: str) -> bool:
        """Check if this agent can handle an intent."""
        return intent.lower() in self.capabilities
    
    async def execute(self, task: Task) -> Any:
        """Execute a task using the engine."""
        if not self.engine:
            raise RuntimeError(f"Agent {self.role.value} has no engine")
        
        self.status = "active"
        self.current_task = task.id
        
        try:
            from src.engine import Intent
            intent_map = {
                "code": Intent.CODE,
                "debug": Intent.DEBUG,
                "review": Intent.REVIEW,
                "build": Intent.BUILD,
                "execute": Intent.EXECUTE,
                "search": Intent.SEARCH,
                "chat": Intent.CHAT,
                "help": Intent.CHAT,
            }
            engine_intent = intent_map.get(task.intent, Intent.CHAT)
            
            # Set context from blackboard
            if task.context:
                self.engine.session.add_context(task.context)
            
            response = await self.engine.process(
                task.prompt,
                streaming=task.metadata.get("streaming", False),
                callback=task.metadata.get("callback")
            )
            
            self.tasks_completed += 1
            return response
            
        finally:
            self.status = "idle"
            self.current_task = None


class UnifiedOrchestrator:
    """Production-grade task orchestrator.
    
    Unifies GUI tracking, parallel execution, CLI swarm, and autonomous
    production into a single system.
    """
    
    def __init__(self, engine=None, max_workers: int = 4):
        self.engine = engine
        self.max_workers = max_workers
        
        # Task management
        self._tasks: Dict[str, Task] = {}
        self._task_queue = PriorityQueue()
        self._running_tasks: Dict[str, threading.Thread] = {}
        self._completed_tasks: List[str] = []
        
        # Agent management
        self._agents: Dict[AgentRole, AgentWorker] = {}
        self._init_agents()
        
        # Shared state
        self.blackboard = Blackboard()
        
        # Execution
        self._running = False
        self._executor_thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()
        
        # Callbacks
        self.on_task_created: Optional[Callable[[Task], None]] = None
        self.on_task_started: Optional[Callable[[Task], None]] = None
        self.on_task_completed: Optional[Callable[[Task], None]] = None
        self.on_task_failed: Optional[Callable[[Task], None]] = None
        self.on_queue_changed: Optional[Callable[[], None]] = None
    
    def _init_agents(self):
        """Initialize all agent workers."""
        for role in AgentRole:
            self._agents[role] = AgentWorker(role, self.engine)
    
    def create_task(
        self,
        prompt: str,
        intent: str = "chat",
        agent: Optional[AgentRole] = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        timeout: float = 120.0,
        max_retries: int = 2,
        depends_on: List[str] = None,
        parent_id: Optional[str] = None,
        context: Dict[str, Any] = None,
        metadata: Dict[str, Any] = None,
    ) -> Task:
        """Create a new task.
        
        Args:
            prompt: The user prompt or instruction
            intent: Intent classification (code, debug, review, etc.)
            agent: Specific agent role (auto-selected if None)
            priority: Task priority level
            timeout: Maximum execution time in seconds
            max_retries: Maximum retry attempts
            depends_on: List of task IDs that must complete first
            parent_id: Parent task ID for sub-tasks
            context: Shared context for the task
            metadata: Additional metadata
        """
        # Auto-select agent based on intent
        if agent is None:
            agent = INTENT_TO_AGENT.get(intent.lower(), AgentRole.CODER)
        
        task = Task(
            intent=intent,
            prompt=prompt,
            agent=agent,
            priority=priority,
            timeout=timeout,
            max_retries=max_retries,
            depends_on=depends_on or [],
            parent_id=parent_id,
            context=context or {},
            metadata=metadata or {},
        )
        
        with self._lock:
            self._tasks[task.id] = task
        
        logger.info(f"Task {task.id} created: {intent} -> {agent.value}")
        
        if self.on_task_created:
            self.on_task_created(task)
        
        return task
    
    def submit(self, task: Task) -> str:
        """Submit a task to the queue.
        
        Args:
            task: Task to submit
            
        Returns:
            Task ID
        """
        task.set_status(TaskStatus.QUEUED)
        
        # Priority: higher value = higher priority
        # Negative because PriorityQueue is min-heap
        priority_value = -task.priority.value
        
        self._task_queue.put((priority_value, task.created_at, task.id))
        
        logger.info(f"Task {task.id} queued (priority: {task.priority.name})")
        
        if self.on_queue_changed:
            self.on_queue_changed()
        
        # Auto-start if not running
        if not self._running:
            self.start()
        
        return task.id
    
    def submit_and_wait(self, task: Task) -> Task:
        """Submit a task and block until completion.
        
        Args:
            task: Task to submit
            
        Returns:
            Completed task
        """
        self.submit(task)
        
        # Wait for terminal state
        while not task.is_terminal:
            time.sleep(0.1)
        
        return task
    
    def start(self):
        """Start the orchestrator worker thread."""
        if self._running:
            return
        
        self._running = True
        self._executor_thread = threading.Thread(target=self._executor_loop, daemon=True)
        self._executor_thread.start()
        
        logger.info(f"Orchestrator started (max_workers: {self.max_workers})")
    
    def stop(self):
        """Stop the orchestrator."""
        self._running = False
        
        if self._executor_thread:
            self._executor_thread.join(timeout=5)
        
        # Cancel all running tasks
        with self._lock:
            for task_id, thread in list(self._running_tasks.items()):
                self.cancel_task(task_id)
        
        logger.info("Orchestrator stopped")
    
    def _executor_loop(self):
        """Main execution loop."""
        while self._running:
            try:
                # Check for available task
                if self._task_queue.empty():
                    time.sleep(0.1)
                    continue
                
                # Check if we have capacity
                with self._lock:
                    if len(self._running_tasks) >= self.max_workers:
                        time.sleep(0.1)
                        continue
                
                # Get next task
                _, _, task_id = self._task_queue.get(timeout=1)
                
                with self._lock:
                    if task_id not in self._tasks:
                        continue
                    task = self._tasks[task_id]
                
                # Check if already terminal
                if task.is_terminal:
                    continue
                
                # Check dependencies
                if not self._check_dependencies(task):
                    # Re-queue if dependencies not met
                    task.set_status(TaskStatus.PENDING)
                    self._task_queue.put((-task.priority.value, task.created_at, task.id))
                    time.sleep(0.5)
                    continue
                
                # Start execution
                self._start_task(task)
                
            except Exception as e:
                logger.error(f"Executor loop error: {e}")
                time.sleep(0.5)
    
    def _check_dependencies(self, task: Task) -> bool:
        """Check if all dependencies are satisfied."""
        with self._lock:
            for dep_id in task.depends_on:
                if dep_id not in self._tasks:
                    logger.warning(f"Task {task.id} depends on unknown task {dep_id}")
                    return False
                dep = self._tasks[dep_id]
                if dep.status != TaskStatus.COMPLETED:
                    return False
        return True
    
    def _start_task(self, task: Task):
        """Start executing a task in a new thread."""
        task.set_status(TaskStatus.RUNNING)
        
        if self.on_task_started:
            self.on_task_started(task)
        
        # Get agent
        agent = self._agents.get(task.agent)
        if not agent:
            task.set_status(TaskStatus.FAILED, f"Unknown agent: {task.agent}")
            self._handle_task_complete(task)
            return
        
        # Start execution thread
        thread = threading.Thread(
            target=self._execute_task_wrapper,
            args=(task, agent),
            daemon=True
        )
        
        with self._lock:
            self._running_tasks[task.id] = thread
        
        thread.start()
    
    def _execute_task_wrapper(self, task: Task, agent: AgentWorker):
        """Wrapper for task execution with timeout and retry handling."""
        try:
            result = self._execute_with_timeout(task, agent)
            
            if result is not None:
                task.result = result
                task.set_status(TaskStatus.COMPLETED)
            else:
                task.set_status(TaskStatus.FAILED, "Execution returned None")
        
        except TimeoutError:
            task.set_status(TaskStatus.TIMEDOUT, f"Timeout after {task.timeout}s")
        
        except Exception as e:
            task.set_status(TaskStatus.FAILED, str(e))
        
        finally:
            with self._lock:
                if task.id in self._running_tasks:
                    del self._running_tasks[task.id]
            
            self._handle_task_complete(task)
    
    def _execute_with_timeout(self, task: Task, agent: AgentWorker) -> Any:
        """Execute task with timeout support."""
        import concurrent.futures
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self._run_task_sync, task, agent)
            return future.result(timeout=task.timeout)
    
    def _run_task_sync(self, task: Task, agent: AgentWorker) -> Any:
        """Run a task synchronously."""
        logger.info(f"Task {task.id} executing with {agent.role.value}")
        
        # Run in async context
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        if loop.is_running():
            # If already in an event loop, run in executor
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(
                    asyncio.run,
                    agent.execute(task)
                )
                return future.result(timeout=task.timeout)
        else:
            return loop.run_until_complete(agent.execute(task))
    
    def _handle_task_complete(self, task: Task):
        """Handle task completion, retry, and queue next tasks."""
        logger.info(f"Task {task.id} completed with status: {task.status.value}")
        
        with self._lock:
            if task.status == TaskStatus.COMPLETED:
                self._completed_tasks.append(task.id)
                if self.on_task_completed:
                    self.on_task_completed(task)
            elif task.status == TaskStatus.FAILED:
                if task.can_retry:
                    self._retry_task(task)
                    return
                if self.on_task_failed:
                    self.on_task_failed(task)
        
        # Blackboard update
        self.blackboard.task_history.append(task.to_dict())
        
        if self.on_queue_changed:
            self.on_queue_changed()
    
    def _retry_task(self, task: Task):
        """Retry a failed task."""
        task.retries += 1
        task.set_status(TaskStatus.RETRYING)
        
        logger.info(f"Task {task.id} retrying ({task.retries}/{task.max_retries})")
        
        # Small delay before retry
        time.sleep(0.5 * task.retries)
        
        task.set_status(TaskStatus.QUEUED)
        self._task_queue.put((-task.priority.value, task.created_at, task.id))
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a task.
        
        Args:
            task_id: Task ID to cancel
            
        Returns:
            True if cancelled
        """
        with self._lock:
            if task_id not in self._tasks:
                return False
            task = self._tasks[task_id]
        
        if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            return False
        
        # Cancel running thread if possible
        if task_id in self._running_tasks:
            # Thread cancellation is cooperative
            logger.info(f"Task {task_id} cancellation requested")
        
        task.set_status(TaskStatus.CANCELLED)
        
        with self._lock:
            if task_id in self._running_tasks:
                del self._running_tasks[task_id]
        
        if self.on_queue_changed:
            self.on_queue_changed()
        
        return True
    
    def delegate(
        self,
        parent_task_id: str,
        prompt: str,
        intent: str = "code",
        agent: Optional[AgentRole] = None,
        priority: TaskPriority = None,
    ) -> str:
        """Delegate a sub-task from a parent task.
        
        Args:
            parent_task_id: Parent task ID
            prompt: Sub-task prompt
            intent: Sub-task intent
            agent: Agent role
            priority: Priority (inherits from parent if None)
            
        Returns:
            Sub-task ID
        """
        with self._lock:
            parent = self._tasks.get(parent_task_id)
        
        if not parent:
            raise ValueError(f"Parent task {parent_task_id} not found")
        
        if priority is None:
            priority = parent.priority
        
        task = self.create_task(
            prompt=prompt,
            intent=intent,
            agent=agent,
            priority=priority,
            parent_id=parent_task_id,
            timeout=parent.timeout,
            max_retries=parent.max_retries,
            context=parent.context,
        )
        
        parent.sub_tasks.append(task.id)
        
        self.submit(task)
        
        logger.info(f"Task {parent_task_id} delegated sub-task {task.id}")
        
        return task.id
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        with self._lock:
            return self._tasks.get(task_id)
    
    def get_all_tasks(self) -> List[Task]:
        """Get all tasks."""
        with self._lock:
            return list(self._tasks.values())
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status."""
        with self._lock:
            tasks = list(self._tasks.values())
        
        status_counts = {s.value: 0 for s in TaskStatus}
        for task in tasks:
            status_counts[task.status.value] += 1
        
        active_agents = [
            {"role": role.value, "status": agent.status, "task": agent.current_task}
            for role, agent in self._agents.items()
            if agent.status == "active"
        ]
        
        running_tasks = [
            task.to_dict()
            for task in tasks
            if task.status == TaskStatus.RUNNING
        ]
        
        return {
            "total": len(tasks),
            "pending": status_counts[TaskStatus.PENDING.value],
            "queued": status_counts[TaskStatus.QUEUED.value],
            "running": status_counts[TaskStatus.RUNNING.value],
            "completed": status_counts[TaskStatus.COMPLETED.value],
            "failed": status_counts[TaskStatus.FAILED.value],
            "cancelled": status_counts[TaskStatus.CANCELLED.value],
            "active_agents": active_agents,
            "running_tasks": running_tasks,
            "max_workers": self.max_workers,
        }
    
    def create_pipeline(self, steps: List[Dict[str, Any]]) -> str:
        """Create a pipeline of dependent tasks.
        
        Args:
            steps: List of step dicts with keys: prompt, intent, agent, priority
            
        Returns:
            First task ID in the pipeline
        """
        prev_id: Optional[str] = None
        first_id: Optional[str] = None
        
        for i, step in enumerate(steps):
            task = self.create_task(
                prompt=step["prompt"],
                intent=step.get("intent", "code"),
                agent=step.get("agent"),
                priority=step.get("priority", TaskPriority.NORMAL),
                depends_on=[prev_id] if prev_id else [],
                metadata=step.get("metadata", {}),
            )
            
            if first_id is None:
                first_id = task.id
            
            self.submit(task)
            prev_id = task.id
        
        logger.info(f"Pipeline created with {len(steps)} steps, first: {first_id}")
        
        return first_id or ""


# Singleton instance
_orchestrator: Optional[UnifiedOrchestrator] = None


def get_orchestrator(engine=None, max_workers: int = 4) -> UnifiedOrchestrator:
    """Get or create the global orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = UnifiedOrchestrator(engine, max_workers)
    return _orchestrator
