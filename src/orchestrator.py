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

try:
    from src.reasoning import (
        ReasoningEngine, ThoughtChain, ReasoningType,
        get_reasoning_engine, AgentReasoning
    )
    _reasoning_available = True
except ImportError:
    _reasoning_available = False
    ReasoningEngine = None
    ThoughtChain = None
    ReasoningType = None
    get_reasoning_engine = None
    AgentReasoning = None

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
    
    # Reasoning
    reasoning_chain_id: Optional[str] = None
    reasoning_log: List[Dict[str, Any]] = field(default_factory=list)
    
    def add_reasoning(self, step_type: str, content: str, confidence: float = 0.5, evidence: List[str] = None):
        """Add a reasoning step to the task's log."""
        self.reasoning_log.append({
            "type": step_type,
            "content": content,
            "confidence": confidence,
            "evidence": evidence or [],
            "timestamp": time.time(),
        })
    
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
            "reasoning_steps": len(self.reasoning_log),
            "reasoning_chain_id": self.reasoning_chain_id,
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
    
    def __init__(self, role: AgentRole, engine=None, agent_id: str = None):
        self.role = role
        self.engine = engine
        self.agent_id = agent_id or f"{role.value}_{str(uuid.uuid4())[:6]}"
        self.status = "idle"
        self.tasks_completed = 0
        self.tasks_failed = 0
        self.current_task: Optional[str] = None
        self.capabilities = AGENT_CAPABILITIES.get(role, [])
        self._reasoning: Optional[Any] = None
    
    @property
    def reasoning(self) -> Optional[Any]:
        """Get agent reasoning state."""
        return self._reasoning
    
    @reasoning.setter
    def reasoning(self, value: Any):
        self._reasoning = value
    
    def can_handle(self, intent: str) -> bool:
        """Check if this agent can handle an intent."""
        return intent.lower() in self.capabilities
    
    async def execute(self, task: Task) -> Any:
        """Execute a task using the engine."""
        if not self.engine:
            raise RuntimeError(f"Agent {self.role.value} has no engine")
        
        self.status = "active"
        self.current_task = task.id
        
        # Log reasoning about task execution
        task.add_reasoning(
            "action",
            f"Agent {self.role.value} executing task {task.id}",
            0.8,
            [f"capabilities: {self.capabilities}", f"intent: {task.intent}"]
        )
        
        if self._reasoning:
            self._reasoning.add_action(
                f"Executing task {task.id} with intent '{task.intent}'",
                0.8,
                [f"Agent: {self.role.value}"],
            )
        
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
            
            # Use ReAct tool loop for complex tasks
            use_tools = task.metadata.get("use_tools", False) or task.intent in ("debug", "review", "build", "search")
            
            if use_tools and hasattr(self.engine, 'process_with_tools'):
                task.add_reasoning(
                    "decision",
                    f"Using ReAct tool loop for {task.intent} task",
                    0.85,
                    ["tool_framework: enabled", f"intent: {task.intent}"]
                )
                response = self.engine.process_with_tools(task.prompt, max_iterations=task.metadata.get("max_iterations", 5))
            else:
                response = await self.engine.process(
                    task.prompt,
                    streaming=task.metadata.get("streaming", False),
                    callback=task.metadata.get("callback")
                )
            
            self.tasks_completed += 1
            
            # Log completion reasoning
            task.add_reasoning(
                "reflection",
                f"Task execution completed successfully",
                0.9 if response and getattr(response, 'success', False) else 0.5,
            )
            
            if self._reasoning:
                self._reasoning.reflect(
                    f"Task {task.id} completed. Success: {getattr(response, 'success', False)}",
                    0.9 if response and getattr(response, 'success', False) else 0.5,
                )
            
            return response
            
        except Exception as e:
            self.tasks_failed += 1
            task.add_reasoning(
                "correction",
                f"Task execution failed: {str(e)}",
                0.3,
                [f"error: {str(e)}"]
            )
            if self._reasoning:
                self._reasoning.correct(
                    f"Task {task.id} failed: {str(e)}",
                    str(e),
                    0.3,
                )
            raise
            
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
        
        # Shared state
        self.blackboard = Blackboard()
        
        # Reasoning - must be before _init_agents
        self._reasoning_engine = get_reasoning_engine() if _reasoning_available else None
        
        # Register orchestrator itself for reasoning
        if _reasoning_available and self._reasoning_engine:
            self._reasoning_engine.register_agent("orchestrator", "orchestrator")
        
        self._init_agents()
        
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
        """Initialize all agent workers and register with reasoning engine."""
        for role in AgentRole:
            agent = AgentWorker(role, self.engine)
            self._agents[role] = agent
            
            # Register with reasoning engine
            if _reasoning_available and self._reasoning_engine:
                reasoning = self._reasoning_engine.register_agent(agent.agent_id, role.value)
                agent.reasoning = reasoning
    
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
        # Start reasoning chain for task creation
        reasoning_chain = None
        if _reasoning_available and self._reasoning_engine:
            reasoning_chain = self._reasoning_engine.create_reasoning_chain(
                agent_id="orchestrator",
                title=f"Task Creation: {intent}",
                context=f"Prompt: {prompt[:100]}..." if len(prompt) > 100 else f"Prompt: {prompt}",
                tags=["task_creation", intent],
            )
        
        # Auto-select agent based on intent with reasoning
        if agent is None:
            agent = INTENT_TO_AGENT.get(intent.lower(), AgentRole.CODER)
            
            # Log agent selection reasoning
            agent_reasoning = f"Selected agent '{agent.value}' based on intent '{intent}'"
            agent_evidence = [f"intent: {intent}", f"mapped_to: {agent.value}"]
            
            # Check capability match
            capabilities = AGENT_CAPABILITIES.get(agent, [])
            if intent.lower() in capabilities:
                agent_reasoning += f" (capability match: {intent} in {capabilities})"
                agent_evidence.append(f"capabilities: {capabilities}")
            else:
                agent_reasoning += f" (fallback: default agent for unmatched intent)"
                agent_evidence.append("fallback: true")
            
            if reasoning_chain:
                reasoning_chain.add_analysis(agent_reasoning, 0.75, agent_evidence, "orchestrator")
        else:
            agent_reasoning = f"Agent '{agent.value}' explicitly specified"
            if reasoning_chain:
                reasoning_chain.add_observation(agent_reasoning, ["explicit_assignment"], "orchestrator")
        
        # Reasoning about priority
        priority_reasoning = f"Priority set to {priority.name}"
        priority_evidence = []
        if parent_id:
            priority_reasoning += " (inherited from parent task)"
            priority_evidence.append(f"parent_id: {parent_id}")
        if depends_on:
            priority_reasoning += f" with {len(depends_on)} dependencies"
            priority_evidence.append(f"dependencies: {len(depends_on)}")
        if reasoning_chain:
            reasoning_chain.add_analysis(priority_reasoning, 0.7, priority_evidence, "orchestrator")
        
        # Reasoning about dependencies
        if depends_on:
            dep_reasoning = f"Task depends on {len(depends_on)} prerequisite task(s): {', '.join(depends_on)}"
            if reasoning_chain:
                reasoning_chain.add_observation(dep_reasoning, depends_on, "orchestrator")
        
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
        
        # Link reasoning chain to task
        if reasoning_chain:
            task.reasoning_chain_id = reasoning_chain.id
            task.add_reasoning(
                "decision",
                f"Task created with agent={agent.value}, priority={priority.name}",
                0.8,
                [f"agent_selection: {agent_reasoning}", f"priority: {priority_reasoning}"]
            )
            self._reasoning_engine.complete_reasoning_chain(
                "orchestrator",
                f"Created task {task.id} -> {agent.value}",
                0.8,
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
        
        # Reasoning about queue submission
        queue_reasoning = f"Task submitted to queue with priority {task.priority.name}"
        queue_evidence = [f"priority_value: {-task.priority.value}", f"queue_size: {self._task_queue.qsize()}"]
        
        if task.depends_on:
            queue_reasoning += f". Will wait for {len(task.depends_on)} dependencies."
            queue_evidence.append(f"dependencies: {task.depends_on}")
        
        task.add_reasoning("action", queue_reasoning, 0.75, queue_evidence)
        
        # Priority: higher value = higher priority
        # Negative because PriorityQueue is min-heap
        priority_value = -task.priority.value
        
        self._task_queue.put((priority_value, task.created_at, task.id))
        
        logger.info(f"Task {task.id} queued (priority: {task.priority.name})")
        
        if self.on_queue_changed:
            self.on_queue_changed()
        
        # Auto-start if not running
        if not self._running:
            task.add_reasoning("action", "Auto-starting orchestrator executor", 0.9)
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
        """Check if all dependencies are satisfied with reasoning."""
        with self._lock:
            for dep_id in task.depends_on:
                if dep_id not in self._tasks:
                    dep_reasoning = f"Dependency {dep_id} not found in task registry"
                    task.add_reasoning("observation", dep_reasoning, 0.2, [f"missing_dep: {dep_id}"])
                    logger.warning(f"Task {task.id} depends on unknown task {dep_id}")
                    return False
                dep = self._tasks[dep_id]
                if dep.status != TaskStatus.COMPLETED:
                    dep_reasoning = f"Waiting for dependency {dep_id} (status: {dep.status.value})"
                    task.add_reasoning("observation", dep_reasoning, 0.4, [
                        f"dep_id: {dep_id}",
                        f"dep_status: {dep.status.value}",
                        f"dep_progress: {dep.execution_time:.1f}s elapsed"
                    ])
                    return False
            
            # All dependencies satisfied
            if task.depends_on:
                task.add_reasoning(
                    "analysis",
                    f"All {len(task.depends_on)} dependencies satisfied",
                    0.9,
                    [f"deps: {task.depends_on}"]
                )
        return True
    
    def _start_task(self, task: Task):
        """Start executing a task in a new thread with reasoning."""
        task.set_status(TaskStatus.RUNNING)
        
        if self.on_task_started:
            self.on_task_started(task)
        
        # Get agent with reasoning
        agent = self._agents.get(task.agent)
        if not agent:
            fail_reasoning = f"Agent '{task.agent.value}' not found in registered agents"
            task.add_reasoning("correction", fail_reasoning, 0.1, [
                f"requested_agent: {task.agent.value}",
                f"available: {[r.value for r in self._agents.keys()]}"
            ])
            task.set_status(TaskStatus.FAILED, f"Unknown agent: {task.agent}")
            self._handle_task_complete(task)
            return
        
        # Log agent assignment reasoning
        active_agents = sum(1 for a in self._agents.values() if a.status == "active")
        assignment_reasoning = f"Assigned task to {agent.role.value} (agent_id: {agent.agent_id})"
        assignment_evidence = [
            f"agent_role: {agent.role.value}",
            f"agent_status: {agent.status}",
            f"active_agents: {active_agents}/{self.max_workers}",
            f"agent_capabilities: {agent.capabilities}",
        ]
        task.add_reasoning("action", assignment_reasoning, 0.85, assignment_evidence)
        
        # Start reasoning chain for agent execution
        if _reasoning_available and self._reasoning_engine and agent.reasoning:
            self._reasoning_engine.create_reasoning_chain(
                agent.agent_id,
                title=f"Execute Task {task.id}: {task.intent}",
                context=f"Task: {task.prompt[:80]}..." if len(task.prompt) > 80 else f"Task: {task.prompt}",
                tags=["task_execution", task.intent],
            )
        
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
                task.add_reasoning("decision", "Task completed successfully", 0.9, [
                    f"result_type: {type(result).__name__}",
                    f"execution_time: {task.execution_time:.2f}s"
                ])
            else:
                fail_reason = "Execution returned None - possible agent failure"
                task.add_reasoning("correction", fail_reason, 0.2, ["null_result"])
                task.set_status(TaskStatus.FAILED, "Execution returned None")
        
        except TimeoutError:
            timeout_reasoning = f"Task timed out after {task.timeout}s (exceeded limit)"
            task.add_reasoning("correction", timeout_reasoning, 0.3, [
                f"timeout_limit: {task.timeout}s",
                f"execution_time: {task.execution_time:.2f}s"
            ])
            task.set_status(TaskStatus.TIMEDOUT, f"Timeout after {task.timeout}s")
        
        except Exception as e:
            error_reasoning = f"Execution failed: {str(e)}"
            task.add_reasoning("correction", error_reasoning, 0.2, [
                f"error_type: {type(e).__name__}",
                f"error_message: {str(e)}"
            ])
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
        """Handle task completion, retry, and queue next tasks with reasoning."""
        logger.info(f"Task {task.id} completed with status: {task.status.value}")
        
        # Add completion reasoning
        completion_reasoning = f"Task completed with status: {task.status.value}"
        completion_evidence = [
            f"status: {task.status.value}",
            f"duration: {task.duration:.2f}s",
            f"execution_time: {task.execution_time:.2f}s",
            f"retries: {task.retries}/{task.max_retries}",
        ]
        if task.error:
            completion_evidence.append(f"error: {task.error[:100]}")
        task.add_reasoning("reflection", completion_reasoning, 0.7, completion_evidence)
        
        with self._lock:
            if task.status == TaskStatus.COMPLETED:
                self._completed_tasks.append(task.id)
                if self.on_task_completed:
                    self.on_task_completed(task)
            elif task.status == TaskStatus.FAILED:
                if task.can_retry:
                    task.add_reasoning(
                        "analysis",
                        f"Task failed but eligible for retry ({task.retries}/{task.max_retries})",
                        0.6,
                        ["retry_eligible: true"]
                    )
                    self._retry_task(task)
                    return
                else:
                    task.add_reasoning(
                        "decision",
                        f"Task failed and exhausted retries ({task.retries}/{task.max_retries})",
                        0.3,
                        ["retry_eligible: false", "final_status: failed"]
                    )
                if self.on_task_failed:
                    self.on_task_failed(task)
        
        # Blackboard update
        self.blackboard.task_history.append(task.to_dict())
        
        if self.on_queue_changed:
            self.on_queue_changed()
    
    def _retry_task(self, task: Task):
        """Retry a failed task with reasoning."""
        task.retries += 1
        task.set_status(TaskStatus.RETRYING)
        
        retry_reasoning = f"Retrying task (attempt {task.retries}/{task.max_retries})"
        retry_evidence = [
            f"retry_count: {task.retries}",
            f"max_retries: {task.max_retries}",
            f"previous_error: {task.error[:100] if task.error else 'none'}",
            f"delay: {0.5 * task.retries}s",
        ]
        
        # Analyze failure for retry strategy
        if task.error:
            if "timeout" in task.error.lower():
                retry_reasoning += " - previous failure was timeout, may succeed with retry"
                retry_evidence.append("failure_type: timeout")
            elif "connection" in task.error.lower():
                retry_reasoning += " - connection issue detected, retry may resolve"
                retry_evidence.append("failure_type: connection")
            else:
                retry_reasoning += " - retrying with same parameters"
                retry_evidence.append("failure_type: unknown")
        
        task.add_reasoning("action", retry_reasoning, 0.6, retry_evidence)
        
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
        """Delegate a sub-task from a parent task with reasoning.
        
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
        
        # Reasoning about delegation
        delegation_reasoning = f"Delegating sub-task from {parent_task_id}"
        delegation_evidence = [
            f"parent_id: {parent_task_id}",
            f"parent_status: {parent.status.value}",
            f"subtask_intent: {intent}",
        ]
        
        if priority is None:
            priority = parent.priority
            delegation_reasoning += f" - inherited priority {priority.name} from parent"
            delegation_evidence.append(f"priority_source: inherited")
        else:
            delegation_reasoning += f" - explicit priority {priority.name}"
            delegation_evidence.append(f"priority_source: explicit")
        
        if agent:
            delegation_reasoning += f" - assigned to {agent.value}"
            delegation_evidence.append(f"assigned_agent: {agent.value}")
        else:
            delegation_reasoning += " - agent will be auto-selected"
            delegation_evidence.append("agent_selection: auto")
        
        parent.add_reasoning("analysis", delegation_reasoning, 0.75, delegation_evidence)
        
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
        
        # Link reasoning between parent and child
        task.add_reasoning(
            "observation",
            f"Created as sub-task of {parent_task_id}",
            0.8,
            [f"parent_id: {parent_task_id}", f"parent_intent: {parent.intent}"]
        )
        
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
