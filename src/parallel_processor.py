#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║        CRACKEDCODE: PARALLEL NEURAL PROCESSOR SYSTEM                  ║
║              MULTI-CORE TASK EXECUTION ENGINE                          ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════════════╝

A comprehensive parallel processing system supporting multiple execution
modes including sequential, parallel, distributed, pipeline, and unified
resolution patterns.

Features:
- Thread and process-based worker pools
- Task dependency management
- Priority queue execution
- Pipeline processing stages
- Unified resolution coordination
- Result aggregation and reporting
"""

import os
import sys
import json
import time
import threading
import queue
import multiprocessing
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed, Future
from concurrent.futures import wait, FIRST_COMPLETED, ALL_COMPLETED
from typing import Optional, List, Dict, Any, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging
import traceback
import random
import statistics

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('ParallelProcessor')


# ============================================================================
# PARALLEL EXECUTION MODES
# ============================================================================

class ExecutionMode(Enum):
    """Defines the execution mode for parallel tasks."""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    DISTRIBUTED = "distributed"
    PIPELINE = "pipeline"
    UNIFIED = "unified"


class TaskPriority(Enum):
    """Priority levels for task execution."""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class TaskStatus(Enum):
    """Status of task execution."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass
class TaskResult:
    """
    Represents the result of a single task execution.
    
    Attributes:
        task_id: Unique identifier for the task
        status: Current execution status
        result: The actual result data
        error: Error message if task failed
        duration: Execution time in seconds
        start_time: When task started executing
        end_time: When task finished executing
        worker_id: ID of worker that executed the task
        metadata: Additional metadata about execution
    """
    task_id: str
    status: TaskStatus
    result: Any = None
    error: Optional[str] = None
    duration: float = 0.0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    worker_id: Optional[str] = None
    metadata: Dict = field(default_factory=dict)
    
    @property
    def success(self) -> bool:
        """Check if task completed successfully."""
        return self.status == TaskStatus.COMPLETED and self.error is None
    
    @property
    def duration_ms(self) -> int:
        """Get duration in milliseconds."""
        return int(self.duration * 1000)
    
    def to_dict(self) -> Dict:
        """Convert result to dictionary for serialization."""
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "duration": self.duration,
            "duration_ms": self.duration_ms,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "worker_id": self.worker_id,
            "metadata": self.metadata,
            "success": self.success
        }


@dataclass
class ParallelTask:
    """
    Represents a task to be executed in parallel.
    
    Attributes:
        task_id: Unique identifier for the task
        func: Callable function to execute
        args: Positional arguments for the function
        kwargs: Keyword arguments for the function
        priority: Task priority for queue ordering
        timeout: Maximum execution time in seconds
        retries: Current retry count
        max_retries: Maximum number of retries on failure
        depends_on: List of task IDs that must complete first
        metadata: Additional task metadata
        result: Task result after execution
    """
    task_id: str
    func: Callable
    args: Tuple = field(default_factory=tuple)
    kwargs: Dict = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    timeout: Optional[float] = None
    retries: int = 0
    max_retries: int = 0
    depends_on: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    result: Optional[TaskResult] = None


class WorkerState(Enum):
    """State of a worker in the pool."""
    IDLE = "idle"
    BUSY = "busy"
    DONE = "done"
    ERROR = "error"


# ============================================================================
# WORKER POOL MANAGEMENT
# ============================================================================

class WorkerPool:
    """
    Manages a pool of workers for parallel task execution.
    
    Supports both thread-based and process-based execution modes.
    Workers are dynamically allocated and released as tasks complete.
    
    Attributes:
        max_workers: Maximum number of workers in pool
        use_processes: If True, use process-based execution
    """
    
    def __init__(self, max_workers: int = None, use_processes: bool = False):
        """
        Initialize the worker pool.
        
        Args:
            max_workers: Maximum number of workers (default: CPU count)
            use_processes: Use process-based execution instead of threads
        """
        self.max_workers = max_workers or multiprocessing.cpu_count()
        self.use_processes = use_processes
        
        if use_processes:
            self.executor_class = ProcessPoolExecutor
            logger.info(f"Using process-based execution with {self.max_workers} workers")
        else:
            self.executor_class = ThreadPoolExecutor
            logger.info(f"Using thread-based execution with {self.max_workers} workers")
            
        self.executor: Optional[Any] = None
        self.workers: Dict[str, Dict] = {}
        self.available_workers: queue.Queue = queue.Queue()
        self.active_count = 0
        self.lock = threading.Lock()
        
        self._initialize_workers()
        
    def _initialize_workers(self):
        """Initialize worker metadata."""
        for i in range(self.max_workers):
            worker_id = f"worker_{i:03d}"
            self.workers[worker_id] = {
                "id": worker_id,
                "state": WorkerState.IDLE,
                "tasks_completed": 0,
                "current_task": None,
                "start_time": None,
            }
            self.available_workers.put(worker_id)
        logger.debug(f"Initialized {self.max_workers} workers")
            
    def start(self):
        """Start the worker pool executor."""
        if self.executor is None:
            self.executor = self.executor_class(max_workers=self.max_workers)
            logger.info("Worker pool started")
            
    def stop(self, wait: bool = True, timeout: float = None):
        """
        Stop the worker pool.
        
        Args:
            wait: If True, wait for pending tasks to complete
            timeout: Maximum time to wait for tasks
        """
        if self.executor:
            self.executor.shutdown(wait=wait, cancel_futures=False)
            self.executor = None
            logger.info("Worker pool stopped")
            
    def get_worker(self, timeout: float = 1.0) -> Optional[str]:
        """
        Get an available worker from the pool.
        
        Args:
            timeout: Maximum time to wait for a worker
            
        Returns:
            Worker ID if available, None otherwise
        """
        try:
            worker_id = self.available_workers.get(timeout=timeout)
            
            with self.lock:
                if worker_id in self.workers:
                    self.workers[worker_id]["state"] = WorkerState.BUSY
                    self.active_count += 1
                    
            return worker_id
            
        except queue.Empty:
            return None
            
    def release_worker(self, worker_id: str):
        """
        Release a worker back to the pool.
        
        Args:
            worker_id: ID of worker to release
        """
        with self.lock:
            if worker_id in self.workers:
                self.workers[worker_id]["state"] = WorkerState.IDLE
                self.workers[worker_id]["tasks_completed"] += 1
                self.active_count = max(0, self.active_count - 1)
                
        self.available_workers.put(worker_id)
        
    def get_stats(self) -> Dict:
        """Get statistics about the worker pool."""
        return {
            "max_workers": self.max_workers,
            "active": self.active_count,
            "available": self.available_workers.qsize(),
            "states": {w["state"].value: w["tasks_completed"] for w in self.workers.values()}
        }


# ============================================================================
# PARALLEL TASK EXECUTOR
# ============================================================================

class ParallelExecutor:
    """
    Executes tasks in parallel using a worker pool.
    
    Supports sequential and parallel execution modes, task dependencies,
    priority queuing, and automatic retry logic.
    
    Attributes:
        mode: Execution mode for tasks
        pool: Worker pool for execution
        tasks: Dictionary of submitted tasks
        results: Dictionary of task results
        task_queue: Priority queue for tasks
        futures: Dictionary of future objects
        running: Whether executor is currently running
    """
    
    def __init__(self, max_workers: int = None, mode: ExecutionMode = ExecutionMode.PARALLEL):
        """
        Initialize the parallel executor.
        
        Args:
            max_workers: Maximum number of workers
            mode: Execution mode
        """
        self.mode = mode
        self.pool = WorkerPool(max_workers=max_workers)
        self.tasks: Dict[str, ParallelTask] = {}
        self.results: Dict[str, TaskResult] = {}
        self.task_queue: queue.PriorityQueue = queue.PriorityQueue()
        self.futures: Dict[str, Future] = {}
        self.lock = threading.Lock()
        self.running = False
        
    def start(self):
        """Start the executor and worker pool."""
        self.running = True
        self.pool.start()
        logger.info(f"ParallelExecutor started in {self.mode.value} mode")
        
    def stop(self, wait: bool = True, timeout: float = None):
        """
        Stop the executor.
        
        Args:
            wait: Wait for pending tasks
            timeout: Maximum wait time
        """
        self.running = False
        self.pool.stop(wait=wait, timeout=timeout)
        logger.info("ParallelExecutor stopped")
        
    def submit(self, task: ParallelTask) -> str:
        """
        Submit a task for execution.
        
        Args:
            task: Task to submit
            
        Returns:
            Task ID
        """
        with self.lock:
            self.tasks[task.task_id] = task
            self.results[task.task_id] = TaskResult(
                task_id=task.task_id,
                status=TaskStatus.PENDING,
                start_time=datetime.now()
            )
            
        self.task_queue.put((task.priority.value, task.task_id))
        
        if self.running:
            self._execute_task_async(task)
            
        return task.task_id
        
    def submit_batch(self, tasks: List[ParallelTask]) -> List[str]:
        """
        Submit multiple tasks for execution.
        
        Args:
            tasks: List of tasks to submit
            
        Returns:
            List of task IDs
        """
        task_ids = []
        
        if self.mode == ExecutionMode.SEQUENTIAL:
            for task in tasks:
                task_ids.append(self.submit(task))
                self.wait_for([task.task_id])
        else:
            for task in tasks:
                task_ids.append(self.submit(task))
                
        return task_ids
        
    def _execute_task_async(self, task: ParallelTask):
        """Execute a task asynchronously."""
        worker_id = self.pool.get_worker(timeout=0.1)
        
        if worker_id:
            future = self.pool.executor.submit(
                self._execute_task_wrapper,
                task,
                worker_id
            )
            self.futures[task.task_id] = future
        else:
            future = self.pool.executor.submit(
                self._execute_task_wrapper,
                task,
                "worker_pool"
            )
            self.futures[task.task_id] = future
            
    def _execute_task_wrapper(self, task: ParallelTask, worker_id: str) -> TaskResult:
        """Wrapper for task execution with error handling."""
        start_time = time.time()
        
        self.results[task.task_id].status = TaskStatus.RUNNING
        self.results[task.task_id].worker_id = worker_id
        
        if task.depends_on:
            for dep_id in task.depends_on:
                if dep_id in self.results:
                    dep_result = self.results[dep_id]
                    if not dep_result.success:
                        return TaskResult(
                            task_id=task.task_id,
                            status=TaskStatus.FAILED,
                            error=f"Dependency {dep_id} failed",
                            duration=time.time() - start_time,
                            worker_id=worker_id
                        )
                        
        try:
            if task.timeout:
                result = task.func(*task.args, timeout=task.timeout, **task.kwargs)
            else:
                result = task.func(*task.args, **task.kwargs)
                
            duration = time.time() - start_time
            
            task_result = TaskResult(
                task_id=task.task_id,
                status=TaskStatus.COMPLETED,
                result=result,
                duration=duration,
                start_time=datetime.now(),
                end_time=datetime.now(),
                worker_id=worker_id
            )
            
        except Exception as e:
            duration = time.time() - start_time
            
            if task.retries < task.max_retries:
                task.retries += 1
                return self._execute_task_wrapper(task, worker_id)
                
            task_result = TaskResult(
                task_id=task.task_id,
                status=TaskStatus.FAILED,
                error=str(e),
                duration=duration,
                start_time=datetime.now(),
                end_time=datetime.now(),
                worker_id=worker_id,
                metadata={"traceback": traceback.format_exc()}
            )
            
        self.results[task.task_id] = task_result
        
        if worker_id != "worker_pool":
            self.pool.release_worker(worker_id)
            
        return task_result
        
    def get_result(self, task_id: str, timeout: float = None) -> Optional[TaskResult]:
        """
        Get the result of a task.
        
        Args:
            task_id: Task ID
            timeout: Optional timeout for waiting
            
        Returns:
            Task result or None
        """
        if task_id in self.futures:
            future = self.futures[task_id]
            
            try:
                if timeout:
                    return future.result(timeout=timeout)
                else:
                    return future.result()
            except Exception as e:
                return TaskResult(
                    task_id=task_id,
                    status=TaskStatus.FAILED,
                    error=str(e),
                    worker_id=self.results.get(task_id, TaskResult(task_id=task_id, status=TaskStatus.PENDING)).worker_id
                )
                
        return self.results.get(task_id)
        
    def wait_for(self, task_ids: List[str], timeout: float = None, 
                return_when: str = "ALL_COMPLETED") -> Dict[str, TaskResult]:
        """
        Wait for tasks to complete.
        
        Args:
            task_ids: List of task IDs to wait for
            timeout: Maximum wait time
            return_when: When to return (FIRST_COMPLETED or ALL_COMPLETED)
            
        Returns:
            Dictionary of results keyed by task ID
        """
        if not task_ids:
            return {}
            
        futures_to_wait = {tid: self.futures[tid] for tid in task_ids if tid in self.futures}
        
        if not futures_to_wait:
            return {tid: self.results[tid] for tid in task_ids if tid in self.results}
            
        if return_when == "FIRST_COMPLETED":
            done, _ = wait(futures_to_wait.values(), return_when=FIRST_COMPLETED)
        else:
            wait(futures_to_wait.values(), return_when=ALL_COMPLETED)
            
        results = {}
        for tid in task_ids:
            results[tid] = self.get_result(tid)
            
        return results
        
    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a pending or running task.
        
        Args:
            task_id: Task ID to cancel
            
        Returns:
            True if cancelled, False otherwise
        """
        if task_id in self.futures:
            cancelled = self.futures[task_id].cancel()
            
            if cancelled:
                self.results[task_id].status = TaskStatus.CANCELLED
                return True
                
        return False
        
    def cancel_all(self):
        """Cancel all pending and running tasks."""
        for task_id in self.futures:
            self.cancel_task(task_id)
            
    def get_stats(self) -> Dict:
        """Get executor statistics."""
        stats = self.pool.get_stats()
        
        status_counts = {}
        for result in self.results.values():
            status = result.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
            
        return {
            "mode": self.mode.value,
            "total_tasks": len(self.tasks),
            "results_count": len(self.results),
            "pending": status_counts.get("pending", 0),
            "running": status_counts.get("running", 0),
            "completed": status_counts.get("completed", 0),
            "failed": status_counts.get("failed", 0),
            "worker_stats": stats
        }


# ============================================================================
# PIPELINE PROCESSOR
# ============================================================================

class PipelineStage:
    """
    Represents a single stage in a processing pipeline.
    
    Each stage processes data and passes the result to the next stage.
    
    Attributes:
        name: Stage name
        func: Processing function
        output_queue: Optional output queue name
        processed_count: Number of items processed
        error_count: Number of processing errors
    """
    
    def __init__(self, name: str, func: Callable, output_queue: str = None):
        """
        Initialize a pipeline stage.
        
        Args:
            name: Stage name
            func: Function to apply to data
            output_queue: Optional output queue name
        """
        self.name = name
        self.func = func
        self.output_queue = output_queue
        self.processed_count = 0
        self.error_count = 0
        
    def process(self, data: Any) -> Any:
        """
        Process data through this stage.
        
        Args:
            data: Input data
            
        Returns:
            Processed output
        """
        try:
            result = self.func(data)
            self.processed_count += 1
            return result
        except Exception as e:
            self.error_count += 1
            raise


class PipelineProcessor:
    """
    Processes data through multiple pipeline stages.
    
    Supports sequential and parallel execution of pipeline stages.
    
    Attributes:
        stages: Dictionary of pipeline stages
        executor: Parallel executor for parallel processing
    """
    
    def __init__(self, max_workers: int = 4):
        """
        Initialize the pipeline processor.
        
        Args:
            max_workers: Maximum number of workers
        """
        self.stages: Dict[str, PipelineStage] = {}
        self.executor = ParallelExecutor(max_workers=max_workers, mode=ExecutionMode.PIPELINE)
        
    def add_stage(self, name: str, func: Callable, output_queue: str = None) -> PipelineStage:
        """
        Add a stage to the pipeline.
        
        Args:
            name: Stage name
            func: Processing function
            output_queue: Optional output queue
            
        Returns:
            Created pipeline stage
        """
        stage = PipelineStage(name, func, output_queue)
        self.stages[name] = stage
        return stage
        
    def execute(self, data: Any, stage_order: List[str] = None) -> Any:
        """
        Execute pipeline on input data.
        
        Args:
            data: Input data
            stage_order: Optional order of stages
            
        Returns:
            Processed output
        """
        if stage_order is None:
            stage_order = list(self.stages.keys())
            
        current_data = data
        
        for stage_name in stage_order:
            if stage_name in self.stages:
                stage = self.stages[stage_name]
                current_data = stage.process(current_data)
                
        return current_data
        
    def execute_parallel(self, inputs: List[Any], stage_order: List[str] = None) -> List[Any]:
        """
        Execute pipeline on multiple inputs in parallel.
        
        Args:
            inputs: List of inputs
            stage_order: Optional order of stages
            
        Returns:
            List of outputs
        """
        if stage_order is None:
            stage_order = list(self.stages.keys())
            
        tasks = []
        for i, data in enumerate(inputs):
            task = ParallelTask(
                task_id=f"pipeline_{i}",
                func=self.execute,
                args=(data, stage_order),
                kwargs={}
            )
            tasks.append(task)
            
        return self.executor.submit_batch(tasks)


# ============================================================================
# UNIFIED RESOLUTION COORDINATOR
# ============================================================================

class ResolutionStrategy(Enum):
    """Strategy for resolving results from multiple workers."""
    FIRST_WINNER = "first_winner"
    MAJORITY = "majority"
    CONSENSUS = "consensus"
    UNANIMOUS = "unanimous"
    WEIGHTED = "weighted"


@dataclass
class UnifiedResolution:
    """
    Represents a unified resolution from multiple sub-results.
    
    Attributes:
        strategy: Resolution strategy used
        task_id: Original task ID
        sub_results: List of sub-task results
        final_result: Final resolved result
        consensus_score: Score indicating consensus level
        resolution_time: Time taken to resolve
    """
    strategy: ResolutionStrategy
    task_id: str
    sub_results: List[TaskResult] = field(default_factory=list)
    final_result: Any = None
    consensus_score: float = 0.0
    resolution_time: float = 0.0
    
    @property
    def is_resolved(self) -> bool:
        """Check if resolution is complete."""
        return self.final_result is not None
    
    @property
    def success(self) -> bool:
        """Check if resolution was successful."""
        if not self.sub_results:
            return False
        return self.final_result is not None


class UnifiedCoordinator:
    """
    Coordinates result resolution from multiple independent methods.
    
    Supports multiple resolution strategies including first winner,
    majority, consensus, and weighted averaging.
    
    Attributes:
        executor: Parallel executor for running sub-tasks
        strategy: Current resolution strategy
        resolutions: Dictionary of resolutions by task ID
    """
    
    def __init__(self, max_workers: int = 4):
        """
        Initialize the unified coordinator.
        
        Args:
            max_workers: Maximum number of workers
        """
        self.executor = ParallelExecutor(max_workers=max_workers, mode=ExecutionMode.UNIFIED)
        self.strategy = ResolutionStrategy.MAJORITY
        self.resolutions: Dict[str, UnifiedResolution] = {}
        
    def start(self):
        """Start the coordinator."""
        self.executor.start()
        
    def stop(self):
        """Stop the coordinator."""
        self.executor.stop()
        
    def submit_resolution_task(self, task_id: str, task_funcs: List[Callable], 
                         strategy: ResolutionStrategy = None) -> str:
        """
        Submit a resolution task with multiple methods.
        
        Args:
            task_id: Unique task ID
            task_funcs: List of functions to execute
            strategy: Resolution strategy
            
        Returns:
            Task ID
        """
        if strategy:
            self.strategy = strategy
            
        resolution = UnifiedResolution(
            strategy=self.strategy,
            task_id=task_id
        )
        self.resolutions[task_id] = resolution
        
        tasks = []
        for i, func in enumerate(task_funcs):
            sub_task = ParallelTask(
                task_id=f"{task_id}_sub{i}",
                func=func,
                args=(),
                kwargs={}
            )
            tasks.append(sub_task)
            
        self.executor.submit_batch(tasks)
        
        return task_id
        
    def resolve(self, task_id: str, timeout: float = None) -> UnifiedResolution:
        """
        Resolve results for a task using the configured strategy.
        
        Args:
            task_id: Task ID to resolve
            timeout: Optional timeout
            
        Returns:
            Unified resolution result
        """
        if task_id not in self.resolutions:
            return None
            
        resolution = self.resolutions[task_id]
        
        sub_task_ids = [f"{task_id}_sub{i}" for i in range(len(self.executor.tasks))]
        
        sub_results = []
        
        for tid in sub_task_ids:
            result = self.executor.get_result(tid, timeout=timeout)
            if result:
                sub_results.append(result)
                
        resolution.sub_results = sub_results
        resolution.resolution_time = time.time()
        
        if self.strategy == ResolutionStrategy.FIRST_WINNER:
            for result in sub_results:
                if result.success:
                    resolution.final_result = result.result
                    break
                    
        elif self.strategy == ResolutionStrategy.MAJORITY:
            success_count = sum(1 for r in sub_results if r.success)
            resolution.consensus_score = success_count / len(sub_results) if sub_results else 0
            
            if resolution.consensus_score > 0.5:
                for result in sub_results:
                    if result.success:
                        resolution.final_result = result.result
                        break
                        
        elif self.strategy == ResolutionStrategy.CONSENSUS:
            success_count = sum(1 for r in sub_results if r.success)
            resolution.consensus_score = success_count / len(sub_results) if sub_results else 0
            
            if resolution.consensus_score >= 0.8:
                results_with_values = [r.result for r in sub_results if r.success and r.result]
                if results_with_values:
                    resolution.final_result = results_with_values[0]
                    
        elif self.strategy == ResolutionStrategy.WEIGHTED:
            weighted_results = []
            
            for result in sub_results:
                if result.success:
                    weight = 1.0 / (result.duration + 0.001)
                    weighted_results.append((result.result, weight))
                    
            if weighted_results:
                total_weight = sum(w for _, w in weighted_results)
                resolution.final_result = sum(r * w for r, w in weighted_results) / total_weight
                
        return resolution
        
    def get_resolution(self, task_id: str) -> Optional[UnifiedResolution]:
        """Get resolution for a task."""
        return self.resolutions.get(task_id)
        
    def get_stats(self) -> Dict:
        """Get coordinator statistics."""
        return {
            "strategy": self.strategy.value,
            "resolutions": len(self.resolutions),
            "executor_stats": self.executor.get_stats()
        }


# ============================================================================
# DISTRIBUTED PROCESSOR
# ============================================================================

class DistributedProcessor:
    """
    Manages task distribution across multiple nodes.
    
    Provides round-robin task dispatching and node management.
    
    Attributes:
        nodes: List of available nodes
        current_node: Current node index for round-robin
        results: Dictionary of task results by node
    """
    
    def __init__(self, nodes: List[str] = None):
        """
        Initialize the distributed processor.
        
        Args:
            nodes: List of node addresses
        """
        self.nodes = nodes or ["localhost"]
        self.current_node = 0
        self.results: Dict[str, Dict] = {}
        self.lock = threading.Lock()
        
    def add_node(self, node: str):
        """Add a node to the pool."""
        with self.lock:
            if node not in self.nodes:
                self.nodes.append(node)
                
    def remove_node(self, node: str):
        """Remove a node from the pool."""
        with self.lock:
            if node in self.nodes:
                self.nodes.remove(node)
                
    def get_next_node(self) -> str:
        """Get the next node in round-robin order."""
        with self.lock:
            if not self.nodes:
                raise RuntimeError("No nodes available")
                
            node = self.nodes[self.current_node % len(self.nodes)]
            self.current_node += 1
            return node
            
    def dispatch_task(self, task: ParallelTask) -> str:
        """Dispatch a task to a node."""
        node = self.get_next_node()
        
        with self.lock:
            self.results[task.task_id] = {
                "node": node,
                "status": "dispatched",
                "dispatched_at": datetime.now()
            }
            
        return task.task_id
        
    def get_node_stats(self) -> Dict:
        """Get node statistics."""
        with self.lock:
            return {
                "total_nodes": len(self.nodes),
                "current_node": self.nodes[self.current_node % len(self.nodes)] if self.nodes else None,
                "tasks_dispatched": len(self.results)
            }


# ============================================================================
# RESULT AGGREGATOR
# ============================================================================

class ResultAggregator:
    """
    Aggregates results from multiple task executions.
    
    Provides statistical analysis and summary of execution results.
    
    Attributes:
        results: Dictionary of aggregated results
    """
    
    def __init__(self):
        """Initialize the result aggregator."""
        self.results: Dict[str, List[TaskResult]] = {}
        
    def add_result(self, task_id: str, result: TaskResult):
        """
        Add a result for aggregation.
        
        Args:
            task_id: Task identifier
            result: Task result to add
        """
        if task_id not in self.results:
            self.results[task_id] = []
        self.results[task_id].append(result)
        
    def add_results(self, results: Dict[str, TaskResult]):
        """
        Add multiple results.
        
        Args:
            results: Dictionary of results
        """
        for task_id, result in results.items():
            self.add_result(task_id, result)
            
    def get_summary(self, task_id: str = None) -> Dict:
        """
        Get summary statistics.
        
        Args:
            task_id: Optional specific task ID
            
        Returns:
            Summary dictionary
        """
        if task_id:
            results = self.results.get(task_id, [])
        else:
            results = [r for results_list in self.results.values() for r in results_list]
            
        if not results:
            return {"total": 0}
            
        durations = [r.duration for r in results]
        successful = [r for r in results if r.success]
        failed = [r for r in results if r.status == TaskStatus.FAILED]
        
        summary = {
            "total": len(results),
            "successful": len(successful),
            "failed": len(failed),
            "success_rate": len(successful) / len(results) if results else 0,
            "durations": {
                "min": min(durations) if durations else 0,
                "max": max(durations) if durations else 0,
                "avg": statistics.mean(durations) if durations else 0,
                "median": statistics.median(durations) if durations else 0,
                "stdev": statistics.stdev(durations) if len(durations) > 1 else 0,
            }
        }
        
        return summary
    
    def get_all_summaries(self) -> Dict[str, Dict]:
        """Get summaries for all task IDs."""
        return {task_id: self.get_summary(task_id) for task_id in self.results.keys()}
        
    def get_successful_results(self, task_id: str = None) -> List[Any]:
        """Get all successful results."""
        if task_id:
            results = self.results.get(task_id, [])
        else:
            results = [r for results_list in self.results.values() for r in results_list]
            
        return [r.result for r in results if r.success]
        
    def clear(self):
        """Clear all aggregated results."""
        self.results.clear()


class ResultReporter:
    """
    Generates reports from task execution results.
    
    Provides formatted output and export capabilities.
    
    Attributes:
        aggregator: Result aggregator
    """
    
    def __init__(self, aggregator: ResultAggregator = None):
        """
        Initialize the result reporter.
        
        Args:
            aggregator: Optional result aggregator
        """
        self.aggregator = aggregator or ResultAggregator()
        
    def generate_text_report(self, results: Dict[str, TaskResult]) -> str:
        """
        Generate a text report from results.
        
        Args:
            results: Dictionary of results
            
        Returns:
            Formatted text report
        """
        lines = []
        lines.append("=" * 60)
        lines.append("PARALLEL EXECUTION REPORT")
        lines.append("=" * 60)
        lines.append("")
        
        self.aggregator.add_results(results)
        
        total = len(results)
        successful = sum(1 for r in results.values() if r.success)
        failed = total - successful
        
        lines.append(f"Total Tasks: {total}")
        lines.append(f"Successful: {successful}")
        lines.append(f"Failed: {failed}")
        lines.append(f"Success Rate: {successful/total*100:.1f}%" if total > 0 else "Success Rate: 0%")
        lines.append("")
        
        summary = self.aggregator.get_summary()
        if summary.get("durations"):
            lines.append("Execution Times:")
            lines.append(f"  Min: {summary['durations']['min']*1000:.2f}ms")
            lines.append(f"  Max: {summary['durations']['max']*1000:.2f}ms")
            lines.append(f"  Avg: {summary['durations']['avg']*1000:.2f}ms")
            lines.append(f"  Median: {summary['durations']['median']*1000:.2f}ms")
        lines.append("")
        
        lines.append("Task Details:")
        for task_id, result in results.items():
            status_icon = "[OK]" if result.success else "[FAIL]"
            lines.append(f"  {status_icon} {task_id}")
            lines.append(f"       Status: {result.status.value}")
            lines.append(f"       Duration: {result.duration_ms}ms")
            if result.success and result.result is not None:
                lines.append(f"       Result: {result.result}")
            if result.error:
                lines.append(f"       Error: {result.error}")
            if result.worker_id:
                lines.append(f"       Worker: {result.worker_id}")
            lines.append("")
            
        lines.append("=" * 60)
        
        return "\n".join(lines)
        
    def generate_json_report(self, results: Dict[str, TaskResult]) -> str:
        """
        Generate a JSON report from results.
        
        Args:
            results: Dictionary of results
            
        Returns:
            JSON formatted string
        """
        self.aggregator.add_results(results)
        
        report = {
            "summary": self.aggregator.get_summary(),
            "results": {task_id: result.to_dict() for task_id, result in results.items()}
        }
        
        return json.dumps(report, indent=2)
        
    def print_report(self, results: Dict[str, TaskResult]):
        """Print a text report to console."""
        print(self.generate_text_report(results))


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_task(task_id: str, func: Callable, args: tuple = (), 
               kwargs: dict = None, priority: int = TaskPriority.NORMAL.value,
               timeout: float = None, depends_on: List[str] = None) -> ParallelTask:
    """
    Create a parallel task.
    
    Args:
        task_id: Unique task identifier
        func: Function to execute
        args: Positional arguments
        kwargs: Keyword arguments
        priority: Task priority (0-3)
        timeout: Maximum execution time
        depends_on: Task IDs this depends on
        
    Returns:
        Created parallel task
    """
    return ParallelTask(
        task_id=task_id,
        func=func,
        args=args,
        kwargs=kwargs or {},
        priority=TaskPriority(priority),
        timeout=timeout,
        depends_on=depends_on or []
    )


def batch_create_tasks(task_specs: List[Dict]) -> List[ParallelTask]:
    """
    Create multiple tasks from specifications.
    
    Args:
        task_specs: List of task specifications
        
    Returns:
        List of created tasks
    """
    tasks = []
    
    for spec in task_specs:
        task = create_task(
            task_id=spec.get("id", f"task_{len(tasks)}"),
            func=spec["func"],
            args=spec.get("args", ()),
            kwargs=spec.get("kwargs", {}),
            priority=spec.get("priority", 1),
            timeout=spec.get("timeout"),
            depends_on=spec.get("depends_on", [])
        )
        tasks.append(task)
        
    return tasks


# ============================================================================
# WORKER FUNCTIONS FOR DEMONSTRATION
# ============================================================================

def worker_add(a: int, b: int) -> int:
    """
    Add two numbers with simulated work.
    
    Args:
        a: First number
        b: Second number
        
    Returns:
        Sum of a and b
    """
    time.sleep(random.uniform(0.1, 0.5))
    return a + b


def worker_multiply(a: int, b: int) -> int:
    """
    Multiply two numbers with simulated work.
    
    Args:
        a: First number
        b: Second number
        
    Returns:
        Product of a and b
    """
    time.sleep(random.uniform(0.1, 0.5))
    return a * b


def worker_string_process(text: str) -> str:
    """
    Process a string with simulated work.
    
    Args:
        text: Input text
        
    Returns:
        Processed text
    """
    time.sleep(0.1)
    return f"PROCESSED: {text.upper()}"


def worker_compute(data: dict) -> dict:
    """
    Compute a result from input data.
    
    Args:
        data: Input data dictionary
        
    Returns:
        Result dictionary
    """
    time.sleep(0.2)
    return {
        "input": data,
        "output": sum(range(data.get("n", 10))),
        "processed_at": datetime.now().isoformat()
    }


def worker_fetch_data(url: str) -> dict:
    """
    Simulate fetching data from a URL.
    
    Args:
        url: URL to fetch
        
    Returns:
        Simulated response data
    """
    time.sleep(random.uniform(0.2, 0.8))
    return {
        "url": url,
        "status": 200,
        "data": f"Data from {url}",
        "size": random.randint(100, 10000),
        "fetched_at": datetime.now().isoformat()
    }


def worker_transform_data(data: Any, transform: str = "upper") -> Any:
    """
    Transform data using specified method.
    
    Args:
        data: Data to transform
        transform: Transformation method
        
    Returns:
        Transformed data
    """
    time.sleep(random.uniform(0.1, 0.4))
    
    if isinstance(data, str):
        if transform == "upper":
            return data.upper()
        elif transform == "lower":
            return data.lower()
        elif transform == "reverse":
            return data[::-1]
        elif transform == "title":
            return data.title()
    elif isinstance(data, (int, float)):
        return data * 2
    elif isinstance(data, list):
        return [x * 2 for x in data]
        
    return data


def worker_aggregate_values(values: List[int]) -> dict:
    """
    Aggregate multiple values.
    
    Args:
        values: List of values
        
    Returns:
        Aggregation result
    """
    time.sleep(random.uniform(0.1, 0.3))
    
    return {
        "count": len(values),
        "sum": sum(values),
        "avg": statistics.mean(values),
        "min": min(values),
        "max": max(values),
        "median": statistics.median(values),
    }


def worker_matrix_multiply(matrix_a: List[List[int]], matrix_b: List[List[int]]) -> List[List[int]]:
    """
    Multiply two matrices.
    
    Args:
        matrix_a: First matrix
        matrix_b: Second matrix
        
    Returns:
        Result matrix
    """
    time.sleep(random.uniform(0.2, 0.6))
    
    result = []
    for i, row in enumerate(matrix_a):
        result_row = []
        for j in range(len(matrix_b[0])):
            val = sum(matrix_a[i][k] * matrix_b[k][j] for k in range(len(matrix_b)))
            result_row.append(val)
        result.append(result_row)
        
    return result


def worker_fibonacci(n: int) -> int:
    """
    Calculate the nth Fibonacci number.
    
    Args:
        n: Index
        
    Returns:
        nth Fibonacci number
    """
    time.sleep(random.uniform(0.1, 0.5))
    
    if n <= 1:
        return n
    
    a, b = 0, 1
    for _ in range(n - 1):
        a, b = b, a + b
        
    return b


def worker_prime_check(n: int) -> dict:
    """
    Check if a number is prime.
    
    Args:
        n: Number to check
        
    Returns:
        Result dictionary
    """
    time.sleep(random.uniform(0.1, 0.4))
    
    is_prime = True
    if n < 2:
        is_prime = False
    elif n == 2:
        is_prime = True
    elif n % 2 == 0:
        is_prime = False
    else:
        for i in range(3, int(n**0.5) + 1, 2):
            if n % i == 0:
                is_prime = False
                break
                
    return {
        "number": n,
        "is_prime": is_prime,
        "checked_at": datetime.now().isoformat()
    }


def worker_batch_process(items: List[Any]) -> List[dict]:
    """
    Process a batch of items.
    
    Args:
        items: List of items
        
    Returns:
        List of results
    """
    results = []
    for item in items:
        results.append({
            "item": item,
            "processed": True,
            "result": str(item).upper(),
            "timestamp": datetime.now().isoformat()
        })
        time.sleep(0.05)
        
    return results


# ============================================================================
# DEMO FUNCTIONS
# ============================================================================

def demo_parallel_executor():
    """Demonstrate parallel executor functionality."""
    print("=" * 60)
    print("PARALLEL EXECUTOR DEMO")
    print("=" * 60)
    print()
    
    executor = ParallelExecutor(max_workers=4, mode=ExecutionMode.PARALLEL)
    executor.start()
    
    print("Submitting tasks...")
    task_specs = [
        {"id": "add_5_3", "func": worker_add, "args": (5, 3)},
        {"id": "add_10_20", "func": worker_add, "args": (10, 20)},
        {"id": "mult_4_7", "func": worker_multiply, "args": (4, 7)},
        {"id": "mult_12_8", "func": worker_multiply, "args": (12, 8)},
        {"id": "str_hello", "func": worker_string_process, "args": ("hello",)},
        {"id": "str_world", "func": worker_string_process, "args": ("world",)},
        {"id": "compute_100", "func": worker_compute, "kwargs": {"n": 100}},
        {"id": "compute_50", "func": worker_compute, "kwargs": {"n": 50}},
        {"id": "fib_20", "func": worker_fibonacci, "args": (20,)},
        {"id": "fib_30", "func": worker_fibonacci, "args": (30,)},
        {"id": "prime_17", "func": worker_prime_check, "args": (17,)},
        {"id": "prime_97", "func": worker_prime_check, "args": (97,)},
    ]
    
    tasks = batch_create_tasks(task_specs)
    task_ids = executor.submit_batch(tasks)
    
    print(f"Submitted {len(task_ids)} tasks: {task_ids}")
    print()
    print("Waiting for completion...")
    
    results = executor.wait_for(task_ids, timeout=30.0)
    
    print("\nTask Results:")
    print("-" * 40)
    
    for tid, result in results.items():
        if result:
            status = "OK" if result.success else "FAIL"
            print(f"[{status}] {tid}")
            print(f"     Status: {result.status.value}")
            print(f"     Duration: {result.duration_ms}ms")
            if result.result is not None:
                print(f"     Result: {result.result}")
            if result.error:
                print(f"     Error: {result.error}")
    
    print()
    print("Statistics:")
    print("-" * 40)
    stats = executor.get_stats()
    print(f"  Mode: {stats['mode']}")
    print(f"  Total Tasks: {stats['total_tasks']}")
    print(f"  Completed: {stats['completed']}")
    print(f"  Failed: {stats['failed']}")
    print(f"  Worker Stats: {stats['worker_stats']}")
    
    executor.stop()
    print()
    print("Demo completed successfully!")
    print()


def demo_result_aggregation():
    """Demonstrate result aggregation functionality."""
    print("=" * 60)
    print("RESULT AGGREGATION DEMO")
    print("=" * 60)
    print()
    
    aggregator = ResultAggregator()
    reporter = ResultReporter(aggregator)
    
    executor = ParallelExecutor(max_workers=4, mode=ExecutionMode.PARALLEL)
    executor.start()
    
    task_specs = [
        {"id": "add", "func": worker_add, "args": (10, 20)},
        {"id": "mult", "func": worker_multiply, "args": (5, 6)},
        {"id": "fib", "func": worker_fibonacci, "args": (25,)},
        {"id": "prime", "func": worker_prime_check, "args": (101,)},
    ]
    
    print("Executing tasks...")
    tasks = batch_create_tasks(task_specs)
    task_ids = executor.submit_batch(tasks)
    results = executor.wait_for(task_ids, timeout=15.0)
    
    print("\nGenerating report...")
    reporter.print_report(results)
    
    print("\nAggregated Summary:")
    summary = aggregator.get_summary()
    print(f"  Total: {summary['total']}")
    print(f"  Successful: {summary['successful']}")
    print(f"  Failed: {summary['failed']}")
    print(f"  Success Rate: {summary['success_rate']*100:.1f}%")
    
    if summary.get("durations"):
        d = summary["durations"]
        print(f"\nExecution Times:")
        print(f"  Min: {d['min']*1000:.2f}ms")
        print(f"  Max: {d['max']*1000:.2f}ms")
        print(f"  Avg: {d['avg']*1000:.2f}ms")
        print(f"  Median: {d['median']*1000:.2f}ms")
    
    executor.stop()
    print()
    print("Demo completed successfully!")
    print()


def demo_unified_resolution():
    """Demonstrate unified resolution functionality."""
    print("=" * 60)
    print("UNIFIED RESOLUTION DEMO")
    print("=" * 60)
    print()
    
    coordinator = UnifiedCoordinator(max_workers=3)
    coordinator.start()
    
    def method_add_10():
        """Method 1: Add 10"""
        time.sleep(0.3)
        return 10
        
    def method_multiply_2():
        """Method 2: Multiply by 2"""
        time.sleep(0.2)
        return 5 * 2
        
    def method_subtract():
        """Method 3: Subtract to get 10"""
        time.sleep(0.1)
        return 20 - 10
        
    print("Submitting resolution task...")
    task_id = coordinator.submit_resolution_task(
        "unified_test",
        [method_add_10, method_multiply_2, method_subtract],
        ResolutionStrategy.MAJORITY
    )
    
    print(f"Task ID: {task_id}")
    print("Waiting for resolution...")
    
    time.sleep(1.0)
    
    resolution = coordinator.resolve(task_id, timeout=5.0)
    
    if resolution:
        print(f"\nResolution Details:")
        print("-" * 40)
        print(f"  Strategy: {resolution.strategy.value}")
        print(f"  Sub-results: {len(resolution.sub_results)}")
        
        for i, result in enumerate(resolution.sub_results):
            status = "OK" if result.success else "FAIL"
            print(f"  [{status}] Sub-task {i}: {result.result}")
        
        print(f"\n  Final Result: {resolution.final_result}")
        print(f"  Consensus Score: {resolution.consensus_score:.2f}")
        
    coordinator.stop()
    print()
    print("Demo completed successfully!")
    print()


def demo_pipeline():
    """Demonstrate pipeline processing functionality."""
    print("=" * 60)
    print("PIPELINE PROCESSOR DEMO")
    print("=" * 60)
    print()
    
    pipeline = PipelineProcessor()
    
    pipeline.add_stage("doubler", lambda x: x * 2, "double")
    pipeline.add_stage("adder", lambda x: x + 10, "add")
    pipeline.add_stage("stringifier", lambda x: f"Result: {x}", "stringify")
    
    test_values = [1, 5, 10, 15, 20]
    
    print("Processing values through pipeline:")
    print("-" * 40)
    
    for value in test_values:
        result = pipeline.execute(value)
        print(f"  Input: {value:2d} -> Output: {result}")
    
    parallel_inputs = list(range(1, 6))
    print("\nParallel execution:")
    print(f"  Inputs: {parallel_inputs}")
    
    executor = PipelineProcessor()
    executor.add_stage("square", lambda x: x ** 2)
    
    parallel_results = executor.execute_parallel(parallel_inputs)
    print(f"  Results: {[r.result for r in parallel_results.values() if r]}")
    
    print()
    print("Demo completed successfully!")
    print()


def demo_worker_variety():
    """Demonstrate various worker functions."""
    print("=" * 60)
    print("WORKER VARIETY DEMO")
    print("=" * 60)
    print()
    
    executor = ParallelExecutor(max_workers=4, mode=ExecutionMode.PARALLEL)
    executor.start()
    
    task_specs = [
        {"id": "fetch_1", "func": worker_fetch_data, "args": ("https://api.example.com/data1",)},
        {"id": "fetch_2", "func": worker_fetch_data, "args": ("https://api.example.com/data2",)},
        {"id": "transform_str", "func": worker_transform_data, "args": ("hello world",), "kwargs": {"transform": "title"}},
        {"id": "transform_list", "func": worker_transform_data, "args": ([1, 2, 3, 4, 5],)},
        {"id": "aggregate", "func": worker_aggregate_values, "args": ([10, 20, 30, 40, 50],)},
        {"id": "prime_1", "func": worker_prime_check, "args": (53,)},
        {"id": "prime_2", "func": worker_prime_check, "args": (89,)},
        {"id": "prime_3", "func": worker_prime_check, "args": (151,)},
        {"id": "batch", "func": worker_batch_process, "args": (["a", "b", "c"],)},
    ]
    
    print("Executing varied worker tasks...")
    tasks = batch_create_tasks(task_specs)
    task_ids = executor.submit_batch(tasks)
    results = executor.wait_for(task_ids, timeout=15.0)
    
    print("\nResults:")
    print("-" * 40)
    
    for tid, result in results.items():
        if result and result.success:
            print(f"\n[{tid}]")
            print(f"  Result: {result.result}")
            print(f"  Duration: {result.duration_ms}ms")
    
    executor.stop()
    print()
    print("Demo completed successfully!")
    print()


def demo_priority_execution():
    """Demonstrate priority-based execution."""
    print("=" * 60)
    print("PRIORITY EXECUTION DEMO")
    print("=" * 60)
    print()
    
    executor = ParallelExecutor(max_workers=4, mode=ExecutionMode.PARALLEL)
    executor.start()
    
    task_specs = [
        {"id": "low_priority", "func": worker_add, "args": (1, 2), "priority": 0},
        {"id": "normal_priority", "func": worker_add, "args": (3, 4), "priority": 1},
        {"id": "high_priority", "func": worker_add, "args": (5, 6), "priority": 2},
        {"id": "critical_priority", "func": worker_add, "args": (7, 8), "priority": 3},
    ]
    
    print("Submitting tasks with different priorities...")
    tasks = batch_create_tasks(task_specs)
    task_ids = executor.submit_batch(tasks)
    results = executor.wait_for(task_ids, timeout=10.0)
    
    print("\nResults (higher priority first):")
    print("-" * 40)
    
    sorted_tasks = sorted(results.items(), 
                       key=lambda x: task_specs[[s["id"] for s in task_specs].index(x[0])]["priority"] if x[0] in [s["id"] for s in task_specs] else 0,
                       reverse=True)
    
    for tid, result in results.items():
        if result:
            priority = next((s["priority"] for s in task_specs if s["id"] == tid), 1)
            priority_name = TaskPriority(priority).name
            print(f"  [{priority_name}] {tid}: {result.result} ({result.duration_ms}ms)")
    
    executor.stop()
    print()
    print("Demo completed successfully!")
    print()


class CodeSwarmCoordinator:
    """
    Coordinator for code generation tasks using swarm pattern.
    
    Manages code generation through parallel agents with result validation.
    """
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.executor = ParallelExecutor(max_workers=max_workers, mode=ExecutionMode.PARALLEL)
        self.results: Dict[str, Any] = {}
        self._running = False
        
    def start(self):
        """Start the coordinator."""
        self._running = True
        self.executor.start()
        
    def stop(self):
        """Stop the coordinator."""
        self._running = False
        self.executor.stop()
        
    def generate_code(self, prompt: str, filepath: str = None) -> Dict[str, Any]:
        """
        Generate code using swarm pattern.
        
        Args:
            prompt: The code generation prompt
            filepath: Optional path to save the code
            
        Returns:
            Dict with success, code, filepath, errors
        """
        if not self._running:
            self.start()
            
        task_id = f"code_gen_{int(time.time() * 1000)}"
        
        def code_gen_task():
            from src.engine import CrackedCodeEngine
            eng = CrackedCodeEngine()
            if filepath:
                resp = eng.generate_and_save(prompt, filepath)
            else:
                resp = eng.generate_code(prompt)
            return {
                "success": resp.success,
                "code": resp.text if resp.success else "",
                "filepath": filepath,
                "error": resp.error if not resp.success else None
            }
        
        task = create_task(
            task_id=task_id,
            func=code_gen_task,
            args=(),
            priority=TaskPriority.HIGH.value
        )
        
        task_ids = self.executor.submit_batch([task])
        results = self.executor.wait_for(task_ids, timeout=60.0)
        
        result = results.get(task_id)
        
        if result and result.success:
            return result.result
        return {
            "success": False,
            "code": "",
            "filepath": filepath,
            "error": result.error if result else "No result"
        }
    
    def generate_with_validation(self, prompt: str, filepath: str = None) -> Dict[str, Any]:
        """
        Generate code with validation.
        
        Args:
            prompt: The code generation prompt
            filepath: Optional path to save the code
            
        Returns:
            Dict with success, code, filepath, validation, errors
        """
        from src.engine import CrackedCodeEngine
        
        result = self.generate_code(prompt, filepath)
        
        if not result.get("success"):
            return result
            
        eng = CrackedCodeEngine()
        validation = eng.validate_code(result.get("code", ""))
        
        result["validation"] = validation
        
        if not validation.get("valid", True):
            result["success"] = False
            result["error"] = f"Validation failed: {validation.get('errors', [])}"
            
        return result


def run_all_demos():
    """Run all demonstration functions."""
    print("\n" + "=" * 60)
    print("RUNNING ALL DEMOS")
    print("=" * 60)
    print()
    
    demo_parallel_executor()
    time.sleep(0.5)
    
    demo_result_aggregation()
    time.sleep(0.5)
    
    demo_unified_resolution()
    time.sleep(0.5)
    
    demo_pipeline()
    time.sleep(0.5)
    
    demo_worker_variety()
    time.sleep(0.5)
    
    demo_priority_execution()
    
    print("\n" + "=" * 60)
    print("ALL DEMOS COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    run_all_demos()