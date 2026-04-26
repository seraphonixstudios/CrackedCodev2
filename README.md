# CrackedCode

Local AI Coding Assistant

<p align="center">
  <img src="https://img.shields.io/badge/Version-2.1.3-blue?style=for-the-badge" alt="Version">
</p>

## Overview

CrackedCode is a local AI coding assistant that runs offline using Ollama.

### Key Features

- **Multi-Agent Swarm**: Supervisor → Architect → Coder → Executor → Reviewer
- **Voice I/O**: Speech-to-Text (faster-whisper) + Text-to-Speech (Piper)
- **100% Local**: No cloud, no API keys, full privacy
- **Tool Use**: File read/write, shell execution, code analysis
- **Debate Protocol**: Coder-Reviewer dynamic resolution
- **Blackboard Memory**: Persistent cross-agent coordination
- **JSON Structured Output**: All agents output valid JSON

### New in v2.1 - Enhanced Interface

- **Agent Thought Visualization**: See each agent's reasoning process
- **Reasoning Chain Display**: Step-by-step thought flow
- **Conversational Context**: Maintains conversation history
- **Colored CLI Output**: Rich terminal UI with colors
- **Debate Visualization**: Real-time debate progress bars
- **Status Indicators**: Visual agent state tracking

## Quick Start

### 1. Install Dependencies

**Linux/macOS:**
```bash
chmod +x install.sh
./install.sh
```

**Windows:**
```cmd
install.bat
```

Or manually:
```bash
pip install ollama faster-whisper sounddevice numpy
ollama pull qwen3-coder:32b
```

### 2. Start Ollama

```bash
ollama serve
```

### 3. Run CrackedCode

```bash
python src/main.py
```

### 4. Voice Commands

| Command | Action |
|---------|--------|
| "architect a system for X" | Design architecture with Mermaid |
| "write code for feature Y" | Generate production code |
| "run tests" | Execute shell commands |
| "review the code" | Critique with debate protocol |
| "show blackboard" | View swarm memory |
| "show history" | View task history |
| "exit" | Quit |

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        Voice Input (STT)                      │
│                   faster-whisper (medium.en)                    │
└──────────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                     Supervisor Agent                         │
│            Task → subtask plan → agent assignment            │
└──────────────────────────────┬──────────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼              ▼              ▼
   ┌──────────┐    ┌──────────┐    ┌──────────┐
   │Architect│    │  Coder  │    │Specialist│
   │  UML   │    │ Write  │    │  Niche  │
   └────┬───┘    └────┬───┘    └────┬───┘
        │             │             │
        ▼             ▼             ▼
   ┌──────────┐    ┌──────────┐    ┌──────────┐
   │Executor │    │Reviewer │    │  Any    │
   │ Shell   │    │ Debate │    │  Tool   │
   └────┬───┘    └────┬───┘    └────┬───┘
        │             │             │
        └─────┬─────┴──────┬─────┘
              │            │
              ▼            ▼
       ┌──────────────┐  ┌──────────────┐
       │Blackboard  │  │ Consensus │
       │  Memory   │  │  Score   │
       └─────┬─────┘  └──────────┘
             │
             ▼
       ┌──────────────┐
       │ Voice Out  │
       │   (TTS)  │
       └──────────┘
```

## Agent Definitions

### Supervisor
Breaks complex tasks into subtask plans assigned to specialized agents.

**Output:**
```json
{
  "plan": [
    {"id": 1, "agent": "architect", "description": "Design system architecture"},
    {"id": 2, "agent": "coder", "description": "Implement core modules"},
    {"id": 3, "agent": "executor", "description": "Run tests"}
  ]
}
```

### Architect
Creates Mermaid diagrams, file structures, component designs.

**Output:**
```json
{
  "action": "design_system",
  "design": {"overview": "...", "components": [...]},
  "mermaid": "graph TD; A-->B;",
  "files": [{"path": "src/main.py", "description": "entry point"}]
}
```

### Coder
Writes production-ready code with 2026 best practices.

**Output:**
```json
{
  "action": "write_file",
  "path": "src/main.py",
  "content": "print('Hello World')",
  "language": "python"
}
```

### Executor
Runs safe shell commands with error handling.

**Output:**
{
  "action": "run_shell",
  "command": "pytest tests/",
  "timeout": 60
}

### Reviewer
Critiques code for bugs, security, performance. Runs debate protocol.

**Output:**
```json
{
  "action": "review",
  "score": 85,
  "issues": [{"severity": "low", "description": "..."}],
  "debate_required": false
}
```

## Configuration

Edit `config.json`:

```json
{
  "model": "qwen3-coder:32b",
  "whisper_size": "medium.en",
  "tts_voice": "en_US-lessac-medium",
  "voice_enabled": true,
  "push_to_talk": false,
  "max_concurrent_agents": 4,
  "debate_rounds": 3,
  "allowed_shell_commands": ["git", "npm", "python", "pytest"]
}
```

## Models

### Recommended Ollama Models

| Model | Size | Best For |
|-------|------|----------|
| qwen3-coder:32b | 32B | Best overall coding |
| deepseek-coder-v2:16b | 16B | Complex logic |
| llama3.3:70b-instruct | 70B | General purpose |
| codellama:34b-instruct | 34B | Code-specialized |

### Voice Models

| STT | Size | Speed |
|-----|------|-------|
| tiny | 39M | Fastest |
| base | 74M | Fast |
| small | 244M | Medium |
| medium | 769M | Slow |

| TTS | Quality |
|-----|--------|
| en_US-lessac-medium | High |
| en_US-lessac-large | Highest |

## Command Line Options

```bash
python src/main.py --help

Options:
  -c, --config       Path to config JSON
  --model          Ollama model to use
  --no-voice       Disable voice features
  --push-to-talk   Enable push-to-talk mode
```

## Troubleshooting

### No audio input
```bash
# List devices
python -c "import sounddevice; sounddevice.query_devices()"
```

### Ollama not found
```bash
export OLLAMA_HOST=http://localhost:11434
```

### Model too slow
Reduce context in config.json:
```json
"num_ctx": 4096
```

### Voice not working
Install dependencies:
```bash
pip install faster-whisper sounddevice
```

Install Piper TTS:
```bash
# Linux
wget https://github.com/rhasspy/piper/releases/download/2024.08.01/piper-linux-amd64.tar.gz
tar -xzf piper-linux-amd64.tar.gz
# Download voice model to ~/.local/share/piper-voices/
```

## File Structure

```
crackedcode/
├── src/
│   ├── main.py      # Main application (Agent Swarm)
│   └── voice.py     # Voice Engine (STT/TTS)
├── config.json     # Default configuration
├── install.sh    # Linux/macOS installer
├── install.bat   # Windows installer
├── README.md    # This file
└── LICENSE     # MIT License
```

## Security

- Arbitrary code execution is blocked
- Shell commands are whitelisted
- File operations are sandboxed
- Max file size: 50KB
- No network calls (fully offline)

## Performance

- Max concurrent agents: 4
- Task timeout: 120s
- Parallel task execution
- GPU acceleration where available

## License

MIT License - See LICENSE file.

## Credits

- **Ollama**: Local LLM inference
- **faster-whisper**: Speech recognition
- **Piper TTS**: Speech synthesis
- **OpenCode**: Inspiration for agent architecture

## Links

- [Ollama](https://ollama.ai)
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
- [Piper TTS](https://github.com/rhasspy/piper)
- [OpenCode](https://github.com/anomalyco/opencode)

---

<p align="center">
  <strong>CrackedCode</strong> - The Final Boss of Local AI Coding Agents
</p>