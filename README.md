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

CrackedCode is a 100% local AI coding assistant featuring the Atlantean Neural Interface with parallel processing, plan/build modes, and Matrix-style effects.

### Version History

| Version | Features |
|---------|----------|
| 2.3.8 | Comprehensive tests (21/21), bug fixes, search intent, voice typing |
| 2.3.5 | Project sidebar, agents panel, file watcher, git integration |
| 2.3.0 | CrackedCodeEngine architecture |

### Running

```bash
python src/gui.py        # Desktop GUI (Recommended)
python src/main.py       # CLI mode
python src/atlan_ui.py   # CLI with Atlantean UI
```

## Desktop GUI

```bash
python src/gui.py
```

### Features

- **Left Sidebar**: Project files, AGENTS list, TASK status
- **Voice Typing**: Click VOICE button to record and transcribe speech (faster-whisper)
- **Code Editor**: Large text area
- **Terminal**: Input prompts, view responses
- **Toolbar**: PLAN/BUILD toggles, VOICE button, EXECUTE button
- **Matrix Overlay**: Animated rain effect
- **Atlantean Theme**: Green `#00FF41` on black
- **Single Instance**: Prevents duplicates
- **Ollama Auto-Detection**: Health check on startup
- **Dev Console**: Press F12

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| F12 | Toggle Dev Console |
| Enter | Submit prompt |

### Status Bar

Shows: READY state, OLLAMA status (ON/OFF), selected MODEL

### Dev Console (F12)

Shows:
- Version
- Ollama available status
- All available Ollama models
- Host and selected model
- Plan/Build state
- Conversation history length

### Usage

1. **NEW/OPEN** - Select project folder (files appear in sidebar)
2. **Type prompt** in terminal input line + Enter
3. **PLAN toggle** - Enable/disable AI processing
4. **BUILD toggle** - Enable/disable code execution
5. **VOICE toggle** - Voice input mode (requires sounddevice)
6. **Press SPACE** - Record voice (3s) when VOICE enabled
7. **EXECUTE** - Run code directly
8. **F12** - Dev console for diagnostics

### CrackedCodeEngine

Programmatic API:

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

### Parallel Processor

Multi-core task execution with multiple modes:

```python
from src.parallel_processor import (
    ParallelExecutor, PipelineProcessor, UnifiedCoordinator, DistributedProcessor,
    ExecutionMode, create_task, batch_create_tasks
)
```

#### Parallel Execution

```python
executor = ParallelExecutor(max_workers=4, mode=ExecutionMode.PARALLEL)
executor.start()

# Create tasks
task_specs = [
    {"id": "task1", "func": worker_add, "args": (5, 3)},
    {"id": "task2", "func": worker_multiply, "args": (4, 7)},
]
tasks = batch_create_tasks(task_specs)

# Submit and wait
task_ids = executor.submit_batch(tasks)
results = executor.wait_for(task_ids)

executor.stop()
```

#### Pipeline Processing

```python
pipeline = PipelineProcessor()
pipeline.add_stage("stage1", lambda x: x * 2)
pipeline.add_stage("stage2", lambda x: x + 1)
pipeline.add_stage("stage3", lambda x: f"Result: {x}")

result = pipeline.execute(5)  # Result: "Result: 11"
```

#### Unified Resolution

```python
coordinator = UnifiedCoordinator(max_workers=3)
coordinator.start()

# Submit multiple methods
task_id = coordinator.submit_resolution_task(
    "unified_task",
    [func1, func2, func3],
    ResolutionStrategy.MAJORITY
)

# Resolve with consensus
resolution = coordinator.resolve(task_id)

coordinator.stop()
```

#### Distributed Processing

```python
dist = DistributedProcessor(nodes=["node1", "node2"])
dist.dispatch_task(task)
```

### Execution Modes

| Mode | Description |
|------|-------------|
| SEQUENTIAL | One task at a time |
| PARALLEL | Multiple workers |
| PIPELINE | Staged processing |
| UNIFIED | Multi-method consensus |
| DISTRIBUTED | Multi-node dispatch |

### Resolution Strategies

| Strategy | Behavior |
|----------|----------|
| FIRST_WINNER | Return first success |
| MAJORITY | >50% agrees |
| CONSENSUS | >=80% agrees |
| WEIGHTED | By execution time |

### Plan/Build Mode Toggle

```python
from src.atlan_ui import atlan_ui

# Set modes
atlan_ui.set_mode(plan=True, build=False)  # Plan only
atlan_ui.set_mode(plan=True, build=True)     # Full execution

# Toggle individually
atlan_ui.toggle_plan()
atlan_ui.toggle_build()

# Execute workflow
results = atlan_ui.execute_plan("build authentication", 5)
```

#### Mode States

| Mode | Function |
|------|----------|
| PLAN only | Analyze and plan tasks |
| BUILD only | Execute existing plan |
| PLAN + BUILD | Full workflow |
| Both OFF | Idle |

### Atlantean Sci-Fi UI

```python
from src.atlan_ui import *

# Print system banner
atlan_ui.print_system_info()

# Loading sequence
atlan_ui.loading_sequence("INITIALIZING")

# Data stream effect
atlan_ui.print_data_stream("SYSTEM ONLINE", "hex", 1.0)

# Status display
atlan_ui.print_status({"NEURAL CORE": "online"})

# Get stylized prompt
prompt = atlan_ui.prompt()  # Returns: "◈> "
```

### UI Effects

```python
# Glitch text
GlitchEffect.glitch_text("SYSTEM")

# Progress bar
NeuralPulse.progress_bar(7, 10)

# Hex grid
HexGrid.hex_pattern(20, 5)

# Circuit connection
CircuitBoard.draw_connection("cpu", "memory")

# Hologram box
HologramBorder.box("Content", "rounded")

# Scanner
ScannerLine.scan("SYSTEM", 3)

# Matrix rain
rain = MatrixRain(width=40, height=20)
rain.start(3.0)
```

### Vision System

```python
from src.main import VisionEngine

vision = VisionEngine(model="llama3.2-vision:11b")

# Analyze image
analysis = vision.analyze_image("screenshot.png")

# Describe image
description = vision.describe_image("screenshot.png", "What's in this?")

# OCR
text = vision.extract_text("screenshot.png")
```

### Natural Prompt Engine

```python
from src.main import NaturalTextPromptEngine, Intent, PromptStyle

engine = NaturalTextPromptEngine()
result = engine.process("fix the bug in auth.py")

# result = {'intent': 'debug', 'entities': ['auth.py'], ...}

engine.set_style(PromptStyle.TECHNICAL)
```

## Environment Variables

| Variable | Values | Description |
|----------|--------|-------------|
| CRACKEDCODE_DEBUG | true/false | Enable debug logging |
| CRACKEDCODE_VERBOSE | true/false | Verbose output |

## File Structure

```
crackedcode/
├── src/
│   ├── main.py              # Main application (CLI)
│   ├── gui.py               # PyQt6 Desktop GUI
│   ├── atlan_ui.py         # Sci-Fi UI effects
│   ├── voice.py           # Voice engine (STT/TTS)
│   ├── voice_typing.py    # Voice typing (faster-whisper)
│   ├── parallel_processor.py # Parallel executor
│   ├── engine.py          # CrackedCodeEngine
│   ├── file_watcher.py    # File change monitor
│   └── git_integration.py # Git status/diffs
├── tests/
├── config.json
├── pyproject.toml
├── logs/
└── README.md
```

## License

MIT

---

**CrackedCode: Atlantean Neural System** - The Final Boss of Local AI Coding Agents