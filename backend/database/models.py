"""Database models. SQLite by default; swap DATABASE_URL for Postgres."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Column, JSON, Text
from sqlmodel import Field, SQLModel


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class Destination(SQLModel, table=True):
    __tablename__ = "destinations"

    id: str = Field(primary_key=True)
    name: str
    country: str = ""
    tagline: str = ""
    description: str = Field(default="", sa_column=Column(Text))
    hero_image: str = ""
    gallery: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    best_season: str = ""
    lat: float = 0
    lon: float = 0


class Place(SQLModel, table=True):
    __tablename__ = "places"

    id: str = Field(primary_key=True)
    name: str = Field(index=True)
    category: str = Field(default="other", index=True)
    destination: str = Field(default="", index=True)
    city: str = Field(default="", index=True)
    country: str = Field(default="")
    description: str = Field(default="", sa_column=Column(Text))
    lat: float = 0
    lon: float = 0
    rating: float | None = None
    review_count: int = 0
    address: str = ""
    price_level: int | None = None
    opening_hours: str = ""
    photos: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    source: str = "curated"
    metadata_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column("metadata", JSON))


class Hotel(SQLModel, table=True):
    __tablename__ = "hotels"

    id: str = Field(primary_key=True)
    name: str = Field(index=True)
    destination: str = Field(default="", index=True)
    stars: int = 0
    rating: float | None = None
    review_count: int = 0
    address: str = ""
    lat: float | None = None
    lon: float | None = None
    price_per_night: float | None = None
    currency: str = "USD"
    amenities: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    photos: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    room_types: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    booking_url: str = ""
    description: str = Field(default="", sa_column=Column(Text))
    source: str = "curated"
    metadata_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column("metadata", JSON))


class Flight(SQLModel, table=True):
    __tablename__ = "flights"

    id: str = Field(primary_key=True)
    airline: str
    airline_code: str = ""
    flight_number: str = ""
    origin: str = Field(index=True)
    destination: str = Field(index=True)
    departure_time: str
    arrival_time: str
    duration_minutes: int = 0
    stops: int = 0
    price_usd: float = 0
    cabin: str = "Economy"
    baggage: str = ""
    booking_url: str = ""
    source: str = "curated"
    metadata_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column("metadata", JSON))


class Trip(SQLModel, table=True):
    __tablename__ = "trips"

    id: str = Field(primary_key=True)
    title: str
    destination: str = Field(default="", index=True)
    start_date: str = ""
    end_date: str = ""
    traveler_type: str = "Traveler"
    budget: float = 0
    cover_photo: str = ""
    summary: str = Field(default="", sa_column=Column(Text))
    status: str = "draft"
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    creator: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    hotel_id: str | None = None
    flight_id: str | None = Field(default=None, index=True)
    flights_json: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    hotels_json: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    session_id: str | None = Field(default=None, index=True)
    created_at: str = Field(default_factory=utcnow)
    updated_at: str = Field(default_factory=utcnow)


class TripDay(SQLModel, table=True):
    __tablename__ = "trip_days"

    id: int | None = Field(default=None, primary_key=True)
    trip_id: str = Field(index=True)
    day_index: int = 1
    date: str = ""
    title: str = ""
    summary: str = ""


class TripStop(SQLModel, table=True):
    __tablename__ = "trip_stops"

    id: int | None = Field(default=None, primary_key=True)
    trip_id: str = Field(index=True)
    trip_day_id: int = Field(index=True)
    place_id: str = ""
    sort_order: int = 0
    time_slot: str = "morning"
    arrival_time: str = ""
    duration_mins: int = 60
    transit_info: str = ""
    notes: str = ""
    kind: str = "place"


class ChatMessage(SQLModel, table=True):
    __tablename__ = "chat_messages"

    id: int | None = Field(default=None, primary_key=True)
    session_id: str = Field(index=True)
    sender: str = "assistant"
    message: str = Field(default="", sa_column=Column(Text))
    cards_json: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    pins_json: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: str = Field(default_factory=utcnow)


class GuestSession(SQLModel, table=True):
    __tablename__ = "guest_sessions"

    id: str = Field(primary_key=True)
    created_at: str = Field(default_factory=utcnow)
    preferences: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
