"""Swarm Mode - Parallel multi-agent coordination for complex tasks.

Provides automatic task decomposition, parallel agent dispatch, agent-to-agent
messaging, and result aggregation for the CrackedCode orchestration system.

Features:
- Automatic decomposition of complex prompts into parallel subtasks
- Parallel dispatch across 11 agent roles with ThreadPoolExecutor
- Agent-to-agent message bus for real-time communication
- Result aggregation with configurable strategies
- Real-time progress callbacks for GUI integration
"""

import uuid
import json
import time
import threading
import concurrent.futures
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Callable, Any, Tuple
from collections import defaultdict
from datetime import datetime

from src.logger_config import get_logger

logger = get_logger("SwarmCoordinator")


class SwarmStrategy(Enum):
    """Result aggregation strategies for swarm execution."""
    SEQUENTIAL = "sequential"       # Execute subtasks one at a time
    PARALLEL = "parallel"          # All subtasks at once
    PARALLEL_THEN_MERGE = "merge"  # Parallel + LLM merge at end
    DEBATE = "debate"              # Agents debate before producing final output
    SUPERVISED = "supervised"       # Supervisor oversees subtask execution


@dataclass
class SwarmTask:
    """A single subtask within a swarm execution."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    prompt: str = ""
    agent_role: str = "coder"
    dependencies: List[str] = field(default_factory=list)
    priority: int = 1
    context: Dict[str, Any] = field(default_factory=dict)
    result: Any = None
    output: str = ""
    status: str = "pending"
    error: str = ""
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    @property
    def duration(self) -> float:
        end = self.completed_at or time.time()
        start = self.started_at or time.time()
        return end - start

    @property
    def is_terminal(self) -> bool:
        return self.status in ("completed", "failed", "cancelled")

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "prompt": self.prompt[:80] + "..." if len(self.prompt) > 80 else self.prompt,
            "agent_role": self.agent_role,
            "status": self.status,
            "dependencies": self.dependencies,
            "duration": round(self.duration, 2),
            "has_result": self.result is not None,
            "has_error": bool(self.error),
        }


@dataclass
class AgentMessage:
    """Message exchanged between agents during swarm execution."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    from_agent: str = ""
    to_agent: str = ""
    content: str = ""
    timestamp: float = field(default_factory=time.time)
    message_type: str = "info"

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "from": self.from_agent,
            "to": self.to_agent,
            "type": self.message_type,
            "content": self.content[:100] + "..." if len(self.content) > 100 else self.content,
            "timestamp": self.timestamp,
        }


class MessageBus:
    """Thread-safe message bus for agent-to-agent communication."""

    def __init__(self):
        self._messages: List[AgentMessage] = []
        self._lock = threading.RLock()
        self._callbacks: Dict[str, List[Callable]] = defaultdict(list)

    def send(self, message: AgentMessage):
        with self._lock:
            self._messages.append(message)
        for cb in self._callbacks.get(message.to_agent, []):
            try:
                cb(message)
            except Exception as e:
                logger.error(f"MessageBus callback error: {e}")
        for cb in self._callbacks.get("*", []):
            try:
                cb(message)
            except Exception as e:
                logger.error(f"MessageBus global callback error: {e}")

    def receive(self, agent_id: str, since: float = 0) -> List[AgentMessage]:
        with self._lock:
            return [
                m for m in self._messages
                if m.to_agent in (agent_id, "*") and m.timestamp >= since
            ]

    def broadcast(self, from_agent: str, content: str, message_type: str = "info"):
        msg = AgentMessage(
            from_agent=from_agent,
            to_agent="*",
            content=content,
            message_type=message_type,
        )
        self.send(msg)

    def subscribe(self, agent_id: str, callback: Callable):
        with self._lock:
            self._callbacks[agent_id].append(callback)

    def get_all_messages(self, since: float = 0) -> List[AgentMessage]:
        with self._lock:
            return [m for m in self._messages if m.timestamp >= since]

    def clear(self):
        with self._lock:
            self._messages.clear()


@dataclass
class SwarmResult:
    """Complete result of a swarm execution."""
    swarm_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    prompt: str = ""
    strategy: SwarmStrategy = SwarmStrategy.PARALLEL_THEN_MERGE
    tasks: List[SwarmTask] = field(default_factory=list)
    aggregated_output: str = ""
    task_results: Dict[str, Any] = field(default_factory=dict)
    messages: List[AgentMessage] = field(default_factory=list)
    status: str = "running"
    consensus_score: float = 0.0
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    error: str = ""

    @property
    def execution_time(self) -> float:
        end = self.completed_at or time.time()
        return end - self.started_at

    @property
    def is_terminal(self) -> bool:
        return self.status in ("completed", "failed", "cancelled")

    @property
    def all_tasks_completed(self) -> bool:
        return all(t.is_terminal for t in self.tasks)

    @property
    def success_count(self) -> int:
        return sum(1 for t in self.tasks if t.status == "completed")

    @property
    def fail_count(self) -> int:
        return sum(1 for t in self.tasks if t.status == "failed")

    def to_dict(self) -> Dict:
        return {
            "swarm_id": self.swarm_id,
            "strategy": self.strategy.value,
            "status": self.status,
            "tasks": [t.to_dict() for t in self.tasks],
            "messages": len(self.messages),
            "success_count": self.success_count,
            "fail_count": self.fail_count,
            "execution_time": round(self.execution_time, 2),
            "has_output": bool(self.aggregated_output),
            "has_error": bool(self.error),
        }


class SwarmCoordinator:
    """Coordinates parallel multi-agent execution (Swarm Mode).

    Integrates with UnifiedOrchestrator for agent role definitions and with
    the engine for LLM processing. Adds swarm-specific capabilities:
    - Task decomposition (complex prompt -> parallel subtasks)
    - Parallel dispatch across agent roles
    - Agent-to-agent messaging during execution
    - Result aggregation with configurable strategies
    """

    def __init__(
        self,
        engine=None,
        orchestrator=None,
        max_workers: int = 4,
    ):
        self.engine = engine
        self.orchestrator = orchestrator
        self.max_workers = max_workers
        self.message_bus = MessageBus()
        self._swarms: Dict[str, SwarmResult] = {}
        self._lock = threading.RLock()

        # Callbacks
        self.on_swarm_started: Optional[Callable[[SwarmResult], None]] = None
        self.on_swarm_completed: Optional[Callable[[SwarmResult], None]] = None
        self.on_task_update: Optional[Callable[[SwarmTask], None]] = None
        self.on_message: Optional[Callable[[AgentMessage], None]] = None

    def process(
        self,
        prompt: str,
        strategy: SwarmStrategy = SwarmStrategy.PARALLEL_THEN_MERGE,
        context: Optional[Dict] = None,
        fast: bool = False,
    ) -> SwarmResult:
        """End-to-end swarm processing: decompose -> dispatch -> aggregate.

        Args:
            prompt: User prompt
            strategy: Execution strategy
            context: Optional context dict
            fast: If True, skip LLM-based aggregation for speed

        Returns:
            SwarmResult with per-task results and aggregated output
        """
        if not prompt or not prompt.strip():
            result = SwarmResult(prompt=prompt, status="failed", error="Empty prompt")
            return result

        if fast:
            strategy = SwarmStrategy.PARALLEL

        result = SwarmResult(prompt=prompt, strategy=strategy)
        result.started_at = time.time()

        with self._lock:
            self._swarms[result.swarm_id] = result

        logger.info(f"Swarm {result.swarm_id} starting with strategy {strategy.value}")

        if self.on_swarm_started:
            try:
                self.on_swarm_started(result)
            except Exception as e:
                logger.error(f"Swarm started callback error: {e}")

        try:
            # 1. Decompose prompt into parallel subtasks
            tasks = self.decompose(prompt, context)
            result.tasks = tasks

            if not tasks:
                result.status = "failed"
                result.error = "Failed to decompose prompt into subtasks"
                result.completed_at = time.time()
                if self.on_swarm_completed:
                    try:
                        self.on_swarm_completed(result)
                    except Exception:
                        pass
                return result

            # 2. Dispatch tasks in parallel
            self._dispatch_parallel(result)

            # 3. Aggregate results
            if strategy == SwarmStrategy.PARALLEL_THEN_MERGE:
                result.aggregated_output = self._aggregate(prompt, result.tasks)

            result.status = "completed"
            result.completed_at = time.time()

            # Calculate consensus score
            if result.tasks:
                result.consensus_score = result.success_count / len(result.tasks)

            logger.info(
                f"Swarm {result.swarm_id} completed: "
                f"{result.success_count}/{len(result.tasks)} tasks succeeded"
            )

        except Exception as e:
            logger.error(f"Swarm {result.swarm_id} failed: {e}")
            result.status = "failed"
            result.error = str(e)
            result.completed_at = time.time()

        # Capture messages
        result.messages = self.message_bus.get_all_messages(since=result.started_at)

        if self.on_swarm_completed:
            try:
                self.on_swarm_completed(result)
            except Exception as e:
                logger.error(f"Swarm completed callback error: {e}")

        return result

    def decompose(
        self,
        prompt: str,
        context: Optional[Dict] = None,
    ) -> List[SwarmTask]:
        """Analyze a complex prompt and decompose into parallel subtasks.

        Uses the SUPERVISOR agent to plan the decomposition. Falls back to
        a single-task plan if the LLM is unavailable.

        Args:
            prompt: The complex user prompt
            context: Optional context

        Returns:
            List of SwarmTask objects for parallel execution
        """
        decomposition_prompt = (
            "You are a supervisor agent that plans parallel coding tasks.\n"
            "Analyze the following user request and decompose it into INDEPENDENT "
            "subtasks that can be executed in parallel by different specialist agents.\n\n"
            "Available agent roles:\n"
            "- architect: design, plan, structure\n"
            "- coder: code, write, generate, implement\n"
            "- executor: run, execute, test, shell\n"
            "- reviewer: review, audit, assess\n"
            "- searcher: search, find, grep\n"
            "- tester: test, verify, validate\n"
            "- debugger: debug, fix, trace\n"
            "- documenter: document, explain\n"
            "- devops: docker, deploy, ci, monitor\n"
            "- security: scan, audit, check, secure\n\n"
            "Rules:\n"
            "1. Each subtask must be INDEPENDENT (no dependencies on other subtasks)\n"
            "2. Assign the most appropriate agent role to each subtask\n"
            "3. Keep subtasks focused and specific\n"
            "4. Output ONLY valid JSON array, no other text\n\n"
            "Output format:\n"
            '```json\n'
            '[\n'
            '  {\n'
            '    "prompt": "detailed subtask description",\n'
            '    "agent_role": "role_name",\n'
            '    "priority": 1\n'
            '  }\n'
            ']\n'
            '```\n\n'
            f"User request: {prompt}"
        )

        if context:
            decomposition_prompt += f"\n\nContext: {json.dumps(context)[:500]}"

        try:
            if self.engine and hasattr(self.engine, 'process_with_tools'):
                # Use non-async path for decomposition
                response = self._call_engine_sync(decomposition_prompt)
            elif self.engine:
                response = self._call_engine_sync(decomposition_prompt)
            else:
                response = None

            if response:
                tasks = self._parse_decomposition(response)
                if tasks:
                    logger.info(
                        f"Decomposed prompt into {len(tasks)} subtasks: "
                        f"{[t.agent_role for t in tasks]}"
                    )
                    return tasks

        except Exception as e:
            logger.warning(f"Decomposition via LLM failed: {e}, falling back to single task")

        # Fallback: create a single coder task
        return [SwarmTask(prompt=prompt, agent_role="coder", priority=1)]

    def _parse_decomposition(self, response: Any) -> List[SwarmTask]:
        """Parse LLM response into SwarmTask list."""
        text = ""
        if isinstance(response, str):
            text = response
        elif hasattr(response, 'output'):
            text = response.output
        elif hasattr(response, 'response'):
            text = response.response
        elif isinstance(response, dict):
            text = response.get("response", response.get("output", str(response)))
        else:
            text = str(response)

        # Extract JSON from markdown code blocks
        json_str = text.strip()
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0].strip()

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            # Try to find JSON array in the text
            start = json_str.find("[")
            end = json_str.rfind("]")
            if start != -1 and end != -1:
                try:
                    data = json.loads(json_str[start:end + 1])
                except json.JSONDecodeError:
                    return []
            else:
                return []

        tasks = []
        for item in data:
            if isinstance(item, dict) and "prompt" in item:
                tasks.append(SwarmTask(
                    prompt=item["prompt"],
                    agent_role=item.get("agent_role", "coder"),
                    priority=item.get("priority", 1),
                    dependencies=item.get("dependencies", []),
                ))

        return tasks

    def _dispatch_parallel(self, result: SwarmResult):
        """Execute all swarm tasks in parallel using thread pool."""
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(self.max_workers, len(result.tasks))
        ) as executor:
            future_to_task = {
                executor.submit(self._execute_single_task, task): task
                for task in result.tasks
            }

            for future in concurrent.futures.as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Task {task.id} execution error: {e}")
                    task.status = "failed"
                    task.error = str(e)

    def _execute_single_task(self, task: SwarmTask):
        """Execute a single swarm task via the appropriate agent."""
        task.started_at = time.time()
        task.status = "running"

        if self.on_task_update:
            try:
                self.on_task_update(task)
            except Exception:
                pass

        logger.info(f"Swarm task {task.id} starting on {task.agent_role} agent")

        try:
            # Build a prompt that includes context and message bus history
            execution_prompt = task.prompt

            # Add relevant messages from the bus
            messages = self.message_bus.receive(task.agent_role, since=task.started_at - 60)
            if messages:
                msg_context = "\n\nMessages from other agents:\n"
                for m in messages:
                    msg_context += f"[{m.from_agent} -> {m.to_agent}]: {m.content}\n"
                execution_prompt += msg_context

            # Execute via engine
            response = self._call_engine_sync(execution_prompt)

            if response:
                output = ""
                if isinstance(response, str):
                    output = response
                elif hasattr(response, 'output'):
                    output = response.output
                elif hasattr(response, 'response'):
                    output = response.response
                elif isinstance(response, dict):
                    output = response.get("response", response.get("output", str(response)))
                else:
                    output = str(response)

                task.output = output
                task.result = response
                task.status = "completed"

                # Broadcast completion to other agents
                self.message_bus.broadcast(
                    task.agent_role,
                    f"Task '{task.prompt[:50]}...' completed successfully ({len(output)} chars)"
                )
            else:
                task.status = "failed"
                task.error = "Engine returned no response"
                self.message_bus.broadcast(
                    task.agent_role,
                    f"Task '{task.prompt[:50]}...' failed: no response",
                    "error"
                )

        except Exception as e:
            logger.error(f"Swarm task {task.id} failed: {e}")
            task.status = "failed"
            task.error = str(e)
            self.message_bus.broadcast(
                task.agent_role,
                f"Task '{task.prompt[:50]}...' failed: {str(e)}",
                "error"
            )

        task.completed_at = time.time()

        if self.on_task_update:
            try:
                self.on_task_update(task)
            except Exception:
                pass

    def _aggregate(self, original_prompt: str, tasks: List[SwarmTask]) -> str:
        """Aggregate results from parallel tasks into a coherent output."""
        completed = [t for t in tasks if t.status == "completed"]

        if not completed:
            return "No tasks completed successfully."

        if len(completed) == 1:
            return completed[0].output

        # Build a summary of all results
        parts = []
        for task in completed:
            agent_label = task.agent_role.upper()
            output_preview = task.output[:500] if task.output else "(empty)"
            parts.append(f"=== {agent_label}: {task.prompt[:60]} ===\n{output_preview}")

        all_results = "\n\n".join(parts)

        # Use LLM to merge results if engine is available
        try:
            merge_prompt = (
                "You are a senior engineer merging outputs from multiple specialist agents "
                "who worked in parallel on different parts of a task.\n\n"
                f"Original request: {original_prompt}\n\n"
                f"Agent outputs:\n\n{all_results}\n\n"
                "Merge these outputs into a single coherent response. "
                "Remove duplication, resolve conflicts, and organize logically. "
                "Keep the best contributions from each agent."
            )

            merged = self._call_engine_sync(merge_prompt)

            if merged:
                if isinstance(merged, str):
                    return merged
                if hasattr(merged, 'output') and merged.output:
                    return merged.output
                if hasattr(merged, 'response') and merged.response:
                    return merged.response
                if isinstance(merged, dict):
                    return merged.get("response", merged.get("output", str(merged)))
                return str(merged)

        except Exception as e:
            logger.warning(f"LLM aggregation failed: {e}, using basic concatenation")

        # Fallback: basic concatenation
        return all_results

    def _call_engine_sync(self, prompt: str) -> Any:
        """Call the engine synchronously, handling both sync and async."""
        if not self.engine:
            return None

        if hasattr(self.engine, 'process') and callable(self.engine.process):
            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            if loop.is_running():
                # Run in a separate thread
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, self.engine.process(prompt))
                    return future.result(timeout=120)
            else:
                return loop.run_until_complete(self.engine.process(prompt))

        return None

    def process_serial(
        self,
        prompt: str,
        context: Optional[Dict] = None,
    ) -> SwarmResult:
        """Process a prompt in serial mode (tasks execute sequentially).

        Useful for tasks where order matters (e.g., architect designs first,
        then coder implements).
        """
        result = SwarmResult(prompt=prompt, strategy=SwarmStrategy.SEQUENTIAL)

        with self._lock:
            self._swarms[result.swarm_id] = result

        if self.on_swarm_started:
            try:
                self.on_swarm_started(result)
            except Exception:
                pass

        try:
            tasks = self.decompose(prompt, context)
            result.tasks = tasks

            for task in tasks:
                self._execute_single_task(task)
                # After each task, allow next task to see previous results
                if task.status == "completed":
                    for next_task in tasks:
                        if task.id in next_task.dependencies:
                            next_task.context["previous_output"] = task.output

            result.status = "completed"
            result.completed_at = time.time()

            # Build aggregated output
            parts = []
            for t in tasks:
                if t.status == "completed" and t.output:
                    parts.append(t.output)
            result.aggregated_output = "\n\n".join(parts)

            if tasks:
                result.consensus_score = result.success_count / len(tasks)

        except Exception as e:
            result.status = "failed"
            result.error = str(e)
            result.completed_at = time.time()

        result.messages = self.message_bus.get_all_messages(since=result.started_at)

        if self.on_swarm_completed:
            try:
                self.on_swarm_completed(result)
            except Exception:
                pass

        return result

    def process_with_debate(
        self,
        prompt: str,
        rounds: int = 2,
    ) -> SwarmResult:
        """Process with debate between coder and reviewer agents.

        The coder produces a solution, then the reviewer critiques it, and
        they iterate for the specified number of rounds.
        """
        result = SwarmResult(prompt=prompt, strategy=SwarmStrategy.DEBATE)

        with self._lock:
            self._swarms[result.swarm_id] = result

        if self.on_swarm_started:
            try:
                self.on_swarm_started(result)
            except Exception:
                pass

        try:
            # Round 1: Coder produces initial solution
            coder_task = SwarmTask(
                prompt=f"Write a solution for:\n{prompt}\n\nProvide complete implementation.",
                agent_role="coder",
                priority=1,
            )
            result.tasks.append(coder_task)
            self._execute_single_task(coder_task)

            for round_num in range(rounds):
                if coder_task.status != "completed":
                    break

                # Reviewer critiques
                reviewer_task = SwarmTask(
                    prompt=(
                        f"Review the following solution and provide detailed feedback:\n\n"
                        f"Original request: {prompt}\n\n"
                        f"Solution:\n{coder_task.output}\n\n"
                        f"Analyze correctness, performance, security, and code quality. "
                        f"Be specific about issues."
                    ),
                    agent_role="reviewer",
                    priority=1,
                )
                result.tasks.append(reviewer_task)
                self._execute_single_task(reviewer_task)

                if reviewer_task.status != "completed":
                    break

                # Coder revises based on feedback
                coder_task = SwarmTask(
                    prompt=(
                        f"Original request: {prompt}\n\n"
                        f"Your previous solution:\n{coder_task.output}\n\n"
                        f"Reviewer feedback:\n{reviewer_task.output}\n\n"
                        f"Revise your solution to address all feedback. "
                        f"Provide the improved complete solution."
                    ),
                    agent_role="coder",
                    priority=1,
                )
                result.tasks.append(coder_task)
                self._execute_single_task(coder_task)

            result.status = "completed"
            result.completed_at = time.time()

            if coder_task.status == "completed":
                result.aggregated_output = coder_task.output

            if result.tasks:
                result.consensus_score = result.success_count / len(result.tasks)

        except Exception as e:
            result.status = "failed"
            result.error = str(e)
            result.completed_at = time.time()

        result.messages = self.message_bus.get_all_messages(since=result.started_at)

        if self.on_swarm_completed:
            try:
                self.on_swarm_completed(result)
            except Exception:
                pass

        return result

    def get_swarm(self, swarm_id: str) -> Optional[SwarmResult]:
        """Get a swarm result by ID."""
        with self._lock:
            return self._swarms.get(swarm_id)

    def get_active_swarms(self) -> List[SwarmResult]:
        """Get all currently running swarms."""
        with self._lock:
            return [s for s in self._swarms.values() if s.status == "running"]

    def get_swarm_status(self, swarm_id: str) -> Optional[Dict]:
        """Get status dict for a swarm."""
        result = self.get_swarm(swarm_id)
        if result:
            return result.to_dict()
        return None

    def get_all_swarms(self) -> List[Dict]:
        """Get all swarms as status dicts."""
        with self._lock:
            return [s.to_dict() for s in self._swarms.values()]

    def get_stats(self) -> Dict[str, Any]:
        """Get swarm coordinator statistics."""
        with self._lock:
            total = len(self._swarms)
            active = sum(1 for s in self._swarms.values() if s.status == "running")
            completed = sum(1 for s in self._swarms.values() if s.status == "completed")
            failed = sum(1 for s in self._swarms.values() if s.status == "failed")
            total_tasks = sum(len(s.tasks) for s in self._swarms.values())
            total_messages = sum(len(s.messages) for s in self._swarms.values())

        return {
            "total_swarms": total,
            "active": active,
            "completed": completed,
            "failed": failed,
            "total_tasks": total_tasks,
            "total_messages": total_messages,
            "max_workers": self.max_workers,
            "strategies": [s.value for s in SwarmStrategy],
        }


# Global singleton
_swarm_coordinator: Optional[SwarmCoordinator] = None


def get_swarm_coordinator(engine=None, orchestrator=None, max_workers: int = 4) -> SwarmCoordinator:
    """Get or create the global SwarmCoordinator singleton."""
    global _swarm_coordinator
    if _swarm_coordinator is None:
        _swarm_coordinator = SwarmCoordinator(engine, orchestrator, max_workers)
    return _swarm_coordinator
