#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║   █████╗  ██████╗  ██████╗ ████████╗    ██████╗  ██╗     ██╗ ██████╗  ║
║  ██╔══██╗██╔═══██╗██╔═══██╗╚══██╔══╝    ██╔══██╗ ██║     ██║██╔════╝  ║
║  ███████║██║   ██║██║   ██║   ██║       ██████╔╝ ██║     ██║██║  ███╗║
║  ██╔══██║██║   ██║██║   ██║   ██║       ██╔══██╗ ██║     ██║██║   ██║║
║  ██║  ██║╚██████╔╝╚██████╔╝   ██║       ██║  ██║ ███████╗██║██║   ██║║
║  ╚═╝  ╚═╝ ╚═════╝  ╚═════╝    ╚═╝       ╚═╝  ╚═╝ ╚══════╝╚═╝╚═════╝║
║                                                                      ║
║                 CRACKEDCODE: ATLANTEAN SYSTEM                        ║
║              NEURAL CODING INTERFACE v2.1                    ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import time
import random
import threading
import datetime
import json
import platform
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

try:
    from colorama import init, Fore, Style, Back
    init(autoreset=True)
    COLORAMA_AVAILABLE = True
except ImportError:
    COLORAMA_AVAILABLE = False
    class Fore:
        RED = GREEN = YELLOW = BLUE = CYAN = MAGENTA = WHITE = RESET =BLACK = ""
    class Style:
        BRIGHT = DIM = NORMAL = RESET_ALL = ""
    class Back:
        RED = GREEN = YELLOW = BLUE = CYAN = MAGENTA = WHITE = BLACK = ""

try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False


# ============================================================================
# ATLANTEAN NEURAL INTERFACE - MATRIX/TECH THEME
# ============================================================================

@dataclass
class AtlanteanTheme:
    PRIMARY = Fore.CYAN
    SECONDARY = Fore.GREEN
    ACCENT = Fore.MAGENTA
    WARNING = Fore.YELLOW
    ERROR = Fore.RED
    DATA = Fore.BLUE
    GHOST = Fore.WHITE
    DIM = Style.DIM
    
    BG_PRIMARY = Back.CYAN
    BG_DARK = Back.BLACK
    
    MATRIX_GREEN = "\033[92m"
    ATLANTEAN_CYAN = "\033[96m"
    NEURAL_PINK = "\033[95m"
    DATA_STREAM = "\033[94m"
    
    GRID_COLOR = Fore.CYAN
    HOLOGRAM_COLOR = Fore.GREEN
    
    def gradient(self, text: str, start_hue: int, end_hue: int) -> str:
        result = ""
        for i, char in enumerate(text):
            hue = start_hue + (end_hue - start_hue) * i // max(len(text), 1)
            result += f"\033[38;5;{hue}m{char}"
        return result + Fore.RESET


class MatrixUI:
    VERSION = "2.9.5"
    
    CHARSETS = {
        "binary": "01",
        "hex": "0123456789ABCDEF",
        "matrix": "アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン",
        "atlan": "◈ ◇ ◆ ▣ ◉ ○ ● ◐ ◑ ◒ ◓ ▤ ▥ ▦ ▧ ▨ ▩ ▪ ▫ ◊ ▼ △ ▽ ◆ ◇",
        "circuit": "├ ┤ ┤ ┴ ┬ ┼ ├ │ ─ ═ ║ ╒ ╓ ╔ ╕ ╖ ╗ ╘ ╙ ╚ ╛ ╜ ╝ ╞ ╟",
        "data": "▀ ▄ █ ▓ ▒ ░ ▬ ▭ ▮ ▯ ▰ ▱ ▲ △ ▴ ▵ ▶ ▷ ▸ ▹ ► ▻ ▼ ▽ ▾ ▿",
        "tech": "⌬ ⌬ ⌬ ⌬ ⌬ ⌬ ⌬ ⌬ ⌬ ⌬ ⌬ ⌬ ⌬ ⌬ ⌬ ⌬ ⌬ ⌬",
    }
    
    FRAMES = {
        "loading": ["◐", "◓", "◑", "◒", "◐", "◓", "◑", "◒"],
        "scan": ["▓", "▒", "░", "▒", "▓", "▒", "░"],
        "link": ["┤", "├", "┤"],
        "pulse": ["●", "◉", "○"],
        "data": ["▌", "▀", "▐", "▄"],
    }
    
    ASCII_ART = {}
    
    @classmethod
    def load_ascii_art(cls):
        cls.ASCII_ART = {
            "skull": [
                "      ████████",
                "    ██          ██",
                "  ██    ██  ██    ██",
                "  ██    ██  ██    ██",
                "  ██              ██",
                "    ██          ██",
                "      ████████",
            ],
            "robot": [
                "   ▄▄▄▄▄▄▄▄▄▄▄▄▄▄",
                "  █              █",
                "  █  ◉        ◉  █",
                "  █  ◉        ◉  █",
                "  █     ░▒░     █",
                "  █    █████    █",
                "  █              █",
                "   ▀▀▀▀▀▀│▀▀▀▀▀▀",
                "      ╔══╩══╗",
                "      ║    ║",
            ],
            "dragon": [
                "              ><>",
                "             <>  <>",
                "            <> <><> <>",
                "           <>  <>    <>",
                "          <>   <>  <>",
                "         <>    <>  <>",
                "        <>  █    █  <>",
                "       <>  █ ██ █ █ <>",
                "      <>   █ ██ █ █  <>",
                "     <>    █      █   <>",
                "    <>     █      █    <>",
                "   <>      █ ██ █ █     <>",
                "  <>       █ ██ █ █      <>",
                " <>        █      █       <>",
                "<>▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒>",
            ],
            "circuit_heart": [
                "    ┌─┐     ┌─┐",
                "   ╭┤├╮   ╭┤├╮",
                "   ││││   ││││",
                "   ╰┴├╯   ╰┴├╯",
                "    └─┘     └─┘",
                "     ╲ ╱   ╲ ╱",
                "      ╳     ╳",
                "     ╱ ╲─┐ ╱ ╲",
                "    ┌────┴────┐",
                "    │  ◉  ◉  │",
                "    │  ████  │",
                "    └────┬────┘",
                "        │││",
                "    █───┴───┈█",
                "  ██         ██",
            ],
            "neural_network": [
                "       ◉──◉──◉",
                "      ╱ │╲ │╱ │",
                "     ◉  ◉  ◉  ◉",
                "    ╱│╲ │╱│╲ │",
                "   ◉ │◉ │◉ │◉",
                "  ╱│╲│╲��╱│╲│╱│╲",
                " ◉  ◉  ◉  ◉  ◉",
            ],
            "system_core": [
                "   ╔═══════════════╗",
                "   ║  ◉  ◉  ◉  ◉  ║",
                "   ║ ◉═╪═◉═╪═◉═╪═◉ ║",
                "   ║  ◉══╬══◉  ◉  ║",
                "   ║ ◉═╪═◉═╪═◉═╪═◉ ║",
                "   ║  ◉  ◉  ◉  ◉  ║",
                "   ╚═══════════════╝",
            ],
            "data_cube": [
                "    ╔══╗",
                "   ╔╝▓▓╚╗",
                "  ╔╝▓▓▓╚╗",
                " ╔╝▓▓▓▓╚╗",
                " ║▓▓▓▓▓║",
                " ║▓▓▓▓╚╝",
                " ║▓▓╚╝",
                " ╚╝",
            ],
            "quantum": [
                "    ◉",
                "   ╱│╲",
                "  ╱ │ ╲",
                " ◉──┼──◉",
                " ╲ │ ╱",
                "  ╲│╱",
                "   ◉",
                "   │",
                "  ◉┼◉",
            ],
        }

MatrixUI.load_ascii_art()
    
BANNERS = {
        "atlan": [
            "============================================================",
            "  CRACKEDCODE v{version} - ATLANTEAN NEURAL SYSTEM",
            "============================================================",
            "  VERSION: {version}",
            "  PLATFORM: {platform}",
            "  [ NEURAL LINK ACTIVE ]",
            "============================================================",
        ],
        "matrix": [
            "============================================================",
            "  MATRIX PROTOCOL v2.1",
            "  SYSTEM ONLINE",
            "============================================================",
        ],
        "circuit": [
            "============================================================",
            "  [NEURAL CIRCUIT] - [CODE INTERFACE]",
            "============================================================",
        ],
    }

ASCII_ART = {
    "skull": [
        "      ████████",
        "    ██          ██",
        "  ██    ██  ██    ██",
        "  ██    ██  ██    ██",
        "  ██              ██",
        "    ██          ██",
        "      ████████",
    ],
    "robot": [
        "   ▄▄▄▄▄▄▄▄▄▄▄▄▄▄",
        "  █              █",
        "  █  ◉        ◉  █",
        "  █  ◉        ◉  █",
        "  █     ░▒░     █",
        "  █    █████    █",
        "  █              █",
        "   ▀▀▀▀▀▀│▀▀▀▀▀▀",
        "      ╔══╩══╗",
        "      ║    ║",
    ],
    "dragon": [
        "              ><>",
        "             <>  <>",
        "            <> <><> <>",
        "           <>  <>    <>",
        "          <>   <>  <>",
        "         <>    <>  <>",
        "        <>  █    █  <>",
        "       <>  █ ██ █ █ <>",
        "      <>   █ ██ █ █  <>",
        "     <>    █      █   <>",
        "    <>     █      █    <>",
        "   <>      █ ██ █ █     <>",
        "  <>       █ ██ █ █      <>",
        " <>        █      █       <>",
        "<>▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒>",
    ],
    "binary_skull": [
        "010000010100001101001100",
        "010100100101001101000100",
        "010000010101010100010100",
        "010010010100000101001001",
        "010000010100001001000100",
        "010101000101001100010100",
        "010000100101000101000010",
    ],
    "circuit_heart": [
        "    ┌─┐     ┌─┐",
        "   ╭┤├╮   ╭┤├╮",
        "   ││││   ││││",
        "   ╰┴├╯   ╰┴├╯",
        "    └─┘     └─┘",
        "     ╲ ╱   ╲ ╱",
        "      ╳     ╳",
        "     ╱ ╲─┐ ╱ ╲",
        "    ┌────┴────┐",
        "    │  ◉  ◉  │",
        "    │  ████  │",
        "    └────┬────┘",
        "        │││",
        "    █───┴───┈█",
        "  ██         ██",
    ],
    "neural_network": [
        "       ◉──◉──◉",
        "      ╱ │╲ │╱ │",
        "     ◉  ◉  ◉  ◉",
        "    ╱│╲ │╱│╲ │",
        "   ◉ │◉ │◉ │◉",
        "  ╱│╲│╲│╱│╲│╱│╲",
        " ◉  ◉  ◉  ◉  ◉",
    ],
    "matrix_rain ascii": [
        "┋┿┋┿┋┿┋┿",
        "┃┃┃┃┃┃┃┃┃┃",
        "┣┿┣┿┣┿┣┿",
        "┃┃┃┃┃┃┃┃┃┃",
        "┋┿┋┿┋┿┋┿",
    ],
    "system_core": [
        "   ╔═══════════════╗",
        "   ║  ◉  ◉  ◉  ◉  ║",
        "   ║ ◉═╪═◉═╪═◉═╪═◉ ║",
        "   ║  ◉══╬══◉  ◉  ║",
        "   ║ ◉═╪═◉═╪═◉═╪═◉ ║",
        "   ║  ◉  ◉  ◉  ◉  ║",
        "   ╚═══════════════╝",
    ],
    "cyber_eye": [
        "     ╔██████╗",
        "   ╔██║▌▌▌██╗",
        "  ╔██║██▌██║██╗",
        " ╔██║██▌▌██║██╗",
        " ╚██║▌▌▌██╝╝",
        "   ╚█████╝",
        "      ▌▌",
        "     █▐▐█",
        "    █▐█▐█",
    ],
    "data_cube": [
        "    ╔══╗",
        "   ╔╝▓▓╚╗",
        "  ╔╝▓▓▓╚╗",
        " ╔╝▓▓▓▓╚╗",
        " ║▓▓▓▓▓║",
        " ║▓▓▓▓╚╝",
        " ║▓▓╚╝",
        " ╚╝",
    ],
    "quantum": [
        "    ◉",
        "   ╱│╲",
        "  ╱ │ ╲",
        " ◉──┼──◉",
        " ╲ │ ╱",
        "  ╲│╱",
        "   ◉",
        "   │",
        "  ◉┼◉",
    ],
    "terminator": [
        "╔══════════════════════════╗",
        "║ ▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄ ░",
        "║█                       █░",
        "║█  ██╗  ██╗  ██╗  ██╗  █░",
        "║█  ██║  ██║  ██║  ██║  █░",
        "║█  ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀  █░",
        "║█                       █░",
        "╚══════════════════════════╝",
    ],
}
    

# ============================================================================
# DATA STREAM ANIMATIONS
# ============================================================================

class DataStream:
    def __init__(self, charset: str = "binary", width: int = 50):
        self.charset = charset
        self.width = width
        self.running = False
        self.thread = None
        
    def _get_char(self) -> str:
        return random.choice(self.charset)
        
    def stream_line(self) -> str:
        return "".join(self._get_char() for _ in range(self.width))
        
    def run(self, duration: float = 2.0, callback = None):
        self.running = True
        start = time.time()
        
        while self.running and time.time() - start < duration:
            print(self.stream_line())
            if callback:
                callback()
            time.sleep(0.05)
            
    def stop(self):
        self.running = False


class MatrixRain:
    def __init__(self, width: int = 60, height: int = 20):
        self.width = width
        self.height = height
        self.drops = [0] * width
        self.running = False
        self.thread = None
        
    def render_frame(self) -> List[str]:
        lines = []
        
        for y in range(self.height):
            line = ""
            for x in range(self.width):
                if random.random() < 0.01:
                    self.drops[x] = y
                    
                if y == self.drops[x]:
                    char = random.choice("アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホ")
                elif y > self.drops[x]:
                    char = " "
                else:
                    fade = (y - self.drops[x]) / self.height
                    char = random.choice("01アイウエオ")
                    
                line += char
            lines.append(line)
            
        return lines
        
    def start(self, duration: float = 3.0):
        self.running = True
        start = time.time()
        
        while self.running and time.time() - start < duration:
            os.system('cls' if os.name == 'nt' else 'clear')
            lines = self.render_frame()
            for i, line in enumerate(lines):
                color = Fore.GREEN if i < len(lines) // 3 else Fore.CYAN
                print(color + line)
            time.sleep(0.1)
            
        self.running = False


class GlitchEffect:
    @staticmethod
    def glitch_text(text: str, intensity: float = 0.1) -> str:
        result = ""
        for char in text:
            if random.random() < intensity:
                glitch_chars = "▓▒░█▓▒░"
                result += random.choice(glitch_chars)
            else:
                result += char
        return result
    
    @staticmethod
    def scan_lines(text: str, lines: int = 5) -> List[str]:
        output = []
        for _ in range(lines):
            offset = random.randint(-2, 2)
            if offset != 0:
                glitch = "▓" * abs(offset)
                output.append(glitch + text)
            else:
                output.append(text)
        return output
    
    @staticmethod
    def corrupt(data: str, corruption: float = 0.05) -> str:
        result = ""
        for char in data:
            if char == "\n":
                result += "\n"
            elif random.random() < corruption:
                result += random.choice("▓▒░█■□")
            else:
                result += char
        return result


class HologramBorder:
    
    CORNERS = {
        "single": {"tl": "┌", "tr": "┐", "bl": "└", "br": "┘"},
        "double": {"tl": "╔", "tr": "╗", "bl": "╚", "br": "╝"},
        "rounded": {"tl": "╭", "tr": "╮", "bl": "╰", "br": "╯"},
        "heavy": {"tl": "┏", "tr": "┓", "bl": "┗", "br": "┛"},
        "matrix": {"tl": "┌", "tr": "┐", "bl": "└", "br": "┘"},
    }
    
    EDGES = {
        "single": {"h": "─", "v": "│"},
        "double": {"h": "═", "v": "║"},
        "matrix": {"h": "━", "v": "┃"},
    }
    
    @classmethod
    def box(cls, content: str, style: str = "single", padding: int = 1) -> str:
        if style not in cls.CORNERS:
            style = "single"
            
        c = cls.CORNERS[style]
        e = cls.EDGES[style]
        
        lines = content.split("\n")
        max_len = max(len(line) for line in lines) if lines else 0
        width = max_len + padding * 2
        
        top = c["tl"] + e["h"] * width + c["tr"]
        bottom = c["bl"] + e["h"] * width + c["br"]
        
        body = []
        for line in lines:
            padded = line.ljust(width)
            body.append(f"{e['v']}{padded}{e['v']}")
            
        return "\n".join([top] + body + [bottom])


class NeuralPulse:
    
    @staticmethod
    def pulse(text: str, style: str = "default") -> List[str]:
        if style == "matrix":
            frames = [
                f"[◐] {text}",
                f"[◑] {text}",
                f"[◒] {text}",
                f"[◓] {text}",
            ]
        elif style == "neural":
            frames = [
                f"◈ {text}",
                f"◇ {text}",
                f"◆ {text}",
                f"◈ {text}",
            ]
        else:
            frames = [
                f"● {text}",
                f"◉ {text}",
                f"○ {text}",
                f"◉ {text}",
            ]
        return frames
    
    @staticmethod
    def animate(text: str, duration: float = 1.0):
        frames = NeuralPulse.pulse(text, "neural")
        start = time.time()
        i = 0
        
        while time.time() - start < duration:
            print(f"\r{frames[i % len(frames)]}", end="", flush=True)
            time.sleep(0.15)
            i += 1
            
        print(f"\r✓ {text}   ")
    
    @staticmethod
    def progress_bar(current: int, total: int, width: int = 30, 
                  fill_char: str = "█", empty_char: str = "▒") -> str:
        percent = current / total
        filled = int(width * percent)
        
        if COLORAMA_AVAILABLE:
            filled_bar = Fore.CYAN + fill_char * filled + Fore.GREEN
            empty_bar = Fore.GREEN + empty_char * (width - filled) + Style.RESET_ALL
        else:
            filled_bar = fill_char * filled
            empty_bar = empty_char * (width - filled)
            
        return f"[{filled_bar}{empty_bar}] {int(percent * 100)}%"


class HexGrid:
    
    @staticmethod
    def hex_pattern(width: int = 20, height: int = 10) -> List[str]:
        lines = []
        
        for y in range(height):
            line = ""
            offset = " " if y % 2 else " "
            
            for x in range(width):
                if (x + y) % 3 == 0:
                    char = "◈"
                elif (x + y) % 2 == 0:
                    char = "◇"
                else:
                    char = " "
                    
                line += char
                
            lines.append(offset + line)
            
        return lines
    
    @staticmethod
    def render_grid(data: Dict = None, width: int = 40) -> str:
        lines = []
        
        if not data:
            data = {"system": "ATLANTEAN", "status": "ONLINE", "neural_link": "ACTIVE"}
            
        for key, value in data.items():
            hex_line = "◇ " * ((width - len(f"{key}: {value}")) // 4)
            line = f"◈ {key}: {value} {hex_line[:width-len(f'{key}: {value}')-4]} ◈"
            lines.append(line)
            
        return "\n".join(lines)


class CircuitBoard:
    
    NODES = {
        "cpu": "◉",
        "memory": "▣",
        "input": "▷",
        "output": "◁", 
        "process": "▦",
        "data": "▤",
        "link": "──",
        "junction": "◇",
    }
    
    @classmethod
    def draw_connection(cls, from_node: str, to_node: str) -> str:
        return f"{cls.NODES[from_node]}───╬───{cls.NODES[to_node]}"
    
    @classmethod
    def render_system(cls, components: List[str]) -> str:
        lines = []
        
        for i, comp in enumerate(components):
            lines.append(f"│  {cls.NODES['junction']} {comp}")
            if i < len(components) - 1:
                lines.append(f"│     │")
                lines.append(f"│     ├")
                
        return "\n".join(lines)


class ScannerLine:
    
    @staticmethod
    def scan(text: str, passes: int = 3) -> None:
        width = len(text) + 4
        
        for _ in range(passes):
            print("═" * width)
            print(f"│ {text} │")
            time.sleep(0.1)
            
        print("═" * width)
    
    @staticmethod
    def radar_scan(text: str, radius: int = 20) -> str:
        lines = []
        
        for r in range(radius):
            line = " "
            if r == radius // 2:
                line = f"│ {text} │"
            elif r < radius // 2:
                line = " " * 2 + "│" + " " * (len(text)) + "│" + " " * 2
            else:
                line = " " * radius
                
            lines.append(line)
            
        return "\n".join(lines)


class StatusDisplay:
    
    STATUS_ICONS = {
        "online": "◈",
        "offline": "◇",
        "processing": "◐",
        "error": "✗",
        "warning": "⚠",
        "success": "✓",
        "complete": "◉",
        "loading": "◓",
    }
    
    @classmethod
    def status(cls, name: str, state: str) -> str:
        icon = cls.STATUS_ICONS.get(state, "○")
        
        colors = {
            "online": Fore.CYAN,
            "offline": Fore.RED,
            "processing": Fore.YELLOW,
            "error": Fore.RED,
            "warning": Fore.YELLOW,
            "success": Fore.GREEN,
            "complete": Fore.GREEN,
            "loading": Fore.CYAN,
        }
        
        color = colors.get(state, Fore.WHITE)
        
        return f"{color}[{icon}] {name}: {state.upper()}{Style.RESET_ALL}"
    
    @classmethod
    def system_status(cls, systems: Dict[str, str]) -> str:
        lines = ["┌─ SYSTEM STATUS ─┐"]
        
        for name, state in systems.items():
            lines.append(f"│ {cls.status(name, state)}")
            
        lines.append("└" + "─" * 20 + "┘")
        
        return "\n".join(lines)


class DataDecoder:
    
    BIN_CHARS = "01░▒█"
    
    @classmethod
    def binary_stream(cls, data: str, chunk_size: int = 8) -> str:
        result = ""
        
        for char in data:
            binary = format(ord(char), '08b')
            for bit in binary:
                result += cls.BIN_CHARS[int(bit)]
            result += " "
                
        return result
    
    @classmethod
    def hex_dump(cls, data: bytes, width: int = 16) -> str:
        lines = []
        
        for i in range(0, len(data), width):
            chunk = data[i:i+width]
            hex_part = " ".join(f"{b:02x}" for b in chunk)
            ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            
            lines.append(f"{i:04x}  {hex_part:<{width*3}}  {ascii_part}")
            
        return "\n".join(lines)


class AtlanInterface:
    def __init__(self):
        self.theme = AtlanteanTheme()
        self.ui = MatrixUI()
        self.glitch = GlitchEffect()
        self.running = False
        self.build_mode = False
        self.plan_mode = True
        self.execution_history = []
        
    def set_mode(self, plan: bool = None, build: bool = None):
        if plan is not None:
            self.plan_mode = plan
        if build is not None:
            self.build_mode = build
            
        mode_display = []
        if self.plan_mode:
            mode_display.append("PLAN")
        if self.build_mode:
            mode_display.append("BUILD")
            
        if not mode_display:
            mode_display = ["IDLE"]
            
        self._print_mode_indicator(" ".join(mode_display))
        
    def _print_mode_indicator(self, mode: str):
        colors = {
            "PLAN": Fore.CYAN,
            "BUILD": Fore.GREEN,
            "IDLE": Fore.RED,
        }
        color = colors.get(mode, Fore.WHITE)
        
        print(f"\n{color}[◈] MODE: {mode}{Style.RESET_ALL}")
        
    def toggle_plan(self):
        self.plan_mode = not self.plan_mode
        self._print_mode_indicator("PLAN" if self.plan_mode else "IDLE")
        
    def toggle_build(self):
        self.build_mode = not self.build_mode
        self._print_mode_indicator("BUILD" if self.build_mode else "IDLE")
        
    def plan_phase(self, tasks: List[str]):
        if not self.plan_mode:
            return None
            
        print(f"\n{Fore.CYAN}◈ PLANNING PHASE:{Style.RESET_ALL}")
        
        plan = []
        for i, task in enumerate(tasks, 1):
            print(f"  {Fore.CYAN}{i}.{Style.RESET_ALL} {task}")
            plan.append({"step": i, "task": task, "status": "planned"})
            
        print(f"  └─ {len(tasks)} tasks planned")
        
        return plan
        
    def build_phase(self, plan: List[Dict]):
        if not self.build_mode:
            return None
            
        print(f"\n{Fore.GREEN}◈ BUILD PHASE:{Style.RESET_ALL}")
        
        results = []
        for step in plan:
            task = step.get("task", "")
            print(f"  {Fore.GREEN}▓{Style.RESET_ALL} Executing: {task}")
            
            results.append({
                "step": step.get("step"),
                "task": task,
                "status": "built",
                "completed_at": datetime.now().isoformat()
            })
            
            self.execution_history.append({
                "mode": "build",
                "task": task,
                "timestamp": datetime.now().isoformat()
            })
            
        print(f"  └─ {len(plan)} tasks executed")
        
        return results
        
    def execute_plan(self, task_description: str, task_count: int = 5):
        plan = [{"step": i, "task": f"subtask_{i}", "status": "pending"} for i in range(1, task_count + 1)]
        
        if self.plan_mode:
            print(f"\n{Fore.CYAN}◈ PROCESSING: {task_description}{Style.RESET_ALL}")
            
            if self.plan_mode:
                plan = self.plan_phase([p["task"] for p in plan])
                
            if self.build_mode and plan:
                results = self.build_phase(plan)
                print(f"\n{Fore.GREEN}✓ EXECUTION COMPLETE{Style.RESET_ALL}")
                return results
            else:
                print(f"\n{Fore.YELLOW}⚠ PLAN READY - Toggle build mode to execute{Style.RESET_ALL}")
                return plan
        else:
            print(f"\n{Fore.RED}◈ SYSTEM IN IDLE MODE{Style.RESET_ALL}")
            return None
        
    def print_banner(self, style: str = "atlan"):
        banners = {
            "atlan": self.ui.BANNERS["atlan"],
            "matrix": self.ui.BANNERS["matrix"],
            "circuit": self.ui.BANNERS["circuit"],
        }
        
        banner = banners.get(style, banners["atlan"])
        
        for line in banner:
            if "{version}" in line:
                line = line.replace("{version}", self.ui.VERSION)
                
            if style == "atlan":
                print(Fore.CYAN + line + Style.RESET_ALL)
            elif style == "matrix":
                print(Fore.GREEN + line + Style.RESET_ALL)
            else:
                print(Fore.CYAN + line + Style.RESET_ALL)
                
        print()
    
    def print_data_stream(self, message: str, charset: str = "binary", duration: float = 0.5):
        stream = DataStream(charset)
        frames = []
        
        for _ in range(int(duration * 20)):
            frame = stream.stream_line()[:len(message)] + " " + message
            frames.append(frame)
            
        for frame in frames:
            print(f"\r{Fore.CYAN}{frame}{Style.RESET_ALL}", end="", flush=True)
            time.sleep(0.05)
            
        print()
    
    def print_status(self, components: Dict[str, str]):
        for name, state in components.items():
            print(StatusDisplay.status(name, state))
            
        print()
    
    def loading_sequence(self, message: str = "INITIALIZING"):
        print(f"\n{Fore.CYAN}◈ {message}..{Style.RESET_ALL}")
        
        frames = self.ui.FRAMES["loading"]
        
        for i in range(20):
            frame = frames[i % len(frames)]
            print(f"\r{Fore.CYAN}{frame} {message}{Style.RESET_ALL}", end="", flush=True)
            time.sleep(0.1)
            
        print(f"\r{Fore.GREEN}✓ {message} COMPLETE{Style.RESET_ALL}\n")
    
    def print_system_info(self):
        self.print_banner("atlan")
        
        systems = {
            "NEURAL CORE": "online",
            "CODE MATRIX": "online", 
            "VOICE LINK": "online",
            "VISION ENGINE": "online",
            "DEBUG MODE": os.environ.get("CRACKEDCODE_DEBUG", "false"),
        }
        
        self.print_status(systems)
        
        data = {
            "PLATFORM": platform.system(),
            "PYTHON": platform.python_version()[:8],
            "VERSION": self.ui.VERSION,
        }
        
        print(HexGrid.render_grid(data))
        print()
    
    def prompt(self) -> str:
        if COLORAMA_AVAILABLE:
            return f"{Fore.CYAN}◈>{Style.RESET_ALL} "
        return "◈> "
    
    def response(self, text: str):
        if COLORAMA_AVAILABLE:
            print(f"{Fore.GREEN}◈>{Style.RESET_ALL} {text}")
        else:
            print(f"◈> {text}")


atlan_ui = AtlanInterface()


def test_interface():
    print("\n" + "="*70)
    print(f"{Fore.CYAN}◈ ATLANTEAN UI INTERFACE TEST{Style.RESET_ALL}")
    print("="*70 + "\n")
    
    atlan_ui.print_system_info()
    
    atlan_ui.loading_sequence("LOADING MODULES")
    
    atlan_ui.print_data_stream("INIT NEURAL LINK", "hex", 1.0)
    
    print(HologramBorder.box("ATLANTEAN SYSTEM\nVERSION 2.1.7\nNEURAL LINK: ACTIVE", "rounded"))
    print()
    
    print(f"{Fore.CYAN}◈ Testing ASCII Art Rendering:{Style.RESET_ALL}\n")
    for art_name in MatrixUI.ASCII_ART:
        if art_name in ["robot", "system_core", "data_cube", "quantum"]:
            art = MatrixUI.ASCII_ART[art_name]
            for line in art:
                print(Fore.GREEN + line)
            print()
    
    print(f"{Fore.CYAN}◈ Testing NeuralPulse Animation:{Style.RESET_ALL}")
    NeuralPulse.animate("SYSTEM DIAGNOSTIC", 1.5)
    
    print(f"{Fore.CYAN}◈ Testing Progress Bar:{Style.RESET_ALL}")
    for i in range(0, 11, 2):
        bar = NeuralPulse.progress_bar(i, 10)
        print(f"\r{Fore.CYAN}{bar}{Style.RESET_ALL}", end="", flush=True)
        time.sleep(0.2)
    print("\n")
    
    print(f"{Fore.CYAN}◈ Testing HexGrid:{Style.RESET_ALL}")
    grid = HexGrid.hex_pattern(18, 6)
    for line in grid:
        print(Fore.GREEN + line)
    print()
    
    print(f"{Fore.CYAN}◈ Testing CircuitBoard:{Style.RESET_ALL}")
    print(CircuitBoard.draw_connection("cpu", "memory"))
    print(CircuitBoard.draw_connection("input", "process"))
    components = ["CPU [◉]", "MEMORY [▣]", "GPU [▦]", "NETWORK [▤]"]
    print(CircuitBoard.render_system(components))
    print()
    
    print(f"{Fore.CYAN}◈ Testing ScannerLine:{Style.RESET_ALL}")
    ScannerLine.scan("SYSTEM DIAGNOSTIC COMPLETE", 3)
    print()
    
    print(f"{Fore.CYAN}◈ Testing DataDecoder:{Style.RESET_ALL}")
    test_data = "ATLAN"
    binary = DataDecoder.binary_stream(test_data)
    print(f"Binary stream: {binary}\n")
    
    test_bytes = b"ATLAS\x00\x01\x02\x03\x04"
    hexdump = DataDecoder.hex_dump(test_bytes)
    print(hexdump)
    print()
    
    print(f"{Fore.GREEN}✓ INTERFACE TEST COMPLETE{Style.RESET_ALL}\n")


def demo_effects():
    print("\n" + "="*70)
    print(f"{Fore.MAGENTA}◈ ATLANTEAN UI EFFECTS DEMO{Style.RESET_ALL}")
    print("="*70 + "\n")
    
    print(f"{Fore.CYAN}[1] Glitch Effect:{Style.RESET_ALL}")
    glitch_output = GlitchEffect.glitch_text("SYSTEM BREACH DETECTED")
    print(f"  {Fore.RED}{glitch_output}{Style.RESET_ALL}")
    print()
    
    print(f"{Fore.CYAN}[2] Scan Lines:{Style.RESET_ALL}")
    scan_lines = GlitchEffect.scan_lines("DATA CORRUPTION", 4)
    for line in scan_lines:
        print(f"  {line}")
    print()
    
    print(f"{Fore.CYAN}[3] Corruption Effect:{Style.RESET_ALL}")
    corrupted = GlitchEffect.corrupt("NEURAL LINK COMPROMISED", 0.1)
    print(f"  {corrupted}")
    print()
    
    print(f"{Fore.CYAN}[4] NeuralPulse Frames:{Style.RESET_ALL}")
    pulse_frames = NeuralPulse.pulse("LINK ESTABLISHED", "matrix")
    for frame in pulse_frames:
        print(f"  {frame}")
    print()
    
    print(f"{Fore.CYAN}[5] NeuralPulse Animation (Live):{Style.RESET_ALL}")
    NeuralPulse.animate("ESTABLISHING CONNECTION", 2.0)
    
    print(f"{Fore.CYAN}[6] Progress Bar Animation:{Style.RESET_ALL}")
    for i in range(0, 101, 10):
        bar = NeuralPulse.progress_bar(i, 100, width=30)
        print(f"\r  {Fore.GREEN}{bar}{Style.RESET_ALL}", end="", flush=True)
        time.sleep(0.15)
    print("\n")
    
    print(f"{Fore.CYAN}[7] HexGrid Pattern:{Style.RESET_ALL}")
    hex_pattern = HexGrid.hex_pattern(20, 8)
    for line in hex_pattern:
        print(f"  {line}")
    print()
    
    print(f"{Fore.CYAN}[8] HexGrid Render Data:{Style.RESET_ALL}")
    sample_data = {
        "CORE": "ACTIVE",
        "MEM": "4096MB",
        "CPU": "NEURAL-7",
        "LINK": "SECURE"
    }
    print(HexGrid.render_grid(sample_data, 40))
    print()
    
    print(f"{Fore.CYAN}[9] HologramBorder Styles:{Style.RESET_ALL}")
    for style in ["single", "double", "rounded", "heavy"]:
        result = HologramBorder.box(f"Style: {style}", style)
        print(result)
    print()
    
    print(f"{Fore.CYAN}[10] Circuit Board Components:{Style.RESET_ALL}")
    conn = CircuitBoard.draw_connection("cpu", "memory")
    print(f"  {conn}")
    conn2 = CircuitBoard.draw_connection("data", "process")
    print(f"  {conn2}")
    render = CircuitBoard.render_system(["NEURAL CORE", "CACHE UNIT", "OUTPUT NODE"])
    for line in render.split("\n"):
        print(f"  {line}")
    print()
    
    print(f"{Fore.CYAN}[11] Scanner Effects:{Style.RESET_ALL}")
    ScannerLine.scan("DEMO SCAN", 3)
    radar = ScannerLine.radar_scan("TARGET ACQUIRED", 12)
    print(radar)
    print()
    
    print(f"{Fore.CYAN}[12] Status Display:{Style.RESET_ALL}")
    systems = {
        "CORE": "online",
        "MATRIX": "loading",
        "OUTPUT": "warning",
        "INPUT": "complete"
    }
    for name, state in systems.items():
        print(f"  {StatusDisplay.status(name, state)}")
    print()
    
    print(f"{Fore.CYAN}[13] Full System Status:{Style.RESET_ALL}")
    full_status = {
        "NEURAL ENGINE": "online",
        "CODE MATRIX": "online",
        "VOICE SYSTEM": "processing",
        "DEBUG MODE": "complete"
    }
    print(StatusDisplay.system_status(full_status))
    print()
    
    print(f"{Fore.CYAN}[14] Matrix DataStream:{Style.RESET_ALL}")
    stream = DataStream("binary", 40)
    for _ in range(8):
        print(f"  {stream.stream_line()}")
    print()
    
    print(f"{Fore.CYAN}[15] Additional ASCII Art:{Style.RESET_ALL}")
    if "robot" in MatrixUI.ASCII_ART:
        print(f"  {Fore.GREEN}Robot:{Style.RESET_ALL}")
        for line in MatrixUI.ASCII_ART["robot"]:
            print(f"  {line}")
    if "system_core" in MatrixUI.ASCII_ART:
        print(f"  {Fore.CYAN}System Core:{Style.RESET_ALL}")
        for line in MatrixUI.ASCII_ART["system_core"]:
            print(f"  {line}")
    print()
    
    print(f"{Fore.GREEN}✓ ALL DEMO EFFECTS COMPLETE{Style.RESET_ALL}\n")


if __name__ == "__main__":
    test_interface()
    demo_effects()
