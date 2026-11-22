"""Places, destinations, inspiration and search endpoints."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.database.db import get_session
from backend.database.models import Destination, Flight, Hotel, Place, Trip
from backend.services import data_service

logger = logging.getLogger("mindtrip.places")

router = APIRouter(tags=["places"])


@router.get("/places")
def list_places(
    destination: str = Query(default=""),
    category: str = Query(default="all"),
    q: str = Query(default=""),
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    dest_cleaned = destination.strip()
    rows = data_service.list_places(session, destination=dest_cleaned, category=category, query=q, limit=limit)
    
    # If no places found for this destination and looking for dining or general places, trigger live scraper
    if not rows and dest_cleaned and (category in ("restaurant", "food", "cafe", "bar", "all") or not category):
        try:
            from scrapers.restaurant_scraper_runner import run_restaurant_scraper
            logger.info("No places in DB for '%s'. Live scraping authentic restaurants...", dest_cleaned)
            run_restaurant_scraper(dest_cleaned, max_count=15)
            rows = data_service.list_places(session, destination=dest_cleaned, category=category, query=q, limit=limit)
        except Exception as exc:
            logger.warning("Live restaurant scraping skipped or failed for '%s': %s", dest_cleaned, exc)
            
    return {"places": rows, "count": len(rows)}


@router.post("/places/scrape")
def trigger_scrape_places(
    destination: str = Query(...),
    max_count: int = Query(default=15, ge=1, le=50),
) -> dict[str, Any]:
    from scrapers.restaurant_scraper_runner import run_restaurant_scraper
    scraped = run_restaurant_scraper(destination.strip(), max_count=max_count)
    return {"destination": destination, "scraped_count": len(scraped), "restaurants": scraped}


class PlaceSearchRequest(BaseModel):
    query: str
    destination: str
    category: str | None = None
    max_results: int = 5


@router.post("/places/search/live")
def search_google_maps_endpoint(
    payload: PlaceSearchRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Live Google Maps search for a place query within a destination.

    Scrapes Google Maps via Playwright (or synthetic fallback), persists results,
    and returns them so the frontend can display them in recommendations.
    """
    try:
        from scrapers.google_maps_adapter import search_google_maps_live
    except ImportError as exc:
        logger.warning("Google Maps adapter unavailable (%s); returning empty results", exc)
        return {"places": [], "count": 0, "query": payload.query, "destination": payload.destination}

    try:
        places = search_google_maps_live(
            query=payload.query,
            location=payload.destination,
            category=payload.category,
            max_results=payload.max_results,
            session=session,
        )
    except Exception as exc:
        logger.exception("Live Google Maps search failed for '%s' in '%s': %s", payload.query, payload.destination, exc)
        return {"places": [], "count": 0, "query": payload.query, "destination": payload.destination}

    return {
        "places": [data_service.place_dict(p) for p in places],
        "count": len(places),
        "query": payload.query,
        "destination": payload.destination,
    }


@router.get("/places/recommended")
def get_recommended_places_endpoint(
    destination: str = Query(...),
    limit: int = Query(default=15, ge=1, le=50),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    dest_cleaned = destination.strip()
    places = data_service.get_recommended_places(session, destination=dest_cleaned, limit=limit)
    return {"destination": dest_cleaned, "count": len(places), "places": places}


@router.get("/places/{place_id}")
def get_place(place_id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    place = data_service.get_place(session, place_id)
    if not place:
        raise HTTPException(status_code=404, detail="Place not found")
    return place


@router.get("/destinations")
def list_destinations(session: Session = Depends(get_session)) -> dict[str, Any]:
    rows = data_service.list_destinations(session)
    return {"destinations": rows, "count": len(rows)}


@router.get("/destinations/{destination_id}")
def get_destination(destination_id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    row = data_service.get_destination(session, destination_id)
    if not row:
        raise HTTPException(status_code=404, detail="Destination not found")
    return row


@router.get("/inspiration")
def inspiration(session: Session = Depends(get_session)) -> dict[str, Any]:
    trips = data_service.list_trips(session, limit=24)
    enriched = []
    for trip in trips:
        destination = data_service.get_destination(session, trip["destination"])
        enriched.append({**trip, "destination_detail": destination})
    return {"collections": enriched, "count": len(enriched)}


@router.get("/search")
def search(
    q: str = Query(default="", min_length=0),
    limit: int = Query(default=8, ge=1, le=30),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    query = q.strip()
    if not query:
        return {"query": q, "destinations": [], "places": [], "hotels": [], "trips": []}
    destinations = [
        data_service.destination_dict(row)
        for row in session.exec(select(Destination).where(Destination.name.ilike(f"%{query}%"))).all()
    ][:limit]
    places = data_service.list_places(session, query=query, limit=limit)
    hotels = data_service.list_hotels(session, query=query, limit=limit)
    trips = [trip for trip in data_service.list_trips(session, limit=50) if query.lower() in trip["title"].lower() or query.lower() in trip["destination"].lower()][:limit]
    return {"query": q, "destinations": destinations, "places": places, "hotels": hotels, "trips": trips}


@router.get("/stats")
def stats(session: Session = Depends(get_session)) -> dict[str, Any]:
    return {
        "destinations": len(session.exec(select(Destination)).all()),
        "places": len(session.exec(select(Place)).all()),
        "hotels": len(session.exec(select(Hotel)).all()),
        "flights": len(session.exec(select(Flight)).all()),
        "trips": len(session.exec(select(Trip)).all()),
    }
