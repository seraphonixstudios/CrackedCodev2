# CrackedCode Agent Guide

## Project Overview

CrackedCode is a 100% local AI coding assistant featuring autonomous application production (OpenClaw-style), multi-agent orchestration, voice I/O, screen capture/vision analysis, web browser automation, security auditing, persistent long-term memory, MCP integration, A2A protocol support, and a sci-fi neural interface.

**Current Version:** 2.8.1
**Branch:** main
**License:** MIT
**Tests:** 86/86 passing

## Architecture

```
crackedcode/
├── src/
│   ├── main.py              # CLI application with AgentSwarm
│   ├── gui.py               # PyQt6 Desktop GUI (primary interface)
│   ├── gui_enhancements.py  # UX widgets: Toast, Command Palette, Welcome
│   ├── gui_git_panel.py     # Git sidebar with diff viewer and AI commits
│   ├── gui_settings.py      # Preferences dialog with Ollama discovery
│   ├── gui_syntax.py        # Code syntax highlighting (Python, JSON)
│   ├── engine.py            # CrackedCodeEngine - core logic
│   ├── orchestrator.py      # UnifiedOrchestrator - task lifecycle, 11 agents
│   ├── autonomous.py        # AutonomousAppProducer - OpenClaw-style agent
│   ├── reasoning.py         # Agent Reasoning Engine - thought chains, coherence
│   ├── codebase_rag.py      # Semantic search with local embeddings
│   ├── tool_framework.py    # Tool Calling Framework - 36+ tools, ReAct loop
│   ├── plugin_system.py     # Plugin System - extensible hooks, hot-reload
│   ├── voice_engine.py      # UnifiedVoiceEngine - STT/TTS/VAD/commands
│   ├── screen_capture.py    # Screenshot capture and vision analysis
│   ├── browser_agent.py     # Web browser automation
│   ├── mcp_client.py        # MCP (Model Context Protocol) client
│   ├── a2a_protocol.py      # Agent-to-Agent protocol
│   ├── long_term_memory.py  # Persistent agent memory
│   ├── parallel_processor.py # ParallelExecutor, PipelineProcessor
│   ├── file_watcher.py      # File system monitoring with auto-save
│   ├── git_integration.py   # Git operations
│   └── logger_config.py     # Centralized logging
├── assets/
│   ├── avatar.png           # Raven mascot (512x512)
│   ├── favicon.png          # Favicon (64x64)
│   └── banner.png           # Logo banner (1024x256)
├── mcp_servers/             # MCP server JSON configs
├── plugins/                 # Plugin Python files
├── test_system.py           # Comprehensive E2E test suite (86 tests)
├── config.json              # Configuration file
├── README.md                # User documentation
└── WHITE_PAPER.md           # Technical white paper
```

## Key Components

### CrackedCodeEngine (src/engine.py)
- Intent parsing with robust multi-layer keyword matching (11 intents)
- Multi-model auto-routing: CODE->qwen3, CHAT->dolphin, VISION->llava
- OllamaBridge for LLM communication with caching, streaming, retries
- CodeExecutor for safe shell command execution
- SessionManager for conversation history
- Autonomous production integration
- Orchestrator integration: process_via_orchestrator(), create_pipeline()
- Long-term memory integration: automatic context injection
- MCP client integration: auto-connect on startup

### UnifiedOrchestrator (src/orchestrator.py)
- Task lifecycle: PENDING -> QUEUED -> RUNNING -> VERIFYING -> COMPLETED/FAILED/RETRYING
- Priority queue with dependency resolution (LOW, NORMAL, HIGH, CRITICAL)
- Agent capability matching and load balancing (11 agent roles)
- Task timeout, retry with exponential backoff
- Sub-task delegation (parent/child relationships)
- Blackboard shared state for agent collaboration
- Pipeline workflows for multi-step dependent tasks
- Real-time status callbacks
- Singleton pattern with get_orchestrator()

### Agent Roles (11 total)

| Role | Capabilities | Intent Mapping |
|------|-------------|----------------|
| SUPERVISOR | plan, coordinate, delegate | help |
| ARCHITECT | design, plan, structure | build |
| CODER | code, write, generate | code, chat |
| EXECUTOR | run, execute, test | execute |
| REVIEWER | review, audit, assess | review |
| SEARCHER | search, find, grep | search |
| TESTER | test, verify, validate | test |
| DEBUGGER | debug, fix, trace | debug |
| DOCUMENTER | document, explain | document |
| DEVOPS | docker, deploy, ci, monitor | deploy, docker, ci |
| SECURITY | scan, audit, check, secure | security, audit, scan |

### AutonomousAppProducer (src/autonomous.py)
- 7-phase pipeline: Analyze -> Architect -> Scaffold -> Code -> Test -> Correct -> Deliver
- 7 architecture templates: MVC, Clean, Layered, CLI, Web API, Desktop GUI, Microservices
- Persistent workspace (IDENTITY.md, MEMORY.md, PROJECT.md, TASKS.md, STANDING_INSTRUCTIONS.md, REASONING.md)
- SkillRegistry with 6 composable skills
- HeartbeatScheduler for background tasks

### UnifiedVoiceEngine (src/voice_engine.py)
- STTEngine: faster-whisper with VAD-based recording, cuda/cpu auto-detection
- TTSEngine: Multi-backend router (pyttsx3 -> edge-tts -> fallback)
- VoiceActivityDetector: Energy-based VAD with adaptive noise floor
- VoiceCommandProcessor: 17 command types with fuzzy matching and parameter extraction
- VoiceSession: Complete listen -> process -> respond cycle
- UnifiedVoiceEngine: Singleton orchestrator with hotword detection

### Agent Reasoning Engine (src/reasoning.py)
- ThoughtChain: Complete reasoning chains from observation to decision
- ReasoningStep: Individual steps with type, confidence, evidence, source
- AgentReasoning: Per-agent reasoning state with memory and coherence
- CoherenceTracker: Cross-agent coherence measurement and conflict detection
- ReasoningEngine: Singleton coordinating all reasoning across the system
- **Persistent memory**: save_reasoning_log() / load_reasoning_log() JSON + REASONING.md
- **LLM meta-reasoning**: analyze_with_llm() feeds coherence report to Ollama for insights

### Codebase RAG (src/codebase_rag.py)
- CodeChunker: Semantic chunking by function/class/module for 15+ languages
- EmbeddingProvider: Ollama embeddings with TF-IDF fallback, 100% local
- VectorStore: NumPy-based cosine similarity search
- CodebaseIndexer: Full project indexing with incremental updates
- SearchResult: Ranked results with relevance scores and reasoning
- **Engine integration**: Automatic context injection for CODE/DEBUG/REVIEW/SECURITY intents
- **Autonomous integration**: Existing codebase awareness before generating new code
- **GUI integration**: Semantic search dialog (Ctrl+Shift+F) with ranked results

### Tool Calling Framework (src/tool_framework.py)
- `@tool` decorator: Auto-register functions with JSON schema from type hints
- ToolRegistry: Central registry with permission levels (READ/WRITE/EXECUTE/DANGEROUS)
- ReActLoop: Full reasoning -> action -> observation cycle with max iterations
- 36+ built-in tools across 8 categories
- Safety: Dangerous tools blocked by default, shell command filtering
- Execution log: All tool calls tracked with timestamps and results
- **Engine integration**: process_with_tools() for debug/review/build/search intents
- **Orchestrator integration**: AgentWorker auto-enables tools for complex tasks
- **Autonomous integration**: Producer uses tools for file ops, testing, git
- **MCP integration**: sync_mcp_tools() auto-imports external MCP tools

### Plugin System (src/plugin_system.py)
- `@plugin` decorator: Auto-register classes/functions as plugins
- PluginRegistry: Central registry with enable/disable, hot-reload
- HookManager: Named hook points across engine/orchestrator/GUI/lifecycle
- 12 hook points: engine.pre/post_process, orchestrator.task_created/completed/failed, gui.menu_ready/command_palette, system.startup/shutdown, tool.pre/post_execute
- Hot-reload: check_hot_reload() detects file changes and reloads plugins
- **Engine integration**: pre/post process, intent parsed hooks
- **Orchestrator integration**: task lifecycle hooks
- **GUI integration**: Plugins menu, reload/manage dialogs, command_palette hook
- **Tool framework integration**: pre/post execute hooks

### DevOps Agent (src/orchestrator.py)
- `AgentRole.DEVOPS`: 10th agent role with docker/deploy/ci/monitor/infra/ssh capabilities
- **Intent mapping**: deploy, docker, monitor, ci, infra -> DEVOPS agent
- **Tools**: docker_build, docker_run, docker_logs, deploy_to_server, monitor_logs, run_ci_pipeline
- **Orchestrator integration**: Auto-created in _init_agents() alongside other 9 agents
- **Safety**: All DevOps tools marked DANGEROUS (blocked by default), except docker_logs and monitor_logs (READ)

### Security Agent (src/orchestrator.py)
- `AgentRole.SECURITY`: 11th agent role with scan/audit/check/secure/vulnerability/pentest capabilities
- **Intent mapping**: security, audit, scan, vulnerability, pentest, secure -> SECURITY agent
- **Tools**: scan_dependencies, audit_secrets, check_permissions, analyze_vulnerabilities
- **Orchestrator integration**: Auto-created in _init_agents() alongside other 10 agents
- **Engine integration**: SECURITY intent triggers security analysis with all 4 tools + LLM report

### Screen Capture / Vision Analysis (src/screen_capture.py)
- ScreenCapture: PIL-based fullscreen and region capture
- VisionAnalyzer: llava:13b-gpu integration for UI description, error detection, OCR
- **Tools**: screen_capture, analyze_screen, detect_screen_errors, ocr_screen
- **Engine integration**: VISION intent auto-captures screen and sends to vision model
- **GUI integration**: View -> Analyze Screen (Ctrl+Shift+S)

### Browser Automation (src/browser_agent.py)
- BrowserAgent: Playwright-based web automation
- Capabilities: navigate, click, fill forms, screenshot, extract text, scroll
- **Tools**: browse_url, click_element, fill_form, screenshot_page, extract_page_text, scroll_page
- **Engine integration**: BROWSE intent extracts URL, navigates, captures content, LLM analyzes

### Persistent Long-Term Memory (src/long_term_memory.py)
- LongTermMemory: Vector store of conversations, decisions, errors, fixes
- Automatic storage on every engine.process() call
- Semantic search via existing RAG EmbeddingProvider/VectorStore
- **Engine integration**: Automatic context injection for all code-related intents
- Storage: .crackedcode/memory/memories.json

### MCP Integration (src/mcp_client.py)
- MCPClient: Connect to external MCP servers via stdio or SSE
- Auto-discovery: tools/list, initialize handshake, tools/call
- **Tool Sync**: MCP tools auto-registered in ToolRegistry as server_name/tool_name
- **Config**: JSON-based server configs in mcp_servers/ directory

### A2A Protocol (src/a2a_protocol.py)
- A2AClient/Server: Google's Agent-to-Agent protocol implementation
- Agent discovery via /.well-known/agent.json
- Task delegation between external agents
- **Registry**: get_a2a_registry() singleton for managing agent connections

### GUI (src/gui.py)
- PyQt6-based with Atlantean theme (#00FF41 on black)
- Tabbed editor with syntax highlighting (Python, JSON), searchable terminal
- Task queue, agent panel, Git panel with diff viewer and AI commit messages
- Toast notifications, command palette (Ctrl+Shift+P), welcome screen
- Enhanced status bar with activity pulse and model/mode display
- Autonomous production dialog (Ctrl+A)
- File watcher with auto-save and external change detection
- **Reasoning Panel** (left sidebar): per-agent thought chains, coherence bar, recent events stream, live terminal integration

### Logger (src/logger_config.py)
- Centralized logging with get_logger(name)
- Colored console output (ANSI codes per level)
- RotatingFileHandler (5MB x 5 backups)
- Separate error log file
- Optional JSON structured logging
- Runtime log level changes

## Development Workflow

1. Make changes to source files
2. Update version numbers in ALL relevant files if version changes
3. Update test_system.py with new tests
4. Update README.md and AGENTS.md
5. Run `python test_system.py` to verify (86 tests, all must pass)
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

# Model routing tests
python -c "from test_system import test_model_routing; test_model_routing()"
```

## Configuration

Key settings in config.json:
- `model`: "qwen3:8b-gpu" (primary)
- `vision_model`: "llava:13b-gpu"
- `secondary_model`: "dolphin-llama3:8b-gpu"
- `unified_mode`: false
- `autonomous_enabled`: true
- `streaming_enabled`: true
- `cache_enabled`: true
- `voice_enabled`: true
- `tts_backend`: "pyttsx3"
- `tts_gender`: "female"

## Code Style

- Type hints everywhere
- Docstrings for all public functions/classes
- PEP 8 conventions
- Explicit error handling
- Modular, testable code
- No placeholders or TODO comments in production code

## Common Tasks

### Adding a New Architecture Template
1. Add pattern to ArchitecturePattern enum in src/autonomous.py
2. Add template to ARCHITECTURE_TEMPLATES dict
3. Include description, structure, and file_contents
4. Add test in test_system.py
5. Update README.md

### Adding a New Skill
1. Create Skill dataclass instance in SkillRegistry._register_builtin_skills()
2. Define name, description, system_prompt, tools
3. Add test in test_system.py

### Modifying the GUI
1. Update styles in setup_styles() method
2. Add widgets in init_ui()
3. Connect signals in relevant methods
4. Test with python src/gui.py

### Adding a New Voice Command
1. Add keywords to VoiceCommandProcessor.COMMAND_MAP in src/voice_engine.py
2. Add parameter extraction logic in _extract_params() if needed
3. Register handler in CrackedCodeGUI._register_voice_command_handlers()
4. Add test in test_system.py

### Adding Syntax Highlighting for a New Language
1. Create a new highlighter class extending QSyntaxHighlighter in src/gui_syntax.py
2. Define _init_formats() for token colors and _init_rules() for regex patterns
3. Implement highlightBlock(self, text) to apply formats
4. Register in HIGHLIGHTERS dict with file extension
5. Add test in test_system.py
6. Update README.md

### Adding Reasoning to a New Component
1. Import reasoning module with graceful fallback: try: from src.reasoning import ... except ImportError: ...
2. Register the component with get_reasoning_engine().register_agent(agent_id, role)
3. Create reasoning chains with engine.create_reasoning_chain(agent_id, title, context, tags)
4. Log steps using agent_reasoning.observe(), .analyze(), .decide(), .reflect(), .correct()
5. Complete chains with engine.complete_reasoning_chain(agent_id, decision, confidence)
6. Add reasoning fields to result dataclasses
7. Add tests in test_system.py

### Adding a New Tool
1. Define the function in src/tool_framework.py (or a new module)
2. Add @tool(description="...", permission=ToolPermission.READ, category=ToolCategory.SYSTEM) decorator
3. Use type hints for all parameters - schema auto-generated from annotations
4. Return Dict[str, Any] with {"success": bool, ...} format
5. Add examples list for few-shot prompting
6. Add test in test_system.py
7. Update README.md tool table

### Adding an MCP Server
1. Create a JSON config in mcp_servers/ directory (e.g., mcp_servers/myserver.json)
2. Set "name", "transport" (stdio or sse), and connection details
3. For stdio: "command" + "args"
4. For SSE: "url"
5. Set "enabled": true to auto-connect on engine startup
6. MCP tools are auto-synced into ToolRegistry as server_name/tool_name
7. Add test in test_system.py
8. Update README.md

### Adding an A2A Agent Connection
1. Create A2AAgentCard with name, capabilities, endpoint
2. Register via get_a2a_registry().register(card)
3. Send tasks via registry.get_client(name).send_task(message)
4. Add test in test_system.py

## Known Issues

- Git push sometimes times out (requires retries)
- Version consistency check: ensure all files are updated together
- Windows path separators may need special handling in tests
- PyQt6 QStatusBar.addSeparator() doesn't exist (removed in v2.8.1)
- QLocalSocket stale sockets need removeServer() before listen

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
- playwright (for browser automation)

## Environment

- Python 3.10+
- Ollama running locally on port 11434
- CUDA for GPU acceleration (optional but recommended)
- Windows / macOS / Linux
