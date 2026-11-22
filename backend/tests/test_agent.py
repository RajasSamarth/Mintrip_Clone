"""Agent, streaming and itinerary tests (demo mode, no API keys)."""

from __future__ import annotations


def test_chat_builds_trip_and_map_pins(client) -> None:
    response = client.post(
        "/api/chat/message",
        json={
            "message": "Plan a 3-day foodie and culture trip to Kyoto with boutique hotels",
            "session_id": "",
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["trip_id"]
    assert payload["mode"] == "demo"
    assert len(payload["pins"]) >= 6
    assert any(card["type"] == "trip" for card in payload["cards"])
    assert any(card["type"] == "hotel" for card in payload["cards"])
    trip = payload["trip"]
    assert trip["day_count"] == 3
    assert trip["days"][0]["stops"]
    assert all(stop["transit_info"] for stop in trip["days"][0]["stops"])


def test_chat_unknown_destination_generates_itinerary(client) -> None:
    response = client.post(
        "/api/chat/message",
        json={"message": "A romantic 2-day trip to Tokyo", "session_id": "guest_tokyo"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["trip"]["destination"] == "tokyo"
    assert payload["trip"]["day_count"] == 2
    assert len(payload["pins"]) >= 4


def test_sse_stream_emits_tokens_and_done(client) -> None:
    with client.stream(
        "POST",
        "/api/chat/stream",
        json={"message": "5 quiet days in the Swiss Alps", "session_id": "guest_stream"},
    ) as response:
        body = "".join(response.iter_text())
    assert response.status_code == 200
    assert "event: token" in body
    assert "event: cards" in body
    assert "event: done" in body


def test_history_is_persisted(client) -> None:
    response = client.get("/api/chat/history/guest_stream")
    assert response.status_code == 200
    messages = response.json()["messages"]
    assert len(messages) >= 2
    assert messages[0]["sender"] == "user"
    assert messages[-1]["sender"] == "assistant"


def test_trip_detail_and_reorder(client) -> None:
    chat = client.post("/api/chat/message", json={"message": "3 days in Rome", "session_id": "guest_rome"}).json()
    trip_id = chat["trip_id"]
    trip = client.get(f"/api/trips/{trip_id}").json()
    assert trip["destination"] == "rome"
    day = trip["days"][0]
    stop_ids = [stop["id"] for stop in day["stops"]]
    reordered = client.post(f"/api/trips/{trip_id}/reorder", json={"day_index": 1, "stop_ids": list(reversed(stop_ids))})
    assert reordered.status_code == 200
    new_ids = [stop["id"] for stop in reordered.json()["days"][0]["stops"]]
    assert new_ids == list(reversed(stop_ids))


def _price_usd(hotel: dict) -> float | None:
    price = hotel.get("price_per_night")
    if not price:
        return None
    return price / 85.0 if (hotel.get("currency") or "INR").upper() == "INR" else price


def test_hotel_swap_followup(client) -> None:
    chat = client.post("/api/chat/message", json={"message": "A 3-day trip to Kyoto", "session_id": "guest_swap"}).json()
    trip_id = chat["trip_id"]
    before = client.get(f"/api/trips/{trip_id}").json()["hotel"]
    before_usd = _price_usd(before)

    swap = client.post(
        "/api/chat/message",
        json={
            "message": "Can you swap the hotel for a cheaper one?",
            "session_id": "guest_swap",
            "context": {"trip_id": trip_id},
        },
    )
    assert swap.status_code == 200
    payload = swap.json()
    assert payload["trip_id"] == trip_id
    assert "Swapped the stay" in payload["message"]
    assert "cheaper" in payload["message"].lower()
    after = payload["trip"]["hotel"]
    assert after["id"] != before["id"]
    if before_usd and _price_usd(after):
        assert _price_usd(after) < before_usd


def test_cheaper_hotel_discovery_does_not_swap(client) -> None:
    chat = client.post("/api/chat/message", json={"message": "A 3-day trip to Kyoto", "session_id": "guest_cheaper_discovery"}).json()
    trip_id = chat["trip_id"]
    before = client.get(f"/api/trips/{trip_id}").json()["hotel"]

    reply = client.post(
        "/api/chat/message",
        json={
            "message": "Show me a cheaper hotel in Kyoto",
            "session_id": "guest_cheaper_discovery",
            "context": {"trip_id": trip_id},
        },
    )
    assert reply.status_code == 200
    payload = reply.json()
    assert "Swapped the stay" not in payload["message"]
    assert payload["trip"]["hotel"]["id"] == before["id"]
    assert payload["cards"]
    assert all(card["type"] == "hotel" for card in payload["cards"])


def test_cheaper_hotel_when_already_cheapest_does_not_swap(client) -> None:
    chat = client.post("/api/chat/message", json={"message": "3 days in Kyoto", "session_id": "guest_already_cheap"}).json()
    trip_id = chat["trip_id"]
    hotels = client.get(
        "/api/hotels",
        params={"destination": "Kyoto", "auto_scrape": False, "live": False, "limit": 5000},
    ).json()["hotels"]
    priced = [h for h in hotels if h.get("price_per_night") and not h.get("price_unavailable")]
    assert priced
    cheapest = min(priced, key=_price_usd)
    patched = client.patch(f"/api/trips/{trip_id}", json={"hotel_id": cheapest["id"]})
    assert patched.status_code == 200
    assert patched.json()["hotel"]["id"] == cheapest["id"]

    reply = client.post(
        "/api/chat/message",
        json={
            "message": "Swap the hotel for a cheaper one",
            "session_id": "guest_already_cheap",
            "context": {"trip_id": trip_id},
        },
    )
    assert reply.status_code == 200
    payload = reply.json()
    assert "already the most affordable" in payload["message"]
    assert "Swapped the stay" not in payload["message"]
    assert payload["trip"]["hotel"]["id"] == cheapest["id"]


def test_named_place_is_added_to_requested_day(client) -> None:
    chat = client.post(
        "/api/chat/message",
        json={"message": "Plan a 3-day trip to Dubai", "session_id": "guest_named_place"},
    ).json()
    trip_id = chat["trip_id"]

    reply = client.post(
        "/api/chat/message",
        json={
            "message": "Add % Arabica Dubai Mall to Day 2",
            "session_id": "guest_named_place",
            "context": {"trip_id": trip_id},
        },
    ).json()
    assert "Arabica" in reply["message"]
    day2 = next(d for d in reply["trip"]["days"] if d["day_index"] == 2)
    names = [s["place"]["name"] for s in day2["stops"] if s.get("place")]
    assert any("Arabica" in name for name in names)


def test_adding_same_place_is_idempotent(client) -> None:
    chat = client.post(
        "/api/chat/message",
        json={"message": "3 days in Rome", "session_id": "guest_idempotent"},
    ).json()
    trip_id = chat["trip_id"]
    places = client.get("/api/places", params={"destination": "rome", "limit": 1}).json()["places"]
    place_id = places[0]["id"]

    first = client.post(
        f"/api/trips/{trip_id}/stops",
        json={"day_index": 1, "place_id": place_id, "time_slot": "morning", "notes": "First"},
    ).json()
    second = client.post(
        f"/api/trips/{trip_id}/stops",
        json={"day_index": 1, "place_id": place_id, "time_slot": "evening", "notes": "Updated"},
    ).json()

    def matching(trip: dict) -> list[dict]:
        day = next(d for d in trip["days"] if d["day_index"] == 1)
        return [s for s in day["stops"] if s["place_id"] == place_id]

    assert len(matching(first)) == 1
    assert len(matching(second)) == 1
    assert matching(second)[0]["time_slot"] == "evening"
    assert matching(second)[0]["notes"] == "Updated"
    assert [s["sort_order"] for s in second["days"][0]["stops"]] == list(range(len(second["days"][0]["stops"])))
