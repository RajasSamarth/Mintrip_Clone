"""Tests for flight scraper runner and search integration."""

import asyncio
from sqlmodel import Session, select

from backend.database.db import engine
from backend.database.models import Flight
from scrapers.flight_scraper_runner import (
    generate_fallback_flights,
    search_flights,
    save_flights_to_db,
)


def test_generate_fallback_flights() -> None:
    records = generate_fallback_flights("SFO", "JFK", "2026-11-20", cabin="economy", count=6)
    assert len(records) == 6
    for r in records:
        assert r.origin == "SFO"
        assert r.destination == "JFK"
        assert r.price_usd > 0
        assert r.duration_minutes > 0
        assert r.airline
        assert "google.com/travel/flights" in r.booking_url


def test_search_flights_fallback() -> None:
    records = asyncio.run(search_flights("LHR", "CDG", "2026-12-01", cabin="business", adults=1, live=False))
    assert len(records) > 0
    assert records[0].origin == "LHR"
    assert records[0].destination == "CDG"
    assert records[0].cabin == "Business"


def test_round_trip_fallback_pairs_return_and_scales_pax() -> None:
    records = asyncio.run(search_flights(
        "DEL",
        "DXB",
        "2026-11-20",
        return_date="2026-11-27",
        trip_type="round-trip",
        adults=2,
        children=1,
        live=False,
        max_results=6,
    ))
    assert records
    for rec in records:
        meta = rec.metadata or {}
        ret = meta.get("return_flight")
        assert ret is not None
        assert ret["origin"] == "DXB" and ret["destination"] == "DEL"
        assert meta["passengers"] == 3
        assert rec.price_usd == round(meta["price_per_person_usd"] * 3, 2)


def test_save_flights_to_db() -> None:
    records = generate_fallback_flights("BOS", "MIA", "2026-11-25", count=3)
    with Session(engine) as session:
        saved = save_flights_to_db(records, session=session)
        assert saved == 3

        query = select(Flight).where(Flight.origin == "BOS", Flight.destination == "MIA")
        db_records = session.exec(query).all()
        assert len(db_records) >= 3
