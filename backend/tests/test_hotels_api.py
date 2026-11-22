"""Tests for hotel API endpoints and scraper search."""

from sqlmodel import Session

from backend.database.db import engine
from backend.routers.hotels import (
    HotelSearchRequest,
    list_hotels,
    search_hotels_endpoint,
)


def test_post_hotels_search_endpoint() -> None:
    payload = HotelSearchRequest(
        destination="Kyoto",
        check_in="2026-11-20",
        check_out="2026-11-23",
        adults=2,
        currency="INR",
        live=False,
    )
    with Session(engine) as session:
        data = search_hotels_endpoint(payload, session=session)
        assert data["count"] > 0
        assert len(data["hotels"]) > 0
        h = data["hotels"][0]
        assert h["name"]
        assert h["destination"] == "Kyoto"
        assert "price_unavailable" in h
        if not h["price_unavailable"]:
            assert h["price_per_night"] > 0


def test_get_hotels_auto_scrape() -> None:
    with Session(engine) as session:
        data = list_hotels(destination="Delhi", auto_scrape=True, live=False, session=session)
        assert data["count"] > 0
        assert data["hotels"][0]["destination"]
