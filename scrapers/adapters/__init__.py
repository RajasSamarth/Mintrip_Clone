"""Scraper adapters for the Mindtrip clone."""

from .base_adapter import (
    AdapterResult,
    FlightRecord,
    HotelRecord,
    PlaceRecord,
    TripDayRecord,
    TripRecord,
    TripStopRecord,
)

__all__ = [
    "AdapterResult",
    "PlaceRecord",
    "HotelRecord",
    "FlightRecord",
    "TripRecord",
    "TripDayRecord",
    "TripStopRecord",
]
