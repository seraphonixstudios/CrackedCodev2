# CrackedCode White Paper
## SOTA Local Multi-Agent Coding Swarm with Agent Reasoning Engine

**Version:** 2.6.1  
**Date:** May 2026  
**Author:** CrackedCode Team  
**License:** MIT  

---

## Executive Summary

CrackedCode is a production-grade local AI coding assistant that operates 100% offline using Ollama for large language model inference and local speech recognition/synthesis for voice I/O. Version 2.6.0 introduced the **Agent Reasoning Engine** — a full chain-of-thought reasoning system that makes every agent decision transparent, measurable, and coherent across the swarm. Version 2.6.1 adds **Codebase RAG** — semantic search with local embeddings that gives every agent full awareness of the existing codebase before acting.

This white paper details the architecture, implementation, and capabilities of CrackedCode v2.6.0.

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

### 1.2 Solution

CrackedCode v2.6.0 addresses all这些问题 by:
- Running 100% locally with Ollama
- No network calls after initial model download
- Free to operate once models are cached
- Sub-100ms inference latency with local GPU
- Full data sovereignty
- **Transparent reasoning**: Every agent decision logged with confidence scores
- **Cross-agent coherence**: Real-time measurement of alignment between agents

### 1.3 Target Users

- Enterprise developers requiring privacy
- Security-conscious organizations
- Air-gapped environments
- Developers in low-connectivity areas
- Privacy advocates
- Researchers studying multi-agent coordination

---

## 2. Architecture

### 2.1 System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CrackedCode v2.6.1                                │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────────────────────┐  │
│  │  Voice I/O  │────▶│  Unified    │────▶│   Agent Reasoning Engine    │  │
│  │ (STT/TTS)   │     │  Voice      │     │  ThoughtChain → Coherence   │  │
│  └─────────────┘     │  Engine     │     └─────────────────────────────┘  │
│                      └─────────────┘                    │                  │
│                                                         ▼                  │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────────────────────┐  │
│  │    GUI      │◀────│  CrackedCode│◀────│   UnifiedOrchestrator       │  │
│  │  (PyQt6)    │     │   Engine    │     │  Task Lifecycle + Blackboard│  │
│  └─────────────┘     └─────────────┘     └─────────────────────────────┘  │
│         │                    │                          │                  │
│         │                    ▼                          ▼                  │
│  ┌─────────────┐     ┌─────────────────┐   ┌─────────────────────────────┐│
│  │ Git Panel   │     │  Codebase RAG   │   │   Ollama Bridge             ││
│  │ Diff Viewer │     │  Semantic Search│   │  Cache + Stream + Retry     ││
│  └─────────────┘     └─────────────────┘   └─────────────────────────────┘│
│                            │                                               │
│                            ▼                                               │
│                     ┌─────────────┐                                        │
│                     │  Autonomous │                                        │
│                     │  Producer   │                                        │
│                     └─────────────┘                                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Multi-Agent Swarm

CrackedCode implements a parallel multi-agent swarm with 9 specialized agents coordinated by the UnifiedOrchestrator:

#### 2.2.1 Supervisor Agent
- **Role**: Orchestrator and task planner
- **Function**: Analyze requirements → Create subtask plan → Assign agents → Monitor coherence
- **Output**: Structured task plan with dependencies and reasoning chains
- **Parallel**: No (coordinates all agents)

#### 2.2.2 Architect Agent
- **Role**: System design specialist
- **Function**: Design architecture from 7 SOTA templates, create file structures, API contracts
- **Output**: Architecture documents with component reasoning
- **Parallel**: Yes (with Coder)

#### 2.2.3 Coder Agent
- **Role**: Code generation specialist
- **Function**: Write production-ready code per specifications with type hints and docstrings
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
- **Parallel**: Yes

#### 2.2.7 Tester Agent
- **Role**: Quality assurance specialist
- **Function**: Create and run comprehensive tests
- **Output**: Test results with coverage reasoning
- **Parallel**: Yes (with Debugger)

#### 2.2.8 Debugger Agent
- **Role**: Bug fixing specialist
- **Function**: Trace failures, propose patches, verify fixes
- **Output**: Debug reports with fix reasoning
- **Parallel**: Yes (with Tester)

#### 2.2.9 Documenter Agent
- **Role**: Documentation specialist
- **Function**: Generate docs, comments, README updates
- **Output**: Documentation with clarity reasoning
- **Parallel**: Yes

### 2.3 Agent Reasoning Engine

The crown jewel of v2.6.0 — every agent decision is transparent:

```
ReasoningStep → ThoughtChain → AgentReasoning → CoherenceTracker → ReasoningEngine
```

**Reasoning Types**:
- **Observation**: Record what the agent perceives
- **Analysis**: Evaluate options with evidence
- **Hypothesis**: Form educated guesses
- **Decision**: Make a choice with confidence
- **Action**: Execute a step
- **Reflection**: Review outcomes
- **Correction**: Fix errors with rationale
- **Inference**: Draw conclusions from data

**Confidence Scoring**: Every step includes a score (0.0-1.0)
- 0.0-0.3: Low — requires verification
- 0.3-0.6: Medium — proceed with caution
- 0.6-0.8: High — likely correct
- 0.8-1.0: Very high — reliable

**Coherence Tracking**:
- **Internal coherence**: Logical flow within a single agent
- **Cross-agent coherence**: Agreement between agents (measured 0.0-1.0)
- **Conflict detection**: Identifies when agents disagree strongly
- **Consensus building**: Records points of agreement

**LLM Meta-Reasoning**: The ReasoningEngine can feed coherence reports back to Ollama for deeper analysis, receiving insights about coordination patterns and recommendations.

### 2.4 Blackboard Memory

Shared state for cross-agent coordination:

```python
BLACKBOARD = {
    "PROJECT_CONTEXT": "",    # Current task context
    "FILES": {},              # Tracked file contents
    "PLAN": [],              # Active task plan with reasoning
    "DEBATE_LOG": [],        # Coder-Reviewer debate history
    "CONSENSUS": {},         # Final settled decisions
    "AGENT_MEMORY": {},      # Per-agent context
    "TASK_HISTORY": [],      # Completed task log
    "REASONING_LOG": [],     # Global reasoning events
    "COHERENCE_HISTORY": [], # Cross-agent coherence over time
}
```

### 2.5 Debate Protocol

When Reviewer scores code < 80 or finds security issues:

1. **Round 1**: Reviewer identifies issues with reasoning → Coder responds with counter-reasoning
2. **Round 2**: Reviewer evaluates response coherence → Coder revises with updated confidence
3. **Round 3**: Final consensus → Score finalized with joint reasoning chain

This ensures code quality through adversarial collaboration with full audit trails.

---

## 3. Codebase RAG (v2.6.1)

### 3.1 Architecture

```
CodeChunker → EmbeddingProvider → VectorStore → CodebaseIndexer
```

### 3.2 Semantic Chunking

The `CodeChunker` splits source files into semantic units:
- **Functions**: Individual function/method definitions
- **Classes**: Class definitions with their methods
- **Modules**: File-level sections for config/docs
- **Multi-language**: Python, JavaScript, Go, Rust, Java, C/C++, and 15+ more

### 3.3 Local Embeddings

**Primary**: Ollama `/api/embeddings` endpoint (100% local)
**Fallback**: sklearn TF-IDF vectorization
**Ultimate fallback**: Simple bag-of-words with normalization

### 3.4 Vector Search

Cosine similarity over NumPy arrays:
- No external vector database required
- Scales to thousands of chunks efficiently
- Deduplication by file path
- Confidence scoring per result

### 3.5 Integration Points

- **Engine**: `get_codebase_context()` injects relevant code into LLM prompts
- **Orchestrator**: Searcher agent uses semantic search instead of grep
- **Autonomous**: Producer indexes existing codebase before generating new code
- **GUI**: `Ctrl+Shift+F` semantic search dialog with ranked results
- **Reasoning**: Every search result includes human-readable rationale

### 3.6 Usage

```python
from src.codebase_rag import get_codebase_indexer

indexer = get_codebase_indexer("./my_project")
indexer.index()

# Natural language search
results = indexer.search("Where is authentication handled?", top_k=5)

# LLM context injection
context = indexer.get_context_for_prompt("Add OAuth support")
```

---

## 4. Autonomous Application Production

### 3.1 Production Pipeline

OpenClaw-style 7-phase autonomous pipeline:

```
Specification → Analyze → Architect → Scaffold → Code → Test → Correct → Deliver
```

| Phase | Description | Reasoning Output |
|-------|-------------|------------------|
| **1. Analyze** | Extract requirements, identify features | Requirement decomposition with confidence |
| **2. Architect** | Design system from 7 templates | Template selection rationale + evidence |
| **3. Scaffold** | Create project file structure | File dependency reasoning |
| **4. Code** | Generate production-ready code | Implementation decisions per file |
| **5. Test** | Run tests and validate | Test coverage reasoning |
| **6. Correct** | Self-correct failures (up to 3 iterations) | Failure analysis + fix rationale |
| **7. Deliver** | Generate documentation | Delivery confidence score |

### 3.2 Architecture Templates

| Pattern | Use Case | Files |
|---------|----------|-------|
| **MVC** | GUI applications | 8 |
| **Clean** | Enterprise apps | 12 |
| **Layered** | Traditional apps | 8 |
| **CLI** | Command-line tools | 8 |
| **Web API** | RESTful services | 8 |
| **Desktop GUI** | PyQt6 applications | 9 |
| **Microservices** | Distributed systems | 7 |

### 3.3 Persistent Workspace

```
.autonomous/
├── IDENTITY.md              # Agent identity and capabilities
├── MEMORY.md                # Cross-session memory
├── PROJECT.md               # Current project context
├── TASKS.md                 # Task queue and history
├── STANDING_INSTRUCTIONS.md # Code standards
├── REASONING.md             # Chain-of-thought archive
├── reasoning_log.json       # Machine-readable reasoning backup
├── REQUIREMENTS.md          # Analyzed requirements
└── ARCHITECTURE.md          # Architecture decisions
```

---

## 5. Voice I/O

### 4.1 Speech-to-Text (STT)

**Technology**: faster-whisper with Voice Activity Detection (VAD)
**Models**: base → small → medium (auto-selected by hardware)
**Latency**: ~300ms on GPU, ~1.5s on CPU
**Features**: Energy-based VAD, adaptive noise floor, cuda/cpu auto-detection

```python
from src.voice_engine import UnifiedVoiceEngine, VoiceConfig

engine = UnifiedVoiceEngine(VoiceConfig(stt_model_size="base"))
engine.initialize()

# Listen with VAD-based recording
result = engine.listen(duration=5.0)
print(result.text)  # "write a function to add numbers"
print(result.confidence)  # 0.95
```

### 4.2 Text-to-Speech (TTS)

**Technology**: Multi-backend router with fallback chain
**Backends**: pyttsx3 → edge-tts → console fallback
**Latency**: ~50ms (pyttsx3), ~500ms (edge-tts)
**Features**: Female voice selection, rate control, backend auto-switching

```python
engine = UnifiedVoiceEngine(VoiceConfig(
    tts_backend="pyttsx3",
    tts_gender="female",
    tts_rate=175
))
engine.speak("CrackedCode is ready")
```

### 4.3 Voice Commands

17 command types with fuzzy matching and parameter extraction:

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

## 6. Implementation

### 5.1 Technology Stack

| Component | Technology | Version |
|-----------|------------|---------|
| Runtime | Python | 3.10+ |
| LLM | Ollama | Latest |
| STT | faster-whisper | Latest |
| TTS | pyttsx3 / edge-tts | Latest |
| GUI | PyQt6 | >= 6.6.0 |
| Async | concurrent.futures | Built-in |
| Git | gitpython | Latest |

### 5.2 Key Classes

```python
class CrackedCodeEngine:
    """Main application orchestrator with reasoning integration"""
    def process(self, prompt: str) -> AgentResponse
    def generate_code(self, prompt: str) -> str
    def autonomous_produce(self, spec: str) -> AutonomousResult
    def process_via_orchestrator(self, intent: Intent, prompt: str) -> TaskResult

class UnifiedOrchestrator:
    """Production-grade task orchestration with reasoning"""
    def create_task(self, prompt: str, intent: str, priority: TaskPriority) -> Task
    def submit(self, task: Task) -> str
    def get_queue_status(self) -> Dict[str, int]
    def get_orchestrator() -> UnifiedOrchestrator  # Singleton

class ReasoningEngine:
    """Central reasoning coordinator"""
    def register_agent(self, agent_id: str, role: str) -> AgentReasoning
    def create_reasoning_chain(self, agent_id: str, title: str) -> ThoughtChain
    def get_coherence_report(self) -> Dict[str, Any]
    def analyze_with_llm(self, ollama_bridge) -> Dict[str, Any]
    def save_reasoning_log(self, filepath: str) -> bool
    def load_reasoning_log(self, filepath: str) -> bool

class AutonomousAppProducer:
    """OpenClaw-style autonomous agent"""
    def produce(self, spec: str, project_name: str) -> AutonomousResult
    def get_status(self) -> Dict[str, Any]

class UnifiedVoiceEngine:
    """Voice I/O orchestrator"""
    def listen(self, duration: float) -> STTResult
    def speak(self, text: str) -> TTSResult
    def process_command(self, text: str) -> Optional[VoiceCommand]
```

### 5.3 JSON Structured Output

All agents output valid JSON for reliable parsing:

```json
// Supervisor
{"plan": [{"id": 1, "agent": "architect", "description": "..."}]}

// Architect
{"action": "design_system", "design": {...}, "mermaid": "..."}

// Coder
{"action": "write_file", "path": "src/main.py", "content": "..."}

// Executor
{"action": "run_shell", "command": "pytest", "timeout": 60}

// Reviewer
{"action": "review", "score": 85, "issues": [...]}

// Reasoning Engine
{"agent_id": "coder", "chain_id": "...", "steps": [...], "coherence": 0.96}
```

---

## 7. Security

### 6.1 Command Whitelist

Only predefined commands can execute:

```json
{
  "allowed_shell_commands": [
    "git", "npm", "node", "python", "pip",
    "ruff", "mypy", "pytest", "cargo", "go"
  ]
}
```

### 6.2 Sandbox Limitations

- No network downloads in code execution
- No system-level commands (rm -rf, format, etc.)
- Max file size: 50KB
- Timeout: 120s per task

### 6.3 Audit Trail

All operations logged to `logs/crackedcode.log`:
- Task submission with reasoning chains
- Agent execution with confidence scores
- File operations
- Shell commands
- Results, errors, and coherence metrics
- Reasoning events with full chain-of-thought

---

## 8. Performance

### 7.1 Benchmarks

| Metric | CPU | GPU (CUDA) |
|--------|-----|------------|
| STT latency | 1.5s | 300ms |
| TTS latency (pyttsx3) | 50ms | 50ms |
| LLM inference | 10s/token | 50ms/token |
| Agent parallel | 4 concurrent | 4 concurrent |
| Total task | 30-60s | 10-20s |
| Reasoning overhead | <1ms | <1ms |

### 7.2 Resource Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| RAM | 16GB | 32GB |
| Storage | 20GB | 50GB |
| GPU | None | 8GB VRAM |
| CPU | 4 cores | 8 cores |

### 7.3 Model Recommendations

**LLM**:
- qwen3:8b-gpu (best balance of speed/quality)
- qwen3-coder:32b (best overall, requires more VRAM)
- dolphin-llama3:8b-gpu (creative tasks)
- llava:13b-gpu (vision tasks)

**STT**:
- base (speed)
- small (balanced)
- medium (accuracy)

**TTS**:
- pyttsx3 (offline, fast)
- edge-tts (online, excellent quality)

---

## 9. Usage Scenarios

### 8.1 Voice-First Development

```
User: "architect a new user authentication system"
CrackedCode: "Designing system architecture..."
[🧠 Architect] Starting: architecture selection
[🧠 Architect] Decision: Selected CLEAN architecture (confidence: 0.92)
→ Outputs Mermaid diagram + file structure + reasoning log
```

### 8.2 Code Generation

```
User: "write a REST API for todo list"
CrackedCode: "Implementing API endpoints..."
[🧠 Coder] Starting: code generation
[🧠 Coder] Decision: Using FastAPI with SQLite (confidence: 0.88)
→ Creates full FastAPI code with tests
```

### 8.3 Code Review with Reasoning

```
User: "review the login module"
CrackedCode: Analyzing code...
[🧠 Reviewer] Starting: code review
[🧠 Reviewer] Observation: Found 3 potential issues
[🧠 Reviewer] Decision: Score 85/100 (confidence: 0.79)
→ Scores 85/100, suggests improvements with reasoning
→ Runs debate if score < 80 with full audit trail
```

### 8.4 Autonomous Production

```
User: "Build a todo app with web API and SQLite"
CrackedCode: "Starting autonomous production..."
[🧠 autonomous_producer] Phase: ANALYZE
[🧠 autonomous_producer] Phase: ARCHITECT → web_api (confidence: 0.95)
[🧠 autonomous_producer] Phase: SCAFFOLD → 8 files
[🧠 autonomous_producer] Phase: CODE → 21 files created
[🧠 autonomous_producer] Phase: TEST → 12 passed, 0 failed
[🧠 autonomous_producer] Decision: Production successful (confidence: 0.90)
→ Full project delivered with reasoning archive
```

---

## 10. Comparison

### 9.1 Vs Cloud AI Assistants

| Feature | CrackedCode | GitHub Copilot | Claude |
|---------|-----------|-------------|--------|
| Privacy | 100% Local | Cloud | Cloud |
| Cost | Free | Subscription | Credits |
| Latency | <1s | >1s | >1s |
| Voice | Yes | No | No |
| Offline | Yes | No | No |
| Agents | 9 specialized | 1 | 1 |
| Reasoning | Transparent | Black-box | Black-box |
| Coherence | Measured | N/A | N/A |

### 9.2 Vs Local Solutions

| Feature | CrackedCode | OpenCode | Cody |
|---------|-------------|----------|------|
| Voice I/O | Yes | No | No |
| Multi-agent | 9 agents | Yes | Yes |
| Reasoning Engine | Full chain-of-thought | Limited | None |
| Coherence Tracking | Yes | No | No |
| Autonomous Production | 7-phase pipeline | No | No |
| Local LLM | Ollama | Ollama | Ollama |

---

## 11. Future Work

### 11.1 Planned Features

- [x] Agent Reasoning Engine with coherence tracking
- [x] GUI Reasoning Panel with live event stream
- [x] Persistent reasoning memory
- [x] LLM meta-reasoning
- [x] Codebase RAG with semantic search
- [x] Git Integration Sidebar
- [x] File Watcher + Auto-Save
- [x] Settings Dialog
- [x] Syntax Highlighting
- [ ] Web UI (Electron/Tkinter)
- [ ] More agent types (DevOps, Security)
- [ ] Custom agent definition
- [ ] Plugin system
- [ ] Multi-language support
- [ ] Video I/O for screen analysis

### 11.2 Model Updates

- [x] Qwen3 8B optimization
- [x] faster-whisper integration
- [x] pyttsx3 + edge-tts multi-backend
- [ ] Qwen3-Coder 32B optimization
- [ ] Whisper large-v3 support
- [ ] Local XTTS integration

---

## 12. Conclusion

CrackedCode v2.6.0 demonstrates that SOTA AI coding assistance is achievable 100% locally without cloud dependencies. By combining:

- Multi-agent swarm architecture (9 specialized agents)
- Agent Reasoning Engine with transparent decision-making
- Cross-agent coherence tracking and conflict detection
- Local LLM inference (Ollama)
- Voice I/O (faster-whisper + multi-backend TTS)
- Autonomous application production (7-phase pipeline)
- Debate protocol for quality assurance
- JSON structured output

We achieve privacy-first, cost-free, transparent, high-performance coding assistance that runs on consumer hardware — with every decision auditable and every agent's reasoning visible.

---

## Appendix A: File Structure

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
├── test_system.py           # Comprehensive E2E test suite (72 tests)
├── config.json              # Configuration file
├── README.md                # User documentation
├── AGENTS.md                # Developer guide
└── WHITE_PAPER.md           # This document
```

## Appendix B: Commands Reference

| Command | Agent | Description |
|---------|-------|-------------|
| "architect X" | Architect | Design system with reasoning |
| "write code X" | Coder | Generate code with confidence |
| "run X" | Executor | Execute commands safely |
| "review X" | Reviewer | Critique code with audit trail |
| "debug X" | Debugger | Fix bugs with reasoning |
| "test X" | Tester | Validate with coverage |
| "show blackboard" | System | View shared memory |
| "show history" | System | View tasks with reasoning |
| "show coherence" | System | View cross-agent alignment |

## Appendix C: API Reference

```python
# Initialize
from src.engine import CrackedCodeEngine
engine = CrackedCodeEngine()

# Process with reasoning
result = engine.process("write a function")

# Orchestrate
from src.orchestrator import get_orchestrator
orch = get_orchestrator(engine=engine)
task = orch.create_task("write a function", intent="code")
orch.submit(task)

# Reasoning
from src.reasoning import get_reasoning_engine
re = get_reasoning_engine()
re.register_agent("my_agent", "custom")
report = re.get_coherence_report()
insights = re.analyze_with_llm(engine.ollama)

# Autonomous
result = engine.autonomous_produce(
    spec="Build a todo app",
    project_name="todo_app",
    architecture="web_api"
)

# Voice
from src.voice_engine import get_voice_engine
voice = get_voice_engine()
voice.initialize()
voice.speak("Ready")
result = voice.listen(duration=5.0)
```

---

**Document Version:** 2.6.1  
**Last Updated:** May 2026  
**Author:** CrackedCode Team  
**License:** MIT
