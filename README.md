# CrackedCode: Atlantean Neural System

Local AI Coding Assistant with Sci-Fi Neural Interface

<p align="center">
  <img src="https://img.shields.io/badge/Version-2.1.7-blue?style=for-the-badge" alt="Version">
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/badge/Platform-Linux%20%7C%20macOS%20%7C%20Windows-orange?style=for-the-badge" alt="Platform">
  <img src="https://img.shields.io/badge/Python-3.10%2B-yellow?style=for-the-badge" alt="Python">
  <img src="https://img.shields.io/badge/AI-Local%20Ollama-red?style=for-the-badge" alt="AI">
</p>

## Overview

CrackedCode is a 100% local AI coding assistant running offline with Ollama. Features the Atlantean Neural Interface - a sci-fi themed terminal UI with Matrix-style effects, neural pulse animations, and holographic displays.

### Key Features

- **Multi-Agent Swarm**: Supervisor → Architect → Coder → Executor → Reviewer
- **Voice I/O**: Speech-to-Text (faster-whisper) + Text-to-Speech (Piper)
- **100% Local**: No cloud, no API keys, full privacy
- **Vision System**: Image analysis, OCR, vision model integration
- **Natural Prompts**: Intent detection, entity tracking
- **Full Logging**: Debug mode, error tracking, session logs
- **Atlantean UI**: Sci-fi neural interface with effects

### Version History

| Version | Features |
|---------|----------|
| 2.1.7 | Atlantean Sci-Fi Neural Interface |
| 2.1.6 | Natural conversational prompts |
| 2.1.5 | Vision/image and text prompt systems |
| 2.1.4 | Full logging and debugging |
| 2.1.3 | Enhanced interface |

## Quick Start

### Install Dependencies

```bash
pip install ollama faster-whisper sounddevice numpy colorama pillow
```

### Start Ollama

```bash
ollama serve
```

### Run CrackedCode

```bash
python src/main.py
```

### Run Atlantean UI Demo

```bash
python src/atlan_ui.py
```

## Atlantean Neural Interface

The Atlantean UI provides a sci-fi themed interface with Matrix/neural effects:

```python
from src.atlan_ui import atlan_ui

# Print system banner
atlan_ui.print_system_info()

# Loading sequence with animation
atlan_ui.loading_sequence("INITIALIZING NEURAL LINK")

# Data stream effect
atlan_ui.print_data_stream("SYSTEM ONLINE", "hex", 1.0)

# Custom prompt
prompt = atlan_ui.prompt()  # Returns: "◈> "
atlan_ui.response("Neural system ready")
```

### UI Components

```python
from src.atlan_ui import *

# Glitch text effect
GlitchEffect.glitch_text("SYSTEM")

# Neural pulse progress
NeuralPulse.progress_bar(7, 10)

# Hex grid display
HexGrid.hex_pattern(20, 5)

# Circuit board
CircuitBoard.draw_connection("cpu", "memory")

# Hologram box
HologramBorder.box("Content", "rounded")

# Scanner
ScannerLine.scan("SYSTEM CHECK", 3)

# Status display
StatusDisplay.status("NEURAL CORE", "online")
```

### Theme Colors

```python
from src.atlan_ui import AtlanteanTheme

theme = AtlanteanTheme()
theme.PRIMARY    # Cyan
theme.SECONDARY  # Green  
theme.ACCENT   # Magenta
theme.DATA     # Blue
theme.WARNING  # Yellow
theme.ERROR   # Red
```

### Matrix Effects

```python
from src.atlan_ui import MatrixRain, DataStream, GlitchEffect

# Matrix rain animation
rain = MatrixRain(width=40, height=20)
rain.start(duration=3.0)

# Binary data stream
stream = DataStream(charset="binary", width=60)
stream.run(duration=2.0)

# Corrupted/glitched text
GlitchEffect.corrupt("data...", 0.1)
```

## Natural Prompt Engine

Process natural language with intent detection:

```python
from src.main import NaturalTextPromptEngine, Intent, PromptStyle

engine = NaturalTextPromptEngine()

# Process user input
result = engine.process("fix the bug in auth.py")

# result = {
#   'intent': 'debug',
#   'entities': ['auth.py'],
#   'system_prompt': '...',
#   'context': '...'
# }

# Set response style
engine.set_style(PromptStyle.TECHNICAL)

# Get conversation stats
stats = engine.get_stats()
```

## Vision System

```python
from src.main import VisionEngine

vision = VisionEngine(model="llama3.2-vision:11b")

# Analyze image
analysis = vision.analyze_image("screenshot.png")

# Describe image with vision model
description = vision.describe_image("screenshot.png", "What's in this UI?")

# OCR text extraction
text = vision.extract_text("screenshot.png")

# Compare images
similarity = vision.compare_images("before.png", "after.png")
```

## Logging and Debug

```bash
# Enable debug mode
export CRACKEDCODE_DEBUG=true

# Enable verbose output
export CRACKEDCODE_VERBOSE=true
```

Logs are written to `logs/` directory with timestamps and full tracebacks.

## Commands

| Command | Action |
|---------|--------|
| "architect X" | Design system architecture |
| "write code X" | Generate production code |
| "run X" | Execute shell commands |
| "review X" | Critique code |
| "show blackboard" | View swarm memory |
| "show history" | View task history |
| "exit" | Quit |

## Environment Variables

| Variable | Values | Description |
|---------|--------| -----------|
| CRACKEDCODE_DEBUG | true/false | Enable debug logging |
| CRACKEDCODE_VERBOSE | true/false | Verbose output |
| OLLAMA_MODEL | model name | Ollama model |
| OLLAMA_HOST | URL | Ollama host |

## File Structure

```
crackedcode/
├── src/
│   ├── main.py        # Main application
│   ├── atlan_ui.py   # Atlantean UI
│   └── voice.py      # Voice engine
├── config.json      # Configuration
├── install.sh     # Linux installer
├── install.bat    # Windows installer
├── logs/         # Log files
└── README.md    # This file
```

## Models

### Ollama Models

- `qwen3-coder:32b` - Best overall coding
- `deepseek-coder-v2:16b` - Complex logic
- `llama3.2-vision:11b` - Vision support

### Voice Models

- **STT**: medium.en (faster-whisper)
- **TTS**: en_US-lessac-medium (Piper)

## License

MIT

---

**CrackedCode: Atlantean Neural System** - The Final Boss of Local AI Coding Agents