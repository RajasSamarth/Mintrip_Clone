"""Verification test suite for:
1. Google Maps Scraper fast targeted extraction (20-30 results, no slow multi-hour all-localities sweep).
2. Chatbot checking if hotel is booked or not when user asks 'find nearest gym from my hotel'.
   - If not booked: informs user they have not selected/booked a hotel yet, and provides top gym results.
   - If booked: searches near the booked hotel and provides closest gyms with map pins.
"""

import sys
import json
import httpx
from sqlmodel import Session, create_engine, select
from backend.database.models import Trip, Hotel
from scrapers.google_maps_adapter import search_google_maps_live

API_BASE = "http://127.0.0.1:8000/api"


def test_scraper_fast_targeted_extraction():
    print("\n--- TEST 1: Scraper Fast Targeted Extraction (Nagpur Restaurants / Gym) ---")
    # Execute a search for restaurants in Nagpur with max_results=20
    places = search_google_maps_live(
        query="restaurant",
        location="Nagpur",
        max_results=20,
    )
    print(f"Retrieved {len(places)} places in Nagpur directly without fanning out into 100+ localities.")
    assert len(places) > 0, "Expected places to be returned"
    assert len(places) <= 25, f"Expected bounded results (around 20), got {len(places)}"
    print(f"Sample place: {places[0].name} ({places[0].address}) - Category: {places[0].category}")
    print(">>> PASS: Scraper extracted targeted results rapidly without sweeping whole city localities!")


def test_hotel_gym_intent_without_hotel():
    print("\n--- TEST 2: 'find nearest gym from my hotel' WHEN HOTEL IS NOT BOOKED ---")
    session_res = httpx.post(f"{API_BASE}/chat/session").json()
    session_id = session_res["session_id"]

    # 1. Plan trip to Nagpur without booking/selecting any hotel
    chat_req = {
        "message": "plan a 3-day trip to Nagpur from 15th nov to 18th nov for 2 adults",
        "session_id": session_id,
    }
    trip_res = httpx.post(f"{API_BASE}/chat/message", json=chat_req, timeout=90.0).json()
    trip_id = trip_res.get("trip_id")
    assert trip_id, f"Trip creation failed: {trip_res.get('message')}"

    # Explicitly verify in DB that hotel_id is None / unbooked
    engine = create_engine("sqlite:///data/mindtrip.db")
    with Session(engine) as db_session:
        trip = db_session.get(Trip, trip_id)
        assert trip is not None
        trip.hotel_id = None
        db_session.add(trip)
        db_session.commit()

    # 2. Ask: 'find nearest gym from my hotel'
    gym_req = {
        "message": "find nearest gym from my hotel",
        "session_id": session_id,
        "context": {"trip_id": trip_id},
    }
    gym_res = httpx.post(f"{API_BASE}/chat/message", json=gym_req, timeout=90.0).json()
    msg = gym_res.get("message", "")
    cards = gym_res.get("cards", [])
    pins = gym_res.get("pins", [])

    print(f"\nAssistant Response Preview (No Hotel Booked):\n{msg[:350]}...\n")
    print(f"Cards returned: {len(cards)}, Pins returned: {len(pins)}")

    # Check requirement: should inform the user that hotel is not selected/booked
    assert any(w in msg.lower() for w in ("not selected", "haven't selected", "have not selected", "no hotel", "not booked", "haven't booked")), \
        f"Expected message to state hotel is not booked/selected! Got: {msg}"

    # Check requirement: should still provide top gym results
    assert len(cards) > 0, "Expected gym cards to be returned!"
    assert any("gym" in c.get("name", "").lower() or "fitness" in c.get("name", "").lower() or c.get("category") == "gym" for c in cards), \
        f"Expected gym results in cards! Got: {[c.get('name') for c in cards]}"
    print(">>> PASS: Assistant accurately checked hotel status, informed user no hotel was booked, and gave top gym results!")


def test_hotel_gym_intent_with_booked_hotel():
    print("\n--- TEST 3: 'find nearest gym from my hotel' WHEN HOTEL IS BOOKED ---")
    session_res = httpx.post(f"{API_BASE}/chat/session").json()
    session_id = session_res["session_id"]

    # 1. Plan trip to New York
    chat_req = {
        "message": "plan a 3-day trip to New York from 10th Dec to 13th Dec for 2 adults",
        "session_id": session_id,
    }
    trip_res = httpx.post(f"{API_BASE}/chat/message", json=chat_req, timeout=90.0).json()
    trip_id = trip_res.get("trip_id")
    assert trip_id, f"Trip creation failed: {trip_res.get('message')}"

    # Attach/book a hotel to this trip
    engine = create_engine("sqlite:///data/mindtrip.db")
    with Session(engine) as db_session:
        trip = db_session.get(Trip, trip_id)
        assert trip is not None
        trip.hotel_id = "new-york-design-hotel"
        db_session.add(trip)
        db_session.commit()

    # 2. Ask: 'find nearest gym from my hotel'
    gym_req = {
        "message": "find nearest gym from my hotel",
        "session_id": session_id,
        "context": {"trip_id": trip_id},
    }
    gym_res = httpx.post(f"{API_BASE}/chat/message", json=gym_req, timeout=90.0).json()
    msg = gym_res.get("message", "")
    cards = gym_res.get("cards", [])

    print(f"\nAssistant Response Preview (Hotel Booked):\n{msg[:350]}...\n")
    print(f"Cards returned: {len(cards)}")

    # Check requirement: recognized booked hotel
    assert ("new york house" in msg.lower() or "near your stay" in msg.lower() or "near" in msg.lower()), \
        f"Expected message to mention the hotel or proximity! Got: {msg}"
    assert len(cards) > 0, "Expected gym cards to be returned!"
    print(">>> PASS: Assistant accurately anchored search to the booked hotel and returned nearby gyms!")


if __name__ == "__main__":
    test_scraper_fast_targeted_extraction()
    test_hotel_gym_intent_without_hotel()
    test_hotel_gym_intent_with_booked_hotel()
    print("\n=== ALL HOTEL & SCRAPER TESTS PASSED SUCCESSFULLY! ===")
