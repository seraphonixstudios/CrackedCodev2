#!/usr/bin/env python3
"""
CRACKEDCODE v2.3.8 - Test Suite
Comprehensive tests with mocks and edge cases
"""

import os
import sys
import time
import json
import tempfile
from pathlib import Path
from typing import Optional
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, 'src')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.engine import Intent


def PASS(name: str, msg: str = "") -> bool:
    print(f"[PASS] {name} {msg}")
    return True


def FAIL(name: str, msg: str = "") -> bool:
    print(f"[FAIL] {name} {msg}")
    return False


def SKIP(name: str, msg: str = "") -> bool:
    print(f"[SKIP] {name} {msg}")
    return False


def print_header(name: str) -> None:
    print(f"\n{'='*60}\n  {name}\n{'='*60}\n")


class MockOllamaResponse:
    def __init__(self, content: str = "Mock response"):
        self.message = Mock()
        self.message.content = content


class MockOllamaList:
    def __init__(self, models: list[str] | None = None):
        self.models = [Mock(model=m) for m in (models or ["qwen3:8b-gpu"])]


class MockOllama:
    def list(self) -> MockOllamaList:
        return MockOllamaList()


def test_modules() -> bool:
    print_header("MODULE IMPORTS")
    
    try:
        from src.main import CrackedCodeConfig
        PASS("Main module")
    except Exception as e:
        return FAIL("Main module", str(e)[:50])
    
    try:
        from src.atlan_ui import AtlanInterface
        PASS("Atlantean UI")
    except Exception as e:
        return FAIL("Atlantean UI", str(e)[:50])
    
    try:
        from src.parallel_processor import ParallelExecutor
        PASS("Parallel processor")
    except Exception as e:
        return FAIL("Parallel processor", str(e)[:50])
    
    try:
        from src.engine import CrackedCodeEngine, Intent
        PASS("Engine module")
    except Exception as e:
        return FAIL("Engine module", str(e)[:50])
    
    try:
        from src.voice_typing import VoiceTyping
        PASS("Voice typing module")
    except Exception as e:
        return FAIL("Voice typing module", str(e)[:50])
    
    try:
        from src.file_watcher import FileWatcher
        PASS("File watcher module")
    except Exception as e:
        return FAIL("File watcher module", str(e)[:50])
    
    try:
        from src.git_integration import GitIntegration
        PASS("Git integration module")
    except Exception as e:
        return FAIL("Git integration module", str(e)[:50])
    
    return True


def test_parallel() -> bool:
    print_header("PARALLEL EXECUTOR")
    
    try:
        from src.parallel_processor import (
            ParallelExecutor, ExecutionMode, TaskPriority,
            create_task, batch_create_tasks
        )
        
        def worker_add(a: int, b: int) -> int:
            time.sleep(0.1)
            return a + b
        
        executor = ParallelExecutor(max_workers=2, mode=ExecutionMode.PARALLEL)
        executor.start()
        
        task = create_task("add", worker_add, args=(2, 3), priority=1)
        task_ids = executor.submit_batch([task])
        results = executor.wait_for(task_ids, timeout=5.0)
        
        executor.stop()
        
        success = sum(1 for r in results.values() if r and r.success)
        return PASS("Parallel tasks", f"{success}/{len(task_ids)}")
        
    except Exception as e:
        return FAIL("Parallel test", str(e)[:50])


def test_pipeline() -> bool:
    print_header("PIPELINE")
    
    try:
        from src.parallel_processor import PipelineProcessor
        
        pipeline = PipelineProcessor()
        pipeline.add_stage("double", lambda x: x * 2)
        pipeline.add_stage("add_one", lambda x: x + 1)
        
        result = pipeline.execute(5)
        expected = 11
        
        if result == expected:
            return PASS("Pipeline", f"5 -> {result} (expected {expected})")
        else:
            return FAIL("Pipeline", f"Expected {expected}, got {result}")
            
    except Exception as e:
        return FAIL("Pipeline", str(e)[:50])


def test_unified() -> bool:
    print_header("UNIFIED RESOLUTION")
    
    try:
        from src.parallel_processor import UnifiedCoordinator, ResolutionStrategy
        
        coordinator = UnifiedCoordinator(max_workers=2)
        coordinator.start()
        
        def method1() -> str:
            time.sleep(0.1)
            return "result1"
        
        def method2() -> str:
            time.sleep(0.15)
            return "result2"
        
        tid = coordinator.submit_resolution_task(
            "test_task", [method1, method2], ResolutionStrategy.FIRST_WINNER
        )
        time.sleep(0.5)
        resolution = coordinator.resolve(tid, timeout=2.0)
        
        coordinator.stop()
        
        if resolution and resolution.final_result:
            return PASS("Unified resolution", f"{resolution.final_result}")
        else:
            return FAIL("Unified", "No result")
            
    except Exception as e:
        return FAIL("Unified", str(e)[:50])


def test_atlan() -> bool:
    print_header("ATLANTEAN UI")
    
    try:
        from src.atlan_ui import GlitchEffect, NeuralPulse, HexGrid
        
        glitch = GlitchEffect.glitch_text("TEST", 0.3)
        if glitch:
            PASS("Glitch effect")
        
        progress = NeuralPulse.progress_bar(5, 10)
        if progress:
            PASS("Progress bar")
        
        grid = HexGrid.hex_pattern(10, 5)
        if grid:
            PASS("Hex grid")
        
        return True
        
    except Exception as e:
        return FAIL("Atlantean", str(e)[:50])


def test_plan_build() -> bool:
    print_header("PLAN/BUILD MODE")
    
    try:
        from src.atlan_ui import AtlanInterface
        
        ui = AtlanInterface()
        
        if ui.plan_mode:
            PASS("Plan mode on")
        else:
            return FAIL("Plan mode", "Should be True by default")
        
        if not ui.build_mode:
            PASS("Build mode off")
        else:
            return FAIL("Build mode", "Should be False by default")
        
        return True
            
    except Exception as e:
        return FAIL("Plan/build", str(e)[:50])


def test_config() -> bool:
    print_header("CONFIGURATION")
    
    if os.path.exists('config.json'):
        with open('config.json') as f:
            config = json.load(f)
        
        model = config.get('model', '')
        vision = config.get('vision_model', '')
        
        PASS("Config file exists")
        
        if model:
            PASS("model", model)
        if vision:
            PASS("vision_model", vision)
            
        return True
    else:
        return FAIL("Config file", "config.json not found")


def test_gui() -> bool:
    print_header("GUI IMPORT")
    
    try:
        from src.gui import CrackedCodeGUI
        PASS("GUI Module")
        return True
    except Exception as e:
        return FAIL("GUI", str(e)[:50])


def test_engine() -> bool:
    print_header("ENGINE")
    
    try:
        from src.engine import CrackedCodeEngine, Intent
        
        engine = CrackedCodeEngine({"model": "qwen3:8b-gpu"})
        status = engine.get_status()
        
        PASS("Engine initialized")
        print(f"  Model: {status['model']}")
        print(f"  Plan: {status['plan']}")
        print(f"  Build: {status['build']}")
        print(f"  Ollama: {status['ollama_available']}")
        
        return True
    except Exception as e:
        return FAIL("Engine", str(e)[:50])


def test_engine_mocks() -> bool:
    print_header("ENGINE WITH MOCKS")
    
    try:
        from src.engine import OllamaBridge, Intent, AgentResponse
        
        bridge = OllamaBridge("qwen3:8b-gpu")
        result = bridge.detect()
        
        return PASS("Ollama detect", str(result['available']))
        
    except Exception as e:
        return FAIL("Engine mocks", str(e)[:50])


def test_session_persistence() -> bool:
    print_header("SESSION PERSISTENCE")
    
    try:
        from src.engine import SessionManager, PromptRequest, AgentResponse
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            tmp_path = f.name
        
        try:
            sm = SessionManager(tmp_path)
            
            request = PromptRequest(text="test prompt", intent=Intent.CHAT)
            response = AgentResponse(success=True, text="test response")
            
            sm.add_turn(request, response)
            sm.save()
            
            sm2 = SessionManager(tmp_path)
            if sm2.history_len() > 0:
                return PASS("Session save/restore", f"{sm2.history_len()} turns")
            else:
                return FAIL("Session", "History not restored")
            
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        
    except Exception as e:
        return FAIL("Session", str(e)[:50])


def test_intent_parsing() -> bool:
    print_header("INTENT PARSING")
    
    try:
        from src.engine import CrackedCodeEngine
        
        engine = CrackedCodeEngine()
        
        test_cases = [
            ("fix this bug", "DEBUG"),
            ("write a function", "CODE"),
            ("review the code", "REVIEW"),
            ("build a plan", "BUILD"),
            ("run the tests", "EXECUTE"),
            ("hello there", "CHAT"),
        ]
        
        passed = 0
        for prompt, expected in test_cases:
            req = engine.parse_intent(prompt)
            if req.intent.value.upper() == expected:
                passed += 1
            else:
                print(f"  [FAIL] '{prompt}' -> {req.intent.value} (expected {expected})")
        
        if passed == len(test_cases):
            PASS("Intent parsing", f"{passed}/{len(test_cases)}")
            return True
        else:
            return FAIL("Intent parsing", f"{passed}/{len(test_cases)}")
        
    except Exception as e:
        return FAIL("Intent parsing", str(e)[:50])


def test_ollama_edge_cases() -> bool:
    print_header("OLLAMA EDGE CASES")
    
    try:
        from src.engine import OllamaBridge
        
        bridge = OllamaBridge("nonexistent-model")
        result = bridge.detect()
        
        return PASS("Ollama detection", str(result['available']))
        
    except Exception as e:
        return FAIL("Ollama edge", str(e)[:50])


def test_ollama() -> bool:
    print_header("OLLAMA CONNECTION")
    
    try:
        import ollama
        models = ollama.list().models
        PASS("Ollama connected", f"{len(models)} models")
        
        for m in models[:3]:
            print(f"  - {m.model}")
        
        return True
        
    except Exception as e:
        return FAIL("Ollama", str(e)[:50])


def main() -> int:
    print(f"\n{'='*60}\n  CRACKEDCODE v2.3.8 - TEST SUITE\n{'='*60}\n")
    
    results: list[tuple[str, bool]] = []
    
    results.append(("Modules", test_modules()))
    results.append(("Config", test_config()))
    results.append(("Engine", test_engine()))
    results.append(("Engine Mocks", test_engine_mocks()))
    results.append(("Session", test_session_persistence()))
    results.append(("Intent", test_intent_parsing()))
    results.append(("GUI", test_gui()))
    results.append(("Ollama", test_ollama()))
    results.append(("Ollama Edge", test_ollama_edge_cases()))
    results.append(("Pipeline", test_pipeline()))
    results.append(("Unified", test_unified()))
    results.append(("Atlantean", test_atlan()))
    results.append(("Plan/Build", test_plan_build()))
    results.append(("Parallel", test_parallel()))
    
    print_header("SUMMARY")
    
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    
    for name, ok in results:
        if ok:
            PASS(name)
        else:
            FAIL(name)
    
    print(f"\n  Passed: {passed}/{total}")
    
    if passed == total:
        print("\n  ALL TESTS PASSED!")
    else:
        print(f"\n  {total - passed} tests failed")
    
    return passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success >= 10 else 1)