"""OpenAI/Grok-compatible tool definitions and dispatcher."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from sqlmodel import Session

from backend.services import data_service
from backend.services.routing_service import calculate_route, transit_label

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_google_maps_places",
            "description": "Live search and scrape Google Maps for specific cuisines (e.g. 'indian restaurant', 'italian pasta', 'thai food'), nightlife & drinks (e.g. 'rooftop cocktail bar', 'jazz club'), local health amenities (e.g. 'pharmacy', 'hospital', 'clinic'), or lifestyle services (e.g. 'hair salon', 'spa', 'gym') in any destination. Results are persisted to database & Supabase and returned with exact coordinates, ratings, and addresses.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Specific query e.g. 'indian restaurant', '24/7 pharmacy', 'rooftop bar', 'nail salon'"},
                    "location": {"type": "string", "description": "City or destination, e.g. 'New York', 'Paris', 'Kyoto'"},
                    "category": {"type": "string", "enum": ["restaurant", "cafe", "bar", "pharmacy", "hospital", "salon", "attraction", "other"], "description": "Category classification"},
                    "limit": {"type": "integer", "default": 5, "description": "Number of places to scrape (default 5)"},
                },
                "required": ["query", "location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_places",
            "description": "Search curated places, restaurants, cafés, attractions and activities by destination and category.",
            "parameters": {
                "type": "object",
                "properties": {
                    "destination": {"type": "string", "description": "Destination slug or city name, e.g. kyoto"},
                    "category": {"type": "string", "enum": ["all", "attraction", "restaurant", "cafe", "activity", "bar", "hotel"]},
                    "query": {"type": "string", "description": "Optional name keyword"},
                    "limit": {"type": "integer", "default": 12},
                },
                "required": ["destination"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_hotels",
            "description": "Find hotels from the destination cache with price, star rating, amenities, location and room types. Filters instantly from cache.",
            "parameters": {
                "type": "object",
                "properties": {
                    "destination": {"type": "string", "description": "City or destination name, e.g. Dubai, Tokyo, Rome"},
                    "max_price": {"type": "number", "description": "Maximum price per night in USD"},
                    "min_price": {"type": "number", "description": "Minimum price per night in USD"},
                    "min_stars": {"type": "integer", "minimum": 0, "maximum": 5},
                    "location_keyword": {"type": "string", "description": "Neighborhood or location filter, e.g. Marina, Downtown, Old Town, Beach"},
                    "amenities": {"type": "array", "items": {"type": "string"}},
                    "limit": {"type": "integer", "default": 6},
                },
                "required": ["destination"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_flights",
            "description": "Find flight options between two IATA airports.",
            "parameters": {
                "type": "object",
                "properties": {
                    "origin": {"type": "string", "description": "IATA code, e.g. SFO"},
                    "destination": {"type": "string", "description": "IATA code, e.g. KIX"},
                    "cabin": {"type": "string", "enum": ["Economy", "Business", "Any"]},
                    "max_price": {"type": "number"},
                    "adults": {"type": "integer", "description": "Number of adult passengers", "default": 1},
                    "children": {"type": "integer", "description": "Number of children passengers", "default": 0},
                    "infants": {"type": "integer", "description": "Number of infant passengers", "default": 0},
                    "limit": {"type": "integer", "default": 6},
                },
                "required": ["origin", "destination"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_route",
            "description": "Calculate distance and duration between two coordinates using OSRM (with offline fallback).",
            "parameters": {
                "type": "object",
                "properties": {
                    "origin_lat": {"type": "number"},
                    "origin_lon": {"type": "number"},
                    "destination_lat": {"type": "number"},
                    "destination_lon": {"type": "number"},
                    "profile": {"type": "string", "enum": ["walking", "cycling", "driving"]},
                },
                "required": ["origin_lat", "origin_lon", "destination_lat", "destination_lon"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "build_itinerary",
            "description": "Create and persist a day-by-day itinerary once the user has provided or confirmed their travel dates and number of travelers. DO NOT call this tool if dates or travelers are unknown — ask the user first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "destination": {"type": "string"},
                    "origin": {"type": "string", "description": "Origin city or airport code, e.g. Delhi, DEL, SFO"},
                    "days": {"type": "integer", "minimum": 1, "maximum": 14},
                    "title": {"type": "string"},
                    "traveler_type": {"type": "string"},
                    "passengers": {"type": "integer", "description": "Number of travelers/passengers"},
                    "budget": {"type": "number"},
                    "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "end_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "hotel_id": {"type": "string"},
                    "preferences": {"type": "string", "description": "e.g. foodie, romantic, slow travel, family"},
                },
                "required": ["destination", "days"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_destination",
            "description": "Get editorial destination copy, best season, hero image and coordinates.",
            "parameters": {
                "type": "object",
                "properties": {"destination": {"type": "string"}},
                "required": ["destination"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_day_visiting_spots",
            "description": "Update or replace the visiting spots/places for a specific day in an existing itinerary. Mutates the database so the itinerary and map stay synced.",
            "parameters": {
                "type": "object",
                "properties": {
                    "trip_id": {"type": "string", "description": "Trip ID"},
                    "day_index": {"type": "integer", "description": "Day number (1-based)", "default": 1},
                    "place_ids": {"type": "array", "items": {"type": "string"}, "description": "List of place IDs to schedule for this day"},
                    "notes": {"type": "array", "items": {"type": "string"}, "description": "Optional notes for each stop"},
                },
                "required": ["trip_id", "day_index", "place_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_stop_from_trip",
            "description": "Remove a specific stop by its stop ID from a trip, re-ordering remaining day stops.",
            "parameters": {
                "type": "object",
                "properties": {
                    "trip_id": {"type": "string", "description": "Trip ID"},
                    "stop_id": {"type": "integer", "description": "Stop ID to delete"},
                },
                "required": ["trip_id", "stop_id"],
            },
        },
    },
]


class ToolDispatcher:
    """Executes tool calls against the local database and routing service."""

    def __init__(self, session: Session, session_id: str = "", itinerary_builder: Callable[..., dict[str, Any]] | None = None) -> None:
        self.session = session
        self.session_id = session_id
        self.itinerary_builder = itinerary_builder

    def dispatch(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        handler = getattr(self, f"_tool_{name}", None)
        if handler is None:
            return {"error": f"Unknown tool: {name}"}
        try:
            return handler(**arguments)
        except TypeError as exc:
            return {"error": f"Bad arguments for {name}: {exc}"}
        except Exception as exc:  # noqa: BLE001 - tools must never kill the chat
            return {"error": f"{name} failed: {exc}"}

    def _tool_search_google_maps_places(
        self,
        query: str,
        location: str,
        category: str = "restaurant",
        limit: int = 5,
    ) -> dict[str, Any]:
        try:
            from scrapers.google_maps_adapter import search_google_maps_live
            places = search_google_maps_live(
                query=query,
                location=location,
                category=category,
                max_results=limit or 5,
                session=self.session,
            )
            return {
                "query": query,
                "location": location,
                "category": category,
                "count": len(places),
                "places": [data_service.place_dict(p) for p in places],
            }
        except Exception as exc:
            return {"error": f"Google Maps scrape failed: {exc}", "query": query, "location": location, "places": []}

    def _tool_search_places(self, destination: str, category: str = "all", query: str = "", limit: int = 12) -> dict[str, Any]:
        rows = data_service.list_places(self.session, destination=destination, category=category, query=query, limit=limit)
        if len(rows) < 3:
            # Check famous spots catalog and seed authentic places
            try:
                from backend.database.famous_spots import get_famous_spots_for_destination
                famous = get_famous_spots_for_destination(destination)
                if famous:
                    from backend.database.models import Place
                    dest_slug = data_service.slugify(destination)
                    for s in famous:
                        if not self.session.get(Place, s.get("id", "")):
                            price_lvl = 1
                            if s.get("price_level") in {"$$$", "€€€", "₹₹₹"}:
                                price_lvl = 3
                            elif s.get("price_level") in {"$$", "€€", "₹₹"}:
                                price_lvl = 2
                            p = Place(
                                id=s.get("id") or f"{dest_slug}-{data_service.slugify(s['name'])}",
                                name=s["name"],
                                category=s.get("category", "attraction"),
                                destination=dest_slug,
                                description=s.get("description", ""),
                                lat=s.get("lat") or 0.0,
                                lon=s.get("lon") or 0.0,
                                rating=s.get("rating", 4.8),
                                review_count=s.get("reviews_count") or s.get("review_count", 1500),
                                address=s.get("address", f"{destination} central district"),
                                price_level=price_lvl,
                                opening_hours="See local listings",
                                photos=s.get("photos") or [],
                                tags=s.get("tags", []),
                                source="curated",
                            )
                            self.session.add(p)
                    self.session.commit()
                    rows = data_service.list_places(self.session, destination=destination, category=category, query=query, limit=limit)
            except Exception:
                pass
        return {"destination": destination, "count": len(rows), "places": rows}

    def _tool_search_hotels(
        self,
        destination: str,
        max_price: float | None = None,
        min_price: float | None = None,
        min_stars: int | None = None,
        amenities: list[str] | None = None,
        location_keyword: str = "",
        query: str = "",
        limit: int = 6,
    ) -> dict[str, Any]:
        dest_clean = destination.strip()
        # Check cache in DB first
        cached_hotels = data_service.list_hotels(self.session, destination=dest_clean, limit=50)

        # Scrape and populate cache ONLY if destination has no / insufficient hotels cached
        if len(cached_hotels) < 4:
            try:
                from scrapers.hotel_scraper_runner import search_hotels as scrape_hotels, save_hotels_to_db
                scraped_records = scrape_hotels(destination=dest_clean, max_results=20)
                if scraped_records:
                    save_hotels_to_db(scraped_records, self.session)
            except Exception as exc:
                logger.warning("Hotel scraper fallback error: %s", exc)

        # Filter strictly from the cached database records based on budget, stars, amenities, and location
        location_filter = location_keyword or query
        rows = data_service.list_hotels(
            self.session,
            destination=dest_clean,
            min_price=min_price,
            max_price=max_price,
            stars=min_stars,
            amenities=amenities or [],
            query=location_filter,
            limit=limit,
            sort="price" if (max_price or min_price) else "recommended",
        )
        return {
            "destination": dest_clean,
            "from_cache": len(cached_hotels) >= 4,
            "cached_pool_size": len(cached_hotels),
            "count": len(rows),
            "hotels": rows,
        }

    def _tool_search_flights(
        self,
        origin: str,
        destination: str,
        date: str = "",
        cabin: str = "Any",
        adults: int = 1,
        children: int = 0,
        infants: int = 0,
        max_price: float | None = None,
        limit: int = 6,
    ) -> dict[str, Any]:
        """Fetch live Google Flights results. Never returns cached/generated data."""
        import asyncio
        import threading

        from scrapers.flight_scraper_runner import save_flights_to_db
        from scrapers.flight_scraper_runner import search_flights as scrape_flights

        total_pax = max(1, int(adults or 1) + int(children or 0) + int(infants or 0))
        wanted_cabin = "Economy" if (cabin or "").lower() in ("", "any") else cabin

        async def _live() -> list:
            return await scrape_flights(
                origin=origin,
                destination=destination,
                date=date,
                cabin=wanted_cabin,
                adults=int(adults or 1),
                children=int(children or 0),
                infants=int(infants or 0),
                max_results=limit or 6,
                live=True,
                allow_fallback=False,
            )

        try:
            # A tool may be dispatched from a worker thread that already owns an
            # event loop. In that case run the coroutine in a nested thread.
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                records = asyncio.run(_live())
            else:
                box: dict[str, Any] = {}

                def _runner() -> None:
                    try:
                        box["records"] = asyncio.run(_live())
                    except BaseException as exc:  # noqa: BLE001 - forwarded to caller
                        box["error"] = exc

                thread = threading.Thread(target=_runner, daemon=True)
                thread.start()
                thread.join()
                if box.get("error"):
                    raise box["error"]
                records = box.get("records") or []
        except Exception as exc:  # noqa: BLE001 - tool must not kill the chat
            return {
                "origin": origin.upper(),
                "destination": destination.upper(),
                "count": 0,
                "flights": [],
                "source": "google_flights_live",
                "error": f"Live flight search failed: {exc}",
            }

        if not records:
            return {
                "origin": origin.upper(),
                "destination": destination.upper(),
                "count": 0,
                "flights": [],
                "source": "google_flights_live",
                "error": "No live Google Flights results for this route/date.",
            }

        try:
            save_flights_to_db(records, self.session)
        except Exception:
            pass

        rows: list[dict[str, Any]] = []
        for r in records[: (limit or 6)]:
            data = r.model_dump(mode="json")
            if max_price is not None:
                try:
                    if float(data.get("price_usd") or 0) > float(max_price):
                        continue
                except (TypeError, ValueError):
                    pass
            rows.append(data)

        return {
            "origin": origin.upper(),
            "destination": destination.upper(),
            "count": len(rows),
            "viewed_at": datetime.now().isoformat(),
            "source": "google_flights_live",
            "currency": "INR",
            "flights": rows,
        }

    def _tool_calculate_route(self, origin_lat: float, origin_lon: float, destination_lat: float, destination_lon: float, profile: str = "walking") -> dict[str, Any]:
        route = calculate_route((origin_lat, origin_lon), (destination_lat, destination_lon), profile)
        route["label"] = transit_label(route)
        return route

    def _tool_build_itinerary(
        self,
        destination: str,
        days: int,
        title: str = "",
        traveler_type: str = "Traveler",
        budget: float = 0,
        start_date: str = "",
        end_date: str = "",
        origin: str = "",
        passengers: int = 1,
        hotel_id: str = "",
        preferences: str = "",
    ) -> dict[str, Any]:
        if self.itinerary_builder is None:
            return {"error": "Itinerary builder unavailable"}
        result = self.itinerary_builder(
            destination_query=destination,
            days=days,
            title=title,
            traveler_type=traveler_type,
            budget=budget,
            start_date=start_date,
            end_date=end_date,
            origin=origin,
            passengers=passengers,
            hotel_id=hotel_id,
            preferences=preferences,
            session_id=self.session_id,
        )
        return {
            "trip_id": result["trip"]["id"],
            "title": result["trip"]["title"],
            "days": len(result["trip"]["days"]),
            "stops": sum(len(day["stops"]) for day in result["trip"]["days"]),
            "trip": result["trip"],
            "pins": result["pins"],
        }

    def _tool_get_destination(self, destination: str) -> dict[str, Any]:
        row = data_service.get_destination(self.session, destination)
        if row:
            return row
        matches = [d for d in data_service.list_destinations(self.session) if destination.lower() in d["name"].lower()]
        return matches[0] if matches else {"error": f"Destination '{destination}' not found"}

    def _tool_update_day_visiting_spots(self, trip_id: str, day_index: int, place_ids: list[str], notes: list[str] | None = None) -> dict[str, Any]:
        updated = data_service.update_day_stops(self.session, trip_id=trip_id, day_index=day_index, place_ids=place_ids, notes_list=notes)
        if not updated:
            return {"error": f"Failed to update stops for day {day_index} of trip {trip_id}"}
        return {"trip_id": trip_id, "day_index": day_index, "stops_count": len(place_ids), "updated": True}

    def _tool_remove_stop_from_trip(self, trip_id: str, stop_id: int) -> dict[str, Any]:
        updated = data_service.remove_stop(self.session, trip_id=trip_id, stop_id=stop_id)
        if not updated:
            return {"error": f"Failed to remove stop {stop_id} from trip {trip_id}"}
        return {"trip_id": trip_id, "stop_id": stop_id, "removed": True}
