# CrackedCode: Atlantean Neural System

Local AI Coding Assistant with Sci-Fi Neural Interface

<p align="center">
  <img src="https://img.shields.io/badge/Version-2.6.0-blue?style=for-the-badge" alt="Version">
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/badge/Platform-Linux%20%7C%20macOS%20%7C%20Windows-orange?style=for-the-badge" alt="Platform">
  <img src="https://img.shields.io/badge/Python-3.10%2B-yellow?style=for-the-badge" alt="Python">
  <img src="https://img.shields.io/badge/AI-Local%20Ollama-red?style=for-the-badge" alt="AI">
</p>

## Overview

CrackedCode is a **100% local AI coding assistant** featuring autonomous application production (OpenClaw-style), agent orchestration, task queue management, voice commands, streaming responses, response caching, and Matrix-style effects. No cloud, no API keys - all running with Ollama.

### Quick Start

```bash
# Desktop GUI (Recommended)
python src/gui.py

# CLI with code generation
python src/main.py code -p "write a function to add numbers"

# Autonomous production
python src/main.py autonomous -p "Build a todo app with web API and SQLite"

# Run tests
python test_system.py
```

### Version History

| Version | Features |
|---------|----------|
| 2.6.1 | **Codebase RAG** - Semantic search with local embeddings, context-aware code generation, autonomous existing codebase awareness |
| 2.6.0 | **Agent Reasoning Engine**, GUI Reasoning Panel, persistent reasoning memory, LLM meta-reasoning, autonomous production, unified orchestrator, SOTA voice engine, Git sidebar, file watcher, settings dialog, syntax highlighting, command palette |
| 2.5.0 | UI/UX overhaul, toast notifications, searchable terminal, command history, tab management, pulse indicators |
| 2.4.0 | Streaming responses, response caching, context management, retry logic, tabbed editor |
| 2.3.9 | Task queue, Agent orchestration, Accessibility |
| 2.3.8 | Code generation pipeline, CLI CODE subcommand, Swarm integration |

---

## Desktop GUI (v2.6.0)

```bash
python src/gui.py
```

### UI Features

- **Toast Notifications**: Non-intrusive auto-dismissing notifications with fade animation
- **Command Palette**: `Ctrl+Shift+P` fuzzy-search all actions with keyboard navigation
- **Welcome Screen**: First-launch feature cards with shortcuts reference
- **Enhanced Status Bar**: Multi-panel with model, mode, file count, voice status, activity pulse
- **Searchable Terminal**: `Ctrl+F` to search and highlight terminal output, timestamped entries
- **Command History**: Up/Down arrow keys to navigate previous commands
- **Tab Management**: Rename tabs on double-click, modified indicators (*)
- **File Tree Icons**: Extension-based colored icons for files
- **Matrix Rain Toggle**: `Ctrl+M` for sci-fi effect
- **Auto-Save**: Automatic save after idle period (configurable)
- **Refresh File Tree**: One-click refresh of project files
- **Cache Size Display**: Real-time cache monitoring in status bar
- **Enhanced Progress Bar**: Gradient animation with smooth transitions
- **Improved Styling**: Rounded corners, hover states, better contrast

### Dockable Panels

- **Project Files**: Hierarchical project navigation with auto-refresh
- **Git Panel**: Full git integration (see Git Integration below)
- **Agent Panel**: Visual status indicators with icons and capabilities
- **Task Queue**: Real-time task tracking with status icons
- **Reasoning Panel**: Live agent thought chains, coherence bar, event stream
- **Tabbed Editor**: Multiple file tabs with close functionality
- **Menu Bar**: FILE/EDIT/VIEW/HELP with full keyboard shortcuts
- **Status Bar**: Live clock, task counter, Ollama status, coherence meter, cursor position
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
│ REASON  │ STATUS: READY | OLLAMA: ON | C:0.95 | Tasks:3│
│ C:0.95  │                                               │
│ 🧠●●●   │                                               │
│ ─────── │                                               │
│ Progress│                                               │
└─────────┴───────────────────────────────────────────────┘
```

### Features

| Feature | Description |
|---------|-------------|
| **Project Files** | Tree view with hierarchical navigation |
| **Agent Panel** | 6 agents with real-time status |
| **Task Queue** | Live task tracking with status icons |
| **Reasoning Panel** | Per-agent thought chains, coherence bar, event stream |
| **Tool Framework** | ReAct-style tool calling with 16 built-in tools |
| **Voice Typing** | Click VOICE to record (faster-whisper) |
| **Code Editor** | Tabbed text editor with syntax highlighting (Python, JSON) |
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
| `Ctrl+N` | New file |
| `Ctrl+O` | Open project |
| `Ctrl+T` | New tab |
| `Ctrl+S` | Save file |
| `Ctrl+Shift+S` | Save as |
| `Ctrl+W` | Close tab |
| `Ctrl+Q` | Quit |
| `Ctrl+Shift+C` | Copy output |
| `Ctrl+L` | Clear terminal |
| `Ctrl+V` | Paste (image or text) |
| `Ctrl+A` | Autonomous production |
| `Ctrl+Enter` | Execute code |
| `Ctrl+Shift+V` | Toggle voice input |
| `Ctrl+Shift+P` | Command palette |
| `Ctrl+F` | Find in terminal |
| `Ctrl+M` | Toggle matrix rain |
| `Ctrl+,` | Settings |
| `F1` | Help |
| `F11` | Toggle fullscreen |
| `F12` | Dev console |
| `Escape` | Stop operation |
| `Up/Down` | Command history |
| `Ctrl+Tab` | Next tab |
| `Ctrl+Shift+Tab` | Previous tab |

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
| Supervisor | Coordinates | Delegate, manage, all |
| Architect | Design | Planning, architecture, blueprint |
| Coder | Implementation | Code, write, modify, create |
| Executor | Execution | Run, execute, test, deploy |
| Reviewer | Analysis | Review, debug, optimize, fix |
| Searcher | Discovery | Search, find, grep, analyze |
| Tester | Quality Assurance | Test, validate, verify |
| Debugger | Bug Fixing | Debug, trace, patch |
| Documenter | Documentation | Document, explain, annotate |

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

## Autonomous Application Production (v2.6.0)

OpenClaw-style autonomous agent that takes a high-level specification and autonomously designs, codes, tests, and delivers complete applications.

### Production Pipeline

```
Specification → Analysis → Architecture → Scaffold → Code → Tests → Self-Correction → Delivery
```

| Phase | Description |
|-------|-------------|
| **1. Analyze** | Extract requirements, identify features and constraints |
| **2. Architect** | Design system architecture with component diagrams |
| **3. Scaffold** | Create project file structure from templates |
| **4. Code** | Generate production-ready code for all files |
| **5. Test** | Run tests and validate functionality |
| **6. Correct** | Self-correct test failures autonomously (up to 3 iterations) |
| **7. Deliver** | Generate documentation and finalize project |

### Usage

```python
from src.engine import CrackedCodeEngine

engine = CrackedCodeEngine()

# Autonomous production
result = engine.autonomous_produce(
    spec="Build a todo list app with web API and SQLite storage",
    project_name="todo_app",
    architecture="clean",
    output_dir="./projects/todo_app"
)

print(f"Files: {result.files_created}")
print(f"Tests: {result.tests_passed} passed, {result.tests_failed} failed")
print(f"Duration: {result.duration:.1f}s")
```

### Architecture Templates

| Pattern | Use Case | Structure |
|---------|----------|-----------|
| **MVC** | GUI applications | Models, Views, Controllers |
| **Clean** | Enterprise apps | Domain, Adapters, Infrastructure (Hexagonal) |
| **Layered** | Traditional apps | Presentation, Service, Repository, Domain |
| **CLI** | Command-line tools | Commands, Core, Utils |
| **Web API** | RESTful services | API, Controllers, Models, Services |
| **Desktop GUI** | PyQt6 applications | UI, Models, Controllers, Resources |
| **Microservices** | Distributed systems | Gateway, Services, Shared |

### Persistent Workspace

The autonomous agent maintains persistent memory across sessions (OpenClaw style):

```
.autonomous/
├── IDENTITY.md          # Agent identity and capabilities
├── MEMORY.md            # Cross-session memory and lessons learned
├── PROJECT.md           # Current project context
├── TASKS.md             # Task queue and history
├── STANDING_INSTRUCTIONS.md  # Code standards and preferences
├── REASONING.md         # Chain-of-thought archive and coherence history
├── REQUIREMENTS.md      # Analyzed requirements
└── ARCHITECTURE.md      # Architecture design decisions
```

### Skill System

Composable skills that the autonomous agent can use:

| Skill | Description | Tools |
|-------|-------------|-------|
| **code-generator** | Production-ready code generation | write_file, read_file, execute_shell |
| **architect** | System architecture design | write_file, read_file |
| **tester** | Comprehensive test creation | write_file, execute_shell, read_file |
| **debugger** | Autonomous bug fixing | read_file, write_file, execute_shell |
| **documenter** | Documentation generation | write_file, read_file |
| **refactorer** | Code quality improvement | read_file, write_file, execute_shell |

### GUI Usage

1. Click **AUTONOMOUS** button in toolbar or press **Ctrl+A**
2. Enter specification in natural language
3. Select architecture pattern
4. Click **PRODUCE**
5. Monitor real-time progress

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

## Unified Voice Engine (v2.6.0)

SOTA Speech-to-Text and Text-to-Speech with multi-backend fallback.

```python
from src.voice_engine import UnifiedVoiceEngine, VoiceConfig

engine = UnifiedVoiceEngine(VoiceConfig(
    stt_model_size="base",
    tts_backend="pyttsx3",
    tts_rate=175
))
engine.initialize()

# Listen and transcribe
result = engine.listen(duration=5.0)
print(result.text)

# Speak with automatic backend fallback
engine.speak("Hello from CrackedCode")

# Voice commands with fuzzy matching
cmd = engine.processor.parse("write a function in app.py")
print(cmd.command_type.value)  # "write"
print(cmd.params)  # {"filename": "app.py", "type": "function"}
```

### Backends (Priority Order)

| Backend | Type | Quality | Requires |
|---------|------|---------|----------|
| pyttsx3 | Local | Good | Windows SAPI5 / nsss / espeak |
| edge-tts | Online | Excellent | Internet (free Azure Edge) |
| fallback | Console | Basic | Nothing |

### Voice Commands

| Command | Example | Action |
|---------|---------|--------|
| write | "write a python function" | Write code |
| execute | "run the code" | Execute |
| debug | "fix the bug" | Debug |
| save | "save this file" | Save |
| search | "search for todo" | Search |
| open | "open app.py" | Open file |
| clear | "clear terminal" | Clear |
| stop | "stop everything" | Stop |
| plan | "plan the architecture" | Plan mode |
| build | "build the project" | Build mode |

---

## Git Integration (v2.6.0)

Full Git sidebar panel in the GUI:

- **Branch Status**: Current branch with ahead/behind indicators
- **File Tree**: Color-coded by status (staged/modified/untracked/conflicts)
- **Diff Viewer**: Double-click any file to view syntax-highlighted diff
- **Context Menu**: Right-click to stage/unstage/view diff
- **AI Commit Messages**: Generate commit messages from staged changes
- **Quick Actions**: Pull, Push, Refresh buttons
- **Auto-Refresh**: Updates every 3 seconds

---

## File Watcher + Auto-Save (v2.6.0)

Automatic file monitoring and saving:

- **External Change Detection**: Detects when files change outside the IDE
- **Auto-Save**: Saves editor content after configurable idle period (default 3s)
- **Conflict Detection**: Warns when externally modified files are open
- **Auto-Refresh**: File tree updates when files are created/deleted

---

## Unified Orchestrator (v2.6.0)

Production-grade task orchestration replacing 4 disconnected systems:

```python
from src.orchestrator import UnifiedOrchestrator, TaskPriority

orch = UnifiedOrchestrator(engine=my_engine, max_workers=4)

# Create prioritized task
task = orch.create_task(
    prompt="write a function",
    intent="code",
    priority=TaskPriority.HIGH
)

# Submit for execution
orch.submit(task)

# Check status
status = orch.get_queue_status()
print(f"Queued: {status['queued']}, Running: {status['running']}")
```

### Task Lifecycle

```
PENDING → QUEUED → RUNNING → VERIFYING → COMPLETED
                              ↓
                           FAILED → RETRYING (with backoff)
                              ↓
                           CANCELLED
```

### Features

- **Priority Queue**: LOW, NORMAL, HIGH, CRITICAL
- **Dependency Resolution**: Tasks wait for dependencies to complete
- **Agent Pool**: 9 roles with capability matching
- **Retry Logic**: Configurable with exponential backoff
- **Sub-Task Delegation**: Parent/child relationships
- **Blackboard**: Shared state for agent collaboration
- **Pipeline Builder**: Multi-step dependent workflows
- **Task Cancellation**: Anytime with status tracking
- **Timeouts**: Per-task configurable

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

## Logging

Structured logging with colored console output, rotating file handlers, and optional JSON format.

```python
from src.logger_config import get_logger, setup_logging

# Get a logger with centralized configuration
logger = get_logger("MyModule")
logger.info("Application started")
logger.debug("Debug info: %s", data)

# Custom configuration
setup_logging({
    "log_level": "DEBUG",
    "log_dir": "logs",
    "use_colored_logs": True,
    "use_json_logs": False,
    "console_logging": True,
})
```

### Log Files

| File | Description |
|------|-------------|
| `logs/crackedcode.log` | All log levels with rotation (5MB × 5 files) |
| `logs/crackedcode_errors.log` | Errors only with rotation |

### Features

- **Colored console output**: ANSI color codes per log level
- **Rotating file handlers**: Automatic rotation at 5MB, keeps 5 backups
- **Structured JSON**: Optional JSON format for log aggregation
- **Runtime level changes**: Adjust log level without restart
- **Separate error log**: Errors automatically written to dedicated file

### Configuration

```json
{
  "logging": {
    "log_level": "INFO",
    "log_dir": "logs",
    "max_log_bytes": 5000000,
    "log_backup_count": 5,
    "use_colored_logs": true,
    "use_json_logs": false,
    "console_logging": true
  }
}
```

---

## Settings Dialog (v2.6.0)

GUI preferences editor (`Ctrl+,`):

- **General**: Model selection with Ollama discovery, behavior toggles, context limits
- **Voice**: TTS backend, voice, rate slider, STT model, hotword
- **Appearance**: Theme selection, font size, auto-save, line numbers
- **Autonomous**: Workspace path, max corrections, debate rounds
- **Shortcuts**: Full keyboard shortcut reference

---

## Code Syntax Highlighting (v2.6.0)

Automatic syntax highlighting in the code editor:

### Supported Languages

| Language | Extensions | Highlighted Elements |
|----------|-----------|---------------------|
| **Python** | `.py` | Keywords, builtins, strings, comments, numbers, decorators, function/class definitions, self/cls |
| **JSON** | `.json` | Keys, strings, numbers, booleans, null |

### Color Scheme (Atlantean Theme)

| Element | Color | Style |
|---------|-------|-------|
| Keywords | `#9D00FF` (Purple) | Bold |
| Builtins | `#00FFFF` (Cyan) | Normal |
| Strings | `#00FF41` (Green) | Normal |
| Comments | `#555555` (Gray) | Italic |
| Numbers | `#FFD700` (Gold) | Normal |
| Functions/Classes | `#FF8C00` (Orange) | Bold |
| Decorators | `#0080FF` (Blue) | Normal |
| self/cls | `#FF3333` (Red) | Italic |

### Extending

Add new languages by creating a highlighter class and registering it in `src/gui_syntax.py`:

```python
# Add to HIGHLIGHTERS dict
HIGHLIGHTERS[".js"] = JavaScriptHighlighter
```

---

## Agent Reasoning Engine (v2.6.0)

Full chain-of-thought reasoning for all agent decisions:

### Architecture

```
ReasoningStep -> ThoughtChain -> AgentReasoning -> CoherenceTracker -> ReasoningEngine
```

### Reasoning Types

| Type | Purpose | Example |
|------|---------|---------|
| **Observation** | Record what the agent sees | "User wants to build a web API" |
| **Analysis** | Evaluate options | "Web API needs REST endpoints" |
| **Hypothesis** | Form educated guesses | "FastAPI would be suitable" |
| **Decision** | Make a choice | "Selected WEB_API architecture" |
| **Action** | Execute a step | "Executing task with coder agent" |
| **Reflection** | Review outcomes | "Task completed successfully" |
| **Correction** | Fix errors | "Tests failed, retrying with fixes" |
| **Inference** | Draw conclusions | "Based on keywords, intent is CODE" |

### Confidence Scoring

Every reasoning step includes a confidence score (0.0-1.0):
- **0.0-0.3**: Low confidence - requires verification
- **0.3-0.6**: Medium confidence - proceed with caution
- **0.6-0.8**: High confidence - likely correct
- **0.8-1.0**: Very high confidence - reliable

### Coherence Tracking

Measures how well agents' reasoning aligns:
- **Internal coherence**: Logical flow within a single agent's thought chain
- **Cross-agent coherence**: Agreement between multiple agents
- **Conflict detection**: Identifies when agents disagree strongly
- **Consensus building**: Records points of agreement

### Integration Points

- **Orchestrator**: Agent selection, priority assignment, dependency resolution, retry decisions
- **Engine**: Intent parsing (why each intent was scored), model selection, execution path
- **Autonomous**: Architecture selection, phase transitions, self-correction rationale

### Accessing Reasoning

Tasks include `reasoning_log` and `reasoning_chain_id`:
```python
task = orch.create_task("Write a function", intent="code")
for step in task.reasoning_log:
    print(f"[{step['type']}] {step['content']} (confidence: {step['confidence']})")
```

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
  "max_retries": 2,
  "auto_save": true,
  "auto_save_delay_ms": 3000,
  "voice_enabled": true,
  "tts_backend": "pyttsx3",
  "tts_rate": 175
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

### Test Coverage (72 tests)

- Module imports, Config loading, Engine initialization
- Ollama Bridge, Intent parsing (8 types), Code Executor
- GUI components, Voice engine, File Watcher, Git Integration
- Parallel Executor, Pipeline Processor, Task properties
- Code Generation, Save and Execute, CLI integration
- Autonomous imports, Workspace, Skills, Heartbeat, Production
- Architecture selection, Templates, Tree generation
- Orchestrator imports, Task lifecycle, Retry logic, Blackboard
- Priority queue, Dependencies, Cancellation
- Engine orchestrator integration
- Git panel imports, Widget, Repo detection, Diff viewer
- Settings dialog imports
- File watcher integration
- GUI file watcher methods
- Female TTS voice selection
- Syntax highlighter imports and registration
- Reasoning Engine (singleton, thought chains, coherence)
- Reasoning + Orchestrator integration
- Reasoning + Engine integration
- Reasoning + Autonomous integration
- Reasoning coherence scoring
- GUI Reasoning Panel (live agent thought chains, coherence bar, event stream)
- Reasoning persistence (JSON log + REASONING.md workspace archive)
- LLM meta-reasoning (Ollama-powered coherence analysis)
- Codebase RAG (semantic search with local embeddings, context-aware generation)
- RAG + Engine integration (context injection for CODE/DEBUG/REVIEW intents)
- RAG + Autonomous integration (existing codebase awareness)
- GUI semantic search dialog (Ctrl+Shift+F)

---

## Codebase RAG (v2.6.1)

100% local semantic search over your codebase using Ollama embeddings or TF-IDF fallback:

```python
from src.codebase_rag import get_codebase_indexer

indexer = get_codebase_indexer("./my_project")
indexer.index()  # Index all code files

# Semantic search - finds relevant code even without keyword matches
results = indexer.search("Where is user authentication handled?", top_k=5)
for r in results:
    print(f"{r.chunk.file_path} (score: {r.score:.2f})")
    print(r.reasoning)  # Why this result is relevant

# Get formatted context for LLM prompting
context = indexer.get_context_for_prompt("How do I add a new endpoint?")
```

### Features

- **Semantic Chunking**: Functions, classes, and modules split intelligently by language
- **Local Embeddings**: Uses Ollama `/api/embeddings` (no cloud)
- **TF-IDF Fallback**: Works even without embedding endpoint
- **Multi-language**: Python, JavaScript, Go, Rust, Java, C/C++, and more
- **Confidence Scoring**: Every result includes relevance score and reasoning
- **Context Injection**: Automatically injected into CODE/DEBUG/REVIEW prompts

### GUI Usage

1. Open a project
2. Press `Ctrl+Shift+F` or select **Search Codebase** from command palette
3. Enter natural language query (e.g., "Find database connection logic")
4. View ranked results with file paths, relevance scores, and code snippets

---

## Tool Calling Framework (v2.6.2)

ReAct-style agent action system with 16 built-in tools across 8 categories:

```python
from src.tool_framework import get_tool_registry, ToolPermission

registry = get_tool_registry()

# Execute a tool
result = registry.execute("read_file", path="src/main.py", limit_lines=50)
print(result.observation)  # Human-readable result summary

# Get tool schemas for LLM tool calling
schemas = registry.get_schemas()

# Enable dangerous tools (requires user approval)
registry.set_permission("run_shell", True)
```

### Built-in Tools

| Tool | Category | Permission | Description |
|------|----------|-----------|-------------|
| `read_file` | filesystem | READ | Read file contents |
| `write_file` | filesystem | WRITE | Write content to file |
| `list_directory` | filesystem | READ | List files and directories |
| `grep_files` | filesystem | READ | Search files by pattern |
| `get_signature` | code | READ | Extract function/class signature |
| `run_tests` | shell | EXECUTE | Run pytest tests |
| `run_linter` | shell | EXECUTE | Run ruff linter |
| `run_shell` | shell | DANGEROUS | Execute shell command (filtered) |
| `git_status` | git | READ | Get git status |
| `git_diff` | git | READ | Get git diff |
| `search_codebase` | rag | READ | Semantic codebase search |
| `get_context` | rag | READ | Get LLM context from codebase |
| `log_observation` | reasoning | READ | Log observation to reasoning engine |
| `log_decision` | reasoning | READ | Log decision to reasoning engine |
| `get_tool_stats` | system | READ | Registry statistics |
| `list_tools` | system | READ | List all tools with schemas |

### ReAct Loop

The `ReActLoop` runs the full reasoning → action → observation cycle:

```python
from src.tool_framework import ReActLoop

react = ReActLoop(agent_id="coder", max_iterations=10)
result = react.run(
    task_description="Find all authentication-related code and run tests",
    llm_callback=lambda prompt: engine.ollama.chat(prompt).text,
)
```

### Safety

- **DANGEROUS tools blocked by default** (e.g., `run_shell`)
- **Shell command filtering** blocks rm, del, format, fdisk, mkfs, dd
- **Execution log** tracks all tool calls with timestamps
- **Per-tool permissions** can be toggled at runtime

### Integration

- **Engine**: `process_with_tools()` auto-enabled for debug/review/build/search intents
- **Orchestrator**: AgentWorker uses ReAct loop for complex tasks
- **Autonomous**: Producer uses tools for file ops, testing, git during pipeline

---

## File Structure

```
crackedcode/
├── src/
│   ├── main.py              # CLI application with AgentSwarm
│   ├── gui.py               # PyQt6 Desktop GUI (primary interface)
│   ├── gui_enhancements.py  # UX widgets: Toast, Command Palette, Welcome
│   ├── gui_git_panel.py     # Git sidebar with diff viewer and AI commits
│   ├── gui_settings.py      # Preferences dialog with Ollama discovery
│   ├── gui_syntax.py        # Code syntax highlighting (Python, JSON)
│   ├── reasoning.py         # Agent Reasoning Engine - thought chains, coherence
│   ├── codebase_rag.py      # Semantic search with local embeddings
│   ├── tool_framework.py    # Tool Calling Framework - ReAct, 16 built-in tools
│   ├── engine.py            # CrackedCodeEngine - core logic
│   ├── orchestrator.py      # UnifiedOrchestrator - task lifecycle, priorities
│   ├── autonomous.py        # AutonomousAppProducer - OpenClaw-style agent
│   ├── voice_engine.py      # UnifiedVoiceEngine - STT/TTS/VAD/commands
│   ├── voice_typing.py      # Backward compatibility wrapper
│   ├── atlan_ui.py          # Sci-Fi UI effects (Matrix, Glitch, etc.)
│   ├── parallel_processor.py # ParallelExecutor, PipelineProcessor
│   ├── file_watcher.py      # File system monitoring with auto-save
│   ├── git_integration.py   # Git operations
│   └── logger_config.py     # Centralized logging
├── test_system.py           # Comprehensive E2E test suite (74 tests)
├── config.json              # Configuration file
├── README.md                # User documentation
├── AGENTS.md                # Developer guide
└── WHITE_PAPER.md           # Technical white paper
```

---

## License

MIT

---

**CrackedCode v2.6.2** - Autonomous AI Coding Agent with Agent Reasoning Engine, Codebase RAG, Tool Calling Framework, and SOTA Architecture Production
