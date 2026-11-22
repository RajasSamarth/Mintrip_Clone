"""Hotel scraper — httpx + BeautifulSoup, with optional Playwright rendering.

Extracts JSON-LD, Open Graph, price hints and amenity keywords from a hotel
page and normalises everything into ``HotelRecord``.

Examples
--------
    python -m scrapers.hotel_scraper --url https://example-hotel.com --destination kyoto
    python -m scrapers.hotel_scraper --demo --out data/fixtures/hotels_scraped.json
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

try:
    from .adapters.base_adapter import HotelRecord
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scrapers.adapters.base_adapter import HotelRecord

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"

AMENITY_KEYWORDS: dict[str, str] = {
    "free wifi": "Free wifi", "wi-fi": "Free wifi", "wifi": "Free wifi",
    "pool": "Pool", "spa": "Spa", "breakfast": "Breakfast", "gym": "Fitness centre",
    "fitness": "Fitness centre", "parking": "Parking", "restaurant": "Restaurant",
    "bar": "Bar", "air conditioning": "Air conditioning", "pet": "Pet friendly",
    "airport shuttle": "Airport shuttle", "beach": "Beach access", "sauna": "Sauna",
}


def _text(node: Any) -> str:
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)) if node else ""


def _parse_price(text: str) -> float | None:
    match = re.search(r"(?:US\$|\$|€|£)\s?([\d,]+(?:\.\d{1,2})?)", text or "")
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return None


def _amenities(text: str) -> list[str]:
    lowered = text.lower()
    found = [label for needle, label in AMENITY_KEYWORDS.items() if needle in lowered]
    return sorted(set(found))


def parse_html(html: str, url: str = "", destination: str = "") -> HotelRecord:
    soup = BeautifulSoup(html, "lxml")

    # 1. Prefer JSON-LD Hotel schema.
    name = ""
    description = ""
    address = ""
    rating: float | None = None
    review_count = 0
    lat = lon = None
    photos: list[str] = []
    price: float | None = None
    stars = 0

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            payload = json.loads(script.string or "{}")
        except json.JSONDecodeError:
            continue
        items = payload if isinstance(payload, list) else [payload]
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("@type") not in {"Hotel", "LodgingBusiness", "Resort"}:
                continue
            name = item.get("name", name)
            description = item.get("description", description)
            addr = item.get("address", {})
            if isinstance(addr, dict):
                address = ", ".join(filter(None, [addr.get("streetAddress"), addr.get("addressLocality"), addr.get("addressCountry")]))
            geo = item.get("geo", {})
            if isinstance(geo, dict):
                lat = geo.get("latitude") or lat
                lon = geo.get("longitude") or lon
            stars = int(item.get("starRating", {}).get("ratingValue", stars) or stars) if isinstance(item.get("starRating"), dict) else stars
            aggregate = item.get("aggregateRating", {})
            if isinstance(aggregate, dict):
                rating = float(aggregate.get("ratingValue", rating) or rating or 0) or rating
                review_count = int(aggregate.get("reviewCount", review_count) or review_count)
            image = item.get("image")
            if isinstance(image, str):
                photos.append(urljoin(url, image))
            elif isinstance(image, list):
                photos.extend(urljoin(url, img) for img in image if isinstance(img, str))
            offers = item.get("priceRange") or item.get("offers")
            if isinstance(offers, str):
                price = _parse_price(offers) or price
            elif isinstance(offers, dict):
                price = _parse_price(str(offers.get("price", ""))) or price

    # 2. Fall back to Open Graph / meta / headings.
    name = name or (soup.find("meta", property="og:title") or {}).get("content", "") or _text(soup.find("h1"))
    description = description or (soup.find("meta", property="og:description") or {}).get("content", "") or (soup.find("meta", attrs={"name": "description"}) or {}).get("content", "")
    if not photos:
        og_image = (soup.find("meta", property="og:image") or {}).get("content", "")
        if og_image:
            photos.append(urljoin(url, og_image))
    for image in soup.find_all("img"):
        src = image.get("src") or image.get("data-src") or ""
        if src and any(ext in src.lower() for ext in (".jpg", ".jpeg", ".webp", ".png")) and src not in photos:
            photos.append(urljoin(url, src))
        if len(photos) >= 8:
            break

    body_text = _text(soup)
    if price is None:
        price = _parse_price(body_text)
    if rating is None:
        match = re.search(r"(\d(?:\.\d)?)\s*(?:/|out of)\s*5", body_text)
        if match:
            rating = float(match.group(1))

    # 3. Room hints.
    room_types: list[dict[str, Any]] = []
    for node in soup.select("[class*='room'], [data-room], h3, h4")[:40]:
        label = _text(node)
        if not label or len(label) > 70:
            continue
        if any(word in label.lower() for word in ("room", "suite", "king", "queen", "double", "twin")):
            if not any(room["name"] == label for room in room_types):
                room_types.append({"name": label, "price": None, "size": "", "bed": ""})
        if len(room_types) >= 4:
            break

    return HotelRecord(
        name=name or "Untitled hotel",
        destination=destination,
        stars=stars,
        rating=rating,
        review_count=review_count,
        address=address,
        lat=float(lat) if lat else None,
        lon=float(lon) if lon else None,
        price_per_night=price,
        amenities=_amenities(body_text),
        photos=photos[:8],
        room_types=room_types,
        booking_url=url,
        description=description,
        source="hotel_scraper",
        metadata={"url": url},
    )


def scrape(url: str, destination: str = "", render: bool = False) -> HotelRecord:
    html = ""
    if render:
        try:
            from playwright.sync_api import sync_playwright  # type: ignore

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(user_agent=USER_AGENT)
                page.goto(url, wait_until="networkidle", timeout=45000)
                html = page.content()
                browser.close()
        except Exception:  # noqa: BLE001 - fall back to httpx
            html = ""
    if not html:
        with httpx.Client(timeout=30, headers={"User-Agent": USER_AGENT}, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            html = response.text
    return parse_html(html, url=url, destination=destination)


def demo_records() -> list[HotelRecord]:
    """Parse a bundled sample so the pipeline can be tested without network."""
    fixture = Path(__file__).resolve().parents[1] / "data" / "fixtures" / "sample_trips.json"
    if not fixture.exists():
        return []
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    return [HotelRecord(**row) for row in payload.get("hotels", [])]


def main() -> None:
    parser = argparse.ArgumentParser(description="Hotel web scraper")
    parser.add_argument("--url", default="", help="Hotel page to scrape")
    parser.add_argument("--destination", default="")
    parser.add_argument("--render", action="store_true", help="Use Playwright for JS-heavy pages")
    parser.add_argument("--demo", action="store_true", help="Emit bundled demo hotel records")
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    records: list[HotelRecord] = []
    if args.demo:
        records = demo_records()
    elif args.url:
        records = [scrape(args.url, args.destination, args.render)]
    else:
        parser.error("Provide --url or --demo")

    text = json.dumps([record.model_dump(mode="json") for record in records], indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {len(records)} hotel(s) to {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
