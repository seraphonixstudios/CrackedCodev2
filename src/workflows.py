"""Workflow Builder v2.10.0 - Multi-step AI automation pipelines.

Define workflows via YAML/JSON in the workflows/ directory:
  workflows/security_audit.yaml
  workflows/code_review.yaml

A workflow is a directed graph of steps. Each step runs an agent,
executes a tool, or evaluates a condition. Steps can run in parallel
when they have no dependencies between them.

Usage:
    from src.workflows import get_workflow_engine
    engine = get_workflow_engine()
    result = engine.execute("security_audit", context={"repo": "myapp"})
"""

import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from src.logger_config import get_logger

logger = get_logger("Workflows")


# ── Data Models ────────────────────────────────────────────────────────────

class StepStatus(Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class WorkflowStep:
    """A single step in a workflow."""
    name: str
    type: str  # agent, tool, condition, notify, composite
    config: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    condition: str = ""
    output_var: str = ""
    retry_count: int = 0
    timeout: int = 300
    parallel: bool = False
    on_failure: str = "fail"  # fail, continue, retry


@dataclass
class WorkflowTrigger:
    """Trigger configuration for a workflow."""
    type: str  # manual, cron, webhook, event
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowDef:
    """A complete workflow definition."""
    name: str
    description: str
    version: str = "1.0"
    steps: List[WorkflowStep] = field(default_factory=list)
    triggers: List[WorkflowTrigger] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)
    output_format: str = "json"  # json, markdown, text
    enabled: bool = True
    author: str = ""
    tags: List[str] = field(default_factory=list)


@dataclass
class StepResult:
    """Result of executing a single step."""
    step_name: str
    status: StepStatus
    output: Any = None
    error: str = ""
    duration: float = 0.0
    attempts: int = 0


@dataclass
class WorkflowResult:
    """Result of executing a complete workflow."""
    workflow: str
    success: bool
    steps: List[StepResult] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    duration: float = 0.0
    started_at: str = ""
    completed_at: str = ""


# ── Workflow Engine ────────────────────────────────────────────────────────

class WorkflowEngine:
    """Execute workflow definitions with dependency resolution."""
    
    def __init__(self, workflows_dir: str = "workflows"):
        self.workflows_dir = Path(workflows_dir)
        self.workflows: Dict[str, WorkflowDef] = {}
        self._load_workflows()
    
    def _load_workflows(self):
        """Load all workflow definitions from disk."""
        if not self.workflows_dir.exists():
            return
        
        for path in self.workflows_dir.iterdir():
            if path.suffix not in (".json", ".yaml", ".yml"):
                continue
            try:
                self._load_workflow_file(path)
            except Exception as e:
                logger.warning(f"Failed to load workflow {path}: {e}")
    
    def _load_workflow_file(self, path: Path):
        """Load a single workflow file."""
        import yaml
        
        with open(path, "r", encoding="utf-8") as f:
            if path.suffix == ".json":
                data = json.load(f)
            else:
                data = yaml.safe_load(f)
        
        if not data:
            return
        
        # Parse steps
        steps = []
        for s in data.get("steps", []):
            steps.append(WorkflowStep(
                name=s.get("name", "step"),
                type=s.get("type", "agent"),
                config=s.get("config", {}),
                depends_on=s.get("depends_on", []),
                condition=s.get("condition", ""),
                output_var=s.get("output_var", ""),
                retry_count=s.get("retry_count", 0),
                timeout=s.get("timeout", 300),
                parallel=s.get("parallel", False),
                on_failure=s.get("on_failure", "fail"),
            ))
        
        # Parse triggers
        triggers = []
        for t in data.get("triggers", []):
            triggers.append(WorkflowTrigger(
                type=t.get("type", "manual"),
                config=t.get("config", {}),
            ))
        
        workflow = WorkflowDef(
            name=data.get("name", path.stem),
            description=data.get("description", ""),
            version=data.get("version", "1.0"),
            steps=steps,
            triggers=triggers,
            variables=data.get("variables", {}),
            output_format=data.get("output_format", "json"),
            enabled=data.get("enabled", True),
            author=data.get("author", ""),
            tags=data.get("tags", []),
        )
        
        self.workflows[workflow.name] = workflow
        logger.info(f"Loaded workflow: {workflow.name} ({len(workflow.steps)} steps)")
    
    def reload(self):
        """Reload all workflows from disk."""
        self.workflows.clear()
        self._load_workflows()
        logger.info(f"Reloaded {len(self.workflows)} workflows")
    
    def list_workflows(self) -> List[WorkflowDef]:
        """List all enabled workflows."""
        return [w for w in self.workflows.values() if w.enabled]
    
    def get(self, name: str) -> Optional[WorkflowDef]:
        """Get a workflow by name."""
        return self.workflows.get(name)
    
    def execute(self, name: str, context: Optional[Dict[str, Any]] = None,
                orchestrator=None) -> WorkflowResult:
        """Execute a workflow with dependency resolution."""
        from datetime import datetime
        
        workflow = self.get(name)
        if not workflow:
            return WorkflowResult(
                workflow=name,
                success=False,
                steps=[StepResult(
                    step_name="load",
                    status=StepStatus.FAILED,
                    error=f"Workflow not found: {name}",
                )],
            )
        
        if not workflow.enabled:
            return WorkflowResult(
                workflow=name,
                success=False,
                steps=[StepResult(
                    step_name="load",
                    status=StepStatus.SKIPPED,
                    error=f"Workflow disabled: {name}",
                )],
            )
        
        started_at = datetime.utcnow().isoformat()
        ctx = {**workflow.variables, **(context or {})}
        step_results: Dict[str, StepResult] = {}
        completed_steps: Set[str] = set()
        all_steps = {s.name: s for s in workflow.steps}
        
        start_time = time.time()
        
        # Execute steps in dependency order
        while len(completed_steps) < len(workflow.steps):
            # Find ready steps (all dependencies satisfied)
            ready = [
                s for s in workflow.steps
                if s.name not in completed_steps
                and s.name not in [r.step_name for r in step_results.values() if r.status in (StepStatus.RUNNING, StepStatus.COMPLETED, StepStatus.SKIPPED)]
                and all(d in completed_steps for d in s.depends_on)
            ]
            
            if not ready:
                # Check for deadlocks
                remaining = [s.name for s in workflow.steps if s.name not in completed_steps]
                if remaining:
                    return WorkflowResult(
                        workflow=name,
                        success=False,
                        steps=list(step_results.values()),
                        context=ctx,
                        duration=time.time() - start_time,
                        started_at=started_at,
                        error=f"Dependency deadlock: {remaining}",
                    )
                break
            
            # Separate parallel vs sequential steps
            parallel_steps = [s for s in ready if s.parallel]
            sequential_steps = [s for s in ready if not s.parallel]
            
            # Execute parallel steps first
            if parallel_steps:
                with ThreadPoolExecutor(max_workers=min(len(parallel_steps), 4)) as executor:
                    futures = {
                        executor.submit(self._execute_step, s, ctx, orchestrator): s
                        for s in parallel_steps
                    }
                    for future in as_completed(futures):
                        step = futures[future]
                        try:
                            result = future.result()
                        except Exception as e:
                            result = StepResult(
                                step_name=step.name,
                                status=StepStatus.FAILED,
                                error=str(e),
                            )
                        step_results[step.name] = result
                        completed_steps.add(step.name)
                        if result.output_var and result.status == StepStatus.COMPLETED:
                            ctx[result.output_var] = result.output
            
            # Execute one sequential step
            if sequential_steps:
                step = sequential_steps[0]
                result = self._execute_step(step, ctx, orchestrator)
                step_results[step.name] = result
                completed_steps.add(step.name)
                if step.output_var and result.status == StepStatus.COMPLETED:
                    ctx[step.output_var] = result.output
                
                # Handle failure
                if result.status == StepStatus.FAILED:
                    if step.on_failure == "fail":
                        break
                    elif step.on_failure == "retry" and result.attempts <= step.retry_count:
                        completed_steps.remove(step.name)
                        del step_results[step.name]
        
        completed_at = datetime.utcnow().isoformat()
        success = all(r.status == StepStatus.COMPLETED or r.status == StepStatus.SKIPPED
                      for r in step_results.values())
        
        return WorkflowResult(
            workflow=name,
            success=success,
            steps=list(step_results.values()),
            context=ctx,
            duration=time.time() - start_time,
            started_at=started_at,
            completed_at=completed_at,
        )
    
    def _execute_step(self, step: WorkflowStep, context: Dict[str, Any],
                      orchestrator=None) -> StepResult:
        """Execute a single workflow step."""
        from datetime import datetime
        
        start = time.time()
        attempts = 0
        
        # Evaluate condition
        if step.condition:
            try:
                safe_globals = {"__builtins__": {}}
                safe_locals = {**context}
                if not eval(step.condition, safe_globals, safe_locals):
                    return StepResult(
                        step_name=step.name,
                        status=StepStatus.SKIPPED,
                        duration=time.time() - start,
                    )
            except Exception as e:
                logger.warning(f"Step {step.name} condition failed: {e}")
                return StepResult(
                    step_name=step.name,
                    status=StepStatus.SKIPPED,
                    error=f"Condition error: {e}",
                    duration=time.time() - start,
                )
        
        # Execute based on type
        while attempts <= step.retry_count:
            attempts += 1
            try:
                if step.type == "agent":
                    result = self._execute_agent_step(step, context, orchestrator)
                elif step.type == "tool":
                    result = self._execute_tool_step(step, context)
                elif step.type == "notify":
                    result = self._execute_notify_step(step, context)
                elif step.type == "condition":
                    result = self._execute_condition_step(step, context)
                elif step.type == "composite":
                    result = self._execute_composite_step(step, context, orchestrator)
                else:
                    result = {"success": False, "error": f"Unknown step type: {step.type}"}
                
                if result.get("success"):
                    return StepResult(
                        step_name=step.name,
                        status=StepStatus.COMPLETED,
                        output=result,
                        duration=time.time() - start,
                        attempts=attempts,
                        output_var=step.output_var,
                    )
                else:
                    error = result.get("error", "Unknown error")
                    if attempts > step.retry_count:
                        return StepResult(
                            step_name=step.name,
                            status=StepStatus.FAILED,
                            error=error,
                            duration=time.time() - start,
                            attempts=attempts,
                        )
                    time.sleep(1)  # Brief delay before retry
            
            except Exception as e:
                logger.error(f"Step {step.name} execution error: {e}")
                if attempts > step.retry_count:
                    return StepResult(
                        step_name=step.name,
                        status=StepStatus.FAILED,
                        error=str(e),
                        duration=time.time() - start,
                        attempts=attempts,
                    )
                time.sleep(1)
        
        return StepResult(
            step_name=step.name,
            status=StepStatus.FAILED,
            error="Max retries exceeded",
            duration=time.time() - start,
            attempts=attempts,
        )
    
    def _execute_agent_step(self, step: WorkflowStep, context: Dict[str, Any],
                           orchestrator) -> Dict[str, Any]:
        """Execute an agent step via the orchestrator."""
        if orchestrator is None:
            return {"success": False, "error": "No orchestrator available"}
        
        agent = step.config.get("agent", "coder")
        task = step.config.get("task", "")
        
        # Interpolate task with context
        for key, val in context.items():
            task = task.replace(f"{{{key}}}", str(val))
        
        try:
            result = orchestrator.submit_task(
                task=task,
                agent_role=agent,
                priority=step.config.get("priority", "normal"),
            )
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _execute_tool_step(self, step: WorkflowStep, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool step."""
        from src.custom_tools import get_custom_tool_registry
        
        tool_name = step.config.get("tool", "")
        params = {}
        
        for key, val in step.config.get("parameters", {}).items():
            if isinstance(val, str):
                for ctx_key, ctx_val in context.items():
                    val = val.replace(f"{{{ctx_key}}}", str(ctx_val))
            params[key] = val
        
        registry = get_custom_tool_registry()
        return registry.execute(tool_name, params)
    
    def _execute_notify_step(self, step: WorkflowStep, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a notification step."""
        try:
            from src.notifications import get_notification_manager
            
            mgr = get_notification_manager()
            message_template = step.config.get("message", "")
            
            # Interpolate message
            for key, val in context.items():
                message_template = message_template.replace(f"{{{key}}}", str(val))
            
            level = step.config.get("level", "info")
            backend = step.config.get("backend", "log")
            
            if backend == "email":
                mgr.send_email(
                    subject=step.config.get("subject", "Workflow Notification"),
                    body=message_template,
                )
            elif backend == "webhook":
                mgr.send_webhook(
                    url=step.config.get("url", ""),
                    message=message_template,
                )
            else:
                mgr.notify(message_template, level=level)
            
            return {"success": True, "message": message_template}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _execute_condition_step(self, step: WorkflowStep, context: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate a condition step."""
        expression = step.config.get("expression", "True")
        try:
            safe_globals = {"__builtins__": {}}
            safe_locals = {**context}
            result = eval(expression, safe_globals, safe_locals)
            return {"success": True, "result": bool(result)}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _execute_composite_step(self, step: WorkflowStep, context: Dict[str, Any],
                               orchestrator) -> Dict[str, Any]:
        """Execute a composite step (nested workflow)."""
        sub_workflow = step.config.get("workflow", "")
        if sub_workflow in self.workflows:
            result = self.execute(sub_workflow, context, orchestrator)
            return {"success": result.success, "data": result}
        return {"success": False, "error": f"Sub-workflow not found: {sub_workflow}"}
    
    def save_example(self, name: str) -> Path:
        """Save an example workflow to disk."""
        example = {
            "name": name,
            "description": f"Example workflow: {name}",
            "version": "1.0",
            "variables": {"repo": "myapp", "branch": "main"},
            "steps": [
                {
                    "name": "scan",
                    "type": "agent",
                    "config": {
                        "agent": "security",
                        "task": "Scan dependencies for vulnerabilities in {repo}",
                    },
                    "output_var": "scan_results",
                },
                {
                    "name": "review",
                    "type": "agent",
                    "config": {
                        "agent": "reviewer",
                        "task": "Review code quality in {repo} branch {branch}",
                    },
                    "depends_on": ["scan"],
                    "condition": "scan_results.get('issues_found', 0) > 0",
                    "output_var": "review_report",
                },
                {
                    "name": "notify",
                    "type": "notify",
                    "config": {
                        "message": "Workflow completed for {repo}",
                        "level": "info",
                    },
                    "depends_on": ["review"],
                },
            ],
            "triggers": [
                {"type": "manual"},
                {"type": "cron", "config": {"schedule": "0 9 * * *"}},
            ],
            "enabled": True,
            "tags": ["example", "security"],
        }
        
        self.workflows_dir.mkdir(parents=True, exist_ok=True)
        path = self.workflows_dir / f"{name}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(example, f, indent=2)
        
        logger.info(f"Saved example workflow to {path}")
        return path


def get_workflow_engine(workflows_dir: str = "workflows") -> WorkflowEngine:
    """Get the global workflow engine."""
    return WorkflowEngine(workflows_dir=workflows_dir)

