"""An offset inner disk; the private correction angle is baked into its pixels."""
import math
from functools import lru_cache
from pathlib import Path
from random import SystemRandom
from typing import Literal

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

from .sliders import angle_distance, eased_progress, png, random_easing

SIZE, INNER_RADIUS, SEAM_BLUR = 256, 82, 2.5
RotationSource = Literal["preset", "procedural"]
PRESETS = ("starlock-garden.png", "starlock-workshop.png", "starlock-aurora.png")
PRESET_DIRECTORY = Path(__file__).resolve().parents[2] / "assets" / "rotation"


@lru_cache(maxsize=len(PRESETS))
def preset_image(name):
    with Image.open(PRESET_DIRECTORY / name) as image:
        return image.convert("RGB").resize((SIZE, SIZE), Image.Resampling.LANCZOS)


def rotation_image(source, rng):
    if source == "preset":
        # Vary the whole scene too: the lock's upright direction is not the correction angle.
        return preset_image(rng.choice(PRESETS)).rotate(rng.randrange(360), resample=Image.Resampling.BICUBIC)
    if source != "procedural":
        raise ValueError("Unsupported rotation image source")
    # The asymmetric bands cross the seam; concentric or repeated motifs would be ambiguous.
    image = Image.new("RGB", (SIZE, SIZE))
    colors = rng.choice((((208, 224, 247), (236, 212, 225)), ((186, 218, 239), (223, 217, 249)),
                         ((223, 220, 247), (248, 226, 209))))
    image.putdata([tuple(round(a * (1 - u) + b * u) for a, b in zip(*colors))
                   for y in range(SIZE) for x in range(SIZE) for u in [(x + y) / (2 * SIZE)]])
    draw = ImageDraw.Draw(image)
    palette = rng.sample(("#7495d2", "#e8a799", "#a49bce", "#609fba", "#e0c9a2"), 3)
    offset = rng.randint(-18, 18)
    draw.line([(0, 30 + offset), (75, 65 + offset), (150, 115 + offset), (256, 200 + offset)], fill=palette[0], width=40)
    draw.ellipse((110, -70, 330, 170), fill=palette[1])
    draw.ellipse((137, -42, 306, 139), fill=colors[0])
    draw.rounded_rectangle((8, 115, 82, 296), radius=32, fill=palette[2])
    draw.ellipse((125, 137, 193, 205), fill="#f2e8e4")
    draw.ellipse((141, 153, 177, 189), fill=palette[0])
    image = image.filter(ImageFilter.GaussianBlur(.6))
    return image


def generate_rotation(source: RotationSource = "preset", image=None):
    rng = SystemRandom()
    image = (ImageOps.fit(image.convert("RGB"), (SIZE, SIZE)).rotate(rng.randrange(360), resample=Image.Resampling.BICUBIC)
             if image is not None else rotation_image(source, rng))
    center = SIZE // 2
    band = Image.new("L", image.size)
    pen = ImageDraw.Draw(band)
    pen.ellipse((center - 87, center - 87, center + 87, center + 87), fill=255)
    pen.ellipse((center - 77, center - 77, center + 77, center + 77), fill=0)
    image = Image.composite(image.filter(ImageFilter.GaussianBlur(SEAM_BLUR)), image, band.filter(ImageFilter.GaussianBlur(1)))
    disk = Image.new("L", image.size)
    ImageDraw.Draw(disk).ellipse((center - INNER_RADIUS, center - INNER_RADIUS, center + INNER_RADIUS, center + INNER_RADIUS), fill=255)
    circle = Image.new("L", image.size)
    ImageDraw.Draw(circle).ellipse((3, 3, SIZE - 3, SIZE - 3), fill=255)
    outer = image.convert("RGBA")
    overlap = Image.new("L", image.size)
    radius = INNER_RADIUS - 3
    ImageDraw.Draw(overlap).ellipse((center - radius, center - radius, center + radius, center + radius), fill=255)
    outer.putalpha(ImageChops.subtract(circle, overlap))
    target_angle = rng.randint(75, 285)
    # Pillow positive angles are counterclockwise; CSS rotates the disk back clockwise.
    inner = image.rotate(target_angle, resample=Image.Resampling.BICUBIC).convert("RGBA")
    # Feather the seam over an overlapping ring rather than leaving a transparent white gap.
    inner.putalpha(disk.filter(ImageFilter.GaussianBlur(1.2)))
    motion = {"easing": random_easing(rng), "rotation": {"start_degrees": 0, "end_degrees": 360}}
    payload = {"instruction": "拖动滑块旋转内圈，让图案恢复完整", "image": png(outer), "image_width": SIZE,
               "image_height": SIZE, "piece_image": png(inner), "piece_width": SIZE, "piece_height": SIZE, "motion": motion}
    return payload, {"target_angle": target_angle, "angle_tolerance": 5, "rotation_period": 360}


def matches_rotation(payload, solution, answer):
    if not isinstance(answer, dict) or set(answer) != {"progress"}:
        return False
    u = answer["progress"]
    if type(u) not in (int, float) or not 0 <= u <= 1 or not math.isfinite(u):
        return False
    angle = eased_progress(payload["motion"]["easing"], u) * 360
    return angle_distance(angle, solution["target_angle"], 360) <= solution["angle_tolerance"]
