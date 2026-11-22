"""Mindtrip reference asset cloner.

Extracts design tokens, stylesheets, SVG marks and editorial imagery from
mindtrip.ai so the clone can match the original's visual language.

Modes
-----
    python -m scrapers.cloner.mindtrip_scraper --test
    python -m scrapers.cloner.mindtrip_scraper --offline
    python -m scrapers.cloner.mindtrip_scraper --limit 24

All assets are written to ``data/reference/``. The cloner is polite: one
request per asset, a desktop UA, and no crawling beyond the landing page.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT / "data" / "reference"
FIXTURES = ROOT / "data" / "fixtures"
BASE_URL = "https://mindtrip.ai"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"

LOCAL_HTML = ROOT / "mindtrip_home.html"
LOCAL_CSS = ROOT / "mindtrip_styles.css"


def _ensure_dirs() -> None:
    for sub in ("", "css", "svg", "img", "layouts"):
        (REFERENCE / sub).mkdir(parents=True, exist_ok=True)


def _fetch(client: httpx.Client, url: str) -> bytes | None:
    try:
        response = client.get(url)
        if response.status_code == 200:
            return response.content
        print(f"  ! {response.status_code} {url}", file=sys.stderr)
    except Exception as exc:  # noqa: BLE001
        print(f"  ! {exc} {url}", file=sys.stderr)
    return None


def extract_tokens(css: str) -> dict[str, Any]:
    """Pull the custom properties that define Mindtrip's design language."""
    tokens: dict[str, Any] = {"colors": {}, "fonts": {}, "radii": {}, "spacing": {}, "containers": {}, "misc": {}}
    patterns = {
        "colors": r"--color-([a-z0-9-]+)\s*:\s*([^;}]+)",
        "fonts": r"--font-([a-z0-9-]+)\s*:\s*([^;}]+)",
        "radii": r"--radius-([a-z0-9-]+)\s*:\s*([^;}]+)",
        "spacing": r"--spacing-([a-z0-9-]+)\s*:\s*([^;}]+)",
        "containers": r"--container-([a-z0-9-]+)\s*:\s*([^;}]+)",
        "misc": r"--(text-[a-z0-9-]+|leading-[a-z0-9-]+|blur-[a-z0-9-]+)\s*:\s*([^;}]+)",
    }
    for group, pattern in patterns.items():
        for name, value in re.findall(pattern, css):
            tokens[group][name] = value.strip()
    tokens["generated_at"] = datetime.now(timezone.utc).isoformat()
    return tokens


def extract_font_families(html: str, css: str) -> list[str]:
    families: set[str] = set()
    for match in re.findall(r"font-family\s*:\s*([^;}]+)", css):
        families.add(match.strip())
    for match in re.findall(r"fonts.googleapis.com/css2\?family=([^\"'&]+)", html):
        families.add(match.replace("+", " "))
    return sorted(families)


def extract_svg_assets(html: str, client: httpx.Client, limit: int = 30) -> list[str]:
    saved: list[str] = []
    refs = set(re.findall(r'(?:src|href)="([^"]+\.svg)"', html))
    for ref in list(refs)[:limit]:
        url = urljoin(BASE_URL, ref)
        content = _fetch(client, url)
        if not content:
            continue
        name = Path(urlparse(url).path).name or "asset.svg"
        _safe_write_bytes(REFERENCE / "svg" / name, content)
        saved.append(name)
    return saved


def extract_images(html: str, client: httpx.Client, limit: int = 24) -> list[str]:
    saved: list[str] = []
    urls = set(re.findall(r'(?:src|srcSet)="(https://[^"\s]+\.(?:jpg|jpeg|png|webp)[^"\s]*)"', html))
    urls |= {urljoin(BASE_URL, ref) for ref in re.findall(r'src="(/img/[^"]+\.(?:jpg|jpeg|png|webp))"', html)}
    for url in list(urls)[:limit]:
        content = _fetch(client, url)
        if not content:
            continue
        name = Path(urlparse(url).path).name or "image.jpg"
        _safe_write_bytes(REFERENCE / "img" / name, content)
        saved.append(name)
    return saved


def extract_editorial_cards(html: str) -> list[dict[str, str]]:
    """Heuristic extraction of inspiration card titles / images from markup."""
    cards: list[dict[str, str]] = []
    for match in re.finditer(r'<img[^>]+alt="([^"]+)"[^>]+src="([^"]+)"', html):
        alt, src = match.group(1), match.group(2)
        if not alt or alt.lower() in {"", "logo"}:
            continue
        if any(word in alt.lower() for word in ("icon", "logo", "qr", "arrow")):
            continue
        cards.append({"title": alt, "image": urljoin(BASE_URL, src)})
        if len(cards) >= 40:
            break
    return cards


import logging
logger = logging.getLogger("cloner")


def _safe_write_text(path: Path, content: str) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return True
    except Exception as exc:
        logger.warning("Could not write %s: %s", path, exc)
        return False


def _safe_write_bytes(path: Path, content: bytes) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return True
    except Exception as exc:
        logger.warning("Could not write %s: %s", path, exc)
        return False


def clone(offline: bool = False, limit: int = 24) -> dict[str, Any]:
    _ensure_dirs()
    html = ""
    css = ""
    source = "network"

    if offline or (LOCAL_HTML.exists() and LOCAL_CSS.exists()):
        if LOCAL_HTML.exists():
            html = LOCAL_HTML.read_text(encoding="utf-8", errors="ignore")
            _safe_write_text(REFERENCE / "layouts" / "mindtrip_home.html", html)
        if LOCAL_CSS.exists():
            css = LOCAL_CSS.read_text(encoding="utf-8", errors="ignore")
            _safe_write_text(REFERENCE / "css" / "mindtrip_styles.css", css)
        if html and css:
            source = "local-reference"

    if not html or not css:
        with httpx.Client(timeout=30, headers={"User-Agent": UA}, follow_redirects=True) as client:
            page = _fetch(client, BASE_URL)
            if page:
                html = page.decode("utf-8", errors="ignore")
                _safe_write_text(REFERENCE / "layouts" / "mindtrip_home.html", html)
                for href in re.findall(r'<link[^>]+rel="stylesheet"[^>]+href="([^"]+)"', html):
                    url = urljoin(BASE_URL, href)
                    content = _fetch(client, url)
                    if content:
                        css += content.decode("utf-8", errors="ignore")
                        name = Path(urlparse(url).path).name or "styles.css"
                        _safe_write_bytes(REFERENCE / "css" / name, content)
                if css:
                    _safe_write_text(REFERENCE / "css" / "mindtrip_styles.css", css)
                svgs = extract_svg_assets(html, client, limit=limit)
                images = extract_images(html, client, limit=limit)
                cards = extract_editorial_cards(html)
            else:
                svgs, images, cards = [], [], []
                source = "unavailable"
    else:
        svgs, images, cards = [], [], extract_editorial_cards(html)

    tokens = extract_tokens(css) if css else {"colors": {}, "fonts": {}, "radii": {}, "spacing": {}, "containers": {}, "misc": {}}
    tokens["font_families"] = extract_font_families(html, css)
    tokens["source"] = source
    tokens["html_bytes"] = len(html)
    tokens["css_bytes"] = len(css)
    _safe_write_text(REFERENCE / "design_tokens.json", json.dumps(tokens, indent=2, ensure_ascii=False))

    if cards:
        _safe_write_text(REFERENCE / "editorial_cards.json", json.dumps(cards, indent=2, ensure_ascii=False))

    summary = {
        "source": source,
        "tokens": {key: len(value) for key, value in tokens.items() if isinstance(value, dict)},
        "svg_assets": svgs,
        "images": images,
        "editorial_cards": len(cards),
        "output": str(REFERENCE),
    }
    _safe_write_text(REFERENCE / "clone_summary.json", json.dumps(summary, indent=2, ensure_ascii=False))
    return summary


def ensure_fixtures() -> None:
    fixture = FIXTURES / "sample_trips.json"
    if fixture.exists():
        return
    generator = ROOT / "scripts" / "generate_fixtures.py"
    if generator.exists():
        import runpy

        runpy.run_path(str(generator), run_name="__main__")


def _test() -> int:
    print("Mindtrip reference cloner — self test")
    summary = clone(offline=True)
    tokens_path = REFERENCE / "design_tokens.json"
    if not tokens_path.exists():
        print("FAIL: design_tokens.json missing")
        return 1
    tokens = json.loads(tokens_path.read_text(encoding="utf-8"))
    print(f"  source: {tokens.get('source')}")
    print(f"  colors: {len(tokens.get('colors', {}))}")
    print(f"  fonts:  {len(tokens.get('fonts', {}))}")
    print(f"  radii:  {len(tokens.get('radii', {}))}")
    print(f"  css:    {tokens.get('css_bytes', 0):,} bytes")
    ensure_fixtures()
    fixture = FIXTURES / "sample_trips.json"
    if not fixture.exists():
        print("FAIL: sample_trips.json missing")
        return 1
    data = json.loads(fixture.read_text(encoding="utf-8"))
    print(f"  fixtures: {len(data['places'])} places · {len(data['hotels'])} hotels · {len(data['trips'])} trips")
    print("PASS")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Clone Mindtrip reference assets")
    parser.add_argument("--test", action="store_true", help="Offline self test")
    parser.add_argument("--offline", action="store_true", help="Use local reference HTML/CSS only")
    parser.add_argument("--limit", type=int, default=24, help="Max SVGs/images to download")
    args = parser.parse_args()
    if args.test:
        raise SystemExit(_test())
    summary = clone(offline=args.offline, limit=args.limit)
    ensure_fixtures()
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
