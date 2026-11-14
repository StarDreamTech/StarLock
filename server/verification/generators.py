"""Extracted from StarDreamCaptcha: character rendering, arithmetic and visual noise.

No StarDream settings, registration, email delivery or answer-bearing public API.
"""
import base64
import secrets
from dataclasses import dataclass
from io import BytesIO
from random import SystemRandom

from PIL import Image, ImageDraw, ImageFont
from .sliders import SLIDER_TYPES, generate_slider
from .rotations import generate_rotation

TYPES = ("text", "digits", "arithmetic", *SLIDER_TYPES, "rotate")
ALPHABET = "ABDEFGHJLMNPQRT3456789"


@dataclass(frozen=True)
class GeneratedChallenge:
    answer: str
    payload: dict
    solution: dict | None = None


def generate(kind):
    if kind not in TYPES:
        raise ValueError("Unsupported challenge type")
    if kind in SLIDER_TYPES:
        payload, solution = generate_slider(kind)
        return GeneratedChallenge("", payload, solution)
    if kind == "rotate":
        payload, solution = generate_rotation()
        return GeneratedChallenge("", payload, solution)
    question = "请输入图片中的字符"
    if kind == "arithmetic":
        left, right = secrets.randbelow(8) + 1, secrets.randbelow(8) + 1
        operator = secrets.choice(("+", "-"))
        if operator == "-" and right > left:
            left, right = right, left
        label = f"{left} {operator} {right} = ?"
        answer = str(left + right if operator == "+" else left - right)
        question = "请输入图片中算式的结果"
    else:
        label = "".join(secrets.choice("23456789" if kind == "digits" else ALPHABET) for _ in range(5))
        answer = label
        if kind == "digits":
            question = "请输入图片中的数字"
    # Pillow's bundled default font avoids redistributing an unverified brand font.
    font = ImageFont.load_default(size=34)
    image = Image.new("RGB", (280, 88), "#f5f7ff")
    draw = ImageDraw.Draw(image)
    rng = SystemRandom()
    for _ in range(5):
        draw.line([(rng.randrange(280), rng.randrange(88)) for _ in range(2)], fill="#c8d4f2", width=1)
    for _ in range(3):
        x, y = rng.randrange(130), rng.randrange(40)
        draw.arc((x, y, x + 120, y + 48), 10, 240, fill="#d6ddf4", width=1)
    bounds = draw.textbbox((0, 0), label, font=font)
    x = (280 - (bounds[2] - bounds[0])) / 2 - bounds[0]
    y = (88 - (bounds[3] - bounds[1])) / 2 - bounds[1]
    draw.text((x, y), label, fill="#22365e", font=font)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return GeneratedChallenge(answer, {
        "instruction": question,
        "image": "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode(),
        "image_width": 280,
        "image_height": 88,
        "input_mode": "numeric" if kind in ("digits", "arithmetic") else "text",
    })
