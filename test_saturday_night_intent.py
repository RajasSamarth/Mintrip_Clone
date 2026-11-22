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
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"HTTPError {e.code}: {e.read().decode('utf-8')}")
        raise e

def get(endpoint):
    with urllib.request.urlopen(f"{BASE_URL}{endpoint}") as resp:
        return json.loads(resp.read().decode("utf-8"))

print("=== TESTING SATURDAY NIGHT ITINERARY INTENT ===")

# Step 1: Create session
session_resp = post("/chat/session", {})
session_id = session_resp["session_id"]
print(f"Session created: {session_id}")

# Step 2: Create trip: 16th Dec to 24th Dec (Dec 16 is Wednesday, Dec 19 is Saturday = Day 4)
print("\n--- Creating Trip ---")
trip_resp = post("/chat/message", {
    "session_id": session_id,
    "message": "plan a complete trip from delhi to new york from 16th dec to 24th dec for 2 adults",
})
trip_id = trip_resp.get("trip_id")
print(f"Trip created: {trip_id}, destination={trip_resp.get('trip', {}).get('destination')}")
days = trip_resp.get("trip", {}).get("days", [])
print(f"Trip has {len(days)} days.")
for d in days:
    print(f"  Day {d.get('day_index')}: {d.get('date')} ({d.get('title')})")

# Step 3: Send the user's exact input
print("\n--- Sending Spot Addition Request ---")
prompt = "Clubhouse at Nordstrom add this in my saturday night itinerary"
print(f"User: '{prompt}'")
reply = post("/chat/message", {
    "session_id": session_id,
    "message": prompt,
    "context": {"trip_id": trip_id}
})

print(f"\nAssistant reply:\n{reply.get('message')}")
msg = reply.get("message", "")

# Verify reply message contents
assert "day 4" in msg.lower(), f"FAILED: Expected Day 4 in reply message, got: {msg}"
assert "saturday" in msg.lower(), f"FAILED: Expected Saturday in reply message, got: {msg}"
assert "evening" in msg.lower(), f"FAILED: Expected evening in reply message, got: {msg}"
assert "clubhouse at nordstrom" in msg.lower(), f"FAILED: Expected spot name in reply, got: {msg}"

# Step 4: Verify directly against the Trip in DB
print("\n--- Verifying Trip in Database ---")
trip_db = get(f"/trips/{trip_id}")
trip_days = trip_db.get("days", [])

day1 = next((d for d in trip_days if d.get("day_index") == 1), {})
day4 = next((d for d in trip_days if d.get("day_index") == 4), {})

day1_stops = [s.get("place", {}).get("name") or s.get("notes") for s in day1.get("stops", [])]
day4_stops = [s.get("place", {}).get("name") or s.get("notes") for s in day4.get("stops", [])]

print(f"Day 1 stops: {day1_stops}")
print(f"Day 4 stops: {day4_stops}")

assert not any("clubhouse" in s.lower() for s in day1_stops), "FAILED: Clubhouse was mistakenly added to Day 1!"
assert any("clubhouse" in s.lower() for s in day4_stops), "FAILED: Clubhouse was NOT found in Day 4!"

clubhouse_stop = next(s for s in day4.get("stops", []) if "clubhouse" in (s.get("place", {}).get("name") or "").lower())
print(f"Clubhouse stop details: slot={clubhouse_stop.get('time_slot')}, notes={clubhouse_stop.get('notes')}")
assert clubhouse_stop.get("time_slot") == "evening", f"FAILED: Expected evening time slot, got {clubhouse_stop.get('time_slot')}"

print("\n>>> ALL SATURDAY NIGHT ASSERTIONS PASSED SEAMLESSLY! <<<")
