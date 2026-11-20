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


def _search(bg: Bannergress, lat: float, lng: float) -> list[dict]:
    lat, lng = round(lat, 3), round(lng, 3)  # neighbouring rows share their neighbours: same query, cached
    return bg.search(orderBy='proximityStartPoint', orderDirection='ASC', proximityLatitude=lat,
                     proximityLongitude=lng, minLatitude=round(lat - RADIUS, 3), maxLatitude=round(lat + RADIUS, 3),
                     minLongitude=round(lng - 1.5 * RADIUS, 3), maxLongitude=round(lng + 1.5 * RADIUS, 3),
                     limit=PER_POINT, offset=0)


def nearby_options(entries: list[dict], screen: list, bg: Bannergress, known: set[str],
                   top: int = 5) -> dict[int, list[dict]]:
    """For every entry without a banner (index -> options): the [top] closest banners near its neighbours,
    leaving out the [known] ones (the done list: already compared)."""
    starts: dict[int, tuple[float, float]] = {}
    for i, e in enumerate(entries):
        if e['id'] and not e['id'].startswith(('medal:', 'single:')):
            try:
                b = bg.banner(e['id'])
            except Exception:
                continue
            if b.get('startLatitude') is not None:
                starts[i] = (b['startLatitude'], b['startLongitude'])
    pictures: dict[str, list] = {}
    out: dict[int, list[dict]] = {}
    for i, e in enumerate(entries):
        if e['id'] is not None:
            continue
        # the [NEIGHBOURS] nearest matched banners above and below (one may be in another city)
        above = [j for j in range(i - 1, -1, -1) if j in starts][:NEIGHBOURS]
        below = [j for j in range(i + 1, len(entries)) if j in starts][:NEIGHBOURS]
        points = [starts[j] for j in above + below]
        found: dict[str, dict] = {}
        for lat, lng in dict.fromkeys(points):
            try:
                for b in _search(bg, lat, lng):
                    if b['id'] not in known and b.get('picture'):
                        found[b['id']] = b
            except Exception as ex:  # Bannergress down: the done list's suggestions still work
                print(f'  Bannergress search near {lat},{lng} failed: {ex}')
        row = screen[e['rows'][0]]
        scored = []
        for bid, b in found.items():
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
