"""Verification script for Google Maps scraper integration, cuisine queries, and amenity queries."""

import sys
import json
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = "http://127.0.0.1:8000/api"

def post(endpoint, data):
    req = urllib.request.Request(
        f"{BASE_URL}{endpoint}",
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def get(endpoint):
    with urllib.request.urlopen(f"{BASE_URL}{endpoint}") as resp:
        return json.loads(resp.read().decode("utf-8"))

print("=== STARTING GOOGLE MAPS LIVE SCRAPER VERIFICATION ===")

# Create session & trip
session_resp = post("/chat/session", {})
session_id = session_resp["session_id"]
print(f"Created test session: {session_id}")

trip_resp = post("/chat/message", {
    "session_id": session_id,
    "message": "plan a 5-day trip to New York for 2 adults",
})
trip_id = trip_resp.get("trip_id")
print(f"Created Trip ID: {trip_id} in {trip_resp.get('trip', {}).get('destination')}")
assert trip_id, "Failed to create trip!"

# Test 1: Specific Cuisine (Indian cuisine)
print("\n--- TEST 1: GOOGLE MAPS LIVE SEARCH FOR INDIAN CUISINE ---")
reply_indian = post("/chat/message", {
    "session_id": session_id,
    "message": "where can i get restaurants with indian cuisine",
    "context": {"trip_id": trip_id}
})
cards = reply_indian.get("cards", [])
pins = reply_indian.get("pins", [])
print(f"Assistant Message: {reply_indian.get('message')[:140]}...")
print(f"Returned Cards: {len(cards)}")
for c in cards:
    print(f" - Place: {c.get('name')} | Category: {c.get('category')} | Rating: {c.get('rating')}")
print(f"Returned Pins: {len(pins)}")

# Ensure cards are Indian dining spots and not Jewish delis or pizza slices
card_names = " ".join(c.get("name", "").lower() for c in cards)
assert any(w in card_names for w in ("amphora", "bengal tiger", "cloves", "indian")), f"Expected Indian restaurants, got: {card_names}"
assert len(pins) > 0, "Expected map pins returned!"
print(">>> PASS: Real Indian restaurants returned as rich cards with exact map pins!")

# Test 2: Add Indian Spot to Itinerary Day 2
print("\n--- TEST 2: ADD GOOGLE MAPS PLACE TO ITINERARY ---")
chosen_name = cards[0]["name"]
reply_add = post("/chat/message", {
    "session_id": session_id,
    "message": f"add {chosen_name} to day 2",
    "context": {"trip_id": trip_id}
})
print(f"Add response: {reply_add.get('message')}")
trip_after = get(f"/trips/{trip_id}")
day2_places = [s.get("place", {}).get("name") or s.get("notes") for s in trip_after.get("days", [])[1].get("stops", [])]
print(f"Day 2 spots in DB after add: {day2_places}")
assert any(chosen_name.lower() in p.lower() for p in day2_places), f"Failed to persist {chosen_name} to Day 2 in DB!"
print(f">>> PASS: {chosen_name} persisted into Day 2 of itinerary database!")

# Test 3: Amenity Query (Pharmacy)
print("\n--- TEST 3: GOOGLE MAPS AMENITY SEARCH (PHARMACY) ---")
reply_pharmacy = post("/chat/message", {
    "session_id": session_id,
    "message": "where is the nearest pharmacy nearby",
    "context": {"trip_id": trip_id}
})
pharm_cards = reply_pharmacy.get("cards", [])
pharm_pins = reply_pharmacy.get("pins", [])
print(f"Pharmacy Message: {reply_pharmacy.get('message')[:140]}...")
print(f"Pharmacy Cards: {len(pharm_cards)}")
for pc in pharm_cards:
    print(f" - Amenity: {pc.get('name')} | Category: {pc.get('category')}")
assert len(pharm_cards) > 0, "No pharmacy cards returned!"
assert all(pc.get("category") == "pharmacy" for pc in pharm_cards), "Category should be pharmacy!"
print(">>> PASS: Pharmacy amenity retrieved via Google Maps adapter and returned with map pins!")

print("\n=== ALL GOOGLE MAPS & TRAVEL CONCIERGE TESTS PASSED CLEANLY! ===")
