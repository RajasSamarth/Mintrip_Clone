"""Seed the database from curated fixtures and optional user scraper output."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from backend.database.models import Destination, Flight, Hotel, Place, Trip, TripDay, TripStop
from backend.services.data_service import slugify


def _upsert(session: Session, model: type, record_id: str, payload: dict[str, Any]) -> None:
    existing = session.get(model, record_id)
    if existing:
        return
    session.add(model(id=record_id, **payload))


def seed_from_fixtures(session: Session, fixtures_path: str | Path, force: bool = False) -> dict[str, int]:
    path = Path(fixtures_path)
    if not path.exists():
        return {"destinations": 0, "places": 0, "hotels": 0, "flights": 0, "trips": 0}

    if not force and session.exec(select(Place)).first() is not None:
        return {"destinations": 0, "places": 0, "hotels": 0, "flights": 0, "trips": 0, "skipped": 1}

    data = json.loads(path.read_text(encoding="utf-8"))
    counts = {"destinations": 0, "places": 0, "hotels": 0, "flights": 0, "trips": 0}

    for row in data.get("destinations", []):
        payload = {k: v for k, v in row.items() if k != "id"}
        _upsert(session, Destination, row["id"], payload)
        counts["destinations"] += 1

    for row in data.get("places", []):
        payload = {k: v for k, v in row.items() if k not in {"id", "metadata"}}
        payload["metadata_json"] = row.get("metadata", {})
        _upsert(session, Place, row["id"], payload)
        counts["places"] += 1

    for row in data.get("hotels", []):
        payload = {k: v for k, v in row.items() if k not in {"id", "metadata"}}
        payload["metadata_json"] = row.get("metadata", {})
        _upsert(session, Hotel, row["id"], payload)
        counts["hotels"] += 1

    for row in data.get("flights", []):
        payload = {k: v for k, v in row.items() if k not in {"id", "metadata"}}
        payload["metadata_json"] = row.get("metadata", {})
        _upsert(session, Flight, row["id"], payload)
        counts["flights"] += 1

    for row in data.get("trips", []):
        if session.get(Trip, row["id"]):
            continue
        trip = Trip(
            id=row["id"],
            title=row["title"],
            destination=row.get("destination", ""),
            start_date=row.get("start_date", ""),
            end_date=row.get("end_date", ""),
            traveler_type=row.get("traveler_type", "Traveler"),
            budget=row.get("budget", 0),
            cover_photo=row.get("cover_photo", ""),
            summary=row.get("summary", ""),
            status=row.get("status", "published"),
            tags=row.get("tags", []),
            creator=row.get("creator", {}),
            hotel_id=row.get("hotel_id"),
            session_id=None,
        )
        session.add(trip)
        session.flush()
        for day in row.get("days", []):
            day_row = TripDay(
                trip_id=trip.id,
                day_index=day["day_index"],
                date=day.get("date", ""),
                title=day.get("title", ""),
                summary=day.get("summary", ""),
            )
            session.add(day_row)
            session.flush()
            for order, stop in enumerate(day.get("stops", [])):
                session.add(
                    TripStop(
                        trip_id=trip.id,
                        trip_day_id=day_row.id or 0,
                        place_id=stop.get("place_id", ""),
                        sort_order=order,
                        time_slot=stop.get("time_slot", "morning"),
                        arrival_time=stop.get("arrival_time", ""),
                        duration_mins=stop.get("duration_mins", 60),
                        transit_info=stop.get("transit_info", ""),
                        notes=stop.get("notes", ""),
                        kind=stop.get("kind", "place"),
                    )
                )
        counts["trips"] += 1

    session.commit()
    return counts


def import_user_scrapers(session: Session, directory: str | Path) -> dict[str, int]:
    """Ingest any recognised JSON/CSV in scrapers/user_scrapers."""
    from scrapers.adapters.google_flights_adapter import ingest as ingest_flights
    from scrapers.adapters.google_maps_adapter import ingest as ingest_places

    path = Path(directory)
    counts = {"places": 0, "flights": 0, "files": 0}
    if not path.exists():
        return counts

    for file in sorted(path.glob("*")):
        if file.suffix.lower() not in {".json", ".csv"}:
            continue
        counts["files"] += 1
        # Try maps first, then flights. Adapters return 0 records when the shape
        # does not match, which makes this safe.
        try:
            place_result = ingest_places(file)
        except Exception:  # noqa: BLE001
            place_result = None
        if place_result and place_result.records:
            for record in place_result.records:
                if session.get(Place, record.id):
                    continue
                payload = record.model_dump()
                payload.pop("id", None)
                payload["metadata_json"] = payload.pop("metadata", {})
                session.add(Place(id=record.id, **payload))
                counts["places"] += 1
            session.commit()
            continue

        try:
            flight_result = ingest_flights(file)
        except Exception:  # noqa: BLE001
            flight_result = None
        if flight_result and flight_result.records:
            for record in flight_result.records:
                if session.get(Flight, record.id):
                    continue
                payload = record.model_dump(mode="json")
                payload.pop("id", None)
                payload["metadata_json"] = payload.pop("metadata", {})
                session.add(Flight(id=record.id, **payload))
                counts["flights"] += 1
            session.commit()

    return counts
