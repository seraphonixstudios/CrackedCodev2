#!/usr/bin/env python3
"""
CRACKEDCODE v2.1.8 - Test Suite
"""

import os
import sys
import time

sys.path.insert(0, 'src')


def PASS(name, msg=""):
    print("[PASS] %s %s" % (name, msg))


def FAIL(name, msg=""):
    print("[FAIL] %s %s" % (name, msg))


def SKIP(name, msg=""):
    print("[SKIP] %s %s" % (name, msg))


def print_header(name, msg=""):
    print("\n%s\n  %s\n%s\n" % ("="*60, name, "="*60))


def test_modules():
    print_header("MODULE IMPORTS")
    
    try:
        from src.main import CrackedCodeConfig
        PASS("Main module")
    except Exception as e:
        FAIL("Main module", str(e)[:30])
        return False
    
    try:
        from src.atlan_ui import AtlanInterface
        PASS("Atlantean UI")
    except Exception as e:
        FAIL("Atlantean UI", str(e)[:30])
        return False
    
    try:
        from src.parallel_processor import ParallelExecutor
        PASS("Parallel processor")
    except Exception as e:
        FAIL("Parallel processor", str(e)[:30])
        return False
    
    return True


def test_parallel():
    print_header("PARALLEL EXECUTOR")
    
    try:
        from src.parallel_processor import ParallelExecutor, ExecutionMode
        from src.parallel_processor import batch_create_tasks
        
        def worker_add(a, b):
            time.sleep(0.1)
            return a + b
        
        executor = ParallelExecutor(max_workers=2, mode=ExecutionMode.PARALLEL)
        executor.start()
        
        tasks = batch_create_tasks([
            {"id": "add", "func": worker_add, "args": (2, 3)},
        ])
        
        ids = executor.submit_batch(tasks)
        results = executor.wait_for(ids, timeout=5.0)
        
        executor.stop()
        
        success = sum(1 for r in results.values() if r and r.success)
        PASS("Parallel tasks: %d/1" % success)
        return success > 0
        
    except Exception as e:
        FAIL("Parallel test", str(e)[:30])
        return False


def test_pipeline():
    print_header("PIPELINE")
    
    try:
        from src.parallel_processor import PipelineProcessor
        
        pipeline = PipelineProcessor()
        pipeline.add_stage("stage1", lambda x: x * 2)
        
        result = pipeline.execute(5)
        
        if result == 10:
            PASS("Pipeline: %d" % result)
            return True
        else:
            FAIL("Pipeline", "Expected 10, got %s" % result)
            return False
            
    except Exception as e:
        FAIL("Pipeline", str(e)[:30])
        return False


def test_unified():
    print_header("UNIFIED RESOLUTION")
    
    try:
        from src.parallel_processor import UnifiedCoordinator, ResolutionStrategy
        
        coordinator = UnifiedCoordinator(max_workers=2)
        coordinator.start()
        
        def method1():
            time.sleep(0.1)
            return "result1"
        
        tid = coordinator.submit_resolution_task("t", [method1], ResolutionStrategy.FIRST_WINNER)
        time.sleep(0.5)
        resolution = coordinator.resolve(tid, timeout=2.0)
        
        coordinator.stop()
        
        if resolution and resolution.final_result:
            PASS("Unified: %s" % resolution.final_result)
            return True
        else:
            FAIL("Unified", "No result")
            return False
            
    except Exception as e:
        FAIL("Unified", str(e)[:30])
        return False


def test_atlan():
    print_header("ATLANTEAN UI")
    
    try:
        from src.atlan_ui import GlitchEffect, NeuralPulse, HexGrid
        
        glitch = GlitchEffect.glitch_text("TEST", 0.3)
        if glitch:
            PASS("Glitch effect")
        
        progress = NeuralPulse.progress_bar(5, 10)
        if progress:
            PASS("Progress bar")
        
        return True
        
    except Exception as e:
        FAIL("Atlantean", str(e)[:30])
        return False


def test_plan_build():
    print("\n%s\n  PLAN/BUILD MODE\n%s\n" % ("="*60, "="*60))
    
    try:
        from src.atlan_ui import AtlanInterface
        
        ui = AtlanInterface()
        
        test_passed = True
        
        if ui.plan_mode == True:
            print("[PASS] Plan mode on (default)")
        else:
            print("[FAIL] Plan mode should be True")
            test_passed = False
        
        if ui.build_mode == False:
            print("[PASS] Build mode off (default)")
        else:
            print("[FAIL] Build mode should be False")
            test_passed = False
        
        return test_passed
            
    except Exception as e:
        print("[FAIL] Plan/build: %s" % str(e)[:30])
        return False
        
        if not ui.build_mode:
            PASS("Build mode off (default)")
        
        ui.set_mode(plan=True, build=True)
        
        if ui.plan_mode and ui.build_mode:
            PASS("Both modes enabled")
        
        PASS("Plan/Build mode configured")
        return True
            
    except Exception as e:
        print("  Exception: %s" % str(e)[:40])
        return False


def test_config():
    print_header("CONFIGURATION")
    
    import json
    
    if os.path.exists('config.json'):
        with open('config.json') as f:
            config = json.load(f)
        
        model = config.get('model', '')
        vision = config.get('vision_model', '')
        
        PASS("Config file")
        
        if model:
            PASS("model: %s" % model)
        if vision:
            PASS("vision_model: %s" % vision)
            
        return True
    else:
        FAIL("Config file")
        return False


def test_gui():
    print_header("GUI IMPORT")
    
    try:
        from src.gui import CrackedCodeGUI
        PASS("GUI Module")
        return True
    except Exception as e:
        FAIL("GUI", str(e)[:30])
        return False


def test_ollama():
    print_header("OLLAMA CONNECTION")
    
    try:
        import ollama
        models = ollama.list().models
        PASS("Ollama: %d models" % len(models))
        
        for m in models[:3]:
            print("  - %s" % m.model)
        
        return True
        
    except Exception as e:
        FAIL("Ollama", str(e)[:30])
        return False


def main():
    print("\n%s\n  CRACKEDCODE v2.2.1 - TEST SUITE\n%s\n" % ("="*60, "="*60))
    
    results = []
    
    results.append(("Modules", test_modules()))
    results.append(("Config", test_config()))
    results.append(("GUI", test_gui()))
    results.append(("Ollama", test_ollama()))
    results.append(("Pipeline", test_pipeline()))
    results.append(("Unified", test_unified()))
    results.append(("Atlantean", test_atlan()))
    results.append(("Plan/Build", test_plan_build()))
    
    print_header("SUMMARY")
    
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    
    for name, ok in results:
        if ok:
            PASS(name)
        else:
            FAIL(name)
    
    print("\n  Passed: %d/%d" % (passed, total))
    
    if passed == total:
        print("\n  ALL TESTS PASSED!")
    else:
        print("\n  %d tests failed" % (total - passed))
    
    return passed == total


if __name__ == "__main__":
    main()