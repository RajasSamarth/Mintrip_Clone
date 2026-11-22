"""The Mindtrip travel concierge agent.

Live providers get a real tool-calling loop. With no key (or if the provider
errors), the deterministic planner still produces a complete, persisted trip so
the split-screen UI always has something meaningful to show.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timedelta
from typing import Any

from sqlmodel import Session, select

from backend.agent.planner import (
    detect_origin,
    extract_destination_and_origin,
    get_spot_image,
    parse_budget,
    parse_dates_and_days,
    parse_days,
    parse_traveler,
    parse_traveler_and_passengers,
    resolve_destination,
    synthesize_trip,
    visuals_for_trip,
)
from backend.agent.conversation_memory import summarize_history
from backend.agent.intent import Intent, classify, INSTANT_REPLIES
from backend.agent.prompts import LOCAL_PLANNER_NOTE, SYSTEM_PROMPT
from backend.agent.tools import TOOL_SCHEMAS, ToolDispatcher
from backend.database.models import Flight, Hotel, Place, Trip, TripDay, TripStop
from backend.services import data_service
from backend.services.llm_service import LLMService

logger = logging.getLogger("mindtrip.agent")

DEFAULT_SUGGESTIONS = [
    "Plan a 3-day trip to Dubai with flight arriving at 14:00",
    "A romantic long weekend in Paris",
    "3 days in Kyoto temples & tea",
    "5 quiet days in the Swiss Alps",
]
SUGGESTIONS = DEFAULT_SUGGESTIONS


def dynamic_suggestions_for_dest(destination: str) -> list[str]:
    d = destination.title() if destination else "Dubai"
    return [
        f"🏨 Show boutique hotels under $180 in {d}",
        f"🍴 Swap Day 2 dinner to local cuisine",
        f"☕ Add a morning coffee stop on Day 1",
        f"✈️ Find flights to {d}",
    ]


# ---------------------------------------------------------------------- #
# Small helpers used by the concierge follow-up paths
# ---------------------------------------------------------------------- #
_GENERIC_NAME_TOKENS = {
    "the", "and", "of", "at", "to", "in", "on", "a", "an", "day",
    "add", "include", "put", "insert", "schedule", "for", "with", "my",
    "coffee", "cafe", "café", "restaurant", "specialty", "speciality",
    "house", "roasters", "roastery", "bar", "shop", "stop", "spot",
}


def _normalise_text(value: str) -> str:
    """Lowercase and collapse punctuation so names can be matched loosely."""
    value = (value or "").lower().replace("&", " and ")
    return re.sub(r"[^a-z0-9%]+", " ", value).strip()


def _distinctive_tokens(value: str) -> list[str]:
    return [tok for tok in _normalise_text(value).split() if len(tok) > 2 and tok not in _GENERIC_NAME_TOKENS]


def _match_requested_item(message: str, items: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the item whose name the user explicitly mentioned, if any."""
    text = _normalise_text(message)
    if not text:
        return None

    # Strongest signal: the complete name appears in the request.
    for item in items:
        name = _normalise_text(item.get("name") or item.get("title") or "")
        if name and name in text:
            return item

    # Otherwise require every distinctive token of a name to appear.
    best: tuple[int, dict[str, Any]] | None = None
    for item in items:
        tokens = _distinctive_tokens(item.get("name") or item.get("title") or "")
        if not tokens:
            continue
        if all(tok in text for tok in tokens):
            score = len(tokens)
            if best is None or score > best[0]:
                best = (score, item)
    return best[1] if best else None


DAYS_OF_WEEK = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def _resolve_target_day_and_slot(
    message: str,
    trip_days: list[dict[str, Any]],
    trip_start_date: str = "",
    default_day: int = 1,
    category: str = "",
) -> tuple[int | None, str, str, str | None]:
    """Parse day index, date label, and time slot from user message.

    Handles:
    - Explicit day numbers: 'day 4', 'day four', 'fourth day'
    - Day of the week: 'saturday', 'saturday night', 'on sunday', 'friday evening', etc.
    - Time of day: 'night', 'tonight', 'evening', 'morning', 'afternoon'

    Returns:
        (day_num, time_slot, day_label, dow_not_in_trip)
        e.g. (4, "evening", "Day 4 (Saturday, Dec 19)", None)
        or (None, "evening", "", "saturday") if user asked for Saturday but trip has no Saturday
    """
    lowered = message.lower()
    day_num = None
    dow_not_in_trip = None

    # 1. Check numeric day (e.g. "day 4")
    day_match = re.search(r"\bday\s*(\d+)\b", lowered)
    if day_match:
        day_num = int(day_match.group(1))
    else:
        word_to_num = {
            "one": 1, "first": 1, "two": 2, "second": 2, "three": 3, "third": 3,
            "four": 4, "fourth": 4, "five": 5, "fifth": 5, "six": 6, "sixth": 6,
            "seven": 7, "seventh": 7, "eight": 8, "eighth": 8, "nine": 9, "ninth": 9,
            "ten": 10, "tenth": 10,
        }
        for word, num in word_to_num.items():
            if f"day {word}" in lowered or f"{word} day" in lowered:
                day_num = num
                break

    # 2. Check day of the week (e.g. "saturday", "saturday night", "on sunday")
    if day_num is None:
        matched_dow = None
        for dow in DAYS_OF_WEEK:
            if re.search(rf"\b{dow}\b", lowered):
                matched_dow = dow
                break

        if matched_dow:
            dow_not_in_trip = matched_dow
            # Check existing trip_days ONLY!
            for d in (trip_days or []):
                d_date = d.get("date")
                if not d_date and trip_start_date:
                    try:
                        s_dt = datetime.fromisoformat(trip_start_date)
                        d_dt = s_dt + timedelta(days=d.get("day_index", 1) - 1)
                        d_date = d_dt.strftime("%Y-%m-%d")
                    except Exception:
                        d_date = None

                if d_date:
                    try:
                        dt = datetime.fromisoformat(d_date)
                        if dt.strftime("%A").lower() == matched_dow:
                            day_num = d.get("day_index", 1)
                            dow_not_in_trip = None
                            break
                    except Exception:
                        pass

    if day_num is None and not dow_not_in_trip:
        day_num = default_day

    # 3. Time slot parsing
    time_slot = "afternoon"
    if any(w in lowered for w in ("night", "tonight", "evening", "dinner", "drinks", "cocktail", "sunset", "late night", "supper")):
        time_slot = "evening"
    elif any(w in lowered for w in ("morning", "breakfast", "brunch", "coffee", "sunrise", "early morning")):
        time_slot = "morning"
    elif any(w in lowered for w in ("afternoon", "lunch", "midday", "noon", "tea")):
        time_slot = "afternoon"
    elif category in ("bar", "club"):
        time_slot = "evening"
    elif category == "cafe":
        time_slot = "morning"

    # 4. Form friendly day label with date if available
    day_label = f"Day {day_num}" if day_num else ""
    if day_num:
        target_day_view = next((d for d in trip_days if d.get("day_index") == day_num), None)
        d_date_str = target_day_view.get("date") if target_day_view else None
        if not d_date_str and trip_start_date:
            try:
                s_dt = datetime.fromisoformat(trip_start_date)
                d_dt = s_dt + timedelta(days=day_num - 1)
                d_date_str = d_dt.strftime("%Y-%m-%d")
            except Exception:
                pass

        if d_date_str:
            try:
                dt = datetime.fromisoformat(d_date_str)
                day_label = f"Day {day_num} ({dt.strftime('%A, %b %d')})"
            except Exception:
                pass

    return day_num, time_slot, day_label, dow_not_in_trip


def _extract_unrecognized_spot_name(message: str) -> str | None:
    text = message.strip()
    # Pattern: [Spot Name] add this (in/to/for)...
    m1 = re.search(r"^(.*?)[,\s]+(?:add this|please add this|add it|put this|add to|add into)\b", text, re.IGNORECASE)
    if m1 and len(m1.group(1).strip()) > 2:
        return m1.group(1).strip()

    # Pattern: add [Spot Name] to/in/on/for...
    m2 = re.search(r"\b(?:add|include|put|schedule|insert)\s+(?:the\s+|a\s+|an\s+)?(.*?)\s+(?:to|in|into|on|for|at)\b", text, re.IGNORECASE)
    if m2 and len(m2.group(1).strip()) > 2:
        cand = m2.group(1).strip()
        if cand.lower() not in {"this", "it", "one", "spot", "place", "stop", "hotel"}:
            return cand
    return None


def _hotel_price_usd(hotel: dict[str, Any]) -> float | None:
    price = hotel.get("price_per_night")
    if price is None or hotel.get("price_unavailable"):
        return None
    currency = (hotel.get("currency") or "INR").upper()
    try:
        amount = float(price)
    except (TypeError, ValueError):
        return None
    if amount <= 0:
        return None
    return amount / 85.0 if currency == "INR" else amount


def _hotel_price_label(hotel: dict[str, Any]) -> str:
    price = hotel.get("price_per_night")
    if price is None or hotel.get("price_unavailable"):
        return "Check rates"
    currency = (hotel.get("currency") or "INR").upper()
    try:
        amount = float(price)
    except (TypeError, ValueError):
        return "Check rates"
    if currency == "INR":
        return f"₹{int(round(amount)):,}/night"
    return f"${int(round(amount)):,}/night"


def _hotel_card(hotel: dict[str, Any]) -> dict[str, Any]:
    """Build a hotel card the frontend can render without losing its currency."""
    price = hotel.get("price_per_night")
    currency = (hotel.get("currency") or "INR").upper()
    card: dict[str, Any] = {
        "type": "hotel",
        "id": hotel.get("id", ""),
        "name": hotel.get("name", "Stay"),
        "stars": hotel.get("stars", 0),
        "rating": hotel.get("rating", 4.7),
        "address": hotel.get("address", ""),
        "description": hotel.get("description", ""),
        "destination": hotel.get("destination", ""),
        "image": (hotel.get("photos") or [""])[0],
        "booking_url": hotel.get("booking_url", ""),
        "price": _hotel_price_label(hotel),
        "price_per_night": price,
        "currency": currency,
    }
    if price is not None and not hotel.get("price_unavailable"):
        if currency == "INR":
            card["price_inr"] = price
        else:
            card["price_usd"] = price
    return card


def _place_card(
    place: dict[str, Any],
    fallback_category: str,
    *,
    day_index: int | None = None,
    is_added: bool = False,
) -> dict[str, Any]:
    # Prefer real scraped photos from Google Maps; fall back to static only
    # when no photos exist at all.
    place_photos = place.get("photos") or []
    real_photos = [
        p for p in place_photos
        if p and ("googleusercontent" in p or "maps.googleapis" in p)
    ]
    card_image = (
        real_photos[0]
        if real_photos
        else (place_photos[0] if place_photos else "")
        or get_spot_image(place.get("name", "Place"), place.get("category", fallback_category), place.get("destination", ""), 0)
    )
    card: dict[str, Any] = {
        "type": "place",
        "id": place.get("id", ""),
        "name": place.get("name", "Place"),
        "category": place.get("category", fallback_category),
        "destination": place.get("destination", ""),
        "rating": place.get("rating", 4.8),
        "price": place.get("price_level", "$$"),
        "image": card_image,
        "photos": place_photos,
        "description": place.get("description", ""),
        "address": place.get("address", ""),
    }
    if day_index is not None:
        card["day_index"] = day_index
    if is_added:
        card["is_added"] = True
    return card


def _places_near_coords(
    places: list[dict[str, Any]],
    lat: float,
    lon: float,
    radius_km: float = 3.0,
) -> list[dict[str, Any]]:
    """Return places within radius_km of the given lat/lon using Haversine distance."""
    import math

    def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        R = 6371.0  # Earth radius in km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
        )
        return 2 * R * math.asin(math.sqrt(a))

    near: list[dict[str, Any]] = []
    for p in places:
        plat = p.get("lat")
        plon = p.get("lon")
        if plat is None or plon is None:
            continue
        try:
            d = haversine(lat, lon, float(plat), float(plon))
        except (TypeError, ValueError):
            continue
        if d <= radius_km:
            near.append(p)
    return near


CITY_TO_AIRPORT: dict[str, str] = {
    "new york": "JFK",
    "new-york": "JFK",
    "nyc": "JFK",
    "dubai": "DXB",
    "paris": "CDG",
    "rome": "FCO",
    "kyoto": "KIX",
    "tokyo": "HND",
    "swiss alps": "ZRH",
    "zürich": "ZRH",
    "zurich": "ZRH",
    "london": "LHR",
    "barcelona": "BCN",
    "singapore": "SIN",
    "bangkok": "BKK",
    "delhi": "DEL",
    "mumbai": "BOM",
    "bangalore": "BLR",
    "hyderabad": "HYD",
    "chennai": "MAA",
    "kolkata": "CCU",
    "goa": "GOI",
    "san francisco": "SFO",
    "los angeles": "LAX",
    "chicago": "ORD",
    "miami": "MIA",
    "seattle": "SEA",
    "boston": "BOS",
    "frankfurt": "FRA",
    "amsterdam": "AMS",
}


def is_off_topic_query(message: str) -> bool:
    """Guardrail to detect non-travel queries (sports/IPL, politics, coding, homework, general trivia)."""
    lowered = message.lower().strip()
    if not lowered:
        return False

    travel_signals = (
        "trip", "travel", "flight", "flights", "hotel", "hotels", "stay", "stays", "resort",
        "itinerary", "vacation", "holiday", "tour", "tourist", "pack", "passport", "visa",
        "airport", "airline", "airlines", "visiting", "sightseeing", "attraction", "destination",
        "booking", "day 1", "day 2", "day 3", "day 4", "day 5", "day 6", "day 7", "day 8",
        "day 9", "day 10", "places to visit"
    )
    has_travel_signal = any(sig in lowered for sig in travel_signals)

    sports_triggers = (
        "ipl", "cricket", "csk", "rcb", "mumbai indians", "chennai super kings", "gujarat titans",
        "kolkata knight riders", "world cup", "champions trophy", "fifa", "premier league", "epl",
        "la liga", "messi", "ronaldo", "virat kohli", "dhoni", "super bowl", "nba", "nfl",
        "formula 1", "f1 race", "who won last year", "who won the match", "match score",
        "who won ipl", "who won the league", "won the championship", "won the cup", "won ipl"
    )
    politics_triggers = (
        "who is the prime minister", "who is the president", "election results", "parliament",
        "congress party", "bjp", "democrat", "republican", "who is the pm", "vote for",
        "political party"
    )
    code_and_math_triggers = (
        "write python", "write a python", "write code", "write a code", "write a script",
        "javascript code", "fix this code", "debug code", "leetcode", "solve equation",
        "write an essay", "do my homework", "solve 2x", "solve math", "algorithm"
    )
    general_non_travel_triggers = (
        "bitcoin price", "crypto price", "ethereum price", "stock market tips",
        "invest in crypto", "forex trading", "who won the war", "tell me a joke"
    )

    all_off_topic_triggers = (
        sports_triggers + politics_triggers + code_and_math_triggers + general_non_travel_triggers
    )

    for trig in all_off_topic_triggers:
        if trig in lowered:
            if has_travel_signal and any(k in lowered for k in ("flight", "hotel", "itinerary", "trip to", "pack for")):
                return False
            return True

    if (lowered.startswith("who won") or lowered.startswith("what is the score") or lowered.startswith("who is the champion")) and not has_travel_signal:
        return True

    return False


_TRIP_INTENT_RE = re.compile(
    r"\b(?:plan|planning|trip|itinerary|travel|vacation|holiday|days?|nights?|"
    r"weekend|getaway|visit|visiting|explore|flights?|hotels?|staying|tour|"
    r"city break)\b",
    re.IGNORECASE,
)


def looks_like_trip_request(message: str) -> bool:
    """Heuristic: is the user asking us to plan or change travel?

    Used to avoid turning greetings and general questions into a full live-
    scraped trip when the LLM replies conversationally without a tool call.
    """
    text = (message or "").strip()
    if not text:
        return False
    if _TRIP_INTENT_RE.search(text):
        return True
    return bool(extract_destination_and_origin(text).get("destination"))


def is_open_trip_planning_intent(message: str, session: Session | None = None) -> bool:
    lowered = message.lower().strip()
    extracted = extract_destination_and_origin(message)
    if extracted.get("destination"):
        return False

    known_destinations = {
        "new york", "new-york", "nyc", "dubai", "paris", "kyoto", "rome",
        "swiss alps", "tokyo", "london", "barcelona", "singapore", "bangkok",
        "delhi", "mumbai", "bangalore", "berlin", "amsterdam", "venice",
        "florence", "madrid", "switzerland"
    }
    if any(city in lowered for city in known_destinations):
        return False

    if session is not None:
        try:
            from backend.database.models import Destination
            # Only match if a database destination's name is explicitly mentioned in lowered
            all_dests = session.exec(select(Destination)).all()
            for d in all_dests:
                d_name = d.name.lower()
                d_id = d.id.lower().replace("-", " ")
                if (len(d_name) > 3 and d_name in lowered) or (len(d_id) > 3 and d_id in lowered):
                    return False
        except Exception:
            pass

    intake_patterns = [
        "plan a trip", "plan my trip", "help me plan a trip", "help me plan",
        "i want to plan a trip", "i want to plan a vacation", "plan a vacation",
        "plan my vacation", "plan a journey", "let's plan a trip", "start planning",
        "create a trip", "create a plan", "make a trip", "plan itinerary",
    ]
    return any(p in lowered for p in intake_patterns) or lowered in {"plan", "travel", "vacation", "trip"}


def is_underspecified_trip_inquiry(
    message: str,
    session: Session | None = None,
    context: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    context = context or {}
    lowered = message.lower().strip()

    # If there is already an active trip being discussed in this context, do not intercept
    trip_id = context.get("trip_id")
    if trip_id:
        return False, ""

    # Check if this is an explicit action command on existing stops/hotels/flights
    if any(w in lowered for w in ("flight", "airline", "hotel", "stay", "room", "rent a car", "car rental", "salon", "saloon", "coffee", "restaurant", "add ", "remove ", "delete ", "swap ")):
        return False, ""

    # Check if timing is already specified: either explicit calendar dates or a
    # stated duration (e.g. "5-day", "3 days", "a week"). A duration fixes the
    # trip length without assuming specific calendar dates.
    dates_info = parse_dates_and_days(message)
    has_dates = bool(dates_info.get("start_date") and dates_info.get("end_date"))
    has_duration = bool(
        dates_info.get("days")
        or re.search(r"\b(\d+)\s*(?:-|\s)?\s*days?\b", lowered)
        or re.search(r"\b(\d+)\s*(?:-|\s)?\s*nights?\b", lowered)
        or "weekend" in lowered
        or "week" in lowered
    )
    has_timing = has_dates or has_duration

    # Check if travelers are already explicitly specified
    has_travelers = bool(
        re.search(r"\b(\d+)\s*(?:adults?|travelers?|travellers?|people|persons?|pax|passengers?)\b", lowered)
        or any(w in lowered for w in ("couple", "honeymoon", "family", "solo", "alone", "partner", "partners", "with kids", "with my wife", "with my husband", "with children"))
    )

    # If timing and travelers are both specified, the trip is buildable without
    # assuming specific calendar dates (the planner defaults the start date).
    if has_timing and has_travelers:
        return False, ""

    # Identify destination
    extracted = extract_destination_and_origin(message)
    dest = extracted.get("destination") or ""

    if not dest:
        known_destinations = [
            "swiss alps", "new york", "dubai", "paris", "kyoto", "rome",
            "tokyo", "london", "barcelona", "singapore", "bangkok",
            "delhi", "mumbai", "bangalore", "berlin", "amsterdam", "venice",
            "florence", "madrid", "switzerland", "bali", "maldives", "iceland",
            "santorini", "alps"
        ]
        for kd in known_destinations:
            if kd in lowered:
                dest = kd
                break

    if not dest and session:
        try:
            from backend.database.models import Destination
            all_dests = session.exec(select(Destination)).all()
            for d in all_dests:
                if len(d.name) > 3 and d.name.lower() in lowered:
                    dest = d.name
                    break
        except Exception:
            pass

    if dest:
        # Destination is detected, but either timing (dates/duration) or travelers (or both) are missing.
        # "quiet days in the Swiss Alps" (no timing, no travelers) still triggers intake.
        if not has_timing or not has_travelers:
            return True, dest

    return False, ""


def _flight_card(flight: Any, pax: int = 1) -> dict[str, Any]:
    """Build a rich flight card the frontend FlightCard component can render."""
    if isinstance(flight, dict):
        f_id = flight.get("id", "")
        airline = flight.get("airline", "Airline")
        airline_code = flight.get("airline_code", "")
        flight_num = flight.get("flight_number", "")
        origin = flight.get("origin", "")
        destination = flight.get("destination", "")
        dep_time = flight.get("departure_time", "")
        arr_time = flight.get("arrival_time", "")
        duration_mins = flight.get("duration_minutes", 0)
        stops = flight.get("stops", 0)
        price_usd = float(flight.get("price_usd", 0) or 0)
        cabin = flight.get("cabin", "Economy")
        baggage = flight.get("baggage", "1 carry-on, 1 checked bag included")
        booking_url = flight.get("booking_url", "")
        meta = flight.get("metadata_json") or flight.get("metadata") or {}
    else:
        f_id = flight.id
        airline = flight.airline
        airline_code = flight.airline_code
        flight_num = flight.flight_number
        origin = flight.origin
        destination = flight.destination
        dep_time = flight.departure_time
        arr_time = flight.arrival_time
        duration_mins = flight.duration_minutes
        stops = flight.stops
        price_usd = float(flight.price_usd or 0)
        cabin = flight.cabin
        baggage = flight.baggage
        booking_url = flight.booking_url
        meta = getattr(flight, "metadata_json", None) or getattr(flight, "metadata", None) or {}

    dur_h = duration_mins // 60
    dur_m = duration_mins % 60
    dep_clean = dep_time.split("T")[-1][:5] if "T" in str(dep_time) else str(dep_time)[:5]
    arr_clean = arr_time.split("T")[-1][:5] if "T" in str(arr_time) else str(arr_time)[:5]

    per_pax_usd = meta.get("price_per_person_usd") or round(price_usd / max(1, pax), 2)
    per_pax_inr = meta.get("price_per_person_inr") or round(per_pax_usd * 85.0, 2)
    total_inr = meta.get("total_price_inr") or round(price_usd * 85.0, 2)
    return_flight = meta.get("return_flight")

    return {
        "type": "flight",
        "id": f_id,
        "airline": airline,
        "airline_code": airline_code,
        "flight_number": flight_num,
        "origin": origin,
        "destination": destination,
        "departure_time": dep_clean,
        "arrival_time": arr_clean,
        "duration": f"{dur_h}h {dur_m}m",
        "duration_minutes": duration_mins,
        "stops": stops,
        "price_usd": price_usd,
        "price_inr": total_inr,
        "cabin": cabin,
        "baggage": baggage or "1 carry-on, 1 checked bag included",
        "booking_url": booking_url or f"https://www.google.com/travel/flights?q=flights+from+{origin}+to+{destination}",
        "passengers": pax,
        "price_per_person_usd": per_pax_usd,
        "price_per_person_inr": per_pax_inr,
        "return_flight": return_flight,
    }


class TravelAgent:
    def __init__(self, session: Session, session_id: str, llm: LLMService | None = None) -> None:
        self.session = session
        self.session_id = session_id
        self.llm = llm or LLMService()

    async def _compose_concierge_response(
        self,
        user_message: str,
        action_summary: str,
        items: list[dict[str, Any]] | None = None,
        active_trip: dict[str, Any] | None = None,
        fallback_text: str = "",
    ) -> str:
        """Formulate a knowledgeable, authentic AI concierge narrative using LLM if live."""
        if not self.llm.is_live:
            return fallback_text

        items = items or []
        items_summary = []
        for it in items[:4]:
            name = it.get("name") or it.get("title") or "Spot"
            rating = it.get("rating", "")
            cat = it.get("category", "")
            desc = it.get("description", "")
            addr = it.get("address", "")
            items_summary.append(f"- **{name}** ({cat}, rating {rating}): {desc} ({addr})")

        items_str = "\n".join(items_summary) if items_summary else "None"
        dest = (active_trip.get("destination") or "").title() if active_trip else ""
        days = active_trip.get("day_count") or (len(active_trip.get("days", [])) if active_trip else 0)

        prompt = (
            f"You are Mindtrip's expert AI travel concierge assisting a discerning traveler.\n\n"
            f"TRIP CONTEXT:\n"
            f"- Destination: {dest}\n"
            f"- Total Days: {days}\n"
            f"- Action / Recommendation: {action_summary}\n"
            f"- Featured Places:\n{items_str}\n\n"
            f"TRAVELER'S REQUEST:\n\"{user_message}\"\n\n"
            f"MANDATORY INSTRUCTIONS:\n"
            f"1. Acknowledge the traveler's specific request and clearly explain what has been adjusted or recommended.\n"
            f"2. Provide genuine concierge insights about the featured places (signature highlights, vibe, best timing, or culinary specialties).\n"
            f"3. Keep your response to 2 engaging, concise paragraphs in elegant markdown.\n"
            f"4. End with an inviting follow-up question offering to tailor the schedule, swap venues, or reserve a table.\n"
            f"5. Do NOT output raw IDs or JSON."
        )

        try:
            res = await self.llm.complete([{"role": "user", "content": prompt}])
            content = (res.content or "").strip()
            if content and len(content) > 35:
                return content
        except Exception as exc:
            logger.warning("LLM concierge narrative generation failed (%s); using fallback", exc)

        return fallback_text

    async def respond(self, message: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        context = context or {}

        # 1. Guardrail against off-topic queries (sports/IPL, politics, coding, non-travel trivia)
        if is_off_topic_query(message):
            return self._off_topic_response(message, context)

        # 2. Lightweight intent classifier — instant local replies for non-planning intents
        #    (zero Groq tokens spent on greetings, goodbyes, thanks, help).
        intent = classify(message)
        if intent in INSTANT_REPLIES:
            return self._instant_reply(intent, context)

        # 3. Check open trip planning intake (e.g. "plan a trip" without details)
        if is_open_trip_planning_intent(message, self.session):
            return self._intake_response(message, context)

        # 3. Check follow-ups (flights, hotels, spot changes, cafes, activities)
        followup = await self._followup(message, context)
        if followup:
            return followup

        # 4. Check underspecified destination inquiry (e.g. "quiet days in the Swiss Alps" without dates/travelers)
        is_under, under_dest = is_underspecified_trip_inquiry(message, self.session, context)
        if is_under:
            return self._destination_intake_response(under_dest, message, context)

        if self.llm.is_live:
            try:
                # Cap the total live-LLM time so a slow/hung provider (e.g. Groq)
                # never blocks the chat stream indefinitely. Falls back to the
                # deterministic local planner, which always returns a full trip.
                total_timeout = float(getattr(self.llm.settings, "llm_timeout_seconds", 45) * 3)
                return await asyncio.wait_for(
                    self._live_response(message, context), timeout=total_timeout
                )
            except asyncio.TimeoutError:
                logger.warning("Live LLM timed out after %ss; using local planner", total_timeout)
            except Exception as exc:  # noqa: BLE001 - fall back, never fail the chat
                logger.warning("Live LLM failed (%s); using local planner", exc)

        return self._local_response(message, context)

    def _off_topic_response(self, message: str, context: dict[str, Any]) -> dict[str, Any]:
        trip_id = context.get("trip_id") or ""
        active_trip = None
        if not trip_id:
            stmt = select(Trip).where(Trip.session_id == self.session_id).order_by(Trip.updated_at.desc())
            row = self.session.exec(stmt).first()
            if row:
                trip_id = row.id
        if trip_id:
            active_trip = data_service.get_trip(self.session, trip_id)

        dest_name = (active_trip.get("destination") or "").title() if active_trip else "your dream destination"

        return {
            "message": (
                "I am Mindtrip's AI travel concierge, dedicated exclusively to curating bespoke travel itineraries, "
                "verifying flights, finding charming stays, and designing unforgettable journeys across the globe. ✨\n\n"
                "While I can't assist with sports trivia, politics, or general non-travel questions, I would love to help "
                f"you plan your next getaway! We can explore boutique stays, verify flights, or customize daily routes for {dest_name}.\n\n"
                "*Where are you dreaming of travelling next?*"
            ),
            "cards": [],
            "pins": visuals_for_trip(self.session, active_trip)["pins"] if active_trip else [],
            "trip": active_trip,
            "trip_id": trip_id or (active_trip["id"] if active_trip else None),
            "provider": self.llm.status(),
            "mode": "concierge_guardrail",
            "tool_calls": [],
            "suggestions": [
                "Plan a 9-day trip from Delhi to New York",
                "Show boutique hotels in Dubai",
                "Explore 3-day itinerary in Paris",
                "Find non-stop flights to Tokyo",
            ],
            "note": "",
        }

    def _instant_reply(self, intent: Intent, context: dict[str, Any]) -> dict[str, Any]:
        """Zero-token instant reply for greetings, goodbyes, thanks, help."""
        trip_id = context.get("trip_id") or ""
        active_trip = None
        if not trip_id:
            stmt = select(Trip).where(Trip.session_id == self.session_id).order_by(Trip.updated_at.desc())
            row = self.session.exec(stmt).first()
            if row:
                trip_id = row.id
        if trip_id:
            active_trip = data_service.get_trip(self.session, trip_id)

        pins = visuals_for_trip(self.session, active_trip)["pins"] if active_trip else []

        return {
            "message": INSTANT_REPLIES[intent],
            "cards": [],
            "pins": pins,
            "trip": active_trip,
            "trip_id": trip_id or (active_trip["id"] if active_trip else None),
            "provider": self.llm.status(),
            "mode": "instant_reply",
            "tool_calls": [],
            "suggestions": [
                "Plan a 5-day trip to Kyoto",
                "A romantic weekend in Paris",
                "3 days in the Swiss Alps",
                "Boutique hotels in Dubai",
            ],
            "note": "",
        }

    def _intake_response(self, message: str, context: dict[str, Any]) -> dict[str, Any]:
        return {
            "message": (
                "### 🌍 Let's Design Your Perfect Journey\n\n"
                "To curate an authentic, bespoke itinerary complete with realistic flight schedules, hand-picked boutique stays, and seamless day-by-day map routing, please share your trip details below:\n\n"
                "1. **Destination**: Where in the world would you love to travel? *(e.g., New York, Dubai, Paris, Kyoto, Swiss Alps, Rome)*\n"
                "2. **Departure City / Hub**: Where will you be flying from? *(e.g., Delhi, Mumbai, London, San Francisco)*\n"
                "3. **Dates & Duration**: What are your target dates or how many days would you like to spend?\n"
                "4. **Travelers**: How many adults and children are travelling?\n"
                "5. **Travel Style & Vibe**: Slow travel, luxury & wellness, culinary exploration, cultural deep-dive, or iconic fast-paced highlights?\n\n"
                "*You can fill out the interactive card below or simply type your details in the chat.*"
            ),
            "cards": [
                {
                    "type": "trip_intake",
                    "title": "Design Your Complete Journey",
                    "description": "Fill in your travel preferences to generate day-by-day stops, verified flights, and curated boutique hotels.",
                    "destinations": ["New York", "Dubai", "Paris", "Kyoto", "Rome", "Swiss Alps"],
                    "default_origin": "Delhi",
                    "default_adults": 2,
                }
            ],
            "pins": [],
            "trip": None,
            "trip_id": None,
            "provider": self.llm.status(),
            "mode": "intake",
            "tool_calls": [],
            "suggestions": [
                "Plan a 9-day trip from Delhi to New York for 3 adults",
                "Plan a 5-day luxury trip to Dubai for 2 adults",
                "Plan a 4-day slow travel trip to Paris for a couple",
                "Plan a 6-day cultural trip to Kyoto",
            ],
            "note": "",
        }

    def _destination_intake_response(self, dest: str, message: str, context: dict[str, Any]) -> dict[str, Any]:
        dest_title = dest.title()
        if dest.lower() in ("swiss alps", "alps", "switzerland"):
            dest_display = "the Swiss Alps"
            emoji = "🏔️"
            intro = "The Swiss Alps offer breathtaking alpine panoramas, serene valleys, crystal mountain lakes, and historic chalets."
        elif dest.lower() in ("paris", "france"):
            dest_display = "Paris"
            emoji = "✨"
            intro = "Paris charms with its iconic boulevards, quiet neighborhood bistros, world-class art collections, and romantic river walks."
        elif dest.lower() in ("tokyo", "japan"):
            dest_display = "Tokyo"
            emoji = "⛩️"
            intro = "Tokyo seamlessly balances centuries-old shrines and tranquil gardens with vibrant modern food and design scenes."
        elif dest.lower() in ("dubai", "uae"):
            dest_display = "Dubai"
            emoji = "🌴"
            intro = "Dubai is renowned for its architectural marvels, desert retreats, world-class dining, and golden beaches."
        elif dest.lower() in ("kyoto",):
            dest_display = "Kyoto"
            emoji = "🍵"
            intro = "Kyoto offers serene zen gardens, historic wooden machiya, bamboo groves, and timeless tea ceremonies."
        else:
            dest_display = dest_title
            emoji = "🌍"
            intro = f"{dest_title} is a remarkable destination with rich culture, scenic vistas, and unforgettable local spots."

        # Extract whatever details the user already provided so we can prefill the card
        extracted = extract_destination_and_origin(message)
        origin_hint = extracted.get("origin") or detect_origin(message) or ""
        pax_label, pax_count = parse_traveler_and_passengers(message)
        date_info = parse_dates_and_days(message)

        return {
            "message": (
                f"### {emoji} Let's Design Your Escape to **{dest_display}**\n\n"
                f"{intro} To curate your bespoke itinerary complete with realistic flight options, verified boutique stays, and personalized day-by-day routing without making assumptions, please share:\n\n"
                "1. 📅 **Travel Dates & Duration**: What are your target dates (or preferred month), and how many days would you like to stay?\n"
                "2. 👥 **Number of Travelers**: How many adults and children will be traveling?\n"
                "3. 🛫 **Departure City / Hub**: Where will you be flying or departing from? *(e.g., Delhi, Mumbai, London, Zurich, New York)*\n\n"
                f"*Once you provide your dates and party size, I'll generate your complete day-by-day {dest_display} itinerary!*"
            ),
            "cards": [
                {
                    "type": "trip_intake",
                    "title": f"Plan Your {dest_display} Journey",
                    "description": f"Tell us your travel dates, departure hub, and party size to build your custom {dest_display} itinerary.",
                    "destination": dest_display,
                    "destinations": ["Swiss Alps", "New York", "Dubai", "Paris", "Kyoto", "Rome"],
                    "default_origin": origin_hint,
                    "default_adults": pax_count,
                    "default_start_date": date_info.get("start_date", ""),
                    "default_end_date": date_info.get("end_date", ""),
                }
            ],
            "pins": [],
            "trip": None,
            "trip_id": None,
            "provider": self.llm.status(),
            "mode": "intake",
            "tool_calls": [],
            "suggestions": [
                f"5 days in {dest_display} for 2 adults in October",
                f"7 days in {dest_display} for a family in December",
                f"4 days solo retreat in {dest_display} departing from London",
            ],
            "note": "",
        }

    # ------------------------------------------------------------------ #
    # Local (zero-key) path
    # ------------------------------------------------------------------ #
    def _local_response(self, message: str, context: dict[str, Any]) -> dict[str, Any]:
        trip_id = context.get("trip_id") or ""
        if not trip_id:
            stmt = select(Trip).where(Trip.session_id == self.session_id).order_by(Trip.updated_at.desc())
            row = self.session.exec(stmt).first()
            if row:
                trip_id = row.id

        is_new_trip = any(
            w in message.lower()
            for w in (
                "plan a", "plan trip", "complete trip", "start a", "create a",
                "build a", "trip to", "trip from", "new trip", "itinerary for"
            )
        )

        if trip_id and not is_new_trip:
            existing = data_service.get_trip(self.session, trip_id)
            if existing:
                visuals = visuals_for_trip(self.session, existing)
                dest = (existing.get("destination") or "").title()
                hotel_name = existing.get("hotel", {}).get("name") if existing.get("hotel") else dest
                lowered_msg = message.lower()

                # Pull enriched context if available (history-aware local path)
                ctx = context.get("_chat_context") or {}
                recent_history = ctx.get("recent_history", [])
                summary = ctx.get("summary", "")

                # Build a compact history string for contextual replies
                history_lines = []
                for turn in recent_history[-6:]:
                    sender = turn.get("sender", "unknown")
                    content = turn.get("message", "")[:150]
                    history_lines.append(f"{sender}: {content}")
                history_str = "\n".join(history_lines) if history_lines else "No prior turns."

                # Day-specific query: "what's on Day 3?", "tell me about Day 2"
                day_match = re.search(r"\bday\s*(\d+)\b", lowered_msg)
                if day_match:
                    day_num = int(day_match.group(1))
                    day_data = next(
                        (d for d in existing.get("days", []) if d.get("day_index") == day_num),
                        None,
                    )
                    if day_data:
                        lines = []
                        for s in day_data.get("stops", []):
                            p = s.get("place", {}) or {}
                            name = p.get("name") or s.get("notes") or "Stop"
                            slot = s.get("time_slot", "")
                            time_range = s.get("arrival_time", "") or s.get("time_range", "")
                            lines.append(f"  • {slot.title()}: {name}" + (f" — {time_range}" if time_range else ""))
                        msg = (
                            f"Here's your **Day {day_num}** in {dest} ({day_data.get('date', 'TBD')}):\n"
                            + "\n".join(lines)
                        )
                        return {
                            "message": msg,
                            "cards": visuals["cards"],
                            "pins": visuals["pins"],
                            "trip": existing,
                            "trip_id": existing["id"],
                            "provider": self.llm.status(),
                            "mode": "demo",
                            "tool_calls": [],
                            "suggestions": dynamic_suggestions_for_dest(existing.get("destination", "")),
                            "note": "",
                        }

                # Hotel / stay query
                if any(w in lowered_msg for w in ("hotel", "stay", "accommodation", "room", "where am i staying")):
                    hotel = existing.get("hotel")
                    if hotel:
                        msg = (
                            f"Your stay in {dest} is at **{hotel.get('name')}** "
                            f"({hotel.get('stars', 4)}-star, rated {hotel.get('rating', 4.7)}/5). "
                            f"{hotel.get('address', '')}. {_hotel_price_label(hotel)}."
                        )
                    else:
                        msg = f"No hotel has been booked for your {dest} trip yet. Would you like me to recommend one?"
                    return {
                        "message": msg,
                        "cards": visuals["cards"],
                        "pins": visuals["pins"],
                        "trip": existing,
                        "trip_id": existing["id"],
                        "provider": self.llm.status(),
                        "mode": "demo",
                        "tool_calls": [],
                        "suggestions": dynamic_suggestions_for_dest(existing.get("destination", "")),
                        "note": "",
                    }

                # Flight / travel query
                if any(w in lowered_msg for w in ("flight", "fly", "airline", "plane", "how am i getting")):
                    flight = existing.get("flight") or ((existing.get("flights_json") or [None])[0])
                    if flight:
                        msg = (
                            f"Your flight for {dest}: **{flight.get('airline')}** {flight.get('flight_number', '')} "
                            f"from {flight.get('origin')} to {flight.get('destination')}. "
                            f"Departs {flight.get('departure_time')}, arrives {flight.get('arrival_time')}. "
                            f"${flight.get('price_usd', 0):,.2f} total."
                        )
                    else:
                        msg = f"No flights have been booked for your {dest} trip yet. Would you like me to search for flights?"
                    return {
                        "message": msg,
                        "cards": visuals["cards"],
                        "pins": visuals["pins"],
                        "trip": existing,
                        "trip_id": existing["id"],
                        "provider": self.llm.status(),
                        "mode": "demo",
                        "tool_calls": [],
                        "suggestions": dynamic_suggestions_for_dest(existing.get("destination", "")),
                        "note": "",
                    }

                # General contextual response referencing the existing trip + conversation history
                history_prefix = ""
                if summary:
                    history_prefix = f"Earlier in our conversation: {summary}\n\n"
                elif history_str and history_str != "No prior turns.":
                    history_prefix = f"Recent conversation:\n{history_str}\n\n"

                return {
                    "message": (
                        f"{history_prefix}"
                        f"You're viewing your itinerary for **{existing.get('title')}** — {dest}, "
                        f"{existing.get('day_count')} days ({existing.get('start_date')} to {existing.get('end_date')}), "
                        f"staying at **{hotel_name}**. It has {existing.get('stop_count', 0)} stops pinned on the map. "
                        f"What would you like to adjust — the hotel, a specific day's stops, flights, or add a new spot?"
                    ),
                    "cards": visuals["cards"],
                    "pins": visuals["pins"],
                    "trip": existing,
                    "trip_id": existing["id"],
                    "provider": self.llm.status(),
                    "mode": "demo",
                    "tool_calls": [],
                    "suggestions": dynamic_suggestions_for_dest(existing.get("destination", "")),
                    "note": "",
                }

        dates_info = parse_dates_and_days(message)
        days = dates_info["days"] or parse_days(message)
        start_date = context.get("start_date") or dates_info["start_date"] or ""
        end_date = context.get("end_date") or dates_info["end_date"] or ""
        traveler_type, passengers = parse_traveler_and_passengers(message)
        extracted = extract_destination_and_origin(message)
        origin = detect_origin(message)
        dest_query = extracted["destination"] or message

        trip = synthesize_trip(
            self.session,
            destination_query=dest_query,
            days=days,
            traveler_type=traveler_type,
            budget=parse_budget(message),
            start_date=start_date,
            end_date=end_date,
            hotel_id=context.get("hotel_id", ""),
            preferences=message,
            session_id=self.session_id,
            origin=origin,
            passengers=passengers,
        )
        return {
            "message": trip["message"],
            "cards": trip["cards"],
            "pins": trip["pins"],
            "trip": trip["trip"],
            "trip_id": trip["trip"]["id"],
            "provider": self.llm.status(),
            "mode": "demo",
            "tool_calls": [],
            "suggestions": dynamic_suggestions_for_dest(trip.get("trip", {}).get("destination", "")),
            "note": LOCAL_PLANNER_NOTE if not self.llm.is_live else "",
        }

    # ------------------------------------------------------------------ #
    # Live tool-calling path
    # ------------------------------------------------------------------ #
    async def _live_response(self, message: str, context: dict[str, Any]) -> dict[str, Any]:
        # Resolve active trip if present
        active_trip = None
        trip_id = context.get("trip_id") or ""
        if not trip_id:
            stmt = select(Trip).where(Trip.session_id == self.session_id).order_by(Trip.updated_at.desc())
            row = self.session.exec(stmt).first()
            if row:
                trip_id = row.id
        if trip_id:
            active_trip = data_service.get_trip(self.session, trip_id)

        # Use enriched context from ChatContextManager if available, otherwise
        # summarize older turns to keep the LLM context compact.
        ctx = context.get("_chat_context") or {}
        enriched_history = ctx.get("recent_history", [])
        existing_summary = ctx.get("summary", "")

        if enriched_history:
            history_rows = enriched_history
            summary = existing_summary or ""
        else:
            memory = await summarize_history(
                self.llm, self.session_id, self.session, max_turns=40
            )
            history_rows = memory["recent_history"]
            summary = memory["summary"] or existing_summary or ""

        system_text = SYSTEM_PROMPT

        if summary:
            system_text += (
                f"\n\nCONVERSATION SUMMARY (older turns):\n{summary}\n"
            )

        if active_trip:
            dest_name = (active_trip.get("destination") or "").title()
            itinerary_summary = (
                f"\n\nCURRENT ACTIVE ITINERARY:\n"
                f"- Trip ID: {active_trip['id']}\n"
                f"- Destination: {dest_name}\n"
                f"- Title: {active_trip.get('title', '')}\n"
                f"- Hotel: {active_trip.get('hotel', {}).get('name') if active_trip.get('hotel') else 'None'}\n"
                f"- Plan:\n"
            )
            for d in active_trip.get("days", []):
                day_stops = ", ".join(s.get("place", {}).get("name") or s.get("notes") or "Stop" for s in d.get("stops", []))
                itinerary_summary += f"  * Day {d.get('day_index')}: {day_stops}\n"

            itinerary_summary += (
                f"\nCRITICAL INSTRUCTION: The user is chatting about their existing {dest_name} itinerary above! "
                "DO NOT call `build_itinerary` to create a new trip from scratch unless they explicitly say 'start a new trip' or specify a completely different city. "
                "For questions about stops, schedule, hotels, restaurants, or adjustments, answer in prose and use search tools (`search_hotels`, `search_places`, etc.) without rebuilding the whole trip."
            )
            system_text += itinerary_summary

        messages: list[dict[str, Any]] = [{"role": "system", "content": system_text}]
        for row in history_rows[-8:]:
            if row.get("sender") in {"user", "assistant"} and row.get("message"):
                messages.append({"role": row["sender"], "content": row["message"]})
        messages.append({"role": "user", "content": message})

        dispatcher = ToolDispatcher(
            self.session,
            self.session_id,
            itinerary_builder=lambda **kwargs: synthesize_trip(self.session, **kwargs),
        )
        tool_calls_log: list[dict[str, Any]] = []
        built_trip: dict[str, Any] | None = None
        final_text = ""

        for _ in range(4):
            response = await self.llm.complete_with_retry(messages, tools=TOOL_SCHEMAS)
            if not response.tool_calls:
                final_text = (response.content or "").strip()
                break

            messages.append(
                {
                    "role": "assistant",
                    "content": response.content or "",
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {"name": call.name, "arguments": json.dumps(call.arguments)},
                        }
                        for call in response.tool_calls
                    ],
                }
            )
            for call in response.tool_calls:
                result = dispatcher.dispatch(call.name, call.arguments)
                tool_calls_log.append({"name": call.name, "arguments": call.arguments, "result_summary": _summarise(result)})
                if call.name == "build_itinerary" and isinstance(result.get("trip"), dict):
                    built_trip = result["trip"]
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "name": call.name,
                        "content": json.dumps(result, ensure_ascii=False, default=str)[:8000],
                    }
                )
        else:
            # Exhausted the tool loop; ask for a final prose answer.
            try:
                final = await self.llm.complete_with_retry(messages)
                final_text = (final.content or "").strip()
            except Exception:  # noqa: BLE001
                final_text = ""

        if built_trip is None:
            if active_trip:
                visuals = visuals_for_trip(self.session, active_trip)
                # If tool calls found hotels, convert to hotel cards
                hotel_cards = []
                google_cards = []
                google_pins = []
                for tc in tool_calls_log:
                    if tc.get("name") == "search_hotels":
                        h_rows = data_service.list_hotels(self.session, destination=active_trip.get("destination", ""), limit=6)
                        for h in h_rows:
                            hotel_cards.append({
                                "type": "hotel",
                                "id": h["id"],
                                "name": h["name"],
                                "price": f"${int(h.get('price_per_night', 0))}/night",
                                "rating": h.get("rating", 4.7),
                                "image": (h.get("photos") or [""])[0],
                                "description": h.get("description", ""),
                                "address": h.get("address", ""),
                            })
                    elif tc.get("name") in {"search_google_maps_places", "search_places"}:
                        q = (tc.get("arguments", {}).get("query") or "").lower()
                        loc = tc.get("arguments", {}).get("location") or tc.get("arguments", {}).get("destination") or active_trip.get("destination", "")
                        dest_clean = loc.strip().lower().replace(" ", "-")
                        all_p = data_service.list_places(self.session, destination=dest_clean, limit=50)
                        q_words = [w.strip() for w in q.split() if len(w.strip()) > 2]
                        matched_p = [
                            p for p in all_p
                            if any(w in (p.get("name") or "").lower() or w in (p.get("description") or "").lower() or any(w in t.lower() for t in p.get("tags") or []) for w in q_words)
                        ] if q_words else all_p[:5]
                        for p in (matched_p or all_p)[:5]:
                            google_cards.append(_place_card(p, p.get("category", "restaurant")))
                            if p.get("lat") and p.get("lon"):
                                google_pins.append({
                                    "id": p["id"],
                                    "name": p["name"],
                                    "category": p.get("category", "restaurant"),
                                    "lat": p["lat"],
                                    "lon": p["lon"],
                                    "rating": p.get("rating", 4.8),
                                    "address": p.get("address", ""),
                                    "photo": (p.get("photos") or [""])[0] if p.get("photos") else "",
                                    "label": "📍",
                                    "trip_id": active_trip["id"],
                                    "description": p.get("description", ""),
                                    "is_itinerary_stop": False,
                                })

                cards_to_show = google_cards or hotel_cards or visuals["cards"]
                pins_to_show = (google_pins + visuals["pins"]) if google_pins else visuals["pins"]
                return {
                    "message": final_text or f"I've updated your notes for {active_trip.get('title', 'your trip')}.",
                    "cards": cards_to_show,
                    "pins": pins_to_show,
                    "trip": active_trip,
                    "trip_id": active_trip["id"],
                    "provider": self.llm.status(),
                    "mode": "live",
                    "tool_calls": tool_calls_log,
                    "suggestions": dynamic_suggestions_for_dest(active_trip.get("destination", "")),
                }

            if not looks_like_trip_request(message):
                # The LLM answered a greeting/general question without calling a
                # tool. Do not turn "hello" into a full live-scraped trip.
                return {
                    "message": final_text
                    or "Hi! Tell me where you'd like to go and for how many days.",
                    "cards": [],
                    "pins": [],
                    "trip": None,
                    "trip_id": None,
                    "provider": self.llm.status(),
                    "mode": "live",
                    "tool_calls": tool_calls_log,
                    "suggestions": dynamic_suggestions_for_dest(""),
                }

            local = self._local_response(message, context)
            return {
                **local,
                "message": final_text or local["message"],
                "provider": self.llm.status(),
                "mode": "live",
                "tool_calls": tool_calls_log,
                "suggestions": dynamic_suggestions_for_dest(local.get("trip", {}).get("destination", "")),
            }

        visuals = visuals_for_trip(self.session, built_trip)
        trip = data_service.get_trip(self.session, built_trip["id"]) or built_trip
        if not final_text:
            final_text = (
                f"I've built “{trip['title']}” — {trip.get('day_count', 0)} days and "
                f"{trip.get('stop_count', 0)} stops, all pinned on the map. "
                "Tell me what to change and I'll rework it."
            )
        return {
            "message": final_text,
            "cards": visuals["cards"],
            "pins": visuals["pins"],
            "trip": trip,
            "trip_id": trip["id"],
            "provider": self.llm.status(),
            "mode": "live",
            "tool_calls": tool_calls_log,
            "suggestions": dynamic_suggestions_for_dest(trip.get("destination", "")),
        }

    # ------------------------------------------------------------------ #
    # Lightweight follow-ups that do not need a new itinerary
    # ------------------------------------------------------------------ #
    async def _followup(self, message: str, context: dict[str, Any]) -> dict[str, Any] | None:
        import re

        trip_id = context.get("trip_id") or ""
        if not trip_id:
            stmt = select(Trip).where(Trip.session_id == self.session_id).order_by(Trip.updated_at.desc())
            row = self.session.exec(stmt).first()
            if row:
                trip_id = row.id

        if not trip_id:
            return None
        trip = self.session.get(Trip, trip_id)
        if not trip:
            return None

        lowered = message.lower()

        # Check if the user query is purely informational or general advice that should be handled by the LLM
        is_informational_question = any(
            lowered.startswith(prefix)
            for prefix in (
                "what should", "what do", "what is", "what are", "what to",
                "how do", "how is", "how can", "how should", "how to",
                "tell me about", "tell me more", "can you tell me", "explain",
                "why should", "why is", "why do",
                "is it safe", "is there any advice", "any tips", "packing tips",
                "do i need a visa", "what currency", "best time of year",
            )
        ) and not any(
            action in lowered
            for action in (
                "add ", "put ", "schedule ", "insert ", "swap ", "change ", "remove ",
                "delete ", "book ", "find me ", "where can i get ", "recommend a ",
                "show me hotels", "find flights", "show flights"
            )
        )
        if is_informational_question:
            return None
        wants_flight = any(
            word in lowered
            for word in (
                "flight", "flights", "airline", "airlines", "airfare", "airfares", "plane", "planes",
                "ticket", "tickets", "fly", "flying", "aviation"
            )
        )
        # Check if "hotel" or "stay" is merely used as a spatial landmark anchor (e.g. "near my hotel", "from my hotel")
        is_hotel_anchor = any(
            pattern in lowered
            for pattern in (
                "near my hotel", "near our hotel", "near the hotel", "near hotel",
                "close to my hotel", "close to the hotel", "close to hotel", "closest to my hotel",
                "around my hotel", "around the hotel", "around hotel",
                "next to my hotel", "next to the hotel", "next to hotel",
                "by my hotel", "by the hotel", "by hotel",
                "from my hotel", "from the hotel", "from our hotel", "from hotel",
                "at my hotel", "at the hotel", "at our hotel",
                "walking distance from my hotel", "walking distance from the hotel", "walking distance from hotel",
            )
        ) or bool(re.search(r"\b(?:nearest|closest|best|find)\s+[a-z\s]+\s+(?:from|near|to)\s+(?:my|the|our)?\s*hotel\b", lowered))

        explicit_hotel_request = any(
            w in lowered
            for w in (
                "show hotel", "show hotels", "find hotel", "find hotels", "recommend hotel", "recommend hotels",
                "suggest hotel", "suggest hotels", "list hotel", "list hotels", "boutique hotel", "boutique hotels",
                "luxury hotel", "luxury hotels", "budget hotel", "budget hotels", "cheap hotel", "cheap hotels",
                "hotel under", "hotels under", "hotel options", "hotels in", "hotels near",
                "swap hotel", "change hotel", "switch hotel", "update hotel", "swap to",
                "where to stay", "where can i stay", "place to stay", "places to stay", "best stays",
                "accommodations", "resorts", "resort in", "book a room", "hotel recommendation"
            )
        )

        has_other_place_or_amenity_intent = any(
            w in lowered
            for w in (
                "saloon", "saloons", "salon", "salons", "barber", "haircut", "spa", "massage",
                "restaurant", "restaurants", "food", "dining", "eat", "dinner", "lunch", "breakfast",
                "cafe", "cafes", "coffee", "pharmacy", "pharmacies", "hospital", "clinic", "gym",
                "museum", "attraction", "visit", "visiting", "pub", "pubs", "bar", "bars", "club",
                "supermarket", "grocery", "chemist", "rent a car", "rent car", "rental car", "rental cars",
                "car rental", "car rentals", "car hire", "hire a car", "rent a vehicle"
            )
        )

        if is_hotel_anchor or has_other_place_or_amenity_intent:
            wants_hotel = explicit_hotel_request and not has_other_place_or_amenity_intent
        else:
            wants_hotel = any(word in lowered for word in ("hotel", "stay", "room", "accommodation", "resort"))

        if wants_flight:
            # Extract origin/destination from the user's message FIRST so the
            # user's actual request takes priority over the trip's stored values.
            msg_extracted = extract_destination_and_origin(message)
            msg_origin = msg_extracted.get("origin", "").strip().lower()
            msg_destination = msg_extracted.get("destination", "").strip().lower()

            # Destination: message > trip.destination > no default (empty)
            dest_raw = msg_destination or (trip.destination or "").strip().lower()
            dest_code = CITY_TO_AIRPORT.get(dest_raw, "") if dest_raw else ""

            # Origin: message > trip.flights_json > detect_origin > empty
            orig_code = ""
            if msg_origin:
                orig_code = CITY_TO_AIRPORT.get(msg_origin, "")
            elif trip.flights_json and len(trip.flights_json) > 0:
                first_fl = trip.flights_json[0]
                orig_code = first_fl.get("origin") or ""
            if not orig_code:
                combined_text = f"{trip.title} {trip.summary} {message}"
                detected_orig = detect_origin(combined_text)
                if detected_orig:
                    orig_code = CITY_TO_AIRPORT.get(detected_orig.lower(), "")

            # VALIDATION: refuse to scrape with missing origin or destination
            if not orig_code or not dest_code:
                missing = []
                if not orig_code:
                    missing.append("departure city (e.g. Delhi, SFO, JFK)")
                if not dest_code:
                    missing.append("destination city (e.g. Jakarta, KIX, JFK)")
                return {
                    "message": (
                        f"I need {' and '.join(missing)} to search for flights. "
                        f"Please tell me: “flights from {orig_code or 'Delhi'} to {dest_code or 'Jakarta'}” "
                        f"with your travel dates."
                    ),
                    "cards": [],
                    "pins": visuals_for_trip(self.session, data_service.get_trip(self.session, trip.id) or {})["pins"],
                    "trip": data_service.get_trip(self.session, trip.id),
                    "trip_id": trip.id,
                    "provider": self.llm.status(),
                    "mode": "live",
                    "tool_calls": [],
                    "suggestions": dynamic_suggestions_for_dest(trip.destination or ""),
                }

            start_date = trip.start_date or (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")
            end_date = trip.end_date
            is_round_trip = bool(end_date and end_date != start_date)
            trip_type = "round-trip" if is_round_trip else "one-way"

            traveler_str = trip.traveler_type or trip.summary or ""
            _, passengers = parse_traveler_and_passengers(traveler_str)
            if passengers <= 1 and trip.flights_json:
                passengers = trip.flights_json[0].get("passengers") or 1
            if passengers <= 1:
                _, msg_pax = parse_traveler_and_passengers(message)
                if msg_pax > 1:
                    passengers = msg_pax
            passengers = max(1, passengers)

            # Always fetch fresh live Google Flights data for chat requests.
            from scrapers.flight_scraper_runner import (
                calculate_great_circle_km,
                save_flights_to_db,
                search_flights as live_search_flights,
            )
            route_dist = calculate_great_circle_km(orig_code, dest_code)
            min_phys_dur = max(45, int((route_dist / 1000.0) * 60))

            live_records: list[Any] = []
            try:
                live_records = await live_search_flights(
                    origin=orig_code,
                    destination=dest_code,
                    date=start_date,
                    return_date=end_date if is_round_trip else None,
                    cabin="Economy",
                    adults=passengers,
                    trip_type=trip_type,
                    live=True,
                    max_results=40,
                    allow_fallback=True,
                )
                if live_records:
                    save_flights_to_db(live_records, self.session)
            except Exception as exc:  # noqa: BLE001 - surface an honest empty state
                logger.warning("Live flight scrape failed in chat: %s", exc)

            if not live_records:
                return {
                    "message": (
                        f"I couldn't pull live Google Flights results for **{orig_code} → {dest_code}** "
                        "right now. Please try again in a moment, or adjust the route or date."
                    ),
                    "cards": [],
                    "pins": visuals_for_trip(self.session, data_service.get_trip(self.session, trip.id) or {})["pins"],
                    "trip": data_service.get_trip(self.session, trip.id),
                    "trip_id": trip.id,
                    "provider": self.llm.status(),
                    "mode": "live",
                    "tool_calls": [{"name": "search_flights", "arguments": {"origin": orig_code, "destination": dest_code}}],
                    "suggestions": dynamic_suggestions_for_dest(trip.destination),
                }

            # Read back only the records we just scraped — never historical cache.
            live_ids = {r.id for r in live_records if getattr(r, "id", None)}
            stmt = select(Flight).where(Flight.origin == orig_code, Flight.destination == dest_code)
            raw_cached = list(self.session.exec(stmt).all())
            cached_flights = [
                f for f in raw_cached
                if f.id in live_ids and f.duration_minutes >= min_phys_dur
            ]
            if not cached_flights:
                cached_flights = [
                    f for f in raw_cached
                    if f.id in live_ids
                ]

            filtered = list(cached_flights)

            # 1. Filter by Airline
            known_airlines = [
                ("air india", "Air India"),
                ("united", "United Airlines"),
                ("american", "American Airlines"),
                ("emirates", "Emirates"),
                ("qatar", "Qatar Airways"),
                ("lufthansa", "Lufthansa"),
                ("british airways", "British Airways"),
                ("air france", "Air France"),
                ("etihad", "Etihad Airways"),
                ("virgin", "Virgin Atlantic"),
                ("delta", "Delta Air Lines"),
                ("singapore", "Singapore Airlines"),
                ("indigo", "IndiGo"),
                ("vistara", "Vistara"),
            ]
            matched_airline = None
            for key, name in known_airlines:
                if key in lowered:
                    matched_airline = name
                    break

            if matched_airline:
                airline_matches = [f for f in filtered if matched_airline.lower() in f.airline.lower()]
                if airline_matches:
                    filtered = airline_matches

            # 2. Filter by Stops
            wants_nonstop = any(w in lowered for w in ("non-stop", "nonstop", "direct", "0 stop", "zero stop"))
            wants_onestop = any(w in lowered for w in ("1 stop", "one stop", "layover", "transit"))
            if wants_nonstop:
                nonstop_matches = [f for f in filtered if f.stops == 0]
                if nonstop_matches:
                    filtered = nonstop_matches
            elif wants_onestop:
                onestop_matches = [f for f in filtered if f.stops == 1]
                if onestop_matches:
                    filtered = onestop_matches

            # 3. Filter by Time of Day
            wants_morning = any(w in lowered for w in ("morning", "early", "am"))
            wants_evening = any(w in lowered for w in ("evening", "night", "pm", "red-eye", "late"))
            def _dep_hour(fl: Flight) -> int:
                t = fl.departure_time.split("T")[-1] if "T" in fl.departure_time else fl.departure_time
                try:
                    return int(t[:2])
                except Exception:
                    return 12

            if wants_morning:
                morn_matches = [f for f in filtered if _dep_hour(f) < 12]
                if morn_matches:
                    filtered = morn_matches
            elif wants_evening:
                eve_matches = [f for f in filtered if _dep_hour(f) >= 17]
                if eve_matches:
                    filtered = eve_matches

            # 4. Sorting
            wants_cheaper = any(w in lowered for w in ("cheap", "cheaper", "budget", "lowest", "affordable", "economical", "price"))
            wants_fastest = any(w in lowered for w in ("fast", "fastest", "quick", "shortest"))

            if wants_cheaper:
                filtered.sort(key=lambda f: f.price_usd)
            elif wants_fastest:
                filtered.sort(key=lambda f: f.duration_minutes)
            else:
                filtered.sort(key=lambda f: (f.stops, f.price_usd))

            # 5. Swap / Book flight into trip
            is_swap_flight = any(w in lowered for w in ("swap flight", "change flight", "switch flight", "choose flight", "book flight", "pick flight", "select flight"))
            if is_swap_flight and filtered:
                chosen_flight = filtered[0]
                flight_card_obj = _flight_card(chosen_flight, pax=passengers)
                trip.flight_id = chosen_flight.id
                trip.flights_json = [flight_card_obj]
                self.session.add(trip)
                self.session.commit()
                trip_detail = data_service.get_trip(self.session, trip.id)
                dur_str = f"{chosen_flight.duration_minutes // 60}h {chosen_flight.duration_minutes % 60}m"
                stops_str = "non-stop" if chosen_flight.stops == 0 else f"{chosen_flight.stops} stop"
                return {
                    "message": (
                        f"I've updated your trip flight to **{chosen_flight.airline} ({chosen_flight.flight_number})**!\n\n"
                        f"- **Route**: {orig_code} ⇄ {dest_code}\n"
                        f"- **Schedule**: Departs {flight_card_obj['departure_time']}, arrives {flight_card_obj['arrival_time']} ({dur_str}, {stops_str})\n"
                        f"- **Total Fare ({passengers} adults)**: ${chosen_flight.price_usd:,.2f} (approx ${flight_card_obj['price_per_person_usd']:,.2f} per person)\n\n"
                        "Your itinerary and transit buffers have been updated on the map."
                    ),
                    "cards": [flight_card_obj],
                    "pins": visuals_for_trip(self.session, trip_detail or {})["pins"],
                    "trip": trip_detail,
                    "trip_id": trip.id,
                    "provider": self.llm.status(),
                    "mode": "live" if self.llm.is_live else "demo",
                    "tool_calls": [{"name": "update_flight", "arguments": {"flight_id": chosen_flight.id}}],
                    "suggestions": [
                        "Show all available flights",
                        f"Show boutique hotels in {trip.destination.title()}",
                        "Show Day 1 route on map",
                    ],
                }

            # 6. Recommendation / Best Pick intent (return ONLY 1-2 recommended cards + rationale)
            wants_recommendation = any(
                phrase in lowered
                for phrase in (
                    "recommended flight", "recommend flight", "which is recommended",
                    "which one is recommended", "what is recommended", "which flight is recommended",
                    "which flight is best", "which is best", "which one is best", "best flight",
                    "top pick", "which do you suggest", "what do you suggest", "which one do you suggest",
                    "which flight do you suggest", "which should i choose", "which one should i choose",
                    "which flight should i choose", "which should i pick", "which one should i pick",
                    "which would you choose", "which flight would you choose", "which one is better",
                    "recommend one", "recommend a flight", "best option", "top choice",
                    "which flight to choose", "which airline is recommended", "recommended one"
                )
            )
            if wants_recommendation and filtered:
                nonstops = [f for f in filtered if f.stops == 0]
                if nonstops:
                    nonstops.sort(key=lambda f: (_dep_hour(f) < 5, f.price_usd))
                    top_rec = nonstops[0]
                else:
                    top_rec = min(filtered, key=lambda f: (f.stops, f.duration_minutes))

                cheapest = min(filtered, key=lambda f: f.price_usd)
                alt_rec = cheapest if cheapest.id != top_rec.id else (filtered[1] if len(filtered) > 1 else None)

                top_card = _flight_card(top_rec, pax=passengers)
                dur_str = top_card["duration"]
                stops_str = "Direct Non-Stop" if top_rec.stops == 0 else f"{top_rec.stops}-stop"
                per_pax = top_card["price_per_person_usd"]

                rec_cards = [top_card]
                if alt_rec:
                    rec_cards.append(_flight_card(alt_rec, pax=passengers))

                rec_lines = [
                    f"### 🏆 Recommended Flight: **{top_rec.airline} ({top_rec.flight_number})**\n",
                    f"Between the options from **{orig_code} to {dest_code}**, I strongly recommend **{top_rec.airline}** for your party of {passengers} adults.\n",
                    "**Why this is your best option:**",
                    f"- ⚡ **{stops_str} Route:** Flight duration is **{dur_str}**, eliminating connection buffers, layovers, and transfer fatigue.",
                    f"- ⏰ **Optimized Schedule:** Departs at **{top_card['departure_time']}** and lands at **{top_card['arrival_time']}**, giving you an easy arrival window with plenty of time for immigration and hotel check-in.",
                    f"- 🧳 **Included Baggage:** {top_card['baggage']}.",
                    f"- 💵 **Fare:** **${top_rec.price_usd:,.2f} total** (approx **${per_pax:,.2f} per adult**).",
                ]

                if alt_rec and alt_rec.id != top_rec.id:
                    alt_card = _flight_card(alt_rec, pax=passengers)
                    savings = top_rec.price_usd - alt_rec.price_usd
                    if savings > 20:
                        rec_lines.append(
                            f"\n💡 **Budget-Friendly Alternative:** If you prefer to save approx **${savings:,.2f} total** (${savings / passengers:,.2f} per adult), **{alt_rec.airline} ({alt_rec.flight_number})** offers a 1-stop route at **${alt_rec.price_usd:,.2f} total** ({alt_card['duration']})."
                        )

                rec_lines.append(f"\nWould you like me to lock in the **{top_rec.airline}** flight for your itinerary, or adjust anything else?")

                return {
                    "message": "\n".join(rec_lines),
                    "cards": rec_cards,
                    "pins": visuals_for_trip(self.session, data_service.get_trip(self.session, trip.id) or {})["pins"],
                    "trip": data_service.get_trip(self.session, trip.id),
                    "trip_id": trip.id,
                    "provider": self.llm.status(),
                    "mode": "live" if self.llm.is_live else "demo",
                    "tool_calls": [{"name": "recommend_flight", "arguments": {"flight_id": top_rec.id}}],
                    "suggestions": [
                        f"Swap flight to {top_rec.airline}",
                        f"Swap flight to {alt_rec.airline}" if alt_rec else "Show all flights",
                        "Show all 15 flight options",
                        f"Show boutique hotels in {trip.destination.title()}",
                    ],
                }

            # Ensure minimum 10-15 cards returned
            if len(filtered) < 12 and len(cached_flights) >= 12:
                seen_ids = {f.id for f in filtered}
                for cf in cached_flights:
                    if cf.id not in seen_ids:
                        filtered.append(cf)
                        seen_ids.add(cf.id)
                    if len(filtered) >= 15:
                        break

            if not filtered:
                return {
                    "message": (
                        f"I found live Google Flights results for **{orig_code} → {dest_code}**, "
                        "but none matched the filters in your request. Try relaxing the airline, "
                        "stops, or time preference."
                    ),
                    "cards": [],
                    "pins": visuals_for_trip(self.session, data_service.get_trip(self.session, trip.id) or {})["pins"],
                    "trip": data_service.get_trip(self.session, trip.id),
                    "trip_id": trip.id,
                    "provider": self.llm.status(),
                    "mode": "live" if self.llm.is_live else "demo",
                    "tool_calls": [{"name": "search_flights", "arguments": {"origin": orig_code, "destination": dest_code}}],
                    "suggestions": dynamic_suggestions_for_dest(trip.destination),
                }

            shown_flights = filtered[:15]
            flight_cards = [_flight_card(f, pax=passengers) for f in shown_flights]

            # Construct rich editorial markdown response
            nonstop_flights = [f for f in shown_flights if f.stops == 0]
            cheapest_flight = min(shown_flights, key=lambda f: f.price_usd)
            fastest_flight = min(shown_flights, key=lambda f: f.duration_minutes)

            dates_label = f"{start_date} → {end_date}" if is_round_trip else start_date
            type_label = "Round-Trip" if is_round_trip else "One-Way"

            md_lines = [
                f"### ✈️ Available Flights: {orig_code} ⇄ {dest_code} ({dates_label})",
                f"**Travelers:** {passengers} Adults • **Trip Type:** {type_label} • **Cabin:** Economy",
                f"*Showing {len(shown_flights)} live options scraped from Google Flights.*\n",
                "| Airline | Flight # | Departs | Arrives | Duration | Stops | Total Fare | Per Adult |",
                "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
            ]

            for fc in shown_flights[:8]:
                card_dict = _flight_card(fc, pax=passengers)
                dur_str = card_dict["duration"]
                stops_label = "**Non-stop**" if fc.stops == 0 else f"{fc.stops} stop"
                per_pax = card_dict["price_per_person_usd"]
                md_lines.append(
                    f"| **{fc.airline}** | `{fc.flight_number}` | {card_dict['departure_time']} | {card_dict['arrival_time']} | {dur_str} | {stops_label} | **${fc.price_usd:,.2f}** | ${per_pax:,.2f} |"
                )

            if is_round_trip and shown_flights[0].metadata_json and shown_flights[0].metadata_json.get("return_flight"):
                md_lines.append(f"\n### 🔄 Paired Return Flights ({dest_code} ⇄ {orig_code} • {end_date})")
                md_lines.append("| Return Airline | Flight # | Departs | Arrives | Duration | Stops |")
                md_lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
                for fc in shown_flights[:6]:
                    ret = (fc.metadata_json or {}).get("return_flight")
                    if ret:
                        ret_dur = f"{ret.get('duration_minutes', 0) // 60}h {ret.get('duration_minutes', 0) % 60}m"
                        ret_stops = "**Non-stop**" if ret.get("stops") == 0 else f"{ret.get('stops')} stop"
                        ret_dep = ret.get("departure_time", "").split("T")[-1][:5]
                        ret_arr = ret.get("arrival_time", "").split("T")[-1][:5]
                        md_lines.append(
                            f"| **{ret.get('airline')}** | `{ret.get('flight_number')}` | {ret_dep} | {ret_arr} | {ret_dur} | {ret_stops} |"
                        )

            md_lines.append("\n**Curated Highlights:**")
            if nonstop_flights:
                top_nonstop = nonstop_flights[0]
                ns_card = _flight_card(top_nonstop, pax=passengers)
                md_lines.append(f"- ⚡ **Fastest Non-Stop**: **{top_nonstop.airline} ({top_nonstop.flight_number})** — direct flight in {ns_card['duration']}.")
            md_lines.append(f"- 🏷️ **Best Value**: **{cheapest_flight.airline} ({cheapest_flight.flight_number})** at **${cheapest_flight.price_usd:,.2f} total** (${cheapest_flight.price_usd/passengers:,.2f}/adult).")
            onestop_picks = [f for f in shown_flights if f.stops == 1]
            if onestop_picks:
                md_lines.append(f"- 🛋️ **Premium Layover**: **{onestop_picks[0].airline}** via international transit hub.")

            md_lines.append("\n*Scroll through the flight cards below to compare timings and baggage. Say 'swap flight to [Airline]' to lock one in.*")

            return {
                "message": "\n".join(md_lines),
                "cards": flight_cards,
                "pins": visuals_for_trip(self.session, data_service.get_trip(self.session, trip.id) or {})["pins"],
                "trip": data_service.get_trip(self.session, trip.id),
                "trip_id": trip.id,
                "provider": self.llm.status(),
                "mode": "live" if self.llm.is_live else "demo",
                "tool_calls": [{"name": "search_flights", "arguments": {"origin": orig_code, "destination": dest_code}}],
                "suggestions": [
                    "Show non-stop flights only",
                    "Show cheaper flights",
                    f"Swap flight to {shown_flights[0].airline}",
                    "Show morning flights only",
                ],
            }

        if wants_hotel:
            # Check price limit from message (prices may be stored in INR or USD).
            max_price: float | None = None
            max_price_usd: float | None = None
            max_price_label = ""
            price_match = re.search(r"(?:under|below|max|budget of|less than)\s*[₹$]?\s*([\d,]+)", lowered)
            if price_match:
                max_price = float(price_match.group(1).replace(",", ""))
                if "₹" in lowered or "inr" in lowered or "rupee" in lowered:
                    max_price_usd = max_price / 85.0
                    max_price_label = f"₹{int(max_price):,}"
                else:
                    max_price_usd = max_price
                    max_price_label = f"${int(max_price)}"

            dest_clean = trip.destination.strip().lower()
            # Retrieve from cache
            cached_hotels = data_service.list_hotels(self.session, destination=dest_clean, limit=50)
            if len(cached_hotels) < 4:
                try:
                    from scrapers.hotel_scraper_runner import search_hotels as scrape_hotels, save_hotels_to_db
                    scraped = scrape_hotels(destination=dest_clean, max_results=20)
                    if scraped:
                        save_hotels_to_db(scraped, self.session)
                except Exception:
                    pass
                cached_hotels = data_service.list_hotels(self.session, destination=dest_clean, limit=50)

            if not cached_hotels:
                return {
                    "message": f"I couldn't find stays for {trip.destination.title()} yet. Try searching the Stays hub, then ask me to swap it in.",
                    "cards": [],
                    "pins": [],
                    "trip": data_service.get_trip(self.session, trip.id),
                    "trip_id": trip.id,
                    "provider": self.llm.status(),
                    "mode": "live" if self.llm.is_live else "demo",
                    "tool_calls": [],
                    "suggestions": dynamic_suggestions_for_dest(trip.destination),
                }

            current_hotel: dict[str, Any] | None = None
            if trip.hotel_id:
                current_hotel = data_service.get_hotel(self.session, trip.hotel_id)
            if current_hotel is None and trip.hotels_json:
                current_hotel = trip.hotels_json[0]
            current_id = (current_hotel or {}).get("id")
            current_usd = _hotel_price_usd(current_hotel) if current_hotel else None

            # Explicit hotel names always win over budget filtering.
            requested_hotel = _match_requested_item(lowered, cached_hotels)

            budget_hotels = cached_hotels
            if max_price_usd is not None and not requested_hotel:
                affordable = [
                    h for h in cached_hotels
                    if (_hotel_price_usd(h) is not None and _hotel_price_usd(h) <= max_price_usd)
                ]
                if affordable:
                    budget_hotels = affordable

            # Only explicit change verbs should mutate the booking. A discovery
            # request such as "show me a cheaper hotel" must not silently swap.
            is_swap = any(
                w in lowered
                for w in ("swap", "change", "switch", "replace", "choose", "pick", "instead", "upgrade")
            )
            wants_cheaper = any(w in lowered for w in ("cheap", "budget", "affordable", "lower price", "less expensive", "economical"))
            wants_upgrade = any(w in lowered for w in ("upgrade", "luxury", "nicer", "better", "5-star", "five star"))

            if is_swap:
                pool = [h for h in budget_hotels if h.get("id") != current_id]
                if not pool:
                    pool = budget_hotels

                if requested_hotel:
                    new_hotel = requested_hotel
                elif wants_cheaper:
                    cheaper = [h for h in pool if _hotel_price_usd(h) is not None and (current_usd is None or _hotel_price_usd(h) < current_usd)]
                    if not cheaper:
                        alternatives = sorted(
                            pool,
                            key=lambda h: (_hotel_price_usd(h) or 10**9, -(h.get("rating") or 0)),
                        )
                        if current_hotel and current_usd is not None:
                            message = (
                                f"**{current_hotel.get('name', 'Your stay')}** is already the most affordable "
                                f"stay I can find in {trip.destination.title()} at "
                                f"{_hotel_price_label(current_hotel)}. I've left your booking unchanged."
                            )
                        else:
                            message = (
                                f"I couldn't verify a cheaper nightly rate in {trip.destination.title()}, "
                                "so I've left your booking unchanged."
                            )
                        if alternatives:
                            message += " Here are the closest alternatives:"
                        return {
                            "message": message,
                            "cards": [_hotel_card(h) for h in alternatives[:6]],
                            "pins": [],
                            "trip": data_service.get_trip(self.session, trip.id),
                            "trip_id": trip.id,
                            "provider": self.llm.status(),
                            "mode": "live" if self.llm.is_live else "demo",
                            "tool_calls": [],
                            "suggestions": (
                                [f"Swap stay to {alternatives[0]['name']}"] if alternatives else []
                            ) + [f"Show luxury hotels in {trip.destination.title()}"],
                        }
                    candidates = cheaper
                    candidates.sort(key=lambda h: (_hotel_price_usd(h) or 10**9, -(h.get("rating") or 0)))
                    new_hotel = candidates[0]
                elif wants_upgrade:
                    pool.sort(key=lambda h: (-(h.get("rating") or 0), -(_hotel_price_usd(h) or 0)))
                    new_hotel = pool[0]
                else:
                    pool.sort(key=lambda h: (-(h.get("rating") or 0), _hotel_price_usd(h) or 10**9))
                    new_hotel = pool[0]

                if new_hotel.get("id") == current_id:
                    # Show other hotels as alternatives, excluding the current one
                    alternatives = [h for h in budget_hotels if h.get("id") != current_id][:6]
                    if alternatives:
                        msg = f"**{new_hotel['name']}** is already your booked stay. Here are other curated options in {trip.destination.title()} — tell me which one to swap in:"
                        suggs = [f"Swap stay to {h['name']}" for h in alternatives[:2]]
                    else:
                        msg = f"**{new_hotel['name']}** is already your booked stay. I couldn't find any other hotels in {trip.destination.title()} to swap to."
                        suggs = [f"Show all hotels in {trip.destination.title()}"]
                    return {
                        "message": msg,
                        "cards": [_hotel_card(h) for h in alternatives],
                        "pins": [],
                        "trip": data_service.get_trip(self.session, trip.id),
                        "trip_id": trip.id,
                        "provider": self.llm.status(),
                        "mode": "live" if self.llm.is_live else "demo",
                        "tool_calls": [],
                        "suggestions": suggs,
                    }

                trip.hotel_id = new_hotel["id"]
                self.session.add(trip)
                self.session.commit()
                detail = data_service.get_trip(self.session, trip.id)
                visuals = visuals_for_trip(self.session, detail or {})
                new_usd = _hotel_price_usd(new_hotel)
                price_label = _hotel_price_label(new_hotel)
                if wants_cheaper and current_usd and new_usd and new_usd < current_usd:
                    saving = int(round(current_usd - new_usd))
                    rationale = f" That's a cheaper option — about ${saving}/night less than your previous stay."
                    if current_hotel and current_hotel.get("name"):
                        rationale = f" That's a cheaper option — about ${saving}/night less than {current_hotel['name']}."
                else:
                    rationale = " The itinerary and transit routes have been re-centered around it."
                return {
                    "message": f"Swapped the stay to **{new_hotel['name']}** ({price_label}, {new_hotel.get('stars', 4)}-star, rated {new_hotel.get('rating', 4.7)}/5).{rationale}",
                    "cards": visuals["cards"],
                    "pins": visuals["pins"],
                    "trip": detail,
                    "trip_id": trip.id,
                    "provider": self.llm.status(),
                    "mode": "live" if self.llm.is_live else "demo",
                    "tool_calls": [{"name": "update_hotel", "arguments": {"hotel_id": new_hotel["id"]}}],
                    "suggestions": dynamic_suggestions_for_dest(trip.destination),
                }

            # Discovery path: return hotel cards from cache without rebuilding trip.
            if max_price_usd is not None:
                budget_hotels = [
                    h for h in budget_hotels
                    if _hotel_price_usd(h) is None or _hotel_price_usd(h) <= max_price_usd
                ]
            if not budget_hotels:
                cheapest = sorted(cached_hotels, key=lambda h: _hotel_price_usd(h) or 10**9)[:6]
                price_note = f" under {max_price_label}" if max_price is not None else ""
                return {
                    "message": f"I couldn't find stays in {trip.destination.title()}{price_note}. Here are the closest available options:",
                    "cards": [_hotel_card(h) for h in cheapest],
                    "pins": [],
                    "trip": data_service.get_trip(self.session, trip.id),
                    "trip_id": trip.id,
                    "provider": self.llm.status(),
                    "mode": "live" if self.llm.is_live else "demo",
                    "tool_calls": [],
                    "suggestions": [f"Swap stay to {h['name']}" for h in cheapest[:2]],
                }

            budget_hotels.sort(
                key=lambda h: (
                    (_hotel_price_usd(h) or 10**9) if (max_price_usd or wants_cheaper) else -(h.get("rating") or 0),
                    (h.get("rating") or 0) if (max_price_usd or wants_cheaper) else (_hotel_price_usd(h) or 10**9),
                )
            )
            shown = budget_hotels[:6]
            price_note = f" under {max_price_label}" if max_price is not None else ""
            fallback_hotel_msg = f"Here are curated hotels in {trip.destination.title()}{price_note} from our collection. Say 'swap to [hotel name]' to update your trip stay:"
            hotel_narrative = await self._compose_concierge_response(
                user_message=message,
                action_summary=f"Curated boutique stays in {trip.destination.title()}{price_note}",
                items=shown,
                active_trip=data_service.get_trip(self.session, trip.id),
                fallback_text=fallback_hotel_msg,
            )
            return {
                "message": hotel_narrative,
                "cards": [_hotel_card(h) for h in shown],
                "pins": [],
                "trip": data_service.get_trip(self.session, trip.id),
                "trip_id": trip.id,
                "provider": self.llm.status(),
                "mode": "live" if self.llm.is_live else "demo",
                "tool_calls": [],
                "suggestions": [f"Swap stay to {shown[0]['name']}", f"Show 5-star hotels in {trip.destination.title()}"],
            }

        # Check spot modifications: changes in visiting spots, remove spot, swap spot
        is_change_spots = (
            any(
                phrase in lowered
                for phrase in (
                    "change visiting spot", "change visiting spots", "changes in visiting spots",
                    "do changes in visiting spots", "change spot", "change spots", "change stop",
                    "change stops", "change the spots", "update spots", "modify spots",
                    "rework spots", "different spots", "change places to visit", "change visiting places",
                    "change my spots", "change itinerary spots", "modify stops", "update stops",
                    "change day 1 spots", "change day 2 spots", "change day 3 spots",
                    "change visiting spots in chat", "do changes in visiting spots in chat",
                    "change places"
                )
            )
            and not wants_hotel
            and not wants_flight
        )

        is_remove_spot = (
            any(w in lowered for w in ("remove ", "delete ", "drop ", "take out ", "cancel spot", "exclude "))
            and not wants_hotel
            and not wants_flight
            and not is_change_spots
        )

        if is_change_spots:
            dest_clean = trip.destination.strip().lower()
            trip_now = data_service.get_trip(self.session, trip.id) or {}
            available_days = sorted({d.get("day_index", 1) for d in trip_now.get("days", [])}) or [1]
            day_num, _, day_label, dow_not_in_trip = _resolve_target_day_and_slot(
                lowered,
                trip_now.get("days", []),
                trip.start_date,
                default_day=available_days[0],
            )
            if dow_not_in_trip:
                dow_title = dow_not_in_trip.title()
                dest_title = trip.destination.replace("-", " ").title()
                return {
                    "message": f"Your **{dest_title}** itinerary currently has {len(available_days)} day(s) ({', '.join(f'Day {d}' for d in available_days)}), with no {dow_title} scheduled. Which of your existing days would you like me to update?",
                    "cards": [],
                    "pins": visuals_for_trip(self.session, trip_now)["pins"] if trip_now else [],
                    "trip": trip_now or None,
                    "trip_id": trip.id,
                    "provider": self.llm.status(),
                    "mode": "live" if self.llm.is_live else "demo",
                    "tool_calls": [],
                    "suggestions": [f"Change spots for Day {d}" for d in available_days[:3]],
                }
            if not day_num or day_num not in available_days:
                day_num = available_days[0]

            day_row = self.session.exec(
                select(TripDay).where(TripDay.trip_id == trip.id, TripDay.day_index == day_num)
            ).first()
            if not day_row:
                day_row = self.session.exec(
                    select(TripDay).where(TripDay.trip_id == trip.id).order_by(TripDay.day_index)
                ).first()

            current_day_stops = (
                self.session.exec(
                    select(TripStop).where(TripStop.trip_day_id == day_row.id).order_by(TripStop.sort_order)
                ).all()
                if day_row
                else []
            )
            used_in_day = {s.place_id for s in current_day_stops if s.place_id}

            all_places = data_service.list_places(self.session, destination=dest_clean, limit=50)
            from backend.database.famous_spots import get_famous_spots_for_destination
            famous = get_famous_spots_for_destination(dest_clean)

            candidate_pool = []
            seen_cand_ids = set()
            for p in all_places:
                if p["id"] not in used_in_day and p["id"] not in seen_cand_ids and p.get("category") != "hotel":
                    candidate_pool.append(p)
                    seen_cand_ids.add(p["id"])

            for s in famous:
                if s["id"] not in used_in_day and s["id"] not in seen_cand_ids and s.get("category") != "hotel":
                    candidate_pool.append(s)
                    seen_cand_ids.add(s["id"])

            if not candidate_pool:
                candidate_pool = [p for p in all_places if p.get("category") != "hotel"] or famous

            chosen_spots = candidate_pool[:3]

            for c in chosen_spots:
                if not self.session.get(Place, c["id"]):
                    try:
                        self.session.add(Place(
                            id=c["id"],
                            name=c["name"],
                            category=c.get("category", "attraction"),
                            destination=dest_clean,
                            description=c.get("description", ""),
                            lat=c.get("lat", 0.0),
                            lon=c.get("lon", 0.0),
                            rating=c.get("rating", 4.8),
                            review_count=c.get("reviews_count", 250),
                            address=c.get("address", ""),
                            photos=c.get("photos", []),
                            tags=c.get("tags", []),
                            source="curated",
                        ))
                        self.session.commit()
                    except Exception:
                        self.session.rollback()

            place_ids = [c["id"] for c in chosen_spots]
            notes = [f"Visiting {c['name']} ({c.get('category', 'attraction')})" for c in chosen_spots]
            updated_trip = data_service.update_day_stops(
                self.session,
                trip_id=trip.id,
                day_index=day_num,
                place_ids=place_ids,
                notes_list=notes,
            )

            detail = updated_trip or data_service.get_trip(self.session, trip.id)
            visuals = visuals_for_trip(self.session, detail or {})
            cards = [_place_card(c, c.get("category", "attraction"), day_index=day_num, is_added=True) for c in chosen_spots]

            schedule_lines = []
            slot_names = ["Morning", "Afternoon", "Evening"]
            for idx, c in enumerate(chosen_spots):
                slot = slot_names[idx] if idx < len(slot_names) else f"Stop {idx+1}"
                schedule_lines.append(f"- **{slot}**: **{c['name']}** ({c.get('category', 'attraction').title()}) — {c.get('description', '')[:120]}")

            return {
                "message": (
                    f"I've updated the visiting spots for **Day {day_num}** in your **{trip.destination.title()}** itinerary!\n\n"
                    f"### 📍 New Day {day_num} Visiting Spots:\n"
                    + "\n".join(schedule_lines)
                    + "\n\nYour itinerary database, map pins, and sequential transit routes have been refreshed. You can view the full itinerary or let me know if you want to swap any of these."
                ),
                "cards": cards,
                "pins": visuals["pins"],
                "trip": detail,
                "trip_id": trip.id,
                "provider": self.llm.status(),
                "mode": "live" if self.llm.is_live else "demo",
                "tool_calls": [
                    {
                        "name": "update_day_visiting_spots",
                        "arguments": {"trip_id": trip.id, "day_index": day_num, "place_ids": place_ids},
                    }
                ],
                "suggestions": [
                    f"Show Day {day_num} route on map",
                    f"Change spots for Day {day_num + 1}" if day_num < len(available_days) else "Show boutique hotels",
                    "Show all available flights",
                    "Add a coffee shop on Day 1",
                ],
            }

        if is_remove_spot:
            trip_now = data_service.get_trip(self.session, trip.id) or {}
            all_stops = []
            for d in trip_now.get("days", []):
                for s in d.get("stops", []):
                    all_stops.append((d.get("day_index", 1), s))

            target_stop = None
            target_day_idx = 1
            for day_idx, s in all_stops:
                p_name = _normalise_text(s.get("place", {}).get("name") or s.get("notes") or "")
                if p_name and p_name in lowered:
                    target_stop = s
                    target_day_idx = day_idx
                    break

            if target_stop and target_stop.get("id"):
                stop_id = target_stop["id"]
                stop_name = target_stop.get("place", {}).get("name") or "the spot"
                updated_trip = data_service.remove_stop(self.session, trip_id=trip.id, stop_id=stop_id)
                detail = updated_trip or data_service.get_trip(self.session, trip.id)
                visuals = visuals_for_trip(self.session, detail or {})
                return {
                    "message": f"I've removed **{stop_name}** from Day {target_day_idx} of your itinerary. The sequential route lines and map pins have been updated in your database.",
                    "cards": visuals["cards"],
                    "pins": visuals["pins"],
                    "trip": detail,
                    "trip_id": trip.id,
                    "provider": self.llm.status(),
                    "mode": "live" if self.llm.is_live else "demo",
                    "tool_calls": [{"name": "remove_stop_from_trip", "arguments": {"trip_id": trip.id, "stop_id": stop_id}}],
                    "suggestions": [
                        f"Show Day {target_day_idx} route on map",
                        f"Add a new spot to Day {target_day_idx}",
                        "Show boutique hotels",
                    ],
                }

        # Check specific cuisines, amenities, and Google Maps intents
        SPECIFIC_CUISINES = [
            "indian", "thai", "italian", "mexican", "chinese", "japanese", "sushi", "korean",
            "vietnamese", "french", "spanish", "tapas", "greek", "mediterranean", "lebanese",
            "turkish", "ethiopian", "vegan", "vegetarian", "halal", "kosher", "bbq", "barbecue",
            "seafood", "steakhouse", "pizza", "burger", "ramen", "tacos", "dim sum", "dumpling",
            "biryani", "curry", "punjabi", "mughlai", "south indian", "north indian",
        ]

        SPECIFIC_AMENITIES = {
            "pharmacy": ["pharmacy", "chemist", "drugstore"],
            "hospital": ["hospital", "clinic", "urgent care", "emergency room", "medical center", "doctor"],
            "salon": [
                "saloon", "saloons", "salon", "salons", "hair salon", "haircut", "barber", "barbershop",
                "hair stylist", "hairdresser", "beauty salon", "beauty parlor", "beauty parlour",
                "nail salon", "spa", "massage", "wellness", "facial", "grooming"
            ],
            "bar": ["rooftop bar", "cocktail bar", "speakeasy", "nightclub", "pub", "brewery", "wine bar", "club", "bar"],
            "gym": [
                "gym", "gyms", "fitness center", "fitness centers", "fitness", "workout",
                "crossfit", "health club", "fitness club", "bodybuilding", "gymnasium"
            ],
            "grocery": ["supermarket", "grocery store", "convenience store"],
            "car_rental": [
                "rent a car", "rent car", "rental car", "rental cars", "car rental", "car rentals",
                "car hire", "hire a car", "rent a vehicle", "car rental agency", "car rental agencies",
                "hire car", "renting a car"
            ],
        }

        detected_cuisine: str | None = None
        for c in SPECIFIC_CUISINES:
            if re.search(rf"\b{re.escape(c)}\b", lowered):
                detected_cuisine = c
                break

        detected_amenity_cat: str | None = None
        detected_amenity_term: str | None = None
        for cat, terms in SPECIFIC_AMENITIES.items():
            for t in terms:
                if re.search(rf"\b{re.escape(t)}\b", lowered):
                    detected_amenity_cat = cat
                    detected_amenity_term = t
                    break
            if detected_amenity_cat:
                break

        is_gmaps_explicit = any(w in lowered for w in ("google maps", "google map", "gmaps", "scraped", "scrape", "live search"))

        # Check coffee / cafe / dining / attraction intents
        wants_coffee = any(w in lowered for w in ("coffee", "cafe", "café", "espresso", "latte", "cappuccino", "brew", "breakfast", "bakery", "tea house"))
        wants_food = bool(detected_cuisine) or (not wants_coffee and any(w in lowered for w in ("restaurant", "dinner", "lunch", "food", "dining", "eat", "meal", "cuisine")))
        wants_activity = any(w in lowered for w in ("museum", "attraction", "sight", "activity", "monument", "landmark", "park", "beach", "safari", "tour"))
        wants_amenity = bool(detected_amenity_cat)
        is_add_action = any(w in lowered for w in ("add ", "include ", "put ", "insert ", "schedule ", "add a ", "add an ", "add the "))

        dest_clean = trip.destination.strip().lower()

        # Seed the curated catalogue once, then resolve an explicitly named spot.
        try:
            data_service.get_recommended_places(self.session, destination=dest_clean, limit=20)
        except Exception:
            pass

        all_places = data_service.list_places(self.session, destination=dest_clean, limit=50)
        named_place = _match_requested_item(lowered, all_places) if is_add_action else None

        if is_add_action and not named_place:
            unrec_spot = _extract_unrecognized_spot_name(message)
            if unrec_spot:
                # Try finding in DB first
                db_p = self.session.exec(
                    select(Place).where(
                        (Place.destination == dest_clean) &
                        Place.name.ilike(f"%{unrec_spot}%")
                    )
                ).first()
                if not db_p:
                    db_p = self.session.exec(
                        select(Place).where(Place.name.ilike(f"%{unrec_spot}%"))
                    ).first()
                if db_p:
                    named_place = data_service.place_dict(db_p)
                else:
                    try:
                        from scrapers.google_maps_adapter import search_google_maps_live
                        scraped_spots = search_google_maps_live(
                            query=unrec_spot,
                            location=trip.destination,
                            session=self.session,
                            max_results=3,
                        )
                        if scraped_spots:
                            named_place = data_service.place_dict(scraped_spots[0])
                            is_gmaps_explicit = True
                    except Exception as exc:
                        logger.warning("Live search for %s failed: %s", unrec_spot, exc)

        # A named place is enough to treat the message as an add request even
        # when it does not contain a category keyword ("add Burj Khalifa...").
        if named_place and not (wants_coffee or wants_food or wants_activity or wants_amenity):
            if named_place.get("category") == "cafe":
                wants_coffee = True
            elif named_place.get("category") == "restaurant":
                wants_food = True
            elif named_place.get("category") in SPECIFIC_AMENITIES:
                detected_amenity_cat = named_place.get("category")
                wants_amenity = True
            else:
                wants_activity = True

        if wants_coffee or wants_food or wants_activity or wants_amenity or is_gmaps_explicit:
            trip_now = data_service.get_trip(self.session, trip.id) or {}
            available_days = sorted({d.get("day_index", 1) for d in trip_now.get("days", [])}) or [1]

            target_cat = named_place.get("category", "") if named_place else (detected_amenity_cat or "")
            day_num, target_slot, day_label, dow_not_in_trip = _resolve_target_day_and_slot(
                lowered,
                trip_now.get("days", []),
                trip.start_date,
                default_day=1,
                category=target_cat,
            )

            if dow_not_in_trip:
                day_range_desc = ""
                if trip_now.get("days"):
                    days_list = trip_now["days"]
                    f_date = days_list[0].get("date")
                    l_date = days_list[-1].get("date")
                    if f_date and l_date:
                        try:
                            f_dt = datetime.fromisoformat(f_date)
                            l_dt = datetime.fromisoformat(l_date)
                            day_range_desc = f"from **{f_dt.strftime('%A, %b %d')}** to **{l_dt.strftime('%A, %b %d')}** "
                        except Exception:
                            pass

                dow_title = dow_not_in_trip.title()
                dest_title = trip.destination.replace("-", " ").title()
                spot_name = named_place["name"] if named_place else (_extract_unrecognized_spot_name(message) or "the spot")

                return {
                    "message": (
                        f"No, there is **no {dow_title}** in your current trip schedule. Your **{dest_title}** itinerary runs for **{len(available_days)} days** {day_range_desc}"
                        f"({', '.join(f'Day {d}' for d in available_days)}).\n\n"
                        f"Since your trip does not include {dow_title}, would you like me to:\n"
                        f"1. Add **{spot_name}** to one of your existing evenings (such as {', '.join(f'Day {d}' for d in available_days[:3])})?\n"
                        f"2. Or extend your itinerary to include {dow_title}?"
                    ),
                    "cards": [_place_card(named_place, named_place.get("category", "attraction"))] if named_place else [],
                    "pins": visuals_for_trip(self.session, trip_now)["pins"] if trip_now else [],
                    "trip": trip_now or None,
                    "trip_id": trip.id,
                    "provider": self.llm.status(),
                    "mode": "live" if self.llm.is_live else "demo",
                    "tool_calls": [],
                    "suggestions": [
                        f"Add {spot_name} to Day {d} evening" for d in available_days[:3]
                    ] + [f"Extend trip to include {dow_title}"],
                }

            if not day_num or day_num not in available_days:
                options = ", ".join(f"Day {d}" for d in available_days)
                return {
                    "message": f"Your {trip.destination.title()} itinerary currently has {len(available_days)} day(s) ({options}). Which of those days should I use?",
                    "cards": [],
                    "pins": visuals_for_trip(self.session, trip_now)["pins"] if trip_now else [],
                    "trip": trip_now or None,
                    "trip_id": trip.id,
                    "provider": self.llm.status(),
                    "mode": "live" if self.llm.is_live else "demo",
                    "tool_calls": [],
                    "suggestions": [f"Add it to Day {d}" for d in available_days[:3]],
                }

            if named_place and named_place.get("category"):
                category_target = named_place["category"]
            elif detected_amenity_cat:
                category_target = detected_amenity_cat
            elif wants_coffee:
                category_target = "cafe"
            elif wants_food or detected_cuisine:
                category_target = "restaurant"
            else:
                category_target = "attraction"

            # Determine whether this is a Google Maps query
            is_live_gmaps_request = bool(detected_cuisine or detected_amenity_cat or is_gmaps_explicit)

            hotel_obj = trip_now.get("hotel") or {}
            if not hotel_obj and trip.hotel_id:
                h_row = self.session.get(Hotel, trip.hotel_id)
                if h_row:
                    hotel_obj = data_service.hotel_dict(h_row)
            if not hotel_obj and trip.hotels_json and len(trip.hotels_json) > 0:
                hotel_obj = trip.hotels_json[0]

            has_booked_hotel = bool(trip.hotel_id or (hotel_obj and (hotel_obj.get("name") or hotel_obj.get("id"))))
            hotel_name = hotel_obj.get("name") if hotel_obj else ("your hotel" if has_booked_hotel else None)
            hotel_lat = hotel_obj.get("lat") if hotel_obj else None
            hotel_lon = hotel_obj.get("lon") if hotel_obj else None

            search_location = trip.destination
            if is_hotel_anchor and has_booked_hotel:
                search_location = f"{hotel_name}, {trip.destination}"
            elif not is_hotel_anchor:
                # Check if query names a specific neighborhood/locality (e.g. "in Dharampeth", "near Times Square")
                area_match = re.search(r"\b(?:in|around|near|at)\s+([a-zA-Z0-9\s]{3,30}?)(?:\s+(?:for|on|day|\b)|$)", lowered)
                if area_match:
                    cand_area = area_match.group(1).strip()
                    stop_words = {"my hotel", "the hotel", "our hotel", "hotel", "today", "tomorrow", "morning", "afternoon", "evening", "night", "saturday", "sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "this trip", "my trip", "the city", "our stay", "my stay"}
                    if cand_area.lower() not in stop_words:
                        if cand_area.lower() in trip.destination.lower():
                            search_location = trip.destination
                        else:
                            search_location = f"{cand_area.title()}, {trip.destination}"

            if detected_cuisine:
                search_query = f"{detected_cuisine} restaurant"
                term_display = f"{detected_cuisine.title()} dining spots"
                if is_hotel_anchor and has_booked_hotel:
                    category_label = f"authentic {detected_cuisine.title()} dining spots near your stay at **{hotel_name}**"
                elif is_hotel_anchor and not has_booked_hotel:
                    category_label = f"authentic {detected_cuisine.title()} dining spots"
                else:
                    category_label = f"authentic {detected_cuisine.title()} dining spots"
            elif detected_amenity_cat:
                if detected_amenity_cat == "salon":
                    term_display = "salon & grooming"
                    search_query = "hair salon" if detected_amenity_term in ("saloon", "saloons", "salon", "salons", "barber") else (detected_amenity_term or detected_amenity_cat)
                elif detected_amenity_cat == "car_rental":
                    term_display = "car rental agencies"
                    search_query = "car rental agency"
                elif detected_amenity_cat == "gym":
                    term_display = "gyms & fitness centers"
                    search_query = "gym" if detected_amenity_term in ("gym", "gyms", "fitness") else (detected_amenity_term or "gym")
                else:
                    term_display = detected_amenity_term or detected_amenity_cat
                    search_query = detected_amenity_term or detected_amenity_cat

                if is_hotel_anchor and has_booked_hotel:
                    category_label = f"closest {term_display} near your stay at **{hotel_name}**"
                elif is_hotel_anchor and not has_booked_hotel:
                    category_label = f"top-rated {term_display}"
                else:
                    category_label = f"{term_display}"
            elif is_gmaps_explicit:
                cleaned_q = re.sub(r"\b(google maps|google map|gmaps|where can i get|find me|show me|search for|places|spots|near my hotel|near the hotel)\b", "", lowered).strip()
                search_query = cleaned_q or "top attractions"
                category_label = "places discovered via Google Maps"
            else:
                search_query = ""
                category_label = "specialty coffee spots" if wants_coffee else ("dining spots" if wants_food else "attractions")

            candidates = []
            if is_live_gmaps_request:
                # 1. First check if DB already has places matching this specific cuisine/amenity
                match_key = (detected_cuisine or detected_amenity_term or detected_amenity_cat or search_query).lower()
                all_cached = data_service.list_places(self.session, destination=dest_clean, limit=100)
                matched_candidates = []
                for p in all_cached:
                    p_tags = p.get("tags") or []
                    p_tags_str = " ".join(p_tags).lower() if isinstance(p_tags, list) else str(p_tags).lower()
                    p_name = (p.get("name") or "").lower()
                    p_desc = (p.get("description") or "").lower()
                    # When a specific cuisine/amenity is detected, require it to match in
                    # name/description/tags so we don't return every place of that category.
                    # For general category requests (no cuisine), fall back to category match.
                    category_match = p.get("category") == category_target
                    if match_key in p_name or match_key in p_desc or match_key in p_tags_str or (
                        not detected_cuisine and not detected_amenity_cat and category_match
                    ):
                        matched_candidates.append(p)

                if len(matched_candidates) >= 3:
                    candidates = matched_candidates
                else:
                    try:
                        from scrapers.google_maps_adapter import search_google_maps_live
                        scraped_models = search_google_maps_live(
                            query=search_query,
                            location=search_location,
                            category=category_target,
                            max_results=5,
                            session=self.session,
                            near_lat=hotel_lat,
                            near_lon=hotel_lon,
                        )
                        candidates = [data_service.place_dict(p) for p in scraped_models] if scraped_models else matched_candidates
                    except Exception as exc:
                        logger.warning("Live Google Maps query failed (%s); using matched candidates", exc)
                        candidates = matched_candidates

                if not candidates:
                    if is_hotel_anchor and hotel_lat and hotel_lon:
                        # First try restaurants near the hotel (1km radius)
                        all_cats = data_service.list_places(self.session, destination=dest_clean, category=category_target, limit=50)
                        candidates = _places_near_coords(all_cats, hotel_lat, hotel_lon, radius_km=1.0)
                        if detected_cuisine:
                            cuisine_key = detected_cuisine.lower()
                            candidates = [
                                p for p in candidates
                                if cuisine_key in (p.get("name") or "").lower()
                                or cuisine_key in (p.get("description") or "").lower()
                                or cuisine_key in " ".join(p.get("tags") or []).lower()
                            ]
                        # If nothing near the hotel, expand to 5km radius
                        if not candidates:
                            candidates = _places_near_coords(all_cats, hotel_lat, hotel_lon, radius_km=5.0)
                            if detected_cuisine:
                                cuisine_key = detected_cuisine.lower()
                                candidates = [
                                    p for p in candidates
                                    if cuisine_key in (p.get("name") or "").lower()
                                    or cuisine_key in (p.get("description") or "").lower()
                                    or cuisine_key in " ".join(p.get("tags") or []).lower()
                                ]
                        # Final fallback: entire city
                        if not candidates:
                            all_cats = data_service.list_places(self.session, destination=dest_clean, category=category_target, limit=20)
                            if detected_cuisine:
                                cuisine_key = detected_cuisine.lower()
                                candidates = [
                                    p for p in all_cats
                                    if cuisine_key in (p.get("name") or "").lower()
                                    or cuisine_key in (p.get("description") or "").lower()
                                    or cuisine_key in " ".join(p.get("tags") or []).lower()
                                ][:6]
                            else:
                                candidates = all_cats[:6]
                    elif detected_cuisine:
                        all_cats = data_service.list_places(self.session, destination=dest_clean, category=category_target, limit=20)
                        cuisine_key = detected_cuisine.lower()
                        candidates = [
                            p for p in all_cats
                            if cuisine_key in (p.get("name") or "").lower()
                            or cuisine_key in (p.get("description") or "").lower()
                            or cuisine_key in " ".join(p.get("tags") or []).lower()
                        ][:6]
                    else:
                        candidates = data_service.list_places(self.session, destination=dest_clean, category=category_target, limit=6)
            else:
                candidates = data_service.list_places(self.session, destination=dest_clean, category=category_target, limit=10)
                if not candidates and wants_coffee:
                    candidates = data_service.list_places(self.session, destination=dest_clean, query="coffee", limit=10)
                if not candidates:
                    from backend.database.famous_spots import get_famous_spots_for_destination
                    famous = get_famous_spots_for_destination(dest_clean)
                    if wants_coffee:
                        candidates = [s for s in famous if s.get("category") == "cafe" or any(k in s.get("name", "").lower() for k in ("coffee", "cafe", "tea"))]
                    elif wants_food:
                        candidates = [s for s in famous if s.get("category") == "restaurant"]
                    else:
                        candidates = [s for s in famous if s.get("category") in {"attraction", "culture", "activity", "nature"}]

                if not candidates:
                    candidates = data_service.list_places(self.session, destination=dest_clean, limit=6)

            # If the user named a specific spot, it must be the one we use.
            if named_place and all(c.get("id") != named_place.get("id") for c in candidates):
                candidates = [named_place, *candidates]
            elif named_place:
                candidates = [named_place, *[c for c in candidates if c.get("id") != named_place.get("id")]]

            if candidates:
                if is_add_action or "add" in lowered:
                    day_view = next((d for d in trip_now.get("days", []) if d.get("day_index") == day_num), {})
                    existing_in_day = {
                        s.get("place_id") for s in day_view.get("stops", []) if s.get("place_id")
                    }

                    # Prefer the requested spot; otherwise pick the next best
                    # option that is not already scheduled that day.
                    chosen = named_place or next(
                        (c for c in candidates if c.get("id") not in existing_in_day),
                        candidates[0],
                    )

                    if chosen.get("id") in existing_in_day:
                        return {
                            "message": f"**{chosen['name']}** is already part of {day_label}. Here are a few other {category_label} you could add instead:",
                            "cards": [
                                _place_card(c, category_target, day_index=day_num)
                                for c in candidates
                                if c.get("id") != chosen.get("id")
                            ][:3],
                            "pins": visuals_for_trip(self.session, trip_now)["pins"] if trip_now else [],
                            "trip": trip_now or None,
                            "trip_id": trip.id,
                            "provider": self.llm.status(),
                            "mode": "live" if self.llm.is_live else "demo",
                            "tool_calls": [],
                            "suggestions": [
                                f"Add {c['name']} to {day_label}"
                                for c in candidates
                                if c.get("id") != chosen.get("id")
                            ][:2],
                        }

                    # Ensure Place exists in database before linking the stop.
                    if not self.session.get(Place, chosen["id"]):
                        try:
                            self.session.add(Place(
                                id=chosen["id"],
                                name=chosen["name"],
                                category=chosen.get("category", category_target),
                                destination=dest_clean,
                                description=chosen.get("description", ""),
                                lat=chosen.get("lat", 0.0),
                                lon=chosen.get("lon", 0.0),
                                rating=chosen.get("rating", 4.8),
                                review_count=chosen.get("reviews_count", 100),
                                address=chosen.get("address", ""),
                                photos=chosen.get("photos", []),
                                tags=chosen.get("tags", []),
                                source="curated",
                            ))
                            self.session.commit()
                        except Exception:
                            self.session.rollback()

                    time_slot = target_slot or ("morning" if wants_coffee else ("evening" if any(w in lowered for w in ("dinner", "night", "drinks")) else "afternoon"))
                    if chosen.get("category") == "bar" or category_target == "bar":
                        notes = f"Evening drinks & relaxation at {chosen['name']}"
                        kind_label = "bar"
                    elif wants_coffee:
                        notes = f"Specialty coffee & breakfast at {chosen['name']}"
                        kind_label = "specialty coffee spot"
                    elif wants_food:
                        notes = f"Dining at {chosen['name']}"
                        kind_label = "dining spot"
                    elif wants_amenity:
                        notes = f"Visit {chosen['name']}"
                        kind_label = f"{category_target}"
                    else:
                        notes = f"Visiting {chosen['name']}"
                        kind_label = "attraction"

                    updated = data_service.add_stop(
                        self.session,
                        trip_id=trip.id,
                        day_index=day_num,
                        place_id=chosen["id"],
                        time_slot=time_slot,
                        notes=notes,
                    )
                    if not updated:
                        return {
                            "message": f"I couldn't add **{chosen['name']}** to {day_label}. Please try again.",
                            "cards": [], "pins": [], "trip": trip_now or None,
                            "trip_id": trip.id,
                            "provider": self.llm.status(),
                            "mode": "live" if self.llm.is_live else "demo",
                            "tool_calls": [],
                            "suggestions": dynamic_suggestions_for_dest(trip.destination),
                        }

                    detail = data_service.get_trip(self.session, trip.id)
                    visuals = visuals_for_trip(self.session, detail or {})
                    place_card = _place_card(chosen, category_target, day_index=day_num, is_added=True)
                    extra_cards = [place_card]
                    for alt in [c for c in candidates if c.get("id") != chosen.get("id")][:2]:
                        extra_cards.append(_place_card(alt, category_target))

                    tool_calls_performed = []
                    if is_live_gmaps_request:
                        tool_calls_performed.append({
                            "name": "search_google_maps_places",
                            "arguments": {"query": search_query, "location": search_location, "category": category_target},
                        })
                    tool_calls_performed.append({"name": "add_stop", "arguments": {"place_id": chosen["id"], "day_index": day_num}})

                    prefix = ""
                    if any(w in lowered for w in ("is there any", "is there a", "if yes", "if so")):
                        date_sub = day_label.split('(')[-1].rstrip(')') if '(' in day_label else day_label
                        prefix = f"Yes, there is! Day {day_num} of your trip is {date_sub}.\n\n"

                    source_note = " from Google Maps" if is_live_gmaps_request else ""
                    hotel_note = " *(Note: You haven't selected or booked a hotel yet, so this was chosen from the top recommendations. Once you pick a stay, we can swap to the closest option near your hotel!)*" if (is_hotel_anchor and not has_booked_hotel) else ""
                    default_add_msg = f"{prefix}I've added **{chosen['name']}** to {day_label} ({time_slot}) of your {trip.destination.title()} itinerary{source_note} as a {kind_label}.{hotel_note} Your {day_label} plan and sequential map routes have been updated."
                    concierge_msg = await self._compose_concierge_response(
                        user_message=message,
                        action_summary=f"Added {chosen['name']} to {day_label} ({time_slot}) as a {kind_label}",
                        items=[chosen] + [c for c in candidates if c.get("id") != chosen.get("id")],
                        active_trip=detail,
                        fallback_text=default_add_msg,
                    )
                    if prefix and not concierge_msg.lower().startswith("yes"):
                        concierge_msg = f"{prefix}{concierge_msg}"
                    if day_label.lower() not in concierge_msg.lower():
                        concierge_msg = f"{default_add_msg}\n\n{concierge_msg}"

                    return {
                        "message": concierge_msg,
                        "cards": extra_cards,
                        "pins": visuals["pins"],
                        "trip": detail,
                        "trip_id": trip.id,
                        "provider": self.llm.status(),
                        "mode": "live" if self.llm.is_live else "demo",
                        "tool_calls": tool_calls_performed,
                        "suggestions": [
                            f"Show {day_label} route on map",
                            f"Suggest top dinner spots in {trip.destination.title()}",
                            f"Show boutique hotels in {trip.destination.title()}",
                        ],
                    }
                else:
                    # Suggestions path
                    cards = [_place_card(c, category_target, day_index=day_num) for c in candidates[:4]]
                    detail = data_service.get_trip(self.session, trip.id)
                    base_pins = visuals_for_trip(self.session, detail or {})["pins"] if detail else []

                    if is_live_gmaps_request:
                        live_pins = []
                        for c in candidates[:5]:
                            lat = c.get("lat") or 0.0
                            lon = c.get("lon") or 0.0
                            if lat and lon:
                                live_pins.append({
                                    "id": c["id"],
                                    "name": c["name"],
                                    "category": c.get("category", category_target),
                                    "lat": lat,
                                    "lon": lon,
                                    "rating": c.get("rating", 4.8),
                                    "address": c.get("address", ""),
                                    "photo": (c.get("photos") or [""])[0] if c.get("photos") else "",
                                    "day_index": day_num,
                                    "label": "📍",
                                    "trip_id": trip.id,
                                    "description": c.get("description", ""),
                                    "is_itinerary_stop": False,
                                    "distance_meters": c.get("distance_meters"),
                                })
                        pins = live_pins + base_pins
                        if detected_amenity_cat == "car_rental":
                            action_prompt = f"You can rent a vehicle or pick up a car from these locations for {day_label}. Click below for details or say 'add [agency] to {day_label}' to schedule your pickup:"
                        else:
                            action_prompt = f"Click below or let me know if you would like me to add one to {day_label}:"

                        dest_display = trip.destination.replace('-', ' ').title()
                        if is_hotel_anchor and not has_booked_hotel:
                            default_gmaps_msg = (
                                f"You haven't selected or booked a hotel for your trip to **{dest_display}** yet. "
                                f"To help you stay on track, here are the highest-rated {term_display} across **{dest_display}** discovered via Google Maps. "
                                f"Once you pick or book your stay, I can find options right at your doorstep! {action_prompt}"
                            )
                            concierge_action_summary = (
                                f"User asked for {term_display} from hotel, but no hotel is selected/booked yet on this trip. "
                                f"Informed the user that they haven't selected a hotel, recommended top-rated {term_display} in {dest_display}, "
                                f"and suggested selecting a hotel to get doorstep proximity."
                            )
                        elif is_hotel_anchor and has_booked_hotel:
                            default_gmaps_msg = (
                                f"Here are the closest {term_display} near your stay at **{hotel_name}** in **{dest_display}** "
                                f"discovered live via Google Maps for {day_label}. {action_prompt}"
                            )
                            concierge_action_summary = f"Discovered closest {term_display} near booked stay {hotel_name} in {dest_display} for {day_label}"
                        else:
                            default_gmaps_msg = (
                                f"Here are the highest-rated {category_label} in **{dest_display}** "
                                f"discovered live via Google Maps for {day_label}. {action_prompt}"
                            )
                            concierge_action_summary = f"Discovered highest-rated {category_label} for {day_label} via Google Maps"

                        concierge_sugg_msg = await self._compose_concierge_response(
                            user_message=message,
                            action_summary=concierge_action_summary,
                            items=candidates,
                            active_trip=detail,
                            fallback_text=default_gmaps_msg,
                        )
                        if is_hotel_anchor and not has_booked_hotel:
                            if not any(k in concierge_sugg_msg.lower() for k in ("not selected", "haven't selected", "have not selected", "no hotel", "not booked", "haven't booked")):
                                concierge_sugg_msg = f"{default_gmaps_msg}\n\n{concierge_sugg_msg}"
                        elif detected_amenity_cat == "car_rental":
                            if "car rental" not in concierge_sugg_msg.lower():
                                concierge_sugg_msg = f"{default_gmaps_msg}\n\n{concierge_sugg_msg}"
                            elif day_label.lower() not in concierge_sugg_msg.lower():
                                concierge_sugg_msg = f"{concierge_sugg_msg}\n\n*(Car rental pickup available on {day_label})*"
                        elif day_label.lower() not in concierge_sugg_msg.lower():
                            concierge_sugg_msg = f"**{category_label.title()} for {day_label}**:\n\n{concierge_sugg_msg}"

                        if is_hotel_anchor and not has_booked_hotel:
                            dynamic_suggs = [
                                f"🏨 Show boutique hotels in {dest_display}",
                                f"Add {candidates[0].get('name', 'Spot')} to {day_label}" if candidates else f"Show {day_label} route",
                                f"Find more {term_display} on Google Maps",
                            ]
                        else:
                            dynamic_suggs = [
                                f"Add {candidates[0].get('name', 'Spot')} to {day_label}" if candidates else f"Show {day_label} route",
                                f"Add {candidates[1].get('name', 'Spot')} to {day_label}" if len(candidates) > 1 else "Show route map",
                                f"Find more {category_label} on Google Maps",
                            ]

                        return {
                            "message": concierge_sugg_msg,
                            "cards": cards,
                            "pins": pins,
                            "trip": detail,
                            "trip_id": trip.id,
                            "provider": self.llm.status(),
                            "mode": "live" if self.llm.is_live else "demo",
                            "tool_calls": [
                                {
                                    "name": "search_google_maps_places",
                                    "arguments": {
                                        "query": search_query,
                                        "location": search_location,
                                        "category": category_target,
                                    },
                                }
                            ],
                            "suggestions": dynamic_suggs,
                        }
                    else:
                        default_curated_msg = f"Here are the highest-rated {category_label} in {trip.destination.title()} for your trip. Click below or let me know if you would like me to add one to {day_label}:"
                        concierge_curated_msg = await self._compose_concierge_response(
                            user_message=message,
                            action_summary=f"Curated {category_label} in {trip.destination.title()} for {day_label}",
                            items=candidates,
                            active_trip=detail,
                            fallback_text=default_curated_msg,
                        )
                        if day_label.lower() not in concierge_curated_msg.lower():
                            concierge_curated_msg = f"**{category_label.title()} for {day_label}**:\n\n{concierge_curated_msg}"
                        return {
                            "message": concierge_curated_msg,
                            "cards": cards,
                            "pins": base_pins,
                            "trip": detail,
                            "trip_id": trip.id,
                            "provider": self.llm.status(),
                            "mode": "live" if self.llm.is_live else "demo",
                            "tool_calls": [{"name": "search_places", "arguments": {"category": category_target, "destination": trip.destination}}],
                            "suggestions": [
                                f"Add {candidates[0].get('name', 'Spot')} to {day_label}" if candidates else f"Show {day_label} route",
                                f"Add {candidates[1].get('name', 'Spot')} to {day_label}" if len(candidates) > 1 else "Show route map",
                            ],
                        }

        return None


def _summarise(result: Any) -> Any:
    if isinstance(result, dict):
        if "count" in result:
            return {"count": result["count"]}
        if "trip_id" in result:
            return {"trip_id": result["trip_id"], "days": result.get("days"), "stops": result.get("stops")}
        if "error" in result:
            return {"error": result["error"]}
        if "label" in result:
            return {"label": result["label"], "distance_km": result.get("distance_km")}
    return "ok"
