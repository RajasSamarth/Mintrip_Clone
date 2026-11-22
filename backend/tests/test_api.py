"""REST surface tests."""

from __future__ import annotations


def test_health_and_config(client) -> None:
    assert client.get("/api/health").json()["status"] == "ok"
    config = client.get("/api/config").json()
    assert config["llm"]["provider"] == "demo"
    assert config["map"]["provider"] == "maplibre"
    assert "nominatim" in config["features"]["free_apis"]


def test_destinations(client) -> None:
    response = client.get("/api/destinations")
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] >= 6
    ids = {row["id"] for row in payload["destinations"]}
    assert {"kyoto", "rome", "swiss-alps"}.issubset(ids)


def test_places_filter(client) -> None:
    response = client.get("/api/places", params={"destination": "kyoto", "category": "attraction"})
    assert response.status_code == 200
    rows = response.json()["places"]
    assert rows
    assert all(row["destination"] == "kyoto" for row in rows)
    assert all(row["category"] == "attraction" for row in rows)


def test_hotels_filter_and_rooms(client) -> None:
    response = client.get("/api/hotels", params={"destination": "kyoto", "max_price": 500})
    assert response.status_code == 200
    rows = response.json()["hotels"]
    assert rows
    assert all(row["price_per_night"] <= 500 for row in rows)
    hotel = rows[0]
    rooms = client.get(f"/api/hotels/{hotel['id']}/rooms").json()
    assert rooms["rooms"]


def test_flights_filter_and_airports(client) -> None:
    response = client.get("/api/flights", params={"destination": "KIX"})
    assert response.status_code == 200
    rows = response.json()["flights"]
    assert rows
    assert all(row["destination"] == "KIX" for row in rows)
    airports = client.get("/api/flights/airports", params={"q": "tokyo"}).json()
    assert airports["airports"][0]["code"] == "HND"


def test_inspiration_and_search(client) -> None:
    inspiration = client.get("/api/inspiration").json()
    assert inspiration["count"] >= 3
    assert inspiration["collections"][0]["destination_detail"]
    search = client.get("/api/search", params={"q": "Kyoto"}).json()
    assert search["destinations"]
    assert search["places"]


def test_stats(client) -> None:
    stats = client.get("/api/stats").json()
    assert stats["places"] >= 24
    assert stats["trips"] >= 3


def test_trip_attach_hotel_and_flight(client) -> None:
    # 1. Create a trip
    trip_res = client.post(
        "/api/trips",
        json={
            "title": "Pune Culinary & Heritage Tour",
            "destination": "pune",
            "days": [{"day_index": 1, "title": "Day 1"}],
        },
    )
    assert trip_res.status_code == 201
    trip_id = trip_res.json()["id"]

    # 2. Attach Hotel
    hotel_res = client.post(
        f"/api/trips/{trip_id}/hotel",
        json={
            "hotel_id": "the-westin-pune",
            "hotel_data": {
                "name": "The Westin Pune Koregaon Park",
                "price_per_night": 12500,
                "stars": 5,
            },
        },
    )
    assert hotel_res.status_code == 200
    updated_trip = hotel_res.json()
    assert updated_trip["hotel"] is not None
    assert updated_trip["hotel"]["name"] == "The Westin Pune Koregaon Park"

    # 3. Attach Flight
    flight_res = client.post(
        f"/api/trips/{trip_id}/flight",
        json={
            "flight_id": "fl-del-pnq-101",
            "flight_data": {
                "airline": "Air India",
                "origin": "DEL",
                "destination": "PNQ",
                "price_usd": 85,
            },
        },
    )
    assert flight_res.status_code == 200
    with_flight = flight_res.json()
    assert with_flight["flight"] is not None
    assert with_flight["flight"]["airline"] == "Air India"

    # 4. Detach Hotel & Flight
    del_hotel = client.delete(f"/api/trips/{trip_id}/hotel")
    assert del_hotel.status_code == 200
    assert del_hotel.json()["hotel"] is None

    del_flight = client.delete(f"/api/trips/{trip_id}/flight")
    assert del_flight.status_code == 200
    assert del_flight.json()["flight"] is None


def test_places_restaurant_deep_fields(client) -> None:
    response = client.get("/api/places", params={"destination": "pune", "category": "restaurant"})
    assert response.status_code == 200
    places = response.json()["places"]
    if places:
        first = places[0]
        assert "menu" in first
        assert "reviews" in first
        assert "opening_hours_weekly" in first
        assert "dining_amenities" in first


def test_places_recommended_and_trip_destination_photo(client) -> None:
    # Test recommended places endpoint
    res = client.get("/api/places/recommended", params={"destination": "pune"})
    assert res.status_code == 200
    data = res.json()
    assert data["count"] >= 3
    assert any("shaniwar" in p["id"].lower() or "aga khan" in p["name"].lower() for p in data["places"])

    # Test trip creation automatically receives destination cover photo
    trip_res = client.post(
        "/api/trips",
        json={
            "title": "Delhi Explorer",
            "destination": "Delhi",
            "days": [{"day_index": 1, "title": "Day 1"}],
        },
    )
    assert trip_res.status_code == 201
    created_trip = trip_res.json()
    assert "photo-1587474260584" in created_trip["cover_photo"]

