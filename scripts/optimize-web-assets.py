"""Build small browser derivatives while retaining the original brand artwork."""
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
assets = [(ROOT / 'assets/brand/starlock-hero-v2.png', (1600, 800))]
assets += [(path, (768, 768)) for path in (ROOT / 'assets/rotation').glob('starlock-*.png')]
for source, size in assets:
    target = source.with_suffix('.webp')
    with Image.open(source) as original:
        image = original.convert('RGB')
        image.thumbnail(size, Image.Resampling.LANCZOS)
        image.save(target, 'WEBP', quality=84, method=6)
    assert target.stat().st_size <= 300_000, target
    print(f'{target.relative_to(ROOT)}: {target.stat().st_size:,} bytes')
