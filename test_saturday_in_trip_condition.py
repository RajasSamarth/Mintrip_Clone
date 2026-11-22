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

print("=== TESTING CONDITIONAL SATURDAY REQUEST IN 3-DAY AND 9-DAY TRIPS ===")

# ==============================================================================
# TEST 1: 3-Day Trip (Monday to Wednesday) - NO Saturday in trip!
# ==============================================================================
print("\n--- TEST 1: 3-Day Trip (Monday to Wednesday) ---")
s1_resp = post("/chat/session", {})
s1_id = s1_resp["session_id"]

# Create 3-day trip in Swiss Alps: Oct 5 (Mon) to Oct 7 (Wed) 2026
trip1_resp = post("/chat/message", {
    "session_id": s1_id,
    "message": "plan a 3-day trip to Swiss Alps from 5th oct to 7th oct for 2 adults from zurich",
})
t1_id = trip1_resp.get("trip_id")
print(f"Created 3-Day Trip: {t1_id}")
trip1_obj = get(f"/trips/{t1_id}")
days1 = trip1_obj.get("days", [])
print(f"Trip 1 days count: {len(days1)}")
for d in days1:
    print(f"  Day {d.get('day_index')}: {d.get('date')} ({d.get('title')})")

assert len(days1) == 3, f"Expected 3 days initially, got {len(days1)}"

# Send the user's exact prompt
prompt1 = "is there any saturday in my trip if yes then add The Swiss House in my evening plan"
print(f"\nUser: '{prompt1}'")
reply1 = post("/chat/message", {
    "session_id": s1_id,
    "message": prompt1,
    "context": {"trip_id": t1_id}
})

msg1 = reply1.get("message", "")
print(f"\nAssistant Response:\n{msg1}")

# Verify assistant response explains there is NO Saturday
assert "no saturday" in msg1.lower(), f"FAILED: Assistant did not state there is no Saturday! Msg: {msg1}"
assert "day 6" not in msg1.lower(), f"FAILED: Assistant hallucinated Day 6! Msg: {msg1}"
assert not ("i've added the swiss house to day 6" in msg1.lower()), f"FAILED: Bot added to Day 6! Msg: {msg1}"

# Verify Database: trip MUST STILL HAVE EXACTLY 3 DAYS
trip1_after = get(f"/trips/{t1_id}")
days1_after = trip1_after.get("days", [])
print(f"Trip 1 days count after prompt: {len(days1_after)}")
assert len(days1_after) == 3, f"FAILED: Trip days increased to {len(days1_after)}! Database was mutated with hallucinated days!"
print(">>> PASS TEST 1: Correctly declined adding to non-existent Saturday and preserved 3-day trip in DB!")

# ==============================================================================
# TEST 2: 9-Day Trip (Wednesday to Thursday) - Saturday DOES exist (Day 4)!
# ==============================================================================
print("\n--- TEST 2: 9-Day Trip (Wednesday to Thursday) ---")
s2_resp = post("/chat/session", {})
s2_id = s2_resp["session_id"]

trip2_resp = post("/chat/message", {
    "session_id": s2_id,
    "message": "plan a complete trip from delhi to new york from 16th dec to 24th dec for 2 adults",
})
t2_id = trip2_resp.get("trip_id")
print(f"Created 9-Day Trip: {t2_id}")

prompt2 = "is there any saturday in my trip if yes then add Clubhouse at Nordstrom in my evening plan"
print(f"\nUser: '{prompt2}'")
reply2 = post("/chat/message", {
    "session_id": s2_id,
    "message": prompt2,
    "context": {"trip_id": t2_id}
})

msg2 = reply2.get("message", "")
print(f"\nAssistant Response:\n{msg2}")

assert "yes" in msg2.lower() and "saturday" in msg2.lower(), f"FAILED: Expected positive confirmation of Saturday! Msg: {msg2}"
assert "day 4" in msg2.lower(), f"FAILED: Expected Day 4 in message! Msg: {msg2}"
assert "evening" in msg2.lower(), f"FAILED: Expected evening in message! Msg: {msg2}"

# Verify Database: Day 4 has Clubhouse at Nordstrom with evening slot
trip2_after = get(f"/trips/{t2_id}")
day4 = next((d for d in trip2_after.get("days", []) if d.get("day_index") == 4), {})
day4_stops = [s.get("place", {}).get("name") or s.get("notes") for s in day4.get("stops", [])]
print(f"Day 4 stops: {day4_stops}")
assert any("clubhouse" in s.lower() for s in day4_stops), f"FAILED: Clubhouse was not added to Day 4!"

print("\n>>> PASS TEST 2: Correctly recognized Saturday exists on Day 4 and added to evening slot!")

print("\n=== ALL CONDITIONAL TESTS PASSED SEAMLESSLY! ===")
