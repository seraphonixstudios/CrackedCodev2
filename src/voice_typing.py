#!/usr/bin/env python3
"""
Voice typing module for CrackedCode GUI
Uses faster-whisper for speech recognition with sounddevice for audio capture
"""

import io
import wave
import threading
import platform
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass

import numpy as np

try:
    import sounddevice as sd
    import soundfile as sf
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False

try:
    from faster_whisper import WhisperModel
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False

import logging
logger = logging.getLogger("VoiceTyping")

AUDIO_CONFIG = {
    "sample_rate": 16000,
    "channels": 1,
    "dtype": "float32",
    "duration": 5.0,
}


@dataclass
class TranscriptionResult:
    text: str
    language: Optional[str] = "en"
    confidence: float = 0.0
    duration: float = 0.0
    success: bool = True
    error: Optional[str] = None


class VoiceTyping:
    def __init__(
        self,
        model_size: str = "base",
        language: str = "en",
        device: Optional[str] = None,
    ):
        self.model_size = model_size
        self.language = language
        self.device = device or self._detect_device()

        self.model: Optional[WhisperModel] = None
        self.is_recording = False
        self.recording_thread: Optional[threading.Thread] = None
        self.recorded_audio: Optional[np.ndarray] = None

        self._available = AUDIO_AVAILABLE and WHISPER_AVAILABLE
        self._load_model()

    def _detect_device(self) -> str:
        if platform.system() == "Windows":
            try:
                import subprocess
                subprocess.run(
                    ["nvidia-smi"],
                    capture_output=True,
                    check=True
                )
                return "cuda"
            except Exception:
                return "cpu"
        return "cpu"

    def _load_model(self) -> bool:
        if not self._available:
            logger.warning("Voice typing not available - missing dependencies")
            return False

        try:
            compute = "float16" if self.device == "cuda" else "int8"
            self.model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=compute,
            )
            logger.info(f"Whisper model loaded: {self.model_size} ({self.device})")
            return True
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            return False

    @property
    def is_available(self) -> bool:
        return self._available and self.model is not None

    def record(self, duration: float = 5.0) -> np.ndarray:
        if not self.is_available:
            raise RuntimeError("Voice typing not available")

        logger.info(f"Recording for {duration}s...")
        frames = int(duration * AUDIO_CONFIG["sample_rate"])

        try:
            audio = sd.rec(
                frames,
                samplerate=AUDIO_CONFIG["sample_rate"],
                channels=AUDIO_CONFIG["channels"],
                dtype=AUDIO_CONFIG["dtype"],
                device=self.device if self.device != "cuda" else None,
            )
            sd.wait()
            audio = np.squeeze(audio)
            logger.info(f"Recorded {len(audio)} samples")
            return audio
        except Exception as e:
            logger.error(f"Recording failed: {e}")
            raise

    def transcribe(self, audio: np.ndarray) -> TranscriptionResult:
        if not self.is_available:
            return TranscriptionResult(
                text="",
                success=False,
                error="Model not loaded"
            )

        try:
            buffer = io.BytesIO()
            with wave.open(buffer, 'wb') as wf:
                wf.setnchannels(AUDIO_CONFIG["channels"])
                wf.setsampwidth(2)
                wf.setframerate(AUDIO_CONFIG["sample_rate"])
                audio_int16 = (audio * 32767).astype(np.int16)
                wf.writeframes(audio_int16.tobytes())

            buffer.seek(0)

            segments, info = self.model.transcribe(
                buffer,
                language=self.language,
                beam_size=5,
                vad_filter=True,
            )

            text = " ".join(seg.text for seg in segments).strip()

            return TranscriptionResult(
                text=text,
                language=info.language,
                confidence=info.language_probability,
                duration=info.duration,
                success=True,
            )

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return TranscriptionResult(
                text="",
                success=False,
                error=str(e)
            )

    def listen_and_transcribe(self, duration: float = 5.0) -> TranscriptionResult:
        audio = self.record(duration)
        return self.transcribe(audio)

    def start_continuous(
        self,
        callback: Callable[[TranscriptionResult], None],
        duration: float = 3.0,
        silence_threshold: float = 0.01,
        silence_timeout: float = 2.0,
    ):
        if self.is_recording:
            return

        self.is_recording = True
        self._callback = callback

        def recording_loop():
            while self.is_recording:
                try:
                    audio = self.record(duration)
                    result = self.transcribe(audio)

                    if result.text and len(result.text) > 2:
                        logger.info(f"Transcribed: {result.text[:50]}...")
                        self._callback(result)

                except Exception as e:
                    logger.error(f"Continuous recording error: {e}")

        self.recording_thread = threading.Thread(target=recording_loop, daemon=True)
        self.recording_thread.start()

    def stop_continuous(self):
        self.is_recording = False
        if self.recording_thread:
            self.recording_thread.join(timeout=2.0)
            self.recording_thread = None

    def get_devices(self):
        if not AUDIO_AVAILABLE:
            return []

        try:
            devices = sd.query_devices()
            return [
                {"id": i, "name": d["name"], "channels": d["max_input_channels"]}
                for i, d in enumerate(devices)
                if d["max_input_channels"] > 0
            ]
        except Exception as e:
            logger.error(f"Failed to query devices: {e}")
            return []


def test_voice_typing():
    print("=== VOICE TYPING TEST ===\n")

    vt = VoiceTyping(model_size="base")

    if not vt.is_available:
        print("Voice typing not available")
        print("Install with: pip install faster-whisper sounddevice soundfile")
        return False

    print(f"Device: {vt.device}")
    print(f"Available input devices:")
    for dev in vt.get_devices()[:3]:
        print(f"  [{dev['id']}] {dev['name']} ({dev['channels']} ch)")

    print("\nRecording 5 seconds of audio...")
    try:
        result = vt.listen_and_transcribe(duration=5.0)

        if result.success:
            print(f"\nResult: {result.text}")
            print(f"Language: {result.language}")
            print(f"Confidence: {result.confidence:.2%}")
            return True
        else:
            print(f"Error: {result.error}")
            return False

    except Exception as e:
        print(f"Test failed: {e}")
        return False


if __name__ == "__main__":
    test_voice_typing()