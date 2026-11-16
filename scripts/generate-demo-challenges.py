"""Generate public, answer-bearing samples exclusively for the static playground."""
import json
import sys
from pathlib import Path
from random import SystemRandom

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'server'))
from verification.generators import TYPES, generate
from verification.image_sets import system_catalog
from verification.selections import matches_text_click, matches_semantic_grid
from verification.rotations import matches_rotation
from verification.sliders import matches_slider, motion_state, eased_progress

rng = SystemRandom()
images = list(system_catalog().values())
samples = []
for kind in TYPES:
    for index in range(4):
        source = None
        if kind == 'rotate' or (kind in ('slider', 'bezier_slider') and index < 2):
            with Image.open(rng.choice(images)['path']) as original:
                source = original.convert('RGB').copy()
        generated = generate(kind, image=source)
        challenge = dict(decision='challenge', challenge_id=f'demo_{kind}_{index}',
                         challenge_type=kind, expires_in=120, payload=generated.payload)
        if kind == 'text_click':
            assert matches_text_click(generated.payload, generated.solution, {'points': generated.solution['targets']})
        elif kind == 'semantic_grid':
            assert matches_semantic_grid(generated.payload, generated.solution, generated.solution)
        elif generated.solution is not None:
            low, high = 0., 1.
            for _ in range(40):
                middle = (low + high) / 2
                current = (eased_progress(generated.payload['motion']['easing'], middle) * 360
                           if kind == 'rotate' else motion_state(generated.payload, middle)[0])
                target = generated.solution['target_angle' if kind == 'rotate' else 'target_x']
                if current < target:
                    low = middle
                else:
                    high = middle
            matches = matches_rotation if kind == 'rotate' else matches_slider
            assert matches(generated.payload, generated.solution, {'progress': (low + high) / 2})
        samples.append(dict(challenge=challenge, answer=generated.answer, solution=generated.solution))

output = ROOT / 'examples/static-demo/public/challenges.json'
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(samples, ensure_ascii=False, separators=(',', ':')) + '\n')
assert len(samples) == len(TYPES) * 4
for kind in TYPES:
    directory = output.parent / 'challenges' / kind
    directory.mkdir(parents=True, exist_ok=True)
    for index, item in enumerate(item for item in samples if item['challenge']['challenge_type'] == kind):
        (directory / f'{index}.json').write_text(json.dumps(item, ensure_ascii=False, separators=(',', ':')) + '\n')
print(f'Generated {len(samples)} public demo samples, {output.stat().st_size:,} bytes. Answers are public and evaluated in the browser.')
