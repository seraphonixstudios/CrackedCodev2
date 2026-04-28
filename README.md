# CrackedCode: Atlantean Neural System

Local AI Coding Assistant with Sci-Fi Neural Interface

<p align="center">
  <img src="https://img.shields.io/badge/Version-2.3.8-blue?style=for-the-badge" alt="Version">
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/badge/Platform-Linux%20%7C%20macOS%20%7C%20Windows-orange?style=for-the-badge" alt="Platform">
  <img src="https://img.shields.io/badge/Python-3.10%2B-yellow?style=for-the-badge" alt="Python">
  <img src="https://img.shields.io/badge/AI-Local%20Ollama-red?style=for-the-badge" alt="AI">
</p>

## Overview

CrackedCode is a **100% local AI coding assistant** featuring the Atlantean Neural Interface with parallel processing, plan/build modes, and Matrix-style effects. No cloud, no API keys - all running with Ollama.

### Quick Start

```bash
# Desktop GUI (Recommended)
python src/gui.py

# CLI with code generation
python src/main.py code -p "write a function to add numbers"

# Run tests
python test_system.py
```

### Version History

| Version | Features |
|---------|----------|
| 2.3.8 | Code generation pipeline, CLI CODE subcommand, Swarm integration, 32 E2E tests |
| 2.3.5 | Project sidebar, agents panel, file watcher, git integration |
| 2.3.0 | CrackedCodeEngine architecture |

---

## Code Generation Pipeline

The core feature - generate, validate, and execute code from natural language prompts.

### CLI CODE Subcommand

```bash
# Basic code generation
python src/main.py code -p "write a hello world function"

# Save to file
python src/main.py code -p "create hello.py with hello world" -o hello.py

# With validation
python src/main.py code -p "write a sort function" --validate

# With Swarm (parallel workers)
python src/main.py code -p "write a parser" --swarm

# Combined options
python src/main.py code -p "create calculator.py" -o calculator.py --swarm --validate
```

### Code Generation API

```python
from src.engine import CrackedCodeEngine

engine = CrackedCodeEngine()

# Generate code from prompt
response = engine.generate_code("write a function to add two numbers")
print(response.text)

# Generate and save to file
response = engine.generate_and_save("create hello.py", "hello.py")

# Validate code
result = engine.validate_code("def foo(): return 1")

# Execute code
result = engine.execute_generated_code("print('Hello!')")
print(result.stdout)
```

### Swarm Integration

Multiple AI workers collaborate on complex tasks:

```python
from src.parallel_processor import CodeSwarmCoordinator

swarm = CodeSwarmCoordinator(max_workers=4)

# Generate with swarm
result = swarm.generate_code("write a REST API")
print(result.result)

# Generate with validation
result = swarm.generate_with_validation("create parser", "parser.py")
print(result.success)
```

---

## Intent Detection

The engine automatically detects what you want:

| Intent | Keywords | Action |
|--------|----------|--------|
| CODE | write, create, generate | Generate code |
| DEBUG | fix, bug, error | Find and fix issues |
| REVIEW | review, analyze | Analyze code quality |
| BUILD | build, plan, design | Create implementation plan |
| EXECUTE | run, execute | Execute shell commands |
| SEARCH | search, find, grep | Search files |
| HELP | help | Get assistance |
| CHAT | other | General conversation |

---

## Desktop GUI

```bash
python src/gui.py
```

### Features

- **Left Sidebar**: Project files, AGENTS list, TASK status
- **Voice Typing**: Click VOICE button to record and transcribe speech (faster-whisper)
- **Code Editor**: Large text area with syntax
- **Terminal**: Input prompts, view AI responses
- **Toolbar**: PLAN/BUILD toggles, VOICE button, EXECUTE button
- **Matrix Overlay**: Animated rain effect
- **Atlantean Theme**: Green `#00FF41` on black

### Usage

1. **NEW/OPEN** - Select project folder
2. **Type prompt** + Enter to submit
3. **EXECUTE** - Run code in editor
4. **VOICE** - Click to speak your request
5. **F12** - Dev console

---

## Parallel Processor

Multi-core task execution with multiple modes:

```python
from src.parallel_processor import (
    ParallelExecutor, PipelineProcessor, UnifiedCoordinator,
    ExecutionMode, create_task, batch_create_tasks
)
```

### Parallel Execution

```python
executor = ParallelExecutor(max_workers=4, mode=ExecutionMode.PARALLEL)
executor.start()

task_specs = [
    {"id": "task1", "func": worker_add, "args": (5, 3)},
    {"id": "task2", "func": worker_multiply, "args": (4, 7)},
]
tasks = batch_create_tasks(task_specs)
task_ids = executor.submit_batch(tasks)
results = executor.wait_for(task_ids)

executor.stop()
```

### Pipeline Processing

```python
pipeline = PipelineProcessor()
pipeline.add_stage("stage1", lambda x: x * 2)
pipeline.add_stage("stage2", lambda x: x + 1)
result = pipeline.execute(5)  # Result: 11
```

### Execution Modes

| Mode | Description |
|------|-------------|
| SEQUENTIAL | One task at a time |
| PARALLEL | Multiple workers |
| PIPELINE | Staged processing |
| UNIFIED | Multi-method consensus |

---

## Plan/Build Mode Toggle

```python
from src.atlan_ui import atlan_ui

# PLAN only - analyze and plan
atlan_ui.set_mode(plan=True, build=False)

# PLAN + BUILD - full workflow
atlan_ui.set_mode(plan=True, build=True)

# Execute workflow
results = atlan_ui.execute_plan("build authentication", 5)
```

| Mode | Function |
|------|----------|
| PLAN only | Analyze and plan tasks |
| BUILD only | Execute existing plan |
| PLAN + BUILD | Full workflow |

---

## Atlantean Sci-Fi UI

```python
from src.atlan_ui import *

atlan_ui.print_system_info()
atlan_ui.loading_sequence("INITIALIZING")
atlan_ui.print_data_stream("SYSTEM ONLINE", "hex", 1.0)
atlan_ui.print_status({"NEURAL CORE": "online"})

# UI Effects
GlitchEffect.glitch_text("SYSTEM")
NeuralPulse.progress_bar(7, 10)
HexGrid.hex_pattern(20, 5)
MatrixRain(width=40, height=20).start(3.0)
```

---

## Vision System

```python
from src.main import VisionEngine

vision = VisionEngine(model="llava:13b-gpu")

# Analyze image
analysis = vision.analyze_image("screenshot.png")

# Extract text (OCR)
text = vision.extract_text("screenshot.png")
```

---

## Voice Typing

Speech-to-text using faster-whisper:

```python
from src.voice_typing import VoiceTyping

voice = VoiceTyping()
result = voice.transcribe()
print(result.text, result.confidence)
```

---

## CrackedCodeEngine API

```python
from src.engine import get_engine, Intent

engine = get_engine({"model": "qwen3:8b-gpu"})

status = engine.get_status()
print(f"Ollama: {status['ollama_available']}")
print(f"Models: {status['ollama_models']}")

import asyncio
response = asyncio.run(engine.process("Hello"))
print(response.text)
```

### Available Methods

| Method | Description |
|--------|-------------|
| `generate_code(prompt)` | Generate code from text |
| `generate_and_save(prompt, filepath)` | Generate and save to file |
| `validate_code(code)` | Validate syntax |
| `execute_generated_code(code)` | Execute in sandbox |
| `process(text)` | Process natural language |
| `get_status()` | Get Ollama status |

---

## Natural Prompt Engine

```python
from src.main import NaturalTextPromptEngine, Intent, PromptStyle

engine = NaturalTextPromptEngine()
result = engine.process("fix the bug in auth.py")

# result = {'intent': 'debug', 'entities': ['auth.py'], ...}

engine.set_style(PromptStyle.TECHNICAL)
```

---

## File Structure

```
crackedcode/
├── src/
│   ├── main.py              # Main application (CLI)
│   ├── gui.py               # PyQt6 Desktop GUI
│   ├── atlan_ui.py         # Sci-Fi UI effects
│   ├── voice_typing.py     # Voice typing (faster-whisper)
│   ├── parallel_processor.py # Parallel executor
│   ├── engine.py           # CrackedCodeEngine
│   ├── file_watcher.py    # File change monitor
│   └── git_integration.py  # Git status/diffs
├── tests/
├── test_system.py           # 32 E2E tests
├── config.json
├── pyproject.toml
└── README.md
```

---

## Configuration

```json
{
  "model": "qwen3:8b-gpu",
  "temperature": 0.1,
  "max_tokens": 4096,
  "ollama_host": "http://127.0.0.1:11434"
}
```

### Available Models

| Model | Purpose |
|-------|---------|
| qwen3:8b-gpu | Default code generation |
| dolphin-llama3:8b-gpu | General conversation |
| llava:13b-gpu | Vision/image analysis |

---

## Testing

```bash
python test_system.py
```

### Test Coverage (32 tests)

- Module imports (7)
- Configuration & Engine (4)
- Ollama Bridge (3)
- Intent parsing (8 intents)
- Code Execution (sandboxed)
- GUI Components
- Voice Typing (faster-whisper)
- File Watcher
- Git Integration
- Parallel Executor
- Pipeline Processor
- Code Generation Pipeline
- Code Save & Execute
- E2E Flows

---

## Environment Variables

| Variable | Values | Description |
|----------|--------|-------------|
| CRACKEDCODE_DEBUG | true/false | Enable debug logging |
| CRACKEDCODE_VERBOSE | true/false | Verbose output |

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| F12 | Toggle Dev Console |
| Enter | Submit prompt |

---

## License

MIT

---

**CrackedCode v2.3.8** - The Final Boss of Local AI Coding Agents