#!/usr/bin/env python3
"""
CrackedCode - Local AI Coding Assistant
Version: 2.3.8
"""

import os
import sys
import json
import subprocess
import signal
import threading
import time
import platform
import re
import traceback
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

try:
    from colorama import init, Fore, Style, Back
    init(autoreset=True)
    COLORAMA_AVAILABLE = True
except ImportError:
    COLORAMA_AVAILABLE = False
    class Fore:
        RED = GREEN = YELLOW = BLUE = CYAN = MAGENTA = WHITE = RESET = ""
    class Style:
        BRIGHT = DIM = NORMAL = RESET_ALL = ""
    class Back:
        BLACK = RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = ""

try:
    from faster_whisper import WhisperModel
    import sounddevice as sd
    import numpy as np
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    FASTER_WHISPER_AVAILABLE = False

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False


# ============================================================================
# DEBUG AND LOGGING SYSTEM - NO PLACEHOLDERS
# ============================================================================

DEBUG_MODE = os.environ.get("CRACKEDCODE_DEBUG", "false").lower() in ("true", "1", "yes")
VERBOSE_MODE = os.environ.get("CRACKEDCODE_VERBOSE", "false").lower() in ("true", "1", "yes")

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

LOG_FILE = LOG_DIR / f"crackedcode_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.DEBUG if DEBUG_MODE else logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger('CrackedCode')
logger.setLevel(logging.DEBUG if DEBUG_MODE else logging.INFO)

def log_debug(message: str, exc_info: bool = False):
    if DEBUG_MODE:
        logger.debug(message, exc_info=exc_info)
        if VERBOSE_MODE:
            _print_debug(f"[DEBUG] {message}")

def log_info(message: str):
    logger.info(message)
    _print_info(f"[INFO] {message}")

def log_warning(message: str):
    logger.warning(message)
    _print_warn(f"[WARNING] {message}")

def log_error(message: str, exc_info: bool = True):
    logger.error(message, exc_info=exc_info)
    _print_error(f"[ERROR] {message}")
    if exc_info:
        exc_type, exc_value, exc_tb = sys.exc_info()
        tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb)
        for line in tb_lines:
            for l in line.strip().split('\n'):
                if l:
                    _print_error(f"  {l}")

def log_critical(message: str, exc_info: bool = True):
    logger.critical(message, exc_info=exc_info)
    _print_error(f"[CRITICAL] {message}")
    if exc_info:
        exc_type, exc_value, exc_tb = sys.exc_info()
        tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb)
        for line in tb_lines:
            for l in line.strip().split('\n'):
                if l:
                    _print_error(f"  {l}")

def _print_debug(msg: str):
    if COLORAMA_AVAILABLE:
        print(f"{Fore.CYAN}{msg}{Style.RESET_ALL}")
    else:
        print(f"[DEBUG] {msg}")

def _print_info(msg: str):
    if COLORAMA_AVAILABLE:
        print(f"{Fore.BLUE}{msg}{Style.RESET_ALL}")
    else:
        print(f"{msg}")

def _print_warn(msg: str):
    if COLORAMA_AVAILABLE:
        print(f"{Fore.YELLOW}{msg}{Style.RESET_ALL}")
    else:
        print(f"{msg}")

def _print_error(msg: str):
    if COLORAMA_AVAILABLE:
        print(f"{Fore.RED}{msg}{Style.RESET_ALL}")
    else:
        print(f"{msg}", file=sys.stderr)

def log_agent_action(agent: str, action: str, details: str = ""):
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    msg = f"[{timestamp}] {agent.upper()} | {action}"
    if details:
        msg += f" | {details}"
    logger.info(msg)
    if COLORAMA_AVAILABLE:
        colors = {"supervisor": Fore.CYAN, "architect": Fore.BLUE, "coder": Fore.GREEN, 
                 "executor": Fore.YELLOW, "reviewer": Fore.MAGENTA, "specialist": Fore.WHITE}
        color = colors.get(agent.lower(), Fore.WHITE)
        print(f"{color}{msg}{Style.RESET_ALL}")
    else:
        print(msg)

def log_tool_call(tool: str, args: Dict, result: Any = None, error: str = None):
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    if error:
        msg = f"[{timestamp}] TOOL | {tool}({json.dumps(args)}) -> ERROR: {error}"
        logger.error(msg)
        _print_error(msg)
    elif result:
        result_str = str(result)[:100]
        msg = f"[{timestamp}] TOOL | {tool}({json.dumps(args)}) -> OK: {result_str}..."
        logger.debug(msg)
        if DEBUG_MODE:
            _print_debug(msg)
    else:
        msg = f"[{timestamp}] TOOL | {tool}({json.dumps(args)})"
        logger.debug(msg)
        if DEBUG_MODE:
            _print_debug(msg)

def log_llm_request(model: str, prompt: str, response: str = None, error: str = None, duration: float = None):
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    prompt_preview = prompt[:50] + "..." if len(prompt) > 50 else prompt
    
    if error:
        msg = f"[{timestamp}] LLM | {model} | Prompt: {prompt_preview} | ERROR: {error}"
        logger.error(msg)
        _print_error(msg)
    elif response:
        response_preview = response[:50] + "..." if len(response) > 50 else response
        duration_str = f" ({duration:.2f}s)" if duration else ""
        msg = f"[{timestamp}] LLM | {model} | Prompt: {prompt_preview} | Response: {response_preview}{duration_str}"
        logger.info(msg)
        _print_info(msg)
    else:
        msg = f"[{timestamp}] LLM | {model} | Prompt: {prompt_preview} | ..."
        logger.debug(msg)
        if DEBUG_MODE:
            _print_debug(msg)

def log_voice_event(event: str, details: str = ""):
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    msg = f"[{timestamp}] VOICE | {event}"
    if details:
        msg += f" | {details}"
    logger.info(msg)
    if COLORAMA_AVAILABLE:
        print(f"{Fore.MAGENTA}{msg}{Style.RESET_ALL}")
    else:
        print(msg)

def log_config_loaded(config: Dict):
    if DEBUG_MODE:
        logger.debug(f"Config loaded: {json.dumps(config, indent=2)}")
    safe_config = {k: v for k, v in config.items() if k not in ['api_key', 'password', 'token']}
    logger.info(f"Config keys: {list(safe_config.keys())}")

def log_task_event(task_id: int, agent: str, event: str, details: str = ""):
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    msg = f"[{timestamp}] TASK #{task_id} | {agent} | {event}"
    if details:
        msg += f" | {details}"
    logger.info(msg)
    print(msg)

def log_session_start():
    log_info("=" * 60)
    log_info("CrackedCode Session Started")
    log_info(f"Version: 2.3.8")
    log_info(f"Platform: {platform.system()} {platform.release()}")
    log_info(f"Python: {platform.python_version()}")
    log_info(f"Debug Mode: {DEBUG_MODE}")
    log_info(f"Verbose Mode: {VERBOSE_MODE}")
    log_info(f"Log File: {LOG_FILE}")
    log_info("=" * 60)

def log_session_end():
    log_info("=" * 60)
    log_info("CrackedCode Session Ended")
    log_info("=" * 60)

def log_exception_with_context(context: str, exc_type: type, exc_value: Exception, tb):
    log_error("=" * 60)
    log_error(f"EXCEPTION IN: {context}")
    log_error(f"Type: {exc_type.__name__}")
    log_error(f"Message: {str(exc_value)}")
    log_error("Traceback:")
    tb_str = "".join(traceback.format_exception(exc_type, exc_value, tb))
    for line in tb_str.split('\n'):
        if line.strip():
            log_error(f"  {line}")
    log_error("=" * 60)

def debug_print_state(state: Dict):
    if DEBUG_MODE and VERBOSE_MODE:
        log_debug("Current State:")
        for key, value in state.items():
            log_debug(f"  {key}: {value}")

def debug_print_memory():
    if DEBUG_MODE:
        log_debug("Memory Dump:")
        log_debug(f"  BLACKBOARD.FILES count: {len(BLACKBOARD.FILES)}")
        log_debug(f"  BLACKBOARD.PLAN length: {len(BLACKBOARD.PLAN)}")
        log_debug(f"  BLACKBOARD.DEBATE_LOG length: {len(BLACKBOARD.DEBATE_LOG)}")
        log_debug(f"  BLACKBOARD.TASK_HISTORY length: {len(BLACKBOARD.TASK_HISTORY)}")

def log_heartbeat(agent: str = "system"):
    if DEBUG_MODE:
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"{Fore.CYAN}{timestamp} {agent.upper()} heartbeat{Style.RESET_ALL}")


# ============================================================================
# VISION AND IMAGE PROCESSING SYSTEM
# ============================================================================

class VisionCapability(Enum):
    NONE = "none"
    BASIC = "basic"
    ADVANCED = "advanced"
    OCR = "ocr"


class ImageFormat(Enum):
    JPEG = "jpeg"
    PNG = "png"
    GIF = "gif"
    BMP = "bmp"
    WEBP = "webp"
    UNKNOWN = "unknown"


@dataclass  
class ImageAnalysis:
    format: str
    width: int
    height: int
    channels: int
    size_bytes: int
    mode: str
    has_transparency: bool
    color_histogram: Dict = field(default_factory=dict)
    dominant_colors: List[Tuple[int, int, int]] = field(default_factory=list)


@dataclass
class OcrResult:
    text: str
    confidence: float
    language: str
    bounding_boxes: List[Dict] = field(default_factory=list)


class VisionEngine:
    SUPPORTED_FORMATS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.tif'}
    MAX_IMAGE_SIZE = 10 * 1024 * 1024
    
    def __init__(self, model: str = "llama3.2-vision:11b"):
        self.model = model
        self.capability = VisionCapability.NONE
        self.pil_available = False
        self.cv2_available = False
        self.pytesseract_available = False
        
        self._check_dependencies()
        self._check_ollama_vision()
        
    def _check_dependencies(self):
        try:
            from PIL import Image
            self.pil_available = True
            log_info("PIL (Pillow) available for image processing")
        except ImportError:
            log_warning("PIL not installed. Install: pip install pillow")
            
        try:
            import cv2
            self.cv2_available = True
            log_info("OpenCV available for advanced image processing")
        except ImportError:
            log_warning("OpenCV not installed. Install: pip install opencv-python")
            
        try:
            import pytesseract
            self.pytesseract_available = True
            log_info("Tesseract OCR available for text extraction")
        except ImportError:
            log_warning("Tesseract not installed for OCR. Install pytesseract and tesseract binary")
            
    def _check_ollama_vision(self):
        if not OLLAMA_AVAILABLE:
            log_error("Ollama not available. Cannot use vision model.")
            return
            
        try:
            response = ollama.list()
            available_models = [m['name'] for m in response.get('models', [])]
            
            if self.model in available_models:
                self.capability = VisionCapability.ADVANCED
                log_info(f"Vision model {self.model} is available")
            else:
                for m in available_models:
                    if 'vision' in m.lower() or 'llama3' in m.lower():
                        self.model = m
                        self.capability = VisionCapability.ADVANCED
                        log_info(f"Using vision model: {self.model}")
                        break
                else:
                    log_warning(f"No vision model found. Models available: {available_models}")
                    log_warning("Pull vision model: ollama pull llama3.2-vision:11b")
        except Exception as e:
            log_error(f"Failed to check vision models: {e}")
            
    def is_ready(self) -> bool:
        return self.capability != VisionCapability.NONE
        
    def get_capability(self) -> str:
        return self.capability.value
        
    def analyze_image(self, image_path: str) -> Optional[ImageAnalysis]:
        from PIL import Image
        import io
        
        path = Path(image_path)
        
        if not path.exists():
            log_error(f"Image file not found: {image_path}")
            return None
            
        if path.suffix.lower() not in self.SUPPORTED_FORMATS:
            log_warning(f"Unsupported image format: {path.suffix}")
            return None
            
        if path.stat().st_size > self.MAX_IMAGE_SIZE:
            log_error(f"Image too large: {path.stat().st_size} > {self.MAX_IMAGE_SIZE}")
            return None
            
        try:
            with Image.open(path) as img:
                analysis = ImageAnalysis(
                    format=img.format or "unknown",
                    width=img.width,
                    height=img.height,
                    channels=len(img.getbands()),
                    size_bytes=path.stat().st_size,
                    mode=img.mode,
                    has_transparency=img.mode in ('RGBA', 'LA') or 'transparency' in img.info
                )
                
                if img.mode == 'RGB' and img.width < 500 and img.height < 500:
                    img_resized = img.resize((100, 100))
                    colors = img_resized.getcolors(maxcolors=101)
                    if colors:
                        analysis.dominant_colors = sorted(colors, reverse=True)[:5]
                        
                log_info(f"Image analyzed: {img.width}x{img.height} {img.format} {analysis.size_bytes} bytes")
                return analysis
                
        except Exception as e:
            log_error(f"Failed to analyze image: {e}", exc_info=True)
            return None
            
    def process_image_for_vision(self, image_path: str) -> Optional[bytes]:
        from PIL import Image
        import io
        
        path = Path(image_path)
        
        if not path.exists():
            log_error(f"Image not found: {image_path}")
            return None
            
        try:
            with Image.open(path) as img:
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                    
                max_size = 1128
                if img.width > max_size or img.height > max_size:
                    ratio = min(max_size / img.width, max_size / img.height)
                    new_size = (int(img.width * ratio), int(img.height * ratio))
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                    
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG', quality=85)
                image_bytes = buffer.getvalue()
                
                log_debug(f"Image processed: {len(image_bytes)} bytes")
                return image_bytes
                
        except Exception as e:
            log_error(f"Failed to process image: {e}", exc_info=True)
            return None
            
    def describe_image(self, image_path: str, prompt: str = "Describe this image in detail.") -> Optional[str]:
        if not self.is_ready():
            log_error("Vision model not ready")
            return None
            
        image_bytes = self.process_image_for_vision(image_path)
        if not image_bytes:
            return None
            
        try:
            start_time = time.time()
            
            response = ollama.chat(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                        "images": [image_bytes]
                    }
                ]
            )
            
            duration = time.time() - start_time
            description = response['message']['content']
            
            log_llm_request(self.model, prompt, description, None, duration)
            log_info(f"Image description generated: {len(description)} chars")
            return description
            
        except Exception as e:
            log_error(f"Failed to describe image: {e}", exc_info=True)
            return None
            
    def extract_text(self, image_path: str, lang: str = "eng") -> Optional[OcrResult]:
        if not self.pytesseract_available:
            log_error("Tesseract OCR not available")
            return None
            
        import pytesseract
        from PIL import Image
        
        path = Path(image_path)
        
        if not path.exists():
            log_error(f"Image not found: {image_path}")
            return None
            
        try:
            with Image.open(path) as img:
                if img.mode != 'L':
                    img = img.convert('L')
                    
                text = pytesseract.image_to_string(img, lang=lang)
                confidence = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
                
                avg_confidence = sum(confidence['conf']) / len([c for c in confidence['conf'] if c > 0]) if confidence['conf'] else 0
                
                result = OcrResult(
                    text=text.strip(),
                    confidence=avg_confidence / 100.0,
                    language=lang,
                    bounding_boxes=[
                        {
                            "text": confidence['text'][i],
                            "left": confidence['left'][i],
                            "top": confidence['top'][i],
                            "width": confidence['width'][i],
                            "height": confidence['height'][i],
                            "conf": confidence['conf'][i]
                        }
                        for i in range(len(confidence['text']))
                        if confidence['text'][i].strip()
                    ]
                )
                
                log_info(f"OCR extracted: {len(result.text)} chars, confidence: {avg_confidence:.1f}%")
                return result
                
        except Exception as e:
            log_error(f"OCR failed: {e}", exc_info=True)
            return None
            
    def compare_images(self, image_path1: str, image_path2: str) -> Optional[Dict]:
        if not self.cv2_available:
            log_error("OpenCV not available for image comparison")
            return None
            
        import cv2
        import numpy as np
        
        path1 = Path(image_path1)
        path2 = Path(image_path2)
        
        if not path1.exists() or not path2.exists():
            log_error("One or both images not found")
            return None
            
        try:
            img1 = cv2.imread(str(path1))
            img2 = cv2.imread(str(path2))
            
            if img1 is None or img2 is None:
                log_error("Failed to load images")
                return None
                
            if img1.shape != img2.shape:
                img2 = cv2.resize(img2, (img1.shape[1], img1.shape[0]))
                
            diff = cv2.absdiff(img1, img2)
            gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
            
            diff_ratio = np.sum(thresh) / thresh.size
            similarity = 1.0 - diff_ratio
            
            histogram1 = cv2.calcHist([img1], [0], None, [256], [0, 256])
            histogram2 = cv2.calcHist([img2], [0], None, [256], [0, 256])
            
            histogram_similarity = cv2.compareHist(histogram1, histogram2, cv2.HISTCMP_CORREL)
            
            result = {
                "pixel_similarity": float(similarity),
                "histogram_similarity": float(histogram_similarity),
                "overall_similarity": float((similarity + histogram_similarity) / 2),
                "difference_pixels": int(np.sum(thresh) / 255)
            }
            
            log_info(f"Images compared: {result['overall_similarity']:.2%} similar")
            return result
            
        except Exception as e:
            log_error(f"Image comparison failed: {e}", exc_info=True)
            return None


class Intent(Enum):
    ASK = "ask"
    CREATE = "create"
    MODIFY = "modify"
    DEBUG = "debug"
    EXPLAIN = "explain"
    EXECUTE = "execute"
    REVIEW = "review"
    SEARCH = "search"
    HELP = "help"
    CHAT = "chat"
    UNKNOWN = "unknown"


class PromptStyle(Enum):
    CONCISE = "concise"
    DETAILED = "detailed"
    TECHNICAL = "technical"
    FRIENDLY = "friendly"
    EXPERT = "expert"


class ConversationTurn:
    def __init__(self, user_input: str, intent: Intent, entities: List[str], 
                 context_needed: bool, user_level: str):
        self.user_input = user_input
        self.intent = intent
        self.entities = entities
        self.context_needed = context_needed
        self.user_level = user_level
        self.timestamp = datetime.now()


class EntityTracker:
    def __init__(self):
        self.entities: Dict[str, Dict] = {}
        
    def add_entity(self, name: str, entity_type: str, value: Any, confidence: float = 1.0):
        self.entities[name] = {
            "type": entity_type,
            "value": value,
            "confidence": confidence,
            "last_mentioned": datetime.now()
        }
        
    def get_entity(self, name: str) -> Optional[Any]:
        return self.entities.get(name, {}).get("value")
        
    def find_entities(self, entity_type: str) -> List[Dict]:
        return [e for e in self.entities.values() if e.get("type") == entity_type]
        
    def resolve_pronouns(self, text: str) -> str:
        text = text.replace("it", "the code")
        text = text.replace("that", "the previous result")
        text = text.replace("this", "current context")
        return text


class NaturalPromptEngine:
    def __init__(self):
        self.history: List[Dict] = []
        self.entities = EntityTracker()
        self.current_style = PromptStyle.TECHNICAL
        self.user_level = "intermediate"
        self.max_history = 100
        self.conversation_flow: List[str] = []
        self.last_topic = ""
        self.pending_confirmations: List[str] = []
        
    def detect_intent(self, user_input: str) -> Intent:
        input_lower = user_input.lower()
        
        create_keywords = ["write", "create", "make", "build", "implement", "add", "new"]
        debug_keywords = ["fix", "bug", "error", "issue", "broken", "not working", "crash"]
        explain_keywords = ["what", "how", "why", "explain", "tell me", "describe"]
        modify_keywords = ["change", "update", "modify", "edit", "refactor", "improve"]
        search_keywords = ["find", "search", "look", "where", "grep", "locate"]
        review_keywords = ["review", "check", "analyze", "critique", "audit"]
        execute_keywords = ["run", "execute", "test", "build", "deploy", "start"]
        
        for kw in debug_keywords:
            if kw in input_lower:
                return Intent.DEBUG
        for kw in create_keywords:
            if kw in input_lower:
                return Intent.CREATE
        for kw in explain_keywords:
            if kw in input_lower:
                return Intent.EXPLAIN
        for kw in modify_keywords:
            if kw in input_lower:
                return Intent.MODIFY
        for kw in search_keywords:
            if kw in input_lower:
                return Intent.SEARCH
        for kw in review_keywords:
            if kw in input_lower:
                return Intent.REVIEW
        for kw in execute_keywords:
            if kw in input_lower:
                return Intent.EXECUTE
            
        if "?" in user_input or "help" in input_lower:
            return Intent.HELP
            
        return Intent.CHAT
        
    def extract_entities(self, user_input: str) -> List[str]:
        import re
        
        file_pattern = r'\b[\w/]+\.\w+\b'
        func_pattern = r'\bdef\s+(\w+)|class\s+(\w+)'
        api_pattern = r'\bAPI|API|api\b'
        
        entities = []
        
        entities.extend(re.findall(file_pattern, user_input))
        
        entities.extend(re.findall(r'def\s+(\w+)', user_input))
        entities.extend(re.findall(r'class\s+(\w+)', user_input))
        
        if "API" in user_input.upper():
            entities.append("API")
            
        return [e for e in entities if e]
        
    def determine_user_level(self, user_input: str) -> str:
        simple_keywords = ["simple", "basic", "easy", "beginner", "hello", "hi"]
        expert_keywords = ["optimize", "performance", "architecture", "pattern", "advanced", "security"]
        
        if any(kw in user_input.lower() for kw in simple_keywords):
            return "beginner"
        elif any(kw in user_input.lower() for kw in expert_keywords):
            return "expert"
        return "intermediate"
        
    def build_context_window(self, max_turns: int = 10) -> str:
        if not self.history:
            return ""
            
        turns = self.history[-max_turns:]
        context_parts = []
        
        for i, turn in enumerate(turns):
            role_emoji = "👤" if turn["role"] == "user" else "🤖"
            content = turn["content"]
            
            if len(content) > 150:
                content = content[:150] + "..."
                
            context_parts.append(f"{role_emoji} {content}")
            
            if turn.get("intent"):
                context_parts.append(f"  └─ Intent: {turn['intent']}")
            
        return "\n".join(context_parts)
        
    def generate_system_prompt(self, intent: Intent, context: str = "") -> str:
        style_guides = {
            PromptStyle.CONCISE: "Keep responses brief and direct. Show only essential code.",
            PromptStyle.DETAILED: "Be thorough. Explain the why behind the what.",
            PromptStyle.TECHNICAL: "Use precise technical terms. Include edge cases.",
            PromptStyle.FRIENDLY: "Be warm and approachable. Use analogies.",
            PromptStyle.EXPERT: "Optimize for performance. Assume deep knowledge."
        }
        
        intent_guides = {
            Intent.CREATE: "Write complete, working code. Include imports and error handling.",
            Intent.DEBUG: "Identify root cause. Show debugging steps. Consider edge cases.",
            Intent.EXPLAIN: "Use clear examples. Build understanding incrementally.",
            Intent.MODIFY: "Show before and after. Explain trade-offs.",
            Intent.REVIEW: "Be constructive. Provide specific improvements.",
            Intent.EXECUTE: "Validate command is safe. Report all output.",
        }
        
        prompt = f"You are a skilled coding assistant. "
        prompt += style_guides.get(self.current_style, "")
        prompt += "\n"
        prompt += intent_guides.get(intent, "")
        
        if context:
            prompt += f"\n\nRecent context:\n{context}"
            
        if self.entities.entities:
            prompt += f"\n\nTracked entities: {list(self.entities.entities.keys())}"
            
        if self.last_topic:
            prompt += f"\nCurrent topic: {self.last_topic}"
            
        return prompt
        
    def enrich_user_input(self, user_input: str) -> str:
        resolved = self.entities.resolve_pronouns(user_input)
        
        self.last_topic = resolved[:50]
        
        return resolved
        
    def generate_response(self, response: str, intent: Intent, style: PromptStyle = None) -> str:
        if style is None:
            style = self.current_style
            
        prefixes = {
            Intent.CREATE: "Here's the code:\n",
            Intent.DEBUG: "Found the issue:\n",
            Intent.EXPLAIN: "Here's the breakdown:\n",
            Intent.MODIFY: "Here are the changes:\n",
            Intent.REVIEW: "Looking at your code:\n",
            Intent.EXECUTE: "Running that now...\n",
            Intent.HELP: "Let me help you with that:\n",
            Intent.CHAT: "",
        }
        
        prefix = prefixes.get(intent, "")
        
        if style == PromptStyle.CONCISE:
            return prefix + response.split('\n')[0]
        
        return prefix + response
        
    def should_confirm(self, user_input: str) -> bool:
        dangerous_keywords = ["delete", "remove", "drop", "rm", "format", "destroy"]
        
        if any(kw in user_input.lower() for kw in dangerous_keywords):
            return True
            
        confirm_needed = ["reboot", "restart", "kill", "stop"]
        
        return any(kw in user_input.lower() for kw in confirm_needed)
        
    def add_to_history(self, role: str, user_input: str, response: str, 
                    intent: Intent = Intent.CHAT, tokens: int = 0):
        turn = {
            "role": role,
            "user_input": user_input,
            "response": response,
            "intent": intent.value,
            "tokens": tokens,
            "timestamp": datetime.now().isoformat(),
            "entities": self.entities.entities.copy()
        }
        
        self.history.append(turn)
        
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
            
    def summarize_conversation(self) -> str:
        if not self.history:
            return "No conversation history."
            
        intents = [t.get("intent", "unknown") for t in self.history]
        unique_intents = set(intents)
        
        summary = f"Conversation Summary:\n"
        summary += f"  Turns: {len(self.history)}\n"
        summary += f"  Intents: {', '.join(unique_intents)}\n"
        summary += f"  Entities: {list(self.entities.entities.keys())}\n"
        
        return summary
        
    def get_conversation_stats(self) -> Dict:
        if not self.history:
            return {"turns": 0, "intents": {}, "entities": 0}
            
        intents = {}
        for t in self.history:
            i = t.get("intent", "unknown")
            intents[i] = intents.get(i, 0) + 1
            
        return {
            "turns": len(self.history),
            "intents": intents,
            "entities": len(self.entities.entities),
            "style": self.current_style.value
        }


class NaturalTextPromptEngine:
    def __init__(self):
        self.nlp = NaturalPromptEngine()
        self.active = True
        
    def process(self, user_input: str) -> Dict:
        intent = self.nlp.detect_intent(user_input)
        entities = self.nlp.extract_entities(user_input)
        
        for entity in entities:
            self.nlp.entities.add_entity(entity, "extracted", entity, 0.8)
        
        resolved_input = self.nlp.enrich_user_input(user_input)
        
        context = self.nlp.build_context_window()
        
        system_prompt = self.nlp.generate_system_prompt(intent, context)
        
        return {
            "original_input": user_input,
            "resolved_input": resolved_input,
            "intent": intent.value,
            "entities": entities,
            "context": context,
            "system_prompt": system_prompt
        }
        
    def process_response(self, user_input: str, response: str):
        intent = self.nlp.detect_intent(user_input)
        
        self.nlp.add_to_history("user", user_input, response, intent)
        
    def set_style(self, style: PromptStyle):
        self.nlp.current_style = style
        
    def get_stats(self) -> Dict:
        return self.nlp.get_conversation_stats()
        
    def summarize(self) -> str:
        return self.nlp.summarize_conversation()


natural_prompt_engine = None


def init_natural_prompt_engine() -> NaturalTextPromptEngine:
    global natural_prompt_engine
    natural_prompt_engine = NaturalTextPromptEngine()
    log_info("Natural prompt engine initialized")
    return natural_prompt_engine


vision_engine = None
text_prompt_engine = None
natural_prompt_engine = None


def init_engines():
    global vision_engine, text_prompt_engine, natural_prompt_engine
    
    log_info("Initializing prompt engines...")
    
    vision_engine = VisionEngine()
    text_prompt_engine = NaturalPromptEngine()
    natural_prompt_engine = NaturalTextPromptEngine()
    
    if vision_engine.is_ready():
        log_info(f"Vision engine ready: {vision_engine.get_capability()} mode")
    else:
        log_warning("Vision engine not ready - no vision model")
        
    log_info("Text prompt engine ready")
    log_info("Natural prompt engine ready")
    
    return vision_engine, text_prompt_engine, natural_prompt_engine


@dataclass
class AgentThought:
    agent: str
    step: str
    reasoning: str
    timestamp: datetime = field(default_factory=datetime.now)
    confidence: float = 0.0
    context: Dict = field(default_factory=dict)


class EnhancedInterface:
    """Enhanced CLI with thought process visualization"""
    
    COLORS = {
        'supervisor': Fore.CYAN,
        'architect': Fore.BLUE,
        'coder': Fore.GREEN,
        'executor': Fore.YELLOW,
        'reviewer': Fore.MAGENTA,
        'system': Fore.WHITE,
        'error': Fore.RED,
        'success': Fore.GREEN,
        'warning': Fore.YELLOW,
        'info': Fore.BLUE,
    }
    
    THOUGHT_ICONS = {
        'analyzing': '🔍',
        'planning': '📋',
        'designing': '🏗️',
        'writing': '✍️',
        'executing': '⚡',
        'reviewing': '🔎',
        'thinking': '💭',
        'reasoning': '🧠',
        'debating': '⚖️',
        'learning': '📚',
    }
    
    @staticmethod
    def color(text: str, color: str) -> str:
        return f"{color}{text}{Style.RESET_ALL}" if COLORAMA_AVAILABLE else text
    
    @staticmethod
    def bold(text: str) -> str:
        return f"{Style.BRIGHT}{text}{Style.RESET_ALL}" if COLORAMA_AVAILABLE else text
    
    @staticmethod
    def dim(text: str) -> str:
        return f"{Style.DIM}{text}{Style.RESET_ALL}" if COLORAMA_AVAILABLE else text
    
    def print_agent_thought(self, thought: AgentThought):
        agent_color = self.COLORS.get(thought.agent, Fore.WHITE)
        icon = self.THOUGHT_ICONS.get(thought.step, '💭')
        
        ts = thought.timestamp.strftime("%H:%M:%S")
        header = f"{icon} [{ts}] {agent_color}{thought.agent.upper()}{Style.RESET_ALL}"
        
        print(f"\n{self.bold(header)}")
        print(f"  └─ {self.dim('Step:')} {thought.step}")
        print(f"  └─ {self.dim('Reasoning:')} {thought.reasoning[:200]}")
        
        if thought.confidence > 0:
            bar_len = int(thought.confidence * 10)
            bar = '█' * bar_len + '░' * (10 - bar_len)
            print(f"  └─ {self.dim('Confidence:')} [{agent_color}{bar}{Style.RESET_ALL}] {thought.confidence:.0%}")
    
    def print_thinking(self, agent: str, message: str):
        agent_color = self.COLORS.get(agent, Fore.WHITE)
        icon = self.THOUGHT_ICONS['thinking']
        
        print(f"\n{icon} {agent_color}{agent.upper()}{Style.RESET_ALL}")
        print(f"  {self.dim('Thinking...')} {message}")
        
        for i in range(3):
            time.sleep(0.3)
            dots = '.' * (i + 1)
            print(f"  {self.dim('Processing')} {dots:3s}", end='\r')
        print()
    
    def print_reasoning_chain(self, agent: str, chain: List[str]):
        agent_color = self.COLORS.get(agent, Fore.WHITE)
        icon = self.THOUGHT_ICONS['reasoning']
        
        print(f"\n{self.bold(f'{icon} {agent.upper()} - Reasoning Chain')}")
        print(f"  {self.dim('─' * 40)}")
        
        for i, step in enumerate(chain, 1):
            print(f"  {agent_color}{i}.{Style.RESET_ALL} {step}")
        
        print(f"  {self.dim('─' * 40)}")
    
    def print_agent_state(self, agent: str, state: str, details: str = ""):
        agent_color = self.COLORS.get(agent, Fore.WHITE)
        
        if state == "active":
            state_text = self.color(f"● {agent.upper()}", agent_color)
            anim = ['│', '▌', '▀', '▐']
            for frame in anim:
                print(f"\r{self.color(frame, agent_color)} {state_text}", end='\r')
                time.sleep(0.1)
            print(f"\r  {state_text}")
        elif state == "thinking":
            print(f"\n💭 {agent_color}{agent.upper()}{Style.RESET_ALL} thinking...")
        elif state == "complete":
            print(f"\n✓ {agent_color}{agent.upper()}{Style.RESET_ALL} complete")
        elif state == "error":
            print(f"\n✗ {self.COLORS['error']}{agent.upper()}{Style.RESET_ALL} error: {details}")
    
    def print_conversation_turn(self, role: str, message: str, context: str = ""):
        if role == "user":
            print(f"\n{self.bold('👤 You:')} {message}")
        elif role == "assistant":
            icon = '🤖'
            print(f"\n{self.bold(f'{icon} CrackedCode:')} {message}")
        
        if context:
            print(f"  {self.dim(f'Context: {context}')}")
    
    def print_status_bar(self, task_id: int, agent: str, progress: float):
        agent_color = self.COLORS.get(agent, Fore.WHITE)
        bar_width = 30
        filled = int(bar_width * progress)
        bar = '█' * filled + '░' * (bar_width - filled)
        
        print(f"\r  {agent_color}{agent.upper()}{Style.RESET_ALL}: [{agent_color}{bar}{Style.RESET_ALL}] {int(progress * 100)}%", end='', flush=True)
    
    def print_debate_visual(self, round_num: int, coder_claim: str, reviewer_critique: str, consensus: float):
        print(f"\n{self.bold('⚖️  Debate Round')} #{round_num}")
        print(f"  {self.dim('─' * 50)}")
        print(f"  {self.COLORS['coder']}Coder:{Style.RESET_ALL} {coder_claim[:80]}...")
        print(f"  {self.COLORS['reviewer']}Reviewer:{Style.RESET_ALL} {reviewer_critique[:80]}...")
        
        bar_width = 20
        filled = int(bar_width * consensus)
        bar = '█' * filled + '░' * (bar_width - filled)
        print(f"  {self.bold('Consensus:')} [{self.COLORS['success']}{bar}{Style.RESET_ALL}] {consensus:.0%}")
        print(f"  {self.dim('─' * 50)}")
    
    def print_banner(self, version: str):
        banner = f"""
{self.bold(self.color('╔' + '═' * 68 + '╗', Fore.CYAN))}
{self.bold(self.color('║', Fore.CYAN))}                                                                              {self.bold(self.color('║', Fore.CYAN))}
{self.bold(self.color('║', Fore.CYAN))}   █████╗  ██████╗  ██████╗ ████████╗    ██████╗  ██╗     ██╗ ██████╗ ██████╗  █████╗   {self.bold(self.color('║', Fore.CYAN))}
{self.bold(self.color('║', Fore.CYAN))}  ██╔══██╗██╔═══██╗██╔═══██╗╚══██╔══╝    ██╔══██╗ ██║     ██║██╔════╝ ██╔══██╗██╔══██╗   {self.bold(self.color('║', Fore.CYAN))}
{self.bold(self.color('║', Fore.CYAN))}  ███████║██║   ██║██║   ██║   ██║       ██████╔╝ ██║     ██║██║  ███╗██████╔╝███████║   {self.bold(self.color('║', Fore.CYAN))}
{self.bold(self.color('║', Fore.CYAN))}  ██╔══██║██║   ██║██║   ██║   ██║       ██╔══██╗ ██║     ██║██║   ██║██╔══██╗██╔══██║   {self.bold(self.color('║', Fore.CYAN))}
{self.bold(self.color('║', Fore.CYAN))}  ██║  ██║╚██████╔╝╚██████╔╝   ██║       ██║  ██║ ███████╗██║██║   ██║██║  ██║██║  ██║   {self.bold(self.color('║', Fore.CYAN))}
{self.bold(self.color('║', Fore.CYAN))}  ╚═╝  ╚═╝ ╚═════╝  ╚═════╝    ╚═╝       ╚═╝  ╚═╝ ╚══════╝╚═╝╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝   {self.bold(self.color('║', Fore.CYAN))}
{self.bold(self.color('║', Fore.CYAN))}                                                                              {self.bold(self.color('║', Fore.CYAN))}
{self.bold(self.color('║', Fore.CYAN))}              {self.bold(self.color('CrackedCode', Fore.GREEN))} {self.bold(self.color('Enhanced Interface', Fore.WHITE))}                                   {self.bold(self.color('║', Fore.CYAN))}
{self.bold(self.color('║', Fore.CYAN))}         {self.bold(self.color('SOTA Local Multi-Agent Coding Swarm', Fore.YELLOW))}                    {self.bold(self.color('║', Fore.CYAN))}
{self.bold(self.color('╚' + '═' * 68 + '╝', Fore.CYAN))}

{self.dim(f'Version: {version}')} | {self.dim('Platform: ' + platform.system())} | {self.dim('Python: ' + platform.python_version())}
"""
        print(banner)
    
    def print_help(self):
        help_text = f"""
{self.bold('📖 Commands:')}
  {self.COLORS['supervisor']}• 'architect X'{Style.RESET_ALL}     → Design system architecture
  {self.COLORS['coder']}• 'write code for X'{Style.RESET_ALL}   → Generate production code
  {self.COLORS['executor']}• 'run X'{Style.RESET_ALL}           → Execute shell commands
  {self.COLORS['reviewer']}• 'review X'{Style.RESET_ALL}        → Critique code
  {self.COLORS['system']}• 'show blackboard'{Style.RESET_ALL} → View swarm memory
  {self.COLORS['system']}• 'show history'{Style.RESET_ALL}   → View task history
  {self.COLORS['system']}• 'show thinking'{Style.RESET_ALL}  → View reasoning chain
  {self.dim('• exit/quit')}               → Quit

{self.bold('🎛️  Hotkeys:')}
  {self.dim('Ctrl+C')}  → Interrupt current task
  {self.dim('Ctrl+L')}  → Clear screen
  {self.dim('Ctrl+H')}  → Show help
"""
        print(help_text)


interface = EnhancedInterface()


class AgentType(Enum):
    SUPERVISOR = "supervisor"
    ARCHITECT = "architect"
    CODER = "coder"
    EXECUTOR = "executor"
    REVIEWER = "reviewer"
    SPECIALIST = "specialist"


@dataclass
class Task:
    id: int
    agent: str
    description: str
    status: str = "pending"
    result: Optional[Dict] = None
    error: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None

    @property
    def duration(self) -> float:
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0.0


@dataclass
class AgentResponse:
    action: str
    reasoning: str = ""
    data: Dict = field(default_factory=dict)
    success: bool = True
    error: Optional[str] = None


class BLACKBOARD:
    PROJECT_CONTEXT = ""
    FILES = {}
    PLAN = []
    DEBATE_LOG = []
    CONSENSUS = {}
    AGENT_MEMORY = {}
    TASK_HISTORY = []


class CrackedCodeConfig:
    DEFAULT_CONFIG = {
        "model": "qwen3:8b-gpu",
        "whisper_size": "medium.en",
        "tts_voice": "en_US-lessac-medium",
        "sample_rate": 16000,
        "push_to_talk": False,
        "max_concurrent_agents": 4,
        "task_timeout": 120,
        "ollama_host": "http://localhost:11434",
        "allowed_shell_commands": [
            "git", "npm", "node", "python", "python3", "pip", "pip3",
            "ruff", "mypy", "pytest", "cargo", "go", "curl", "wget",
            "ls", "dir", "cd", "mkdir", "rm", "cp", "mv", "cat", "type",
            "find", "grep", "rg", "echo"
        ],
        "project_root": str(Path.cwd()),
        "log_level": "INFO",
        "voice_enabled": True,
        "auto_save_blackboard": True,
        "debate_rounds": 3,
        "max_retries": 2,
        "temperature": 0.1,
        "num_ctx": 16384,
    }

    def __init__(self, config_path: Optional[str] = None):
        self.config = self.DEFAULT_CONFIG.copy()
        if config_path and Path(config_path).exists():
            self.load(config_path)

    def load(self, config_path: str):
        try:
            with open(config_path, 'r') as f:
                user_config = json.load(f)
                self.config.update(user_config)
                logger.info(f"Loaded config from {config_path}")
        except Exception as e:
            logger.warning(f"Failed to load config: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

    def set(self, key: str, value: Any):
        self.config[key] = value

    def save(self, config_path: str):
        with open(config_path, 'w') as f:
            json.dump(self.config, f, indent=2)
        logger.info(f"Saved config to {config_path}")


AGENT_SYSTEM_PROMPTS = {
    AgentType.SUPERVISOR.value: """You are the Supervisor Agent - the orchestrator of the CrackedCode Multi-Agent Swarm.

Your role:
- Analyze complex coding tasks and break them into structured subtask plans
- Assign appropriate agents (Architect, Coder, Executor, Reviewer, Specialist) to each subtask
- Ensure proper task dependency ordering
- Coordinate inter-agent communication via the BLACKBOARD
- Makefinal decision when consensus is reached

Output format - MUST be valid JSON:
{
  "plan": [
    {
      "id": 1,
      "agent": "architect|coder|executor|reviewer|specialist",
      "description": "detailed task description",
      "priority": "high|medium|low",
      "depends_on": []  // array of task IDs this depends on
    }
  ],
  "reasoning": "your analysis and task breakdown reasoning"
}

Guidelines:
- Break complex tasks into 3-7 manageable subtasks
- Assign "coder" for code generation
- Assign "architect" for system design
- Assign "executor" for running commands
- Assign "reviewer" for code critique
- Consider task dependencies for ordering
- Output ONLY valid JSON, no additional text""",

    AgentType.ARCHITECT.value: """You are the Architect Agent - the system design specialist.

Your role:
- Design SOTA system architecture using modern patterns (2026 best practices)
- Create Mermaid diagrams for visual representation
- Define file structures and component relationships
- Select appropriate tech stacks
- Document API contracts and data models
- Consider scalability, security, and performance

Output format - MUST be valid JSON:
{
  "action": "design_system",
  "design": {
    "overview": "system overview description",
    "components": [
      {
        "name": "component name",
        "type": "service|module|class",
        "responsibilities": ["responsibility 1", "responsibility 2"],
        "dependencies": ["dependency 1", "dependency 2"]
      }
    ],
    "api_contracts": [
      {
        "endpoint": "/api/v1/resource",
        "method": "GET|POST|PUT|DELETE",
        "request": {"param": "type"},
        "response": {"status": "code", "data": {}}
      }
    ],
    "data_models": [
      {
        "name": "ModelName",
        "fields": {"field": "type"},
        "relationships": []
      }
    ],
    "mermaid": "graph TD; A-->B; B-->C;"
  },
  "files": [
    {"path": "src/main.py", "description": "entry point"},
    {"path": "src/models/__init__.py", "description": "model definitions"}
  ],
  "reasoning": "your architectural decisions and trade-offs"
}

Guidelines:
- Use modern patterns: Clean Architecture, DDD, Event-Driven
- Consider 2026 best practices
- Include security by design
- Plan for scaling
- Output ONLY valid JSON, no additional text""",

    AgentType.CODER.value: """You are the Coder Agent - the code generation specialist.

Your role:
- Write production-ready code with 2026 best practices
- Follow clean code principles
- Implement proper error handling
- Add comprehensive comments for complex logic
- Consider security and performance
- Write testable code

Available tools:
- read_file(path): Read file content
- write_file(path, content): Write code to file
- run_shell(command): Execute shell commands

Output format - MUST be valid JSON:
{
  "action": "write_file",
  "path": "src/module/file.py",
  "content": "full Python code...",
  "language": "python|javascript|typescript|go|rust|etc",
  "reasoning": "code design decisions and implementation details",
  "tests": [
    {"description": "test case 1", "input": "value", "expected": "result"}
  ]
}

Guidelines:
- Production-ready code only
- Follow PEP 8 (Python), ESLint (JS), etc.
- Add docstrings and type hints
- Handle errors gracefully
- Consider edge cases
- Output ONLY valid JSON, no additional text""",

    AgentType.EXECUTOR.value: """You are the Executor Agent - the command execution specialist.

Your role:
- Execute safe shell commands
- Report comprehensive results
- Handle errors gracefully
- Support multiple platforms (Linux, macOS, Windows)
- Provide detailed logging

Available tools:
- run_shell(command, timeout): Execute command (default timeout 30s)

Output format - MUST be valid JSON:
{
  "action": "run_shell",
  "command": "npm install",
  "timeout": 60,
  "expected_output": "what success looks like",
  "error_patterns": ["error pattern 1", "error pattern 2"]
}

Result format:
{
  "action": "shell_result",
  "stdout": "command output",
  "stderr": "errors",
  "exit_code": 0,
  "success": true/false,
  "duration": 1.23,
  "analysis": "result analysis"
}

Guidelines:
- Use allowed commands only
- Provide meaningful timeouts
- Report all output streams
- Handle failures gracefully
- Output ONLY valid JSON, no additional text""",

    AgentType.REVIEWER.value: """You are the Reviewer Agent - the code critique specialist.

Your role:
- Analyze code for bugs, security issues, performance problems
- Check for code smells and anti-patterns
- Verify test coverage
- Ensure security best practices
- Score code quality 0-100
- Run debate protocol with Coder

Available tools:
- read_file(path): Read file content
- run_shell(command): Execute linters, tests

Output format - MUST be valid JSON:
{
  "action": "review",
  "score": 85,
  "issues": [
    {
      "severity": "critical|high|medium|low",
      "category": "security|performance|bug|code_smell",
      "location": "file:line",
      "description": "issue description",
      "suggestion": "how to fix"
    }
  ],
  "strengths": ["good practice 1", "good practice 2"],
  "suggestions": ["improvement 1", "improvement 2"],
  "debate_required": true/false,
  "debate_points": ["point to debate with coder"],
  "reasoning": "review analysis"
}

If score < 80 or security issues found, debate is required.
Output ONLY valid JSON, no additional text""",

    AgentType.SPECIALIST.value: """You are the Specialist Agent - dynamic task handler.

Your role:
- Handle niche tasks assigned by Supervisor
- Provide expert analysis
- Adapt to task requirements
- Research and document findings

Output format - MUST be valid JSON:
{
  "action": "specialist_analysis",
  "findings": [
    {"topic": "finding 1", "details": "detailed explanation"}
  ],
  "recommendations": ["recommendation 1", "recommendation 2"],
  "resources": ["resource 1", "resource 2"],
  "reasoning": "analysis reasoning"
}

Guidelines:
- Be thorough and precise
- Provide actionable insights
- Include relevant research
- Output ONLY valid JSON, no additional text"""
}


class ToolRegistry:
    def __init__(self, config: CrackedCodeConfig):
        self.config = config
        self.tools = {}

    def register(self, name: str, func: callable):
        self.tools[name] = func

    def execute(self, name: str, **kwargs) -> Any:
        if name in self.tools:
            return self.tools[name](**kwargs)
        raise ValueError(f"Unknown tool: {name}")

    def get_available_tools(self) -> List[str]:
        return list(self.tools.keys())


class FileTools:
    def __init__(self, config: CrackedCodeConfig):
        self.config = config

    def read_file(self, path: str, max_size: int = 50000) -> str:
        p = Path(path)
        if not p.exists():
            return json.dumps({"error": f"File not found: {path}"})

        try:
            content = p.read_text(encoding='utf-8')
            BLACKBOARD.FILES[str(p)] = content[:max_size]
            return json.dumps({
                "success": True,
                "path": str(p),
                "content": content[:max_size],
                "size": len(content),
                "truncated": len(content) > max_size
            })
        except Exception as e:
            return json.dumps({
                "error": str(e),
                "path": str(p)
            })

    def write_file(self, path: str, content: str, create_dirs: bool = True) -> str:
        p = Path(path)
        try:
            if create_dirs:
                p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding='utf-8')
            BLACKBOARD.FILES[str(p)] = content
            return json.dumps({
                "success": True,
                "path": str(p),
                "size": len(content)
            })
        except Exception as e:
            return json.dumps({
                "error": str(e),
                "path": str(p)
            })

    def delete_file(self, path: str) -> str:
        p = Path(path)
        try:
            if p.exists():
                p.unlink()
                if str(p) in BLACKBOARD.FILES:
                    del BLACKBOARD.FILES[str(p)]
                return json.dumps({"success": True, "path": str(p)})
            return json.dumps({"error": f"File not found: {path}"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    def list_directory(self, path: str = ".", pattern: str = "*") -> str:
        p = Path(path)
        try:
            files = []
            for item in p.glob(pattern):
                files.append({
                    "name": item.name,
                    "type": "dir" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else 0,
                    "path": str(item)
                })
            return json.dumps({
                "success": True,
                "path": str(p),
                "files": files,
                "count": len(files)
            })
        except Exception as e:
            return json.dumps({"error": str(e)})


class ShellTools:
    def __init__(self, config: CrackedCodeConfig):
        self.config = config
        self.allowed_commands = config.get("allowed_shell_commands", [])

    def is_command_allowed(self, cmd: str) -> bool:
        parts = cmd.split()
        if not parts:
            return False
        base_cmd = parts[0].lower()

        if platform.system() == "Windows":
            base_cmd = base_cmd.replace('.exe', '')

        return any(base_cmd.startswith(allowed) for allowed in self.allowed_commands)

    def run_shell(self, cmd: str, timeout: int = 30, cwd: Optional[str] = None) -> str:
        if not self.is_command_allowed(cmd):
            return json.dumps({
                "error": f"Command not allowed: {cmd}",
                "allowed": self.allowed_commands[:10]
            })

        try:
            start_time = time.time()
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd or self.config.get("project_root"),
                encoding='utf-8',
                errors='replace'
            )
            duration = time.time() - start_time

            return json.dumps({
                "success": result.returncode == 0,
                "command": cmd,
                "stdout": result.stdout[:10000],
                "stderr": result.stderr[:5000],
                "exit_code": result.returncode,
                "duration": round(duration, 3),
                "truncated": len(result.stdout) > 10000 or len(result.stderr) > 5000
            })
        except subprocess.TimeoutExpired:
            return json.dumps({
                "error": f"Command timed out after {timeout}s",
                "command": cmd,
                "timeout": timeout
            })
        except Exception as e:
            return json.dumps({
                "error": str(e),
                "command": cmd
            })


class OllamaClient:
    def __init__(self, config: CrackedCodeConfig):
        self.config = config
        self.model = config.get("model", "qwen3-coder:32b")
        self.host = config.get("ollama_host", "http://localhost:11434")

    def chat(self, agent: str, prompt: str, context: Optional[str] = None,
            format_json: bool = True) -> AgentResponse:
        system_prompt = AGENT_SYSTEM_PROMPTS.get(agent, AGENT_SYSTEM_PROMPTS[AgentType.CODER.value])

        context_str = f"""
BLACKBOARD STATE:
{json.dumps({
    "project_context": BLACKBOARD.PROJECT_CONTEXT,
    "files_tracked": len(BLACKBOARD.FILES),
    "plan": BLACKBOARD.PLAN[-5:] if BLACKBOARD.PLAN else [],
    "debate_rounds": len(BLACKBOARD.DEBATE_LOG)
}, indent=2)}

PROJECT ROOT: {self.config.get('project_root')}
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{context_str}\n\nTASK: {prompt}"}
        ]

        try:
            ollama_host = os.environ.get('OLLAMA_HOST', self.host)
            response = ollama.chat(
                model=self.model,
                messages=messages,
                format="json" if format_json else None,
                options={
                    "temperature": self.config.get("temperature", 0.1),
                    "num_ctx": self.config.get("num_ctx", 16384),
                }
            )

            content = response['message']['content']

            try:
                data = json.loads(content)
                return AgentResponse(
                    action=data.get('action', 'unknown'),
                    reasoning=data.get('reasoning', ''),
                    data=data,
                    success=True
                )
            except json.JSONDecodeError:
                return AgentResponse(
                    action='text',
                    reasoning='Non-JSON response',
                    data={'raw': content},
                    success=True
                )

        except Exception as e:
            logger.error(f"Ollama error: {e}")
            return AgentResponse(
                action='error',
                reasoning=str(e),
                data={},
                success=False,
                error=str(e)
            )

    def is_available(self) -> bool:
        try:
            response = ollama.list()
            model_names = [m.model for m in response.models]
            return self.model in model_names
        except Exception:
            return False

    def pull_model(self, model: Optional[str] = None):
        model = model or self.model
        try:
            logger.info(f"Pulling model: {model}")
            ollama.pull(model)
            return True
        except Exception as e:
            logger.error(f"Failed to pull model: {e}")
            return False


class VoiceController:
    def __init__(self, config: CrackedCodeConfig):
        self.config = config
        self.stt_model = None
        self.sample_rate = config.get("sample_rate", 16000)
        self.push_to_talk = config.get("push_to_talk", False)
        self.whisper_size = config.get("whisper_size", "medium.en")

    def init_stt(self) -> bool:
        if not FASTER_WHISPER_AVAILABLE:
            logger.warning("faster-whisper not available")
            return False

        if not self.config.get("voice_enabled", True):
            logger.info("Voice disabled in config")
            return False

        try:
            device = "cuda" if self._check_cuda() else "cpu"
            compute = "float16" if device == "cuda" else "int8"

            logger.info(f"Loading Whisper: {self.whisper_size} on {device}")
            self.stt_model = WhisperModel(
                self.whisper_size,
                device=device,
                compute_type=compute
            )
            logger.info("STT initialized successfully")
            return True

        except Exception as e:
            logger.error(f"STT init failed: {e}")
            return False

    def _check_cuda(self) -> bool:
        if platform.system() == "Windows":
            try:
                subprocess.run(["nvidia-smi"], capture_output=True, check=True)
                return True
            except Exception:
                return False
        return False

    def listen(self, duration: float = 5.0) -> str:
        if not self.stt_model:
            logger.warning("STT not initialized")
            return ""

        try:
            logger.info(f"Listening for {duration}s...")
            recording = sd.rec(
                int(duration * self.sample_rate),
                samplerate=self.sample_rate,
                channels=1,
                dtype='float32'
            )
            sd.wait()
            audio = np.squeeze(recording)

            segments, _ = self.stt_model.transcribe(
                audio,
                beam_size=5,
                language="en",
                vad_filter=True
            )

            transcript = " ".join(seg.text for seg in segments).strip()
            logger.info(f"Transcribed: {transcript[:100]}...")
            return transcript

        except Exception as e:
            logger.error(f"Listen error: {e}")
            return f"Error: {e}"

    def speak(self, text: str) -> bool:
        try:
            logger.info(f"TTS: {text[:50]}...")

            if platform.system() == "Windows":
                piper_exe = Path.home() / ".piper" / "piper.exe"
                voice_model = Path.home() / ".piper" / f"{self.config.get('tts_voice')}.onnx"
            else:
                piper_exe = Path("/usr/local/bin/piper")
                voice_model = Path.home() / ".local/share/piper-voices" / f"{self.config.get('tts_voice')}.onnx"

            if not piper_exe.exists():
                logger.warning("Piper not found")
                return False

            output_wav = "/tmp/crackedcode_response.wav"
            cmd = [
                str(piper_exe),
                "--model", str(voice_model),
                "--output_file", output_wav
            ]

            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
            proc.communicate(input=text.encode(), timeout=10)

            if platform.system() == "Windows":
                subprocess.run(["start", output_wav], shell=True, capture_output=True)
            else:
                subprocess.run(["aplay", output_wav], capture_output=True)

            return True

        except FileNotFoundError:
            logger.warning("Piper not installed")
            return False
        except Exception as e:
            logger.error(f"TTS error: {e}")
            return False


class AgentSwarm:
    def __init__(self, config: CrackedCodeConfig):
        self.config = config
        self.ollama = OllamaClient(config)
        self.file_tools = FileTools(config)
        self.shell_tools = ShellTools(config)
        self.voice = VoiceController(config)
        self.max_workers = config.get("max_concurrent_agents", 4)
        self.task_timeout = config.get("task_timeout", 120)

    def _execute_task(self, task: Task) -> Tuple[Task, Dict]:
        task.status = "running"
        task.start_time = time.time()

        logger.info(f"Executing task {task.id}: {task.agent}")

        try:
            response = self.ollama.chat(task.agent, task.description)

            if task.agent == AgentType.CODER.value and response.action == "write_file":
                result = self.file_tools.write_file(
                    response.data.get("path", ""),
                    response.data.get("content", "")
                )
                task.result = json.loads(result)

            elif task.agent == AgentType.EXECUTOR.value:
                cmd = response.data.get("command", "")
                timeout = response.data.get("timeout", 30)
                result = self.shell_tools.run_shell(cmd, timeout)
                task.result = json.loads(result)

            elif task.agent == "read_file" and response.data.get("path"):
                result = self.file_tools.read_file(response.data.get("path"))
                task.result = json.loads(result)

            else:
                task.result = response.data

            task.status = "completed"
            task.end_time = time.time()

        except Exception as e:
            logger.error(f"Task {task.id} failed: {e}")
            task.status = "failed"
            task.error = str(e)
            task.end_time = time.time()

        BLACKBOARD.TASK_HISTORY.append(task)
        return task, task.result

    def run_plan(self, plan: List[Dict]) -> List[Tuple[Task, Dict]]:
        tasks = [
            Task(
                id=t["id"],
                agent=t["agent"],
                description=t["description"],
                status="pending"
            )
            for t in plan
        ]

        BLACKBOARD.PLAN = plan
        results = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._execute_task, task): task
                for task in tasks
            }

            for future in as_completed(futures, timeout=self.task_timeout):
                task = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"Task {task.id} exception: {e}")
                    task.status = "failed"
                    task.error = str(e)
                    results.append((task, {"error": str(e)}))

        return results

    def run_debate_protocol(self, coder_result: Dict, reviewer_result: Dict,
                           rounds: int = 3) -> Dict:
        BLACKBOARD.DEBATE_LOG.append({
            "coder": coder_result,
            "reviewer": reviewer_result
        })

        for round_num in range(rounds):
            logger.info(f"Debate round {round_num + 1}/{rounds}")

            coder_response = self.ollama.chat(
                AgentType.CODER.value,
                f"Respond to reviewer issues: {reviewer_result.get('issues', [])}"
            )

            reviewer_response = self.ollama.chat(
                AgentType.REVIEWER.value,
                f"Evaluate coder response to issues"
            )

            BLACKBOARD.DEBATE_LOG.append({
                "round": round_num + 1,
                "coder": coder_response.data,
                "reviewer": reviewer_response.data
            })

            if reviewer_response.data.get("score", 0) >= 80:
                break

        consensus = reviewer_response.data
        BLACKBOARD.CONSENSUS = consensus
        return consensus


class CrackedCode:
    VERSION = "2.3.8"
    BANNER = """
============================================================
  CRACKEDCODE v{version} - Local AI Coding Assistant
============================================================
  Platform: {platform}
  Python: {python}
  Models: qwen3:8b-gpu, llava:13b-gpu
============================================================
"""

    def __init__(self, config_path: Optional[str] = None):
        self.config = CrackedCodeConfig(config_path)
        self.swarm = AgentSwarm(self.config)
        self.running = False

        logger.info(f"CrackedCode v{self.VERSION} initializing...")

    def _print_banner(self):
        print(self.BANNER.format(
            version=self.VERSION,
            platform=platform.system(),
            python=platform.python_version()
        ))
        print("-" * 70)

    def start(self):
        self._print_banner()

        if not OLLAMA_AVAILABLE:
            logger.error("Ollama SDK not available")
            print("Error: Ollama SDK required. Install with: pip install ollama")
            return False

        if not self.swarm.ollama.is_available():
            logger.warning("Ollama not available, attempting model pull...")
            if not self.swarm.ollama.pull_model():
                logger.error("Failed to connect to Ollama")
                print("Error: Ollama not running. Start with: ollama serve")
                return False

        self.config.set("voice_enabled", self.swarm.voice.init_stt())

        self.running = True
        logger.info("CrackedCode ready")
        print("\n🎯 CrackedCode is ready!")
        print("\nCommands:")
        print("  • 'exit' - Quit")
        print("  • 'show blackboard' - View memory")
        print("  • 'show history' - View task history")
        print("  • 'help' - Show this help")
        print()

        return True

    def run(self):
        if not self.start():
            return

        conversation_context = ""
        conversation_history = []
        
        while self.running:
            try:
                if self.config.get("push_to_talk"):
                    input(f"\n{interface.color('Press Enter to speak... ', interface.COLORS['system'])}")

                if self.swarm.voice.stt_model:
                    transcript = self.swarm.voice.listen()
                else:
                    transcript = input(f"{interface.color('You: ', Fore.GREEN)}").strip()

                if not transcript:
                    continue

                interface.print_conversation_turn("user", transcript, conversation_context)

                if transcript.lower() in ["exit", "quit", "shutdown"]:
                    logger.info("Shutting down...")
                    interface.print_conversation_turn("assistant", "Shutting down. Goodnight!")
                    self.swarm.voice.speak("Shutting down. Goodnight!")
                    break

                if transcript.lower() == "show blackboard":
                    print("\n" + interface.bold("📌 BLACKBOARD STATE"))
                    print(interface.dim("─" * 50))
                    print(json.dumps({
                        "project_context": BLACKBOARD.PROJECT_CONTEXT,
                        "files_tracked": len(BLACKBOARD.FILES),
                        "plan": BLACKBOARD.PLAN[-5:] if BLACKBOARD.PLAN else [],
                        "debate_rounds": len(BLACKBOARD.DEBATE_LOG),
                        "consensus": BLACKBOARD.CONSENSUS
                    }, indent=2, default=str))
                    continue

                if transcript.lower() == "show history":
                    print("\n" + interface.bold("📜 TASK HISTORY"))
                    print(interface.dim("─" * 50))
                    for task in BLACKBOARD.TASK_HISTORY[-10:]:
                        status_icon = "✓" if task.status == "completed" else "✗"
                        status_color = interface.COLORS['success'] if task.status == "completed" else interface.COLORS['error']
                        print(f"  {status_icon} {task.agent}: {task.description[:40]}... [{status_color}{task.status}{Style.RESET_ALL}]")
                    continue

                if transcript.lower() == "show thinking" or transcript.lower() == "thinking":
                    print("\n" + interface.bold("💭 REASONING CHAINS"))
                    print(interface.dim("─" * 50))
                    for task in BLACKBOARD.TASK_HISTORY[-5:]:
                        reasoning_chain = [
                            "Analyzing task requirements",
                            "Decomposing into subtasks",
                            f"Executing via {task.agent}",
                            "Evaluating results"
                        ]
                        interface.print_reasoning_chain(task.agent, reasoning_chain)
                    continue

                if transcript.lower() == "help":
                    interface.print_banner(self.VERSION)
                    interface.print_help()
                    continue

                supervisor_thought = AgentThought(
                    agent="supervisor",
                    step="analyzing",
                    reasoning=f"Analyzing user request: {transcript[:50]}..."
                )
                interface.print_agent_thought(supervisor_thought)

                interface.print_thinking("Supervisor", "Creating task plan...")

                supervisor_response = self.swarm.ollama.chat(
                    AgentType.SUPERVISOR.value,
                    transcript
                )

                plan = supervisor_response.data.get("plan", [
                    {"id": 1, "agent": "architect", "description": transcript}
                ])

                reasoning_chain = [
                    f"Understood: {transcript[:30]}...",
                    f"Created {len(plan)} subtasks",
                    f"Assigned to: {', '.join(set(t['agent'] for t in plan))}"
                ]
                interface.print_reasoning_chain("SUPERVISOR", reasoning_chain)
                
                print(f"\n{interface.color('📋 Supervisor:', interface.COLORS['supervisor'])} Created {len(plan)} subtasks")
                self.swarm.voice.speak(f"Executing {len(plan)} subtasks")

                print(interface.dim("─" * 50))
                
                reasoning_thought = AgentThought(
                    agent="supervisor",
                    step="reasoning",
                    reasoning=f"Task breakdown: {', '.join(t['description'][:20] for t in plan[:3])}..."
                )
                interface.print_agent_thought(reasoning_thought)

                results = self.swarm.run_plan(plan)

                for task, result in results:
                    task_thought = AgentThought(
                        agent=task.agent,
                        step=task.agent,
                        reasoning=f"Completed: {task.description[:40]}...",
                        confidence=0.85
                    )
                    interface.print_agent_thought(task_thought)
                    
                    if result.get("action") == "review":
                        coder_result = next(
                            (r[1] for r in results if r[1].get("action") == "write_file"),
                            {}
                        )
                        if result.get("debate_required") or result.get("score", 0) < 80:
                            consensus = self.swarm.run_debate_protocol(
                                coder_result,
                                result,
                                self.config.get("debate_rounds", 3)
                            )
                            interface.print_debate_visual(
                                len(BLACKBOARD.DEBATE_LOG),
                                result.get("reasoning", "Code improvements")[:50],
                                result.get("issues", ["Quality check"])[0] if result.get("issues") else "Review complete",
                                result.get("score", 80) / 100.0
                            )

                completed = len([t for t, r in results if t.status == "completed"])
                summary = f"Complete. {completed}/{len(results)} tasks succeeded."
                
                conversation_history.append({
                    "role": "user",
                    "content": transcript,
                    "timestamp": datetime.now().isoformat()
                })
                conversation_history.append({
                    "role": "assistant", 
                    "content": summary,
                    "timestamp": datetime.now().isoformat()
                })
                if len(conversation_history) > 20:
                    conversation_history = conversation_history[-20:]
                
                conversation_context = f"Last task: {transcript[:30]}... | {completed} completed"

                print(f"\n{interface.COLORS['success']}✓{Style.RESET_ALL} {summary}")
                self.swarm.voice.speak(summary)

            except KeyboardInterrupt:
                print(f"\n\n{interface.color('Interrupted. Type exit to quit.', Fore.YELLOW)}")
            except Exception as e:
                logger.error(f"Error: {e}")
                print(f"\n{interface.COLORS['error']}✗ Error:{Style.RESET_ALL} {e}")

        self.running = False


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="CrackedCode - SOTA Local Multi-Agent Coding Swarm"
    )
    # Subcommand support
    subparsers = parser.add_subparsers(dest="subcmd")
    code_parser = subparsers.add_parser("code", help="Generate code via CODE intent")
    code_parser.add_argument("-p", "--prompt", required=True, help="Code generation prompt")
    code_parser.add_argument("-o", "--output", dest="output", required=False, help="Optional output file path to save code")
    code_parser.add_argument("-c", "--config", dest="config", required=False, help="Path to config JSON file")
    code_parser.add_argument("--swarm", action="store_true", help="Execute code generation via swarm coordinator")
    code_parser.add_argument("--validate", action="store_true", help="Validate generated code before returning")

    parser.add_argument(
        "-c", "--config",
        help="Path to config JSON file",
        default=None
    )
    parser.add_argument(
        "--model",
        help="Ollama model to use",
        default=None
    )
    parser.add_argument(
        "--no-voice",
        help="Disable voice features",
        action="store_true"
    )
    parser.add_argument(
        "--push-to-talk",
        help="Enable push-to-talk mode",
        action="store_true"
    )

    args = parser.parse_args()

    # Handle CODE subcommand first
    if getattr(args, "subcmd", None) == "code":
        config = _load_config_from_path(getattr(args, "config", None))
        prompt = getattr(args, "prompt")
        out = getattr(args, "output", None)
        use_swarm = getattr(args, "swarm", False)
        validate = getattr(args, "validate", False)
        
        if use_swarm:
            from src.parallel_processor import CodeSwarmCoordinator
            coordinator = CodeSwarmCoordinator(max_workers=4)
            coordinator.start()
            try:
                if validate:
                    result = coordinator.generate_with_validation(prompt, out)
                else:
                    result = coordinator.generate_code(prompt, out)
            finally:
                coordinator.stop()
            
            if result.get("success"):
                if out:
                    print(f"CODE generated and saved to: {result.get('filepath')}")
                else:
                    print(result.get("code", "")[:500])
                if validate and result.get("validation"):
                    v = result["validation"]
                    print(f"Validation: {'PASS' if v.get('valid') else 'FAIL'}")
                    if v.get("warnings"):
                        print(f"Warnings: {v['warnings']}")
                return 0
            else:
                print(f"Code generation failed: {result.get('error', 'Unknown error')}")
                return 1
        else:
            eng = get_engine(config or {})
            resp = eng.generate_and_save(prompt, out) if out else eng.generate_code(prompt)
            if resp and resp.success:
                if validate:
                    v = eng.validate_code(resp.text)
                    print(f"Validation: {'PASS' if v.get('valid') else 'FAIL'}")
                    if v.get("warnings"):
                        print(f"Warnings: {v['warnings']}")
                print(resp.text[:500])
                return 0
            print(resp.text if resp else 'Code generation failed')
            return 1

    app = CrackedCode(args.config)

    if args.model:
        app.config.set("model", args.model)

    if args.no_voice:
        app.config.set("voice_enabled", False)

    if args.push_to_talk:
        app.config.set("push_to_talk", True)

    app.run()

def cli_code_generate(prompt: str, output_path: str | None = None, config: dict | None = None) -> dict:
    """CLI helper: generate code from a prompt and optionally save to a file.

    This is a lightweight entry point intended for tests and scripting.
    It bypasses the interactive UI and uses the engine directly.
    """
    eng = get_engine(config or {})
    resp = eng.generate_and_save(prompt, output_path) if output_path else eng.generate_code(prompt)
    return {
        "success": resp.success,
        "path": output_path or None,
        "text": resp.text if hasattr(resp, 'text') else str(resp)
    }


def _load_config_from_path(path: str | None) -> dict:
    if not path:
        return {}
    try:
        import json as _json
        with open(path, 'r', encoding='utf-8') as f:
            return _json.load(f)
    except Exception:
        return {}



if __name__ == "__main__":
    main()
