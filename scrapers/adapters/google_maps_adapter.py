"""Ingest Google Maps scraper output in JSON or CSV form.

The adapter is deliberately forgiving about field names because Google Maps
scrapers in the wild use many conventions (camelCase, snake_case, nested
``location`` objects, ``reviews`` vs ``review_count``, etc.).

Usage:
    python -m scrapers.adapters.google_maps_adapter raw.json --out data/fixtures/places.json
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Iterable

try:
    from .base_adapter import AdapterResult, PlaceRecord
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scrapers.adapters.base_adapter import AdapterResult, PlaceRecord

FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "name": ("name", "title", "place_name", "business_name"),
    "category": ("category", "type", "place_type", "categories", "primary_type"),
    "destination": ("destination", "city", "locality", "search_city"),
    "description": ("description", "summary", "editorial_summary", "about"),
    "lat": ("lat", "latitude", "y", "location_lat"),
    "lon": ("lon", "lng", "longitude", "x", "location_lng"),
    "rating": ("rating", "stars", "average_rating", "google_rating"),
    "review_count": ("review_count", "reviews", "user_ratings_total", "reviewCount", "num_reviews"),
    "address": ("address", "formatted_address", "full_address", "location_address"),
    "price_level": ("price_level", "price", "priceLevel", "price_range"),
    "opening_hours": ("opening_hours", "hours", "open_hours", "working_hours"),
    "photos": ("photos", "images", "photo_urls", "image_urls"),
    "tags": ("tags", "labels", "features"),
    "id": ("id", "place_id", "google_id", "cid", "slug"),
}


def _pick(row: dict[str, Any], key: str) -> Any:
    for alias in FIELD_ALIASES[key]:
        if alias in row and row[alias] not in (None, ""):
            return row[alias]
    return None


def _flatten(row: dict[str, Any]) -> dict[str, Any]:
    """Pull common nested shapes up to the top level."""
    out = dict(row)
    location = row.get("location") or row.get("coordinates") or row.get("geometry")
    if isinstance(location, dict):
        if "lat" not in out and "latitude" not in out:
            out["lat"] = location.get("lat", location.get("latitude"))
        if "lng" not in out and "longitude" not in out:
            out["lng"] = location.get("lng", location.get("longitude"))
        coords = location.get("coordinates")
        if isinstance(coords, (list, tuple)) and len(coords) == 2:
            out.setdefault("lng", coords[0])
            out.setdefault("lat", coords[1])
    if "geometry" in row and isinstance(row["geometry"], dict):
        loc = row["geometry"].get("location", {})
        out.setdefault("lat", loc.get("lat"))
        out.setdefault("lng", loc.get("lng"))
    if isinstance(row.get("reviews"), list):
        out["review_count"] = len(row["reviews"])
    return out


def _to_record(row: dict[str, Any], destination: str = "") -> PlaceRecord | None:
    row = _flatten(row)
    name = _pick(row, "name")
    lat, lon = _pick(row, "lat"), _pick(row, "lon")
    if not name or lat is None or lon is None:
        return None
    price = _pick(row, "price_level")
    if isinstance(price, str):
        # "$", "$$", "$$$" or "2" -> integer 0-4
        digits = "".join(ch for ch in price if ch.isdigit())
        price = int(digits) if digits else min(4, max(0, price.count("$")))
    return PlaceRecord(
        id=_pick(row, "id") or "",
        name=str(name),
        category=_pick(row, "category") or "other",
        destination=str(_pick(row, "destination") or destination),
        description=str(_pick(row, "description") or ""),
        lat=float(lat),
        lon=float(lon),
        rating=float(_pick(row, "rating")) if _pick(row, "rating") is not None else None,
        review_count=int(_pick(row, "review_count") or 0),
        address=str(_pick(row, "address") or ""),
        price_level=price,
        opening_hours=str(_pick(row, "opening_hours") or ""),
        photos=_pick(row, "photos") or [],
        tags=_pick(row, "tags") or [],
        source="google_maps",
        metadata={k: v for k, v in row.items() if k not in {"photos", "reviews", "location", "geometry"}},
    )


def _iter_rows(path: Path) -> Iterable[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            yield from csv.DictReader(fh)
        return
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        for key in ("results", "places", "data", "items"):
            if isinstance(payload.get(key), list):
                payload = payload[key]
                break
    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list):
        raise ValueError("Expected a JSON list or an object with results/places/data/items")
    yield from payload


def ingest(path: str | Path, destination: str = "") -> AdapterResult:
    path = Path(path)
    records: list[PlaceRecord] = []
    warnings: list[str] = []
    skipped = 0
    for index, row in enumerate(_iter_rows(path)):
        try:
            record = _to_record(row, destination)
        except Exception as exc:  # noqa: BLE001 - report and continue
            warnings.append(f"row {index}: {exc}")
            skipped += 1
            continue
        if record is None:
            warnings.append(f"row {index}: missing name or coordinates")
            skipped += 1
            continue
        records.append(record)
    return AdapterResult(source="google_maps", total=len(records), records=records, skipped=skipped, warnings=warnings[:20])


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalise Google Maps scraper output")
    parser.add_argument("input", help="JSON or CSV file")
    parser.add_argument("--destination", default="", help="Fallback destination slug")
    parser.add_argument("--out", default="", help="Write normalised JSON here")
    args = parser.parse_args()
    result = ingest(args.input, args.destination)
    payload = result.model_dump(mode="json")
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {len(result.records)} places to {args.out} ({result.skipped} skipped)")
    else:
        print(text)


if __name__ == "__main__":
    main()
