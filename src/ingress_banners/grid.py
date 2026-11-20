"""The medal grid of Ingress's "Mission medals" view: rows, cells and medal fingerprints.

All geometry is for a screenshot scaled to WIDTH px. The view shows 6 round medals per row,
newest first, under a header with the title and the agent name.
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image

WIDTH = 1080
COLS = 6
GRID_X0, GRID_X1 = 84, 996  # the 6 cells, 152 px each
CELL = (GRID_X1 - GRID_X0) / COLS
FP = 8  # fingerprint size (FP x FP colour pixels)


def normalize(im: Image.Image) -> Image.Image:
    """RGB at WIDTH px wide (phones with other widths are scaled)."""
    im = im.convert('RGB')
    if im.width != WIDTH:
        im = im.resize((WIDTH, round(im.height * WIDTH / im.width)), Image.LANCZOS)
    return im


def header_end(im: Image.Image, fallback: int = 280) -> int:
    """The y below the header's line (a thin bright line across the view, within the first 800 px)."""
    g = np.asarray(im.convert('L').crop((100, 0, 980, min(800, im.height))), dtype=np.float32)
    ys = np.nonzero((g > 60).mean(axis=1) > 0.9)[0]
    # The first thin run (a slice through bright medals can be bright across too, but is thicker or later)
    k = 0
    while k < len(ys):
        end = k
        while end + 1 < len(ys) and ys[end + 1] == ys[end] + 1:
            end += 1
        if end - k < 5:
            return int(ys[end]) + 3
        k = end + 1
    return fallback


def find_rows(im: Image.Image, header: int | None = None) -> list[tuple[int, int]]:
    """The y ranges of the medal rows: bright bands between dark gaps, below the header."""
    if header is None:
        header = header_end(im)
    g = np.asarray(im.convert('L').crop((80, 0, 1000, im.height)).resize((115, im.height)))
    bright = g.max(axis=1) >= 40
    runs: list[list[int]] = []
    y, h = 0, len(bright)
    while y < h:
        if bright[y]:
            start = y
            while y < h and bright[y]:
                y += 1
            runs.append([start, y])
        else:
            y += 1
    runs = [r for r in runs if r[0] > header]
    # A dark line inside a medal splits a row: join runs with a small gap that stay one row high.
    merged: list[list[int]] = []
    for a, b in runs:
        if merged and a - merged[-1][1] < 8 and b - merged[-1][0] <= 150:
            merged[-1][1] = b
        else:
            merged.append([a, b])
    return [(a, b) for a, b in merged if b - a >= 60]


def _fingerprint(cell: Image.Image) -> np.ndarray:
    """The inside of a round medal (no ring, no background) as a small colour image."""
    w, h = cell.size
    m = 0.22  # cut the ring and the corners
    inner = cell.crop((round(w * m), round(h * m), round(w * (1 - m)), round(h * (1 - m))))
    return np.asarray(inner.resize((FP, FP), Image.BOX), dtype=np.float32) / 255.0


def row_cells(im: Image.Image, row: tuple[int, int]) -> list[Image.Image]:
    a, b = row
    c = (a + b) / 2
    return [im.crop((round(GRID_X0 + k * CELL), round(c - CELL / 2), round(GRID_X0 + (k + 1) * CELL), round(c + CELL / 2)))
            for k in range(COLS)]


def row_fingerprints(im: Image.Image, row: tuple[int, int]) -> np.ndarray:
    """(COLS, FP, FP, 3); an empty cell (black) is all zeros."""
    return np.stack([_fingerprint(c) for c in row_cells(im, row)])


def picture_rows(pic: Image.Image) -> list[np.ndarray]:
    """A Bannergress banner picture (6 medals per row, about 100 px each) as fingerprint rows."""
    pic = pic.convert('RGB')
    cw = pic.width / COLS
    n = max(1, round(pic.height / cw))
    rh = pic.height / n
    rows = []
    for r in range(n):
        cells = [pic.crop((round(k * cw), round(r * rh), round((k + 1) * cw), round((r + 1) * rh))) for k in range(COLS)]
        rows.append(np.stack([_fingerprint(c) for c in cells]))
    return rows


def medal_picture(im: Image.Image, rows: list[tuple[int, int]], first: int, count: int, width: int = 330) -> Image.Image:
    """The medals of rows first..first+count-1 as one picture (the page's img/mNNN.jpg)."""
    top = rows[first][0] - 1
    end = rows[first + count][0] - 2 if first + count < len(rows) else rows[first + count - 1][1] + 7
    crop = im.crop((86, top, 994, end))
    return crop.resize((width, round(crop.height * width / crop.width)), Image.LANCZOS)


def unloaded(cell: Image.Image) -> bool:
    """A medal whose picture didn't load: a white/grey ring (loaded medals have an orange one) around black.

    The ring is the brightest pixel on each ray from the centre between 38 and 50 % of the cell (it is thin).
    """
    a = np.asarray(cell.convert('RGB'), dtype=np.float32)
    h, w, _ = a.shape
    peaks = []
    for k in range(72):
        t = 2 * math.pi * k / 72
        pts = [a[min(h - 1, int(h / 2 + r * h * math.sin(t))), min(w - 1, int(w / 2 + r * w * math.cos(t)))]
               for r in np.linspace(0.38, 0.495, 12)]
        peaks.append(max(pts, key=lambda p: p.sum()))
    ring = np.median(np.array(peaks), axis=0)
    if max(ring) < 60:
        return False  # no medal there (the end of a row)
    inner = a[int(h * .25):int(h * .75), int(w * .25):int(w * .75)].mean()
    return ring[0] - ring[2] <= 60 and inner < 25


def unloaded_rows(im: Image.Image, top: int | None = None, bottom: int | None = None) -> list[int]:
    """The y of medal rows below [top] (default: the header line) and above [bottom] (whole rows only) with
    medals that didn't load."""
    bottom = im.height if bottom is None else bottom
    return [a for a, b in find_rows(im, header=top) if b <= bottom and any(unloaded(c) for c in row_cells(im, (a, b)))]
