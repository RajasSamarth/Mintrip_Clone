import sys
import json
import urllib.request
import urllib.error

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

print("=== STARTING FULL VERIFICATION SUITE ===")

# Create session
session_resp = post("/chat/session", {})
session_id = session_resp["session_id"]
print(f"Created session: {session_id}")

# Test 1: Guardrail against off-topic query "who won ipl last year"
print("\n--- TEST 1: OFF-TOPIC GUARDRAIL ---")
reply1 = post("/chat/message", {
    "session_id": session_id,
    "message": "who won ipl last year",
})
print("User: 'who won ipl last year'")
print(f"Assistant mode: {reply1.get('mode')}")
print(f"Assistant message excerpt: {reply1.get('message')[:160]}...")
assert "gujarat titans" not in reply1.get("message", "").lower(), "FAILED: Bot answered IPL trivia!"
assert any(w in reply1.get("message", "").lower() for w in ("concierge", "travel", "getaway", "journey")), "FAILED: Bot did not redirect to travel!"
print(">>> PASS: Off-topic query politely declined and redirected to travel!")

# Test 2: Trip creation
print("\n--- TEST 2: TRIP CREATION ---")
reply2 = post("/chat/message", {
    "session_id": session_id,
    "message": "plan a complete trip from delhi to new york from 16th dec to 24th dec for 3 adults",
})
trip_id = reply2.get("trip_id")
print(f"Created Trip ID: {trip_id}")
print(f"Trip Title: {reply2.get('trip', {}).get('title')}")
print(f"Days: {len(reply2.get('trip', {}).get('days', []))}")
assert trip_id, "FAILED: No trip_id generated!"
day1_stops_before = [s.get("place", {}).get("name") or s.get("notes") for s in reply2.get("trip", {}).get("days", [])[0].get("stops", [])]
print(f"Initial Day 1 spots: {day1_stops_before}")

# Test 3: Flight options
print("\n--- TEST 3: FLIGHT SEARCH ---")
reply3 = post("/chat/message", {
    "session_id": session_id,
    "message": "show me all available flights",
    "context": {"trip_id": trip_id}
})
cards3 = reply3.get("cards", [])
print(f"Flight cards returned: {len(cards3)}")
assert len(cards3) >= 10, f"FAILED: Expected >= 10 flight cards, got {len(cards3)}"
print(f"First flight: {cards3[0].get('airline')} - {cards3[0].get('flight_number')} - ${cards3[0].get('price_usd')}")
print(">>> PASS: Flight inventory returned in rich cards!")

# Test 4: Flight recommendation (Requirement 1)
print("\n--- TEST 4: FLIGHT RECOMMENDATION ---")
reply4 = post("/chat/message", {
    "session_id": session_id,
    "message": "which is recommended flight from this?",
    "context": {"trip_id": trip_id}
})
cards4 = reply4.get("cards", [])
print("User: 'which is recommended flight from this?'")
print(f"Number of cards returned: {len(cards4)}")
print(f"Message preview:\n{reply4.get('message')}")
assert len(cards4) in (1, 2), f"FAILED: Expected 1-2 recommended cards, but got {len(cards4)}!"
assert "recommended" in reply4.get("message", "").lower() or "best" in reply4.get("message", "").lower(), "FAILED: No recommendation rationale!"
print(">>> PASS: Flight recommendation gave personalized rationale and only 1-2 cards instead of 15-flight dump!")

# Test 5: Itinerary Spot Changes in chat persisting in DB (Requirement 3)
print("\n--- TEST 5: SPOT CHANGES PERSISTING IN DATABASE ---")
reply5 = post("/chat/message", {
    "session_id": session_id,
    "message": "do changes in visiting spots in chat",
    "context": {"trip_id": trip_id}
})
print("User: 'do changes in visiting spots in chat'")
print(f"Assistant reply:\n{reply5.get('message')}")

# Now query the trip directly from the database API to verify persistence
trip_from_db = get(f"/trips/{trip_id}")
day1_stops_after = [s.get("place", {}).get("name") or s.get("notes") for s in trip_from_db.get("days", [])[0].get("stops", [])]
print(f"\nDay 1 stops before: {day1_stops_before}")
print(f"Day 1 stops after (verified in DB): {day1_stops_after}")
assert day1_stops_after != day1_stops_before, "FAILED: Day 1 stops were not changed in the database!"
print(">>> PASS: Spot changes successfully mutated the database and verified on /trips/{id}!")

print("\n=== ALL 5 REQUIREMENTS VERIFIED SUCCESSFULLY! ===")
