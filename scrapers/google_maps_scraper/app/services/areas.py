"""Automatic area discovery for a city.

Sources are tried in order until one answers:

1. **mapsofindia.com** locality pages (``/<city>/localities/``) — the curated
   list the project is built around (:mod:`app.services.localities`).
2. **OpenStreetMap** (Nominatim bounding box + Overpass suburb / neighbourhood
   names), asked concurrently across mirrors.
3. A coarse **coordinate grid** over the city bounding box, so coverage never
   depends on either site being up.

Standard library only.  Any failure falls back to the next source, and the
caller can always fall back to searching the plain location as before.

Why this module is so defensive
-------------------------------
The public Overpass mirrors are frequently overloaded.  Two mistakes turn that
into a guaranteed "read operation timed out" on every mirror:

  1. A client timeout shorter than the ``[timeout:...]`` inside the Overpass
     query.  The server keeps computing while the client already gave up, so
     a big city bbox *never* succeeds.
  2. Asking the mirrors one after another.  Three overloaded mirrors then cost
     3 x timeout before the job even starts scraping.

So we ask every mirror concurrently (first non-empty answer wins), give the
client more time than the server-side query timeout, and -- if OSM is simply
down -- sweep a coordinate grid over the city bounding box instead.  That last
step keeps city-wide coverage working even when area names cannot be resolved.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.services import localities as localities_service

logger = logging.getLogger(__name__)

OVERPASS_URLS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
)
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

_USER_AGENT = "maps-extractor/1.0"

# Overpass distance queries are position-dependent, so a 6h TTL is plenty.
_CACHE_TTL = 6 * 3600
# City bounding boxes basically never move.
_BBOX_TTL = 30 * 24 * 3600

_CACHE: dict[str, tuple[float, list[str]]] = {}
_BBOX_CACHE: dict[str, tuple[float, tuple[float, float, float, float] | None]] = {}

#: Labels such as ``"21.14580,79.08820"`` produced by the grid fallback.
_COORD_RE = re.compile(r"^-?\d{1,3}\.\d+\s*,\s*-?\d{1,3}\.\d+$")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def is_coordinate_label(label: str) -> bool:
    """True when ``label`` is a ``"lat,lng"`` pair (grid fallback)."""
    return bool(_COORD_RE.match((label or "").strip()))


def extract_city(location: str) -> str:
    """Take the city part of a location ("Dharampeth, Nagpur" -> "Nagpur")."""
    parts = [p.strip() for p in (location or "").split(",") if p.strip()]
    if not parts:
        return ""
    # If the last token looks like a railway station or airport code (e.g. "SBC", "NDLS", "HWH")
    # and there's a preceding part, use the preceding part as the city.
    if len(parts) > 1 and len(parts[-1]) <= 4 and parts[-1].isupper() and parts[-1].isalpha():
        return parts[-2]
    return parts[-1]


def _request(url: str, *, data: bytes | None = None, timeout: float) -> bytes:
    req = urllib.request.Request(
        url,
        data=data,
        headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
        method="POST" if data is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _bbox_via_nominatim(city: str, timeout: float = 15) -> tuple[float, float, float, float] | None:
    """Resolve a city to an (south, west, north, east) box. None on failure."""
    try:
        url = NOMINATIM_URL + "?" + urllib.parse.urlencode(
            {"format": "json", "limit": 1, "q": city}
        )
        data = json.loads(_request(url, timeout=timeout).decode("utf-8", "replace"))
        if not data:
            return None
        bb = data[0].get("boundingbox")  # [south, north, west, east] as strings
        s, n, w, e = float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3])
        if n <= s or e <= w:
            return None
        return (s, w, n, e)
    except Exception as exc:  # noqa: BLE001 - network/parse must never crash a job
        logger.warning("Nominatim lookup failed for %r: %s", city, exc)
        return None


def _bbox(city: str) -> tuple[float, float, float, float] | None:
    """Cached bounding box for ``city`` (geocoding is slow and rate limited)."""
    key = city.lower()
    now = time.time()
    hit = _BBOX_CACHE.get(key)
    if hit and now - hit[0] < _BBOX_TTL:
        return hit[1]
    bbox = _bbox_via_nominatim(city)
    if bbox is not None:
        _BBOX_CACHE[key] = (now, bbox)
    return bbox


def _query(bbox: tuple[float, float, float, float], server_timeout: int) -> str:
    """Overpass QL for the city's localities.

    Each place type is matched with an *exact* value in its own statement.
    A regex such as ``node["place"~"^(suburb|neighbourhood|...)$"]`` is
    rejected by the public mirrors (HTTP 502/504) or takes so long that the
    client times out -- which is exactly how area discovery used to fail.
    """
    s, w, n, e = bbox
    box = f"({s},{w},{n},{e})"
    parts = "".join(
        f'node["place"="{place}"]{box};'
        for place in ("suburb", "neighbourhood", "quarter", "hamlet", "village", "town")
    )
    return f"[out:json][timeout:{server_timeout}];({parts});out tags;"


def _parse_names(payload: dict) -> list[str]:
    names: list[str] = []
    elements = payload.get("elements") if isinstance(payload, dict) else None
    for el in elements or []:
        tags = (el or {}).get("tags") or {}
        name = (tags.get("name") or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def _overpass_once(endpoint: str, query: str, timeout: float) -> list[str]:
    data = urllib.parse.urlencode({"data": query}).encode()
    payload = json.loads(_request(endpoint, data=data, timeout=timeout).decode("utf-8", "replace"))
    return _parse_names(payload)


def _overpass_first(query: str, timeout: float) -> list[str]:
    """Ask every mirror at once and return the first non-empty answer.

    Running the mirrors concurrently bounds the discovery cost to a single
    ``timeout`` instead of ``len(OVERPASS_URLS) * timeout``.  Leftover mirror
    requests are abandoned (not awaited) so one slow mirror cannot hold up the
    scrape.
    """
    pool = ThreadPoolExecutor(max_workers=len(OVERPASS_URLS), thread_name_prefix="overpass")
    futures = {pool.submit(_overpass_once, ep, query, timeout): ep for ep in OVERPASS_URLS}
    try:
        for fut in as_completed(futures):
            endpoint = futures[fut]
            try:
                names = fut.result()
            except Exception as exc:  # noqa: BLE001 - try the next mirror
                logger.warning("Area discovery via %s failed: %s", endpoint, exc)
                continue
            if names:
                return names
        return []
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def coordinate_grid(bbox: tuple[float, float, float, float], cells: int = 3) -> list[str]:
    """Grid of ``"lat,lng"`` centres covering ``bbox``.

    Used when OSM cannot name the city's localities: Google Maps accepts a
    coordinate as the location, so sweeping the cell centres still covers the
    whole city instead of a single ~120-listing feed.
    """
    s, w, n, e = bbox
    cells = max(1, min(10, cells))
    lat_step = (n - s) / cells
    lng_step = (e - w) / cells
    out: list[str] = []
    for i in range(cells):
        for j in range(cells):
            lat = s + lat_step * (i + 0.5)
            lng = w + lng_step * (j + 0.5)
            out.append(f"{lat:.5f},{lng:.5f}")
    return out


def discover_areas(
    city: str,
    limit: int | None = None,
    timeout: float | None = None,
    grid_fallback: bool = True,
    use_mapsofindia: bool | None = None,
) -> list[str]:
    """Return area names for ``city`` (may be empty).

    mapsofindia.com is asked first (``use_mapsofindia=None`` reads
    ``USE_MAPSOFINDIA_LOCALITIES``, default on); OpenStreetMap is the fallback.

    When ``limit`` is ``None`` every discovered area is returned (no cap) so a
    city-wide sweep is complete.  Pass an integer to cap the list.

    ``timeout`` is the *client* timeout.  It defaults to
    ``AREAS_TIMEOUT`` (40s) and is always kept above the Overpass server-side
    query timeout, otherwise every mirror is guaranteed to time out.
    """
    city = (city or "").strip().replace('"', "")[:100]
    if not city:
        return []
    if limit is not None and limit <= 0:
        return []

    if use_mapsofindia is None:
        use_mapsofindia = os.getenv("USE_MAPSOFINDIA_LOCALITIES", "1") == "1"

    now = time.time()
    hit = _CACHE.get(city.lower())
    if hit and now - hit[0] < _CACHE_TTL:
        names = hit[1]
        return names if limit is None else names[:limit]

    if use_mapsofindia:
        try:
            moi_names = localities_service.discover_localities(city, limit=limit)
        except Exception as exc:  # noqa: BLE001 - discovery must never break a job
            logger.warning("mapsofindia locality lookup crashed for %r: %s", city, exc)
            moi_names = []
        if moi_names:
            # Real curated names: worth caching like an OSM answer.
            _CACHE[city.lower()] = (now, moi_names)
            logger.info(
                "Using %d mapsofindia.com localities for %r", len(moi_names), city
            )
            return moi_names

    if timeout is None:
        timeout = float(_env_int("AREAS_TIMEOUT", 40))
    timeout = max(5.0, float(timeout))
    server_timeout = int(min(30, max(5, timeout - 10)))

    bbox = _bbox(city)
    if bbox is None:
        logger.warning("No bounding box for %r; skipping area discovery", city)
        return []

    names = _overpass_first(_query(bbox, server_timeout), timeout)
    used_grid = False
    if not names and grid_fallback:
        cells = _env_int("AREA_GRID_CELLS", 3)
        names = coordinate_grid(bbox, cells=cells)
        used_grid = bool(names)
        if used_grid:
            logger.warning(
                "Overpass returned no areas for %r; falling back to a %dx%d coordinate grid",
                city, cells, cells,
            )

    if limit is not None:
        names = names[:limit]

    # Cache real OSM answers only: caching a grid would keep the (worse)
    # fallback alive for hours after Overpass recovers.
    if names and not used_grid:
        _CACHE[city.lower()] = (now, names)
    elif not names:
        logger.warning("Area discovery failed for %r on all mirrors", city)
    logger.info(
        "Discovered %d areas for %r%s",
        len(names), city, " (coordinate grid)" if used_grid else "",
    )
    return names


def discover_city_areas(city: str, limit: int | None = None) -> tuple[list[str], str]:
    """Return ``(locality_names, source)`` for a city, for display / planning.

    Unlike :func:`discover_areas` this never returns coordinate-grid labels —
    a grid is a scraping fallback, not a locality listing.  ``source`` is
    ``"mapsofindia"`` or ``"openstreetmap"`` (``""`` when nothing was found).
    """
    city = (city or "").strip()
    if not city or (limit is not None and limit <= 0):
        return [], ""

    moi = localities_service.discover_localities(city, limit=limit)
    if moi:
        return moi, "mapsofindia"

    # Grid fallback disabled: only real names are useful here.
    osm = discover_areas(city, limit=limit, grid_fallback=False)
    if osm:
        return osm, "openstreetmap"
    return [], ""
