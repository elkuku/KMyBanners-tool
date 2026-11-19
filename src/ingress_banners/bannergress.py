"""Bannergress: banner details and pictures (public API, no sign-in), cached on disk."""
from __future__ import annotations

import hashlib
import json
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

API = 'https://api.bannergress.com'
USER_AGENT = 'ingress-banners-tool/0.1 (+https://github.com/elkuku/ingress-banners-tool)'


class Bannergress:
    def __init__(self, cache: Path):
        self.cache = Path(cache)
        self.cache.mkdir(parents=True, exist_ok=True)

    def _get(self, url: str) -> bytes:
        key = self.cache / hashlib.sha1(url.encode()).hexdigest()
        if key.exists():
            return key.read_bytes()
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
        key.write_bytes(data)
        return data

    def banner(self, banner_id: str) -> dict:
        return json.loads(self._get(f'{API}/bnrs/{urllib.parse.quote(banner_id)}'))

    def picture(self, path: str) -> Image.Image:
        """A banner picture by its `picture` path (/bnrs/pictures/…)."""
        from io import BytesIO
        url = path if path.startswith('http') else API + path
        return Image.open(BytesIO(self._get(url))).convert('RGB')

    def search(self, **params) -> list[dict]:
        """GET /bnrs with query parameters (e.g. minLatitude…, query=, limit=)."""
        qs = urllib.parse.urlencode(params, doseq=True)
        return json.loads(self._get(f'{API}/bnrs?{qs}'))


def entry(b: dict) -> dict:
    """The page's banner fields from a Bannergress banner."""
    missions = b.get('missions') or {}
    dur = sum((m.get('averageDurationMilliseconds') or 0) for m in missions.values()) / 60000
    return {
        'id': b['id'],
        'title': b['title'],
        'addr': b.get('formattedAddress'),
        'missions': b.get('numberOfMissions'),
        'desc': b.get('description'),
        'km': round((b.get('lengthMeters') or 0) / 1000, 1),
        'order': b.get('type'),
        'dur': round(dur) or None,
        'disabled': b.get('numberOfDisabledMissions') or 0,
        'lat': b.get('startLatitude'),
        'lng': b.get('startLongitude'),
        'event': [b['eventStartDate'], b['eventEndDate']] if b.get('eventStartDate') else None,
        'warning': b.get('warning'),
        'offline': b.get('plannedOfflineDate'),
    }
