"""Experiences discovery endpoints with live Google Maps scraper."""

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
)

router = APIRouter(prefix="/experiences", tags=["experiences"])
log = logging.getLogger("experiences_router")

EXPERIENCE_CATEGORIES = [
    {"key": "activity", "label": "Tours & Activities"},
    {"key": "attraction", "label": "Museums & Attractions"},
    {"key": "tour", "label": "Guided Tours"},
    {"key": "outdoor", "label": "Outdoor & Adventure"},
    {"key": "class", "label": "Classes & Workshops"},
    {"key": "food", "label": "Food & Drink"},
    {"key": "nightlife", "label": "Nightlife"},
    {"key": "family", "label": "Family & Kids"},
]


class ExperienceSearchRequest(BaseModel):
    destination: str = Field(default="", description="Destination city name, e.g. Delhi, Paris, Bangkok")
    category: str = Field(default="activity", description="Activity category")
    query: str = Field(default="", description="Free-text search within experiences")
    max_results: int = Field(default=20, ge=1, le=50, description="Max results")
    live: bool = Field(default=True, description="Attempt live Google Maps scrape")


@router.get("/categories")
def list_experience_categories() -> dict[str, Any]:
    """Return available experience categories for the frontend filter chips."""
    return {"categories": EXPERIENCE_CATEGORIES}


@router.get("")
@router.get("/")
def list_experiences(
    destination: str = Query(default="", description="Destination city name"),
    category: str = Query(default="activity", description="Experience category"),
    q: str = Query(default="", description="Free-text search"),
    limit: int = Query(default=50, ge=1, le=200),
    auto_scrape: bool = Query(default=True, description="Live-scrape if DB results are empty"),
    live: bool = Query(default=True),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """List experiences for a destination, optionally filtered by category."""
    dest_filter = str(destination or "").strip()
    category_filter = str(category or "activity").strip().lower()
    query_filter = str(q or "").strip()

    # Map frontend category to scraper place_type
    scraper_type = category_filter if category_filter in ("activity", "attraction", "tour", "museum") else "activity"

    rows: list[dict[str, Any]] = []

    if dest_filter and auto_scrape and live:
        try:
            log.info("Live scraping experiences for '%s' (%s) (fast mode)...", dest_filter, category_filter)
            run_restaurant_scraper(dest_filter, max_count=limit, place_type=scraper_type, fast_mode=True)
            rows = data_service.list_places(
                session,
                destination=dest_filter,
                category=category_filter,
                query=query_filter,
                limit=limit,
            )
        except Exception as exc:
            log.warning("Live experience scraping failed for '%s': %s", dest_filter, exc)
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
        "experiences": rows,
        "count": len(rows),
        "destination": dest_filter,
        "category": category_filter,
        "categories": EXPERIENCE_CATEGORIES,
    }


@router.post("/search")
def search_experiences_live(
    payload: ExperienceSearchRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Live-search experiences places and persist them to the DB."""
    dest = str(payload.destination or "").strip()
    category = str(payload.category or "activity").strip().lower()
    query = str(payload.query or "").strip()

    if not dest:
        raise HTTPException(status_code=400, detail="Destination is required")

    scraper_type = category if category in ("activity", "attraction", "tour", "museum") else "activity"
    scraped = run_restaurant_scraper(dest, max_count=payload.max_results, place_type=scraper_type, fast_mode=True)

    rows = data_service.list_places(
        session,
        destination=dest,
        category=category,
        query=query,
        limit=payload.max_results,
    )

    return {
        "experiences": rows,
        "count": len(rows),
        "destination": dest,
        "category": category,
        "scraped_count": len(scraped),
        "source": "google_maps_live",
    }


@router.get("/{experience_id}")
def get_experience(experience_id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    """Get a single experience/place detail by ID."""
    place = data_service.get_place(session, experience_id)
    if not place:
        raise HTTPException(status_code=404, detail="Experience not found")
    return place


@router.get("/{experience_id}/detail")
def get_experience_detail(
    experience_id: str,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Scrape the live Google Maps detail page for a single experience on demand."""
    place = data_service.get_place(session, experience_id)
    if not place:
        raise HTTPException(status_code=404, detail="Experience not found")

    dest = str(getattr(place, "destination", "") or "")
    name = str(getattr(place, "name", "") or "")
    place_category = str(getattr(place, "category", "") or "activity")

    try:
        scraped = run_restaurant_scraper(dest, max_count=1, place_type=place_category, fast_mode=False)
        if scraped:
            detail = scraped[0]
            detail["id"] = experience_id
            detail["source"] = "google_maps_live_detail"
            return detail
    except Exception as exc:
        log.warning("Live detail scrape failed for %s: %s", name, exc)

    return data_service.get_place(session, experience_id)
