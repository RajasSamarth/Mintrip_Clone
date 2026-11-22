"""FastAPI entrypoint for the Mindtrip clone."""

from __future__ import annotations

import json
import logging
import sys
import time as _time
from collections import defaultdict as _defaultdict
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlmodel import Session

# Allow running as `python -m uvicorn main:app` from inside backend/ as well as
# `python -m uvicorn backend.main:app` from the project root.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend.config import get_settings
from backend.database.db import engine, init_db
from backend.database.seed import import_user_scrapers, seed_from_fixtures
from backend.routers import chat, eats, experiences, flights, hotels, places, trips
from backend.services.llm_service import LLMService
from backend.services.production_middleware import request_id_middleware

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("mindtrip")
settings = get_settings()


# --------------------------------------------------------------------------- #
# Rate limiting (Redis-backed when REDIS_URL is set, in-memory otherwise)
# --------------------------------------------------------------------------- #
_chat_request_log: _defaultdict[str, list[float]] = _defaultdict(list)


def _session_rate_limit_exceeded(session_id: str) -> bool:
    now = _time.time()
    window = settings.chat_rate_limit_rpm
    timestamps = _chat_request_log[session_id]
    _chat_request_log[session_id] = [t for t in timestamps if now - t < 60]
    if len(_chat_request_log[session_id]) >= settings.chat_rate_limit_rpm:
        return True
    _chat_request_log[session_id].append(now)
    return False


# --------------------------------------------------------------------------- #
# Circuit breaker registry (shared across services)
# --------------------------------------------------------------------------- #
_circuit_breakers: dict[str, dict[str, Any]] = {}


def get_breaker(name: str) -> dict[str, Any]:
    if name not in _circuit_breakers:
        _circuit_breakers[name] = {
            "failures": 0,
            "last_failure": None,
            "state": "closed",  # closed | open | half_open
        }
    return _circuit_breakers[name]


def breaker_call(name: str, func):
    """Execute func through a simple in-memory circuit breaker."""
    b = get_breaker(name)
    now = _time.time()
    if b["state"] == "open":
        if b["last_failure"] and (now - b["last_failure"]) > settings.circuit_breaker_recovery_timeout:
            b["state"] = "half_open"
            b["failures"] = 0
        else:
            raise RuntimeError(f"Circuit breaker '{name}' is OPEN")
    try:
        result = func()
    except Exception:
        b["failures"] += 1
        b["last_failure"] = now
        if b["failures"] >= settings.circuit_breaker_failure_threshold:
            b["state"] = "open"
        raise
    if b["state"] == "half_open":
        b["state"] = "closed"
        b["failures"] = 0
    return result


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
        if settings.auto_seed:
            with Session(engine) as session:
                counts = seed_from_fixtures(session, settings.fixtures_path)
                if any(counts.values()):
                    logger.info("Seeded fixtures: %s", counts)
                imported = import_user_scrapers(session, settings.user_scraper_dir)
                if imported.get("files"):
                    logger.info("Imported user scrapers: %s", imported)
    except Exception as exc:
        logger.warning("Database initialization or seeding warning: %s", exc)
    logger.info("Mindtrip API ready · LLM provider=%s live=%s", settings.llm_provider, LLMService().is_live)
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="AI travel concierge, visual itinerary planner, stays and flights — 100% free data sources.",
    lifespan=lifespan,
)

# Request ID middleware applied at app level (covers all routes)
@app.middleware("http")
async def _request_id_middleware(request: Request, call_next):
    return await request_id_middleware(request, call_next)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Per-session rate limiting for chat endpoints
@app.middleware("http")
async def _session_rate_limit_middleware(request: Request, call_next):
    if request.url.path.startswith(f"{settings.api_prefix}/chat"):
        session_id = (
            request.headers.get("x-session-id")
            or request.query_params.get("session_id")
            or (request.client.host if request.client else "anonymous")
        )
        if _session_rate_limit_exceeded(session_id):
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many messages. Please slow down and try again in a minute.",
                    "retry_after": 60,
                },
            )
    return await call_next(request)


app.include_router(chat.router, prefix=settings.api_prefix)
app.include_router(eats.router, prefix=settings.api_prefix)
app.include_router(experiences.router, prefix=settings.api_prefix)
app.include_router(trips.router, prefix=settings.api_prefix)
app.include_router(hotels.router, prefix=settings.api_prefix)
app.include_router(flights.router, prefix=settings.api_prefix)
app.include_router(places.router, prefix=settings.api_prefix)

# Fallback root endpoints without /api prefix
app.include_router(chat.router)
app.include_router(eats.router)
app.include_router(experiences.router)
app.include_router(trips.router)
app.include_router(hotels.router)
app.include_router(flights.router)
app.include_router(places.router)


@app.get("/")
def root() -> dict[str, Any]:
    return {
        "name": settings.app_name,
        "status": "ok",
        "docs": "/docs",
        "api": settings.api_prefix,
    }


@app.get("/health")
@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "environment": settings.environment}


@app.get("/config")
@app.get("/api/config")
def config() -> dict[str, Any]:
    return {
        "llm": LLMService().status(),
        "map": {
            "provider": "maplibre",
            "style": "osm-english-vector",
            "tiles": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
            "attribution": "© OpenStreetMap contributors",
        },
        "routing": {"provider": "OSRM", "live": settings.enable_live_routing},
        "features": {
            "guest_sessions": True,
            "sse_streaming": True,
            "scraper_adapters": True,
            "free_apis": ["nominatim", "overpass", "wikivoyage", "osrm", "unsplash"],
            "circuit_breaker": True,
            "redis_rate_limit": bool(settings.redis_url),
        },
    }


@app.get("/v1/models")
def v1_models() -> dict[str, Any]:
    return {
        "object": "list",
        "data": [
            {
                "id": settings.llm_model,
                "object": "model",
                "owned_by": "mindtrip",
            }
        ],
    }


# --------------------------------------------------------------------------- #
# Share & export endpoints
# --------------------------------------------------------------------------- #
@app.get("/api/trips/{trip_id}/share")
def share_trip(trip_id: str):
    """Return a shareable summary of a trip (no auth required)."""
    from backend.services import data_service
    from backend.database.db import Session as DBSession
    from sqlmodel import Session as DBSession2

    with DBSession2(engine) as session:
        trip = data_service.get_trip(session, trip_id)
        if not trip:
            return JSONResponse(status_code=404, content={"detail": "Trip not found"})
        return {
            "share_url": f"/trip/{trip_id}",
            "title": trip.get("title"),
            "destination": trip.get("destination"),
            "start_date": trip.get("start_date"),
            "end_date": trip.get("end_date"),
            "day_count": trip.get("day_count"),
            "stop_count": trip.get("stop_count"),
            "summary": trip.get("summary"),
            "cover_photo": trip.get("cover_photo"),
        }


@app.get("/api/trips/{trip_id}/export")
def export_trip(trip_id: str, format: str = "json"):
    """Export a trip as JSON or plain-text itinerary."""
    from backend.services import data_service
    from backend.database.db import Session as DBSession2

    with DBSession2(engine) as session:
        trip = data_service.get_trip(session, trip_id)
        if not trip:
            return JSONResponse(status_code=404, content={"detail": "Trip not found"})

    if format.lower() == "txt":
        lines = [
            f"Trip: {trip.get('title')}",
            f"Destination: {trip.get('destination')}",
            f"Dates: {trip.get('start_date')} to {trip.get('end_date')}",
            f"Travelers: {trip.get('traveler_type')}",
            f"Budget: ${trip.get('budget', 0):,.2f}",
            "",
            "Itinerary:",
        ]
        for day in trip.get("days", []):
            lines.append(f"  Day {day.get('day_index')} ({day.get('date')}): {day.get('title')}")
            lines.append(f"    {day.get('summary')}")
            for stop in day.get("stops", []):
                lines.append(f"    - {stop.get('arrival_time')} {stop.get('place', {}).get('name', 'Stop')} — {stop.get('notes', '')}")
                if stop.get("transit_info"):
                    lines.append(f"        Transit: {stop.get('transit_info')}")
        content = "\n".join(lines)
        return PlainTextResponse(content=content, media_type="text/plain")
    else:
        return JSONResponse(content=trip)
