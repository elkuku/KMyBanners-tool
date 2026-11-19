"""Match the medal rows of a screenshot to Bannergress banners by their pictures."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class Candidate:
    id: str
    rows: list[np.ndarray]  # picture rows, newest missions first (as in Ingress)
    info: dict = field(default_factory=dict)


@dataclass
class RowMatch:
    row: int
    id: str | None
    picture_row: int | None
    dist: float
    second: float  # distance of the best other banner (how sure the match is)


def row_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Mean colour difference of two fingerprint rows (COLS, FP, FP, 3), 0..1."""
    return float(np.abs(a - b).mean())


def match_rows(screen: list[np.ndarray], candidates: list[Candidate], threshold: float = 0.12) -> list[RowMatch]:
    """The best banner row for every screen row (id None when nothing is close enough)."""
    flat, owner = [], []
    for ci, c in enumerate(candidates):
        for r, fp in enumerate(c.rows):
            flat.append(fp)
            owner.append((ci, r))
    if not flat:
        return [RowMatch(k, None, None, 1.0, 1.0) for k in range(len(screen))]
    lib = np.stack(flat).reshape(len(flat), -1)
    out = []
    for k, s in enumerate(screen):
        d = np.abs(lib - s.reshape(1, -1)).mean(axis=1)
        order = np.argsort(d)
        best = int(order[0])
        ci, r = owner[best]
        second = next((float(d[j]) for j in order[1:] if owner[j][0] != ci), 1.0)
        if d[best] <= threshold:
            out.append(RowMatch(k, candidates[ci].id, r, float(d[best]), second))
        else:
            out.append(RowMatch(k, None, None, float(d[best]), second))
    return out


def group(matches: list[RowMatch]) -> list[dict]:
    """Banners in screenshot order: consecutive rows of the same banner form one entry;
    rows of a banner that come back later (missions done at another time) join its entry.
    Every unmatched row is an entry of its own (id None): the agent checks them one by one."""
    entries: list[dict] = []
    by_id: dict[str, dict] = {}
    for m in matches:
        if m.id is None:
            entries.append({'id': None, 'rows': [m.row], 'dist': [m.dist]})
            continue
        e = by_id.get(m.id)
        if e is None:
            e = {'id': m.id, 'rows': [], 'dist': [], 'second': []}
            by_id[m.id] = e
            entries.append(e)
        e['rows'].append(m.row)
        e['dist'].append(m.dist)
        e['second'].append(m.second)
    return entries


def rows_text(rows: list[int]) -> str:
    """[0, 1, 2, 7] -> "0-2,7" (data.js format)."""
    parts, start = [], None
    for i, r in enumerate(rows):
        if start is None:
            start = r
        if i + 1 == len(rows) or rows[i + 1] != r + 1:
            parts.append(f'{start}-{r}' if r != start else f'{r}')
            start = None
    return ','.join(parts)
