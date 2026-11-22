"""Tests for flight API endpoints and scraper search."""

import asyncio
from unittest.mock import patch

from sqlmodel import Session

from backend.database.db import engine
from backend.routers.flights import (
    FlightSearchRequest,
    airports,
    list_flights,
    search_flights_endpoint,
)
from scrapers.flight_scraper_runner import generate_fallback_flights


def _records(origin: str, destination: str, flight_date: str, count: int = 4):
    """Deterministic fixture records used instead of a live scrape."""
    return generate_fallback_flights(
        origin=origin,
        destination=destination,
        flight_date=flight_date,
        count=count,
    )


def test_airports_search() -> None:
    # Test worldwide searches
    res_tokyo = airports(q="tokyo")
    assert any(a["code"] in ("HND", "NRT") for a in res_tokyo["airports"])

    res_india = airports(q="delhi")
    assert any(a["code"] == "DEL" for a in res_india["airports"])

    res_london = airports(q="heathrow")
    assert any(a["code"] == "LHR" for a in res_london["airports"])


def test_post_flights_search_endpoint() -> None:
    payload = FlightSearchRequest(
        origin="SFO",
        destination="JFK",
        outbound_date="2026-11-20",
        cabin="Economy",
        adults=1,
        live=True,
    )
    records = _records("SFO", "JFK", "2026-11-20")

    async def _fake_search(**_kwargs):
        return records

    with Session(engine) as session:
        with patch("backend.routers.flights.search_flights", _fake_search):
            data = asyncio.run(search_flights_endpoint(payload, session=session))

        assert data["count"] > 0
        assert len(data["flights"]) > 0
        fl = data["flights"][0]
        assert fl["origin"] == "SFO"
        assert fl["destination"] == "JFK"
        assert fl["price_usd"] > 0
        assert fl["airline"]


def test_get_flights_auto_scrape() -> None:
    records = _records("LHR", "CDG", "2026-12-01")

    async def _fake_search(**_kwargs):
        return records

    with Session(engine) as session:
        with patch("backend.routers.flights.search_flights", _fake_search):
            data = asyncio.run(
                list_flights(
                    origin="LHR",
                    destination="CDG",
                    auto_scrape=True,
                    live=True,
                    session=session,
                )
            )

        assert data["count"] > 0
        assert data["flights"][0]["origin"] == "LHR"
        assert data["flights"][0]["destination"] == "CDG"
