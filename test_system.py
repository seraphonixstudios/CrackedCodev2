#!/usr/bin/env python3
"""
CRACKEDCODE v2.1.8 - Test Suite
"""

import os
import sys
import time

sys.path.insert(0, 'src')

try:
    from colorama import init, Fore, Style, Back
    init(autoreset=True)
except:
    class Fore:
        RED = GREEN = YELLOW = BLUE = CYAN = MAGENTA = WHITE = ""
    class Style:
        BRIGHT = DIM = NORMAL = RESET_ALL = ""


def test_header(title):
    print(f"\n{'='*60}")
    print(f"  TEST: {title}")
    print(f"{'='*60}\n")


def PASS(name):
    print(f"{Fore.GREEN}✓ PASS{Style.RESET_ALL} {name}")


def FAIL(name, error=""):
    print(f"{Fore.RED}✗ FAIL{Style.RESET_ALL} {name}")
    if error:
        print(f"       {error}")


def SKIP(name, reason=""):
    print(f"{Fore.YELLOW}⚠ SKIP{Style.RESET_ALL} {name}")


def test_modules():
    test_header("MODULE IMPORTS")
    
    try:
        from src.main import CrackedCodeConfig
        PASS("Main module loads")
    except Exception as e:
        FAIL("Main module", str(e)[:50])
        return False
    
    try:
        from src.atlan_ui import AtlanInterface
        PASS("Atlantean UI loads")
    except Exception as e:
        FAIL("Atlantean UI", str(e)[:50])
        return False
    
    try:
        from src.parallel_processor import ParallelExecutor
        PASS("Parallel processor loads")
    except Exception as e:
        FAIL("Parallel processor", str(e)[:50])
        return False
    
    return True


def test_parallel():
    test_header("PARALLEL PROCESSOR")
    
    try:
        from src.parallel_processor import ParallelExecutor, ExecutionMode, create_task
        from src.parallel_processor import batch_create_tasks
        
        def worker_add(a, b):
            time.sleep(0.1)
            return a + b
        
        def worker_mul(a, b):
            time.sleep(0.1)
            return a * b
        
        executor = ParallelExecutor(max_workers=2, mode=ExecutionMode.PARALLEL)
        executor.start()
        
        tasks = batch_create_tasks([
            {"id": "add", "func": worker_add, "args": (2, 3)},
            {"id": "mul", "func": worker_mul, "args": (4, 5)},
        ])
        
        ids = executor.submit_batch(tasks)
        results = executor.wait_for(ids, timeout=5.0)
        
        success_count = sum(1 for r in results.values() if r and r.success)
        
        executor.stop()
        
        PASS(f"Parallel tasks: {success_count}/2 completed")
        return success_count > 0
        
    except Exception as e:
        FAIL("Parallel test", str(e)[:50])
        return False


def test_pipeline():
    test_header("PIPELINE PROCESSOR")
    
    try:
        from src.parallel_processor import PipelineProcessor
        
        pipeline = PipelineProcessor()
        pipeline.add_stage("stage1", lambda x: x * 2)
        pipeline.add_stage("stage2", lambda x: x + 10)
        
        result = pipeline.execute(5)
        
        if result == 20:
            PASS(f"Pipeline result: {result}")
            return True
        else:
            FAIL("Pipeline", f"Expected 20, got {result}")
            return False
            
    except Exception as e:
        FAIL("Pipeline test", str(e)[:50])
        return False


def test_unified():
    test_header("UNIFIED RESOLUTION")
    
    try:
        from src.parallel_processor import UnifiedCoordinator, ResolutionStrategy
        
        coordinator = UnifiedCoordinator(max_workers=2)
        coordinator.start()
        
        def method1():
            time.sleep(0.1)
            return "result1"
        
        def method2():
            time.sleep(0.05)
            return "result1"
        
        tid = coordinator.submit_resolution_task(
            "test", [method1, method2], ResolutionStrategy.FIRST_WINNER
        )
        
        time.sleep(1.0)
        resolution = coordinator.resolve(tid, timeout=3.0)
        
        coordinator.stop()
        
        if resolution and resolution.final_result:
            PASS(f"Unified resolution: {resolution.final_result}")
            return True
        else:
            FAIL("Unified", "No result")
            return False
            
    except Exception as e:
        FAIL("Unified test", str(e)[:50])
        return False


def test_atlan():
    test_header("ATLANTEAN UI")
    
    try:
        from src.atlan_ui import GlitchEffect, NeuralPulse, HexGrid
        
        glitch = GlitchEffect.glitch_text("TEST", 0.3)
        if glitch:
            PASS("Glitch effect")
        
        progress = NeuralPulse.progress_bar(5, 10)
        if progress:
            PASS("Progress bar")
        
        grid = HexGrid.hex_pattern(5, 3)
        if grid:
            PASS("Hex grid")
        
        return True
        
    except Exception as e:
        FAIL("Atlantean UI", str(e)[:50])
        return False


def test_plan_build():
    test_header("PLAN/BUILD MODE")
    
    try:
        from src.atlan_ui import AtlanInterface
        
        ui = AtlanInterface()
        
        if ui.plan_mode:
            PASS("Plan mode enabled")
        
        if not ui.build_mode:
            PASS("Build mode disabled initially")
        
        results = ui.execute_plan("test workflow", 2)
        
        if results:
            PASS(f"Execute plan: {len(results)} tasks")
            return True
        else:
            FAIL("Execute plan", "No results")
            return False
            
    except Exception as e:
        FAIL("Plan/Build", str(e)[:50])
        return False


def test_config():
    test_header("CONFIGURATION")
    
    if os.path.exists('config.json'):
        import json
        with open('config.json') as f:
            config = json.load(f)
        PASS("Config file exists")
        
        model = config.get('model', '')
        if model:
            PASS(f"Model: {model}")
        else:
            print("  Note: No model set in config")
        
        return True
    else:
        FAIL("Config file")
        return False


def test_ollama():
    test_header("OLLAMA CONNECTION")
    
    try:
        import ollama
        models = ollama.list().get('models', [])
        PASS(f"Ollama: {len(models)} models")
        
        model_names = [m.get('name','') for m in models]
        if model_names:
            for name in model_names[:3]:
                print(f"  - {name}")
        
        return True
        
    except Exception as e:
        FAIL("Ollama connection", str(e)[:50])
        return False


def main():
    print("\n" + "="*60)
    print("  CRACKEDCODE v2.1.8 - TEST SUITE")
    print("="*60 + "\n")
    
    results = []
    
    results.append(("Modules", test_modules()))
    results.append(("Config", test_config()))
    results.append(("Ollama", test_ollama()))
    results.append(("Pipeline", test_pipeline()))
    results.append(("Unified", test_unified()))
    results.append(("Atlantean", test_atlan()))
    results.append(("Plan/Build", test_plan_build()))
    
    test_header("SUMMARY")
    
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    
    for name, ok in results:
        if ok:
            PASS(name)
        else:
            FAIL(name)
    
    print(f"\n  Passed: {passed}/{total}")
    
    if passed == total:
        print(f"\n{Fore.GREEN}✓ ALL TESTS PASSED!{Style.RESET_ALL}")
    else:
        print(f"\n{Fore.YELLOW}⚠ {total-passed} tests failed{Style.RESET_ALL}")
    
    return passed == total


if __name__ == "__main__":
    main()