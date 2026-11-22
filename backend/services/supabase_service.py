"""Supabase persistence and synchronization service for places, restaurants, and amenities.

Allows storing and retrieving places directly to/from Supabase tables ('places').
Gracefully handles missing credentials or network issues with automatic local fallback.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.config import get_settings

logger = logging.getLogger("mindtrip.supabase")

_supabase_client = None
_client_initialized = False
_quota_exceeded = False
_quota_warning_logged = False


def _check_and_mark_quota(exc: Exception) -> bool:
    """Check if the error is related to Supabase storage / free tier quota limit."""
    global _quota_exceeded, _quota_warning_logged
    msg = str(exc).lower()
    quota_indicators = (
        "quota",
        "storage",
        "limit",
        "exceeded",
        "disk",
        "capacity",
        "payment",
        "billing",
        "tier",
        "507",
        "413",
        "402",
        "resource exhausted",
    )
    if any(ind in msg for ind in quota_indicators):
        _quota_exceeded = True
        if not _quota_warning_logged:
            _quota_warning_logged = True
            logger.warning(
                "Supabase free tier storage / quota limit reached (%s). "
                "Disabling remote Supabase persistence; local SQLite database remains active as primary source.",
                exc,
            )
        return True
    return False


def get_supabase_client():
    """Lazily initialize and return the Supabase client if credentials are configured."""
    global _supabase_client, _client_initialized, _quota_exceeded
    if _quota_exceeded:
        return None
    if _client_initialized:
        return _supabase_client

    _client_initialized = True
    settings = get_settings()
    url = (settings.supabase_url or "").strip()
    key = (settings.supabase_service_role_key or settings.supabase_key or "").strip()

    if not url or not key:
        logger.debug("Supabase credentials not configured; local storage will be primary.")
        return None

    try:
        from supabase import create_client
        _supabase_client = create_client(url, key)
        logger.info("Supabase client initialized successfully (%s)", url)
        return _supabase_client
    except Exception as exc:
        if not _check_and_mark_quota(exc):
            logger.warning("Could not initialize Supabase client: %s", exc)
        return None


def is_supabase_enabled() -> bool:
    """Return True if Supabase client is configured and available."""
    global _quota_exceeded
    if _quota_exceeded:
        return False
    return get_supabase_client() is not None


def sync_place_to_supabase(place_data: dict[str, Any]) -> bool:
    """Upsert a single Place dictionary into Supabase 'places' table."""
    client = get_supabase_client()
    if not client:
        return False

    try:
        # Prepare payload matching standard Supabase places schema
        row = {
            "id": place_data.get("id"),
            "name": place_data.get("name"),
            "category": place_data.get("category", "other"),
            "destination": place_data.get("destination", "").lower(),
            "city": place_data.get("city", ""),
            "country": place_data.get("country", ""),
            "description": place_data.get("description", ""),
            "lat": float(place_data.get("lat") or 0.0),
            "lon": float(place_data.get("lon") or 0.0),
            "rating": float(place_data.get("rating") or 0.0) if place_data.get("rating") is not None else None,
            "review_count": int(place_data.get("review_count") or 0),
            "address": place_data.get("address", ""),
            "price_level": place_data.get("price_level"),
            "opening_hours": place_data.get("opening_hours", ""),
            "photos": place_data.get("photos", []),
            "tags": place_data.get("tags", []),
        }

        # Clean None id
        if not row["id"]:
            return False

        res = client.table("places").upsert(row).execute()
        logger.info("Successfully synced place '%s' to Supabase", row["name"])
        return True
    except Exception as exc:
        if not _check_and_mark_quota(exc):
            logger.warning("Failed to sync place '%s' to Supabase: %s", place_data.get("name"), exc)
        return False


def sync_places_batch_to_supabase(places: list[dict[str, Any]]) -> int:
    """Upsert a list of places into Supabase in bulk."""
    client = get_supabase_client()
    if not client or not places:
        return 0

    success_count = 0
    for p in places:
        if sync_place_to_supabase(p):
            success_count += 1
    return success_count


def fetch_places_from_supabase(destination: str, query: str = "", limit: int = 15) -> list[dict[str, Any]]:
    """Query places from Supabase matching destination and optional category/tag query."""
    client = get_supabase_client()
    if not client:
        return []

    try:
        dest_clean = destination.strip().lower()
        req = client.table("places").select("*").eq("destination", dest_clean)
        if query:
            q_clean = query.strip().lower()
            req = req.or_(f"category.ilike.%{q_clean}%,name.ilike.%{q_clean}%,description.ilike.%{q_clean}%")

        res = req.limit(limit).execute()
        return res.data or []
    except Exception as exc:
        if not _check_and_mark_quota(exc):
            logger.warning("Failed to query Supabase places for %s (%s): %s", destination, query, exc)
        return []
