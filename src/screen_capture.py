"""Screen Capture and Vision Analysis - AI-powered screen understanding.

Captures screenshots and analyzes them using the vision model (llava:13b-gpu).

Features:
- Full screen capture
- Active window capture
- Region capture
- Vision model analysis (describe, OCR, error detection)
"""

import base64
import io
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass

from src.logger_config import get_logger

try:
    from PIL import ImageGrab, Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

logger = get_logger("ScreenCapture")


@dataclass
class CaptureResult:
    """Result of a screen capture."""
    success: bool
    image_data: bytes = b""
    width: int = 0
    height: int = 0
    format: str = "png"
    error: str = ""
    
    def to_base64(self) -> str:
        """Convert image data to base64 string."""
        return base64.b64encode(self.image_data).decode("utf-8")


class ScreenCapture:
    """Screen capture utility using PIL."""
    
    def __init__(self):
        if not PIL_AVAILABLE:
            logger.warning("PIL not available - screen capture disabled")
    
    def capture_fullscreen(self) -> CaptureResult:
        """Capture the entire screen."""
        if not PIL_AVAILABLE:
            return CaptureResult(success=False, error="PIL not available")
        
        try:
            screenshot = ImageGrab.grab()
            buffer = io.BytesIO()
            screenshot.save(buffer, format="PNG")
            data = buffer.getvalue()
            
            return CaptureResult(
                success=True,
                image_data=data,
                width=screenshot.width,
                height=screenshot.height,
                format="png",
            )
        except Exception as e:
            logger.error(f"Screen capture failed: {e}")
            return CaptureResult(success=False, error=str(e))
    
    def capture_region(self, bbox: tuple) -> CaptureResult:
        """Capture a specific screen region.
        
        Args:
            bbox: (left, top, right, bottom) coordinates
        """
        if not PIL_AVAILABLE:
            return CaptureResult(success=False, error="PIL not available")
        
        try:
            screenshot = ImageGrab.grab(bbox=bbox)
            buffer = io.BytesIO()
            screenshot.save(buffer, format="PNG")
            data = buffer.getvalue()
            
            return CaptureResult(
                success=True,
                image_data=data,
                width=screenshot.width,
                height=screenshot.height,
                format="png",
            )
        except Exception as e:
            logger.error(f"Region capture failed: {e}")
            return CaptureResult(success=False, error=str(e))
    
    def save_capture(self, result: CaptureResult, path: str = "screenshot.png") -> str:
        """Save a capture result to disk."""
        if not result.success:
            return ""
        
        try:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(result.image_data)
            return str(p.resolve())
        except Exception as e:
            logger.error(f"Save capture failed: {e}")
            return ""


class VisionAnalyzer:
    """Analyze screenshots using a vision model."""
    
    def __init__(self, engine=None):
        self.engine = engine
        self.capture = ScreenCapture()
    
    def analyze_screen(self, prompt: str = "Describe what you see on this screen.",
                       save_path: str = None) -> Dict[str, Any]:
        """Capture screen and analyze with vision model.
        
        Args:
            prompt: Question to ask the vision model
            save_path: Optional path to save the screenshot
            
        Returns:
            Dict with success, description, screenshot_path
        """
        # Capture screen
        capture = self.capture.capture_fullscreen()
        if not capture.success:
            return {"success": False, "error": capture.error}
        
        # Optionally save
        screenshot_path = None
        if save_path:
            screenshot_path = self.capture.save_capture(capture, save_path)
        
        # Analyze with vision model
        if not self.engine:
            return {
                "success": True,
                "captured": True,
                "screenshot_path": screenshot_path,
                "width": capture.width,
                "height": capture.height,
                "analysis": "No vision engine available",
            }
        
        try:
            # Use vision model via engine
            vision_model = self.engine.config.get("vision_model", "llava:13b-gpu")
            
            # Build messages with image
            import ollama
            messages = [
                {"role": "user", "content": prompt, "images": [capture.to_base64()]}
            ]
            
            response = ollama.chat(model=vision_model, messages=messages)
            analysis = response.message.content
            
            return {
                "success": True,
                "captured": True,
                "screenshot_path": screenshot_path,
                "width": capture.width,
                "height": capture.height,
                "analysis": analysis,
                "model": vision_model,
            }
        except Exception as e:
            logger.error(f"Vision analysis failed: {e}")
            return {
                "success": False,
                "captured": True,
                "screenshot_path": screenshot_path,
                "error": str(e),
            }
    
    def describe_ui(self) -> Dict[str, Any]:
        """Specialized prompt for UI description."""
        return self.analyze_screen(
            prompt="Describe the UI elements visible on this screen. Identify buttons, text fields, menus, error messages, and any other interactive elements. Be specific about layout and visible text.",
        )
    
    def detect_errors(self) -> Dict[str, Any]:
        """Specialized prompt for error detection."""
        return self.analyze_screen(
            prompt="Look for any error messages, warnings, pop-ups, orå¼‚å¸¸ states on this screen. Report the exact error text and what UI element it appears on.",
        )
    
    def ocr_screen(self) -> Dict[str, Any]:
        """Specialized prompt for OCR."""
        return self.analyze_screen(
            prompt="Extract all visible text from this screen. Preserve the layout and structure as much as possible. Include text from buttons, labels, menus, and any content areas.",
        )


def get_screen_capture() -> ScreenCapture:
    """Get a ScreenCapture instance."""
    return ScreenCapture()


def get_vision_analyzer(engine=None) -> VisionAnalyzer:
    """Get a VisionAnalyzer instance."""
    return VisionAnalyzer(engine)

