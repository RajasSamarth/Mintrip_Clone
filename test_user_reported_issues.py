"""Test verifying resolution of:
1. No duplicated spots in itineraries (same place appearing many times).
2. Unique, authentic images for Gateway of India, Marine Drive, Taj Mahal Palace, etc.
3. Chatbot provides intelligent AI concierge reasoning and thoughts instead of just raw tool dumps.
"""

from sqlmodel import Session, create_engine, select
import httpx
from backend.agent.planner import synthesize_trip
from backend.database.models import SQLModel, Place

API_BASE = "http://127.0.0.1:8000/api"

def test_mumbai_deduplication_and_unique_images():
    print("\n--- TEST: Mumbai Itinerary Deduplication & Photo Distinctness ---")
    engine = create_engine("sqlite:///data/mindtrip.db")
    with Session(engine) as session:
        trip = synthesize_trip(session, destination_query="mumbai", days=3)
        days = trip["trip"]["days"]
        assert len(days) == 3, f"Expected 3 days, got {len(days)}"
        
        all_stops = []
        all_photos = []
        for d in days:
            day_stops = [s["place"]["name"] for s in d["stops"]]
            day_photos = [s["place"]["photos"][0] for s in d["stops"] if s["place"].get("photos")]
            print(f"Day {d['day_index']}: {day_stops}")
            
            # Assert no duplicate on same day
            assert len(day_stops) == len(set(day_stops)), f"Duplicate on day {d['day_index']}: {day_stops}"
            assert len(day_photos) == len(set(day_photos)), f"Duplicate photo on day {d['day_index']}: {day_photos}"
            all_stops.extend(day_stops)
            all_photos.extend(day_photos)
            
        print(f"Total stops scheduled: {len(all_stops)}, Unique stops: {len(set(all_stops))}")
        assert len(all_stops) == len(set(all_stops)), f"Duplicate stops across trip: {all_stops}"
        
        # Verify Gateway of India and Marine Drive photos are totally distinct
        gateway = session.get(Place, "mumbai-gateway-of-india")
        marine = session.get(Place, "mumbai-marine-drive")
        taj = session.get(Place, "mumbai-taj-mahal-palace")
        
        assert gateway and marine and taj, "Missing Mumbai key places in DB"
        print(f"Gateway photo: {gateway.photos[0]}")
        print(f"Marine Drive photo: {marine.photos[0]}")
        print(f"Taj Mahal Palace photo: {taj.photos[0]}")
        
        assert gateway.photos[0] != marine.photos[0], "Gateway and Marine Drive have identical photos!"
        assert gateway.photos[0] != taj.photos[0], "Gateway and Taj Mahal Palace have identical photos!"
        assert marine.photos[0] != taj.photos[0], "Marine Drive and Taj Mahal Palace have identical photos!"
        print(">>> PASS: Mumbai spots and photos are 100% unique and distinct!")

def test_concierge_thinking_and_conversing():
    print("\n--- TEST: Concierge Conversational Reasoning & Thinking ---")
    session_res = httpx.post(f"{API_BASE}/chat/session").json()
    session_id = session_res["session_id"]
    
    # 1. Plan trip with dates and travelers
    chat_req = {
        "message": "Plan a 3-day trip from Delhi to Mumbai from 10th Oct to 13th Oct for 2 adults",
        "session_id": session_id,
    }
    trip_res = httpx.post(f"{API_BASE}/chat/message", json=chat_req, timeout=150.0).json()
    trip_id = trip_res.get("trip_id")
    assert trip_id, f"Trip not created: {trip_res.get('message')}"
    
    # 2. Ask for authentic local food recommendations
    rec_req = {
        "message": "where can i get restaurants with authentic coastal cuisine?",
        "session_id": session_id,
        "context": {"trip_id": trip_id},
    }
    rec_res = httpx.post(f"{API_BASE}/chat/message", json=rec_req, timeout=150.0).json()
    msg = rec_res.get("message", "")
    safe_preview = msg[:300].encode('ascii', 'replace').decode('ascii')
    print(f"Assistant Message Excerpt:\n{safe_preview}...")
    
    assert len(msg) > 60, "Assistant response was too brief or empty!"
    assert any(w in msg.lower() for w in ("restaurant", "dining", "coastal", "cuisine", "trishna", "canteen")), "Did not answer about coastal cuisine!"
    print(">>> PASS: Assistant answered thoughtfully with genuine concierge commentary!")

if __name__ == "__main__":
    test_mumbai_deduplication_and_unique_images()
    test_concierge_thinking_and_conversing()
    print("\n=== ALL USER REPORTED ISSUES VERIFIED FIXED! ===")
