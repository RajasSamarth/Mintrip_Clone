"""Standard records shared by every scraper adapter.

The goal is simple: whatever shape your Google Maps / Google Flights scraper
emits, normalise it to these models before it touches the database.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "record"


def _normalise_photos(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    out = []
    for item in value:
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict):
            out.append(item.get("url") or item.get("src") or item.get("photo") or "")
    return [p for p in out if p]


class PlaceRecord(BaseModel):
    id: str = ""
    name: str
    category: Literal["hotel", "restaurant", "cafe", "attraction", "activity", "bar", "shopping", "other"] = "other"
    destination: str = ""
    description: str = ""
    lat: float
    lon: float
    rating: float | None = None
    review_count: int = 0
    address: str = ""
    price_level: int | None = Field(default=None, ge=0, le=4)
    opening_hours: str = ""
    photos: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    source: str = "google_maps"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _default_id(self) -> "PlaceRecord":
        if not self.id:
            self.id = slugify(self.name)
        return self

    @field_validator("category", mode="before")
    @classmethod
    def _normalise_category(cls, value: Any) -> str:
        if not value:
            return "other"
        raw = str(value).strip().lower()
        mapping = {
            "lodging": "hotel", "hotels": "hotel", "accommodation": "hotel",
            "restaurants": "restaurant", "food": "restaurant", "eatery": "restaurant",
            "cafes": "cafe", "coffee": "cafe", "coffee shop": "cafe",
            "tourist attraction": "attraction", "museum": "attraction", "landmark": "attraction",
            "things to do": "activity", "tour": "activity", "experience": "activity",
            "bars": "bar", "nightclub": "bar", "store": "shopping", "shop": "shopping",
        }
        for key, mapped in mapping.items():
            if key in raw:
                return mapped
        return raw if raw in {"hotel", "restaurant", "cafe", "attraction", "activity", "bar", "shopping", "other"} else "other"

    @field_validator("photos", mode="before")
    @classmethod
    def _photos(cls, value: Any) -> list[str]:
        return _normalise_photos(value)


class HotelRecord(BaseModel):
    id: str = ""
    name: str
    destination: str = ""
    stars: int = Field(default=0, ge=0, le=5)
    rating: float | None = Field(default=None, ge=0, le=5)
    review_count: int = 0
    address: str = ""
    lat: float | None = None
    lon: float | None = None
    price_per_night: float | None = None
    currency: str = "USD"
    price_unavailable: bool = False
    amenities: list[str] = Field(default_factory=list)
    photos: list[str] = Field(default_factory=list)
    room_types: list[dict[str, Any]] = Field(default_factory=list)
    booking_url: str = ""
    description: str = ""
    source: str = "hotel_scraper"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _default_id(self) -> "HotelRecord":
        if not self.id:
            self.id = slugify(self.name)
        return self

    @field_validator("amenities", mode="before")
    @classmethod
    def _amenities(cls, value: Any) -> list[str]:
        if not value:
            return []
        if isinstance(value, str):
            return [v.strip() for v in re.split(r"[,;|]", value) if v.strip()]
        return [str(v).strip() for v in value if str(v).strip()]

    @field_validator("photos", mode="before")
    @classmethod
    def _photos(cls, value: Any) -> list[str]:
        return _normalise_photos(value)


class FlightRecord(BaseModel):
    id: str = ""
    airline: str
    airline_code: str = ""
    flight_number: str = ""
    origin: str
    destination: str
    departure_time: datetime | str
    arrival_time: datetime | str
    duration_minutes: int = 0
    stops: int = 0
    price_usd: float = 0.0
    price_inr: float = 0.0
    is_top_pick: bool = False
    cabin: str = "Economy"
    baggage: str = ""
    booking_url: str = ""
    emissions: str = ""
    emissions_diff_pct: int = 0
    self_transfer: bool = False
    source: str = "google_flights"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _default_id(self) -> "FlightRecord":
        if not self.id:
            if self.flight_number:
                self.id = slugify(f"{self.airline}-{self.flight_number}-{self.origin}-{self.destination}")
            else:
                self.id = slugify(f"{self.airline}-{self.origin}-{self.destination}-{self.departure_time}")
        if self.price_usd and not self.price_inr:
            self.price_inr = round(self.price_usd * 85.0, 2)
        elif self.price_inr and not self.price_usd:
            self.price_usd = round(self.price_inr / 85.0, 2)
        return self

    @field_validator("origin", "destination", mode="before")
    @classmethod
    def _iata(cls, value: Any) -> str:
        return str(value or "").strip().upper()[:3]


class TripStopRecord(BaseModel):
    place_id: str
    time_slot: Literal["morning", "afternoon", "evening"] = "morning"
    arrival_time: str = ""
    duration_mins: int = 60
    transit_info: str = ""
    notes: str = ""
    kind: str = "place"


class TripDayRecord(BaseModel):
    day_index: int
    date: date | str
    title: str = ""
    summary: str = ""
    stops: list[TripStopRecord] = Field(default_factory=list)


class TripRecord(BaseModel):
    id: str = ""
    title: str
    destination: str = ""
    start_date: date | str
    end_date: date | str
    traveler_type: str = "Traveler"
    budget: float = 0
    cover_photo: str = ""
    summary: str = ""
    status: str = "draft"
    tags: list[str] = Field(default_factory=list)
    days: list[TripDayRecord] = Field(default_factory=list)

    @model_validator(mode="after")
    def _default_id(self) -> "TripRecord":
        if not self.id:
            self.id = slugify(self.title)
        return self


class AdapterResult(BaseModel):
    """Every adapter returns one of these so ingestion can be audited."""

    source: str
    total: int
    records: list[Any]
    skipped: int = 0
    warnings: list[str] = Field(default_factory=list)
