import random
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from ingress_banners import grid
from ingress_banners.grid import header_end
from ingress_banners.stitch import BELOW_LINE, BOTTOM, NAV, StitchError, band_top, stitch

Image.MAX_IMAGE_PIXELS = None
LONG = Path.home() / 'repos/nikp3h-ingress-stats/ingress-missions.png'
needs_long = pytest.mark.skipif(not LONG.exists(), reason='needs nikp3h screenshot')


def fake_screens(long: Image.Image, steps: list[int], bar: int = 140, h: int = 2400, width: int = 1080):
    """Phone screenshots of the view: a status bar of [bar] px with a changing clock, the view's header (with
    its line) that stays in place, the medals scrolled by [steps], a close button at the bottom."""
    line = header_end(long) - 3                   # the header line in the long screenshot
    head = line + BELOW_LINE                      # the header part of the view, down to below the line
    shots, y = [], 0
    for n, step in enumerate([0] + steps):
        y += step
        s = Image.new('RGB', (1080, h))
        s.paste(long.crop((0, 0, 1080, head)), (0, bar))
        s.paste(long.crop((0, head + y, 1080, head + y + h - bar - head)), (0, bar + head))
        d = ImageDraw.Draw(s)
        d.rectangle((0, 0, 1080, bar), fill=(0, 0, 0))
        d.text((40, bar // 3), f'17:{n:02d}', fill=(255, 255, 255))
        d.ellipse((480, h - 280, 600, h - 160), outline=(255, 255, 255), width=6)
        if width != 1080:  # a phone with another resolution
            s = s.resize((width, round(h * width / 1080)), Image.LANCZOS)
        shots.append(s)
    return shots


def check(long: Image.Image, shots: list[Image.Image], steps: list[int], bar: int, tolerance: float):
    out = stitch(shots)
    first = band_top(shots[0].resize((1080, round(shots[0].height * 1080 / shots[0].width))), True)
    start = first - bar                           # where the output starts in the long screenshot
    # the last shot is used down to the navigation bar
    assert out.height == 2400 - NAV - first + sum(steps)
    n = out.height - (BOTTOM - NAV)                # above the last shot's close button
    a = np.asarray(out.crop((0, 0, 1080, n)), dtype=np.int16)
    b = np.asarray(long.crop((0, start, 1080, start + n)), dtype=np.int16)
    assert np.abs(a - b).mean() < tolerance


@needs_long
@pytest.mark.parametrize('bar', [100, 140, 190])
def test_stitch_matches_original(bar):
    long = Image.open(LONG).convert('RGB').crop((0, 0, 1080, 12000))
    random.seed(bar)
    steps = [random.randint(600, 1250) for _ in range(5)]
    check(long, fake_screens(long, steps, bar=bar), steps, bar, 0.5)


@needs_long
def test_other_resolution():
    """A 1440 px wide phone: scaled to 1080 the medals are a little blurred, but the rows line up."""
    long = Image.open(LONG).convert('RGB').crop((0, 0, 1080, 12000))
    steps = [900, 1100, 1000]
    check(long, fake_screens(long, steps, width=1440), steps, 140, 3.0)


@needs_long
def test_no_overlap_fails():
    long = Image.open(LONG).convert('RGB').crop((0, 0, 1080, 12000))
    with pytest.raises(StitchError):
        stitch(fake_screens(long, [1900]))


@needs_long
def test_end_of_list_spinner_is_removed():
    """At the end of the list Ingress keeps a loading spinner moving over the medals: shots taken again
    without scrolling are merged without it."""
    long = Image.open(LONG).convert('RGB').crop((0, 0, 1080, 6000))
    shots = fake_screens(long, [1000, 0, 0])      # the last shot three times (the median removes the spinner)
    for n, s in enumerate(shots[1:]):            # a white "spinner" at a different place each time
        ImageDraw.Draw(s).line((200 + 150 * n, 900, 300 + 150 * n, 1000), fill=(255, 255, 255), width=8)
    out = stitch(shots)
    first = band_top(shots[0], True)
    n = out.height - (BOTTOM - NAV)
    a = np.asarray(out.crop((0, 0, 1080, n)), dtype=np.int16)
    b = np.asarray(long.crop((0, first - 140, 1080, first - 140 + n)), dtype=np.int16)
    assert np.abs(a - b).mean() < 0.5


def test_an_empty_cell_has_no_medal():
    """The end of a last row that isn't full: black, no ring."""
    assert not grid.has_medal(Image.new('RGB', (152, 152)))
