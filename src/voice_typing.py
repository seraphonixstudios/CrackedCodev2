#!/usr/bin/env python3
"""
CrackedCode Voice Typing Module (Compatibility Wrapper)

This module re-exports the unified voice engine for backward compatibility.
New code should import directly from src.voice_engine.

DEPRECATED: Use src.voice_engine for new development.
"""

from src.voice_engine import (
    UnifiedVoiceEngine as VoiceTyping,
    VoiceConfig,
    STTResult as TranscriptionResult,
    CommandType,
    VoiceCommand,
    TTSResult,
    VoiceMode,
    TTSBackend,
    get_voice_engine,
)

# Re-export legacy VOICE_COMMANDS mapping for compatibility
VOICE_COMMANDS = {
    "write": ["write", "create", "generate", "make", "new file", "new code"],
    "execute": ["run", "execute", "start", "launch", "go", "do it"],
    "debug": ["fix", "debug", "repair", "bug", "error"],
    "review": ["review", "analyze", "check", "audit"],
    "search": ["search", "find", "grep", "look for"],
    "save": ["save", "store", "keep", "export"],
    "open": ["open", "load", "read", "import"],
    "copy": ["copy", "duplicate", "clone", "to clipboard"],
    "paste": ["paste", "insert", "drop in"],
    "voice": ["voice mode", "speech", "speak", "record"],
    "stop": ["stop", "cancel", "abort", "exit", "quit"],
    "help": ["help", "assist", "support", "guide", "what"],
    "clear": ["clear", "wipe", "reset"],
    "copy_output": ["copy output", "copy result", "copy that"],
}

__all__ = [
    "VoiceTyping",
    "VoiceConfig",
    "TranscriptionResult",
    "CommandType",
    "VoiceCommand",
    "TTSResult",
    "VoiceMode",
    "TTSBackend",
    "VOICE_COMMANDS",
    "get_voice_engine",
]
