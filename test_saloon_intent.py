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

# 1. Create session
session_resp = post("/chat/session", {})
session_id = session_resp["session_id"]
print(f"Created Session: {session_id}")

# 2. Plan 9-day trip to New York
trip_resp = post("/chat/message", {
    "session_id": session_id,
    "message": "plan a 9-day trip to New York for 2 adults",
})
trip_id = trip_resp.get("trip_id")
print(f"Created Trip: {trip_id}")

# 3. Ask for saloon on day 6 near hotel
msg = "on day 6 i want to visit a saloon so find me near my hotel"
reply = post("/chat/message", {
    "session_id": session_id,
    "message": msg,
    "context": {"trip_id": trip_id}
})

print("\n--- HTTP API RESPONSE ---")
print("Message:", reply.get("message"))
print("Cards Count:", len(reply.get("cards", [])))
for c in reply.get("cards", []):
    print(" - Place:", c.get("name"), "| Category:", c.get("category"), "| Rating:", c.get("rating"), "| Day:", c.get("day_index"))
print("Tool Calls:", reply.get("tool_calls"))
print("Suggestions:", reply.get("suggestions"))

assert "curated hotels in" not in reply.get("message", "").lower(), "FAILED: Bot returned hotels instead of salons!"
assert any(c.get("category") == "salon" for c in reply.get("cards", [])), "FAILED: No salon cards returned!"
assert any(c.get("day_index") == 6 for c in reply.get("cards", [])), "FAILED: Day index should be 6!"
assert all(c.get("name") != "Place" for c in reply.get("cards", [])), "FAILED: Card has generic name 'Place'!"
print("\n>>> VERIFIED VIA LIVE HTTP API SUCCESSFULLY!")
