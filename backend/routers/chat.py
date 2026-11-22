"""Chat, streaming and guest session endpoints with production middleware."""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from backend.agent.travel_agent import SUGGESTIONS, TravelAgent
from backend.database.db import engine, get_session
from backend.database.models import GuestSession, Trip
from backend.services import data_service
from backend.services.chat_context import ChatContextManager
from backend.services.production_middleware import (
    error_response,
    validate_chat_request,
)

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    session_id: str = ""
    message: str = Field(min_length=1, max_length=4000)
    context: dict[str, Any] = Field(default_factory=dict)


class SessionResponse(BaseModel):
    session_id: str
    created_at: str


def _ensure_session(session: Session, session_id: str) -> str:
    if session_id:
        if session.get(GuestSession, session_id):
            return session_id
    new_id = session_id or f"guest_{uuid.uuid4().hex[:16]}"
    session.add(GuestSession(id=new_id, preferences={}))
    session.commit()
    return new_id


def _sse(event: str, payload: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"


@router.post("/session", response_model=SessionResponse)
def create_session(session: Session = Depends(get_session)) -> SessionResponse:
    session_id = _ensure_session(session, "")
    row = session.get(GuestSession, session_id)
    return SessionResponse(session_id=session_id, created_at=row.created_at if row else "")


@router.get("/suggestions")
def suggestions() -> dict[str, Any]:
    return {"suggestions": SUGGESTIONS}


@router.post("/stream")
async def stream_chat(request: ChatRequest, session: Session = Depends(get_session)) -> StreamingResponse:
    # Validate & sanitize input
    clean_message, clean_session_id, _redactions = validate_chat_request(
        request.message, request.session_id
    )
    session_id = _ensure_session(session, clean_session_id or request.session_id or "")
    data_service.save_chat_message(session, session_id, "user", clean_message)

    # Build enriched context
    ctx_mgr = ChatContextManager(session, session_id)
    enriched_context = await ctx_mgr.build_context(
        clean_message,
        context=request.context or {},
    )

    async def generator():
        # Dedicated sessions: the agent session is created inside the worker
        # thread, and persistence uses this generator's own session.
        from sqlmodel import Session as SQLSession

        yield _sse("status", {"text": "Concierge is searching authentic spots & preparing your travel plan..."})
        agent_context = {
            **request.context,
            "trip_id": enriched_context["trip_id"],
            "_chat_context": enriched_context,
        }

        def _run_agent_turn() -> dict[str, Any]:
            # Run the whole agent turn on a worker thread with its own event
            # loop and its own DB session. Scrapers (Playwright flights/places)
            # and legacy blocking tool handlers can no longer stall the SSE
            # event loop, and Chromium can still spawn subprocesses thanks to
            # the Proactor policy set at process start.
            with SQLSession(engine) as agent_db:
                agent = TravelAgent(agent_db, session_id)
                return asyncio.run(agent.respond(clean_message, agent_context))

        try:
            task = asyncio.create_task(asyncio.to_thread(_run_agent_turn))
            while True:
                done, _pending = await asyncio.wait({task}, timeout=10)
                if task in done:
                    reply = task.result()
                    break
                # Keep the connection alive (and the UI informed) while live
                # Google Flights / Google Maps scrapes run.
                yield _sse(
                    "status",
                    {"text": "Still working — verifying live flights, stays and map pins…"},
                )
        except Exception as exc:  # noqa: BLE001
            yield _sse("error", {"message": f"The concierge hit a snag: {exc}"})
            return

        yield _sse("meta", {"session_id": session_id, "provider": reply.get("provider", {}), "mode": reply.get("mode", "demo")})
        text = reply.get("message", "")
        for index in range(0, len(text), 22):
            yield _sse("token", {"text": text[index : index + 22]})
            await asyncio.sleep(0.012)
        yield _sse("cards", reply.get("cards", []))
        yield _sse("pins", reply.get("pins", []))
        if reply.get("trip"):
            yield _sse("trip", reply["trip"])
        if reply.get("suggestions"):
            yield _sse("suggestions", reply["suggestions"])
        if reply.get("tool_calls"):
            yield _sse("tools", reply["tool_calls"])

        with SQLSession(engine) as db:
            data_service.save_chat_message(
                db,
                session_id,
                "assistant",
                text,
                cards=reply.get("cards", []),
                pins=reply.get("pins", []),
            )
        yield _sse("done", {"session_id": session_id, "trip_id": reply.get("trip_id", "")})

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/message")
async def send_message(
    request: ChatRequest,
    raw_req: Request,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    # Validate & sanitize input
    clean_message, clean_session_id, _redactions = validate_chat_request(
        request.message, request.session_id
    )
    session_id = _ensure_session(session, clean_session_id or request.session_id or "")
    data_service.save_chat_message(session, session_id, "user", clean_message)

    # Build enriched context
    ctx_mgr = ChatContextManager(session, session_id)
    enriched_context = await ctx_mgr.build_context(
        clean_message,
        context=request.context or {},
    )

    agent_context = {
        **request.context,
        "trip_id": enriched_context["trip_id"],
        "_chat_context": enriched_context,
    }

    def _run_agent_turn() -> dict[str, Any]:
        from sqlmodel import Session as SQLSession

        with SQLSession(engine) as agent_db:
            agent = TravelAgent(agent_db, session_id)
            return asyncio.run(agent.respond(clean_message, agent_context))

    try:
        # Keep the API responsive while live scraping runs. A worker thread gets
        # its own Proactor loop so Playwright can launch Chromium.
        reply = await asyncio.wait_for(
            asyncio.to_thread(_run_agent_turn),
            timeout=240,
        )
    except asyncio.TimeoutError:
        return error_response(
            status_code=504,
            error_code="agent_timeout",
            message="The concierge took too long to respond. Please try again.",
            request_id=getattr(raw_req.state, "request_id", None),
        )
    except Exception as exc:  # noqa: BLE001
        return error_response(
            status_code=502,
            error_code="agent_error",
            message="The concierge hit a snag. Please try again.",
            request_id=getattr(raw_req.state, "request_id", None),
            detail=str(exc)[:200],
        )

    data_service.save_chat_message(
        session,
        session_id,
        "assistant",
        reply.get("message", ""),
        cards=reply.get("cards", []),
        pins=reply.get("pins", []),
    )
    reply["session_id"] = session_id
    reply["request_id"] = getattr(raw_req.state, "request_id", None)
    return reply


@router.get("/history")
@router.get("/history/{session_id}")
def history(session_id: str = "", session: Session = Depends(get_session)) -> dict[str, Any]:
    if not session_id:
        return {"session_id": "", "messages": []}
    return {"session_id": session_id, "messages": data_service.chat_history(session, session_id)}


@router.get("/trip/{trip_id}")
def trip_chat(trip_id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    trip = session.get(Trip, trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    session_id = trip.session_id or f"trip_{trip.id}"
    messages = data_service.chat_history(session, session_id)
    trip_dict = data_service.get_trip(session, trip_id)

    # Extract pins and cards so the chat map and card carousel display immediately
    pins: list[dict[str, Any]] = []
    cards: list[dict[str, Any]] = []
    pin_number = 0
    if trip_dict:
        if trip_dict.get("hotel") and trip_dict["hotel"].get("lat") and trip_dict["hotel"].get("lon"):
            h = trip_dict["hotel"]
            pins.append({
                "id": h["id"],
                "name": h["name"],
                "category": "hotel",
                "lat": h["lat"],
                "lon": h["lon"],
                "rating": h.get("rating"),
                "address": h.get("address"),
                "photo": (h.get("photos") or [""])[0],
                "label": "H",
                "trip_id": trip_id,
            })
            cards.append({
                "type": "hotel",
                "id": h["id"],
                "name": h["name"],
                "price": f"${h.get('price_per_night', 0)}/night",
                "rating": h.get("rating", 4.7),
                "image": (h.get("photos") or [""])[0],
            })

        for day in trip_dict.get("days", []):
            for stop in day.get("stops", []):
                p = stop.get("place")
                if p and p.get("lat") and p.get("lon"):
                    pin_number += 1
                    pins.append({
                        "id": p["id"],
                        "name": p["name"],
                        "category": p.get("category", "place"),
                        "lat": p["lat"],
                        "lon": p["lon"],
                        "rating": p.get("rating"),
                        "address": p.get("address"),
                        "photo": (p.get("photos") or [""])[0],
                        "day_index": day.get("day_index", 1),
                        "order": pin_number,
                        "label": str(pin_number),
                        "trip_id": trip_id,
                    })
                    cards.append({
                        "type": "place",
                        "id": p["id"],
                        "name": p["name"],
                        "category": p.get("category", "place"),
                        "destination": trip_dict.get("destination", ""),
                        "description": p.get("description", ""),
                        "image": (p.get("photos") or [""])[0],
                        "rating": p.get("rating"),
                        "address": p.get("address"),
                    })

    return {"session_id": session_id, "trip": trip_dict, "messages": messages, "pins": pins, "cards": cards}


@router.delete("/history/{session_id}")
def clear_history(session_id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    from backend.database.models import ChatMessage

    rows = session.exec(select(ChatMessage).where(ChatMessage.session_id == session_id)).all()
    for row in rows:
        session.delete(row)
    session.commit()
    return {"deleted": len(rows)}
