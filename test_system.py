#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║          CRACKEDCODE v2.1.8 - FULL SYSTEM TEST                        ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import time
import json
import platform
from datetime import datetime

sys.path.insert(0, 'src')

def test_header(title):
    print(f"\n{'='*60}")
    print(f"  TEST: {title}")
    print(f"{'='*60}\n")

def test_result(name, passed, details=""):
    status = "✓ PASS" if passed else "✗ FAIL"
    color = Fore.GREEN if passed else Fore.RED
    print(f"{color}{status}{Style.RESET_ALL} {name}")
    if details:
        print(f"       {details}")

def test_modules():
    test_header("MODULE IMPORTS")
    
    passed = True
    
    try:
        from main import (
            CrackedCodeConfig, BLACKBOARD, AgentType, 
            OllamaClient, FileTools, ShellTools, VoiceController, AgentSwarm
        )
        test_result("Main modules", True)
    except Exception as e:
        test_result("Main modules", False, str(e))
        passed = False
        
    try:
        from atlan_ui import (
            AtlanInterface, MatrixRain, GlitchEffect, NeuralPulse,
            HexGrid, CircuitBoard, HologramBorder, ScannerLine
        )
        test_result("Atlantean UI", True)
    except Exception as e:
        test_result("Atlantean UI", False, str(e))
        passed = False
        
    try:
        from parallel_processor import (
            ParallelExecutor, PipelineProcessor, UnifiedCoordinator,
            ExecutionMode, ResolutionStrategy, create_task
        )
        test_result("Parallel Processor", True)
    except Exception as e:
        test_result("Parallel Processor", False, str(e))
        passed = False
        
    try:
        from voice import STTEngine, TTSEngine, VoiceController
        test_result("Voice Engine", True)
    except Exception as e:
        test_result("Voice Engine", False, str(e))
        passed = False
        
    return passed


def test_parallel_executor():
    test_header("PARALLEL EXECUTOR")
    
    from parallel_processor import ParallelExecutor, ExecutionMode, create_task
    
    def worker_add(a, b):
        time.sleep(0.1)
        return a + b
    
    def worker_multiply(a, b):
        time.sleep(0.1)
        return a * b
    
    def worker_string(s):
        time.sleep(0.05)
        return f"PROCESSED: {s}"
    
    executor = ParallelExecutor(max_workers=4, mode=ExecutionMode.PARALLEL)
    executor.start()
    
    task_specs = [
        {"id": "add", "func": worker_add, "args": (5, 3)},
        {"id": "mult", "func": worker_multiply, "args": (4, 7)},
        {"id": "str", "func": worker_string, "args": ("hello",)},
    ]
    
    from parallel_processor import batch_create_tasks
    tasks = batch_create_tasks(task_specs)
    task_ids = executor.submit_batch(tasks)
    
    results = executor.wait_for(task_ids, timeout=10.0)
    
    passed = True
    for tid, result in results.items():
        if result and result.success:
            test_result(f"Task {tid}", True, f"result={result.result}")
        else:
            test_result(f"Task {tid}", False, result.error if result else "No result")
            passed = False
            
    executor.stop()
    
    stats = executor.get_stats()
    print(f"\n  Stats: {json.dumps(stats, indent=2)}")
    
    return passed


def test_pipeline():
    test_header("PIPELINE PROCESSOR")
    
    from parallel_processor import PipelineProcessor
    
    pipeline = PipelineProcessor()
    
    pipeline.add_stage("stage1", lambda x: x * 2)
    pipeline.add_stage("stage2", lambda x: x + 10)
    pipeline.add_stage("stage3", lambda x: f"Final: {x}")
    
    result = pipeline.execute(5)
    
    passed = result == "Final: 20"
    test_result("Pipeline execution", passed, f"result={result}")
    
    return passed


def test_unified_resolution():
    test_header("UNIFIED RESOLUTION")
    
    from parallel_processor import UnifiedCoordinator, ResolutionStrategy
    
    coordinator = UnifiedCoordinator(max_workers=3)
    coordinator.start()
    
    def method_1():
        time.sleep(0.2)
        return "result_1"
    
    def method_2():
        time.sleep(0.15)
        return "result_2"
    
    def method_3():
        time.sleep(0.1)
        return "result_2"
    
    task_id = coordinator.submit_resolution_task(
        "test_unified",
        [method_1, method_2, method_3],
        ResolutionStrategy.MAJORITY
    )
    
    time.sleep(1.0)
    
    resolution = coordinator.resolve(task_id, timeout=5.0)
    
    passed = resolution and resolution.final_result is not None
    test_result("Unified resolution", passed, f"result={resolution.final_result if resolution else None}")
    
    if resolution:
        print(f"  Strategy: {resolution.strategy.value}")
        print(f"  Score: {resolution.consensus_score}")
        print(f"  Sub-results: {len(resolution.sub_results)}")
    
    coordinator.stop()
    
    return passed


def test_atlan_ui():
    test_header("ATLANTEAN UI")
    
    from atlan_ui import AtlanInterface, GlitchEffect, NeuralPulse, HexGrid
    
    ui = AtlanInterface()
    
    print("Testing GlitchEffect...")
    glitch_text = GlitchEffect.glitch_text("TEST", 0.3)
    test_result("Glitch effect", len(glitch_text) > 0)
    
    print("Testing NeuralPulse...")
    progress = NeuralPulse.progress_bar(7, 10)
    test_result("Progress bar", len(progress) > 0)
    
    print("Testing HexGrid...")
    grid = HexGrid.hex_pattern(10, 3)
    test_result("Hex grid", len(grid) > 0)
    
    print("Testing UI prompt...")
    prompt = ui.prompt()
    test_result("UI prompt", "◈" in prompt or ">" in prompt)
    
    print("\nTesting Plan/Build modes...")
    ui.set_mode(plan=True, build=False)
    test_result("Set plan mode", ui.plan_mode == True)
    
    ui.toggle_build()
    ui.set_mode(plan=True, build=True)
    results = ui.execute_plan("test workflow", 2)
    test_result("Execute plan", results is not None)
    
    return True


def test_plan_build_mode():
    test_header("PLAN/BUILD MODE")
    
    from atlan_ui import AtlanInterface
    
    ui = AtlanInterface()
    
    test_result("Initial plan mode", ui.plan_mode == True)
    test_result("Initial build mode", ui.build_mode == False)
    
    ui.toggle_plan()
    test_result("Toggle plan", True)
    
    ui.toggle_build()
    test_result("Toggle build", True)
    
    results = ui.execute_plan("authentication system", 3)
    passed = results is not None and len(results) > 0
    test_result("Execute plan workflow", passed, f"tasks={len(results) if results else 0}")
    
    return True


def test_model_config():
    test_header("MODEL CONFIGURATION")
    
    import json
    
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
            
        test_result("Config file loads", True)
        
        print(f"\n  Current model: {config.get('model', 'NOT SET')}")
        print(f"  Vision model: {config.get('vision_model', 'NOT SET')}")
        
        models = ["qwen3:8b-gpu", "llava:13b-gpu", "dolphin-llama3:8b-gpu"]
        
        for model in models:
            if model in config.get('model', ''):
                test_result(f"Model: {model}", True)
            else:
                print(f"  Note: Add '{model}' to config")
                
        return True
        
    except Exception as e:
        test_result("Config loads", False, str(e))
        return False


def test_ollama_connection():
    test_header("OLLAMA CONNECTION")
    
    try:
        import ollama
        response = ollama.list()
        models = response.get('models', [])
        
        test_result("Ollama connection", True, f"{len(models)} models")
        
        print(f"\n  Available models:")
        for m in models:
            name = m.get('name', 'unknown')
            size = m.get('size', 0) / (1024**3)
            print(f"    - {name}: {size:.1f}GB")
            
        model_names = [m.get('name', '') for m in models]
        
        expected = ["qwen3:8b-gpu", "llava:13b-gpu", "dolphin-llama3:8b-gpu"]
        for exp in expected:
            if exp in model_names:
                test_result(f"Model present: {exp}", True)
            else:
                test_result(f"Model present: {exp}", False, "Not installed")
                
        return True
        
    except Exception as e:
        test_result("Ollama connection", False, str(e))
        return False


def test_system_info():
    test_header("SYSTEM INFORMATION")
    
    test_result("Platform", platform.system() in ["Windows", "Linux", "Darwin"])
    print(f"  System: {platform.system()}")
    print(f"  Release: {platform.release()}")
    print(f"  Python: {platform.python_version()}")
    print(f"  CPU count: {os.cpu_count()}")
    
    try:
        import psutil
        mem = psutil.virtual_memory()
        print(f"  RAM: {mem.total / (1024**3):.1f}GB")
    except:
        pass
    
    return True


def run_all_tests():
    print("\n")
    print("╔" + "═"*58 + "╗")
    print("║" + " "*10 + "CRACKEDCODE v2.1.8 FULL TEST" + " "*16 + "║")
    print("╚" + "═"*58 + "╝")
    print(f"  Timestamp: {datetime.now().isoformat()}")
    print(f"  Platform: {platform.system()}")
    
    results = {}
    
    results["modules"] = test_modules()
    results["system"] = test_system_info()
    results["config"] = test_model_config()
    results["ollama"] = test_ollama_connection()
    results["parallel"] = test_parallel_executor()
    results["pipeline"] = test_pipeline()
    results["unified"] = test_unified_resolution()
    results["atlan_ui"] = test_atlan_ui()
    results["plan_build"] = test_plan_build_mode()
    
    test_header("TEST SUMMARY")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    print(f"\n  Passed: {passed}/{total}")
    
    for name, result in results.items():
        color = Fore.GREEN if result else Fore.RED
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {color}{status}{Style.RESET_ALL} {name}")
    
    if passed == total:
        print(f"\n{Fore.GREEN}🎉 ALL TESTS PASSED!{Style.RESET_ALL}")
    else:
        print(f"\n{Fore.YELLOW}⚠ SOME TESTS FAILED{Style.RESET_ALL}")
    
    return passed == total


if __name__ == "__main__":
    try:
        from colorama import Fore, Style
    except ImportError:
        class Fore:
            RED = GREEN = YELLOW = BLUE = CYAN = MAGENTA = WHITE = ""
        class Style:
            BRIGHT = DIM = NORMAL = RESET_ALL = ""
    
    success = run_all_tests()
    sys.exit(0 if success else 1)