"""Trip CRUD, reordering and export endpoints."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlmodel import Session

from backend.database.db import get_session
from backend.database.models import Trip
from backend.services import data_service

router = APIRouter(prefix="/trips", tags=["trips"])


class TripCreate(BaseModel):
    title: str
    destination: str
    days: list[dict[str, Any]] = Field(default_factory=list)
    start_date: str = ""
    end_date: str = ""
    traveler_type: str = "Traveler"
    budget: float = 0
    cover_photo: str = ""
    summary: str = ""
    tags: list[str] = Field(default_factory=list)
    hotel_id: str = ""
    flight_id: str = ""
    flights_json: list[dict[str, Any]] = Field(default_factory=list)
    hotels_json: list[dict[str, Any]] = Field(default_factory=list)
    session_id: str = ""


class TripPatch(BaseModel):
    title: str | None = None
    destination: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    traveler_type: str | None = None
    budget: float | None = None
    cover_photo: str | None = None
    summary: str | None = None
    status: str | None = None
    tags: list[str] | None = None
    hotel_id: str | None = None
    flight_id: str | None = None
    flights_json: list[dict[str, Any]] | None = None
    hotels_json: list[dict[str, Any]] | None = None


class AttachHotelRequest(BaseModel):
    hotel_id: str | None = None
    hotel_data: dict[str, Any] | None = None


class AttachFlightRequest(BaseModel):
    flight_id: str | None = None
    flight_data: dict[str, Any] | None = None


class ReorderRequest(BaseModel):
    day_index: int
    stop_ids: list[int]


class AddStopRequest(BaseModel):
    day_index: int = 1
    place_id: str
    time_slot: str = "afternoon"
    notes: str = ""


@router.get("")
@router.get("/")
def list_trips(
    session_id: str = Query(default=""),
    destination: str = Query(default=""),
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    trips = data_service.list_trips(session, session_id=session_id, destination=destination, limit=limit)
    return {"trips": trips, "count": len(trips)}


@router.get("/{trip_id}")
def get_trip(trip_id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    trip = data_service.get_trip(session, trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


@router.post("", status_code=201)
@router.post("/", status_code=201)
def create_trip(payload: TripCreate, session: Session = Depends(get_session)) -> dict[str, Any]:
    trip = data_service.create_trip(
        session,
        title=payload.title,
        destination=payload.destination,
        days=payload.days,
        start_date=payload.start_date or None,
        end_date=payload.end_date or None,
        traveler_type=payload.traveler_type,
        budget=payload.budget,
        cover_photo=payload.cover_photo,
        summary=payload.summary,
        tags=payload.tags,
        hotel_id=payload.hotel_id or None,
        flight_id=payload.flight_id or None,
        flights_json=payload.flights_json or [],
        hotels_json=payload.hotels_json or [],
        session_id=payload.session_id or None,
    )
    return trip


@router.patch("/{trip_id}")
def patch_trip(trip_id: str, payload: TripPatch, session: Session = Depends(get_session)) -> dict[str, Any]:
    trip = data_service.update_trip(session, trip_id, payload.model_dump(exclude_unset=True))
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


@router.post("/{trip_id}/hotel")
def attach_hotel(trip_id: str, payload: AttachHotelRequest, session: Session = Depends(get_session)) -> dict[str, Any]:
    patch_data: dict[str, Any] = {}
    if payload.hotel_id:
        patch_data["hotel_id"] = payload.hotel_id
    if payload.hotel_data:
        patch_data["hotels_json"] = [payload.hotel_data]
    trip = data_service.update_trip(session, trip_id, patch_data)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


@router.delete("/{trip_id}/hotel")
def detach_hotel(trip_id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    trip = data_service.update_trip(session, trip_id, {"hotel_id": None, "hotels_json": []})
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


@router.post("/{trip_id}/flight")
def attach_flight(trip_id: str, payload: AttachFlightRequest, session: Session = Depends(get_session)) -> dict[str, Any]:
    patch_data: dict[str, Any] = {}
    if payload.flight_id:
        patch_data["flight_id"] = payload.flight_id
    if payload.flight_data:
        existing = session.get(Trip, trip_id)
        current_flights = [f for f in (existing.flights_json or []) if isinstance(f, dict) and f.get("id") != payload.flight_data.get("id")] if existing else []
        # Prepend so the newly attached flight is primary at index 0
        current_flights.insert(0, payload.flight_data)
        patch_data["flights_json"] = current_flights
    trip = data_service.update_trip(session, trip_id, patch_data)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


@router.delete("/{trip_id}/flight")
def detach_flight(trip_id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    trip = data_service.update_trip(session, trip_id, {"flight_id": None, "flights_json": []})
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


@router.delete("/{trip_id}")
def delete_trip(trip_id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    if not data_service.delete_trip(session, trip_id):
        raise HTTPException(status_code=404, detail="Trip not found")
    return {"deleted": True, "id": trip_id}


@router.post("/{trip_id}/reorder")
def reorder(trip_id: str, payload: ReorderRequest, session: Session = Depends(get_session)) -> dict[str, Any]:
    trip = data_service.reorder_stops(session, trip_id, payload.day_index, payload.stop_ids)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip or day not found")
    return trip


@router.post("/{trip_id}/stops")
def add_stop(trip_id: str, payload: AddStopRequest, session: Session = Depends(get_session)) -> dict[str, Any]:
    trip = data_service.add_stop(session, trip_id, payload.day_index, payload.place_id, payload.time_slot, payload.notes)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip or day not found")
    return trip


@router.delete("/{trip_id}/stops/{stop_id}")
def remove_stop(trip_id: str, stop_id: int, session: Session = Depends(get_session)) -> dict[str, Any]:
    trip = data_service.remove_stop(session, trip_id, stop_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Stop not found")
    return trip


@router.get("/{trip_id}/export")
def export_trip(trip_id: str, session: Session = Depends(get_session)) -> Response:
    trip = data_service.get_trip(session, trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    payload = json.dumps(trip, indent=2, ensure_ascii=False)
    return Response(
        content=payload,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{trip_id}.json"'},
    )
