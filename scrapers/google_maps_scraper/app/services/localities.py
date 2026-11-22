"""Locality discovery via https://www.mapsofindia.com/.

The site publishes a locality index for most Indian cities at either

    https://www.mapsofindia.com/<city>/localities/      (folder form, e.g. Nagpur)
    https://www.mapsofindia.com/<city>/localities.html  (file form, e.g. Kolkata)

Two page layouts exist and both are supported:

* **Folder pages** list localities as links whose path is
  ``/<city>/localities/<locality-slug>.html`` (Nagpur, Mumbai, Bangalore,
  Chandigarh, ...).  Attributes can be single- *or* double-quoted (Mumbai uses
  single quotes), so a real HTML parser is used instead of regexes.
* **Index pages** (Kolkata) list localities as relative links tagged
  ``class="indexlinksnew"`` with a ``" Map"`` suffix on the label, plus
  alphabetical sub-index pages (``a-d-localities.html`` ...) that are followed
  up to ``MAX_LOCALITY_INDEX_PAGES``.

Anything the module cannot resolve simply returns an empty list; the caller
(:mod:`app.services.areas`) then falls back to OpenStreetMap, and finally to
the coordinate grid.  Nothing here is allowed to raise.
"""
from __future__ import annotations

import logging
import os
import re
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser

logger = logging.getLogger(__name__)

BASE_URL = "https://www.mapsofindia.com"

#: Extra slugs tried when the plain city slug has no locality page.  A miss is
#: cheap (one 404), so a few plausible aliases are worth trying.
CITY_ALIASES: dict[str, list[str]] = {
    "nashik": ["nasik"],
    "bengaluru": ["bangalore"],
    "mysuru": ["mysore"],
    "mangaluru": ["mangalore"],
    "prayagraj": ["allahabad"],
    "gurugram": ["gurgaon"],
    "vadodara": ["baroda"],
    "kochi": ["cochin"],
    "thiruvananthapuram": ["trivandrum"],
    "bhubaneswar": ["bhubaneshwar"],
}

_USER_AGENT = "maps-extractor/1.0 (+localities discovery)"

#: Safety ceiling so a pathological page can never blow up a job (capped to 20 for fast responses).
MAX_LOCALITIES = 20

#: Kolkata-style alphabetical sub-index pages (``a-d-localities.html``).
_SUB_INDEX_RE = re.compile(r"^[a-z](?:-[a-z])?-localities\.html$")

#: Labels that are navigation chrome, never a locality.
_SKIP_NAMES = {"", "more", "more...", "home", "map", "maps of india"}

# Locality lists on the site carry a "Last Updated on 03/03/2020" stamp, so a
# long TTL is safe and keeps repeat sweeps instant.
_CACHE_TTL = 7 * 24 * 3600
_CACHE: dict[str, tuple[float, list[str]]] = {}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _mapsofindia_enabled() -> bool:
    return os.getenv("USE_MAPSOFINDIA_LOCALITIES", "1") == "1"


def city_slug(city: str) -> str:
    """Turn a city name into a mapsofindia path slug ("New Delhi" -> "new-delhi")."""
    slug = (city or "").strip().lower()
    slug = slug.replace("&", " and ")
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return re.sub(r"-+", "-", slug).strip("-")


def candidate_urls(city: str) -> list[str]:
    """Every URL that might host the city's locality list, best guess first."""
    slug = city_slug(city)
    if not slug:
        return []
    slugs = [slug]
    for alias in CITY_ALIASES.get(slug, []):
        if alias not in slugs:
            slugs.append(alias)
    urls: list[str] = []
    for s in slugs:
        urls.append(f"{BASE_URL}/{s}/localities/")
        urls.append(f"{BASE_URL}/{s}/localities.html")
    return urls


class _AnchorCollector(HTMLParser):
    """Collect ``(href, class, text)`` for every ``<a>`` tag.

    Uses the stdlib parser so single-quoted attributes (Mumbai) and entity
    references are handled correctly.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[tuple[str, str, str]] = []
        self._href: str | None = None
        self._classes = ""
        self._text: list[str] = []

    def handle_starttag(self, tag, attrs):  # noqa: D102
        if tag != "a":
            return
        attr = dict(attrs)
        self._href = attr.get("href") or ""
        self._classes = attr.get("class") or ""
        self._text = []

    def handle_data(self, data):  # noqa: D102
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):  # noqa: D102
        if tag == "a" and self._href is not None:
            text = " ".join("".join(self._text).split())
            self.anchors.append((self._href, self._classes, text))
            self._href = None


def _slug_to_name(segment: str) -> str:
    """Rebuild a display name from a URL slug ("wadi-naka" -> "Wadi Naka")."""
    words = []
    for token in segment.split("-"):
        if not token:
            continue
        words.append(token[0].upper() + token[1:])
    return " ".join(words)


def _clean_name(text: str, fallback_slug: str) -> str:
    """Normalise an anchor label; fall back to the URL slug when empty."""
    name = (text or "").strip().strip(",;|").strip()
    # Kolkata labels carry a trailing " Map" ("Adarsha Nagar Map").
    name = re.sub(r"\s*Maps?$", "", name, flags=re.IGNORECASE).strip()
    if not name:
        name = _slug_to_name(fallback_slug)
    return " ".join(name.split())


def _is_host_ours(hostname: str | None) -> bool:
    return (hostname or "").lower() in ("www.mapsofindia.com", "mapsofindia.com")


def parse_locality_page(html: str, page_url: str) -> tuple[list[str], list[str], bool]:
    """Extract locality names from one mapsofindia page.

    Returns ``(names, sub_index_urls, index_style)`` where ``names`` keeps
    document order and is de-duplicated case-insensitively, and
    ``sub_index_urls`` are same-city alphabetical sub-pages worth following
    (Kolkata's ``a-d-localities.html`` style).
    """
    collector = _AnchorCollector()
    try:
        collector.feed(html)
        collector.close()
    except Exception as exc:  # noqa: BLE001 - malformed HTML must never crash a job
        logger.warning("Locality page %s could not be parsed: %s", page_url, exc)
        return [], [], False

    names: list[str] = []
    seen: set[str] = set()
    sub_pages: list[str] = []
    index_style = False

    def add(name: str) -> None:
        key = name.casefold()
        if key in seen or key in _SKIP_NAMES or len(names) >= MAX_LOCALITIES:
            return
        seen.add(key)
        names.append(name)

    for href, classes, text in collector.anchors:
        if not href:
            continue
        absolute = urllib.parse.urljoin(page_url, href)
        parsed = urllib.parse.urlsplit(absolute)
        if not _is_host_ours(parsed.hostname):
            continue
        path = parsed.path or "/"
        last = path.rstrip("/").rsplit("/", 1)[-1]
        is_index_link = "indexlinksnew" in classes.lower()

        # Kolkata-style alphabetical sub-index page: follow, never a locality.
        if _SUB_INDEX_RE.match(last):
            if absolute not in sub_pages:
                sub_pages.append(absolute)
            continue

        # Layout 1: /<city>/localities/<locality>.html (Nagpur, Mumbai, ...).
        match = re.search(r"/localities/([^/]+)\.html?$", path)
        if match:
            add(_clean_name(text, match.group(1)))
            continue

        # Layout 2: class="indexlinksnew" relative links (Kolkata).
        if is_index_link and path.endswith(".html"):
            index_style = True
            add(_clean_name(text, last))
            continue

        # Anything else is navigation / ads / cross-city chrome.

    return names, sub_pages, index_style


def parse_locality_names(html: str, page_url: str) -> list[str]:
    """Public single-page helper: just the locality names."""
    names, _sub_pages, _index_style = parse_locality_page(html, page_url)
    return names


def _fetch_page(url: str, timeout: float) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": _USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Encoding": "identity",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def _uncache_duplicates(names: list[str]) -> list[str]:
    return list(dict.fromkeys(names))


def discover_localities(
    city: str,
    limit: int | None = None,
    timeout: float | None = None,
) -> list[str]:
    """Return the mapsofindia locality names for ``city`` (may be empty).

    Tries every candidate URL, follows alphabetical sub-index pages, caches
    successful answers for a week, and never raises.
    """
    city = (city or "").strip().replace('"', "")[:100]
    if not city or (limit is not None and limit <= 0):
        return []
    if not _mapsofindia_enabled():
        return []

    key = city.lower()
    now = time.time()
    hit = _CACHE.get(key)
    if hit and now - hit[0] < _CACHE_TTL:
        cached = hit[1]
        return cached if limit is None else cached[:limit]

    if timeout is None:
        timeout = float(_env_int("LOCALITIES_TIMEOUT", 20))
    timeout = max(5.0, timeout)

    names: list[str] = []
    for url in candidate_urls(city):
        try:
            html = _fetch_page(url, timeout)
        except Exception as exc:  # noqa: BLE001 - 404s and timeouts are expected
            logger.debug("Locality page %s unavailable: %s", url, exc)
            continue
        page_names, sub_pages, _style = parse_locality_page(html, url)
        if not page_names:
            continue
        names = page_names
        # Kolkata-style pages split the alphabet across sub-pages; follow a
        # bounded number of them for complete coverage.
        if sub_pages:
            max_pages = max(0, _env_int("MAX_LOCALITY_INDEX_PAGES", 8))
            for sub_url in sub_pages[:max_pages]:
                try:
                    sub_html = _fetch_page(sub_url, timeout)
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Sub-index %s unavailable: %s", sub_url, exc)
                    continue
                sub_names, _more, _ = parse_locality_page(sub_html, sub_url)
                names.extend(sub_names)
        break

    names = _uncache_duplicates(names)[:MAX_LOCALITIES]
    if names:
        _CACHE[key] = (time.time(), names)
        logger.info("Found %d localities for %r on mapsofindia.com", len(names), city)
    else:
        logger.info("mapsofindia.com has no locality list for %r", city)
    return names if limit is None else names[:limit]
