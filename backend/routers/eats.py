"""Eats / dining discovery endpoints with live Google Maps restaurant scraper."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import Session

from backend.database.db import get_session
from backend.services import data_service
from scrapers.restaurant_scraper_runner import (
    run_restaurant_scraper,
    scrape_google_maps_restaurants,
)

router = APIRouter(prefix="/eats", tags=["eats"])
log = logging.getLogger("eats_router")

EAT_CATEGORIES = [
    {"key": "restaurant", "label": "Restaurants", "icon": "SpoonFork"},
    {"key": "cafe", "label": "Cafes", "icon": "Coffee"},
    {"key": "bar", "label": "Bars & Pubs", "icon": "Wine"},
    {"key": "bakery", "label": "Bakeries", "icon": "Wheat"},
    {"key": "other", "label": "Other Eats", "icon": "Utensils"},
]


class EatsSearchRequest(BaseModel):
    destination: str = Field(default="", description="Destination city name, e.g. Delhi, Paris, Bangkok")
    category: str = Field(default="restaurant", description="restaurant | cafe | bar | bakery | other")
    query: str = Field(default="", description="Free-text search within eats results")
    max_results: int = Field(default=20, ge=1, le=50, description="Max results")
    live: bool = Field(default=True, description="Attempt live Google Maps scrape if results are empty")


@router.get("/categories")
def list_eat_categories() -> dict[str, Any]:
    """Return available eat/dining categories for the frontend filter chips."""
    return {"categories": EAT_CATEGORIES}


@router.get("")
@router.get("/")
def list_eats(
    destination: str = Query(default="", description="Destination city name"),
    category: str = Query(default="restaurant", description="restaurant | cafe | bar | bakery | other"),
    q: str = Query(default="", description="Free-text search"),
    limit: int = Query(default=50, ge=1, le=200),
    auto_scrape: bool = Query(default=True, description="Live-scrape if DB results are empty"),
    live: bool = Query(default=True),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """List eats places for a destination, optionally filtered by category."""
    dest_filter = str(destination or "").strip()
    category_filter = str(category or "restaurant").strip().lower()
    query_filter = str(q or "").strip()

    rows: list[dict[str, Any]] = []

    # Always live-scrape when requested (fast mode). Fall back to DB only if
    # the scrape returns nothing, so users always get fresh results.
    if dest_filter and auto_scrape and live:
        try:
            log.info("Live scraping eats for '%s' (%s) (fast mode)...", dest_filter, category_filter)
            run_restaurant_scraper(dest_filter, max_count=limit, place_type=category_filter, fast_mode=True)
            rows = data_service.list_places(
                session,
                destination=dest_filter,
                category=category_filter,
                query=query_filter,
                limit=limit,
            )
        except Exception as exc:
            log.warning("Live eats scraping failed for '%s': %s", dest_filter, exc)
            rows = data_service.list_places(
                session,
                destination=dest_filter,
                category=category_filter,
                query=query_filter,
                limit=limit,
            )
    else:
        rows = data_service.list_places(
            session,
            destination=dest_filter,
            category=category_filter,
            query=query_filter,
            limit=limit,
        )

    return {
        "eats": rows,
        "count": len(rows),
        "destination": dest_filter,
        "category": category_filter,
        "categories": EAT_CATEGORIES,
    }


@router.post("/search")
def search_eats_live(
    payload: EatsSearchRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Live-search eats places and persist them to the DB."""
    dest = str(payload.destination or "").strip()
    category = str(payload.category or "restaurant").strip().lower()
    query = str(payload.query or "").strip()

    if not dest:
        raise HTTPException(status_code=400, detail="Destination is required")

    scraped = run_restaurant_scraper(dest, max_count=payload.max_results, place_type=category, fast_mode=True)

    rows = data_service.list_places(
        session,
        destination=dest,
        category=category,
        query=query,
        limit=payload.max_results,
    )

    return {
        "eats": rows,
        "count": len(rows),
        "destination": dest,
        "category": category,
        "scraped_count": len(scraped),
        "source": "google_maps_live",
    }


@router.get("/{eat_id}")
def get_eat(eat_id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    """Get a single eat/place detail by ID."""
    place = data_service.get_place(session, eat_id)
    if not place:
        raise HTTPException(status_code=404, detail="Eat place not found")
    return place


@router.get("/{eat_id}/detail")
def get_eat_detail(
    eat_id: str,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Scrape the live Google Maps detail page for a single place on demand.

    Returns real address, phone, website, hours, menu, reviews and photos.
    """
    place = data_service.get_place(session, eat_id)
    if not place:
        raise HTTPException(status_code=404, detail="Eat place not found")

    dest = str(getattr(place, "destination", "") or "")
    name = str(getattr(place, "name", "") or "")
    place_category = str(getattr(place, "category", "") or "restaurant")

    try:
        scraped = run_restaurant_scraper(dest, max_count=1, place_type=place_category, fast_mode=False)
        if scraped:
            detail = scraped[0]
            # Merge with stored record fields
            detail["id"] = eat_id
            detail["source"] = "google_maps_live_detail"
            return detail
    except Exception as exc:
        log.warning("Live detail scrape failed for %s: %s", name, exc)

    # Fallback: return stored place data
    return data_service.get_place(session, eat_id)
