@echo off
REM ============================================================================
REM CrackedCode Installation Script - Windows
REM SOTA Local Multi-Agent Coding Swarm with Voice I/O
REM ============================================================================

setlocal enabledelayedexpansion

echo.
echo ╔══════════════════════════════════════════════════════════════════════════════╗
echo ║                                                                              ║
echo ║   █████╗  ██████╗  ██████╗ ████████╗    ██████╗  ██╗     ██╗ ██████╗ ██████╗  █████╗ ║
echo ║  ██╔══██╗██╔═══██╗██╔═══██╗╚══██╔══╝    ██╔══██╗ ██║     ██║██╔════╝ ██╔══██╗██╔══██╗║
echo ║  ███████║██║   ██║██║   ██║   ██║       ██████╔╝ ██║     ██║██║  ███╗██████╔╝███████║║
echo ║  ██╔══██║██║   ██║██║   ██║   ██║       ██╔══██╗ ██║     ██║██║   ██║██╔══██╗██╔══██║║
echo ║  ██║  ██║╚██████╔╝╚██████╔╝   ██║       ██║  ██║ ███████╗██║██║   ██║██║  ██║██║  ██║║
echo ║  ╚═╝  ╚═╝ ╚═════╝  ╚═════╝    ╚═╝       ╚═╝  ╚═╝ ╚══════╝╚═╝╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝║
echo ║                                                                              ║
echo ║                      WINDOWS INSTALLATION SCRIPT                             ║
echo ║                   SOTA Local Multi-Agent System                              ║
echo ╚══════════════════════════════════════════════════════════════════════════════╝

REM ============================================================================
REM CONFIGURATION
REM ============================================================================

set "CRACKEDCODE_DIR=%USERPROFILE%\crackedcode"
set "OLLAMA_MODEL=qwen3-coder:32b"
set "WHISPER_MODEL=medium.en"
set "TTS_VOICE=en_US-lessac-medium"

echo.
echo 📋 Configuration:
echo   Install directory: %CRACKEDCODE_DIR%
echo   Ollama model: %OLLAMA_MODEL%
echo   Whisper model: %WHISPER_MODEL%
echo   TTS voice: %TTS_VOICE%
echo.

REM ============================================================================
REM CHECK PYTHON
REM ============================================================================

echo 📦 Checking Python...

python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python not found. Install from https://python.org
    echo   Make sure to add Python to PATH
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo   Python version: %PYTHON_VERSION%

REM ============================================================================
REM INSTALL PYTHON PACKAGES
REM ============================================================================

echo 📦 Installing Python packages...

python -m pip install --upgrade pip

python -m pip install ^
    ollama ^
    faster-whisper ^
    sounddevice ^
    numpy

if errorlevel 1 (
    echo ❌ Failed to install Python packages
    pause
    exit /b 1
)

echo   ✅ Python packages installed

REM ============================================================================
REM SETUP OLLAMA
REM ============================================================================

echo 📦 Setting up Ollama...

where ollama >nul 2>&1
if errorlevel 1 (
    echo   Installing Ollama for Windows...
    powershell -Command "irm https://ollama.ai/install.ps1 ^| iex"
)

where ollama >nul 2>&1
if not errorlevel 1 (
    echo   📥 Pulling Ollama models...
    ollama pull %OLLAMA_MODEL%
    ollama pull deepseek-coder-v2:16b
    ollama pull llama3.3:70b-instruct-q4_K_M
    echo   ✅ Ollama models ready
) else (
    echo   ⚠️  Ollama not in PATH. Start 'ollama serve' after install.
)

REM ============================================================================
REM SETUP PIPER TTS
REM ============================================================================

echo 📦 Setting up Piper TTS...

if not exist "%USERPROFILE%\.piper" mkdir "%USERPROFILE%\.piper"

powershell -Command "Invoke-WebRequest -Uri 'https://github.com/rhasspy/piper/releases/download/2024.08.01/piper-windows-amd64.zip' -OutFile '%TEMP%\piper.zip'"
powershell -Command "Expand-Archive -Path '%TEMP%\piper.zip' -DestinationPath '%USERPROFILE%\.piper' -Force"
del /q "%TEMP%\piper.zip" 2>nul

echo   📥 Downloading voice model...
powershell -Command "Invoke-WebRequest -Uri 'https://github.com/rhasspy/piper/releases/download/2024.08.01/%TTS_VOICE%.onnx' -OutFile '%USERPROFILE%\.piper\%TTS_VOICE%.onnx'"
powershell -Command "Invoke-WebRequest -Uri 'https://github.com/rhasspy/piper/releases/download/2024.08.01/%TTS_VOICE%.onnx.json' -OutFile '%USERPROFILE%\.piper\%TTS_VOICE%.onnx.json'"

echo   ✅ Piper TTS ready

REM ============================================================================
REM CREATE PROJECT STRUCTURE
REM ============================================================================

echo 📦 Creating project structure...

if not exist "%CRACKEDCODE_DIR%\src" mkdir "%CRACKEDCODE_DIR%\src"
if not exist "%CRACKEDCODE_DIR%\config" mkdir "%CRACKEDCODE_DIR%\config"
if not exist "%CRACKEDCODE_DIR%\logs" mkdir "%CRACKEDCODE_DIR%\logs"

echo   ✅ Project structure created

REM ============================================================================
REM VERIFY INSTALLATION
REM ============================================================================

echo.
echo 🧪 Verifying installation...

set ERRORS=0

python -c "import ollama" 2>nul
if errorlevel 1 (
    echo   ❌ ollama Python SDK not working
    set ERRORS=1
) else (
    echo   ✅ ollama Python SDK ready
)

python -c "import faster_whisper" 2>nul
if errorlevel 1 (
    echo   ⚠️  faster-whisper not working
) else (
    echo   ✅ faster-whisper ready
)

python -c "import sounddevice" 2>nul
if errorlevel 1 (
    echo   ⚠️  sounddevice not working
) else (
    echo   ✅ sounddevice ready
)

REM ============================================================================
REM COMPLETION
REM ============================================================================

echo.
echo ╔══════════════════════════════════════════════════════════════════════════════╗
echo ║                       ✅ INSTALLATION COMPLETE                         ║
echo ╚═══════════════════════��══════════════════════════════════════════════════════╝
echo.
echo Next steps:
echo.
echo   1. Start Ollama:
echo      ollama serve
echo.
echo   2. Run CrackedCode:
echo      cd %CRACKEDCODE_DIR%
echo      python src\main.py
echo.
echo   3. Voice commands:
echo      • "architect a system for X" - Design architecture
echo      • "write code for feature Y" - Generate code
echo      • "run tests" - Execute tests
echo      • "review the code" - Critique code
echo      • "exit" - Quit
echo.
echo   Config: %CRACKEDCODE_DIR%\config\default.json
echo   Logs: %CRACKEDCODE_DIR%\logs\crackedcode.log
echo.

if %ERRORS% GTR 0 (
    echo ⚠️  Issues detected. See above for details.
)

pause