# CrackedCode: Atlantean Neural System

Local AI Coding Assistant with Sci-Fi Neural Interface

<p align="center">
  <img src="https://img.shields.io/badge/Version-2.5.0-blue?style=for-the-badge" alt="Version">
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/badge/Platform-Linux%20%7C%20macOS%20%7C%20Windows-orange?style=for-the-badge" alt="Platform">
  <img src="https://img.shields.io/badge/Python-3.10%2B-yellow?style=for-the-badge" alt="Python">
  <img src="https://img.shields.io/badge/AI-Local%20Ollama-red?style=for-the-badge" alt="AI">
</p>

## Overview

CrackedCode is a **100% local AI coding assistant** featuring the Atlantean Neural Interface with agent orchestration, task queue management, voice commands, streaming responses, response caching, and Matrix-style effects. No cloud, no API keys - all running with Ollama.

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
| 2.5.0 | Complete UI/UX overhaul, toast notifications, searchable terminal, command history, tab management, pulse indicators, task filtering |
| 2.4.0 | Streaming responses, response caching, context management, retry logic, tabbed editor |
| 2.3.9 | Complete UI overhaul, Task queue, Agent orchestration, Accessibility |
| 2.3.8 | Code generation pipeline, CLI CODE subcommand, Swarm integration |
| 2.3.5 | Project sidebar, agents panel, file watcher, git integration |

---

## Desktop GUI (v2.5.0)

```bash
python src/gui.py
```

### New UI Features

- **Toast Notifications**: Animated notifications with auto-dismiss and color-coded types
- **Searchable Terminal**: Ctrl+F to search and highlight terminal output
- **Command History**: Up/Down arrow keys to navigate previous commands
- **Pulse Indicators**: Animated status dots for real-time agent activity
- **Task Filtering**: Filter tasks by status (ALL/PEND/RUN/DONE/FAIL)
- **Tab Management**: Rename tabs on double-click, modified indicators (*)
- **File Tree Icons**: Extension-based colored icons for files
- **Matrix Rain Toggle**: Ctrl+M or MATRIX button for sci-fi effect
- **Refresh File Tree**: One-click refresh of project files
- **Cache Size Display**: Real-time cache monitoring in status bar
- **Enhanced Progress Bar**: Gradient animation with smooth transitions
- **Improved Styling**: Rounded corners, hover states, better contrast

### Dockable Panels**: Left control center with project files, agents, and task queue
- **Task Queue Widget**: Real-time status updates with pending/running/completed tracking
- **Agent Panel**: Visual status indicators with icons and capabilities
- **File Tree Widget**: Hierarchical project navigation
- **Tabbed Editor**: Multiple file tabs with close functionality
- **Menu Bar**: FILE/EDIT/VIEW/HELP with full keyboard shortcuts
- **Status Bar**: Live clock, task counter, Ollama status
- **Progress Bar**: Visual feedback during task processing
- **Streaming Responses**: Real-time character-by-character output
- **Matrix Overlay**: Animated rain effect

### Layout

```
┌─────────────────────────────────────────────────────────┐
│ MENU BAR: File | Edit | View | Help                       │
├─────────┬───────────────────────────────────────────────┤
│ CONTROL │ TOOLBAR: [PLAN][BUILD] [EXECUTE][VOICE]       │
│ CENTER  │ [UNIFIED] [STREAM]                            │
│         ├───────────────────────────────────────────────┤
│ Project │ CODE EDITOR (Tabbed)                           │
│ Files   │ [untitled] [file1.py] [file2.py]              │
│         │                                               │
│ ─────── │                                               │
│ AGENTS  │                                               │
│ S A C E │                                               │
│ R F     │                                               │
│         ├───────────────────────────────────────────────┤
│ ─────── │                                               │
│ TASK    │ TERMINAL: > Command input...                  │
│ QUEUE   │        [SEND]                                │
│ ○ ○ ●   │                                               │
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
| **Code Editor** | Tabbed text editor with multiple files |
| **Terminal** | AI response display with streaming |
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
| `Ctrl+T` | New tab |
| `Ctrl+S` | Save file |
| `Ctrl+Shift+S` | Save as |
| `Ctrl+Q` | Quit |
| `Ctrl+Shift+C` | Copy output |
| `Ctrl+L` | Clear terminal |
| `Ctrl+V` | Paste (image or text) |
| `Ctrl+A` | Select all |
| `Ctrl+Enter` | Send prompt |
| `Ctrl+F` | Find in terminal |
| `Ctrl+M` | Toggle matrix rain |
| `F11` | Toggle fullscreen |
| `F12` | Dev console |
| `Escape` | Stop operation |
| `Up/Down` | Command history |

---

## Streaming Responses (v2.4.0)

Enable real-time character-by-character output from the AI:

```python
# In GUI: Click STREAM button in toolbar
# In config: "streaming_enabled": true

# Programmatic usage:
response = await engine.process(prompt, streaming=True, callback=lambda chunk: print(chunk, end=""))
```

### Benefits
- Immediate feedback during generation
- Better user experience for long responses
- Can cancel mid-stream if needed

---

## Response Caching (v2.4.0)

Automatic caching of responses to reduce redundant API calls:

```python
# Cache is enabled by default
# Cache key: hash of (model, system_prompt, prompt)

# Clear cache:
engine.ollama.clear_cache()

# Get cache stats:
stats = engine.ollama.get_cache_stats()
# {"size": 15, "context_length": 10, "max_context": 20}
```

### Benefits
- Faster response for repeated queries
- Reduced load on Ollama
- Automatic cache management

---

## Context Management (v2.4.0)

Automatic conversation history tracking:

```python
# Context is maintained automatically
# Max context window: 20 turns (configurable)

# Clear context:
engine.ollama.clear_context()

# Context is sent with each request for coherent conversations
```

---

## Retry Logic (v2.4.0)

Automatic retry on failed requests:

```python
# Default: 2 retries with exponential backoff
# Configurable in config.json: "max_retries": 2

# Backoff: 0.5s, 1s, 1.5s between retries
```

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
    ParallelExecutor, PipelineProcessor, UnifiedCoordinator,
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

# Unified resolution
coordinator = UnifiedCoordinator(max_workers=3)
coordinator.start()
task_id = coordinator.submit_resolution_task("test", [func1, func2, func3])
resolution = coordinator.resolve(task_id)
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

## Unified Intelligence Mode

Combine all 3 Ollama models into a single brain:

| Mode | Description |
|------|-------------|
| **UNIFIED** | Combines all models for comprehensive responses |
| **SINGLE** | Uses specialized models for specific tasks |

### Model Roles

| Model | Role | Strength |
|-------|------|----------|
| qwen3:8b-gpu | General/Code | Reasoning, coding, planning |
| dolphin-llama3:8b-gpu | Creative | Conversation, writing |
| llava:13b-gpu | Vision | Image analysis, OCR |

---

## Configuration

```json
{
  "model": "qwen3:8b-gpu",
  "temperature": 0.1,
  "max_tokens": 4096,
  "ollama_host": "http://127.0.0.1:11434",
  "unified_mode": false,
  "streaming_enabled": true,
  "cache_enabled": true,
  "max_context": 20,
  "max_retries": 2
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
- Response Caching
- Context Management
- Streaming Responses

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
├── test_system.py           # E2E tests
├── config.json
└── README.md
```

---

## License

MIT

---

**CrackedCode v2.5.0** - The Final Boss of Local AI Coding Agents
