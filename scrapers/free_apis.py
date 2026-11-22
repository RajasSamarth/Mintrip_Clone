"""100% free data sources used across the clone.

Every function degrades gracefully: if a public endpoint is unreachable, a
deterministic fallback is returned so the UI and agent never hard-fail.

Sources
-------
* Nominatim / Overpass (OpenStreetMap) — geocoding & POIs
* Wikivoyage MediaWiki API — destination editorial copy
* OSRM — walking / cycling / driving durations
* Unsplash — optional API search, plus a curated static CDN fallback
"""

from __future__ import annotations

import argparse
import json
import math
import os
import time
from pathlib import Path
from typing import Any

import httpx

USER_AGENT = "MindtripClone/1.0 (local development; contact: dev@example.com)"
CACHE_DIR = Path(__file__).resolve().parents[1] / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

NOMINATIM_URL = "https://nominatim.openstreetmap.org"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
WIKIVOYAGE_URL = "https://en.wikivoyage.org/w/api.php"
OSRM_URL = "https://router.project-osrm.org"
UNSPLASH_URL = "https://api.unsplash.com"

# Static, licence-friendly fallback imagery (Unsplash CDN).
FALLBACK_IMAGES: dict[str, str] = {
    "kyoto": "https://images.unsplash.com/photo-1493976040374-85c8e12f0c0e?auto=format&fit=crop&w=1600&q=80",
    "rome": "https://images.unsplash.com/photo-1552832230-c0197dd311b5?auto=format&fit=crop&w=1600&q=80",
    "swiss-alps": "https://images.unsplash.com/photo-1533105079780-92b9be482077?auto=format&fit=crop&w=1600&q=80",
    "tokyo": "https://images.unsplash.com/photo-1540959733332-eab4deabeeaf?auto=format&fit=crop&w=1600&q=80",
    "paris": "https://images.unsplash.com/photo-1502602898657-3e91760cbb34?auto=format&fit=crop&w=1600&q=80",
    "lisbon": "https://images.unsplash.com/photo-1555881400-74d7acaacd8b?auto=format&fit=crop&w=1600&q=80",
    "default": "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?auto=format&fit=crop&w=1600&q=80",
}


def _client(timeout: float = 20.0) -> httpx.Client:
    return httpx.Client(
        timeout=timeout,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        follow_redirects=True,
    )


def _cache_path(key: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in key)[:120]
    return CACHE_DIR / f"{safe}.json"


def _read_cache(key: str, max_age: int = 86400) -> Any | None:
    path = _cache_path(key)
    if not path.exists():
        return None
    if time.time() - path.stat().st_mtime > max_age:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _write_cache(key: str, value: Any) -> None:
    try:
        _cache_path(key).write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


# --------------------------------------------------------------------------- #
# Nominatim / Overpass
# --------------------------------------------------------------------------- #
def geocode(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Forward geocode a free-text query. Returns [] on failure."""
    cached = _read_cache(f"geocode_{query}_{limit}")
    if cached is not None:
        return cached
    try:
        with _client() as client:
            response = client.get(
                f"{NOMINATIM_URL}/search",
                params={"q": query, "format": "jsonv2", "addressdetails": 1, "limit": limit},
            )
            response.raise_for_status()
            rows = response.json()
        results = [
            {
                "name": row.get("display_name", "").split(",")[0],
                "display_name": row.get("display_name", ""),
                "lat": float(row["lat"]),
                "lon": float(row["lon"]),
                "type": row.get("type", ""),
                "category": row.get("class", ""),
                "country_code": (row.get("address") or {}).get("country_code", ""),
                "bounding_box": row.get("boundingbox", []),
                "source": "nominatim",
            }
            for row in rows
            if row.get("lat") and row.get("lon")
        ]
        _write_cache(f"geocode_{query}_{limit}", results)
        return results
    except Exception:  # noqa: BLE001 - offline friendly
        return []


def reverse_geocode(lat: float, lon: float) -> dict[str, Any]:
    cached = _read_cache(f"reverse_{lat}_{lon}")
    if cached is not None:
        return cached
    try:
        with _client() as client:
            response = client.get(
                f"{NOMINATIM_URL}/reverse",
                params={"lat": lat, "lon": lon, "format": "jsonv2", "addressdetails": 1},
            )
            response.raise_for_status()
            row = response.json()
        result = {
            "display_name": row.get("display_name", ""),
            "address": row.get("address", {}),
            "lat": lat,
            "lon": lon,
            "source": "nominatim",
        }
        _write_cache(f"reverse_{lat}_{lon}", result)
        return result
    except Exception:  # noqa: BLE001
        return {"display_name": "", "address": {}, "lat": lat, "lon": lon, "source": "fallback"}


def overpass_pois(lat: float, lon: float, radius: int = 1200, category: str = "restaurant", limit: int = 30) -> list[dict[str, Any]]:
    """Find nearby POIs with Overpass. ``category`` maps to an OSM tag value."""
    category_map = {
        "restaurant": ('amenity', 'restaurant'),
        "cafe": ('amenity', 'cafe'),
        "bar": ('amenity', 'bar'),
        "hotel": ('tourism', 'hotel'),
        "attraction": ('tourism', 'attraction'),
        "museum": ('tourism', 'museum'),
        "activity": ('tourism', 'attraction'),
    }
    key, value = category_map.get(category, ('tourism', 'attraction'))
    query = f"""
    [out:json][timeout:25];
    (
      node["{key}"="{value}"](around:{radius},{lat},{lon});
      way["{key}"="{value}"](around:{radius},{lat},{lon});
    );
    out center {limit};
    """
    try:
        with _client(timeout=30) as client:
            response = client.post(OVERPASS_URL, data={"data": query})
            response.raise_for_status()
            payload = response.json()
        results = []
        for element in payload.get("elements", [])[:limit]:
            center = element.get("center") or {}
            tags = element.get("tags") or {}
            poi_lat = element.get("lat", center.get("lat"))
            poi_lon = element.get("lon", center.get("lon"))
            if poi_lat is None or poi_lon is None or not tags.get("name"):
                continue
            results.append(
                {
                    "id": f"osm-{element.get('type', 'node')}-{element.get('id')}",
                    "name": tags.get("name"),
                    "category": category,
                    "lat": float(poi_lat),
                    "lon": float(poi_lon),
                    "address": " ".join(
                        filter(None, [tags.get("addr:housenumber"), tags.get("addr:street"), tags.get("addr:city")])
                    ),
                    "rating": None,
                    "photos": [],
                    "tags": [v for k, v in tags.items() if k in {"cuisine", "tourism", "amenity"}],
                    "opening_hours": tags.get("opening_hours", ""),
                    "source": "openstreetmap",
                }
            )
        return results
    except Exception:  # noqa: BLE001
        return []


# --------------------------------------------------------------------------- #
# Wikivoyage
# --------------------------------------------------------------------------- #
def wikivoyage_summary(destination: str, sentences: int = 4) -> dict[str, Any]:
    cached = _read_cache(f"wikivoyage_{destination}")
    if cached is not None:
        return cached
    title = destination.strip().replace(" ", "_").title()
    try:
        with _client() as client:
            response = client.get(
                WIKIVOYAGE_URL,
                params={
                    "action": "query",
                    "format": "json",
                    "prop": "extracts",
                    "exintro": 1,
                    "explaintext": 1,
                    "redirects": 1,
                    "titles": title,
                },
            )
            response.raise_for_status()
            pages = response.json().get("query", {}).get("pages", {})
            page = next(iter(pages.values()), {})
        extract = page.get("extract", "") or ""
        parts = [p.strip() for p in extract.split("\n") if p.strip()]
        summary = " ".join(parts[:sentences])
        result = {"title": page.get("title", title), "summary": summary, "source": "wikivoyage"}
        _write_cache(f"wikivoyage_{destination}", result)
        return result
    except Exception:  # noqa: BLE001
        return {"title": title, "summary": "", "source": "fallback"}


# --------------------------------------------------------------------------- #
# OSRM
# --------------------------------------------------------------------------- #
def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def osrm_route(
    origin: tuple[float, float],
    destination: tuple[float, float],
    profile: str = "driving",
) -> dict[str, Any]:
    """Return distance/duration/geometry between (lat, lon) pairs.

    Falls back to haversine + walking speed when the public demo is unreachable.
    """
    profile = profile if profile in {"driving", "walking", "cycling"} else "driving"
    osrm_profile = {"driving": "driving", "walking": "foot", "cycling": "bike"}[profile]
    coords = f"{origin[1]},{origin[0]};{destination[1]},{destination[0]}"
    try:
        with _client(timeout=20) as client:
            response = client.get(
                f"{OSRM_URL}/route/v1/{osrm_profile}/{coords}",
                params={"overview": "full", "geometries": "geojson", "steps": "false"},
            )
            if response.status_code != 200 and osrm_profile != "driving":
                response = client.get(
                    f"{OSRM_URL}/route/v1/driving/{coords}",
                    params={"overview": "full", "geometries": "geojson"},
                )
            response.raise_for_status()
            payload = response.json()
        route = payload["routes"][0]
        distance_km = route["distance"] / 1000
        duration_min = route["duration"] / 60
        if osrm_profile != "driving" and profile == "walking":
            # The demo server may return a driving route for foot; re-estimate.
            duration_min = max(duration_min, distance_km / 4.8 * 60)
        return {
            "profile": profile,
            "distance_km": round(distance_km, 2),
            "duration_minutes": max(1, round(duration_min)),
            "geometry": route.get("geometry", {}).get("coordinates", []),
            "source": "osrm",
        }
    except Exception:  # noqa: BLE001
        distance = _haversine_km(origin[0], origin[1], destination[0], destination[1]) * 1.25
        speed = {"walking": 4.8, "cycling": 14, "driving": 32}[profile]
        return {
            "profile": profile,
            "distance_km": round(distance, 2),
            "duration_minutes": max(1, round(distance / speed * 60)),
            "geometry": [[origin[1], origin[0]], [destination[1], destination[0]]],
            "source": "haversine-fallback",
        }


def transit_label(route: dict[str, Any]) -> str:
    minutes = route.get("duration_minutes", 0)
    profile = route.get("profile", "driving")
    icon = {"walking": "walk", "cycling": "cycle", "driving": "drive"}.get(profile, "drive")
    return f"{minutes} min {icon}"


# --------------------------------------------------------------------------- #
# Imagery
# --------------------------------------------------------------------------- #
def destination_image(query: str) -> str:
    """Unsplash search when a key exists, else a curated static image."""
    key = os.getenv("UNSPLASH_ACCESS_KEY", "").strip()
    slug = query.strip().lower().replace(" ", "-")
    if key:
        try:
            with _client() as client:
                response = client.get(
                    f"{UNSPLASH_URL}/search/photos",
                    params={"query": query, "per_page": 1, "orientation": "landscape"},
                    headers={"Authorization": f"Client-ID {key}"},
                )
                response.raise_for_status()
                results = response.json().get("results", [])
            if results:
                return results[0]["urls"]["regular"]
        except Exception:  # noqa: BLE001
            pass
    return FALLBACK_IMAGES.get(slug, FALLBACK_IMAGES["default"])


def _self_test() -> int:
    print("→ Nominatim geocode: Kyoto, Japan")
    matches = geocode("Kyoto, Japan", limit=1)
    print("  ", matches[0]["display_name"] if matches else "unavailable (offline fallback)")

    print("→ OSRM route: Fushimi Inari → Kiyomizu-dera (walking)")
    route = osrm_route((34.9671, 135.7727), (34.9949, 135.7850), "walking")
    print("  ", route)

    print("→ Wikivoyage summary: Kyoto")
    summary = wikivoyage_summary("Kyoto")
    print("  ", (summary.get("summary") or "unavailable")[:180], "...")

    print("→ Overpass POIs: restaurants near Gion")
    pois = overpass_pois(35.0037, 135.7752, 500, "restaurant", 3)
    print("  ", [poi["name"] for poi in pois] or "unavailable (offline fallback)")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Free travel data sources")
    parser.add_argument("--test", action="store_true", help="Run a live smoke test")
    args = parser.parse_args()
    if args.test:
        raise SystemExit(_self_test())
    print(json.dumps({"geocode": geocode("Kyoto")[:1], "route": osrm_route((35.0, 135.7), (35.01, 135.78))}, indent=2))
