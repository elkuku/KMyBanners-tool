"""Build an agent's banner page from their repo (the template layout).

The agent's repo:
  config.json         {"agent": "name"}
  inbox/<batch>/*.png  new screenshots from the app (the newest batch is used), in scroll order
  captures/<batch>/    the screenshots of earlier builds (moved here from the inbox)
  capture/medals.jpg   the stitched screenshot (written here from the inbox; kept for later builds): a new batch
                       from the top of the list down to medals that were there before is joined onto it
  done.json            the Bannergress done list (Bannergress /bnrs format or AgentTools export)
  corrections.json     rows the agent decided in the app: {"rows": [{"fp": …, "end": …, "id": …|null, "name": …,
                       "single": true?}]}; end is the row's place from the end of the list (0: the last row)
  notes.json           optional notes per banner id
The page goes to the output directory (the Pages artifact).
"""
from __future__ import annotations

import base64
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from . import grid, match
from .bannergress import Bannergress, entry
from .nearby import nearby_options
from .stitch import join, stitch

Image.MAX_IMAGE_PIXELS = None
SITE = Path(__file__).parent / 'site'
SHOTS = ('.png', '.jpg', '.jpeg', '.webp')
TILE, SCALE = 1500, 0.5
SPECOPS = [(500, 'black'), (200, 'platinum'), (100, 'gold'), (25, 'silver'), (5, 'bronze')]
CORRECTION_DIST = 0.03  # a row the agent decided before is the same row again


# --- inputs ------------------------------------------------------------------------------------

def take_inbox(repo: Path) -> Path | None:
    """Stitch the newest screenshot batch onto capture/medals.jpg and move the inbox to captures/."""
    inbox = repo / 'inbox'
    if not inbox.is_dir():
        return None
    batches = sorted([d for d in inbox.iterdir() if d.is_dir()]) or [inbox]
    shots = sorted(f for f in batches[-1].iterdir() if f.suffix.lower() in SHOTS)
    if not shots:
        return None
    im = stitch([Image.open(f) for f in shots])
    out = repo / 'capture' / 'medals.jpg'
    joined = out.exists()
    if joined:
        im = join(im, grid.normalize(Image.open(out)))
    out.parent.mkdir(exist_ok=True)
    im.save(out, quality=92, optimize=True)
    # Kept: a later build can stitch them again; earlier batches never built (an upload replaced) too
    archive = repo / 'captures'
    loose = [f for f in inbox.iterdir() if f.is_file() and f.name != '.gitkeep']
    if loose:
        stamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H%M%SZ')
        (archive / stamp).mkdir(parents=True, exist_ok=True)
        for f in loose:
            shutil.move(f, archive / stamp / f.name)
    for d in (d for d in inbox.iterdir() if d.is_dir()):
        archive.mkdir(exist_ok=True)
        target = archive / d.name
        if target.exists():
            shutil.rmtree(target)
        shutil.move(d, target)
    print(f'{len(shots)} screenshots from {batches[-1].relative_to(repo)} -> {out.relative_to(repo)} '
          f'({im.height} px{", joined onto the capture before" if joined else ""})')
    missing = grid.unloaded_rows(im)
    if missing:
        print(f'  medals that did not load in {len(missing)} rows (y {", ".join(map(str, missing[:10]))})')
    return out


def read_done(path: Path) -> list[dict]:
    """The done list, newest first: Bannergress /bnrs objects or the AgentTools export."""
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding='utf-8'))
    if isinstance(data, dict):
        data = data.get('banners') or data.get('member') or data.get('hydra:member') or []
    out = []
    for n, d in enumerate(data):
        out.append({
            'id': d.get('bannerId') or d['id'],
            'title': (d.get('title') or '').strip(),
            'missions': d.get('missions') if isinstance(d.get('missions'), int) else d.get('numberOfMissions'),
            'pos': d.get('position', n),
            'lat': d.get('startLatitude'),
            'lng': d.get('startLongitude'),
            'doneAt': d.get('doneAt'),
            'picture': d.get('picture'),
        })
    return sorted(out, key=lambda d: d['pos'])


def fp_encode(fp: np.ndarray) -> str:
    return base64.b64encode((fp * 255).round().astype(np.uint8).tobytes()).decode()


def fp_decode(s: str) -> np.ndarray:
    a = np.frombuffer(base64.b64decode(s), dtype=np.uint8).astype(np.float32) / 255.0
    return a.reshape(grid.COLS, grid.FP, grid.FP, 3)


# --- analysis ----------------------------------------------------------------------------------

def analyse(im: Image.Image, done: list[dict], corrections: list[dict], bg: Bannergress,
            threshold: float = 0.06, margin: float = 0.005) -> tuple[list, list[np.ndarray], list[dict]]:
    """Medal rows -> banner entries (screenshot order, newest first).

    threshold 0.06: right matches are below 0.05 (p95); when a banner is missing from the done list, a similar
    one is closer than 0.10 for 13 % of rows but closer than 0.06 for 3 % (nikp3h, leave-one-out).
    """
    rows = grid.find_rows(im)
    screen = [grid.row_fingerprints(im, r) for r in rows]
    bg.prefetch(bg.picture_url(d['picture']) for d in done if d.get('picture'))
    cands = [match.Candidate(d['id'], grid.picture_rows(bg.picture(d['picture']))) for d in done if d.get('picture')]
    ms = match.match_rows(screen, cands, threshold=threshold)
    for m in ms:  # too close to another banner: let the agent decide
        if m.id and m.second - m.dist <= margin:
            m.id, m.picture_row = None, None
    # The agent's own decisions win: a row they decided before looks the same in a new capture. Look-alike
    # banners (a series, "Second Sunday" …) are closer to each other than a row is to itself in another
    # capture, so a decision with the row's place from the end of the list ("end": new medals come in on top,
    # so it stays) applies only to the row at that place
    fixed = [(fp_decode(c['fp']), c) for c in corrections if c.get('fp')]
    for m in ms:
        end = len(rows) - 1 - m.row
        near = [(match.row_distance(screen[m.row], fp), c) for fp, c in fixed if c.get('end') in (None, end)]
        if not near:
            continue
        d, c = min(near, key=lambda x: x[0])
        if d <= CORRECTION_DIST:
            if c.get('single'):  # single missions, not a banner
                m.id = 'single:' + (c.get('name') or 'Single missions')
            else:
                m.id = c.get('id') or ('medal:' + (c.get('name') or 'Unknown'))
            m.dist = d
    entries = match.group(ms)
    return rows, screen, entries


# --- output ------------------------------------------------------------------------------------

def write_tiles(im: Image.Image, out: Path) -> dict:
    half = im.resize((round(im.width * SCALE), round(im.height * SCALE)), Image.LANCZOS)
    (out / 'shot').mkdir(parents=True, exist_ok=True)
    tiles = []
    for n, y in enumerate(range(0, half.height, TILE)):
        tile = half.crop((0, y, half.width, min(y + TILE, half.height)))
        name = f's{n:02d}.jpg'
        tile.save(out / 'shot' / name, quality=72, optimize=True, progressive=True)
        tiles.append({'src': f'shot/{name}', 'h': tile.height})
    return {'w': im.width, 'h': im.height, 'scale': SCALE, 'tiles': tiles}


def _font(size: int, bold: bool = False):
    for f in (('NotoSans-Bold.ttf' if bold else 'NotoSans-Regular.ttf'),
              ('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf')):
        for d in ('/usr/share/fonts/noto', '/usr/share/fonts/truetype/noto', '/usr/share/fonts/truetype/dejavu',
                  '/usr/share/fonts/TTF'):
            try:
                return ImageFont.truetype(f'{d}/{f}', size)
            except OSError:
                pass
    return ImageFont.load_default(size)


def write_preview(banners: list[dict], agent: str, out: Path) -> tuple[str, str]:
    """The link preview image (1200 x 630) and its description."""
    count = sum(1 for b in banners if not b.get('single') and b['status'] != 'review')
    missions = sum(b['count'] for b in banners)
    W, H, bg = 1200, 630, (11, 16, 15)
    im = Image.new('RGB', (W, H), bg)
    x0, cw, gap = 790, 200, 8
    for c in range(2):
        y = -20 - c * 60
        for b in [b for b in banners if not b.get('single')][c::2]:
            pic = Image.open(out / b['img']).convert('RGB')
            pic = pic.resize((cw, round(pic.height * cw / pic.width)), Image.LANCZOS)
            im.paste(pic, (x0 + c * (cw + gap), y))
            y += pic.height + gap
            if y > H:
                break
    fade = Image.linear_gradient('L').rotate(-90).resize((160, H))
    im.paste(Image.new('RGB', (160, H), bg), (x0, 0), fade)
    d = ImageDraw.Draw(im)
    title = _font(84, True)
    name = f"{agent}'s"
    while d.textlength(name, font=title) > 700 and title.size > 40:
        title = _font(title.size - 6, True)
    d.text((64, 110), name, font=title, fill=(228, 236, 233))
    d.text((64, 215), 'Banners', font=_font(84, True), fill=(58, 209, 154))
    for k, line in enumerate(('Ingress mission banners matched with', 'Bannergress, on a map of the start points')):
        d.text((66, 345 + k * 40), line, font=_font(30), fill=(143, 161, 155))
    y, x = 470, 66
    for n, label in ((count, 'BANNERS'), (missions, 'MISSIONS')):
        d.text((x, y), f'{n:,}', font=_font(52, True), fill=(228, 236, 233))
        x += d.textlength(f'{n:,}', font=_font(52, True)) + 12
        d.text((x, y + 24), label, font=_font(24), fill=(143, 161, 155))
        x += d.textlength(label, font=_font(24)) + 40
    tier = next((t for n, t in SPECOPS if missions >= n), None)
    if tier:
        medal = Image.open(SITE / 'medals' / f'specops-{tier}.webp').convert('RGBA').resize((96, 96), Image.LANCZOS)
        im.paste(medal, (round(x) - 16, y - 14), medal)
    im.save(out / 'preview.jpg', quality=85, optimize=True, progressive=True)
    desc = (f'{count} Ingress mission banners and {missions:,} missions of agent {agent}: the medals, '
            'a map of the start points and the matching Bannergress banners.')
    return desc, hashlib.sha1((out / 'preview.jpg').read_bytes()).hexdigest()[:8]


def build_site(repo: Path, out: Path, url: str = '', cache: Path | None = None) -> dict | None:
    """The page in out; None when there are no screenshots yet (a new repo)."""
    repo, out = Path(repo), Path(out)
    config = json.loads((repo / 'config.json').read_text(encoding='utf-8')) if (repo / 'config.json').exists() else {}
    agent = config.get('agent') or 'Agent'
    take_inbox(repo)
    shot = repo / 'capture' / 'medals.jpg'
    if not shot.exists():
        print('No screenshots yet (the app puts them in inbox/): nothing to build.')
        return None
    bg = Bannergress(cache or repo / '.cache' / 'bannergress')
    done = read_done(repo / 'done.json')
    corr = json.loads((repo / 'corrections.json').read_text()) if (repo / 'corrections.json').exists() else {}
    im = grid.normalize(Image.open(shot))
    rows, screen, entries = analyse(im, done, corr.get('rows', []), bg)
    bg.prefetch(bg.banner_url(e['id']) for e in entries if e['id'] and not e['id'].startswith(('medal:', 'single:')))
    nearby = nearby_options(entries, screen, bg, {d['id'] for d in done})

    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(SITE, out)
    (out / 'img').mkdir()
    banners = []
    for i, e in enumerate(entries):
        first = e['rows'][0]
        run = 1
        while run < len(e['rows']) and e['rows'][run] == first + run:
            run += 1
        img = f'img/m{i:03d}.jpg'
        grid.medal_picture(im, rows, first, run).save(out / img, quality=90)
        b = {'i': i, 'rows': match.rows_text(e['rows']), 'count': sum(grid.row_medals(im, rows[r]) for r in e['rows']),
             'img': img, 'fp': fp_encode(screen[first]),
             # every row's fingerprint: the app changes a whole entry (corrections.json has one per row)
             'fps': [fp_encode(screen[r]) for r in e['rows']],
             # and its place from the end of the list, which new medals on top don't change (for corrections)
             'ends': [len(rows) - 1 - r for r in e['rows']]}
        if e['id'] and e['id'].startswith('single:'):
            b.update({'status': 'none', 'name': e['id'][7:], 'single': True})
        elif e['id'] and not e['id'].startswith('medal:'):
            b.update({'status': 'match', 'score': round(max(e['dist']), 3)})
            b.update(entry(bg.banner(e['id'])))
        elif e['id']:
            b.update({'status': 'none', 'name': e['id'][6:]})
        else:
            # The closest banners of the done list, for the app's review screen
            by_id = {d['id']: d for d in done}
            options = [{'id': i, 'dist': dist, 'title': by_id[i]['title'], 'missions': by_id[i]['missions'],
                        'picture': by_id[i]['picture']} for i, dist in e.get('options', []) if i in by_id]
            # and banners near the neighbouring banners that aren't on the done list
            options = sorted(options + nearby.get(i, []), key=lambda o: o['dist'])[:6]
            b.update({'status': 'review', 'score': round(min(e['dist']), 3), 'name': None, 'options': options})
        b.setdefault('missions', b['count'])
        banners.append(b)

    notes = json.loads((repo / 'notes.json').read_text()) if (repo / 'notes.json').exists() else {}
    synced = config.get('doneSyncedAt') or datetime.fromtimestamp((repo / 'done.json').stat().st_mtime, timezone.utc) \
        .strftime('%Y-%m-%dT%H:%M:%SZ') if (repo / 'done.json').exists() else None
    shot_tiles = write_tiles(im, out)
    desc, version = write_preview(banners, agent, out)  # reads img/ by plain path, before the versions below

    # Every file of the page gets its content hash in its URL: GitHub Pages lets browsers keep files for
    # 10 minutes, so without it visitors see old data (or new and old mixed) after an update.
    def versioned(rel: str) -> str:
        return f"{rel}?v={hashlib.sha1((out / rel).read_bytes()).hexdigest()[:8]}"
    for b in banners:
        b['img'] = versioned(b['img'])
    for t in shot_tiles['tiles']:
        t['src'] = versioned(t['src'])
    missions = {'shot': shot_tiles, 'rows': [list(r) for r in rows],
                'done': {'source': 'Bannergress done list', 'syncedAt': synced, 'banners': done}, 'notes': notes}
    (out / 'data.js').write_text('window.BANNERS=' + json.dumps(banners, ensure_ascii=False, indent=1) + ';\n', encoding='utf-8')
    (out / 'missions-data.js').write_text('window.MISSIONS=' + json.dumps(missions, ensure_ascii=False) + ';\n', encoding='utf-8')
    (out / 'banners.json').write_text(json.dumps({'agent': agent, 'banners': banners}, ensure_ascii=False), encoding='utf-8')
    base = url.rstrip('/') + '/' if url else ''
    html = (SITE / 'index.html').read_text(encoding='utf-8')
    esc = lambda s: s.replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;')  # noqa: E731
    for k, v in {'agent': esc(agent), 'description': esc(desc), 'url': esc(base),
                 'preview': esc(f'{base}preview.jpg?v={version}')}.items():
        html = html.replace('{{' + k + '}}', v)
    for rel in ('data.js', 'missions-data.js', 'world.js', 'app.js', 'style.css'):
        html = html.replace(f'"{rel}"', f'"{versioned(rel)}"')
    (out / 'index.html').write_text(html, encoding='utf-8')
    (out / '.nojekyll').write_text('')
    result = {'rows': len(rows), 'matched': sum(1 for b in banners if b['status'] == 'match'),
              'review': sum(1 for b in banners if b['status'] == 'review'), 'done': len(done)}
    print(f"{result['rows']} medal rows: {result['matched']} banners matched, {result['review']} to check; "
          f"{result['done']} on the done list")
    return result
