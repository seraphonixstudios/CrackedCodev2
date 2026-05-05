# CrackedCode White Paper
## SOTA Local Multi-Agent Coding Swarm with Agent Reasoning Engine

**Version:** 2.7.1
**Date:** May 2026
**Author:** CrackedCode Team
**License:** MIT

---

## Executive Summary

CrackedCode is a production-grade local AI coding assistant that operates 100% offline using Ollama for large language model inference and local speech recognition/synthesis for voice I/O. Version 2.7.1 represents a major milestone with 11 specialized agent roles, 36+ tools, multi-model auto-routing, security auditing, web browser automation, screen capture/vision analysis, persistent long-term memory, MCP and A2A protocol support, and a comprehensive plugin system.

Key innovations in v2.7.1:
- **Multi-Model Auto-Routing**: Each intent automatically routed to the optimal model (qwen3/dolphin/llava)
- **Security Agent**: Dedicated 11th agent role with vulnerability scanning and secret detection
- **Browser Automation**: Playwright-based web agent for automated testing and research
- **Persistent Long-Term Memory**: Vector store of all agent experiences for context injection
- **A2A Protocol**: Google's Agent-to-Agent protocol for multi-agent communication
- **MCP Integration**: Model Context Protocol for external tool servers
- **Screen Capture / Vision**: AI-powered screen understanding with llava:13b-gpu
- **DevOps Agent**: Docker, deploy, and CI/CD automation

This white paper details the architecture, implementation, and capabilities of CrackedCode v2.7.1.

---

## 1. Introduction

### 1.1 Problem Statement

Current AI coding assistants require cloud API access, raising concerns about:
- **Privacy**: Code uploaded to third-party servers
- **Cost**: API usage fees accumulate rapidly
- **Latency**: Network Round-Trip Times (RTT) impact productivity
- **Connectivity**: Requires constant internet access
- **Transparency**: Black-box decision making with no audit trail
- **Coherence**: Multiple agents working without shared reasoning context
- **Extensibility**: Closed systems that cannot integrate external tools

### 1.2 Solution

CrackedCode v2.7.1 addresses all这些问题 by:
- Running 100% locally with Ollama
- No network calls after initial model download
- Free to operate once models are cached
- Sub-100ms inference latency with local GPU
- Full data sovereignty
- **Transparent reasoning**: Every agent decision logged with confidence scores
- **Cross-agent coherence**: Real-time measurement of alignment between agents
- **Extensible tool framework**: 36+ built-in tools + MCP external servers
- **Multi-model routing**: Optimal model selected per intent automatically

### 1.3 Target Users

- Enterprise developers requiring privacy
- Security-conscious organizations
- Air-gapped environments
- Developers in low-connectivity areas
- Privacy advocates
- Researchers studying multi-agent coordination
- DevOps engineers needing local CI/CD automation

---

## 2. Architecture

### 2.1 System Overview

```
+-----------------------------------------------------------------------------+
|                           CrackedCode v2.7.1                                |
+-----------------------------------------------------------------------------+
|  +-------------+     +-------------+     +-----------------------------+   |
|  |  Voice I/O  |---->|  Unified    |---->|   Agent Reasoning Engine    |   |
|  | (STT/TTS)   |     |  Voice      |     |  ThoughtChain -> Coherence  |   |
|  +-------------+     |  Engine     |     +-----------------------------+   |
|                      +-------------+                    |                  |
|                                                         V                  |
|  +-------------+     +-------------+     +-----------------------------+   |
|  |    GUI      |<----|  CrackedCode|<----|   UnifiedOrchestrator       |   |
|  |  (PyQt6)    |     |   Engine    |     |  Task Lifecycle + Blackboard|   |
|  +-------------+     +-------------+     +-----------------------------+   |
|         |                    |                          |                  |
|         |                    V                          V                  |
|  +-------------+     +-----------------+   +-----------------------------+ |
|  | Git Panel   |     |  Codebase RAG   |   |   Ollama Bridge             | |
|  | Diff Viewer |     |  Semantic Search|   |  Cache + Stream + Retry     | |
|  +-------------+     +-----------------+   +-----------------------------+ |
|                            |                                               |
|                            V                                               |
|                     +-------------------------------+                      |
|                     |  Tool Calling Framework       |                      |
|                     |  @tool -> Registry -> ReAct   |                      |
|                     +-------------------------------+                      |
|                            |                                               |
|                            V                                               |
|                     +-------------------------------+                      |
|                     |  Multi-Model Router           |                      |
|                     |  CODE->qwen3 CHAT->dolphin    |                      |
|                     |  VISION->llava                |                      |
|                     +-------------------------------+                      |
|                            |                                               |
|                            V                                               |
|                     +-------------------------------+                      |
|                     |  Security / Browser / MCP     |                      |
|                     |  Memory / A2A / Vision        |                      |
|                     +-------------------------------+                      |
|                            |                                               |
|                            V                                               |
|                     +-------------+                                        |
|                     |  Autonomous |                                        |
|                     |  Producer   |                                        |
|                     +-------------+                                        |
+-----------------------------------------------------------------------------+
```

### 2.2 Multi-Agent Swarm

CrackedCode implements a parallel multi-agent swarm with 11 specialized agents coordinated by the UnifiedOrchestrator:

#### 2.2.1 Supervisor Agent
- **Role**: Orchestrator and task planner
- **Function**: Analyze requirements, create subtask plan, assign agents, monitor coherence
- **Output**: Structured task plan with dependencies and reasoning chains
- **Parallel**: No (coordinates all agents)

#### 2.2.2 Architect Agent
- **Role**: System design specialist
- **Function**: Design architecture from 7 SOTA templates, create file structures
- **Output**: Architecture documents with component reasoning
- **Parallel**: Yes (with Coder)

#### 2.2.3 Coder Agent
- **Role**: Code generation specialist
- **Function**: Write production-ready code per specifications
- **Output**: Valid code files with reasoning log
- **Parallel**: Yes (with Architect)

#### 2.2.4 Executor Agent
- **Role**: Command execution specialist
- **Function**: Run tests, linters, build commands safely
- **Output**: Execution results with exit codes
- **Parallel**: Yes (with Reviewer)

#### 2.2.5 Reviewer Agent
- **Role**: Code critique specialist
- **Function**: Find bugs, security issues, performance problems
- **Output**: Scored review with issues and correction reasoning
- **Parallel**: Yes (with Executor)

#### 2.2.6 Searcher Agent
- **Role**: Discovery specialist
- **Function**: Search codebase, find patterns, analyze dependencies
- **Output**: Search results with relevance reasoning
- **Parallel**: Yes (with Tester)

#### 2.2.7 Tester Agent
- **Role**: Validation specialist
- **Function**: Write and run tests, measure coverage
- **Output**: Test results with pass/fail reasoning
- **Parallel**: Yes (with Searcher)

#### 2.2.8 Debugger Agent
- **Role**: Problem diagnosis specialist
- **Function**: Trace execution, identify root causes
- **Output**: Debug reports with fix reasoning
- **Parallel**: Yes (with Documenter)

#### 2.2.9 Documenter Agent
- **Role**: Documentation specialist
- **Function**: Generate docs, comments, README files
- **Output**: Documentation with clarity reasoning
- **Parallel**: Yes (with Debugger)

#### 2.2.10 DevOps Agent
- **Role**: Deployment and infrastructure specialist
- **Function**: Docker operations, CI/CD, remote deployment, monitoring
- **Output**: Deployment reports with status
- **Parallel**: Yes

#### 2.2.11 Security Agent
- **Role**: Security auditing specialist
- **Function**: Vulnerability scanning, secret detection, permission auditing
- **Output**: Security reports with severity ratings
- **Parallel**: Yes

### 2.3 Data Flow

```
User Input
    |
    v
Intent Parser (11 intents + multi-layer keyword matching)
    |
    +---> CHAT/CODE/DEBUG/SEARCH/REVIEW/EXECUTE/BUILD/HELP/VISION/SECURITY/BROWSE
    |
    v
Model Router (qwen3 / dolphin / llava)
    |
    v
Context Assembly (codebase RAG + long-term memory + reasoning log)
    |
    v
LLM Inference (OllamaBridge with caching, streaming, retries)
    |
    v
Response Processing (tool calls, reasoning log, memory storage)
    |
    v
Output (GUI terminal / voice / file writes)
```

---

## 3. Codebase RAG (v2.7.1)

### 3.1 Architecture

```
CodebaseRAG
    |
    +---> CodeChunker (semantic chunking by function/class/module)
    +---> EmbeddingProvider (Ollama embeddings + TF-IDF fallback)
    +---> VectorStore (NumPy cosine similarity)
    +---> CodebaseIndexer (full project indexing)
```

### 3.2 Integration Points

- **Engine**: Automatic context injection for CODE/DEBUG/REVIEW/SECURITY/BUILD intents
- **Autonomous**: Existing codebase awareness before generating new code
- **GUI**: Semantic search dialog (Ctrl+Shift+F)

### 3.3 Performance

- Indexing: ~2s per 100 files (with Ollama embeddings)
- Search: <50ms for top-k results
- Memory: ~10MB per 1000 chunks
- Languages: Python, JavaScript, TypeScript, Java, C++, Go, Rust, and 8 more

---

## 4. Tool Calling Framework (v2.7.1)

### 4.1 Architecture

```
@tool decorator
    |
    v
ToolRegistry (singleton)
    |
    +---> Permission levels: READ / WRITE / EXECUTE / DANGEROUS
    +---> Categories: FILESYSTEM / CODE / SHELL / GIT / RAG / REASONING / SYSTEM
    +---> Execution log (timestamp, result, error)
    |
    v
ReActLoop (reasoning -> action -> observation)
    |
    +---> Max iterations: configurable
    +---> JSON response parsing
    +---> Tool result observation building
```

### 4.2 Built-in Tools (36+)

| Category | Count | Examples |
|----------|-------|----------|
| Filesystem | 4 | read_file, write_file, list_directory, grep_files |
| Code | 2 | run_tests, run_linter |
| Shell | 1 | run_shell |
| Git | 2 | git_status, git_diff |
| RAG | 2 | search_codebase, get_context |
| Reasoning | 2 | log_observation, log_decision |
| System | 2 | get_tool_stats, list_tools |
| DevOps | 6 | docker_build, docker_run, deploy_to_server, etc. |
| Security | 4 | scan_dependencies, audit_secrets, etc. |
| Vision | 4 | screen_capture, analyze_screen, etc. |
| Browser | 6 | browse_url, click_element, screenshot_page, etc. |

### 4.3 Safety

- DANGEROUS tools blocked by default
- Shell command filtering (rm, del, format, fdisk, mkfs, dd)
- Per-tool permission toggles at runtime
- Execution log for audit trail

---

## 5. Plugin System (v2.7.1)

### 5.1 Architecture

```
@plugin decorator
    |
    v
PluginRegistry (singleton)
    +---> Enable/disable per plugin
    +---> Hot-reload via file mtime checks
    +---> Error isolation (one failure doesn't break others)
    |
    v
HookManager
    +---> 12 named hook points
    +---> execute_hook() at lifecycle moments
```

### 5.2 Hook Points

| Hook Point | When Fired | Arguments |
|-----------|-----------|-----------|
| engine.pre_process | Before engine.process() | request |
| engine.post_process | After engine.process() | response |
| engine.intent_parsed | After intent detection | request, intent |
| orchestrator.task_created | New task created | task |
| orchestrator.task_completed | Task finished | task, result |
| orchestrator.task_failed | Task failed | task, error |
| gui.menu_ready | GUI menu built | menu |
| gui.command_palette | Command palette shown | actions |
| system.startup | Application starts | - |
| system.shutdown | Application exits | - |
| tool.pre_execute | Before tool call | tool_name, params |
| tool.post_execute | After tool call | tool_name, result |

### 5.3 Example Plugins

- `hello_world.py` — Logs at every system event
- `auto_commit.py` — Auto-commits after autonomous production
- `discord_webhook.py` — Sends task notifications to Discord

---

## 6. DevOps Agent (v2.7.1)

### 6.1 Architecture

```
User: "Deploy the API to production"
  -> Intent: deploy -> AgentRole.DEVOPS
    -> Tool: deploy_to_server(host, path)
      -> SSH/rsync deployment with pre-commands
```

### 6.2 Capabilities

- **docker**: Build, run, and inspect containers
- **deploy**: Remote deployment via SSH/rsync
- **ci**: Trigger GitHub Actions, GitLab CI, or local pipelines
- **monitor**: Watch log files for errors and patterns
- **infra**: Infrastructure operations
- **ssh**: Remote server management

### 6.3 DevOps Tools

| Tool | Permission | Description |
|------|-----------|-------------|
| `docker_build` | DANGEROUS | Build Docker image from Dockerfile |
| `docker_run` | DANGEROUS | Run container with ports/env/volumes |
| `docker_logs` | READ | Get container logs with tail/grep |
| `deploy_to_server` | DANGEROUS | Deploy via rsync over SSH |
| `monitor_logs` | READ | Monitor log files for patterns |
| `run_ci_pipeline` | DANGEROUS | Run local script, GitHub Actions, or GitLab CI |

### 6.4 Safety

- All container and deployment tools are DANGEROUS (blocked by default)
- Log monitoring tools are READ-only (always available)
- SSH deployment requires explicit key path or agent forwarding
- CI pipeline tools require authentication tokens

---

## 7. Security Agent (v2.7.1)

### 7.1 Architecture

```
User: "Audit this code for vulnerabilities"
  -> Intent: security -> AgentRole.SECURITY
    -> Runs 4 security tools simultaneously
    -> LLM generates comprehensive security report
```

### 7.2 Capabilities

- **scan**: Dependency vulnerability scanning (CVE database)
- **audit**: Secret and API key detection in code
- **check**: File permission auditing
- **secure**: Static analysis for SQL injection, XSS, eval usage, etc.

### 7.3 Security Tools

| Tool | Permission | Description |
|------|-----------|-------------|
| `scan_dependencies` | READ | Scan requirements.txt for known CVEs |
| `audit_secrets` | READ | Find hardcoded secrets, API keys, passwords |
| `check_permissions` | READ | Check for overly permissive file modes |
| `analyze_vulnerabilities` | READ | Detect SQL injection, XSS, eval/exec usage |

### 7.4 Integration

- **Orchestrator**: Auto-created as the 11th agent in _init_agents()
- **Intent mapping**: security/audit/scan/vulnerability/pentest/secure -> SECURITY
- **Engine**: SECURITY intent triggers all 4 tools + LLM report generation
- **Reasoning**: Security agent logs all audit decisions with confidence scores

---

## 8. Screen Capture / Vision Analysis (v2.7.1)

### 8.1 Architecture

```
User: "What's on my screen?"
  -> Intent: VISION -> ScreenCapture.grab()
    -> VisionAnalyzer (llava:13b-gpu)
      -> analyze_screen() / describe_ui() / detect_errors() / ocr_screen()
```

### 8.2 Components

- **ScreenCapture**: PIL-based fullscreen and region capture
- **CaptureResult**: Dataclass with image data, dimensions, base64 encoding
- **VisionAnalyzer**: Integrates with llava:13b-gpu via Ollama

### 8.3 Vision Tools

| Tool | Permission | Description |
|------|-----------|-------------|
| `screen_capture` | READ | Capture fullscreen screenshot |
| `analyze_screen` | READ | Capture + analyze with vision model |
| `detect_screen_errors` | READ | Specialized error detection prompt |
| `ocr_screen` | READ | Text extraction from screen |

### 8.4 GUI Integration

- View -> Analyze Screen (Ctrl+Shift+S)
- QuickActions: "Analyze Screen" item
- Terminal output: Screenshot metadata + AI analysis

---

## 9. Browser Automation (v2.7.1)

### 9.1 Architecture

```
User: "Go to https://example.com and tell me what's wrong"
  -> Intent: BROWSE -> BrowserAgent
    -> navigate() -> get_text() -> screenshot()
    -> LLM analyzes content
```

### 9.2 Components

- **BrowserAgent**: Playwright-based web automation
- **BrowserActionResult**: Dataclass for action results

### 9.3 Browser Tools

| Tool | Permission | Description |
|------|-----------|-------------|
| `browse_url` | EXECUTE | Navigate to a URL |
| `click_element` | EXECUTE | Click by CSS selector |
| `fill_form` | EXECUTE | Fill a form field |
| `screenshot_page` | READ | Capture page screenshot |
| `extract_page_text` | READ | Extract page text content |
| `scroll_page` | READ | Scroll the page |

### 9.4 Integration

- BROWSE intent: Extracts URL, navigates, captures content, LLM analyzes
- Pairs with VISION intent for visual verification
- Pairs with MCP fetch server for extended web capabilities

---

## 10. MCP Integration (v2.7.1)

### 10.1 Protocol Overview

CrackedCode implements the Model Context Protocol (MCP), an open standard for connecting AI assistants to external data sources and tools:

```
User: "Search the web for Python best practices"
  -> MCP fetch server -> web search -> results -> LLM context
```

### 10.2 Architecture

- **MCPClient**: Singleton managing connections to multiple MCP servers
- **Transports**: STDIO (subprocess) and SSE (HTTP Server-Sent Events)
- **Tool Sync**: MCP tools automatically registered in ToolRegistry as server_name/tool_name
- **ConfigManager**: JSON-based server configuration in mcp_servers/ directory

### 10.3 Supported Transports

| Transport | Use Case | Requirements |
|-----------|----------|--------------|
| STDIO | Local CLI-based servers | command + args |
| SSE | Remote HTTP servers | url + httpx |

### 10.4 Example Servers

- **filesystem**: Read/write beyond project root
- **fetch**: Web search and HTTP requests
- **sqlite**: Database queries

---

## 11. A2A Protocol (v2.7.1)

### 11.1 Protocol Overview

Google's Agent-to-Agent protocol for multi-agent communication:

```
CrackedCode (Coder) -> A2A -> External Agent (Reviewer)
  <- Results <-
```

### 11.2 Architecture

- **A2AClient**: Discovers agents, sends tasks via HTTP
- **A2AServer**: Hosts own A2A endpoint (/.well-known/agent.json)
- **A2ARegistry**: Singleton for managing agent connections
- **A2ATask**: Task lifecycle with states (SUBMITTED -> WORKING -> COMPLETED/FAILED)

### 11.3 Usage

```python
from src.a2a_protocol import A2AAgentCard, get_a2a_registry

registry = get_a2a_registry()
card = A2AAgentCard(name="reviewer", capabilities=["review"], endpoint="http://localhost:8000")
registry.register(card)

client = registry.get_client("reviewer")
task = client.send_task("Review this code")
```

---

## 12. Persistent Long-Term Memory (v2.7.1)

### 12.1 Architecture

```
Engine.process()
    |
    +---> Success: Store as "conversation" memory
    +---> Error: Store as "error" memory
    |
    v
LongTermMemory
    +---> Vector store (Ollama embeddings)
    +---> JSON persistence (.crackedcode/memory/)
    +---> Semantic search (recall())
    |
    v
Next Request: get_context_for_prompt()
    -> Injects relevant memories into LLM prompt
```

### 12.2 Memory Types

- **conversation**: User/assistant exchanges
- **decision**: Agent decisions with reasoning
- **error**: Failed operations with context
- **fix**: Bug fixes and solutions
- **pattern**: Reusable code patterns
- **insight**: General knowledge

### 12.3 Integration

- **Engine**: Automatic storage on every process() call
- **Context Injection**: Prepends relevant memories to all code-related intents
- **Storage**: .crackedcode/memory/memories.json

---

## 13. Multi-Model Auto-Routing (v2.7.1)

### 13.1 Architecture

```
User Input
    |
    v
Intent Parser (11 intents)
    |
    v
INTENT_TO_MODEL mapping
    |
    +---> CODE/DEBUG/BUILD/SECURITY -> qwen3:8b-gpu
    +---> CHAT/HELP/REVIEW -> dolphin-llama3:8b-gpu
    +---> VISION -> llava:13b-gpu
    +---> BROWSE -> qwen3:8b-gpu
    |
    v
_select_model_for_intent()
    +---> Check availability (Ollama)
    +---> Fallback chain: preferred -> primary -> any -> default
    |
    v
OllamaBridge.chat(model=selected)
```

### 13.2 Model Roles

| Model | Role | Best For |
|-------|------|----------|
| qwen3:8b-gpu | General/Code | Reasoning, coding, planning, security |
| dolphin-llama3:8b-gpu | Creative | Conversation, writing, review |
| llava:13b-gpu | Vision | Image analysis, OCR, screen understanding |

### 13.3 Fallback Chain

1. Preferred model for intent
2. Primary model (qwen3:8b-gpu)
3. Any available model from Ollama
4. Default (may fail but preserves intent)

---

## 14. Autonomous Application Production

### 14.1 Production Pipeline

OpenClaw-style 7-phase autonomous pipeline:

```
Specification -> Analyze -> Architect -> Scaffold -> Code -> Test -> Correct -> Deliver
```

### 14.2 Architecture Templates

| Template | Description | Files |
|----------|-------------|-------|
| MVC | Model-View-Controller | 8 |
| Clean | Clean Architecture | 12 |
| Layered | N-tier | 8 |
| CLI | Command-line tool | 8 |
| Web API | RESTful services | 8 |
| Desktop GUI | PyQt6 application | 9 |
| Microservices | Distributed services | 7 |

### 14.3 Persistent Workspace

- IDENTITY.md: Agent identity and capabilities
- MEMORY.md: Project memory and learnings
- PROJECT.md: Project specification and requirements
- TASKS.md: Task list and progress
- STANDING_INSTRUCTIONS.md: Reusable patterns
- REASONING.md: Reasoning logs and decisions

---

## 15. Voice I/O

### 15.1 Architecture

```
Audio Input -> VAD -> STT (faster-whisper) -> Command Parser
                                                 |
Audio Output <--------------------------- TTS (pyttsx3/edge-tts)
```

### 15.2 Components

- **STTEngine**: faster-whisper with VAD-based recording
- **TTSEngine**: Multi-backend router (pyttsx3 -> edge-tts -> fallback)
- **VoiceActivityDetector**: Energy-based VAD with adaptive noise floor
- **VoiceCommandProcessor**: 17 command types with fuzzy matching

### 15.3 Voice Commands

save, open, run, build, search, clear, help, exit, debug, test, deploy, git, status, settings, voice, matrix, full

---

## 16. Performance

### 16.1 Benchmarks

| Metric | Value |
|--------|-------|
| Intent parsing | <1ms |
| Model routing | <1ms |
| Codebase indexing | ~2s per 100 files |
| Semantic search | <50ms |
| LLM inference (qwen3 8B) | ~15s for 500 tokens |
| Tool execution | <100ms (filesystem), <5s (shell) |
| Voice command latency | <2s (STT) + <1s (TTS) |
| Screen capture + analysis | ~3s |
| Browser navigation | ~2s |

### 16.2 Resource Usage

| Component | Memory | CPU | GPU |
|-----------|--------|-----|-----|
| Ollama (qwen3 8B) | ~6GB | Low | High |
| Ollama (llava 13B) | ~8GB | Low | High |
| faster-whisper | ~2GB | Medium | Optional |
| PyQt6 GUI | ~200MB | Low | None |
| Vector store (1000 chunks) | ~10MB | Low | None |

---

## 17. Security

### 17.1 Local-First Design

- No network calls after model download
- Code never leaves the machine
- All embeddings computed locally
- No API keys or credentials required

### 17.2 Tool Safety

- DANGEROUS tools blocked by default
- Shell command filtering
- Permission levels: READ / WRITE / EXECUTE / DANGEROUS
- Execution log for audit trail

### 17.3 Secret Detection

- audit_secrets tool scans for hardcoded secrets
- Checks for API keys, passwords, tokens, private keys
- Pattern-based detection with masking in output

---

## 18. Future Work

### 18.1 Planned Features

- [x] Agent Reasoning Engine with coherence tracking
- [x] GUI Reasoning Panel with live event stream
- [x] Persistent reasoning memory
- [x] LLM meta-reasoning
- [x] Codebase RAG with semantic search
- [x] Tool Calling Framework with ReAct loop
- [x] Plugin System with hot-reload
- [x] Git Integration Sidebar
- [x] File Watcher + Auto-Save
- [x] Settings Dialog
- [x] Syntax Highlighting
- [x] DevOps agent with Docker, deploy, CI tools
- [x] Screen Capture / Vision Analysis
- [x] MCP Integration
- [x] A2A (Agent-to-Agent) Protocol
- [x] Browser Automation
- [x] Security agent
- [x] Persistent Long-Term Memory
- [x] Multi-Model Auto-Routing
- [ ] Custom agent definition (YAML/JSON)
- [ ] Web UI (Electron/Tkinter)
- [ ] Multi-language support
- [ ] Video I/O for screen analysis
- [ ] Qwen3-Coder 32B optimization
- [ ] Whisper large-v3 support
- [ ] Local XTTS integration

---

## 19. Conclusion

CrackedCode v2.7.1 represents a mature, production-ready local AI coding assistant with:

- **11 specialized agent roles** with coherent reasoning
- **36+ tools** across 8 categories with ReAct loops
- **Multi-model auto-routing** for optimal quality per intent
- **Security auditing** with dedicated agent and 4 tools
- **Web browser automation** for testing and research
- **Screen capture/vision** for UI understanding
- **Persistent memory** that learns from every interaction
- **MCP and A2A protocols** for external integration
- **Plugin system** with 12 hook points and hot-reload
- **86/86 passing tests** ensuring reliability

All running 100% locally with Ollama — no cloud, no API keys, no data leaving the machine.

---

## Appendix A: API Reference

### CrackedCodeEngine

```python
engine = CrackedCodeEngine(config={
    "model": "qwen3:8b-gpu",
    "vision_model": "llava:13b-gpu",
    "secondary_model": "dolphin-llama3:8b-gpu",
    "autonomous_enabled": True,
    "unified_mode": False,
})

# Process a prompt
response = engine.process("Write a Python function to add numbers")

# Get status
status = engine.get_status()

# Autonomous production
result = engine.autonomous_produce("Build a todo app")
```

### UnifiedOrchestrator

```python
from src.orchestrator import get_orchestrator, TaskPriority

orch = get_orchestrator(engine)
task = orch.create_task("Write tests", intent="code", priority=TaskPriority.HIGH)
```

### Tool Registry

```python
from src.tool_framework import get_tool_registry

registry = get_tool_registry()
registry.execute("read_file", path="src/main.py")
```

### Long-Term Memory

```python
from src.long_term_memory import get_long_term_memory

memory = get_long_term_memory()
memory.remember("Fixed bug", memory_type="fix")
results = memory.recall("bug fix")
```

---

## Appendix B: Configuration

### config.json

```json
{
  "model": "qwen3:8b-gpu",
  "vision_model": "llava:13b-gpu",
  "secondary_model": "dolphin-llama3:8b-gpu",
  "temperature": 0.1,
  "max_tokens": 4096,
  "streaming_enabled": true,
  "cache_enabled": true,
  "voice_enabled": true,
  "tts_backend": "pyttsx3",
  "tts_gender": "female",
  "autonomous_enabled": true,
  "unified_mode": false,
  "project_root": "."
}
```

---

## Appendix C: Troubleshooting

### Ollama not detected
- Ensure Ollama is running on port 11434
- Check `ollama list` shows models
- Verify model names match config.json

### GUI won't start
- Install PyQt6: `pip install PyQt6`
- Check for conflicting Qt installations
- Try `python src/gui.py --no-splash`

### Tests failing
- Ensure Ollama is running
- Check all models are downloaded
- Run `python test_system.py -v` for verbose output

### Memory issues
- Reduce `max_tokens` in config
- Clear cache: delete `.crackedcode/cache/`
- Use smaller models for testing

---

<p align="center">
  <strong>CrackedCode v2.7.1</strong> — Neural Coding Interface
  <br>
  <em>100% Local. 100% Powerful. 100% Yours.</em>
</p>
