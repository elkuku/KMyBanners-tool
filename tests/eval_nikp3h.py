"""Spike: match nikp3h's screenshot against the done list and compare with data.js (hand-made).

  .venv/bin/python tests/eval_nikp3h.py <ingress-missions.png> <data.js> <done.json> [cache dir]
"""
import json
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))
from ingress_banners import grid, match  # noqa: E402
from ingress_banners.bannergress import Bannergress  # noqa: E402

Image.MAX_IMAGE_PIXELS = None


def truth_rows(data_js: Path) -> dict[int, str | None]:
    src = data_js.read_text(encoding='utf-8')
    banners = json.loads(src[src.index('['):src.rindex(']') + 1])
    out = {}
    for b in banners:
        for part in b['rows'].split(','):
            a, _, c = part.partition('-')
            for r in range(int(a), int(c or a) + 1):
                out[r] = b.get('id')
    return out


def main():
    shot, data_js, done_json = map(Path, sys.argv[1:4])
    cache = Path(sys.argv[4]) if len(sys.argv) > 4 else Path('.cache/bannergress')
    bg = Bannergress(cache)
    im = grid.normalize(Image.open(shot))
    rows = grid.find_rows(im)
    screen = [grid.row_fingerprints(im, r) for r in rows]
    done = json.loads(done_json.read_text())
    cands = [match.Candidate(d['bannerId'], grid.picture_rows(bg.picture(d['picture'])))
             for d in done if d.get('picture')]
    print(f'{len(rows)} rows, {len(cands)} candidates')
    truth = truth_rows(data_js)
    ms = match.match_rows(screen, cands, threshold=1.0)  # all, to see distances
    ids_done = {c.id for c in cands}
    ok = [m.dist for m in ms if truth.get(m.row) and m.id == truth[m.row]]
    wrong = [m for m in ms if truth.get(m.row) in ids_done and m.id != truth[m.row]]
    absent = [m.dist for m in ms if truth.get(m.row) not in ids_done]
    q = lambda xs, p: sorted(xs)[min(len(xs) - 1, int(len(xs) * p))] if xs else None  # noqa: E731
    print(f'right rows: {len(ok)}  dist median {q(ok, .5):.3f} p95 {q(ok, .95):.3f} max {max(ok):.3f}')
    print(f'wrong rows (banner on done list): {len(wrong)}')
    for m in wrong[:15]:
        print(f'  row {m.row}: got {m.id} {m.dist:.3f}, truth {truth[m.row]}')
    if absent:
        print(f'rows of banners not on the done list: {len(absent)}  dist min {min(absent):.3f} median {q(absent, .5):.3f}')


if __name__ == '__main__':
    main()
