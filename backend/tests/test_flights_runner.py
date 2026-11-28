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


def test_round_trip_tfs_encodes_both_legs_and_mode() -> None:
    import base64
    from scrapers.user_scrapers.google_flights_scraper.app.flights_source import PlaywrightFlightsSource
    from scrapers.user_scrapers.google_flights_scraper.app.models import Leg

    src = PlaywrightFlightsSource()
    leg = Leg(origin="SFO", destination="ORD", date="2026-12-11")
    rt_tfs = src._build_tfs(leg, {"trip_type": "round-trip", "return_date": "2026-12-18", "cabin_class": "economy", "adults": 1})
    ow_tfs = src._build_tfs(leg, {"trip_type": "one-way", "cabin_class": "economy", "adults": 1})

    pad_rt = rt_tfs + "=" * (-len(rt_tfs) % 4)
    raw_rt = base64.urlsafe_b64decode(pad_rt)
    assert b"2026-12-11" in raw_rt
    assert b"2026-12-18" in raw_rt
    assert b"SFO" in raw_rt
    assert b"ORD" in raw_rt
    assert raw_rt.endswith(b"\x98\x01\x01")  # 1 = Round trip UI mode
    assert rt_tfs != ow_tfs


def test_parse_aria_label_extracts_explicit_arrival_date_and_sets_complete() -> None:
    from scrapers.user_scrapers.google_flights_scraper.app.flights_source import parse_aria_label
    from scrapers.user_scrapers.google_flights_scraper.app.models import Leg

    leg = Leg(origin="SFO", destination="ORD", date="2026-12-11")
    label = (
        "From 18886 Indian rupees. 1 stop flight with Frontier. "
        "Leaves San Francisco International Airport at 6:30 PM on Friday, December 11 "
        "and arrives at O'Hare International Airport at 5:01 AM on Saturday, December 12. "
        "Total duration 8 hr 31 min. Select flight"
    )
    rec = parse_aria_label(
        label,
        leg,
        {"currency": "INR", "trip_type": "round-trip"},
        dom_baggage="1 carry-on bag included",
    )
    assert rec is not None
    assert rec.arr_time == "2026-12-12T05:01:00"
    assert rec.detail_status == "Complete"
    assert rec.detail_failed is False
    assert rec.price_missing is False
    assert rec.baggage == "1 carry-on bag included"


def test_live_round_trip_no_fake_return_and_pairs_by_airline() -> None:
    from unittest.mock import patch
    from scrapers.adapters.base_adapter import FlightRecord as AdapterFlightRecord

    outbound = [
        AdapterFlightRecord(
            id="aa-out",
            airline="American",
            airline_code="AA",
            origin="SFO",
            destination="ORD",
            departure_time="2026-12-11T06:11:00",
            arrival_time="2026-12-11T12:30:00",
            duration_minutes=259,
            stops=0,
            price_usd=297.8,
            price_inr=25313.0,
            source="google_flights_live",
        ),
        AdapterFlightRecord(
            id="ua-out",
            airline="United",
            airline_code="UA",
            origin="SFO",
            destination="ORD",
            departure_time="2026-12-11T06:35:00",
            arrival_time="2026-12-11T13:01:00",
            duration_minutes=266,
            stops=0,
            price_usd=297.8,
            price_inr=25313.0,
            source="google_flights_live",
        ),
    ]
    returns = [
        AdapterFlightRecord(
            id="ua-ret",
            airline="United",
            airline_code="UA",
            origin="ORD",
            destination="SFO",
            departure_time="2026-12-18T09:20:00",
            arrival_time="2026-12-18T11:45:00",
            duration_minutes=265,
            stops=0,
            price_usd=297.8,
            price_inr=25313.0,
            source="google_flights_live",
        ),
        AdapterFlightRecord(
            id="aa-ret",
            airline="American",
            airline_code="AA",
            origin="ORD",
            destination="SFO",
            departure_time="2026-12-18T15:10:00",
            arrival_time="2026-12-18T17:40:00",
            duration_minutes=270,
            stops=0,
            price_usd=297.8,
            price_inr=25313.0,
            source="google_flights_live",
        ),
    ]

    # Case 1: Return scrape yields nothing -> must NOT fabricate fake return_flight (" 200", etc.)
    async def _scrape_no_return(**kwargs):
        if kwargs["origin"] == "SFO":
            return [r.model_copy(deep=True) for r in outbound]
        return []

    with patch("scrapers.flight_scraper_runner._scrape_live_leg", _scrape_no_return), patch("asyncio.sleep"):
        res = asyncio.run(search_flights(
            origin="SFO",
            destination="ORD",
            date="2026-12-11",
            return_date="2026-12-18",
            trip_type="round-trip",
            live=True,
            allow_fallback=False,
        ))
    assert len(res) == 2
    assert all(r.metadata.get("return_flight") is None for r in res)

    # Case 2: Return scrape succeeds -> matches by airline (AA->AA, UA->UA)
    async def _scrape_with_return(**kwargs):
        if kwargs["origin"] == "SFO":
            return [r.model_copy(deep=True) for r in outbound]
        return [r.model_copy(deep=True) for r in returns]

    with patch("scrapers.flight_scraper_runner._scrape_live_leg", _scrape_with_return), patch("asyncio.sleep"):
        res_paired = asyncio.run(search_flights(
            origin="SFO",
            destination="ORD",
            date="2026-12-11",
            return_date="2026-12-18",
            trip_type="round-trip",
            live=True,
            allow_fallback=False,
        ))
    assert res_paired[0].metadata["return_flight"]["airline"] == "American"
    assert res_paired[0].metadata["return_flight"]["airline_code"] == "AA"
    assert res_paired[1].metadata["return_flight"]["airline"] == "United"
    assert res_paired[1].metadata["return_flight"]["airline_code"] == "UA"
