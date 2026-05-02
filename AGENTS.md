# CrackedCode Agent Guide

## Project Overview

CrackedCode is a 100% local AI coding assistant featuring autonomous application production (OpenClaw-style), multi-agent orchestration, voice I/O, and a sci-fi neural interface.

**Current Version:** 2.6.0
**Branch:** feat/voice-typing-2.3.8
**License:** MIT

## Architecture

```
crackedcode/
├── src/
│   ├── main.py              # CLI application with AgentSwarm
│   ├── gui.py               # PyQt6 Desktop GUI (primary interface)
│   ├── engine.py            # CrackedCodeEngine - core logic
│   ├── autonomous.py        # AutonomousAppProducer - OpenClaw-style agent
│   ├── atlan_ui.py          # Sci-Fi UI effects (Matrix, Glitch, etc.)
│   ├── voice_typing.py      # Voice input/output (faster-whisper, TTS)
│   ├── parallel_processor.py # ParallelExecutor, PipelineProcessor
│   ├── file_watcher.py      # File system monitoring
│   └── git_integration.py   # Git operations
├── test_system.py           # Comprehensive E2E test suite
├── config.json              # Configuration file
└── README.md                # User documentation
```

## Key Components

### CrackedCodeEngine (src/engine.py)
- Intent parsing with robust multi-layer keyword matching
- OllamaBridge for LLM communication with caching, streaming, retries
- CodeExecutor for safe shell command execution
- SessionManager for conversation history
- Autonomous production integration

### AutonomousAppProducer (src/autonomous.py)
- 7-phase pipeline: Analyze → Architect → Scaffold → Code → Test → Correct → Deliver
- 7 architecture templates: MVC, Clean, Layered, CLI, Web API, Desktop GUI, Microservices
- Persistent workspace (IDENTITY.md, MEMORY.md, PROJECT.md, TASKS.md)
- SkillRegistry with 6 composable skills
- HeartbeatScheduler for background tasks

### GUI (src/gui.py)
- PyQt6-based with Atlantean theme (#00FF41 on black)
- Tabbed editor, searchable terminal, task queue, agent panel
- Toast notifications, pulse indicators, command history
- Autonomous production dialog (Ctrl+A)

## Development Workflow

1. Make changes to source files
2. Update version numbers in ALL relevant files if version changes
3. Update test_system.py with new tests
4. Update README.md and AGENTS.md
5. Run `python test_system.py` to verify
6. Commit with descriptive message
7. Push to origin

## Testing

```bash
# Full E2E test suite
python test_system.py

# Autonomous tests only
python -c "from test_system import test_autonomous_imports, test_autonomous_workspace, test_autonomous_skills, test_autonomous_heartbeat; [fn() for fn in [test_autonomous_imports, test_autonomous_workspace, test_autonomous_skills, test_autonomous_heartbeat]]"

# Intent parsing tests
python -c "from test_system import test_intent_parsing; test_intent_parsing()"
```

## Configuration

Key settings in `config.json`:
- `model`: "qwen3:8b-gpu" (primary)
- `vision_model`: "llava:13b-gpu"
- `secondary_model`: "dolphin-llama3:8b-gpu"
- `unified_mode`: false
- `autonomous_enabled`: true
- `streaming_enabled`: true
- `cache_enabled`: true

## Code Style

- Type hints everywhere
- Docstrings for all public functions/classes
- PEP 8 conventions
- Explicit error handling
- Modular, testable code
- No placeholders or TODO comments in production code

## Common Tasks

### Adding a New Architecture Template
1. Add pattern to `ArchitecturePattern` enum in `src/autonomous.py`
2. Add template to `ARCHITECTURE_TEMPLATES` dict
3. Include `description`, `structure`, and `file_contents`
4. Add test in `test_system.py`
5. Update README.md

### Adding a New Skill
1. Create `Skill` dataclass instance in `SkillRegistry._register_builtin_skills()`
2. Define `name`, `description`, `system_prompt`, `tools`
3. Add test in `test_system.py`

### Modifying the GUI
1. Update styles in `setup_styles()` method
2. Add widgets in `init_ui()`
3. Connect signals in relevant methods
4. Test with `python src/gui.py`

## Known Issues

- Git push sometimes times out (requires retries)
- Version consistency check: ensure all files are updated together
- Windows path separators may need special handling in tests

## Models

| Model | Role | Best For |
|-------|------|----------|
| qwen3:8b-gpu | General/Code | Reasoning, coding, planning |
| dolphin-llama3:8b-gpu | Creative | Conversation, writing |
| llava:13b-gpu | Vision | Image analysis, OCR |

## Dependencies

- PyQt6 >= 6.6.0
- ollama (Python client)
- faster-whisper (for voice)
- pyperclip, psutil, gitpython
- httpx, requests

## Environment

- Python 3.10+
- Ollama running locally on port 11434
- CUDA for GPU acceleration (optional but recommended)
- Windows / macOS / Linux
