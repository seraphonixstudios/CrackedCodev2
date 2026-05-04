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
│   ├── gui_enhancements.py  # UX widgets: Toast, Command Palette, Welcome
│   ├── gui_git_panel.py     # Git sidebar with diff viewer and AI commits
│   ├── gui_settings.py      # Preferences dialog with Ollama discovery
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
├── test_system.py           # Comprehensive E2E test suite (62 tests)
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
- Orchestrator integration: process_via_orchestrator(), create_pipeline()

### UnifiedOrchestrator (src/orchestrator.py)
- Task lifecycle: PENDING → QUEUED → RUNNING → VERIFYING → COMPLETED/FAILED/RETRYING
- Priority queue with dependency resolution (LOW, NORMAL, HIGH, CRITICAL)
- Agent capability matching and load balancing (9 agent roles)
- Task timeout, retry with exponential backoff
- Sub-task delegation (parent/child relationships)
- Blackboard shared state for agent collaboration
- Pipeline workflows for multi-step dependent tasks
- Real-time status callbacks
- Singleton pattern with get_orchestrator()

### AutonomousAppProducer (src/autonomous.py)
- 7-phase pipeline: Analyze → Architect → Scaffold → Code → Test → Correct → Deliver
- 7 architecture templates: MVC, Clean, Layered, CLI, Web API, Desktop GUI, Microservices
- Persistent workspace (IDENTITY.md, MEMORY.md, PROJECT.md, TASKS.md, STANDING_INSTRUCTIONS.md)
- SkillRegistry with 6 composable skills
- HeartbeatScheduler for background tasks

### UnifiedVoiceEngine (src/voice_engine.py)
- STTEngine: faster-whisper with VAD-based recording, cuda/cpu auto-detection
- TTSEngine: Multi-backend router (pyttsx3 → edge-tts → fallback)
- VoiceActivityDetector: Energy-based VAD with adaptive noise floor
- VoiceCommandProcessor: 17 command types with fuzzy matching and parameter extraction
- VoiceSession: Complete listen → process → respond cycle
- UnifiedVoiceEngine: Singleton orchestrator with hotword detection

### GUI (src/gui.py)
- PyQt6-based with Atlantean theme (#00FF41 on black)
- Tabbed editor, searchable terminal, task queue, agent panel
- Git panel with diff viewer and AI commit messages
- Toast notifications, command palette (Ctrl+Shift+P), welcome screen
- Enhanced status bar with activity pulse and model/mode display
- Autonomous production dialog (Ctrl+A)
- File watcher with auto-save and external change detection

### Logger (src/logger_config.py)
- Centralized logging with `get_logger(name)`
- Colored console output (ANSI codes per level)
- RotatingFileHandler (5MB × 5 backups)
- Separate error log file
- Optional JSON structured logging
- Runtime log level changes

## Development Workflow

1. Make changes to source files
2. Update version numbers in ALL relevant files if version changes
3. Update test_system.py with new tests
4. Update README.md and AGENTS.md
5. Run `python test_system.py` to verify (62 tests, all must pass)
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

### Adding a New Voice Command
1. Add keywords to `VoiceCommandProcessor.COMMAND_MAP` in `src/voice_engine.py`
2. Add parameter extraction logic in `_extract_params()` if needed
3. Register handler in `CrackedCodeGUI._register_voice_command_handlers()`
4. Add test in `test_system.py`

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

## Known Issues

- Git push sometimes times out (requires retries)
- Version consistency check: ensure all files are updated together
- Windows path separators may need special handling in tests
- PyQt6 `QStatusBar.addSeparator()` doesn't exist (removed in v2.6.0)
- `QLocalSocket` stale sockets need `removeServer()` before listen

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
