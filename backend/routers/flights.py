"""Flight search endpoints and scraper integration."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import Session

import json

from backend.database.db import get_session
from backend.services import data_service
from scrapers.flight_scraper_runner import (
    save_flights_to_db,
    search_flights,
)

router = APIRouter(prefix="/flights", tags=["flights"])
log = logging.getLogger("flights_router")


def _safe_float(val: Any, default: float = 0.0) -> float:
    """Safely convert a value to float, returning default on failure."""
    try:
        if val is None:
            return default
        return float(val)
    except (TypeError, ValueError):
        return default


def _safe_json(val: Any) -> Any:
    """Return a JSON-safe version of val, dropping non-serializable items."""
    try:
        json.dumps(val)
        return val
    except (TypeError, ValueError):
        if isinstance(val, dict):
            return {k: _safe_json(v) for k, v in val.items()}
        if isinstance(val, list):
            return [_safe_json(v) for v in val]
        return str(val)


# In-memory job store for async flight scraping.
# Key: job_id, Value: {"status": "pending"|"done"|"error", "result": dict|None, "error": str|None}
_search_jobs: dict[str, dict[str, Any]] = {}


def _build_flight_rows(records: list[Any], adults: int = 1, children: int = 0, cabin: str = "Economy", trip_type: str = "one-way", currency: str = "INR") -> list[dict[str, Any]]:
    """Build clean output rows preserving is_top_pick, price_inr, emissions, self_transfer, return flight & multi-pax."""
    total_pax = max(1, adults + children)
    rows = []
    for r in records:
        try:
            meta = r.metadata or {}
            ret_fl = meta.get("return_flight")
            trip_type_val = trip_type or meta.get("trip_type", "one-way")
            total_usd = _safe_float(meta.get("total_price_usd") or r.price_usd or 0.0)
            per_person_usd = _safe_float(
                meta.get("price_per_person_usd")
                or round(total_usd / max(1, total_pax), 2)
                or 120.0
            )
            per_person_inr = _safe_float(meta.get("price_per_person_inr") or round(per_person_usd * 85.0, 2))
            total_inr = _safe_float(meta.get("total_price_inr") or round(total_usd * 85.0, 2))

            rows.append({
                "id": str(r.id),
                "airline": str(r.airline or ""),
                "airline_code": str(r.airline_code or ""),
                "flight_number": str(r.flight_number or ""),
                "origin": str(r.origin or ""),
                "destination": str(r.destination or ""),
                "departure_time": str(r.departure_time or ""),
                "arrival_time": str(r.arrival_time or ""),
                "duration_minutes": int(r.duration_minutes or 0),
                "stops": int(r.stops or 0),
                "price_usd": total_usd,
                "price_inr": total_inr,
                "price_per_person_usd": per_person_usd,
                "price_per_person_inr": per_person_inr,
                "passengers": int(total_pax),
                "trip_type": str(trip_type_val),
                "return_flight": ret_fl,
                "cabin": str(r.cabin or "Economy"),
                "baggage": str(r.baggage or ""),
                "booking_url": str(r.booking_url or ""),
                "source": str(r.source or "google_flights_live"),
                "is_top_pick": bool(r.is_top_pick),
                "emissions": str(r.emissions or ""),
                "emissions_diff_pct": _safe_float(r.emissions_diff_pct),
                "self_transfer": bool(r.self_transfer),
                "metadata": _safe_json({
                    **meta,
                    "return_flight": ret_fl,
                    "passengers": int(total_pax),
                    "trip_type": str(trip_type_val),
                    "price_per_person_usd": per_person_usd,
                    "price_per_person_inr": per_person_inr,
                    "total_price_usd": total_usd,
                    "total_price_inr": total_inr,
                }),
            })
        except Exception as row_err:
            log.warning("Failed to build flight row: %s", row_err)
            continue
    return rows


async def _run_scrape_job(
    job_id: str,
    origin: str,
    destination: str,
    date: str,
    return_date: str | None,
    cabin: str,
    adults: int,
    children: int,
    infants_seat: int,
    infants_lap: int,
    currency: str,
    trip_type: str,
    legs: list[dict[str, str]] | None,
    max_results: int | None,
) -> None:
    """Run the flight scrape in the background and store results in _search_jobs."""
    try:
        records = await search_flights(
            origin=origin,
            destination=destination,
            date=date,
            return_date=return_date,
            cabin=cabin,
            adults=adults,
            children=children,
            infants_seat=infants_seat,
            infants_lap=infants_lap,
            currency=currency,
            trip_type=trip_type,
            legs=legs,
            live=True,
            max_results=max_results,
            allow_fallback=False,
        )
        # Always store the result, even if empty
        if records:
            # Save to DB for history (best effort)
            try:
                from backend.database.db import engine as _engine
                from sqlmodel import Session as _Session
                with _Session(_engine) as _s:
                    save_flights_to_db(records, session=_s)
            except Exception as db_err:
                log.warning("Could not persist flights to DB: %s", db_err)

        # Per-leg diagnostics so the UI can tell which multi-city leg failed
        # instead of silently displaying an incomplete journey.
        leg_summary: list[dict[str, Any]] = []
        failed_legs: list[dict[str, Any]] = []
        if trip_type == "multi-city" and legs:
            counts: dict[int, int] = {}
            for r in records:
                idx = int((r.metadata or {}).get("leg_index", 0))
                counts[idx] = counts.get(idx, 0) + 1
            for idx, leg in enumerate(legs):
                count = counts.get(idx, 0)
                entry = {
                    "index": idx,
                    "origin": str(leg.get("origin", "")).upper(),
                    "destination": str(leg.get("destination", "")).upper(),
                    "date": leg.get("date", ""),
                    "count": count,
                }
                leg_summary.append(entry)
                if count == 0:
                    failed_legs.append(entry)

        _search_jobs[job_id] = {
            "status": "done",
            "result": {
                "flights": _build_flight_rows(records, adults, children, cabin, trip_type, currency),
                "count": len(records),
                "source": "google_flights_live" if any(r.source == "google_flights_live" for r in records) else "curated_route_model",
                "currency": currency,
                "origin": origin,
                "destination": destination,
                "legs": leg_summary,
                "failed_legs": failed_legs,
            },
            "error": None,
            "created": _search_jobs.get(job_id, {}).get("created", time.time()),
        }
    except Exception as e:
        log.exception("Flight scrape job %s failed: %s", job_id, e)
        _search_jobs[job_id] = {
            "status": "error",
            "result": None,
            "error": str(e),
            "created": _search_jobs.get(job_id, {}).get("created", time.time()),
        }


AIRPORTS = [
    # North America
    {"code": "SFO", "city": "San Francisco", "name": "San Francisco International", "country": "US"},
    {"code": "LAX", "city": "Los Angeles", "name": "Los Angeles International", "country": "US"},
    {"code": "JFK", "city": "New York", "name": "John F. Kennedy International", "country": "US"},
    {"code": "EWR", "city": "Newark", "name": "Newark Liberty International", "country": "US"},
    {"code": "LGA", "city": "New York", "name": "LaGuardia Airport", "country": "US"},
    {"code": "ORD", "city": "Chicago", "name": "O'Hare International", "country": "US"},
    {"code": "BOS", "city": "Boston", "name": "Logan International", "country": "US"},
    {"code": "SEA", "city": "Seattle", "name": "Seattle-Tacoma International", "country": "US"},
    {"code": "MIA", "city": "Miami", "name": "Miami International", "country": "US"},
    {"code": "DFW", "city": "Dallas", "name": "Dallas/Fort Worth International", "country": "US"},
    {"code": "DEN", "city": "Denver", "name": "Denver International", "country": "US"},
    {"code": "ATL", "city": "Atlanta", "name": "Hartsfield-Jackson International", "country": "US"},
    {"code": "IAD", "city": "Washington, D.C.", "name": "Dulles International", "country": "US"},
    {"code": "LAS", "city": "Las Vegas", "name": "Harry Reid International", "country": "US"},
    {"code": "PHX", "city": "Phoenix", "name": "Phoenix Sky Harbor", "country": "US"},
    {"code": "YVR", "city": "Vancouver", "name": "Vancouver International", "country": "CA"},
    {"code": "YYZ", "city": "Toronto", "name": "Toronto Pearson International", "country": "CA"},
    # Europe
    {"code": "LHR", "city": "London", "name": "Heathrow", "country": "GB"},
    {"code": "LGW", "city": "London", "name": "Gatwick", "country": "GB"},
    {"code": "CDG", "city": "Paris", "name": "Charles de Gaulle", "country": "FR"},
    {"code": "ORY", "city": "Paris", "name": "Paris Orly", "country": "FR"},
    {"code": "FCO", "city": "Rome", "name": "Leonardo da Vinci–Fiumicino", "country": "IT"},
    {"code": "MXP", "city": "Milan", "name": "Malpensa", "country": "IT"},
    {"code": "FRA", "city": "Frankfurt", "name": "Frankfurt am Main", "country": "DE"},
    {"code": "MUC", "city": "Munich", "name": "Munich Airport", "country": "DE"},
    {"code": "AMS", "city": "Amsterdam", "name": "Schiphol", "country": "NL"},
    {"code": "BCN", "city": "Barcelona", "name": "El Prat", "country": "ES"},
    {"code": "MAD", "city": "Madrid", "name": "Barajas", "country": "ES"},
    {"code": "ZRH", "city": "Zurich", "name": "Zurich Airport", "country": "CH"},
    {"code": "GVA", "city": "Geneva", "name": "Geneva Airport", "country": "CH"},
    {"code": "LIS", "city": "Lisbon", "name": "Humberto Delgado", "country": "PT"},
    {"code": "VIE", "city": "Vienna", "name": "Vienna International", "country": "AT"},
    {"code": "ATH", "city": "Athens", "name": "Eleftherios Venizelos", "country": "GR"},
    {"code": "DUB", "city": "Dublin", "name": "Dublin Airport", "country": "IE"},
    {"code": "CPH", "city": "Copenhagen", "name": "Copenhagen Airport", "country": "DK"},
    {"code": "IST", "city": "Istanbul", "name": "Istanbul Airport", "country": "TR"},
    # Asia & Pacific
    {"code": "HND", "city": "Tokyo", "name": "Haneda", "country": "JP"},
    {"code": "NRT", "city": "Tokyo", "name": "Narita International", "country": "JP"},
    {"code": "KIX", "city": "Osaka", "name": "Kansai International", "country": "JP"},
    {"code": "ICN", "city": "Seoul", "name": "Incheon International", "country": "KR"},
    {"code": "SIN", "city": "Singapore", "name": "Changi Airport", "country": "SG"},
    {"code": "BKK", "city": "Bangkok", "name": "Suvarnabhumi Airport", "country": "TH"},
    {"code": "HKG", "city": "Hong Kong", "name": "Hong Kong International", "country": "HK"},
    {"code": "TPE", "city": "Taipei", "name": "Taoyuan International", "country": "TW"},
    {"code": "KUL", "city": "Kuala Lumpur", "name": "Kuala Lumpur International", "country": "MY"},
    {"code": "DPS", "city": "Bali", "name": "Ngurah Rai International", "country": "ID"},
    {"code": "SYD", "city": "Sydney", "name": "Sydney Kingsford Smith", "country": "AU"},
    {"code": "MEL", "city": "Melbourne", "name": "Melbourne Airport", "country": "AU"},
    {"code": "AKL", "city": "Auckland", "name": "Auckland Airport", "country": "NZ"},
    # India & South Asia
    {"code": "DEL", "city": "Delhi", "name": "Indira Gandhi International", "country": "IN"},
    {"code": "BOM", "city": "Mumbai", "name": "Chhatrapati Shivaji Maharaj International", "country": "IN"},
    {"code": "BLR", "city": "Bengaluru", "name": "Kempegowda International", "country": "IN"},
    {"code": "MAA", "city": "Chennai", "name": "Chennai International", "country": "IN"},
    {"code": "HYD", "city": "Hyderabad", "name": "Rajiv Gandhi International", "country": "IN"},
    {"code": "CCU", "city": "Kolkata", "name": "Netaji Subhash Chandra Bose International", "country": "IN"},
    {"code": "GOI", "city": "Goa", "name": "Dabolim / Manohar International", "country": "IN"},
    {"code": "COK", "city": "Kochi", "name": "Cochin International", "country": "IN"},
    # Middle East
    {"code": "DXB", "city": "Dubai", "name": "Dubai International", "country": "AE"},
    {"code": "DOH", "city": "Doha", "name": "Hamad International", "country": "QA"},
    {"code": "AUH", "city": "Abu Dhabi", "name": "Zayed International", "country": "AE"},
    {"code": "JED", "city": "Jeddah", "name": "King Abdulaziz International", "country": "SA"},
    {"code": "RUH", "city": "Riyadh", "name": "King Khalid International", "country": "SA"},
]


class FlightLeg(BaseModel):
    origin: str
    destination: str
    date: str


class FlightSearchRequest(BaseModel):
    origin: str = Field(default="SFO", description="Origin airport code or query, e.g. SFO")
    destination: str = Field(default="JFK", description="Destination airport code or query, e.g. JFK")
    outbound_date: str | None = Field(default=None, description="Departure date (YYYY-MM-DD)")
    return_date: str | None = Field(default=None, description="Return date (YYYY-MM-DD)")
    trip_type: str = Field(default="one-way", description="one-way, round-trip, multi-city")
    legs: list[FlightLeg] = Field(default_factory=list, description="Legs for multi-city search")
    cabin: str = Field(default="Economy", description="Economy, Premium, Business, First")
    adults: int = Field(default=1, ge=1, le=9)
    children: int = Field(default=0, ge=0, le=8)
    infants_seat: int = Field(default=0, ge=0, le=4)
    infants_lap: int = Field(default=0, ge=0, le=4)
    currency: str = Field(default="INR", description="Currency: INR, USD, EUR, GBP, AED, etc.")
    live: bool = Field(default=True, description="Always freshly scrapes live")
    max_results: int | None = Field(default=None, description="Maximum results or None for all")


@router.get("")
@router.get("/")
async def list_flights(
    origin: str = "",
    destination: str = "",
    cabin: str = "",
    max_price: float | None = None,
    max_stops: int | None = None,
    sort: str = "price",
    limit: int = 10000,
    auto_scrape: bool = True,
    live: bool = True,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    # Handle direct call where Query objects might be passed if using Query(...)
    cabin_val = str(cabin or "")
    origin_val = str(origin or "").strip().upper()
    dest_val = str(destination or "").strip().upper()

    rows = data_service.list_flights(
        session,
        origin=origin_val,
        destination=dest_val,
        cabin=cabin_val,
        max_price=max_price,
        max_stops=max_stops,
        sort=sort,
        limit=limit,
    )

    # If user searched for a specific origin + destination and 0 flights exist in DB:
    if not rows and origin_val and dest_val and auto_scrape:
        try:
            log.info("Auto-scraping flights for %s -> %s...", origin_val, dest_val)
            records = await search_flights(
                origin=origin_val,
                destination=dest_val,
                date="",
                cabin=cabin_val or "Economy",
                max_results=limit,
                live=live,
                allow_fallback=not live,
            )
            saved = save_flights_to_db(records, session=session)
            if saved > 0:
                try:
                    rows = data_service.list_flights(
                        session,
                        origin=origin,
                        destination=destination,
                        cabin=cabin,
                        max_price=max_price,
                        max_stops=max_stops,
                        sort=sort,
                        limit=limit,
                    )
                except Exception:
                    rows = []
            if not rows:
                rows = [
                    {
                        "id": r.id,
                        "airline": r.airline,
                        "airline_code": r.airline_code,
                        "flight_number": r.flight_number,
                        "origin": r.origin,
                        "destination": r.destination,
                        "departure_time": str(r.departure_time),
                        "arrival_time": str(r.arrival_time),
                        "duration_minutes": r.duration_minutes,
                        "stops": r.stops,
                        "price_usd": r.price_usd,
                        "price_inr": r.price_inr or (round(r.price_usd * 85.0, 2) if r.price_usd else None),
                        "cabin": r.cabin,
                        "baggage": r.baggage,
                        "booking_url": r.booking_url,
                        "source": r.source,
                        "is_top_pick": r.is_top_pick,
                        "emissions": r.emissions,
                        "emissions_diff_pct": r.emissions_diff_pct,
                        "self_transfer": r.self_transfer,
                    }
                    for r in records
                ]
        except Exception as e:
            log.warning("Auto-scrape fallback failed: %s", e)

    return {"flights": rows, "count": len(rows)}


@router.post("/search")
async def search_flights_endpoint(
    payload: FlightSearchRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Execute on-demand flight search via Google Flights live scraper.

    Returns a job_id immediately. The scrape runs in the background; poll
    GET /api/flights/search/{job_id} for results.
    """
    origin = payload.origin.strip().upper()[:3]
    destination = payload.destination.strip().upper()[:3]

    # Convert legs if multi-city
    legs_dicts = [leg.model_dump() for leg in payload.legs] if payload.legs else None

    job_id = uuid.uuid4().hex

    # Prune stale jobs (older than 1 hour) to keep the in-memory store bounded.
    now = time.time()
    for stale_id in [
        jid
        for jid, job in _search_jobs.items()
        if now - job.get("created", now) > 3600
    ]:
        _search_jobs.pop(stale_id, None)

    # Register the job immediately so clients can poll right away
    _search_jobs[job_id] = {
        "status": "pending",
        "result": None,
        "error": None,
        "created": now,
    }

    # Kick off the scrape in the background so the HTTP response returns
    # immediately (avoids Next.js dev proxy timeout on long scrapes).
    asyncio.create_task(
        _run_scrape_job(
            job_id=job_id,
            origin=origin,
            destination=destination,
            date=payload.outbound_date or "",
            return_date=payload.return_date,
            cabin=payload.cabin,
            adults=payload.adults,
            children=payload.children,
            infants_seat=payload.infants_seat,
            infants_lap=payload.infants_lap,
            currency=payload.currency,
            trip_type=payload.trip_type,
            legs=legs_dicts,
            max_results=None,  # No limit — return all available flights
        )
    )

    return {
        "job_id": job_id,
        "status": "pending",
        "message": "Flight search started. Poll GET /api/flights/search/{job_id} for results.",
        "origin": origin,
        "destination": destination,
    }


@router.get("/search/{job_id}")
async def get_flight_search_results(job_id: str) -> dict[str, Any]:
    """Poll for flight search results."""
    job = _search_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job["status"] == "pending":
        return {
            "status": "pending",
            "message": "Flight search still in progress. Poll again.",
            "job_id": job_id,
        }

    if job["status"] == "error":
        return {
            "status": "error",
            "message": job["error"] or "Flight search failed",
            "job_id": job_id,
            "flights": [],
            "count": 0,
        }

    # status == "done"
    return {
        "status": "done",
        **job["result"],
        "job_id": job_id,
    }


@router.get("/airports")
def airports(q: str = Query(default="")) -> dict[str, Any]:
    query = q.strip().lower()
    rows = [
        airport
        for airport in AIRPORTS
        if not query
        or query in airport["code"].lower()
        or query in airport["city"].lower()
        or query in airport["name"].lower()
    ]
    return {"airports": rows, "count": len(rows)}


@router.get("/{flight_id}")
def get_flight(flight_id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    flight = data_service.get_flight(session, flight_id)
    if not flight:
        raise HTTPException(status_code=404, detail="Flight not found")
    return flight