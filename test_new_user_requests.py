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

print("=== STARTING VERIFICATION FOR BOTH NEW USER SCENARIOS ===")

# ==============================================================================
# SCENARIO 1: Car Rental Request for Day 6 in Existing Trip
# ==============================================================================
print("\n--- SCENARIO 1: CAR RENTAL ON DAY 6 ---")
s1_resp = post("/chat/session", {})
s1_id = s1_resp["session_id"]

# Create New York trip
trip_resp = post("/chat/message", {
    "session_id": s1_id,
    "message": "plan a complete trip from delhi to new york from 16th dec to 24th dec for 2 adults",
})
trip_id = trip_resp.get("trip_id")
print(f"Created Trip: {trip_id}")

# Send the user's exact input
prompt1 = "i want to rent a car for day 6. Give me informations from where i can get"
print(f"User: '{prompt1}'")
reply1 = post("/chat/message", {
    "session_id": s1_id,
    "message": prompt1,
    "context": {"trip_id": trip_id}
})

msg1 = reply1.get("message", "")
cards1 = reply1.get("cards", [])
pins1 = reply1.get("pins", [])

print(f"\nAssistant Response Preview:\n{msg1[:300]}...")
print(f"Cards returned: {len(cards1)}")
print(f"Pins returned: {len(pins1)}")

# Assertions for Scenario 1
assert "looking at your itinerary for new york" not in msg1.lower(), (
    "FAILED: Bot fell through to generic itinerary summary!"
)
assert any(w in msg1.lower() for w in ("car rental", "vehicle", "rent a car", "agency")), (
    f"FAILED: Bot did not recognize car rental intent! Message: {msg1}"
)
assert "day 6" in msg1.lower(), f"FAILED: Day 6 not mentioned in message! Message: {msg1}"
assert len(cards1) > 0, "FAILED: Expected rich car rental cards, got 0!"
print("First card:", cards1[0].get("name"), "-", cards1[0].get("address"))
print(">>> PASS SCENARIO 1: Car rental recognized for Day 6 and returned rich agency cards & pins!")

# ==============================================================================
# SCENARIO 2: Underspecified Destination "quiet days in the Swiss Alps" in New Chat
# ==============================================================================
print("\n--- SCENARIO 2: UNDERSPECIFIED DESTINATION (NO ASSUMED DATES / TRAVELERS) ---")
s2_resp = post("/chat/session", {})
s2_id = s2_resp["session_id"]

prompt2 = "quiet days in the Swiss Alps"
print(f"User in new chat: '{prompt2}'")
reply2 = post("/chat/message", {
    "session_id": s2_id,
    "message": prompt2,
})

msg2 = reply2.get("message", "")
trip2 = reply2.get("trip")
mode2 = reply2.get("mode")

print(f"\nAssistant Response:\n{msg2}")
print(f"Mode: {mode2}")
print(f"Trip created: {trip2}")

# Assertions for Scenario 2
assert trip2 is None, f"FAILED: Bot assumed dates/travelers and created trip unexpectedly! Trip: {trip2}"
assert "5 oct" not in msg2.lower() and "11 oct" not in msg2.lower(), (
    "FAILED: Bot assumed specific calendar dates (5 Oct - 11 Oct) without asking user!"
)
assert not ("2 adults" in msg2.lower() and "departing from zurich" in msg2.lower()), (
    "FAILED: Bot assumed '2 adults, departing from Zurich' without asking user!"
)
assert any(w in msg2.lower() for w in ("dates", "when are you", "preferred month", "duration")), (
    "FAILED: Bot did not ask user for their travel dates/duration!"
)
assert any(w in msg2.lower() for w in ("travelers", "who is traveling", "how many adults")), (
    "FAILED: Bot did not ask user for their number of travelers!"
)
print(">>> PASS SCENARIO 2: Bot correctly asked user for dates and travelers without assuming on its own!")

print("\n=== ALL SCENARIOS VERIFIED SUCCESSFULLY! ===")
