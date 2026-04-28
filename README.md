# CrackedCode: Atlantean Neural System

Local AI Coding Assistant with Sci-Fi Neural Interface

<p align="center">
  <img src="https://img.shields.io/badge/Version-2.3.9-blue?style=for-the-badge" alt="Version">
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/badge/Platform-Linux%20%7C%20macOS%20%7C%20Windows-orange?style=for-the-badge" alt="Platform">
  <img src="https://img.shields.io/badge/Python-3.10%2B-yellow?style=for-the-badge" alt="Python">
  <img src="https://img.shields.io/badge/AI-Local%20Ollama-red?style=for-the-badge" alt="AI">
</p>

## Overview

CrackedCode is a **100% local AI coding assistant** featuring the Atlantean Neural Interface with agent orchestration, task queue management, voice commands, and Matrix-style effects. No cloud, no API keys - all running with Ollama.

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
| 2.3.9 | Complete UI overhaul, Task queue, Agent orchestration, Accessibility |
| 2.3.8 | Code generation pipeline, CLI CODE subcommand, Swarm integration |
| 2.3.5 | Project sidebar, agents panel, file watcher, git integration |

---

## Desktop GUI (v2.3.9)

```bash
python src/gui.py
```

### New UI Features

- **Dockable Panels**: Left control center with project files, agents, and task queue
- **Task Queue Widget**: Real-time status updates with pending/running/completed tracking
- **Agent Panel**: Visual status indicators with icons and capabilities
- **File Tree Widget**: Hierarchical project navigation
- **Menu Bar**: FILE/EDIT/VIEW/HELP with full keyboard shortcuts
- **Status Bar**: Live clock, task counter, Ollama status
- **Progress Bar**: Visual feedback during task processing

### Layout

```
┌─────────────────────────────────────────────────────────┐
│ MENU BAR: File | Edit | View | Help                       │
├─────────┬───────────────────────────────────────────────┤
│ CONTROL │ TOOLBAR: [PLAN][BUILD] [EXECUTE][VOICE]       │
│ CENTER  ├───────────────────────────────────────────────┤
│         │                                              │
│ Project │ CODE EDITOR                                   │
│ Files   │                                              │
│         │                                              │
│ ─────── │                                              │
│ AGENTS  │                                              │
│ S A C E │                                              │
│ R F     │                                              │
│         ├───────────────────────────────────────────────┤
│ ─────── │                                              │
│ TASK    │ TERMINAL: > Command input...                  │
│ QUEUE   │        [SEND]                                │
│ ○ ○ ●   │                                              │
│         ├───────────────────────────────────────────────┤
│ Progress│ STATUS: READY | OLLAMA: ON | Tasks: 3/5      │
└─────────┴───────────────────────────────────────────────┘
```

### Features

| Feature | Description |
|---------|-------------|
| **Project Files** | Tree view with hierarchical navigation |
| **Agent Panel** | 6 agents with real-time status |
| **Task Queue** | Live task tracking with status icons |
| **Voice Typing** | Click VOICE to record (faster-whisper) |
| **Code Editor** | Full text editor with syntax |
| **Terminal** | AI response display and input |
| **Matrix Overlay** | Animated rain effect |
| **Atlantean Theme** | Green `#00FF41` on black |

### Voice Commands

Natural language commands detected from voice input:

| Command | Keywords | Action |
|---------|----------|--------|
| stop | stop, cancel, abort, quit | Stop operation |
| execute | run, execute, go | Run code |
| save | save, store | Save file |
| copy | copy, clipboard | Copy output |
| clear | clear, wipe | Clear terminal |
| voice | voice, listen | Toggle voice mode |

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+N` | New project |
| `Ctrl+O` | Open project |
| `Ctrl+S` | Save file |
| `Ctrl+Q` | Quit |
| `Ctrl+Shift+C` | Copy output |
| `Ctrl+V` | Paste (image or text) |
| `Ctrl+A` | Select all |
| `Ctrl+Enter` | Send prompt |
| `F11` | Toggle fullscreen |
| `F12` | Dev console |
| `Escape` | Stop operation |

### Accessibility

All widgets have `AccessibleName` for screen readers:
- `AccessibleName="Code editor"` 
- `AccessibleName="Command input"`
- `AccessibleName="Send command"`

---

## Agent Orchestration

Tasks are automatically delegated to specialized agents based on intent:

```python
from src.gui import AgentOrchestrator, AgentTask, TaskStatus

orchestrator = AgentOrchestrator()

# Delegate based on intent
agent, task = orchestrator.delegate(Intent.CODE, "write a function")
print(f"Delegated to {agent} for task {task.task_id}")

# Check queue status
status = orchestrator.get_queue_status()
print(f"Pending: {status['pending']}, Running: {status['running']}")

# Complete when done
orchestrator.complete_task(task.task_id, "generated code here")
```

### Agent Types

| Agent | Role | Capabilities |
|-------|------|--------------|
| Supervisor | Coordinates | Delegate, manage |
| Architect | Design | Planning, architecture |
| Coder | Implementation | Code, write, modify |
| Executor | Execution | Run, execute, test |
| Reviewer | Analysis | Review, debug, fix |
| Searcher | Discovery | Search, find, grep |

### Task States

- `○` Pending
- `◐` Running  
- `●` Completed
- `✕` Failed
- `⊘` Cancelled

---

## Code Generation Pipeline

```bash
# CLI code generation
python src/main.py code -p "write a hello world function"

# Save to file
python src/main.py code -p "create hello.py" -o hello.py

# With validation
python src/main.py code -p "write function" --validate

# With Swarm
python src/main.py code -p "write parser" --swarm
```

### API

```python
from src.engine import CrackedCodeEngine

engine = CrackedCodeEngine()

# Generate code
response = engine.generate_code("write a function to add numbers")

# Generate and save
response = engine.generate_and_save("create hello.py", "hello.py")

# Validate
result = engine.validate_code("def foo(): return 1")

# Execute
result = engine.execute_generated_code("print('Hello!')")
```

---

## Intent Detection

The engine automatically detects user intent:

| Intent | Keywords | Agent |
|--------|----------|-------|
| CODE | write, create, generate | Coder |
| DEBUG | fix, bug, error | Reviewer |
| REVIEW | review, analyze | Reviewer |
| BUILD | build, plan, design | Architect |
| EXECUTE | run, execute | Executor |
| SEARCH | search, find, grep | Searcher |
| HELP | help, assist | Supervisor |
| CHAT | other | Coder |

---

## Image Paste & Drop

- **Paste images**: `Ctrl+V` in editor
- **Drop images**: Drag & drop PNG/JPG/GIF/BMP
- Images processed through vision model (llava)

---

## Parallel Processor

```python
from src.parallel_processor import (
    ParallelExecutor, PipelineProcessor, CodeSwarmCoordinator,
    ExecutionMode, create_task, batch_create_tasks
)

# Parallel execution
executor = ParallelExecutor(max_workers=4, mode=ExecutionMode.PARALLEL)
executor.start()
task_ids = executor.submit_batch(tasks)
results = executor.wait_for(task_ids)
executor.stop()

# Pipeline processing
pipeline = PipelineProcessor()
pipeline.add_stage("stage1", lambda x: x * 2)
pipeline.add_stage("stage2", lambda x: x + 1)
result = pipeline.execute(5)  # 11
```

---

## Voice Typing

```python
from src.voice_typing import VoiceTyping

voice = VoiceTyping(model_size="base")

# Record and transcribe
result = voice.listen_and_transcribe(duration=5.0)
print(result.text, result.confidence)

# Detect voice commands
cmd = voice.detect_command("stop recording")
print(cmd)  # "stop"
```

---

## Plan/Build Mode Toggle

| Mode | Function |
|------|----------|
| PLAN only | Analyze and plan |
| BUILD only | Execute plan |
| PLAN + BUILD | Full workflow |

---

## Atlantean Sci-Fi UI

```python
from src.atlan_ui import *

atlan_ui.print_system_info()
atlan_ui.loading_sequence("INITIALIZING")
atlan_ui.print_data_stream("ONLINE", "hex", 1.0)

# Effects
GlitchEffect.glitch_text("SYSTEM")
NeuralPulse.progress_bar(7, 10)
HexGrid.hex_pattern(20, 5)
MatrixRain(width=40, height=20).start(3.0)
```

---

## File Structure

```
crackedcode/
├── src/
│   ├── main.py              # CLI application
│   ├── gui.py               # PyQt6 Desktop GUI
│   ├── atlan_ui.py          # Sci-Fi UI effects
│   ├── voice_typing.py      # Voice typing
│   ├── parallel_processor.py # Parallel executor
│   ├── engine.py            # CrackedCodeEngine
│   ├── file_watcher.py      # File monitor
│   └── git_integration.py  # Git integration
├── tests/
├── test_system.py           # 32 E2E tests
├── config.json
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

### Models

| Model | Purpose |
|-------|---------|
| qwen3:8b-gpu | Code generation |
| dolphin-llama3:8b-gpu | Conversation |
| llava:13b-gpu | Vision |

---

## Testing

```bash
python test_system.py
```

### Test Coverage

- Module imports (7)
- Configuration (4)
- Ollama Bridge (3)
- Intent parsing (8)
- Code Execution
- GUI Components
- Voice Typing
- Parallel Executor
- Pipeline Processor
- Code Generation
- E2E Flows

---

## License

MIT

---

**CrackedCode v2.3.9** - The Final Boss of Local AI Coding Agents