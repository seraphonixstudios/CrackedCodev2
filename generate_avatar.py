"""Generate CrackedCode Raven Avatar - Digital raven with matrix/glitch aesthetic."""

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

# Atlantean theme colors
PRIMARY = "#00FF41"
DARK_GREEN = "#008F11"
BG = "#0a0a0a"
ACCENT = "#00CC33"
MATRIX_CHARS = "01アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン"

def generate_raven_avatar(size=512, output_path="assets/avatar.png"):
    """Generate the CrackedCode raven avatar."""
    img = Image.new("RGB", (size, size), BG)
    draw = ImageDraw.Draw(img)
    
    center = size // 2
    
    # Background matrix rain effect (subtle)
    for _ in range(300):
        x = random.randint(0, size)
        y = random.randint(0, size)
        alpha = random.randint(15, 60)
        char = random.choice(MATRIX_CHARS)
        draw.text((x, y), char, fill=(0, alpha, 0))
    
    body_color = PRIMARY
    shadow_color = DARK_GREEN
    
    # === RAVEN BODY ===
    # Main body (oval-ish, upright)
    body_points = [
        (center, center - 100),       # top of head
        (center + 45, center - 40),   # right cheek
        (center + 55, center + 40),   # right shoulder
        (center + 40, center + 120),  # right side
        (center, center + 150),       # bottom
        (center - 40, center + 120),  # left side
        (center - 55, center + 40),   # left shoulder
        (center - 45, center - 40),   # left cheek
    ]
    draw.polygon(body_points, fill=BG, outline=body_color, width=3)
    draw.polygon([(x, y + 3) for x, y in body_points], fill=(0, 30, 0), outline=shadow_color, width=2)
    
    # === BEAK (sharp, angular) ===
    beak_points = [
        (center, center - 20),        # base
        (center + 8, center - 5),     # right edge
        (center + 3, center + 35),    # tip right
        (center, center + 40),        # tip
        (center - 3, center + 35),    # tip left
        (center - 8, center - 5),     # left edge
    ]
    draw.polygon(beak_points, fill=shadow_color, outline=body_color, width=2)
    # Beak highlight
    draw.line([(center, center - 15), (center, center + 35)], fill=body_color, width=1)
    
    # === EYES (glowing, intense) ===
    # Left eye
    draw.ellipse([center - 32, center - 45, center - 12, center - 20], 
                 fill=BG, outline=body_color, width=2)
    draw.ellipse([center - 28, center - 40, center - 16, center - 25], 
                 fill=body_color)
    # Eye glow
    draw.ellipse([center - 26, center - 38, center - 20, center - 30], 
                 fill=(150, 255, 150))
    
    # Right eye (slightly offset for glitch effect)
    draw.ellipse([center + 12, center - 43, center + 32, center - 18], 
                 fill=BG, outline=body_color, width=2)
    draw.ellipse([center + 16, center - 38, center + 28, center - 23], 
                 fill=body_color)
    # Eye glow
    draw.ellipse([center + 20, center - 36, center + 26, center - 28], 
                 fill=(150, 255, 150))
    
    # === FEATHER TEXTURE (circuit lines) ===
    # Chest feathers - V shapes
    for i in range(5):
        y = center + 20 + i * 18
        width = 20 + i * 5
        draw.line([(center - width, y), (center, y + 12)], fill=body_color, width=1)
        draw.line([(center + width, y), (center, y + 12)], fill=body_color, width=1)
    
    # Side feather lines
    for side in [-1, 1]:
        for i in range(4):
            x = center + side * (35 + i * 3)
            y_start = center - 10 + i * 20
            y_end = y_start + 25
            draw.line([(x, y_start), (x + side * 5, y_end)], fill=shadow_color, width=1)
    
    # === WINGS (spread slightly, angular) ===
    # Left wing
    left_wing = [
        (center - 50, center - 10),
        (center - 120, center - 60),
        (center - 140, center + 20),
        (center - 110, center + 80),
        (center - 60, center + 60),
    ]
    draw.polygon(left_wing, fill=BG, outline=body_color, width=2)
    draw.polygon([(x + 5, y + 5) for x, y in left_wing], fill=(0, 25, 0))
    
    # Wing feather details
    for i in range(3):
        y = center - 20 + i * 25
        draw.line([(center - 100, y), (center - 130, y + 15)], fill=body_color, width=1)
    
    # Right wing
    right_wing = [
        (center + 50, center - 10),
        (center + 120, center - 60),
        (center + 140, center + 20),
        (center + 110, center + 80),
        (center + 60, center + 60),
    ]
    draw.polygon(right_wing, fill=BG, outline=body_color, width=2)
    draw.polygon([(x - 5, y + 5) for x, y in right_wing], fill=(0, 25, 0))
    
    # Wing feather details
    for i in range(3):
        y = center - 20 + i * 25
        draw.line([(center + 100, y), (center + 130, y + 15)], fill=body_color, width=1)
    
    # === HEAD FEATHERS (ear tufts) ===
    # Left tuft
    draw.line([(center - 30, center - 80), (center - 50, center - 130)], fill=body_color, width=2)
    draw.line([(center - 35, center - 75), (center - 60, center - 115)], fill=body_color, width=2)
    # Right tuft
    draw.line([(center + 30, center - 80), (center + 50, center - 130)], fill=body_color, width=2)
    draw.line([(center + 35, center - 75), (center + 60, center - 115)], fill=body_color, width=2)
    
    # === GLITCH EFFECTS ===
    # Horizontal displacement strips
    for _ in range(10):
        y = random.randint(40, size - 40)
        h = random.randint(2, 6)
        offset = random.randint(-15, 15)
        strip = img.crop((0, y, size, y + h))
        img.paste(strip, (offset, y))
    
    # === CRACK LINES (the "cracked" in CrackedCode) ===
    crack_starts = [
        (center - 70, center - 30),
        (center + 75, center + 10),
        (center - 20, center + 100),
    ]
    for start in crack_starts:
        points = [start]
        x, y = start
        for _ in range(4):
            x += random.randint(-12, 12)
            y += random.randint(5, 18)
            points.append((x, y))
        for i in range(len(points) - 1):
            draw.line([points[i], points[i + 1]], fill=ACCENT, width=1)
    
    # === HEXAGON FRAME (Atlantean tech) ===
    hex_radius = 210
    hex_points = []
    for angle in range(0, 360, 60):
        rad = math.radians(angle)
        x = center + hex_radius * math.cos(rad)
        y = center + hex_radius * math.sin(rad)
        hex_points.append((x, y))
    draw.polygon(hex_points, outline=DARK_GREEN, width=1)
    
    # Corner dots
    for angle in range(0, 360, 60):
        rad = math.radians(angle)
        x = center + hex_radius * math.cos(rad)
        y = center + hex_radius * math.sin(rad)
        draw.ellipse([x - 4, y - 4, x + 4, y + 4], fill=body_color)
    
    # Outer ring
    draw.ellipse([center - 235, center - 235, center + 235, center + 235], 
                 outline=(0, 30, 0), width=1)
    
    # === SCANLINES ===
    for y in range(0, size, 4):
        draw.line([(0, y), (size, y)], fill=(0, 8, 0), width=1)
    
    # === VIGNETTE ===
    vignette = Image.new("L", (size, size), 0)
    v_draw = ImageDraw.Draw(vignette)
    v_draw.ellipse([30, 30, size - 30, size - 30], fill=200)
    vignette = vignette.filter(ImageFilter.GaussianBlur(50))
    img = Image.composite(img, Image.new("RGB", (size, size), BG), vignette)
    
    # Save
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    img.save(output, "PNG")
    print(f"Raven avatar saved to {output}")
    return img


def generate_favicon(size=64, output_path="assets/favicon.png"):
    """Generate a small favicon version."""
    img = Image.new("RGB", (size, size), BG)
    draw = ImageDraw.Draw(img)
    
    center = size // 2
    
    # Simplified raven head
    # Body
    body = [
        (center, 6),
        (size - 10, 18),
        (size - 8, size - 12),
        (center, size - 4),
        (8, size - 12),
        (10, 18),
    ]
    draw.polygon(body, fill=DARK_GREEN, outline=PRIMARY, width=2)
    
    # Beak
    beak = [
        (center, 28),
        (center + 4, 34),
        (center + 2, 44),
        (center, 46),
        (center - 2, 44),
        (center - 4, 34),
    ]
    draw.polygon(beak, fill=PRIMARY, outline=PRIMARY, width=1)
    
    # Eyes
    draw.ellipse([center - 14, center - 10, center - 6, center - 2], fill=PRIMARY)
    draw.ellipse([center + 6, center - 10, center + 14, center - 2], fill=PRIMARY)
    
    output = Path(output_path)
    img.save(output, "PNG")
    print(f"Favicon saved to {output}")
    return img


def generate_banner(width=1024, height=256, output_path="assets/banner.png"):
    """Generate a banner with the raven and text."""
    img = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(img)
    
    # Raven on left
    raven = generate_raven_avatar(200, "/tmp/raven_temp.png")
    img.paste(raven, (30, 28))
    
    # Text on right
    try:
        font_large = ImageFont.truetype("consolas.ttf", 64)
        font_small = ImageFont.truetype("consolas.ttf", 24)
    except Exception:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()
    
    draw.text((260, 70), "CRACKEDCODE", fill=PRIMARY, font=font_large)
    draw.text((265, 145), "v2.6.7  //  NEURAL CODING INTERFACE", fill=DARK_GREEN, font=font_small)
    
    # Decorative line
    draw.line([(260, 130), (width - 50, 130)], fill=DARK_GREEN, width=1)
    
    # Matrix chars background
    for _ in range(150):
        x = random.randint(0, width)
        y = random.randint(0, height)
        char = random.choice(MATRIX_CHARS)
        draw.text((x, y), char, fill=(0, random.randint(15, 50), 0))
    
    output = Path(output_path)
    img.save(output, "PNG")
    print(f"Banner saved to {output}")
    return img


if __name__ == "__main__":
    generate_raven_avatar(512, "assets/avatar.png")
    generate_favicon(64, "assets/favicon.png")
    generate_banner(1024, 256, "assets/banner.png")
    print("All raven avatar assets generated!")
