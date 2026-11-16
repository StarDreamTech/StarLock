"""Ordered text clicks and semantic image grids, with private answer geometry."""
import base64
import json
import math
import secrets
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from random import SystemRandom

from PIL import Image, ImageDraw, ImageFont, ImageOps

from .sliders import png

ASSETS = Path(__file__).resolve().parents[1] / 'assets'
CLICK_WIDTH, CLICK_HEIGHT, CLICK_COUNT = 300, 180, 3
CLICK_CHARACTERS = '星月山水风云花鸟鱼雨春夏秋冬红蓝绿紫光梦海林石竹火马金银木'
SEMANTIC_QUESTIONS = {
    'car': ('请选择所有用于道路行驶的小汽车', '请选择所有有四个车轮的小汽车'),
    'boat': ('请选择所有能在水上航行的交通工具', '请选择所有可以载人在水面行驶的交通工具'),
    'fruit': ('请选择所有可以食用的水果', '请选择所有生长在植物上的水果'),
}


def click_font():
    font = ImageFont.truetype(str(ASSETS / 'fonts' / 'NotoSansSC.ttf'), 34)
    font.set_variation_by_axes([600])
    return font


def generate_text_click():
    rng = SystemRandom()
    font = click_font()
    characters = rng.sample(CLICK_CHARACTERS, 6)
    targets = rng.sample(range(6), CLICK_COUNT)
    image = Image.new('RGB', (CLICK_WIDTH, CLICK_HEIGHT), '#f5f1fa')
    pen = ImageDraw.Draw(image)
    for _ in range(6):
        pen.line([(rng.randrange(CLICK_WIDTH), rng.randrange(CLICK_HEIGHT)) for _ in range(3)],
                 fill=rng.choice(('#e4d9ee', '#d9e3ed', '#e4dce6')), width=1)
    centers = [(x + rng.randint(-9, 9), y + rng.randint(-6, 6)) for y in (44, 132) for x in (50, 150, 250)]
    rng.shuffle(centers)
    for character, (x, y) in zip(characters, centers):
        letter = Image.new('RGBA', (80, 80))
        drawing = ImageDraw.Draw(letter)
        bounds = drawing.textbbox((0, 0), character, font=font)
        drawing.text((40 - (bounds[0] + bounds[2]) / 2, 40 - (bounds[1] + bounds[3]) / 2), character,
                     font=font, fill=rng.choice(('#604789', '#315d83', '#3e796a', '#88566e')))
        letter = letter.rotate(rng.randint(-18, 18), resample=Image.Resampling.BICUBIC)
        image.paste(letter, (x - 40, y - 40), letter)
    payload = {'instruction': '请依次点击 ' + ' → '.join('「' + characters[index] + '」' for index in targets),
               'image': png(image), 'image_width': CLICK_WIDTH, 'image_height': CLICK_HEIGHT,
               'required_clicks': CLICK_COUNT}
    solution = {'targets': [{'x': centers[index][0] / CLICK_WIDTH, 'y': centers[index][1] / CLICK_HEIGHT} for index in targets],
                'radius': 27}
    return payload, solution


def matches_text_click(payload, solution, answer):
    if not isinstance(answer, dict) or set(answer) != {'points'} or not isinstance(answer['points'], list):
        return False
    points = answer['points']
    if len(points) != len(solution['targets']):
        return False
    for point, target in zip(points, solution['targets']):
        if not isinstance(point, dict) or set(point) != {'x', 'y'}:
            return False
        if any(type(point[key]) not in (int, float) or not 0 <= point[key] <= 1 or not math.isfinite(point[key]) for key in ('x', 'y')):
            return False
        distance = math.hypot((point['x'] - target['x']) * payload['image_width'],
                              (point['y'] - target['y']) * payload['image_height'])
        if distance > solution['radius']:
            return False
    return True


@lru_cache(maxsize=1)
def semantic_catalog():
    return json.loads((ASSETS / 'semantic' / 'manifest.json').read_text())['images']


@lru_cache(maxsize=32)
def semantic_tile(filename):
    with Image.open(ASSETS / 'semantic' / filename) as original:
        image = ImageOps.fit(original.convert('RGB'), (192, 192), Image.Resampling.LANCZOS)
        stream = BytesIO()
        image.save(stream, 'JPEG', quality=84, optimize=True)
    return 'data:image/jpeg;base64,' + base64.b64encode(stream.getvalue()).decode()


def generate_semantic_grid():
    rng = SystemRandom()
    category = rng.choice(tuple(SEMANTIC_QUESTIONS))
    source = semantic_catalog()
    targets = rng.sample([item for item in source if item['category'] == category], rng.randint(2, 4))
    distractors = rng.sample([item for item in source if item['category'] != category], 9 - len(targets))
    items = targets + distractors
    rng.shuffle(items)
    tiles, expected = [], []
    for item in items:
        tile_id = 'tile_' + secrets.token_urlsafe(12)
        tiles.append({'id': tile_id, 'image': semantic_tile(item['file'])})
        if item['category'] == category:
            expected.append(tile_id)
    payload = {'instruction': rng.choice(SEMANTIC_QUESTIONS[category]), 'columns': 3, 'tiles': tiles}
    return payload, {'tile_ids': expected}


def matches_semantic_grid(payload, solution, answer):
    if not isinstance(answer, dict) or set(answer) != {'tile_ids'} or not isinstance(answer['tile_ids'], list):
        return False
    ids = answer['tile_ids']
    if not 1 <= len(ids) <= 9 or any(not isinstance(value, str) or not 1 <= len(value) <= 80 for value in ids):
        return False
    if len(ids) != len(set(ids)) or not set(ids).issubset({tile['id'] for tile in payload['tiles']}):
        return False
    return set(ids) == set(solution['tile_ids'])
