"""Task Scheduler v2.9.6 - Cron-based recurring AI task execution.

Define recurring tasks that run on a schedule:
  schedules/weekly_security.yaml
  schedules/daily_backup.json

The scheduler uses the orchestrator to execute tasks,
so retries, timeouts, and agent assignment are automatic.

Usage:
    from src.task_scheduler import TaskScheduler
    scheduler = TaskScheduler(engine)
    scheduler.start()
    scheduler.add_schedule(name="weekly_scan", cron="0 9 * * 1", ...)
"""

import json
import threading
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.logger_config import get_logger

logger = get_logger("TaskScheduler")


# â”€â”€ Data Models â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@dataclass
class Schedule:
    """A scheduled recurring task."""
    name: str
    cron: str  # "min hour day month dow"
    agent: str  # Agent role or name
    prompt: str
    enabled: bool = True
    output: Optional[str] = None  # Optional file to save results
    description: str = ""
    tags: List[str] = None
    max_history: int = 10
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []


@dataclass  
class ScheduledRun:
    """Record of a scheduled task execution."""
    schedule_name: str
    timestamp: float
    success: bool
    result_text: str = ""
    error: str = ""
    duration: float = 0.0


# â”€â”€ Cron Parser â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def parse_cron(cron: str) -> Dict[str, List[int]]:
    """Parse a cron expression into minute/hour/day/month/dow lists.
    
    Supports: * (all), */N (step), N-M (range), N (single), N,M (list)
    """
    parts = cron.strip().split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron: '{cron}' (need 5 fields: min hour day month dow)")
    
    field_names = ["minute", "hour", "day", "month", "dow"]
    ranges = {
        "minute": (0, 59),
        "hour": (0, 23),
        "day": (1, 31),
        "month": (1, 12),
        "dow": (0, 6),  # 0=Sunday
    }
    
    result = {}
    for i, (name, part) in enumerate(zip(field_names, parts)):
        min_v, max_v = ranges[name]
        values = _parse_cron_field(part, min_v, max_v)
        result[name] = sorted(values)
    
    return result


def _parse_cron_field(part: str, min_v: int, max_v: int) -> List[int]:
    """Parse a single cron field."""
    values = set()
    
    for subpart in part.split(","):
        subpart = subpart.strip()
        
        if subpart == "*":
            values.update(range(min_v, max_v + 1))
        elif subpart.startswith("*/"):
            step = int(subpart[2:])
            values.update(range(min_v, max_v + 1, step))
        elif "-" in subpart:
            start, end = subpart.split("-")
            values.update(range(int(start), int(end) + 1))
        else:
            values.add(int(subpart))
    
    return list(values)


def should_run_now(cron_spec: Dict[str, List[int]]) -> bool:
    """Check if the current time matches the cron spec."""
    now = datetime.now()
    return (
        now.minute in cron_spec["minute"] and
        now.hour in cron_spec["hour"] and
        now.day in cron_spec["day"] and
        now.month in cron_spec["month"] and
        now.weekday() in cron_spec["dow"]
    )


# â”€â”€ Task Scheduler â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TaskScheduler:
    """Cron-based recurring task scheduler using the orchestrator."""
    
    def __init__(self, engine=None, schedules_dir: str = "schedules", check_interval: int = 60, notifications=None):
        self.engine = engine
        self.schedules_dir = Path(schedules_dir)
        self.check_interval = check_interval
        self.notifications = notifications
        self.schedules: Dict[str, Schedule] = {}
        self.history: Dict[str, List[ScheduledRun]] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_run_minute: Optional[str] = None
        self._load_schedules()
    
    def _load_schedules(self):
        """Load schedule definitions from disk."""
        if not self.schedules_dir.exists():
            logger.debug(f"Schedules dir not found: {self.schedules_dir}")
            return
        
        for path in self.schedules_dir.iterdir():
            if path.suffix not in (".json", ".yaml", ".yml"):
                continue
            try:
                self._load_schedule_file(path)
            except Exception as e:
                logger.warning(f"Failed to load schedule {path}: {e}")
    
    def _load_schedule_file(self, path: Path):
        """Load a single schedule file."""
        import yaml
        
        with open(path, "r", encoding="utf-8") as f:
            if path.suffix == ".json":
                data = json.load(f)
            else:
                data = yaml.safe_load(f)
        
        if not data:
            return
        
        schedule = Schedule(
            name=data.get("name", path.stem),
            cron=data.get("cron", "0 0 * * *"),
            agent=data.get("agent", "coder"),
            prompt=data.get("prompt", ""),
            enabled=data.get("enabled", True),
            output=data.get("output"),
            description=data.get("description", ""),
            tags=data.get("tags", []),
            max_history=data.get("max_history", 10),
        )
        
        self.schedules[schedule.name] = schedule
        logger.info(f"Loaded schedule: {schedule.name} ({schedule.cron})")
    
    def add_schedule(self, name: str, cron: str, agent: str, prompt: str,
                     enabled: bool = True, output: Optional[str] = None,
                     description: str = "", tags: List[str] = None) -> Schedule:
        """Add a new schedule programmatically."""
        schedule = Schedule(
            name=name, cron=cron, agent=agent, prompt=prompt,
            enabled=enabled, output=output, description=description,
            tags=tags or [],
        )
        self.schedules[name] = schedule
        
        # Save to disk
        self.schedules_dir.mkdir(parents=True, exist_ok=True)
        path = self.schedules_dir / f"{name}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(schedule), f, indent=2)
        
        logger.info(f"Added schedule: {name} ({cron})")
        return schedule
    
    def remove_schedule(self, name: str) -> bool:
        """Remove a schedule."""
        if name in self.schedules:
            del self.schedules[name]
            path = self.schedules_dir / f"{name}.json"
            if path.exists():
                path.unlink()
            logger.info(f"Removed schedule: {name}")
            return True
        return False
    
    def enable_schedule(self, name: str) -> bool:
        """Enable a schedule."""
        if name in self.schedules:
            self.schedules[name].enabled = True
            return True
        return False
    
    def disable_schedule(self, name: str) -> bool:
        """Disable a schedule."""
        if name in self.schedules:
            self.schedules[name].enabled = False
            return True
        return False
    
    def list_schedules(self) -> List[Schedule]:
        """List all schedules."""
        return list(self.schedules.values())
    
    def get_history(self, name: str) -> List[ScheduledRun]:
        """Get execution history for a schedule."""
        return self.history.get(name, [])
    
    def start(self):
        """Start the scheduler background thread."""
        if self._running:
            logger.info("TaskScheduler already running")
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("TaskScheduler started")
    
    def stop(self):
        """Stop the scheduler."""
        self._running = False
        logger.info("TaskScheduler stopped")
    
    def _run_loop(self):
        """Main scheduler loop."""
        while self._running:
            try:
                self._check_schedules()
            except Exception as e:
                logger.error(f"Scheduler check error: {e}")
            
            # Sleep in small increments to allow clean shutdown
            for _ in range(self.check_interval):
                if not self._running:
                    break
                time.sleep(1)
    
    def _check_schedules(self):
        """Check all schedules and run any that match the current time."""
        now = datetime.now()
        current_minute = now.strftime("%Y-%m-%d %H:%M")
        
        # Prevent running same minute twice
        if current_minute == self._last_run_minute:
            return
        self._last_run_minute = current_minute
        
        for name, schedule in self.schedules.items():
            if not schedule.enabled:
                continue
            
            try:
                cron_spec = parse_cron(schedule.cron)
                if should_run_now(cron_spec):
                    logger.info(f"Triggering scheduled task: {name}")
                    self._execute_schedule(schedule)
            except Exception as e:
                logger.error(f"Schedule check failed for {name}: {e}")
    
    def _execute_schedule(self, schedule: Schedule):
        """Execute a single scheduled task."""
        start = time.time()
        
        try:
            if self.engine:
                # Use the engine to process the prompt
                import asyncio
                response = asyncio.run(self.engine.process(
                    prompt=schedule.prompt,
                    intent="chat",
                ))
                
                success = response.success
                result_text = response.text
                error = response.error or ""
            else:
                success = False
                result_text = ""
                error = "No engine available"
            
            duration = time.time() - start
            
            # Save to history
            run = ScheduledRun(
                schedule_name=schedule.name,
                timestamp=time.time(),
                success=success,
                result_text=result_text,
                error=error,
                duration=duration,
            )
            
            if schedule.name not in self.history:
                self.history[schedule.name] = []
            self.history[schedule.name].append(run)
            
            # Trim history
            if len(self.history[schedule.name]) > schedule.max_history:
                self.history[schedule.name] = self.history[schedule.name][-schedule.max_history:]
            
            # Save output to file if specified
            if schedule.output and success:
                try:
                    output_path = Path(schedule.output)
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(output_path, "a", encoding="utf-8") as f:
                        f.write(f"\n{'='*60}\n")
                        f.write(f"Scheduled Run: {schedule.name}\n")
                        f.write(f"Time: {datetime.now().isoformat()}\n")
                        f.write(f"{'='*60}\n\n")
                        f.write(result_text)
                        f.write("\n")
                    logger.info(f"Schedule output saved: {schedule.output}")
                except Exception as e:
                    logger.error(f"Failed to save schedule output: {e}")
            
            logger.info(f"Schedule {schedule.name}: {'SUCCESS' if success else 'FAILED'} ({duration:.2f}s)")
            
            # Send notification
            if self.notifications:
                if success:
                    self.notifications.success(
                        title=f"Schedule Complete: {schedule.name}",
                        message=f"Task completed successfully in {duration:.1f}s.\n\n{result_text[:500]}",
                        source="task_scheduler",
                        metadata={"schedule": schedule.name, "duration": duration, "agent": schedule.agent},
                    )
                else:
                    self.notifications.error(
                        title=f"Schedule Failed: {schedule.name}",
                        message=f"Task failed after {duration:.1f}s.\n\nError: {error[:500]}",
                        source="task_scheduler",
                        metadata={"schedule": schedule.name, "duration": duration, "error": error},
                    )
            
        except Exception as e:
            logger.error(f"Schedule execution failed for {schedule.name}: {e}")
            if self.notifications:
                self.notifications.error(
                    title=f"Schedule Error: {schedule.name}",
                    message=f"Unhandled exception: {str(e)[:500]}",
                    source="task_scheduler",
                    metadata={"schedule": schedule.name, "exception": str(e)},
                )


def create_task_scheduler(engine=None, schedules_dir: str = "schedules") -> TaskScheduler:
    """Create a TaskScheduler instance."""
    return TaskScheduler(engine=engine, schedules_dir=schedules_dir)


# â”€â”€ CLI Entry Point â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

if __name__ == "__main__":
    from src.engine import CrackedCodeEngine
    
    engine = CrackedCodeEngine()
    scheduler = create_task_scheduler(engine=engine)
    
    # Add example schedule
    scheduler.add_schedule(
        name="test_hello",
        cron="* * * * *",  # Every minute for testing
        agent="coder",
        prompt="Generate a random Python one-liner",
        description="Test schedule that runs every minute",
    )
    
    print(f"TaskScheduler started. Schedules: {len(scheduler.list_schedules())}")
    print("Press Ctrl+C to stop")
    
    scheduler.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        scheduler.stop()
        print("\nTaskScheduler stopped")

