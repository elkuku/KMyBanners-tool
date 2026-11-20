"""Stitch phone screenshots of the "Mission medals" view into one long image.

Each screenshot shows the status bar on top, then the view's header (title, agent name, a line),
which stays in place while the medals scroll, and the close button (and the navigation bar) at the
bottom, over the medals. The first shot is used from below the status bar (with the header), the
others only between the header line and the close button:
consecutive shots are aligned by finding where the top of the next shot's content is in the
previous one.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

from .grid import header_end, normalize

# The content band, found from the header's line in each shot (phones differ in their status bar and the
# header's place); the numbers in brackets are a Pixel 6a's (1080 x 2400), used when no line is found.
ABOVE_LINE = 250  # the first shot keeps this much above the line: the title and the agent name  [TOP = 140]
BELOW_LINE = 18   # the others start this far below it, after a slight fade under the line      [HEADER = 410]
TOP = 140
HEADER = 410
BOTTOM = 370      # above the fade-out, the close button and the navigation bar (from the bottom)
SAMPLE = 4     # compare every 4th pixel


class StitchError(ValueError):
    pass


def _gray(im: Image.Image) -> np.ndarray:
    return np.asarray(im.convert('L'), dtype=np.float32)[:, ::SAMPLE]


def offset(prev: np.ndarray, nxt: np.ndarray, min_overlap: int = 250) -> tuple[int, float]:
    """Where row 0 of nxt is in prev (the scroll distance) and the mean difference there.

    Both are content bands (same width). Tries every offset with at least min_overlap rows in common.
    """
    h = prev.shape[0]
    best = (0, float('inf'))
    # Compare a strip from the top of nxt; small steps for the coarse search, then refine.
    strip = nxt[:min_overlap:2]
    for off in range(0, h - min_overlap + 1, 2):
        d = float(np.abs(prev[off:off + min_overlap:2] - strip).mean())
        if d < best[1]:
            best = (off, d)
    lo, hi = max(0, best[0] - 3), min(h - min_overlap, best[0] + 3)
    for off in range(lo, hi + 1):
        ov = min(h - off, nxt.shape[0])
        d = float(np.abs(prev[off:off + ov] - nxt[:ov]).mean())
        if off == lo or d < best[1]:
            best = (off, d)
    return best


def band_top(im: Image.Image, first: bool) -> int:
    """Where a shot's content starts: from its header line, else the Pixel 6a's numbers."""
    end = header_end(im, fallback=-1)  # the line's last row + 3
    if end < 0:
        return TOP if first else HEADER
    line = end - 3
    return max(0, line - ABOVE_LINE) if first else line + BELOW_LINE


def stitch(shots: list[Image.Image], bottom: int = BOTTOM, max_diff: float = 6.0) -> Image.Image:
    """One long image from screenshots in scroll order (top of the list first).

    The first shot keeps everything below the status bar (the view's header); later shots add
    what was scrolled in. Raises StitchError when two shots don't overlap.
    """
    if not shots:
        raise StitchError('no screenshots')
    ims = [normalize(s) for s in shots]
    bands = [im.crop((0, band_top(im, k == 0), im.width, im.height - bottom)) for k, im in enumerate(ims)]
    parts = [bands[0]]
    total = bands[0].height
    for k in range(1, len(bands)):
        a, b = _gray(bands[k - 1]), _gray(bands[k])
        off, diff = offset(a, b)
        if diff > max_diff:
            raise StitchError(f'screenshots {k} and {k + 1} do not overlap (best difference {diff:.1f}); '
                              'take them with less scrolling in between')
        new = bands[k].height - (bands[k - 1].height - off)
        if new <= 0:
            continue  # not scrolled
        parts.append(bands[k].crop((0, bands[k].height - new, bands[k].width, bands[k].height)))
        total += new
    out = Image.new('RGB', (parts[0].width, total))
    y = 0
    for p in parts:
        out.paste(p, (0, y))
        y += p.height
    return out
