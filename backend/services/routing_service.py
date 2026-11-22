"""Routing helpers built on OSRM with an offline haversine fallback."""

from __future__ import annotations

import math
from typing import Any

from backend.config import get_settings

settings = get_settings()


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def _fallback(origin: tuple[float, float], destination: tuple[float, float], profile: str) -> dict[str, Any]:
    distance = haversine_km(origin[0], origin[1], destination[0], destination[1]) * 1.25
    speed = {"walking": 4.8, "cycling": 14, "driving": 32}.get(profile, 32)
    return {
        "profile": profile,
        "distance_km": round(distance, 2),
        "duration_minutes": max(1, round(distance / speed * 60)),
        "geometry": [[origin[1], origin[0]], [destination[1], destination[0]]],
        "source": "haversine-fallback",
    }


def calculate_route(
    origin: tuple[float, float],
    destination: tuple[float, float],
    profile: str = "walking",
) -> dict[str, Any]:
    """Calculate a route. Uses OSRM when ENABLE_LIVE_ROUTING=true."""
    current_settings = get_settings()
    if not current_settings.enable_live_routing:
        return _fallback(origin, destination, profile)
    try:
        from scrapers.free_apis import osrm_route

        return osrm_route(origin, destination, profile)
    except Exception:  # noqa: BLE001
        return _fallback(origin, destination, profile)


def transit_label(route: dict[str, Any]) -> str:
    minutes = route.get("duration_minutes", 0)
    profile = route.get("profile", "walking")
    noun = {"walking": "walk", "cycling": "cycle", "driving": "drive"}.get(profile, "transit")
    return f"{minutes} min {noun}"
