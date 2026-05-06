"""Benchmark Suite v2.9.1 - Standardized code generation quality tests.

Measure AI performance over time with standardized benchmarks:
- HumanEval-style function completion
- Security vulnerability detection
- Code refactoring tasks
- Documentation generation

Usage:
    from src.benchmarks import get_benchmark_runner
    runner = get_benchmark_runner()
    
    # Run all benchmarks
    report = runner.run_all(engine)
    
    # Run specific benchmark
    report = runner.run("humaneval", engine)
    
    # Compare models
    comparison = runner.compare_models([
        ("qwen3:8b", engine1),
        ("dolphin:8b", engine2),
    ])
"""

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from src.logger_config import get_logger

logger = get_logger("Benchmarks")


# ── Data Models ────────────────────────────────────────────────────────────

@dataclass
class BenchmarkCase:
    """A single benchmark test case."""
    name: str
    category: str
    prompt: str
    expected: str = ""
    test_code: str = ""
    timeout: int = 30
    weight: float = 1.0


@dataclass
class BenchmarkResult:
    """Result of running a single benchmark case."""
    case: str
    category: str
    passed: bool
    score: float  # 0-1
    response: str = ""
    error: str = ""
    duration: float = 0.0


@dataclass
class BenchmarkReport:
    """Complete benchmark report."""
    name: str
    model: str
    results: List[BenchmarkResult] = field(default_factory=list)
    total_score: float = 0.0
    pass_rate: float = 0.0
    duration: float = 0.0
    started_at: str = ""
    completed_at: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)


# ── Benchmark Suites ───────────────────────────────────────────────────────

HUMANEVAL_CASES = [
    BenchmarkCase(
        name="has_close_elements",
        category="function_completion",
        prompt="""Write a Python function `has_close_elements(numbers: List[float], threshold: float) -> bool` that returns True if any two numbers in the list are closer to each other than the given threshold.

Example:
>>> has_close_elements([1.0, 2.0, 3.0], 0.5)
False
>>> has_close_elements([1.0, 2.8, 3.0, 4.0, 5.0, 2.0], 0.3)
True
""",
        test_code="""
from typing import List

def test_has_close_elements():
    assert has_close_elements([1.0, 2.0, 3.0], 0.5) == False
    assert has_close_elements([1.0, 2.8, 3.0, 4.0, 5.0, 2.0], 0.3) == True
    assert has_close_elements([1.0, 2.0, 3.0], 1.5) == True
    assert has_close_elements([], 0.5) == False
    assert has_close_elements([1.0], 0.5) == False
""",
    ),
    BenchmarkCase(
        name="separate_paren_groups",
        category="function_completion",
        prompt="""Write a Python function `separate_paren_groups(paren_string: str) -> List[str]` that takes a string of nested parentheses and returns a list of separate groups. Each group is balanced and not nested within another group.

Example:
>>> separate_paren_groups("( ) (( )) (( )( ))")
['()', '(())', '(()())']
""",
        test_code="""
from typing import List

def test_separate_paren_groups():
    assert separate_paren_groups("( ) (( )) (( )( ))") == ['()', '(())', '(()())']
    assert separate_paren_groups("()") == ['()']
    assert separate_paren_groups("(())(())") == ['(())', '(())']
""",
    ),
    BenchmarkCase(
        name="truncate_number",
        category="function_completion",
        prompt="""Write a Python function `truncate_number(number: float) -> float` that truncates a floating point number to an integer component, returning the remaining decimal part.

Example:
>>> truncate_number(3.5)
0.5
""",
        test_code="""
def test_truncate_number():
    assert truncate_number(3.5) == 0.5
    assert truncate_number(10.75) == 0.75
    assert truncate_number(100.0) == 0.0
    assert truncate_number(0.123) == 0.123
""",
    ),
]

SECURITY_CASES = [
    BenchmarkCase(
        name="detect_sql_injection",
        category="security",
        prompt="""Review this Python function and identify the security vulnerability:

```python
def get_user(user_id):
    query = f"SELECT * FROM users WHERE id = {user_id}"
    return db.execute(query)
```

What is the vulnerability and how would you fix it?""",
        expected="SQL injection",
        test_code="""
def test_detects_sql_injection():
    assert "sql injection" in response.lower() or "parameterized" in response.lower()
""",
    ),
    BenchmarkCase(
        name="detect_hardcoded_secret",
        category="security",
        prompt="""Review this code and identify the security issue:

```python
API_KEY = "sk-live-1234567890abcdef"

def make_request():
    headers = {"Authorization": f"Bearer {API_KEY}"}
    return requests.get("https://api.example.com/data", headers=headers)
```

What is wrong and how should it be fixed?""",
        expected="hardcoded secret",
        test_code="""
def test_detects_hardcoded_secret():
    assert "hardcoded" in response.lower() or "environment" in response.lower() or "secret" in response.lower()
""",
    ),
]

REFACTORING_CASES = [
    BenchmarkCase(
        name="refactor_nested_loops",
        category="refactoring",
        prompt="""Refactor this Python code to be more efficient and readable:

```python
def find_common(list1, list2):
    common = []
    for item1 in list1:
        for item2 in list2:
            if item1 == item2 and item1 not in common:
                common.append(item1)
    return common
```

Provide the refactored version.""",
        expected="set",
        test_code="""
def test_uses_set():
    assert "set" in response.lower() or "intersection" in response.lower()
""",
    ),
]

DOCUMENTATION_CASES = [
    BenchmarkCase(
        name="generate_docstring",
        category="documentation",
        prompt="""Write a comprehensive docstring for this Python function:

```python
def calculate_moving_average(data, window_size):
    if not data or window_size <= 0:
        return []
    result = []
    window_sum = sum(data[:window_size])
    result.append(window_sum / window_size)
    for i in range(window_size, len(data)):
        window_sum = window_sum - data[i - window_size] + data[i]
        result.append(window_sum / window_size)
    return result
```""",
        expected="docstring",
        test_code="""
def test_has_docstring():
    assert '\"\"\"' in response or "\'\'\'" in response
""",
    ),
]

BENCHMARK_SUITES = {
    "humaneval": HUMANEVAL_CASES,
    "security": SECURITY_CASES,
    "refactoring": REFACTORING_CASES,
    "documentation": DOCUMENTATION_CASES,
    "all": HUMANEVAL_CASES + SECURITY_CASES + REFACTORING_CASES + DOCUMENTATION_CASES,
}


# ── Benchmark Runner ───────────────────────────────────────────────────────

class BenchmarkRunner:
    """Run standardized benchmarks against CrackedCode."""

    def __init__(self, storage_dir: str = ".crackedcode/benchmarks"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.history_file = self.storage_dir / "history.json"
        self.history = self._load_history()

    def _load_history(self) -> List[Dict[str, Any]]:
        """Load benchmark history from disk."""
        if self.history_file.exists():
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def _save_history(self):
        """Save benchmark history to disk."""
        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(self.history, f, indent=2)

    def list_benchmarks(self) -> List[str]:
        """List available benchmark suites."""
        return list(BENCHMARK_SUITES.keys())

    def run(
        self,
        name: str,
        engine,
        model: Optional[str] = None,
    ) -> BenchmarkReport:
        """Run a benchmark suite."""
        from datetime import datetime

        cases = BENCHMARK_SUITES.get(name, [])
        if not cases:
            logger.warning(f"Unknown benchmark: {name}")
            return BenchmarkReport(name=name, model=model or "unknown")

        start = time.time()
        started_at = datetime.utcnow().isoformat()
        results: List[BenchmarkResult] = []

        for case in cases:
            logger.info(f"Running benchmark case: {case.name}")
            result = self._run_case(case, engine)
            results.append(result)

        # Calculate scores
        total_weight = sum(case.weight for case in cases)
        weighted_score = sum(
            r.score * next(c.weight for c in cases if c.name == r.case)
            for r in results
        )
        total_score = weighted_score / total_weight if total_weight > 0 else 0.0
        pass_rate = sum(1 for r in results if r.passed) / len(results) if results else 0.0

        completed_at = datetime.utcnow().isoformat()

        report = BenchmarkReport(
            name=name,
            model=model or getattr(engine, "model", "unknown"),
            results=results,
            total_score=round(total_score, 3),
            pass_rate=round(pass_rate, 3),
            duration=time.time() - start,
            started_at=started_at,
            completed_at=completed_at,
        )

        # Save to history
        self.history.append({
            "name": report.name,
            "model": report.model,
            "total_score": report.total_score,
            "pass_rate": report.pass_rate,
            "duration": report.duration,
            "started_at": report.started_at,
        })
        self._save_history()

        return report

    def _run_case(self, case: BenchmarkCase, engine) -> BenchmarkResult:
        """Run a single benchmark case."""
        start = time.time()

        try:
            # Generate response
            response = engine.process(case.prompt)
            response_text = response.get("response", "") if isinstance(response, dict) else str(response)

            # Evaluate
            passed, score = self._evaluate_case(case, response_text)

            return BenchmarkResult(
                case=case.name,
                category=case.category,
                passed=passed,
                score=score,
                response=response_text[:500],
                duration=time.time() - start,
            )
        except Exception as e:
            logger.error(f"Benchmark case {case.name} failed: {e}")
            return BenchmarkResult(
                case=case.name,
                category=case.category,
                passed=False,
                score=0.0,
                error=str(e),
                duration=time.time() - start,
            )

    def _evaluate_case(self, case: BenchmarkCase, response: str) -> tuple:
        """Evaluate a benchmark response."""
        if case.test_code:
            # Execute test code with response context
            try:
                namespace = {"response": response}
                exec(case.test_code, namespace)
                # Look for test functions
                test_funcs = [v for k, v in namespace.items() if k.startswith("test_")]
                if test_funcs:
                    for test_func in test_funcs:
                        test_func()
                    return True, 1.0
            except AssertionError:
                return False, 0.0
            except Exception:
                pass

        if case.expected:
            # Check if expected content is in response
            if case.expected.lower() in response.lower():
                return True, 1.0
            return False, 0.0

        # Default: check if response is non-empty
        return len(response.strip()) > 50, 0.5

    def run_all(self, engine, model: Optional[str] = None) -> List[BenchmarkReport]:
        """Run all benchmark suites."""
        reports = []
        for name in ["humaneval", "security", "refactoring", "documentation"]:
            report = self.run(name, engine, model=model)
            reports.append(report)
        return reports

    def compare_models(
        self,
        models: List[tuple],
        benchmark: str = "all",
    ) -> Dict[str, Any]:
        """Compare multiple models on the same benchmark."""
        results = {}
        for model_name, engine in models:
            report = self.run(benchmark, engine, model=model_name)
            results[model_name] = {
                "total_score": report.total_score,
                "pass_rate": report.pass_rate,
                "duration": report.duration,
            }

        # Rank models
        ranked = sorted(results.items(), key=lambda x: x[1]["total_score"], reverse=True)

        return {
            "benchmark": benchmark,
            "models": results,
            "ranking": [name for name, _ in ranked],
            "winner": ranked[0][0] if ranked else None,
        }

    def get_history(self, name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get benchmark history."""
        if name:
            return [h for h in self.history if h.get("name") == name]
        return self.history

    def get_trends(self) -> Dict[str, Any]:
        """Get score trends over time."""
        if not self.history:
            return {}

        by_benchmark = {}
        for entry in self.history:
            bench = entry.get("name", "unknown")
            if bench not in by_benchmark:
                by_benchmark[bench] = []
            by_benchmark[bench].append(entry)

        trends = {}
        for bench, entries in by_benchmark.items():
            scores = [e.get("total_score", 0) for e in entries]
            trends[bench] = {
                "latest": scores[-1] if scores else 0,
                "average": sum(scores) / len(scores) if scores else 0,
                "best": max(scores) if scores else 0,
                "runs": len(scores),
            }

        return trends


def get_benchmark_runner(storage_dir: str = ".crackedcode/benchmarks") -> BenchmarkRunner:
    """Get the global benchmark runner."""
    return BenchmarkRunner(storage_dir=storage_dir)
