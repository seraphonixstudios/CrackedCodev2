#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   █████╗  ██████╗  ██████╗ ████████╗    ██████╗  ██╗     ██╗ ██████╗ ██████╗  █████╗ ║
║  ██╔══██╗██╔═══██╗██╔═══██╗╚══██╔══╝    ██╔══██╗ ██║     ██║██╔════╝ ██╔══██╗██╔══██╗║
║  ███████║██║   ██║██║   ██║   ██║       ██████╔╝ ██║     ██║██║  ███╗██████╔╝███████║║
║  ██╔══██║██║   ██║██║   ██║   ██║       ██╔══██╗ ██║     ██║██║   ██║██╔══██╗██╔══██║║
║  ██║  ██║╚██████╔╝╚██████╔╝   ██║       ██║  ██║ ███████╗██║██║   ██║██║  ██║██║  ██║║
║  ╚═╝  ╚═╝ ╚═════╝  ╚═════╝    ╚═╝       ╚═╝  ╚═╝ ╚══════╝╚═╝╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝║
║                                                                              ║
║                         Voice Engine Module                                   ║
║              Speech-to-Text + Text-to-Speech Integration                      ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

CrackedCode Voice Engine
Module for Speech Recognition and Speech Synthesis

Author: CrackedCode Team
License: MIT
"""

import os
import sys
import json
import subprocess
import threading
import platform
import wave
import struct
from pathlib import Path
from typing import Optional, List, Tuple, Callable
from dataclasses import dataclass
from enum import Enum

try:
    from faster_whisper import WhisperModel
    import sounddevice as sd
    import numpy as np
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    FASTER_WHISPER_AVAILABLE = False

try:
    import pyaudio
    PY_AUDIO_AVAILABLE = True
except ImportError:
    PY_AUDIO_AVAILABLE = False


class VoiceMode(Enum):
    PUSH_TO_TALK = "ptt"
    CONTINUOUS = "continuous"
    HOTWORD = "hotword"
    COMMAND = "command"


@dataclass
class AudioConfig:
    sample_rate: int = 16000
    channels: int = 1
    chunk_size: int = 1024
    format: str = "float32"
    duration: float = 5.0
    silence_threshold: float = 0.01
    silence_timeout: float = 2.0


@dataclass
class TranscriptionResult:
    text: str
    language: str = "en"
    confidence: float = 0.0
    segments: List[dict] = None

    def __post_init__(self):
        if self.segments is None:
            self.segments = []


@dataclass
class SynthesisResult:
    audio_file: str
    duration: float = 0.0
    success: bool = True
    error: Optional[str] = None


class STTEngine:
    """Speech-to-Text Engine using faster-whisper"""

    SUPPORTED_MODELS = {
        "tiny": {"params": "39M", "speed": "fastest", "accuracy": "lowest"},
        "base": {"params": "74M", "speed": "fast", "accuracy": "low"},
        "small": {"params": "244M", "speed": "medium", "accuracy": "medium"},
        "medium": {"params": "769M", "speed": "slow", "accuracy": "good"},
        "large": {"params": "1550M", "speed": "slowest", "accuracy": "best"},
    }

    def __init__(self, model_size: str = "medium.en", config: AudioConfig = None):
        self.model_size = model_size.replace(".en", "")
        self.use_english = model_size.endswith(".en")
        self.config = config or AudioConfig()
        self.model = None
        self.device = "cpu"
        self.compute_type = "int8"

    def _detect_device(self) -> str:
        if platform.system() == "Windows":
            try:
                result = subprocess.run(
                    ["nvidia-smi"],
                    capture_output=True,
                    check=True
                )
                return "cuda"
            except:
                return "cpu"
        else:
            try:
                subprocess.run(
                    ["nvidia-smi"],
                    capture_output=True,
                    check=True
                )
                return "cuda"
            except:
                return "cpu"

    def load(self) -> bool:
        if not FASTER_WHISPER_AVAILABLE:
            print("Error: faster-whisper not installed")
            print("Install with: pip install faster-whisper sounddevice numpy")
            return False

        self.device = self._detect_device()
        self.compute_type = "float16" if self.device == "cuda" else "int8"

        print(f"Loading Whisper model: {self.model_size}")
        print(f"  Device: {self.device}")
        print(f"  Compute: {self.compute_type}")

        try:
            self.model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type
            )
            print(f"✅ STT Engine loaded successfully")
            return True

        except Exception as e:
            print(f"❌ Failed to load STT model: {e}")
            return False

    def transcribe(self, audio: np.ndarray, beam_size: int = 5,
                  language: Optional[str] = None,
                  vad_filter: bool = True) -> TranscriptionResult:
        if not self.model:
            return TranscriptionResult(
                text="",
                error="Model not loaded"
            )

        language = language or ("en" if self.use_english else None)

        try:
            segments, info = self.model.transcribe(
                audio,
                beam_size=beam_size,
                language=language,
                vad_filter=vad_filter,
                word_timestamps=False
            )

            text = " ".join(seg.text for seg in segments).strip()

            return TranscriptionResult(
                text=text,
                language=info.language if info.language else "en",
                confidence=info.language_probability,
                segments=[
                    {"text": seg.text, "start": seg.start, "end": seg.end}
                    for seg in segments
                ]
            )

        except Exception as e:
            return TranscriptionResult(
                text=f"Error: {e}",
                error=str(e)
            )

    def record(self, duration: float = None) -> np.ndarray:
        duration = duration or self.config.duration

        print(f"🎤 Recording for {duration}s...")
        recording = sd.rec(
            int(duration * self.config.sample_rate),
            samplerate=self.config.sample_rate,
            channels=self.config.channels,
            dtype=self.config.format
        )
        sd.wait()
        return np.squeeze(recording)

    def transcribe_audio(self, audio: np.ndarray) -> TranscriptionResult:
        return self.transcribe(audio)


class TTSEngine:
    """Text-to-Speech Engine using Piper"""

    SUPPORTED_VOICES = {
        "en_US-lessac": {"quality": "high", "size": "78MB"},
        "en_US-lessac-medium": {"quality": "high", "size": "78MB"},
        "en_US-lessac-large": {"quality": "highest", "size": "156MB"},
        "en_GB-southern_english_female-medium": {"quality": "high", "size": "78MB"},
        "de_DE-max-medium": {"quality": "high", "size": "78MB"},
        "fr_FR-siwis-medium": {"quality": "high", "size": "78MB"},
    }

    def __init__(self, voice: str = "en_US-lessac-medium"):
        self.voice = voice
        self.piper_path = self._find_piper()
        self.voice_model_path = self._find_voice_model()

    def _find_piper(self) -> Optional[Path]:
        search_paths = [
            Path("/usr/local/bin/piper"),
            Path("/usr/bin/piper"),
            Path.home() / ".local/bin/piper",
            Path.home() / ".piper/piper.exe",
            Path("C:/Users/User/.piper/piper.exe"),
        ]

        for path in search_paths:
            if path.exists():
                return path

        return None

    def _find_voice_model(self) -> Optional[Path]:
        if platform.system() == "Windows":
            base = Path.home() / ".piper"
        else:
            base = Path.home() / ".local/share/piper-voices"

        possible_paths = [
            base / f"{self.voice}.onnx",
            base / self.voice / f"{self.voice}.onnx",
        ]

        for path in possible_paths:
            if path.exists():
                return path

        return possible_paths[0] if possible_paths[0].parent.exists() else None

    def is_ready(self) -> bool:
        return self.piper_path is not None and self.voice_model_path is not None

    def speak(self, text: str, output_file: Optional[str] = None) -> SynthesisResult:
        if not self.is_ready():
            return SynthesisResult(
                audio_file="",
                success=False,
                error="Piper not configured"
            )

        output_file = output_file or "/tmp/crackedcode_speak.wav"
        output_path = Path(output_file)

        cmd = [
            str(self.piper_path),
            "--model", str(self.voice_model_path),
            "--output_file", str(output_path)
        ]

        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            proc.communicate(input=text.encode(), timeout=30)

            if not output_path.exists():
                return SynthesisResult(
                    audio_file=str(output_path),
                    success=False,
                    error="Output file not created"
                )

            duration = self._get_audio_duration(output_path)

            self._play_audio(output_path)

            return SynthesisResult(
                audio_file=str(output_path),
                duration=duration,
                success=True
            )

        except subprocess.TimeoutExpired:
            return SynthesisResult(
                audio_file=str(output_path),
                success=False,
                error="TTS timeout"
            )
        except Exception as e:
            return SynthesisResult(
                audio_file=str(output_path),
                success=False,
                error=str(e)
            )

    def _get_audio_duration(self, wav_file: Path) -> float:
        try:
            with wave.open(str(wav_file), 'r') as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                return frames / rate
        except:
            return 0.0

    def _play_audio(self, wav_file: Path):
        if platform.system() == "Windows":
            subprocess.run(
                ["start", "/b", str(wav_file)],
                shell=True,
                capture_output=True
            )
        elif platform.system() == "Darwin":
            subprocess.run(
                ["afplay", str(wav_file)],
                capture_output=True
            )
        else:
            subprocess.run(
                ["aplay", str(wav_file)],
                capture_output=True
            )


class SynthesisError(Exception):
    pass


class CoquiTTSEngine:
    """Alternative TTS using Coqui for higher quality voices"""

    def __init__(self, model: str = "xtts_v31"):
        self.model = model
        self.tts = None

    def load(self) -> bool:
        try:
            from TTS.api import TTS
            self.tts = TTS(model_path=self.model, gpu=True)
            return True
        except ImportError:
            print("Coqui TTS not installed")
            print("Install with: pip install coqui-tts")
            return False
        except Exception as e:
            print(f"Failed to load Coqui: {e}")
            return False

    def speak(self, text: str, output_file: str = "/tmp/crackedcode_coqui.wav") -> SynthesisResult:
        if not self.tts:
            return SynthesisResult(
                audio_file=output_file,
                success=False,
                error="Model not loaded"
            )

        try:
            self.tts.tts_to_file(
                text=text,
                speaker_wav="reference.wav",
                language="en",
                file_path=output_file
            )

            return SynthesisResult(
                audio_file=output_file,
                success=True
            )

        except Exception as e:
            return SynthesisResult(
                audio_file=output_file,
                success=False,
                error=str(e)
            )


class VoiceHotkeyManager:
    """Manage voice hotkeys for push-to-talk and commands"""

    def __init__(self, callback: Optional[Callable] = None):
        self.callback = callback
        self.listening = False
        self.hotkey = "<ctrl>+<shift>+v"

    def start_listening(self):
        self.listening = True
        print(f"🎤 Voice hotkey enabled: {self.hotkey}")

    def stop_listening(self):
        self.listening = False

    def trigger(self):
        if self.callback:
            self.callback()


class VoiceController:
    """Complete voice I/O controller"""

    def __init__(self, stt_model: str = "medium.en",
                 tts_voice: str = "en_US-lessac-medium",
                 mode: VoiceMode = VoiceMode.PUSH_TO_TALK,
                 audio_config: AudioConfig = None):
        self.stt = STTEngine(stt_model)
        self.tts = TTSEngine(tts_voice)
        self.mode = mode
        self.config = audio_config or AudioConfig()
        self.hotkey_manager = VoiceHotkeyManager()
        self.initialized = False

    def initialize(self, load_stt: bool = True, load_tts: bool = True) -> bool:
        print("Initializing Voice Controller...")

        success = True

        if load_stt:
            success = self.stt.load() and success

        if load_tts:
            success = self.tts.is_ready() or success
            if not self.tts.is_ready():
                print("⚠️  TTS not ready, but continuing...")

        self.initialized = success
        print(f"✅ Voice Controller ready" if success else "❌ Voice init failed")
        return success

    def listen(self, duration: float = None) -> str:
        if not self.initialized:
            return "Error: Voice not initialized"

        duration = duration or self.config.duration
        audio = self.stt.record(duration)
        result = self.stt.transcribe_audio(audio)

        return result.text

    def listen_continuously(self, callback: Callable[[str], None],
                      duration: float = 3.0, silence_timeout: float = 3.0):
        if not self.initialized:
            print("Error: Voice not initialized")
            return

        print(f"🎤 Continuous listening mode (timeout: {silence_timeout}s)")

        while True:
            audio = self.stt.record(duration)
            result = self.stt.transcribe_audio(audio)

            if result.text and len(result.text) > 2:
                callback(result.text)

            threading.Event().wait(0.1)

    def speak(self, text: str) -> bool:
        if not self.tts.is_ready():
            print(f"Speaking: {text}")
            return False

        result = self.tts.speak(text)
        return result.success

    def voice_loop(self):
        print("\n" + "=" * 50)
        print("🎤 Voice Loop Ready")
        print("=" * 50)
        print(f"Mode: {self.mode.value}")
        print("Commands:")
        print("  • Say 'exit' to quit")
        print("  • Say 'listen' to activate")
        print()

        while True:
            try:
                if self.mode == VoiceMode.PUSH_TO_TALK:
                    input("\nPress Enter then speak... ")

                transcript = self.listen()

                if not transcript or transcript.startswith("Error"):
                    continue

                print(f"👤 You: {transcript}")

                if transcript.lower() in ["exit", "quit", "shutdown"]:
                    print("👋 Goodbye!")
                    self.speak("Goodbye")
                    break

                if self.callback:
                    self.callback(transcript)

            except KeyboardInterrupt:
                print("\n\nInterrupted. Press Ctrl+C to exit.")
            except Exception as e:
                print(f"Error: {e}")

    def set_callback(self, callback: Callable):
        self.hotkey_manager.callback = callback


def test_stt():
    """Test speech recognition"""
    print("\n🧪 Testing STT Engine...")
    stt = STTEngine("medium.en")
    if stt.load():
        audio = stt.record(5.0)
        result = stt.transcribe_audio(audio)
        print(f"Result: {result.text}")
        return True
    return False


def test_tts():
    """Test speech synthesis"""
    print("\n🧪 Testing TTS Engine...")
    tts = TTSEngine("en_US-lessac-medium")
    if tts.is_ready():
        result = tts.speak("CrackedCode voice system is working. Hello world!")
        print(f"Success: {result.success}")
        return result.success
    else:
        print("TTS not configured. Install Piper.")
        return False


def voice_main():
    """Main entry point for voice module"""
    import argparse

    parser = argparse.ArgumentParser(description="CrackedCode Voice Engine")
    parser.add_argument("--test-stt", action="store_true", help="Test STT")
    parser.add_argument("--test-tts", action="store_true", help="Test TTS")
    parser.add_argument("--stt-model", default="medium.en", help="STT model")
    parser.add_argument("--tts-voice", default="en_US-lessac-medium", help="TTS voice")
    parser.add_argument("--mode", default="ptt", choices=["ptt", "continuous"],
                     help="Voice mode")

    args = parser.parse_args()

    if args.test_stt:
        test_stt()
        return

    if args.test_tts:
        test_tts()
        return

    mode = VoiceMode.PUSH_TO_TALK if args.mode == "ptt" else VoiceMode.CONTINUOUS
    controller = VoiceController(args.stt_model, args.tts_voice, mode)

    if controller.initialize():
        controller.voice_loop()
    else:
        print("Voice initialization failed")


if __name__ == "__main__":
    voice_main()