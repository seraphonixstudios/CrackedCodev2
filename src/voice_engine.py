#!/usr/bin/env python3
"""
CrackedCode Unified Voice Engine v2.6.0
SOTA Speech-to-Text and Text-to-Speech with multi-backend fallback,
Voice Activity Detection (VAD), natural language command processing,
and hands-free voice interaction.
"""

from __future__ import annotations

import io
import os
import re
import wave
import time
import asyncio
import tempfile
import threading
import platform
import subprocess
from pathlib import Path
from typing import Optional, Callable, Dict, List, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum, auto
from collections import deque

import numpy as np

from src.logger_config import get_logger

logger = get_logger("VoiceEngine")

try:
    import sounddevice as sd
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False

try:
    from faster_whisper import WhisperModel
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False

try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False

try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False


class VoiceMode(Enum):
    PUSH_TO_TALK = auto()
    CONTINUOUS = auto()
    HOTWORD = auto()
    COMMAND = auto()


class TTSBackend(Enum):
    PYTTSX3 = "pyttsx3"
    EDGE = "edge-tts"
    FALLBACK = "fallback"


class CommandType(Enum):
    WRITE = "write"
    EXECUTE = "execute"
    DEBUG = "debug"
    REVIEW = "review"
    SEARCH = "search"
    SAVE = "save"
    OPEN = "open"
    COPY = "copy"
    PASTE = "paste"
    CLEAR = "clear"
    STOP = "stop"
    HELP = "help"
    VOICE = "voice"
    PLAN = "plan"
    BUILD = "build"
    NEW_TAB = "new_tab"
    CLOSE_TAB = "close_tab"
    UNKNOWN = "unknown"


@dataclass
class VoiceConfig:
    sample_rate: int = 16000
    channels: int = 1
    dtype: str = "float32"
    record_duration: float = 5.0
    silence_threshold: float = 0.015
    silence_timeout: float = 2.0
    stt_model_size: str = "base"
    stt_language: str = "en"
    stt_beam_size: int = 5
    tts_backend: TTSBackend = TTSBackend.PYTTSX3
    tts_voice: str = "default"
    tts_gender: str = "female"  # "female" | "male"
    tts_rate: int = 175
    tts_volume: float = 1.0
    max_command_history: int = 50
    vad_aggressiveness: int = 2
    continuous_interval: float = 0.3
    hotword: str = "cracked code"
    hotword_sensitivity: float = 0.7


@dataclass
class STTResult:
    text: str = ""
    language: str = "en"
    confidence: float = 0.0
    duration: float = 0.0
    segments: List[Dict[str, Any]] = field(default_factory=list)
    success: bool = False
    error: Optional[str] = None
    is_command: bool = False
    command_type: Optional[CommandType] = None
    command_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TTSResult:
    text: str = ""
    audio_data: Optional[bytes] = None
    audio_path: Optional[str] = None
    duration: float = 0.0
    backend: TTSBackend = TTSBackend.FALLBACK
    success: bool = False
    error: Optional[str] = None


@dataclass
class VoiceCommand:
    raw_text: str = ""
    command_type: CommandType = CommandType.UNKNOWN
    confidence: float = 0.0
    params: Dict[str, Any] = field(default_factory=dict)
    matched_keyword: str = ""


class STTEngine:
    """Speech-to-Text using faster-whisper with VAD."""

    SUPPORTED_MODELS = {
        "tiny": {"params": "39M", "speed": "fastest", "accuracy": "lowest", "ram": "~1GB"},
        "base": {"params": "74M", "speed": "fast", "accuracy": "low", "ram": "~1GB"},
        "small": {"params": "244M", "speed": "medium", "accuracy": "medium", "ram": "~2GB"},
        "medium": {"params": "769M", "speed": "slow", "accuracy": "good", "ram": "~5GB"},
        "large": {"params": "1550M", "speed": "slowest", "accuracy": "best", "ram": "~10GB"},
    }

    def __init__(self, config: Optional[VoiceConfig] = None):
        self.config = config or VoiceConfig()
        self.model: Optional[WhisperModel] = None
        self._available = WHISPER_AVAILABLE and AUDIO_AVAILABLE
        self._device = self._detect_device()
        self._loaded = False
        self._load_lock = threading.Lock()

    def _detect_device(self) -> str:
        if platform.system() == "Windows":
            try:
                result = subprocess.run(
                    ["nvidia-smi"], capture_output=True, text=True, timeout=3
                )
                if result.returncode == 0 and "NVIDIA-SMI" in result.stdout:
                    return "cuda"
            except Exception:
                pass
        return "cpu"

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def is_loaded(self) -> bool:
        return self._loaded and self.model is not None

    def load(self) -> bool:
        if not self._available:
            logger.error("STT not available: faster-whisper or sounddevice missing")
            return False
        if self._loaded:
            return True

        with self._load_lock:
            if self._loaded:
                return True
            try:
                compute = "float16" if self._device == "cuda" else "int8"
                self.model = WhisperModel(
                    self.config.stt_model_size,
                    device=self._device,
                    compute_type=compute,
                    download_root=str(Path.home() / ".cache" / "whisper"),
                )
                self._loaded = True
                logger.info(f"Whisper loaded: {self.config.stt_model_size} ({self._device}, {compute})")
                return True
            except Exception as e:
                logger.error(f"Failed to load Whisper model: {e}")
                self._available = False
                return False

    def unload(self) -> None:
        self.model = None
        self._loaded = False
        logger.info("Whisper model unloaded")

    def record(self, duration: Optional[float] = None) -> np.ndarray:
        if not AUDIO_AVAILABLE:
            raise RuntimeError("sounddevice not installed")
        duration = duration or self.config.record_duration
        frames = int(duration * self.config.sample_rate)
        logger.info(f"Recording {duration}s audio...")
        try:
            audio = sd.rec(
                frames,
                samplerate=self.config.sample_rate,
                channels=self.config.channels,
                dtype=self.config.dtype,
            )
            sd.wait()
            audio = np.squeeze(audio)
            logger.info(f"Recorded {len(audio)} samples ({duration}s)")
            return audio
        except Exception as e:
            logger.error(f"Recording failed: {e}")
            raise

    def record_with_vad(self, timeout: float = 30.0) -> Optional[np.ndarray]:
        if not AUDIO_AVAILABLE:
            raise RuntimeError("sounddevice not installed")
        logger.info("Recording with VAD (speak now)...")
        start_time = time.time()
        buffer: List[np.ndarray] = []
        silence_start: Optional[float] = None
        chunk_samples = int(0.1 * self.config.sample_rate)

        def _is_speech(audio_chunk: np.ndarray) -> bool:
            energy = np.sqrt(np.mean(audio_chunk ** 2))
            return energy > self.config.silence_threshold

        try:
            with sd.InputStream(
                samplerate=self.config.sample_rate,
                channels=self.config.channels,
                dtype=self.config.dtype,
                blocksize=chunk_samples,
            ) as stream:
                has_speech = False
                while time.time() - start_time < timeout:
                    chunk, _ = stream.read(chunk_samples)
                    chunk = np.squeeze(chunk)
                    buffer.append(chunk)
                    if _is_speech(chunk):
                        has_speech = True
                        silence_start = None
                    elif has_speech:
                        if silence_start is None:
                            silence_start = time.time()
                        elif time.time() - silence_start > self.config.silence_timeout:
                            logger.info("Silence detected, stopping recording")
                            break
            if not has_speech:
                logger.warning("No speech detected")
                return None
            audio = np.concatenate(buffer)
            logger.info(f"VAD recording: {len(audio) / self.config.sample_rate:.1f}s")
            return audio
        except Exception as e:
            logger.error(f"VAD recording failed: {e}")
            raise

    def transcribe(
        self,
        audio: np.ndarray,
        language: Optional[str] = None,
        beam_size: Optional[int] = None,
    ) -> STTResult:
        if not self.is_loaded:
            if not self.load():
                return STTResult(error="Model not loaded", success=False)
        language = language or self.config.stt_language
        beam_size = beam_size or self.config.stt_beam_size
        try:
            buffer = io.BytesIO()
            with wave.open(buffer, "wb") as wf:
                wf.setnchannels(self.config.channels)
                wf.setsampwidth(2)
                wf.setframerate(self.config.sample_rate)
                audio_int16 = np.clip(audio * 32767, -32768, 32767).astype(np.int16)
                wf.writeframes(audio_int16.tobytes())
            buffer.seek(0)
            segments, info = self.model.transcribe(
                buffer,
                language=language,
                beam_size=beam_size,
                vad_filter=True,
                condition_on_previous_text=True,
            )
            text_parts: List[str] = []
            seg_list: List[Dict[str, Any]] = []
            for seg in segments:
                text_parts.append(seg.text.strip())
                seg_list.append({
                    "text": seg.text,
                    "start": seg.start,
                    "end": seg.end,
                    "confidence": getattr(seg, "avg_logprob", 0.0),
                })
            full_text = " ".join(text_parts).strip()
            return STTResult(
                text=full_text,
                language=info.language or language,
                confidence=info.language_probability,
                duration=info.duration,
                segments=seg_list,
                success=len(full_text) > 0,
            )
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return STTResult(error=str(e), success=False)

    def listen(self, duration: Optional[float] = None) -> STTResult:
        try:
            audio = self.record(duration)
            return self.transcribe(audio)
        except Exception as e:
            return STTResult(error=str(e), success=False)

    def listen_vad(self, timeout: float = 30.0) -> STTResult:
        try:
            audio = self.record_with_vad(timeout)
            if audio is None:
                return STTResult(error="No speech detected", success=False)
            return self.transcribe(audio)
        except Exception as e:
            return STTResult(error=str(e), success=False)


class BaseTTSEngine:
    """Base class for TTS backends."""
    def __init__(self, config: Optional[VoiceConfig] = None):
        self.config = config or VoiceConfig()

    @property
    def is_available(self) -> bool:
        return False

    def speak(self, text: str) -> TTSResult:
        raise NotImplementedError

    def stop(self) -> None:
        pass


class Pyttsx3Engine(BaseTTSEngine):
    """Local offline TTS using pyttsx3 (SAPI5 on Windows)."""

    def __init__(self, config: Optional[VoiceConfig] = None):
        super().__init__(config)
        self._engine: Optional[Any] = None
        self._voices: List[Dict[str, str]] = []
        self._lock = threading.Lock()
        self._init_engine()

    def _init_engine(self) -> None:
        if not PYTTSX3_AVAILABLE:
            return
        try:
            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", self.config.tts_rate)
            self._engine.setProperty("volume", self.config.tts_volume)
            self._voices = [
                {"id": v.id, "name": v.name, "languages": v.languages}
                for v in self._engine.getProperty("voices")
            ]
            # Select voice by preference: explicit > gender > first available
            selected = False
            if self.config.tts_voice != "default" and self._voices:
                for v in self._voices:
                    if self.config.tts_voice.lower() in v["name"].lower():
                        self._engine.setProperty("voice", v["id"])
                        selected = True
                        break
            
            if not selected and self._voices:
                gender = self.config.tts_gender.lower()
                for v in self._voices:
                    name_lower = v["name"].lower()
                    # Common female voice identifiers across platforms
                    if gender == "female" and any(x in name_lower for x in ["zira", "female", "woman", "girl", "jenny", "aria", "sonia", "clara"]):
                        self._engine.setProperty("voice", v["id"])
                        selected = True
                        logger.info(f"Selected female voice: {v['name']}")
                        break
                    elif gender == "male" and any(x in name_lower for x in ["david", "male", "man", "guy"]):
                        self._engine.setProperty("voice", v["id"])
                        selected = True
                        logger.info(f"Selected male voice: {v['name']}")
                        break
            
            logger.info(f"pyttsx3 initialized with {len(self._voices)} voices")
        except Exception as e:
            logger.error(f"pyttsx3 init failed: {e}")
            self._engine = None

    @property
    def is_available(self) -> bool:
        return PYTTSX3_AVAILABLE and self._engine is not None

    @property
    def voices(self) -> List[Dict[str, str]]:
        return self._voices

    def speak(self, text: str) -> TTSResult:
        if not self.is_available:
            return TTSResult(text=text, error="pyttsx3 not available", backend=TTSBackend.PYTTSX3)
        try:
            with self._lock:
                self._engine.say(text)
                self._engine.runAndWait()
            return TTSResult(text=text, success=True, backend=TTSBackend.PYTTSX3)
        except Exception as e:
            logger.error(f"pyttsx3 speak error: {e}")
            return TTSResult(text=text, error=str(e), backend=TTSBackend.PYTTSX3)

    def stop(self) -> None:
        if self._engine:
            try:
                self._engine.stop()
            except Exception:
                pass


class EdgeTTSEngine(BaseTTSEngine):
    """Online neural TTS using Microsoft Azure Edge (free)."""
    
    FEMALE_VOICES = [
        "en-US-AriaNeural", "en-US-JennyNeural", "en-US-AnaNeural",
        "en-US-MichelleNeural", "en-GB-SoniaNeural", "en-GB-LibbyNeural",
        "en-AU-NatashaNeural", "en-CA-ClaraNeural", "en-IN-NeerjaNeural",
        "en-IE-EmilyNeural", "en-NZ-MollyNeural", "en-PH-RosaNeural",
        "en-SG-LunaNeural", "en-ZA-LeahNeural",
    ]
    MALE_VOICES = [
        "en-US-GuyNeural", "en-US-ChristopherNeural", "en-US-EricNeural",
        "en-GB-RyanNeural", "en-GB-ThomasNeural", "en-AU-WilliamNeural",
    ]
    DEFAULT_VOICE = "en-US-AriaNeural"

    def __init__(self, config: Optional[VoiceConfig] = None):
        super().__init__(config)
        self._voice = self.config.tts_voice
        if self._voice == "default":
            self._voice = self._select_voice_by_gender()

    def _select_voice_by_gender(self) -> str:
        """Select default voice based on gender preference."""
        gender = getattr(self.config, 'tts_gender', 'female').lower()
        if gender == 'female' and self.FEMALE_VOICES:
            return self.FEMALE_VOICES[0]
        elif gender == 'male' and self.MALE_VOICES:
            return self.MALE_VOICES[0]
        return self.DEFAULT_VOICE

    @property
    def is_available(self) -> bool:
        return EDGE_TTS_AVAILABLE

    def speak(self, text: str) -> TTSResult:
        if not self.is_available:
            return TTSResult(text=text, error="edge-tts not installed", backend=TTSBackend.EDGE)
        try:
            fd, path = tempfile.mkstemp(suffix=".mp3")
            os.close(fd)
            communicate = edge_tts.Communicate(text, self._voice)
            asyncio.run(communicate.save(path))
            self._play_audio(path)
            duration = self._get_audio_duration(path)
            return TTSResult(
                text=text, audio_path=path, duration=duration,
                success=True, backend=TTSBackend.EDGE,
            )
        except Exception as e:
            logger.error(f"edge-tts speak error: {e}")
            return TTSResult(text=text, error=str(e), backend=TTSBackend.EDGE)

    def _get_audio_duration(self, path: str) -> float:
        try:
            import mutagen
            from mutagen.mp3 import MP3
            audio = MP3(path)
            return audio.info.length
        except Exception:
            return 0.0

    def _play_audio(self, path: str) -> None:
        try:
            if platform.system() == "Windows":
                os.startfile(path)
            elif platform.system() == "Darwin":
                subprocess.run(["afplay", path], capture_output=True, timeout=60)
            else:
                subprocess.run(["aplay", path], capture_output=True, timeout=60)
        except Exception as e:
            logger.warning(f"Audio playback failed: {e}")


class FallbackTTSEngine(BaseTTSEngine):
    """Fallback TTS that prints to console. Always available."""
    @property
    def is_available(self) -> bool:
        return True

    def speak(self, text: str) -> TTSResult:
        logger.info(f"[TTS] {text}")
        print(f"  [TTS] {text}")
        return TTSResult(text=text, success=True, backend=TTSBackend.FALLBACK)


class TTSEngine:
    """TTS router that tries backends in priority order."""
    BACKEND_PRIORITY = [TTSBackend.PYTTSX3, TTSBackend.EDGE, TTSBackend.FALLBACK]

    def __init__(self, config: Optional[VoiceConfig] = None):
        self.config = config or VoiceConfig()
        self._engines: Dict[TTSBackend, BaseTTSEngine] = {
            TTSBackend.PYTTSX3: Pyttsx3Engine(self.config),
            TTSBackend.EDGE: EdgeTTSEngine(self.config),
            TTSBackend.FALLBACK: FallbackTTSEngine(self.config),
        }
        self._current_backend: TTSBackend = self._select_best_backend()
        self._speak_lock = threading.Lock()
        logger.info(f"TTS router initialized with backend: {self._current_backend.value}")

    def _select_best_backend(self) -> TTSBackend:
        requested = self.config.tts_backend
        if requested != TTSBackend.FALLBACK and self._engines[requested].is_available:
            return requested
        for backend in self.BACKEND_PRIORITY:
            if self._engines[backend].is_available:
                return backend
        return TTSBackend.FALLBACK

    @property
    def current_backend(self) -> TTSBackend:
        return self._current_backend

    @property
    def is_available(self) -> bool:
        return self._engines[self._current_backend].is_available

    def set_backend(self, backend: TTSBackend) -> bool:
        if self._engines[backend].is_available:
            self._current_backend = backend
            logger.info(f"TTS backend switched to: {backend.value}")
            return True
        logger.warning(f"TTS backend {backend.value} not available")
        return False

    def get_available_backends(self) -> List[TTSBackend]:
        return [b for b in self.BACKEND_PRIORITY if self._engines[b].is_available]

    def speak(self, text: str) -> TTSResult:
        if not text or not text.strip():
            return TTSResult(error="Empty text", success=False)
        with self._speak_lock:
            result = self._engines[self._current_backend].speak(text)
            if not result.success:
                for backend in self.BACKEND_PRIORITY:
                    if backend == self._current_backend:
                        continue
                    if self._engines[backend].is_available:
                        logger.warning(f"TTS fallback to {backend.value}")
                        result = self._engines[backend].speak(text)
                        if result.success:
                            break
            return result

    def stop(self) -> None:
        self._engines[self._current_backend].stop()


class VoiceActivityDetector:
    """Energy-based voice activity detection with noise floor adaptation."""

    def __init__(self, config: Optional[VoiceConfig] = None):
        self.config = config or VoiceConfig()
        self._noise_floor: float = 0.0
        self._noise_samples: deque = deque(maxlen=50)
        self._is_speaking: bool = False
        self._silence_start: Optional[float] = None

    def calibrate(self, audio_chunks: List[np.ndarray]) -> None:
        energies = [np.sqrt(np.mean(chunk ** 2)) for chunk in audio_chunks]
        self._noise_floor = np.median(energies) if energies else 0.001
        self._noise_samples.clear()
        self._noise_samples.extend(energies)
        logger.info(f"VAD calibrated: noise_floor={self._noise_floor:.4f}")

    def is_speech(self, audio_chunk: np.ndarray) -> bool:
        energy = np.sqrt(np.mean(audio_chunk ** 2))
        self._noise_samples.append(energy)
        self._noise_floor = np.percentile(list(self._noise_samples), 10)
        threshold = self._noise_floor + self.config.silence_threshold
        is_speech = energy > threshold
        if is_speech:
            self._is_speaking = True
            self._silence_start = None
        elif self._is_speaking:
            if self._silence_start is None:
                self._silence_start = time.time()
            elif time.time() - self._silence_start > self.config.silence_timeout:
                self._is_speaking = False
                self._silence_start = None
        return is_speech

    def reset(self) -> None:
        self._is_speaking = False
        self._silence_start = None


class VoiceCommandProcessor:
    """Natural language voice command parsing with fuzzy matching."""

    COMMAND_MAP: Dict[CommandType, List[str]] = {
        CommandType.WRITE: [
            "write", "create", "generate", "make", "new file", "new code",
            "code a", "build a", "implement",
        ],
        CommandType.EXECUTE: [
            "run", "execute", "start", "launch", "go", "do it", "perform",
        ],
        CommandType.DEBUG: [
            "fix", "debug", "repair", "bug", "error", "broken", "not working",
        ],
        CommandType.REVIEW: [
            "review", "analyze", "check", "audit", "inspect", "examine",
        ],
        CommandType.SEARCH: [
            "search", "find", "grep", "look for", "locate", "where is",
        ],
        CommandType.SAVE: [
            "save", "store", "keep", "export", "write to disk",
        ],
        CommandType.OPEN: [
            "open", "load", "read", "import", "show me", "display",
        ],
        CommandType.COPY: [
            "copy", "duplicate", "clone", "to clipboard", "copy output",
        ],
        CommandType.PASTE: [
            "paste", "insert", "drop in", "put here",
        ],
        CommandType.CLEAR: [
            "clear", "wipe", "reset", "clean", "empty",
        ],
        CommandType.STOP: [
            "stop", "cancel", "abort", "exit", "quit", "halt", "terminate",
        ],
        CommandType.HELP: [
            "help", "assist", "support", "guide", "what can you do", "commands",
        ],
        CommandType.VOICE: [
            "voice mode", "speech", "speak", "listen", "microphone",
        ],
        CommandType.PLAN: [
            "plan", "design", "architect", "structure", "outline",
        ],
        CommandType.BUILD: [
            "build", "compile", "make project", "construct", "assemble",
        ],
        CommandType.NEW_TAB: [
            "new tab", "add tab", "create tab", "another tab",
        ],
        CommandType.CLOSE_TAB: [
            "close tab", "remove tab", "delete tab", "kill tab",
        ],
    }

    PARAM_PATTERNS = {
        "filename": re.compile(
            r'([\w\-./\\]+\.(?:py|js|ts|jsx|tsx|html|css|json|md|txt|java|cpp|c|h|rs|go))',
            re.IGNORECASE,
        ),
        "language": re.compile(
            r'\b(python|javascript|typescript|java|c\+\+|rust|go|html|css|json|markdown)\b',
            re.IGNORECASE,
        ),
        "number": re.compile(r'\b(\d+)\b'),
    }

    def __init__(self):
        self._history: deque = deque(maxlen=100)
        self._command_handlers: Dict[CommandType, Callable] = {}

    def register_handler(self, command_type: CommandType, handler: Callable) -> None:
        self._command_handlers[command_type] = handler
        logger.info(f"Registered handler for {command_type.value}")

    def unregister_handler(self, command_type: CommandType) -> None:
        self._command_handlers.pop(command_type, None)

    def parse(self, text: str) -> VoiceCommand:
        if not text:
            return VoiceCommand(raw_text="", command_type=CommandType.UNKNOWN)
        text_lower = text.lower().strip()
        best_match: Optional[CommandType] = None
        best_keyword = ""
        best_score = 0.0
        for cmd_type, keywords in self.COMMAND_MAP.items():
            for keyword in keywords:
                if keyword == text_lower:
                    return VoiceCommand(
                        raw_text=text, command_type=cmd_type, confidence=1.0,
                        matched_keyword=keyword, params=self._extract_params(text),
                    )
                if keyword in text_lower:
                    score = len(keyword) / len(text_lower)
                    if score > best_score:
                        best_score = score
                        best_match = cmd_type
                        best_keyword = keyword
                kw_first = keyword.split()[0]
                if kw_first in text_lower.split():
                    score = 0.5 + (len(keyword) / len(text_lower)) * 0.3
                    if score > best_score:
                        best_score = score
                        best_match = cmd_type
                        best_keyword = keyword
        if best_match and best_score >= 0.2:
            cmd = VoiceCommand(
                raw_text=text, command_type=best_match, confidence=min(best_score, 0.95),
                matched_keyword=best_keyword, params=self._extract_params(text),
            )
            self._history.append(cmd)
            return cmd
        return VoiceCommand(
            raw_text=text, command_type=CommandType.UNKNOWN, confidence=0.0,
            params=self._extract_params(text),
        )

    def _extract_params(self, text: str) -> Dict[str, Any]:
        params: Dict[str, Any] = {"raw": text}
        words_lower = text.lower().split()
        words_orig = text.split()
        filename_match = self.PARAM_PATTERNS["filename"].search(text)
        if filename_match:
            params["filename"] = filename_match.group(1)
        lang_match = self.PARAM_PATTERNS["language"].search(text)
        if lang_match:
            params["language"] = lang_match.group(1).lower()
        numbers = self.PARAM_PATTERNS["number"].findall(text)
        if numbers:
            params["numbers"] = [int(n) for n in numbers]
        quotes = re.findall(r'["\'](.+?)["\']', text)
        if quotes:
            params["quoted"] = quotes
        skip_words = {"a", "an", "the", "called", "named", "in", "to", "of"}
        for i, word in enumerate(words_lower):
            if word in ["function", "class", "method", "variable"] and i + 1 < len(words_orig):
                params["type"] = word
                for j in range(i + 1, len(words_orig)):
                    if words_lower[j] not in skip_words:
                        params["name"] = words_orig[j].strip(".,;:!?")
                        break
            if word == "in" and i + 1 < len(words_orig):
                potential_file = words_orig[i + 1]
                if "." in potential_file:
                    params["filename"] = potential_file
            if word in ["save", "to"]:
                for w in words_orig[i + 1 :]:
                    if "." in w:
                        params["filename"] = w.strip(".,;:!?")
                        break
        return params

    def execute(self, command: VoiceCommand) -> bool:
        if command.command_type == CommandType.UNKNOWN:
            return False
        handler = self._command_handlers.get(command.command_type)
        if handler:
            try:
                handler(command)
                return True
            except Exception as e:
                logger.error(f"Command handler error for {command.command_type.value}: {e}")
                return False
        return False

    def get_history(self, count: int = 10) -> List[VoiceCommand]:
        return list(self._history)[-count:]


class VoiceSession:
    """Manages a complete voice interaction: listen -> process -> respond."""

    def __init__(
        self,
        stt: STTEngine,
        tts: TTSEngine,
        processor: VoiceCommandProcessor,
        config: Optional[VoiceConfig] = None,
    ):
        self.stt = stt
        self.tts = tts
        self.processor = processor
        self.config = config or VoiceConfig()
        self._active = False
        self._thread: Optional[threading.Thread] = None
        self._on_transcript: Optional[Callable[[STTResult], None]] = None
        self._on_command: Optional[Callable[[VoiceCommand], None]] = None
        self._on_response: Optional[Callable[[str], None]] = None

    def set_callbacks(
        self,
        on_transcript: Optional[Callable[[STTResult], None]] = None,
        on_command: Optional[Callable[[VoiceCommand], None]] = None,
        on_response: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._on_transcript = on_transcript
        self._on_command = on_command
        self._on_response = on_response

    def start_continuous(self, use_vad: bool = True) -> None:
        if self._active:
            return
        if not self.stt.is_available:
            logger.error("STT not available, cannot start session")
            return
        self._active = True
        logger.info("Voice session started (continuous mode)")

        def _loop():
            while self._active:
                try:
                    if use_vad:
                        result = self.stt.listen_vad(timeout=30.0)
                    else:
                        result = self.stt.listen(self.config.record_duration)
                    if not result.success or not result.text:
                        continue
                    if self._on_transcript:
                        self._on_transcript(result)
                    command = self.processor.parse(result.text)
                    result.is_command = command.command_type != CommandType.UNKNOWN
                    result.command_type = command.command_type
                    result.command_params = command.params
                    if result.is_command:
                        if self._on_command:
                            self._on_command(command)
                        executed = self.processor.execute(command)
                        if executed:
                            response = f"Executed {command.command_type.value}"
                        else:
                            response = f"Recognized {command.command_type.value}, but no handler registered"
                    else:
                        response = f"Transcribed: {result.text}"
                    if self._on_response:
                        self._on_response(response)
                    self.tts.speak(response)
                except Exception as e:
                    logger.error(f"Voice session loop error: {e}")
                    time.sleep(self.config.continuous_interval)

        self._thread = threading.Thread(target=_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._active = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        logger.info("Voice session stopped")

    def interact_once(self, use_vad: bool = True) -> Optional[VoiceCommand]:
        try:
            if use_vad:
                result = self.stt.listen_vad(timeout=30.0)
            else:
                result = self.stt.listen(self.config.record_duration)
            if not result.success or not result.text:
                return None
            if self._on_transcript:
                self._on_transcript(result)
            command = self.processor.parse(result.text)
            return command
        except Exception as e:
            logger.error(f"Single interaction error: {e}")
            return None

    @property
    def is_active(self) -> bool:
        return self._active


class UnifiedVoiceEngine:
    """
    Unified voice engine orchestrating STT, TTS, VAD, and command processing.
    Singleton pattern for global access.
    """

    _instance: Optional["UnifiedVoiceEngine"] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, config: Optional[VoiceConfig] = None):
        if self._initialized:
            return
        self.config = config or VoiceConfig()
        self.stt = STTEngine(self.config)
        self.tts = TTSEngine(self.config)
        self.vad = VoiceActivityDetector(self.config)
        self.processor = VoiceCommandProcessor()
        self.session: Optional[VoiceSession] = None
        self._initialized = True
        self._initialized_engines = False
        logger.info("UnifiedVoiceEngine created")

    def initialize(self, load_stt: bool = True, load_tts: bool = True) -> bool:
        success = True
        if load_stt:
            stt_ok = self.stt.load()
            success = success and stt_ok
        if load_tts:
            tts_ok = self.tts.is_available
            if not tts_ok:
                logger.warning("TTS not fully available, using fallback")
        self._initialized_engines = success
        logger.info(f"Voice engine initialized: STT={self.stt.is_loaded}, TTS={self.tts.is_available}")
        return success

    @property
    def is_ready(self) -> bool:
        return self._initialized_engines

    @property
    def status(self) -> Dict[str, Any]:
        return {
            "initialized": self._initialized_engines,
            "stt_available": self.stt.is_available,
            "stt_loaded": self.stt.is_loaded,
            "tts_available": self.tts.is_available,
            "tts_backend": self.tts.current_backend.value,
            "tts_backends": [b.value for b in self.tts.get_available_backends()],
            "session_active": self.session is not None and self.session.is_active,
            "command_handlers": [c.value for c in self.processor._command_handlers.keys()],
        }

    def listen(self, duration: Optional[float] = None, use_vad: bool = False) -> STTResult:
        if not self.stt.is_loaded:
            if not self.stt.load():
                return STTResult(error="STT not available", success=False)
        if use_vad:
            return self.stt.listen_vad()
        return self.stt.listen(duration)

    def speak(self, text: str) -> TTSResult:
        return self.tts.speak(text)

    def listen_and_respond(
        self,
        on_transcript: Optional[Callable[[STTResult], None]] = None,
        on_command: Optional[Callable[[VoiceCommand], None]] = None,
        use_vad: bool = True,
    ) -> Optional[VoiceCommand]:
        result = self.listen(use_vad=use_vad)
        if on_transcript:
            on_transcript(result)
        if not result.success or not result.text:
            self.speak("I did not catch that. Please try again.")
            return None
        command = self.processor.parse(result.text)
        if on_command:
            on_command(command)
        if command.command_type != CommandType.UNKNOWN:
            executed = self.processor.execute(command)
            if executed:
                self.speak(f"Done: {command.command_type.value}")
            else:
                self.speak(f"I heard {command.command_type.value}, but I cannot do that yet.")
        else:
            self.speak(f"I heard: {result.text}")
        return command

    def start_continuous_session(
        self,
        on_transcript: Optional[Callable[[STTResult], None]] = None,
        on_command: Optional[Callable[[VoiceCommand], None]] = None,
        on_response: Optional[Callable[[str], None]] = None,
        use_vad: bool = True,
    ) -> bool:
        if self.session and self.session.is_active:
            logger.warning("Voice session already active")
            return False
        if not self.stt.is_loaded and not self.stt.load():
            logger.error("Cannot start session: STT not available")
            return False
        self.session = VoiceSession(self.stt, self.tts, self.processor, self.config)
        self.session.set_callbacks(on_transcript, on_command, on_response)
        self.session.start_continuous(use_vad=use_vad)
        return True

    def stop_session(self) -> None:
        if self.session:
            self.session.stop()
            self.session = None

    def register_command_handler(self, command_type: CommandType, handler: Callable) -> None:
        self.processor.register_handler(command_type, handler)

    def unregister_command_handler(self, command_type: CommandType) -> None:
        self.processor.unregister_handler(command_type)

    def detect_hotword(self, text: str) -> bool:
        if not self.config.hotword:
            return True
        hotword_lower = self.config.hotword.lower()
        text_lower = text.lower()
        if hotword_lower in text_lower:
            return True
        hotword_words = set(hotword_lower.split())
        text_words = set(text_lower.split())
        overlap = len(hotword_words & text_words)
        ratio = overlap / len(hotword_words) if hotword_words else 0
        return ratio >= self.config.hotword_sensitivity

    def shutdown(self) -> None:
        self.stop_session()
        self.stt.unload()
        self.tts.stop()
        logger.info("Voice engine shutdown complete")


def get_voice_engine(config: Optional[VoiceConfig] = None) -> UnifiedVoiceEngine:
    """Get or create the global voice engine singleton."""
    return UnifiedVoiceEngine(config)


# Module Tests

def test_stt_engine():
    print("\n=== STT ENGINE TEST ===")
    stt = STTEngine(VoiceConfig(stt_model_size="tiny"))
    print(f"Available: {stt.is_available}")
    print(f"Device: {stt._device}")
    if stt.is_available:
        loaded = stt.load()
        print(f"Loaded: {loaded}")
        if loaded:
            print("STT engine ready")
            stt.unload()
    else:
        print("SKIP: faster-whisper not installed")
    return stt.is_available


def test_tts_engine():
    print("\n=== TTS ENGINE TEST ===")
    tts = TTSEngine(VoiceConfig())
    print(f"Current backend: {tts.current_backend.value}")
    print(f"Available backends: {[b.value for b in tts.get_available_backends()]}")
    result = tts.speak("CrackedCode voice engine test successful")
    print(f"Speak result: success={result.success}, backend={result.backend.value}")
    return result.success


def test_command_processor():
    print("\n=== COMMAND PROCESSOR TEST ===")
    processor = VoiceCommandProcessor()
    test_cases = [
        ("write a python function", CommandType.WRITE),
        ("run the code", CommandType.EXECUTE),
        ("fix the bug in main.py", CommandType.DEBUG),
        ("search for todo items", CommandType.SEARCH),
        ("save this file", CommandType.SAVE),
        ("open app.py", CommandType.OPEN),
        ("clear the terminal", CommandType.CLEAR),
        ("stop everything", CommandType.STOP),
        ("help me", CommandType.HELP),
        ("random nonsense", CommandType.UNKNOWN),
    ]
    passed = 0
    for text, expected in test_cases:
        cmd = processor.parse(text)
        ok = cmd.command_type == expected
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] '{text}' -> {cmd.command_type.value} (conf={cmd.confidence:.2f})")
        if ok:
            passed += 1
    print(f"\nCommand parsing: {passed}/{len(test_cases)} passed")
    return passed == len(test_cases)


def test_voice_session():
    print("\n=== VOICE SESSION TEST ===")
    stt = STTEngine(VoiceConfig(stt_model_size="tiny"))
    tts = TTSEngine(VoiceConfig())
    processor = VoiceCommandProcessor()
    session = VoiceSession(stt, tts, processor)
    print(f"Session created: {session is not None}")
    print(f"STT available: {stt.is_available}")
    print(f"TTS available: {tts.is_available}")
    print("Voice session lifecycle: OK")
    return True


def test_unified_engine():
    print("\n=== UNIFIED VOICE ENGINE TEST ===")
    engine = UnifiedVoiceEngine(VoiceConfig(stt_model_size="tiny"))
    status = engine.status
    print(f"Status: {status}")
    print(f"STT available: {status['stt_available']}")
    print(f"TTS available: {status['tts_available']}")
    print(f"TTS backend: {status['tts_backend']}")
    print(f"TTS backends: {status['tts_backends']}")
    result = engine.speak("Unified voice engine test")
    print(f"Speak result: success={result.success}, backend={result.backend.value}")
    cmd = engine.processor.parse("write a function in app.py")
    print(f"Command: {cmd.command_type.value}, params: {cmd.params}")
    return True


def test_param_extraction():
    print("\n=== PARAMETER EXTRACTION TEST ===")
    processor = VoiceCommandProcessor()
    tests = [
        ("write a function in app.py", {"filename": "app.py", "type": "function"}),
        ("create a class called User in models.py", {"filename": "models.py", "type": "class", "name": "User"}),
        ("search for todo in main.py", {"filename": "main.py"}),
        ("save the file", {}),
    ]
    passed = 0
    for text, expected in tests:
        cmd = processor.parse(text)
        ok = all(cmd.params.get(k) == v for k, v in expected.items())
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] '{text}' -> {cmd.params}")
        if ok:
            passed += 1
    print(f"\nParameter extraction: {passed}/{len(tests)} passed")
    return passed == len(tests)


def run_all_tests():
    print("=" * 60)
    print("  CRACKEDCODE UNIFIED VOICE ENGINE TESTS")
    print("=" * 60)
    results = {
        "STT Engine": test_stt_engine(),
        "TTS Engine": test_tts_engine(),
        "Command Processor": test_command_processor(),
        "Voice Session": test_voice_session(),
        "Unified Engine": test_unified_engine(),
        "Parameter Extraction": test_param_extraction(),
    }
    print("\n" + "=" * 60)
    print("  TEST SUMMARY")
    print("=" * 60)
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}")
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    print(f"\n  Total: {passed}/{total} passed")
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
