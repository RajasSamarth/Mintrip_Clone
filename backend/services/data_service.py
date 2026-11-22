"""Read/write helpers shared by routers, tools and the agent."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any, Iterable

from sqlalchemy import func, or_
from sqlmodel import Session, select

from backend.database.models import (
    ChatMessage,
    Destination,
    Flight,
    Hotel,
    Place,
    Trip,
    TripDay,
    TripStop,
    utcnow,
)


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "item"


def unique_id(session: Session, model: type, base: str) -> str:
    candidate = slugify(base)
    existing = session.get(model, candidate)
    if existing is None:
        return candidate
    for index in range(2, 1000):
        candidate = f"{slugify(base)}-{index}"
        if session.get(model, candidate) is None:
            return candidate
    return f"{slugify(base)}-{int(datetime.now().timestamp())}"


# --------------------------------------------------------------------------- #
# Serialisers
# --------------------------------------------------------------------------- #
def place_dict(place: Place) -> dict[str, Any]:
    meta = place.metadata_json or {}
    return {
        "id": place.id,
        "name": place.name,
        "category": place.category,
        "destination": place.destination,
        "description": place.description,
        "lat": place.lat,
        "lon": place.lon,
        "rating": place.rating,
        "review_count": place.review_count,
        "address": place.address,
        "price_level": place.price_level,
        "opening_hours": place.opening_hours,
        "photos": place.photos or [],
        "tags": place.tags or [],
        "source": place.source,
        "menu": meta.get("menu") or [],
        "reviews": meta.get("reviews") or [],
        "opening_hours_weekly": meta.get("opening_hours_weekly") or {},
        "dining_amenities": meta.get("dining_amenities") or meta.get("amenities") or [],
        "phone": meta.get("phone") or meta.get("phone_number") or "",
        "website": meta.get("website") or "",
        "price_range": meta.get("price_range") or "",
        "metadata": meta,
    }


def hotel_dict(hotel: Hotel) -> dict[str, Any]:
    meta = hotel.metadata_json or {}
    price_unavail = meta.get("price_unavailable", hotel.price_per_night is None or hotel.price_per_night <= 0)
    return {
        "id": hotel.id,
        "name": hotel.name,
        "destination": hotel.destination,
        "stars": hotel.stars,
        "rating": hotel.rating,
        "review_count": hotel.review_count,
        "address": hotel.address,
        "lat": hotel.lat,
        "lon": hotel.lon,
        "price_per_night": hotel.price_per_night if not price_unavail else None,
        "price_unavailable": bool(price_unavail),
        "currency": hotel.currency or "INR",
        "amenities": hotel.amenities or [],
        "photos": hotel.photos or [],
        "room_types": hotel.room_types if (hotel.room_types and len(hotel.room_types) > 0) else [],
        "booking_url": hotel.booking_url,
        "description": hotel.description,
        "source": hotel.source,
        "metadata": meta,
    }


def flight_dict(flight: Flight) -> dict[str, Any]:
    meta = flight.metadata_json or {}
    raw_inr = meta.get("price_inr")
    price_inr = raw_inr if (raw_inr is not None and raw_inr > 0) else (round(flight.price_usd * 85.0, 2) if flight.price_usd else 0.0)
    price_usd = flight.price_usd or (round(price_inr / 85.0, 2) if price_inr else 0.0)
    return {
        "id": flight.id,
        "airline": flight.airline,
        "airline_code": flight.airline_code,
        "flight_number": flight.flight_number,
        "origin": flight.origin,
        "destination": flight.destination,
        "departure_time": flight.departure_time,
        "arrival_time": flight.arrival_time,
        "duration_minutes": flight.duration_minutes,
        "stops": flight.stops,
        "price_usd": price_usd,
        "price_inr": price_inr,
        "currency": meta.get("currency", "INR"),
        "selected_currency": meta.get("selected_currency", "INR"),
        "cabin": flight.cabin,
        "baggage": flight.baggage,
        "booking_url": flight.booking_url,
        "source": flight.source,
        "is_top_pick": bool(meta.get("is_top_pick", False)),
        "emissions": meta.get("emissions"),
        "emissions_diff_pct": meta.get("emissions_diff_pct"),
        "self_transfer": bool(meta.get("self_transfer", False)),
        "metadata": meta,
    }


def destination_dict(destination: Destination) -> dict[str, Any]:
    return {
        "id": destination.id,
        "name": destination.name,
        "country": destination.country,
        "tagline": destination.tagline,
        "description": destination.description,
        "hero_image": destination.hero_image,
        "gallery": destination.gallery or [],
        "tags": destination.tags or [],
        "best_season": destination.best_season,
        "lat": destination.lat,
        "lon": destination.lon,
    }


def trip_summary(session: Session, trip: Trip) -> dict[str, Any]:
    days = session.exec(select(TripDay).where(TripDay.trip_id == trip.id)).all()
    stops = session.exec(select(TripStop).where(TripStop.trip_id == trip.id)).all()
    
    # Resolve hotel
    hotel = session.get(Hotel, trip.hotel_id) if trip.hotel_id else None
    hotel_res = hotel_dict(hotel) if hotel else (trip.hotels_json[0] if (trip.hotels_json and len(trip.hotels_json) > 0) else None)
    hotels_res = trip.hotels_json if (trip.hotels_json and len(trip.hotels_json) > 0) else ([hotel_res] if hotel_res else [])

    # Resolve flight
    flight = session.get(Flight, trip.flight_id) if trip.flight_id else None
    flight_custom = trip.flights_json[0] if (trip.flights_json and len(trip.flights_json) > 0) else None
    if flight and flight_custom:
        flight_res = {**flight_dict(flight), **flight_custom}
    elif flight:
        flight_res = flight_dict(flight)
    else:
        flight_res = flight_custom
    flights_res = trip.flights_json if (trip.flights_json and len(trip.flights_json) > 0) else ([flight_res] if flight_res else [])

    return {
        "id": trip.id,
        "title": trip.title,
        "destination": trip.destination,
        "start_date": trip.start_date,
        "end_date": trip.end_date,
        "traveler_type": trip.traveler_type,
        "budget": trip.budget,
        "cover_photo": trip.cover_photo,
        "summary": trip.summary,
        "status": trip.status,
        "tags": trip.tags or [],
        "creator": trip.creator or {},
        "hotel_id": trip.hotel_id,
        "hotel": hotel_res,
        "hotels": hotels_res,
        "flight_id": trip.flight_id,
        "flight": flight_res,
        "flights": flights_res,
        "session_id": trip.session_id,
        "day_count": len(days),
        "stop_count": len(stops),
        "created_at": trip.created_at,
        "updated_at": trip.updated_at,
    }


def trip_detail(session: Session, trip: Trip) -> dict[str, Any]:
    data = trip_summary(session, trip)
    days = session.exec(
        select(TripDay).where(TripDay.trip_id == trip.id).order_by(TripDay.day_index)
    ).all()
    place_cache: dict[str, Place] = {}
    out_days = []
    for day in days:
        stops = session.exec(
            select(TripStop)
            .where(TripStop.trip_day_id == day.id)
            .order_by(TripStop.sort_order)
        ).all()
        stop_payloads = []
        for stop in stops:
            place = place_cache.get(stop.place_id)
            if place is None and stop.place_id:
                place = session.get(Place, stop.place_id)
                if place:
                    place_cache[stop.place_id] = place
            stop_payloads.append(
                {
                    "id": stop.id,
                    "place_id": stop.place_id,
                    "sort_order": stop.sort_order,
                    "time_slot": stop.time_slot,
                    "arrival_time": stop.arrival_time,
                    "duration_mins": stop.duration_mins,
                    "transit_info": stop.transit_info,
                    "notes": stop.notes,
                    "kind": stop.kind,
                    "place": place_dict(place) if place else None,
                }
            )
        out_days.append(
            {
                "id": day.id,
                "day_index": day.day_index,
                "date": day.date,
                "title": day.title,
                "summary": day.summary,
                "stops": stop_payloads,
            }
        )
    data["days"] = out_days
    return data


# --------------------------------------------------------------------------- #
# Queries
# --------------------------------------------------------------------------- #
def list_destinations(session: Session) -> list[dict[str, Any]]:
    rows = session.exec(select(Destination).order_by(Destination.name)).all()
    return [destination_dict(row) for row in rows]


def get_destination(session: Session, destination_id: str) -> dict[str, Any] | None:
    row = session.get(Destination, destination_id)
    return destination_dict(row) if row else None


def list_places(
    session: Session,
    destination: str = "",
    category: str = "",
    query: str = "",
    limit: int = 50,
) -> list[dict[str, Any]]:
    statement = select(Place)
    if destination:
        dest_clean = destination.split(",")[0].strip().lower()
        statement = statement.where(
            or_(
                func.lower(Place.destination) == dest_clean,
                Place.destination.ilike(f"%{dest_clean}%"),
                Place.city.ilike(f"%{dest_clean}%"),
            )
        )
    if category and category != "all":
        statement = statement.where(Place.category == category)
    if query:
        statement = statement.where(
            or_(
                Place.name.ilike(f"%{query}%"),
                Place.destination.ilike(f"%{query}%"),
            )
        )
    statement = statement.order_by(Place.rating.desc()).limit(limit)
    return [place_dict(row) for row in session.exec(statement).all()]


def get_recommended_places(
    session: Session,
    destination: str = "",
    limit: int = 15,
) -> list[dict[str, Any]]:
    if not destination:
        return []

    dest_clean = destination.split(",")[0].strip().lower()

    # 1. Seed curated famous spots if needed
    try:
        from backend.database.famous_spots import get_famous_spots_for_destination
        famous_list = get_famous_spots_for_destination(dest_clean)
        for spot in famous_list:
            existing = session.get(Place, spot["id"])
            if not existing:
                meta = {
                    "tags": spot.get("tags", []),
                    "best_time": spot.get("best_time", ""),
                    "duration": spot.get("duration", ""),
                }
                new_place = Place(
                    id=spot["id"],
                    name=spot["name"],
                    category=spot["category"],
                    destination=spot["destination"],
                    city=spot.get("city", ""),
                    country=spot.get("country", ""),
                    description=spot["description"],
                    lat=spot["lat"],
                    lon=spot["lon"],
                    rating=spot["rating"],
                    review_count=spot["reviews_count"],
                    address=spot["address"],
                    price_level=spot.get("price_level", "Free"),
                    photos=spot.get("photos", []),
                    tags=spot.get("tags", []),
                    source="mindtrip_curated",
                    metadata_json=meta,
                )
                session.add(new_place)
        session.commit()
    except Exception:
        session.rollback()

    # 2. Query places for this destination (ordered by rating & reviews)
    stmt = (
        select(Place)
        .where(
            or_(
                func.lower(Place.destination) == dest_clean,
                Place.destination.ilike(f"%{dest_clean}%"),
                Place.address.ilike(f"%{dest_clean}%"),
            )
        )
        .order_by(
            Place.rating.desc(),
            Place.review_count.desc(),
        )
        .limit(limit)
    )
    places = session.exec(stmt).all()
    if not places:
        try:
            from backend.database.famous_spots import get_famous_spots_for_destination
            return get_famous_spots_for_destination(dest_clean)[:limit]
        except Exception:
            return []
    return [place_dict(p) for p in places]


def get_place(session: Session, place_id: str) -> dict[str, Any] | None:
    row = session.get(Place, place_id)
    return place_dict(row) if row else None


def list_hotels(
    session: Session,
    destination: str = "",
    min_price: float | None = None,
    max_price: float | None = None,
    stars: int | None = None,
    amenities: Iterable[str] = (),
    query: str = "",
    limit: int = 50,
    sort: str = "recommended",
) -> list[dict[str, Any]]:
    statement = select(Hotel)
    if destination:
        statement = statement.where(func.lower(Hotel.destination) == destination.strip().lower())
    if min_price is not None:
        statement = statement.where(Hotel.price_per_night >= min_price)
    if max_price is not None:
        statement = statement.where(Hotel.price_per_night <= max_price)
    if stars is not None:
        statement = statement.where(Hotel.stars >= stars)
    if query:
        statement = statement.where(
            or_(
                Hotel.name.ilike(f"%{query}%"),
                Hotel.address.ilike(f"%{query}%"),
                Hotel.description.ilike(f"%{query}%"),
            )
        )
    rows = list(session.exec(statement).all())
    wanted = [a.lower() for a in amenities if a]
    if wanted:
        rows = [row for row in rows if all(any(w in amenity.lower() for amenity in (row.amenities or [])) for w in wanted)]

    # Deduplicate rows: filter out duplicate hotels while preserving distinct branches
    try:
        from scrapers.adapters.google_hotels_adapter import are_same_hotel
        deduped_rows = []
        for row in rows:
            match_found = False
            for d in deduped_rows:
                if are_same_hotel(row.name, row.address, d.name, d.address):
                    match_found = True
                    break
            if not match_found:
                deduped_rows.append(row)
        rows = deduped_rows
    except Exception:
        pass

    if sort == "price":
        rows.sort(key=lambda row: row.price_per_night or 10**9)
    elif sort == "rating":
        rows.sort(key=lambda row: row.rating or 0, reverse=True)
    else:
        rows.sort(key=lambda row: ((row.rating or 0), -(row.price_per_night or 10**9)), reverse=True)
    return [hotel_dict(row) for row in rows[:limit]]


def get_hotel(session: Session, hotel_id: str) -> dict[str, Any] | None:
    row = session.get(Hotel, hotel_id)
    return hotel_dict(row) if row else None


def list_flights(
    session: Session,
    origin: str = "",
    destination: str = "",
    cabin: str = "",
    max_price: float | None = None,
    max_stops: int | None = None,
    sort: str = "price",
    limit: int | None = None,
) -> list[dict[str, Any]]:
    statement = select(Flight)
    if origin:
        statement = statement.where(Flight.origin == origin.upper())
    if destination:
        statement = statement.where(Flight.destination == destination.upper())
    if cabin and cabin.lower() != "any":
        statement = statement.where(Flight.cabin.ilike(cabin))
    if max_price is not None:
        statement = statement.where(Flight.price_usd <= max_price)
    if max_stops is not None:
        statement = statement.where(Flight.stops <= max_stops)
    rows = list(session.exec(statement).all())
    if sort == "duration":
        rows.sort(key=lambda row: row.duration_minutes)
    elif sort == "departure":
        rows.sort(key=lambda row: row.departure_time)
    else:
        rows.sort(key=lambda row: row.price_usd)
    if limit is not None and limit > 0:
        rows = rows[:limit]
    return [flight_dict(row) for row in rows]


def get_flight(session: Session, flight_id: str) -> dict[str, Any] | None:
    row = session.get(Flight, flight_id)
    return flight_dict(row) if row else None


def list_trips(session: Session, session_id: str = "", destination: str = "", limit: int = 50) -> list[dict[str, Any]]:
    statement = select(Trip).order_by(Trip.updated_at.desc())
    if session_id:
        statement = statement.where(Trip.session_id == session_id)
    if destination:
        statement = statement.where(Trip.destination == destination)
    rows = session.exec(statement.limit(limit)).all()
    return [trip_summary(session, row) for row in rows]


def get_trip(session: Session, trip_id: str) -> dict[str, Any] | None:
    row = session.get(Trip, trip_id)
    return trip_detail(session, row) if row else None


# --------------------------------------------------------------------------- #
# Mutations
# --------------------------------------------------------------------------- #
def create_trip(
    session: Session,
    *,
    title: str,
    destination: str,
    days: list[dict[str, Any]],
    start_date: str | None = None,
    end_date: str | None = None,
    traveler_type: str = "Traveler",
    budget: float = 0,
    cover_photo: str = "",
    summary: str = "",
    tags: list[str] | None = None,
    hotel_id: str | None = None,
    flight_id: str | None = None,
    flights_json: list[dict[str, Any]] | None = None,
    hotels_json: list[dict[str, Any]] | None = None,
    session_id: str | None = None,
    status: str = "draft",
    trip_id: str | None = None,
) -> dict[str, Any]:
    start = start_date or date.today().isoformat()
    end = end_date or (date.fromisoformat(start) + timedelta(days=max(0, len(days) - 1))).isoformat()
    destination_row = session.get(Destination, destination)
    if not cover_photo:
        from backend.services.destination_photos import resolve_destination_photo
        cover = (destination_row.hero_image if destination_row else "") or resolve_destination_photo(destination, session)
    else:
        cover = cover_photo

    if not summary:
        dest_display = destination.title() if destination else "your destination"
        summary = f"Your personalized travel journey through {dest_display}, featuring curated stays, attractions, and local experiences."
    
    # Auto budget calculation if not provided
    calculated_budget = budget
    if calculated_budget == 0:
        day_count = max(1, len(days))
        stay_cost = 0.0
        h_obj = session.get(Hotel, hotel_id) if hotel_id else None
        if not h_obj and hotels_json and len(hotels_json) > 0:
            h_obj = hotels_json[0]

        if h_obj:
            if isinstance(h_obj, dict):
                h_price = float(h_obj.get("price_per_night") or h_obj.get("price") or 0)
                h_curr = (h_obj.get("currency") or "USD").upper()
            else:
                h_price = float(getattr(h_obj, "price_per_night", 0) or 0)
                h_curr = (getattr(h_obj, "currency", "USD") or "USD").upper()
            h_usd = h_price / 85.0 if h_curr == "INR" else h_price
            stay_cost = h_usd * day_count

        flight_cost = 0.0
        fl_obj = session.get(Flight, flight_id) if flight_id else None
        if not fl_obj and flights_json and len(flights_json) > 0:
            fl_obj = flights_json[0]

        if fl_obj:
            if isinstance(fl_obj, dict):
                flight_cost = float(fl_obj.get("price_usd") or (float(fl_obj.get("price_inr", 0) or 0) / 85.0) or 0)
            else:
                fl_usd = float(getattr(fl_obj, "price_usd", 0) or 0)
                if fl_usd == 0 and getattr(fl_obj, "price_inr", 0):
                    fl_usd = float(getattr(fl_obj, "price_inr", 0)) / 85.0
                flight_cost = fl_usd

        if stay_cost > 0 or flight_cost > 0:
            calculated_budget = round(stay_cost + flight_cost + (day_count * 100.0), 2)

    trip = Trip(
        id=trip_id or unique_id(session, Trip, title),
        title=title,
        destination=destination,
        start_date=start,
        end_date=end,
        traveler_type=traveler_type,
        budget=calculated_budget,
        cover_photo=cover,
        summary=summary,
        status=status,
        tags=tags or [],
        creator={"name": "Mindtrip Assistant", "avatar_color": "#F1F2BA", "initials": "AI"},
        hotel_id=hotel_id,
        flight_id=flight_id,
        flights_json=flights_json or [],
        hotels_json=hotels_json or [],
        session_id=session_id,
    )
    session.add(trip)
    session.flush()
    for index, day in enumerate(days):
        day_row = TripDay(
            trip_id=trip.id,
            day_index=day.get("day_index", index + 1),
            date=day.get("date") or (date.fromisoformat(start) + timedelta(days=index)).isoformat(),
            title=day.get("title", f"Day {index + 1}"),
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
                    duration_mins=int(stop.get("duration_mins", 60)),
                    transit_info=stop.get("transit_info", ""),
                    notes=stop.get("notes", ""),
                    kind=stop.get("kind", "place"),
                )
            )
    session.commit()
    session.refresh(trip)
    return trip_detail(session, trip)


def update_trip(session: Session, trip_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
    trip = session.get(Trip, trip_id)
    if not trip:
        return None
    allowed = {
        "title", "destination", "start_date", "end_date", "traveler_type",
        "budget", "cover_photo", "summary", "status", "tags",
        "hotel_id", "flight_id", "flights_json", "hotels_json"
    }
    for key, value in patch.items():
        if key in allowed:
            setattr(trip, key, value)
            
    # Auto budget update if trip budget is 0
    if trip.budget == 0:
        day_count = len(session.exec(select(TripDay).where(TripDay.trip_id == trip.id)).all()) or 1
        stay_cost = 0.0
        h_obj = session.get(Hotel, trip.hotel_id) if trip.hotel_id else None
        if not h_obj and trip.hotels_json and len(trip.hotels_json) > 0:
            h_obj = trip.hotels_json[0]

        if h_obj:
            if isinstance(h_obj, dict):
                h_price = float(h_obj.get("price_per_night") or h_obj.get("price") or 0)
                h_curr = (h_obj.get("currency") or "USD").upper()
            else:
                h_price = float(getattr(h_obj, "price_per_night", 0) or 0)
                h_curr = (getattr(h_obj, "currency", "USD") or "USD").upper()
            h_usd = h_price / 85.0 if h_curr == "INR" else h_price
            stay_cost = h_usd * day_count

        flight_cost = 0.0
        fl_obj = session.get(Flight, trip.flight_id) if trip.flight_id else None
        if not fl_obj and trip.flights_json and len(trip.flights_json) > 0:
            fl_obj = trip.flights_json[0]

        if fl_obj:
            if isinstance(fl_obj, dict):
                flight_cost = float(fl_obj.get("price_usd") or (float(fl_obj.get("price_inr", 0) or 0) / 85.0) or 0)
            else:
                fl_usd = float(getattr(fl_obj, "price_usd", 0) or 0)
                if fl_usd == 0 and getattr(fl_obj, "price_inr", 0):
                    fl_usd = float(getattr(fl_obj, "price_inr", 0)) / 85.0
                flight_cost = fl_usd

        if stay_cost > 0 or flight_cost > 0:
            trip.budget = round(stay_cost + flight_cost + (day_count * 100.0), 2)

    trip.updated_at = utcnow()
    session.add(trip)
    session.commit()
    session.refresh(trip)
    return trip_detail(session, trip)


def delete_trip(session: Session, trip_id: str) -> bool:
    trip = session.get(Trip, trip_id)
    if not trip:
        return False
    for day in session.exec(select(TripDay).where(TripDay.trip_id == trip_id)).all():
        for stop in session.exec(select(TripStop).where(TripStop.trip_day_id == day.id)).all():
            session.delete(stop)
        session.delete(day)
    session.delete(trip)
    session.commit()
    return True


def reorder_stops(session: Session, trip_id: str, day_index: int, stop_ids: list[int]) -> dict[str, Any] | None:
    trip = session.get(Trip, trip_id)
    if not trip:
        return None
    day = session.exec(select(TripDay).where(TripDay.trip_id == trip_id, TripDay.day_index == day_index)).first()
    if not day:
        return None
    stops = {stop.id: stop for stop in session.exec(select(TripStop).where(TripStop.trip_day_id == day.id)).all()}
    for order, stop_id in enumerate(stop_ids):
        stop = stops.get(stop_id)
        if stop:
            stop.sort_order = order
            session.add(stop)
    trip.updated_at = utcnow()
    session.add(trip)
    session.commit()
    return trip_detail(session, trip)


def add_stop(session: Session, trip_id: str, day_index: int, place_id: str, time_slot: str = "afternoon", notes: str = "") -> dict[str, Any] | None:
    trip = session.get(Trip, trip_id)
    if not trip:
        return None
    day = session.exec(select(TripDay).where(TripDay.trip_id == trip_id, TripDay.day_index == day_index)).first()
    if not day:
        return None

    # Adding the same place to the same day is idempotent: refresh its slot
    # and notes instead of creating a duplicate stop / duplicate route line.
    existing = session.exec(
        select(TripStop).where(TripStop.trip_day_id == day.id, TripStop.place_id == place_id)
    ).first()
    if existing:
        existing.time_slot = time_slot or existing.time_slot
        if notes:
            existing.notes = notes
        trip.updated_at = utcnow()
        session.add(existing)
        session.add(trip)
        session.commit()
        return trip_detail(session, trip)

    count = len(session.exec(select(TripStop).where(TripStop.trip_day_id == day.id)).all())
    session.add(
        TripStop(
            trip_id=trip_id,
            trip_day_id=day.id or 0,
            place_id=place_id,
            sort_order=count,
            time_slot=time_slot,
            arrival_time="",
            duration_mins=90,
            transit_info="",
            notes=notes,
        )
    )
    trip.updated_at = utcnow()
    session.add(trip)
    session.commit()
    return trip_detail(session, trip)


def remove_stop(session: Session, trip_id: str, stop_id: int) -> dict[str, Any] | None:
    stop = session.get(TripStop, stop_id)
    if not stop or stop.trip_id != trip_id:
        return None
    day_id = stop.trip_day_id
    session.delete(stop)
    session.flush()

    # Re-order remaining stops in day so sort_order stays sequential
    remaining = session.exec(select(TripStop).where(TripStop.trip_day_id == day_id).order_by(TripStop.sort_order)).all()
    for idx, s in enumerate(remaining):
        s.sort_order = idx
        session.add(s)

    trip = session.get(Trip, trip_id)
    if trip:
        trip.updated_at = utcnow()
        session.add(trip)
    session.commit()
    return get_trip(session, trip_id)


def update_day_stops(
    session: Session,
    trip_id: str,
    day_index: int,
    place_ids: list[str],
    notes_list: list[str] | None = None,
) -> dict[str, Any] | None:
    """Replace all stops for a given day with a new ordered list of place IDs."""
    trip = session.get(Trip, trip_id)
    if not trip:
        return None
    day = session.exec(select(TripDay).where(TripDay.trip_id == trip_id, TripDay.day_index == day_index)).first()
    if not day:
        return None

    # Delete existing stops for this day
    old_stops = session.exec(select(TripStop).where(TripStop.trip_day_id == day.id)).all()
    for s in old_stops:
        session.delete(s)
    session.flush()

    slots = ["morning", "afternoon", "evening", "night"]
    for idx, pid in enumerate(place_ids):
        slot = slots[idx] if idx < len(slots) else "afternoon"
        note = (notes_list[idx] if notes_list and idx < len(notes_list) else "")
        session.add(
            TripStop(
                trip_id=trip_id,
                trip_day_id=day.id or 0,
                place_id=pid,
                sort_order=idx,
                time_slot=slot,
                arrival_time="",
                duration_mins=90,
                transit_info="",
                notes=note,
                kind="place",
            )
        )
    trip.updated_at = utcnow()
    session.add(trip)
    session.commit()
    return get_trip(session, trip_id)


# --------------------------------------------------------------------------- #
# Chat persistence
# --------------------------------------------------------------------------- #
def save_chat_message(
    session: Session,
    session_id: str,
    sender: str,
    message: str,
    cards: list[dict[str, Any]] | None = None,
    pins: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    row = ChatMessage(
        session_id=session_id,
        sender=sender,
        message=message,
        cards_json=cards or [],
        pins_json=pins or [],
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return {
        "id": row.id,
        "session_id": row.session_id,
        "sender": row.sender,
        "message": row.message,
        "cards": row.cards_json or [],
        "pins": row.pins_json or [],
        "created_at": row.created_at,
    }


def chat_history(session: Session, session_id: str, limit: int = 100) -> list[dict[str, Any]]:
    rows = session.exec(
        select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.id).limit(limit)
    ).all()
    return [
        {
            "id": row.id,
            "session_id": row.session_id,
            "sender": row.sender,
            "message": row.message,
            "cards": row.cards_json or [],
            "pins": row.pins_json or [],
            "created_at": row.created_at,
        }
        for row in rows
    ]
