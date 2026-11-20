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

from .grid import find_rows, header_end, normalize, row_fingerprints, unloaded_rows

# The content band, found from the header's line in each shot (phones differ in their status bar and the
# header's place); the numbers in brackets are a Pixel 6a's (1080 x 2400), used when no line is found.
ABOVE_LINE = 250  # the first shot keeps this much above the line: the title and the agent name  [TOP = 140]
BELOW_LINE = 18   # the others start this far below it, after a slight fade under the line      [HEADER = 410]
TOP = 140
HEADER = 410
BOTTOM = 370      # above the fade-out, the close button and the navigation bar (from the bottom)
NAV = 70          # the last shot is used down to the navigation bar
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


def _merge(copies: list[Image.Image]) -> Image.Image:
    """Copies of the same band (shots without scrolling, the last one may reach further down) as one band
    without Ingress's loading spinner, which moves over the medals while pictures load: the per-pixel
    median of 3 or more copies; of 2 the later one (it had more time to load the pictures); below the
    common height the tallest copy."""
    if len(copies) == 1:
        return copies[0]
    w, h = copies[0].width, min(c.height for c in copies)
    a = np.stack([np.asarray(c.crop((0, 0, w, h)), dtype=np.uint8) for c in copies])
    common = Image.fromarray((np.median(a, axis=0) if len(copies) > 2 else a[-1]).astype(np.uint8))
    tallest = max(copies, key=lambda c: c.height)
    out = tallest.copy()
    out.paste(common, (0, 0))
    return out


def stitch(shots: list[Image.Image], bottom: int = BOTTOM, max_diff: float = 6.0) -> Image.Image:
    """One long image from screenshots in scroll order (top of the list first).

    The first shot keeps everything below the status bar (the view's header). Where two shots overlap, the
    later one is used: there the rows are higher up on the screen, and Ingress loads a medal's picture only
    once it is well on the screen (the lowest row of a shot often shows empty circles or "RETRY").
    The last shot is used down to the navigation bar: the list can't scroll its last rows above the fade.
    Shots taken again without scrolling (at the end of the list) are merged without the loading spinner.
    Raises StitchError when two shots don't overlap.
    """
    if not shots:
        raise StitchError('no screenshots')
    ims = [normalize(s) for s in shots]
    last = len(ims) - 1
    bands = [im.crop((0, band_top(im, k == 0), im.width, im.height - (NAV if k == last else bottom)))
             for k, im in enumerate(ims)]
    groups: list[tuple[int, list[Image.Image]]] = [(0, [bands[0]])]  # (y in the output, copies of a band)
    for k in range(1, len(bands)):
        prev_y, copies = groups[-1]
        prev = copies[0]
        off, diff = offset(_gray(prev), _gray(bands[k]))
        if diff > max_diff:
            empty = [n for n in (k - 1, k) if unloaded_rows(bands[n])]
            if empty:
                raise StitchError(f'screenshot {empty[0] + 1}: some medals had not loaded yet (empty circles); '
                                  'wait until the pictures appear before taking the next screenshot')
            raise StitchError(f'screenshots {k} and {k + 1} do not overlap (best difference {diff:.1f}); '
                              'take them with less scrolling in between')
        if off == 0:
            copies.append(bands[k])  # not scrolled: the same band again
        else:
            groups.append((prev_y + off, [bands[k]]))
    merged = [(y, _merge(c)) for y, c in groups]
    out = Image.new('RGB', (bands[0].width, max(y + b.height for y, b in merged)))
    for y, band in merged:  # later shots over earlier ones
        out.paste(band, (0, y))
    return out


JOIN_DIST = 0.03  # the same medal row in two captures (as site.CORRECTION_DIST)
JOIN_RUN = 3      # rows in a row that must be the same: one row alone can look like another (Second Sunday …)


def _row_distance(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.abs(a - b).mean())


def join(new: Image.Image, old: Image.Image) -> Image.Image:
    """A new capture (stitched, from the top of the list) on top of the one before: an update needs screenshots
    only down to medals that were there before.

    From the bottom of the new capture up, the first row that, with the rows above it, is the same as rows of the
    old capture is where they meet: the new one down to there, then the old one below. Rows at the bottom of the
    new capture that aren't in the old one (under the fade of its last screenshot) are left out. When the new
    capture reaches the end of the list, it is used alone. Raises StitchError when they don't meet.
    """
    rows_new, rows_old = find_rows(new), find_rows(old)
    if not rows_old:
        return new
    fps_new = [row_fingerprints(new, r) for r in rows_new]
    fps_old = [row_fingerprints(old, r) for r in rows_old]
    for i in range(len(rows_new) - 1, JOIN_RUN - 2, -1):
        # New medals come in on top: the same row is at j <= i in the old capture; the closest run wins
        found = [(sum(_row_distance(fps_new[i - k], fps_old[j - k]) for k in range(JOIN_RUN)), j)
                 for j in range(min(i, len(rows_old) - 1), JOIN_RUN - 2, -1)
                 if all(_row_distance(fps_new[i - k], fps_old[j - k]) <= JOIN_DIST for k in range(JOIN_RUN))]
        if not found:
            continue
        j = min(found)[1]
        if j == len(rows_old) - 1:
            return new  # down to the end of the list
        cut_new = (rows_new[i][1] + (rows_new[i + 1][0] if i + 1 < len(rows_new) else rows_new[i][1] + 8)) // 2
        cut_old = (rows_old[j][1] + rows_old[j + 1][0]) // 2
        top = new.crop((0, 0, new.width, cut_new))
        rest = old.crop((0, cut_old, old.width, old.height))
        out = Image.new('RGB', (new.width, top.height + rest.height))
        out.paste(top, (0, 0))
        out.paste(rest, (0, top.height))
        return out
    raise StitchError('the new screenshots do not reach the medals already on your page; '
                      'take them down to medals that were there before, and a few rows more')
