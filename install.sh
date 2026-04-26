#!/bin/bash
# ============================================================================
# CrackedCode Installation Script
# SOTA Local Multi-Agent Coding Swarm with Voice I/O
#
# Usage: chmod +x install.sh && ./install.sh
# ============================================================================

set -e

echo "╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║                                                                              ║"
echo "║   █████╗  ██████╗  ██████╗ ████████╗    ██████╗  ██╗     ██╗ ██████╗ ██████╗  █████╗ ║"
echo "║  ██╔══██╗██╔═══██╗██╔═══██╗╚══██╔══╝    ██╔══██╗ ██║     ██║██╔════╝ ██╔══██╗██╔══██╗║"
echo "║  ███████║██║   ██║██║   ██║   ██║       ██████╔╝ ██║     ██║██║  ███╗██████╔╝███████║║"
echo "║  ██╔══██║██║   ██║██║   ██║   ██║       ██╔══██╗ ██║     ██║██║   ██║██╔══██╗██╔══██║║"
echo "║  ██║  ██║╚██████╔╝╚██████╔╝   ██║       ██║  ██║ ███████╗██║██║   ██║██║  ██║██║  ██║║"
echo "║  ╚═╝  ╚═╝ ╚═════╝  ╚═════╝    ╚═╝       ╚═╝  ╚═╝ ╚══════╝╚═╝╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝║"
echo "║                                                                              ║"
echo "║                         INSTALLATION SCRIPT                                  ║"
echo "║                   SOTA Local Multi-Agent System                              ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"

# ============================================================================
# CONFIGURATION
# ============================================================================

CRACKEDCODE_DIR="${CRACKEDCODE_DIR:-$HOME/crackedcode}"
OLLAMA_MODEL="${OLLAMA_MODEL:-qwen3-coder:32b}"
WHISPER_MODEL="${WHISPER_MODEL:-medium.en}"
TTS_VOICE="${TTS_VOICE:-en_US-lessac-medium}"

# Detect OS
OS="$(uname -s)"
ARCH="$(uname -m)"

echo ""
echo "📋 Detected: $OS ($ARCH)"
echo "📁 Install directory: $CRACKEDCODE_DIR"
echo ""

# ============================================================================
# PYTHON DEPENDENCIES
# ============================================================================

echo "📦 Installing Python dependencies..."

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install from python.org"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "  Python version: $PYTHON_VERSION"

# Install pip packages
python3 -m pip install --upgrade pip

python3 -m pip install \
    ollama \
    faster-whisper \
    sounddevice \
    numpy \
    colorama \
    logging \
    dataclasses \
    concurrent-futures

echo "  ✅ Python packages installed"

# ============================================================================
# OLLAMA SETUP
# ============================================================================

echo "📦 Setting up Ollama..."

# Install Ollama if not present
if ! command -v ollama &> /dev/null; then
    echo "  Installing Ollama..."

    if [ "$OS" = "Linux" ]; then
        curl -fsSL https://ollama.ai/install.sh | sh
    elif [ "$OS" = "Darwin" ]; then
        brew install ollama
    else
        echo "  ❌ Ollama not supported on this OS"
        echo "  Please install manually from ollama.ai"
    fi
fi

# Add to PATH
export PATH="$HOME/.local/bin:$PATH"

# Pull recommended models
echo "  📥 Pulling Ollama models..."
echo "  Model: $OLLAMA_MODEL"

if command -v ollama &> /dev/null; then
    ollama pull $OLLAMA_MODEL
    ollama pull deepseek-coder-v2:16b
    ollama pull llama3.3:70b-instruct-q4_K_M

    echo "  ✅ Ollama models ready"
else
    echo "  ⚠️  Ollama not available. Run 'ollama serve' after install."
fi

# ============================================================================
# FASTER-WHISPER SETUP
# ============================================================================

echo "📦 Setting up faster-whisper..."

# Models are auto-downloaded on first use
# Download medium.en model explicitly
mkdir -p ~/.cache/whisper

echo "  Whisper model: $WHISPER_MODEL"
echo "  (Auto-downloaded on first use)"

# ============================================================================
# PIPER TTS SETUP
# ============================================================================

echo "📦 Setting up Piper TTS..."

PIPER_DIR="$HOME/.piper"
mkdir -p "$PIPER_DIR"

if [ "$OS" = "Linux" ]; then
    # Download Piper binary
    if [ "$ARCH" = "x86_64" ]; then
        PIPER_URL="https://github.com/rhasspy/piper/releases/download/2024.08.01/piper-linux-amd64.tar.gz"
        PIPER_TMP="/tmp/piper.tar.gz"

        curl -fsSL -o "$PIPER_TMP" "$PIPER_URL"
        tar -xzf "$PIPER_TMP" -C "$PIPER_DIR"
        rm "$PIPER_TMP"

        chmod +x "$PIPER_DIR/piper"
    fi
elif [ "$OS" = "Darwin" ]; then
    brew install piper-tts
fi

# Download voice model
VOICE_URL="https://github.com/rhasspy/piper/releases/download/2024.08.01/${TTS_VOICE}.onnx"
VOICE_JSON_URL="https://github.com/rhasspy/piper/releases/download/2024.08.01/${TTS_VOICE}.onnx.json"

mkdir -p "$HOME/.local/share/piper-voices"

curl -fsSL -o "$HOME/.local/share/piper-voices/${TTS_VOICE}.onnx" "$VOICE_URL"
curl -fsSL -o "$HOME/.local/share/piper-voices/${TTS_VOICE}.onnx.json" "$VOICE_JSON_URL"

echo "  ✅ Piper TTS ready"

# ============================================================================
# AUDIO DEPENDENCIES
# ============================================================================

echo "📦 Setting up audio drivers..."

if [ "$OS" = "Linux" ]; then
    if command -v apt-get &> /dev/null; then
        sudo apt-get update
        sudo apt-get install -y libasound2 portaudio19-dev libsox-fmt-all
    elif command -v yum &> /dev/null; then
        sudo yum install -y alsa-lib portaudio-devel
    fi
elif [ "$OS" = "Darwin" ]; then
    brew install portaudio
fi

echo "  ✅ Audio drivers ready"

# ============================================================================
# CREATE PROJECT
# ============================================================================

echo "📦 Creating project structure..."

mkdir -p "$CRACKEDCODE_DIR/src"
mkdir -p "$CRACKEDCODE_DIR/config"
mkdir -p "$CRACKEDCODE_DIR/logs"

# Copy config
cp config.json "$CRACKEDCODE_DIR/config/default.json"

echo "  ✅ Project structure created"

# ============================================================================
# ENVIRONMENT CONFIGURATION
# ============================================================================

echo "📦 Configuring environment..."

# Create environment file
cat > "$CRACKEDCODE_DIR/.env" << EOF
# CrackedCode Environment Configuration
# Generated: $(date)

# Ollama
export OLLAMA_HOST=http://localhost:11434
export OLLAMA_MODEL=$OLLAMA_MODEL

# Voice
export WHISPER_MODEL=$WHISPER_MODEL
export TTS_VOICE=$TTS_VOICE

# Project
export CRACKEDCODE_DIR=$CRACKEDCODE_DIR
export CRACKEDCODE_CONFIG=$CRACKEDCODE_DIR/config/default.json
EOF

# Add to shell config
if [ -f "$HOME/.bashrc" ]; then
    if ! grep -q "crackedcode" "$HOME/.bashrc"; then
        echo "" >> "$HOME/.bashrc"
        echo "# CrackedCode" >> "$HOME/.bashrc"
        echo "source $CRACKEDCODE_DIR/.env" >> "$HOME/.bashrc"
    fi
fi

if [ -f "$HOME/.zshrc" ]; then
    if ! grep -q "crackedcode" "$HOME/.zshrc"; then
        echo "" >> "$HOME/.zshrc"
        echo "# CrackedCode" >> "$HOME/.zshrc"
        echo "source $CRACKEDCODE_DIR/.env" >> "$HOME/.zshrc"
    fi
fi

echo "  ✅ Environment configured"

# ============================================================================
# VERIFY INSTALLATION
# ============================================================================

echo ""
echo "🧪 Verifying installation..."

ERRORS=0

# Check Python
python3 -c "import ollama" 2>/dev/null || { echo "  ❌ ollama Python SDK not working"; ERRORS=$((ERRORS+1)); }
python3 -c "import faster_whisper" 2>/dev/null || { echo "  ⚠️  faster-whisper not working"; }
python3 -c "import sounddevice" 2>/dev/null || { echo "  ⚠️  sounddevice not working"; }

# Check Ollama
if command -v ollama &> /dev/null; then
    echo "  ✅ Ollama CLI ready"
else
    echo "  ⚠️  Ollama CLI not in PATH"
fi

# Check Piper
if [ -f "$PIPER_DIR/piper" ] || command -v piper &> /dev/null; then
    echo "  ✅ Piper TTS ready"
else
    echo "  ⚠️  Piper TTS not ready"
fi

# ============================================================================
# COMPLETION
# ============================================================================

echo ""
echo "╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║                       ✅ INSTALLATION COMPLETE                         ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "Next steps:"
echo ""
echo "  1. Start Ollama:"
echo "     $ ollama serve"
echo ""
echo "  2. Run CrackedCode:"
echo "     $ cd $CRACKEDCODE_DIR"
echo "     $ python3 src/main.py"
echo ""
echo "  3. Voice commands:"
echo "     • 'architect a system for X' - Design architecture"
echo "     • 'write code for feature Y' - Generate code"
echo "     • 'run tests' - Execute tests"
echo "     • 'review the code' - Critique code"
echo "     • 'exit' - Quit"
echo ""
echo "Config file: $CRACKEDCODE_DIR/config/default.json"
echo "Log file: $CRACKEDCODE_DIR/logs/crackedcode.log"
echo ""

if [ $ERRORS -gt 0 ]; then
    echo "⚠️  $ERRORS issue(s) detected. See above for details."
fi

exit $ERRORS