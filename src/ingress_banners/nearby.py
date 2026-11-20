"""Suggestions from Bannergress for medal rows the done list doesn't explain.

Medals are in the order the agent did them, so a banner they did that day usually starts close to the banners
next to it in the list. For a row to check, the banners near the start points of the nearest matched banners
above and below it are compared with the row, like the done list's pictures.
"""
from __future__ import annotations

from . import grid, match
from .bannergress import Bannergress

RADIUS = 0.1     # degrees of latitude around a start point (~11 km)
PER_POINT = 40   # the closest banners there
NEIGHBOURS = 2   # matched banners above and below a row whose start points are searched


def _search_params(lat: float, lng: float) -> dict:
    lat, lng = round(lat, 3), round(lng, 3)  # neighbouring rows share their neighbours: same query, cached
    return dict(orderBy='proximityStartPoint', orderDirection='ASC', proximityLatitude=lat, proximityLongitude=lng,
                minLatitude=round(lat - RADIUS, 3), maxLatitude=round(lat + RADIUS, 3),
                minLongitude=round(lng - 1.5 * RADIUS, 3), maxLongitude=round(lng + 1.5 * RADIUS, 3),
                limit=PER_POINT, offset=0)


def nearby_options(entries: list[dict], screen: list, bg: Bannergress, known: set[str],
                   top: int = 5) -> dict[int, list[dict]]:
    """For every entry without a banner (index -> options): the [top] closest banners near its neighbours,
    leaving out the [known] ones (the done list: already compared). All searches and pictures are fetched
    in parallel first."""
    starts: dict[int, tuple[float, float]] = {}
    for i, e in enumerate(entries):
        if e['id'] and not e['id'].startswith(('medal:', 'single:')):
            try:
                b = bg.banner(e['id'])
            except Exception:
                continue
            if b.get('startLatitude') is not None:
                starts[i] = (b['startLatitude'], b['startLongitude'])
    # every row's search points: the [NEIGHBOURS] nearest matched banners above and below
    points: dict[int, list] = {}
    for i, e in enumerate(entries):
        if e['id'] is None:
            above = [j for j in range(i - 1, -1, -1) if j in starts][:NEIGHBOURS]
            below = [j for j in range(i + 1, len(entries)) if j in starts][:NEIGHBOURS]
            points[i] = list(dict.fromkeys(starts[j] for j in above + below))
    bg.prefetch(bg.search_url(**_search_params(*p)) for ps in points.values() for p in ps)
    found: dict[int, dict[str, dict]] = {}
    for i, ps in points.items():
        found[i] = {}
        for lat, lng in ps:
            try:
                for b in bg.search(**_search_params(lat, lng)):
                    if b['id'] not in known and b.get('picture'):
                        found[i][b['id']] = b
            except Exception as ex:  # Bannergress down: the done list's suggestions still work
                print(f'  Bannergress search near {lat},{lng} failed: {ex}')
    bg.prefetch(bg.picture_url(b['picture']) for f in found.values() for b in f.values())
    pictures: dict[str, list] = {}
    out: dict[int, list[dict]] = {}
    for i, f in found.items():
        row = screen[entries[i]['rows'][0]]
        scored = []
        for bid, b in f.items():
            if bid not in pictures:
                try:
                    pictures[bid] = grid.picture_rows(bg.picture(b['picture']))
                except Exception:
                    pictures[bid] = []
            if pictures[bid]:
                scored.append((min(match.row_distance(row, fp) for fp in pictures[bid]), b))
        scored.sort(key=lambda x: x[0])
        out[i] = [{'id': b['id'], 'dist': round(d, 3), 'title': b.get('title', ''), 'missions': b.get('numberOfMissions'),
                   'picture': b['picture'], 'nearby': True} for d, b in scored[:top]]
    return out
