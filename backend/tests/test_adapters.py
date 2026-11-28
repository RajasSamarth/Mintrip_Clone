"""Adapter ingestion tests."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from scrapers.adapters.base_adapter import FlightRecord, HotelRecord, PlaceRecord, slugify
from scrapers.adapters.google_flights_adapter import ingest as ingest_flights
from scrapers.adapters.google_maps_adapter import ingest as ingest_places


def test_slugify() -> None:
    assert slugify("Fushimi Inari Taisha") == "fushimi-inari-taisha"
    assert slugify("  Café  de Flore ") == "caf-de-flore"


def test_place_record_defaults_id() -> None:
    record = PlaceRecord(name="Nishiki Market", lat=35.0, lon=135.7)
    assert record.id == "nishiki-market"
    assert record.category == "other"


def test_google_maps_json_nested(tmp_path: Path) -> None:
    payload = [
        {
            "title": "Kiyomizu-dera",
            "categories": ["Tourist attraction", "Temple"],
            "location": {"lat": 34.9949, "lng": 135.7850},
            "stars": 4.8,
            "reviews": [{"text": "great"}, {"text": "lovely"}],
            "full_address": "Kyoto",
            "price": "$$",
            "photo_urls": [{"url": "https://example.com/a.jpg"}, "https://example.com/b.jpg"],
        },
        {"title": "Missing coords"},
    ]
    path = tmp_path / "maps.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = ingest_places(path, destination="kyoto")
    assert result.total == 1
    assert result.skipped == 1
    record = result.records[0]
    assert record.category == "attraction"
    assert record.review_count == 2
    assert record.price_level == 2
    assert record.photos == ["https://example.com/a.jpg", "https://example.com/b.jpg"]
    assert record.destination == "kyoto"


def test_google_maps_csv(tmp_path: Path) -> None:
    path = tmp_path / "maps.csv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["name", "category", "latitude", "longitude", "rating", "price_level"])
        writer.writeheader()
        writer.writerow({"name": "Ace Hotel", "category": "Lodging", "latitude": "35.009", "longitude": "135.759", "rating": "4.7", "price_level": "$$$"})
    result = ingest_places(path)
    assert result.total == 1
    assert result.records[0].category == "hotel"
    assert result.records[0].price_level == 3


def test_google_flights_json(tmp_path: Path) -> None:
    payload = {
        "flights": [
            {
                "carrier": "Japan Airlines",
                "carrier_code": "JL",
                "flight_no": "JL 1",
                "from": "sfo",
                "to": "kix",
                "departure": "2026-11-12T11:25:00",
                "duration": "9h 45m",
                "stops": "Nonstop",
                "price": "$812",
                "cabin": "Economy",
                "bags": "2 checked",
                "link": "https://example.com/book",
            },
            {"carrier": "Broken"},
        ]
    }
    path = tmp_path / "flights.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = ingest_flights(path)
    assert result.total == 1
    assert result.skipped == 1
    record = result.records[0]
    assert record.origin == "SFO"
    assert record.destination == "KIX"
    assert record.duration_minutes == 585
    assert record.stops == 0
    assert record.price_usd == 812
    assert record.arrival_time.startswith("2026-11-12T21:10")


def test_flight_record_defaults_id() -> None:
    record = FlightRecord(
        airline="ANA",
        flight_number="NH 107",
        origin="sfo",
        destination="kix",
        departure_time="2026-11-12T13:10:00",
        arrival_time="2026-11-13T18:05:00",
        price_usd=764,
    )
    assert record.id == "ana-nh-107-sfo-kix"
    assert record.origin == "SFO"


def test_hotel_record_normalises_amenities() -> None:
    record = HotelRecord(name="Hotel Kanra", amenities="Free wifi, Bar | Spa", photos=["https://example.com/1.jpg"])
    assert record.id == "hotel-kanra"
    assert record.amenities == ["Free wifi", "Bar", "Spa"]
    assert record.photos == ["https://example.com/1.jpg"]


def test_google_flights_overnight_and_airline_code() -> None:
    from scrapers.adapters.google_flights_adapter import _to_record

    # Overnight flight (6:30 PM -> 5:01 AM next day)
    overnight = _to_record({
        "airline": "Frontier",
        "origin": "SFO",
        "destination": "ORD",
        "flight_date": "2026-12-11",
        "departure_time": "6:30 PM",
        "arrival_time": "5:01 AM",
        "duration_minutes": 511,
        "stops": 1,
        "price": 18886.0,
        "currency": "INR",
    })
    assert overnight is not None
    assert overnight.airline_code == "F9"
    assert overnight.departure_time == "2026-12-11T18:30:00"
    assert overnight.arrival_time == "2026-12-12T05:01:00"

    # Multi-day >24h flight (8:26 PM -> 12:54 AM +2 days, 26h 28m = 1588m)
    multiday = _to_record({
        "airline": "American, Operated by SkyWest",
        "origin": "SFO",
        "destination": "ORD",
        "flight_date": "2026-12-11",
        "departure_time": "8:26 PM",
        "arrival_time": "12:54 AM",
        "duration_minutes": 1588,
        "stops": 1,
        "price": 25313.0,
        "currency": "INR",
    })
    assert multiday is not None
    assert multiday.airline_code == "AA"
    assert multiday.arrival_time == "2026-12-13T00:54:00"

    # Explicit ISO arrival time must be preserved
    explicit = _to_record({
        "airline": "JetBlue",
        "origin": "DEL",
        "destination": "SFO",
        "flight_date": "2026-12-11",
        "departure_time": "3:00 AM",
        "arrival_time": "2026-12-11T05:30:00",
        "duration_minutes": 960,
        "stops": 0,
        "price": 1000.0,
        "currency": "USD",
    })
    assert explicit is not None
    assert explicit.airline_code == "B6"
    assert explicit.arrival_time == "2026-12-11T05:30:00"
