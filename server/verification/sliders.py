"""Puzzle rendering and original-image coordinate checks; no client-supplied target."""
import base64
import math
from io import BytesIO
from random import SystemRandom

from PIL import Image, ImageChops, ImageDraw, ImageFilter

SLIDER_TYPES = ("slider", "bezier_slider")
WIDTH, HEIGHT, PIECE = 320, 180, 64
MARGIN, HOLE_GAP = 8, 10
MIN_TRAVEL, MAX_TRAVEL = 96, 204
SHAPES = {"jigsaw": 360, "star": 72, "square": 90, "rectangle": 180}


def path_point(path, progress):
    points = path["control_points"]
    if path["kind"] == "linear":
        weights = (1 - progress, progress)
    else:
        u = progress
        weights = ((1 - u) ** 3, 3 * (1 - u) ** 2 * u, 3 * (1 - u) * u ** 2, u ** 3)
    return tuple(sum(weight * point[axis] for weight, point in zip(weights, points)) for axis in ("x", "y"))


def eased_progress(easing, progress):
    if not easing or easing["kind"] == "linear" or progress in (0, 1):
        return progress
    a, b = easing["control_points"]
    # Input is the curve's x, not its parameter; match CSS cubic-bezier semantics.
    low, high = 0., 1.
    for _ in range(30):
        t = (low + high) / 2
        x = 3 * (1 - t) ** 2 * t * a["x"] + 3 * (1 - t) * t ** 2 * b["x"] + t ** 3
        if x < progress:
            low = t
        else:
            high = t
    t = (low + high) / 2
    return 3 * (1 - t) ** 2 * t * a["y"] + 3 * (1 - t) * t ** 2 * b["y"] + t ** 3


def motion_state(payload, progress):
    motion = payload.get("motion", {})
    parameter = eased_progress(motion.get("easing"), progress)
    x, y = path_point(payload["path"], parameter)
    rotation = motion.get("rotation", {"start_degrees": 0, "end_degrees": 0})
    angle = rotation["start_degrees"] + parameter * (rotation["end_degrees"] - rotation["start_degrees"])
    return x, y, angle


def angle_distance(a, b, period):
    return abs((a - b + period / 2) % period - period / 2)


def separated(a, b):
    return abs(a["x"] - b["x"]) >= PIECE + HOLE_GAP or abs(a["y"] - b["y"]) >= PIECE + HOLE_GAP


def random_easing(rng):
    x1, y1, x2, y2 = rng.choice(((.42, 0, .58, 1), (.42, 0, 1, 1), (0, 0, .58, 1)))
    return {"kind": "cubic_bezier", "control_points": [{"x": x1, "y": y1}, {"x": x2, "y": y2}]}


def slider_layout(kind, rng):
    if kind == "slider":
        y = rng.randint(28, 88)
        points = [(MARGIN, y), (WIDTH - PIECE - MARGIN, y)]
    else:
        points = [(MARGIN, rng.randint(65, 104)), (rng.randint(72, 96), rng.randint(12, 30)),
                  (rng.randint(164, 192), rng.randint(90, 106)), (WIDTH - PIECE - MARGIN, rng.randint(28, 66))]
    path = {"kind": "linear" if kind == "slider" else "cubic_bezier",
            "control_points": [{"x": x, "y": y} for x, y in points]}
    easing = random_easing(rng)
    start_angle, end_angle = rng.choice(((-80, 60), (65, -85), (-100, 80)))
    motion = {"easing": easing,
              "rotation": {"start_degrees": start_angle, "end_degrees": end_angle}}
    payload = {"path": path, "motion": motion}
    start = {"x": points[0][0], "y": points[0][1]}
    candidates = []
    for n in range(350, 851, 5):
        u = n / 1000
        x, y, angle = motion_state(payload, u)
        target = {"x": round(x), "y": round(y), "angle": angle, "progress": u}
        if separated(target, start) and MIN_TRAVEL <= math.hypot(target["x"] - start["x"], target["y"] - start["y"]) <= MAX_TRAVEL:
            candidates.append(target)
    # Finite construction: valid ranges leave an interior target for every motion profile.
    if not candidates:
        raise ValueError("No safe slider target")
    target = rng.choice(candidates)
    shape = rng.choice(tuple(SHAPES))
    target["shape"] = shape
    decoys = []
    for n in range(1, 101):
        u = n / 100
        x, y, angle = motion_state(payload, u)
        hole = {"x": round(x), "y": round(y), "progress": u,
                "angle": angle + SHAPES[shape] * .35, "shape": shape}
        if separated(hole, start) and separated(hole, target):
            decoys.append(hole)
    if not decoys:
        raise ValueError("No safe distractor")
    distractors = [rng.choice(decoys)]
    # An optional off-path hole uses another shape, so it cannot become an alternate fit.
    off_path = [{"x": x, "y": y} for x in (88, 168, 248) for y in (8, 108)
                if all(separated({"x": x, "y": y}, old) for old in [start, target, *distractors])]
    if off_path:
        hole = rng.choice(off_path)
        hole.update(shape=rng.choice([s for s in SHAPES if s != shape]), angle=rng.randrange(360))
        distractors.append(hole)
    return {**payload, "shape": shape, "target": target, "distractors": distractors}


def shape_mask(kind, angle=0):
    scale = 4
    mask = Image.new("L", (PIECE * scale, PIECE * scale))
    draw = ImageDraw.Draw(mask)
    box = lambda values: tuple(round(v * scale) for v in values)
    if kind == "star":
        vertices = [(32 + (27 if n % 2 == 0 else 12) * math.cos(-math.pi / 2 + n * math.pi / 5),
                     32 + (27 if n % 2 == 0 else 12) * math.sin(-math.pi / 2 + n * math.pi / 5)) for n in range(10)]
        draw.polygon([(round(x * scale), round(y * scale)) for x, y in vertices], fill=255)
    elif kind == "square":
        draw.rectangle(box((13, 13, 51, 51)), fill=255)
    elif kind == "rectangle":
        draw.rectangle(box((8, 19, 56, 45)), fill=255)
    else:
        draw.rounded_rectangle(box((15, 15, 49, 49)), radius=3 * scale, fill=255)
        draw.ellipse(box((25, 5, 39, 21)), fill=255)
        draw.ellipse(box((43, 25, 59, 39)), fill=255)
        draw.ellipse(box((9, 25, 25, 39)), fill=0)
        draw.ellipse(box((25, 43, 39, 59)), fill=0)
    return mask.rotate(-angle, resample=Image.Resampling.BICUBIC).resize((PIECE, PIECE), Image.Resampling.LANCZOS)


def png(image):
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


def generate_slider(kind):
    rng = SystemRandom()
    layout = slider_layout(kind, rng)
    path, target = layout["path"], layout["target"]
    target_x, target_y = target["x"], target["y"]

    # A fresh procedural scene avoids shipping a labelled stock-image answer set.
    image = Image.new("RGB", (WIDTH, HEIGHT))
    phase = rng.uniform(0, math.tau)
    image.putdata([(int(20 + 18 * x / WIDTH), int(35 + 30 * y / HEIGHT),
                    int(72 + 28 * math.sin(x / 95 + phase) ** 2 + 28 * y / HEIGHT))
                   for y in range(HEIGHT) for x in range(WIDTH)])
    draw = ImageDraw.Draw(image)
    for _ in range(40):
        x, y, radius = rng.randrange(WIDTH), rng.randrange(HEIGHT), rng.choice((1, 1, 2))
        draw.ellipse((x, y, x + radius, y + radius), fill=rng.choice(("#9eaff2", "#718ac8", "#c6d8ff")))
    cx, cy = rng.randint(90, 240), rng.randint(30, 110)
    for radius in (32, 49, 69, 92):
        draw.ellipse((cx - radius, cy - radius // 2, cx + radius, cy + radius // 2), outline="#506ca7", width=1)
    for index in range(3):
        y = 130 + index * 18
        draw.polygon([(0, y + 25), (0, y), (70, y - rng.randint(12, 30)),
                      (160, y + 8), (250, y - rng.randint(15, 35)), (WIDTH, y),
                      (WIDTH, HEIGHT), (0, HEIGHT)], fill=(40 + index * 10, 58 + index * 12, 102 + index * 16))
    if kind == "bezier_slider":
        guide = [tuple(round(v + PIECE / 2) for v in path_point(path, n / 100)) for n in range(101)]
        draw.line(guide, fill="#7591c4", width=1)

    mask = shape_mask(layout["shape"])
    # Undo the target's clockwise display rotation before cutting the canonical piece.
    piece = image.crop((target_x, target_y, target_x + PIECE, target_y + PIECE)).rotate(
        target["angle"], resample=Image.Resampling.BICUBIC).convert("RGBA")
    piece.putalpha(mask)
    border = ImageChops.subtract(mask, mask.filter(ImageFilter.MinFilter(3)))
    piece.paste("#dbeaff", (0, 0), border)
    for hole in [target, *layout["distractors"]]:
        mask = shape_mask(hole["shape"], hole["angle"])
        border = ImageChops.subtract(mask, mask.filter(ImageFilter.MinFilter(3)))
        patch = image.crop((hole["x"], hole["y"], hole["x"] + PIECE, hole["y"] + PIECE))
        patch = Image.blend(patch, Image.new("RGB", patch.size, "#050e20"), .78)
        patch.paste("#9bb5da", (0, 0), border)
        image.paste(patch, (hole["x"], hole["y"]), mask)
    payload = {"instruction": "拖动滑块，让图形的位置与角度同时贴合缺口",
               "image": png(image), "image_width": WIDTH, "image_height": HEIGHT,
               "piece_image": png(piece), "piece_width": PIECE, "piece_height": PIECE,
               "path": path, "motion": layout["motion"]}
    return payload, {"target_x": target_x, "target_y": target_y, "tolerance": 4,
                     "target_angle": target["angle"], "angle_tolerance": 5, "rotation_period": SHAPES[layout["shape"]]}


def matches_slider(payload, solution, answer):
    if not isinstance(answer, dict) or set(answer) != {"progress"}:
        return False
    progress = answer["progress"]
    if type(progress) not in (int, float) or not 0 <= progress <= 1 or not math.isfinite(progress):
        return False
    x, y, angle = motion_state(payload, progress)
    return (math.hypot(x - solution["target_x"], y - solution["target_y"]) <= solution["tolerance"] and
            ("target_angle" not in solution or angle_distance(angle, solution["target_angle"], solution["rotation_period"]) <= solution["angle_tolerance"]))
