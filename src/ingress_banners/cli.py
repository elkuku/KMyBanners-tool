"""ingress-banners: from mission medal screenshots to a banner list.

  ingress-banners stitch shot1.png shot2.png … -o medals.png
  ingress-banners build medals.png --done done.json -o out/   # out/banners.json, out/img/
  ingress-banners site --repo . -o _site [--url https://…/]   # an agent's repo -> their page
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from . import grid, match
from .bannergress import Bannergress, entry
from .stitch import StitchError, stitch

Image.MAX_IMAGE_PIXELS = None


def medal_count(fp_row: np.ndarray) -> int:
    """Medals in a row (empty cells are black)."""
    return int(sum(1 for cell in fp_row if cell.mean() > 0.04))


def read_done(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding='utf-8'))
    if isinstance(data, dict):
        data = data.get('member') or data.get('hydra:member') or []
    return [{'id': d.get('bannerId') or d['id'], 'picture': d.get('picture'), 'title': d.get('title')} for d in data]


def build(shot: Path, done: Path, out: Path, cache: Path, threshold: float, margin: float) -> dict:
    bg = Bannergress(cache)
    im = grid.normalize(Image.open(shot))
    rows = grid.find_rows(im)
    screen = [grid.row_fingerprints(im, r) for r in rows]
    cands = [match.Candidate(d['id'], grid.picture_rows(bg.picture(d['picture'])))
             for d in read_done(done) if d.get('picture')]
    ms = match.match_rows(screen, cands, threshold=threshold)
    for m in ms:  # too close to another banner: let the agent decide
        if m.id and m.second - m.dist <= margin:
            m.id, m.picture_row = None, None
    entries = match.group(ms)
    (out / 'img').mkdir(parents=True, exist_ok=True)
    banners = []
    for i, e in enumerate(entries):
        first = e['rows'][0]
        run = 1
        while run < len(e['rows']) and e['rows'][run] == first + run:
            run += 1
        img = f'img/m{i:03d}.jpg'
        grid.medal_picture(im, rows, first, run).save(out / img, quality=90)
        b = {'i': i, 'rows': match.rows_text(e['rows']), 'count': sum(medal_count(screen[r]) for r in e['rows']),
             'img': img}
        if e['id']:
            b.update({'status': 'match', 'score': round(max(e['dist']), 3)})
            b.update(entry(bg.banner(e['id'])))
        else:
            b.update({'status': 'review', 'score': round(min(e['dist']), 3)})
        banners.append(b)
    result = {'rows': [list(r) for r in rows], 'banners': banners}
    (out / 'banners.json').write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding='utf-8')
    return result


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog='ingress-banners', description=__doc__.split('\n')[0])
    sub = p.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('stitch', help='stitch screenshots (in scroll order) into one image')
    s.add_argument('shots', nargs='+', type=Path)
    s.add_argument('-o', '--out', type=Path, required=True)
    b = sub.add_parser('build', help='match the medal rows with the Bannergress done list')
    b.add_argument('shot', type=Path)
    b.add_argument('--done', type=Path, required=True, help='done list JSON (bannerId/id, picture)')
    b.add_argument('-o', '--out', type=Path, required=True)
    b.add_argument('--cache', type=Path, default=Path('.cache/bannergress'))
    b.add_argument('--threshold', type=float, default=0.10)
    b.add_argument('--margin', type=float, default=0.005)
    w = sub.add_parser('site', help="build an agent's page from their repo (inbox, capture, done list)")
    w.add_argument('--repo', type=Path, default=Path('.'))
    w.add_argument('-o', '--out', type=Path, required=True)
    w.add_argument('--url', default='', help='the page URL (for the link preview)')
    w.add_argument('--cache', type=Path)
    a = p.parse_args(argv)
    if a.cmd == 'site':
        from .site import build_site
        built = build_site(a.repo, a.out, a.url, a.cache) is not None
        if os.environ.get('GITHUB_OUTPUT'):  # tell the workflow whether there is a page to deploy
            with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
                f.write(f'built={str(built).lower()}\n')
        return 0
    if a.cmd == 'stitch':
        try:
            im = stitch([Image.open(f) for f in a.shots])
        except StitchError as e:
            print(e, file=sys.stderr)
            return 1
        im.save(a.out)
        print(f'{a.out}: {im.width} x {im.height}, {len(grid.find_rows(im))} medal rows')
    else:
        r = build(a.shot, a.done, a.out, a.cache, a.threshold, a.margin)
        bs = r['banners']
        print(f'{len(r["rows"])} rows: {sum(1 for x in bs if x["status"] == "match")} banners matched, '
              f'{sum(1 for x in bs if x["status"] == "review")} groups of rows to review')
    return 0


if __name__ == '__main__':
    sys.exit(main())
