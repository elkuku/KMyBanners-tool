"""Bannergress: banner details and pictures (public API, no sign-in), cached on disk."""
from __future__ import annotations

import hashlib
import json
import threading
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

API = 'https://api.bannergress.com'
USER_AGENT = 'kmybanners-tool/0.1 (+https://github.com/elkuku/KMyBanners-tool)'


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
        tmp = key.with_suffix(f'.{threading.get_ident()}.tmp')  # whole files only (parallel prefetch)
        tmp.write_bytes(data)
        tmp.replace(key)
        return data

    def prefetch(self, urls, workers: int = 16) -> None:
        """Fetches [urls] into the cache in parallel (one request after another took over 10 minutes for a
        whole list); failures are left for the calls that need the data."""
        todo = [u for u in dict.fromkeys(urls) if not (self.cache / hashlib.sha1(u.encode()).hexdigest()).exists()]
        if not todo:
            return

        def get(u):
            try:
                self._get(u)
            except Exception:
                pass

        with ThreadPoolExecutor(workers) as pool:
            list(pool.map(get, todo))

    @staticmethod
    def banner_url(banner_id: str) -> str:
        return f'{API}/bnrs/{urllib.parse.quote(banner_id)}'

    @staticmethod
    def picture_url(path: str) -> str:
        return path if path.startswith('http') else API + path

    @staticmethod
    def search_url(**params) -> str:
        return f'{API}/bnrs?{urllib.parse.urlencode(params, doseq=True)}'

    def banner(self, banner_id: str) -> dict:
        return json.loads(self._get(self.banner_url(banner_id)))

    def picture(self, path: str) -> Image.Image:
        """A banner picture by its `picture` path (/bnrs/pictures/…)."""
        from io import BytesIO
        return Image.open(BytesIO(self._get(self.picture_url(path)))).convert('RGB')

    def search(self, **params) -> list[dict]:
        """GET /bnrs with query parameters (e.g. minLatitude…, query=, limit=)."""
        return json.loads(self._get(self.search_url(**params)))


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
