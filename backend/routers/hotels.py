"""Hotel discovery endpoints with live Google Hotels scraper integration."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import Session

from backend.database.db import get_session
from backend.services import data_service
from scrapers.hotel_scraper_runner import (
    save_hotels_to_db,
    search_hotels,
)

router = APIRouter(prefix="/hotels", tags=["hotels"])
log = logging.getLogger("hotels_router")


class HotelSearchRequest(BaseModel):
    destination: str = Field(default="Kyoto", description="Destination city name, e.g. Kyoto, Delhi, Rome")
    check_in: str | None = Field(default=None, description="Check-in date (YYYY-MM-DD)")
    check_out: str | None = Field(default=None, description="Check-out date (YYYY-MM-DD)")
    adults: int = Field(default=2, ge=1, le=10)
    rooms: int = Field(default=1, ge=1, le=8)
    currency: str = Field(default="INR", description="Currency: INR, USD, EUR, GBP")
    min_price: float | None = Field(default=None, ge=0)
    max_price: float | None = Field(default=None, ge=0)
    stars: int | None = Field(default=None, ge=0, le=5)
    amenities: list[str] = Field(default_factory=list)
    live: bool = Field(default=True, description="Attempt live Playwright Google Hotels scrape")
    max_results: int | None = Field(default=None, description="Max results or None for all")


@router.get("")
@router.get("/")
def list_hotels(
    destination: str = Query(default=""),
    min_price: float | None = Query(default=None, ge=0),
    max_price: float | None = Query(default=None, ge=0),
    stars: int | None = Query(default=None, ge=0, le=5),
    amenities: str = Query(default="", description="Comma-separated, e.g. spa,pool"),
    q: str = Query(default=""),
    sort: str = Query(default="recommended", pattern="^(recommended|price|rating)$"),
    limit: int = Query(default=1000, ge=1, le=5000),
    auto_scrape: bool = Query(default=True),
    live: bool = Query(default=True),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    # Unpack possible Query defaults when invoked directly
    dest_raw = destination if not hasattr(destination, "default") else destination.default
    q_raw = q if not hasattr(q, "default") else q.default
    dest_filter = str(dest_raw or "").strip() or str(q_raw or "").strip()

    amen_raw = amenities if not hasattr(amenities, "default") else amenities.default
    amenities_list = [a.strip() for a in str(amen_raw or "").split(",") if a.strip()]

    min_p = min_price if not hasattr(min_price, "default") else min_price.default
    max_p = max_price if not hasattr(max_price, "default") else max_price.default
    stars_val = stars if not hasattr(stars, "default") else stars.default
    limit_val = limit if not hasattr(limit, "default") else limit.default
    sort_val = sort if not hasattr(sort, "default") else sort.default
    auto_s = auto_scrape if not hasattr(auto_scrape, "default") else auto_scrape.default
    live_val = live if not hasattr(live, "default") else live.default

    rows = data_service.list_hotels(
        session,
        destination=dest_filter,
        min_price=min_p,
        max_price=max_p,
        stars=stars_val,
        amenities=amenities_list,
        query=q_raw,
        limit=limit_val,
        sort=sort_val,
    )

    # Auto-scrape if user searched a specific destination and 0 hotels are in DB
    if not rows and dest_filter and auto_s:
        try:
            log.info("Auto-scraping hotels for destination '%s'...", dest_filter)
            records = search_hotels(
                destination=dest_filter,
                min_price=min_p,
                max_price=max_p,
                stars=stars_val,
                amenities=amenities_list,
                live=live_val,
                max_results=limit_val,
            )
            saved = save_hotels_to_db(records, session=session)
            if saved > 0:
                rows = data_service.list_hotels(
                    session,
                    destination=dest_filter,
                    min_price=min_p,
                    max_price=max_p,
                    stars=stars_val,
                    amenities=amenities_list,
                    query=q_raw,
                    limit=limit_val,
                    sort=sort_val,
                )
            if not rows and records:
                rows = [
                    {
                        "id": r.id,
                        "name": r.name,
                        "destination": r.destination,
                        "stars": r.stars,
                        "rating": r.rating,
                        "review_count": r.review_count,
                        "address": r.address,
                        "lat": r.lat,
                        "lon": r.lon,
                        "price_per_night": r.price_per_night,
                        "price_unavailable": getattr(r, "price_unavailable", r.price_per_night is None),
                        "currency": getattr(r, "currency", "INR"),
                        "amenities": r.amenities or [],
                        "photos": r.photos or [],
                        "room_types": r.room_types or [],
                        "booking_url": r.booking_url,
                        "description": r.description,
                        "source": r.source,
                        "metadata": r.metadata or {},
                    }
                    for r in records
                ]
        except Exception as e:
            log.warning("Auto-scrape fallback failed for destination %s: %s", dest_filter, e)

    return {"hotels": rows, "count": len(rows)}


@router.post("/search")
def search_hotels_endpoint(
    payload: HotelSearchRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Execute on-demand hotel search via live Google Hotels scraper or destination model."""
    dest = payload.destination.strip()
    if not dest:
        raise HTTPException(status_code=400, detail="Destination is required.")

    try:
        records = search_hotels(
            destination=dest,
            check_in=payload.check_in or "",
            check_out=payload.check_out or "",
            adults=payload.adults,
            rooms=payload.rooms,
            currency=payload.currency,
            min_price=payload.min_price,
            max_price=payload.max_price,
            stars=payload.stars,
            amenities=payload.amenities,
            live=payload.live if payload.live is not None else True,
            max_results=payload.max_results,
        )

        if not records:
            # Check if database has cached authentic records for this destination
            existing_db = data_service.list_hotels(
                session,
                destination=dest,
                min_price=payload.min_price,
                max_price=payload.max_price,
                stars=payload.stars,
                amenities=payload.amenities,
                limit=payload.max_results or 100,
            )
            if existing_db:
                return {
                    "hotels": existing_db,
                    "count": len(existing_db),
                    "source": "google_hotels_live",
                    "currency": payload.currency,
                    "destination": dest,
                }
            return {
                "hotels": [],
                "count": 0,
                "source": "google_hotels_live",
                "currency": payload.currency,
                "destination": dest,
                "message": f"No hotels found for '{dest}'. Please verify the destination name or try different dates.",
            }

        # Save to database for caching & future queries (best effort)
        try:
            save_hotels_to_db(records, session=session)
        except Exception as db_err:
            log.warning("Could not persist hotels to DB: %s", db_err)

        rows = [
            {
                "id": r.id,
                "name": r.name,
                "destination": r.destination,
                "stars": r.stars,
                "rating": r.rating,
                "review_count": r.review_count,
                "address": r.address,
                "lat": r.lat,
                "lon": r.lon,
                "price_per_night": r.price_per_night,
                "price_unavailable": getattr(r, "price_unavailable", r.price_per_night is None),
                "currency": getattr(r, "currency", payload.currency),
                "amenities": r.amenities or [],
                "photos": r.photos or [],
                "room_types": r.room_types or [],
                "booking_url": r.booking_url,
                "description": r.description,
                "source": r.source,
                "metadata": r.metadata or {},
            }
            for r in records
        ]

        return {
            "hotels": rows,
            "count": len(rows),
            "source": "google_hotels_live",
            "currency": payload.currency,
            "destination": dest,
        }
    except Exception as e:
        log.exception("Hotel search failed for destination '%s': %s", dest, e)
        existing_db = data_service.list_hotels(session, destination=dest, limit=payload.max_results or 100)
        if existing_db:
            return {
                "hotels": existing_db,
                "count": len(existing_db),
                "source": "google_hotels_live",
                "currency": payload.currency,
                "destination": dest,
            }
        return {
            "hotels": [],
            "count": 0,
            "source": "google_hotels_live",
            "currency": payload.currency,
            "destination": dest,
            "message": f"Hotel search encountered an error: {str(e)}",
        }


@router.get("/{hotel_id}")
def get_hotel(hotel_id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    hotel = data_service.get_hotel(session, hotel_id)
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")
    return hotel


@router.get("/{hotel_id}/rooms")
def get_rooms(hotel_id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    hotel = data_service.get_hotel(session, hotel_id)
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")
    return {"hotel_id": hotel_id, "rooms": hotel.get("room_types", [])}

