import random
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from ingress_banners.stitch import BOTTOM, HEADER, TOP, StitchError, stitch

Image.MAX_IMAGE_PIXELS = None
LONG = Path.home() / 'repos/nikp3h-ingress-stats/ingress-missions.png'


def fake_screens(long: Image.Image, steps: list[int], h: int = 2400) -> list[Image.Image]:
    """Phone screenshots of the view: status bar with a changing clock, a header that stays in place,
    close button at the bottom."""
    shots, y = [], 0
    head = HEADER - TOP
    for n, step in enumerate([0] + steps):
        y += step
        s = Image.new('RGB', (1080, h))
        s.paste(long.crop((0, 0, 1080, head)), (0, TOP))
        s.paste(long.crop((0, head + y, 1080, head + y + h - HEADER)), (0, HEADER))
        d = ImageDraw.Draw(s)
        d.rectangle((0, 0, 1080, TOP), fill=(0, 0, 0))
        d.text((40, 40), f'17:{n:02d}', fill=(255, 255, 255))
        d.ellipse((480, h - 280, 600, h - 160), outline=(255, 255, 255), width=6)
        shots.append(s)
    return shots


@pytest.mark.skipif(not LONG.exists(), reason='needs nikp3h screenshot')
def test_stitch_matches_original():
    long = Image.open(LONG).convert('RGB').crop((0, 0, 1080, 12000))
    random.seed(1)
    steps = [random.randint(600, 1300) for _ in range(5)]
    out = stitch(fake_screens(long, steps))
    n = sum(steps) + 2400 - TOP - BOTTOM
    assert out.height == n
    a = np.asarray(out, dtype=np.int16)
    b = np.asarray(long.crop((0, 0, 1080, n)), dtype=np.int16)
    assert np.abs(a - b).mean() < 0.5


@pytest.mark.skipif(not LONG.exists(), reason='needs nikp3h screenshot')
def test_no_overlap_fails():
    long = Image.open(LONG).convert('RGB').crop((0, 0, 1080, 12000))
    with pytest.raises(StitchError):
        stitch(fake_screens(long, [1900]))
