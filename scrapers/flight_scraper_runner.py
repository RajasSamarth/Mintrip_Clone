"""Flight scraper runner and service.

Executes Google Flights scraping using Playwright with seamless automated
fallback to synthetic/route-matched data when live scraping is unavailable or blocked.
Normalises all output into FlightRecord models and optionally ingests into the Mindtrip DB.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Ensure user_scrapers/google_flights_scraper is in sys.path
FLIGHT_SCRAPER_DIR = PROJECT_ROOT / "scrapers" / "user_scrapers" / "google_flights_scraper"
if str(FLIGHT_SCRAPER_DIR) not in sys.path:
    sys.path.insert(0, str(FLIGHT_SCRAPER_DIR))

from scrapers.adapters.base_adapter import FlightRecord, slugify

# Set Windows Proactor event loop policy at module level to allow Playwright
# browser subprocess creation. This must be set before any asyncio event loop
# is created, otherwise create_subprocess_exec will fail on Windows.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
from scrapers.adapters.google_flights_adapter import _to_record

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("flight_scraper_runner")

import math

AIRPORT_COORDINATES: dict[str, tuple[float, float]] = {
    # India / South Asia
    "DEL": (28.5562, 77.1000),
    "BOM": (19.0896, 72.8656),
    "BLR": (13.1986, 77.7066),
    "HYD": (17.2403, 78.4294),
    "MAA": (12.9941, 80.1709),
    "CCU": (22.6547, 88.4467),
    "GOI": (15.3808, 73.8314),
    # North America
    "JFK": (40.6413, -73.7781),
    "EWR": (40.6895, -74.1745),
    "LGA": (40.7769, -73.8740),
    "SFO": (37.6213, -122.3790),
    "LAX": (33.9416, -118.4085),
    "ORD": (41.9742, -87.9073),
    "MIA": (25.7959, -80.2870),
    "SEA": (47.4502, -122.3088),
    "BOS": (42.3656, -71.0096),
    "DFW": (32.8998, -97.0403),
    "DEN": (39.8561, -104.6737),
    "ATL": (33.6407, -84.4277),
    # Europe
    "LHR": (51.4700, -0.4543),
    "LGW": (51.1537, -0.1821),
    "CDG": (49.0097, 2.5479),
    "FRA": (50.0379, 8.5622),
    "AMS": (52.3105, 4.7683),
    "FCO": (41.8003, 12.2389),
    "ZRH": (47.4582, 8.5555),
    "BCN": (41.2974, 2.0833),
    "MAD": (40.4839, -3.5680),
    "LIS": (38.7756, -9.1354),
    # Middle East
    "DXB": (25.2532, 55.3657),
    "DOH": (25.2731, 51.6081),
    "AUH": (24.4330, 54.6511),
    # Asia & Pacific
    "HND": (35.5494, 139.7798),
    "NRT": (35.7720, 140.3929),
    "KIX": (34.4320, 135.2304),
    "SIN": (1.3644, 103.9915),
    "BKK": (13.6900, 100.7501),
    "ICN": (37.4602, 126.4407),
    "HKG": (22.3080, 113.9185),
    "SYD": (-33.9399, 151.1753),
    "MEL": (-37.6690, 144.8410),
}


def calculate_great_circle_km(orig: str, dest: str) -> float:
    """Calculate distance in km between two airports using Haversine formula."""
    c1 = AIRPORT_COORDINATES.get(orig.upper())
    c2 = AIRPORT_COORDINATES.get(dest.upper())
    if not c1 or not c2:
        return 3000.0  # sensible intermediate fallback

    lat1, lon1 = c1
    lat2, lon2 = c2
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c


def _select_airlines_for_route(origin: str, dest: str) -> list[tuple[str, str, int]]:
    """Select authentic airlines and baseline stop count (0=non-stop, 1=one-stop) for a route."""
    origin = origin.upper()
    dest = dest.upper()

    india_hubs = {"DEL", "BOM", "BLR", "MAA", "HYD", "CCU", "GOI"}
    us_hubs = {"JFK", "EWR", "LGA", "SFO", "LAX", "ORD", "MIA", "SEA", "BOS", "DFW", "DEN", "ATL"}
    eu_hubs = {"LHR", "LGW", "CDG", "FRA", "AMS", "FCO", "ZRH", "BCN", "MAD", "LIS"}
    me_hubs = {"DXB", "DOH", "AUH"}
    asia_hubs = {"HND", "NRT", "KIX", "SIN", "ICN", "BKK", "SYD", "MEL", "HKG"}

    # India <-> North America (Ultra Long Haul)
    if (origin in india_hubs and dest in us_hubs) or (origin in us_hubs and dest in india_hubs):
        return [
            ("Air India", "AI", 0),
            ("United Airlines", "UA", 0),
            ("American Airlines", "AA", 0),
            ("Emirates", "EK", 1),
            ("Qatar Airways", "QR", 1),
            ("Lufthansa", "LH", 1),
            ("British Airways", "BA", 1),
            ("Air France", "AF", 1),
            ("Etihad Airways", "EY", 1),
            ("Virgin Atlantic", "VS", 1),
            ("Delta Air Lines", "DL", 1),
            ("Singapore Airlines", "SQ", 1),
        ]

    # India <-> Europe
    if (origin in india_hubs and dest in eu_hubs) or (origin in eu_hubs and dest in india_hubs):
        return [
            ("Air India", "AI", 0),
            ("British Airways", "BA", 0),
            ("Lufthansa", "LH", 0),
            ("Air France", "AF", 0),
            ("Emirates", "EK", 1),
            ("Qatar Airways", "QR", 1),
            ("Swiss", "LX", 0),
            ("KLM", "KL", 0),
        ]

    # India <-> Middle East
    if (origin in india_hubs and dest in me_hubs) or (origin in me_hubs and dest in india_hubs):
        return [
            ("Emirates", "EK", 0),
            ("Air India", "AI", 0),
            ("IndiGo", "6E", 0),
            ("Qatar Airways", "QR", 0),
            ("Etihad Airways", "EY", 0),
            ("Vistara", "UK", 0),
        ]

    # US Domestic
    if origin in us_hubs and dest in us_hubs:
        return [
            ("United Airlines", "UA", 0),
            ("Delta Air Lines", "DL", 0),
            ("American Airlines", "AA", 0),
            ("JetBlue Airways", "B6", 0),
            ("Alaska Airlines", "AS", 0),
        ]

    # India Domestic
    if origin in india_hubs and dest in india_hubs:
        return [
            ("IndiGo", "6E", 0),
            ("Air India", "AI", 0),
            ("Vistara", "UK", 0),
            ("Akasa Air", "QP", 0),
            ("SpiceJet", "SG", 0),
        ]

    # Transatlantic (US <-> Europe)
    if (origin in us_hubs and dest in eu_hubs) or (origin in eu_hubs and dest in us_hubs):
        return [
            ("British Airways", "BA", 0),
            ("Virgin Atlantic", "VS", 0),
            ("Delta Air Lines", "DL", 0),
            ("United Airlines", "UA", 0),
            ("American Airlines", "AA", 0),
            ("Air France", "AF", 0),
            ("Lufthansa", "LH", 0),
        ]

    # Transpacific (US <-> Asia)
    if (origin in us_hubs and dest in asia_hubs) or (origin in asia_hubs and dest in us_hubs):
        return [
            ("All Nippon Airways", "NH", 0),
            ("Japan Airlines", "JL", 0),
            ("Singapore Airlines", "SQ", 0),
            ("United Airlines", "UA", 0),
            ("Cathay Pacific", "CX", 0),
            ("Korean Air", "KE", 0),
        ]

    # Global fallback
    return [
        ("United Airlines", "UA", 0),
        ("Delta Air Lines", "DL", 0),
        ("Emirates", "EK", 1),
        ("Lufthansa", "LH", 1),
        ("Singapore Airlines", "SQ", 1),
        ("British Airways", "BA", 1),
        ("Qatar Airways", "QR", 1),
        ("Air France", "AF", 1),
    ]


def generate_fallback_flights(
    origin: str,
    destination: str,
    flight_date: str = "",
    cabin: str = "Economy",
    count: int = 24,
    trip_type: str = "one-way",
    return_date: str | None = None,
    adults: int = 1,
    children: int = 0,
    departure_date: str = "",
) -> list[FlightRecord]:
    """Generate realistic route-accurate flight records with physical flight durations, top picks and emissions."""
    origin = origin.upper()
    destination = destination.upper()
    flight_date = flight_date or departure_date
    carriers = _select_airlines_for_route(origin, destination)
    cabin_norm = cabin.capitalize() if cabin else "Economy"

    # Base departure date
    try:
        base_d = datetime.strptime(flight_date, "%Y-%m-%d")
    except Exception:
        base_d = datetime.now() + timedelta(days=7)

    # Base return date if round-trip
    is_round_trip = trip_type == "round-trip"
    try:
        ret_base_d = datetime.strptime(return_date or "", "%Y-%m-%d")
    except Exception:
        ret_base_d = base_d + timedelta(days=7)

    total_pax = max(1, adults + children)

    # Calculate realistic route distance and physical durations
    dist_km = calculate_great_circle_km(origin, destination)
    # Air speed approx 840 km/h + 45m taxi/takeoff/approach
    base_nonstop_mins = max(50, int(round((dist_km / 840.0) * 60.0 + 45.0)))

    # Realistic base price based on physical route distance
    if dist_km >= 8000:
        # Ultra Long Haul (e.g. DEL <-> JFK: ~11,750 km)
        base_oneway_usd = 720.0
        base_roundtrip_usd = 1190.0
    elif dist_km >= 4500:
        # Long Haul (e.g. DEL <-> LHR: ~6,700 km)
        base_oneway_usd = 440.0
        base_roundtrip_usd = 790.0
    elif dist_km >= 1800:
        # Medium Haul (e.g. DEL <-> DXB: ~2,200 km)
        base_oneway_usd = 180.0
        base_roundtrip_usd = 330.0
    else:
        # Short Haul domestic (e.g. DEL <-> BOM: ~1,150 km)
        base_oneway_usd = 75.0
        base_roundtrip_usd = 135.0

    if cabin_norm == "Business":
        base_oneway_usd *= 2.9
        base_roundtrip_usd *= 2.9
    elif cabin_norm == "Premium":
        base_oneway_usd *= 1.65
        base_roundtrip_usd *= 1.65

    records: list[FlightRecord] = []
    dep_hours = [6, 7, 8, 9, 10, 11, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22]
    ret_hours = [7, 8, 10, 12, 14, 15, 17, 19, 20, 21, 22, 23]
    emissions_options = [
        ("-21% emissions", -21),
        ("-15% emissions", -15),
        ("-9% emissions", -9),
        ("Avg emissions", 0),
        ("+6% emissions", 6),
        ("+14% emissions", 14),
    ]

    total_to_generate = count if count is not None else 5
    for i in range(total_to_generate):
        carrier_tuple = carriers[i % len(carriers)]
        if len(carrier_tuple) == 3:
            carrier_name, carrier_code, default_stops = carrier_tuple
        else:
            carrier_name, carrier_code = carrier_tuple[0], carrier_tuple[1]
            default_stops = 0

        # Alternate stops based on airline capability
        stops = default_stops if (i < len(carriers)) else (0 if i % 3 != 1 else 1)
        fl_num = f"{carrier_code} {100 + i * 29}"
        hour = dep_hours[i % len(dep_hours)]
        minute = (i * 17) % 60
        dep_time = base_d.replace(hour=hour, minute=minute, second=0)

        # Non-stop vs 1-stop realistic flight physics duration
        if stops == 0:
            dur_min = base_nonstop_mins + ((i * 13) % 40) - 20
        else:
            # Add realistic layover of 3 to 5.5 hours
            layover_mins = 180 + ((i * 35) % 150)
            dur_min = base_nonstop_mins + layover_mins

        arr_time = dep_time + timedelta(minutes=dur_min)

        # Calculate per-person rate
        if is_round_trip:
            # 1-stop has a modest discount; non-stop has slight convenience value
            stop_adj = 0.0 if stops == 0 else -60.0
            per_person_usd = round(base_roundtrip_usd + ((i * 29) % 210) + stop_adj, 2)
        else:
            stop_adj = 0.0 if stops == 0 else -35.0
            per_person_usd = round(base_oneway_usd + ((i * 19) % 110) + stop_adj, 2)

        per_person_inr = round(per_person_usd * 85.0, 2)
        total_usd = round(per_person_usd * total_pax, 2)
        total_inr = round(per_person_inr * total_pax, 2)

        # Generate paired return leg if round-trip
        return_flight_info = None
        if is_round_trip:
            ret_tuple = carriers[(i + 1) % len(carriers)]
            ret_carrier_name, ret_carrier_code = ret_tuple[0], ret_tuple[1]
            ret_stops = ret_tuple[2] if len(ret_tuple) == 3 else (0 if i % 3 != 2 else 1)
            ret_fl_num = f"{ret_carrier_code} {200 + i * 31}"
            ret_h = ret_hours[i % len(ret_hours)]
            ret_m = (i * 23) % 60
            ret_dep = ret_base_d.replace(hour=ret_h, minute=ret_m, second=0)
            if ret_stops == 0:
                ret_dur = base_nonstop_mins + (((i + 1) * 11) % 40) - 20
            else:
                ret_layover = 180 + (((i + 1) * 29) % 150)
                ret_dur = base_nonstop_mins + ret_layover
            ret_arr = ret_dep + timedelta(minutes=ret_dur)
            return_flight_info = {
                "airline": ret_carrier_name,
                "airline_code": ret_carrier_code,
                "flight_number": ret_fl_num,
                "origin": destination,
                "destination": origin,
                "departure_time": ret_dep.isoformat(),
                "arrival_time": ret_arr.isoformat(),
                "duration_minutes": ret_dur,
                "stops": ret_stops,
                "date": ret_base_d.strftime("%Y-%m-%d"),
            }

        is_top = i < 4  # Top 4 are Top Picks
        em_text, em_pct = emissions_options[i % len(emissions_options)]
        self_xfer = (i % 7 == 5)
        bag = "1 carry-on, 1 checked bag included" if (cabin_norm != "Economy" or i % 3 == 0) else "1 carry-on included"

        record = FlightRecord(
            id=slugify(f"{carrier_code}-{fl_num}-{origin}-{destination}-{flight_date}-{i}"),
            airline=carrier_name,
            airline_code=carrier_code,
            flight_number=fl_num,
            origin=origin,
            destination=destination,
            departure_time=dep_time.isoformat(),
            arrival_time=arr_time.isoformat(),
            duration_minutes=dur_min,
            stops=stops,
            price_usd=total_usd,
            price_inr=total_inr,
            cabin=cabin_norm,
            baggage=bag,
            booking_url=f"https://www.google.com/travel/flights?q=flights+from+{origin}+to+{destination}+on+{flight_date}&curr=INR&gl=in",
            source="google_flights",
            is_top_pick=is_top,
            emissions=em_text,
            emissions_diff_pct=em_pct,
            self_transfer=self_xfer,
            metadata={
                "scraped_at": datetime.now().isoformat(),
                "mode": "fallback_model",
                "is_top_pick": is_top,
                "emissions": em_text,
                "emissions_diff_pct": em_pct,
                "self_transfer": self_xfer,
                "trip_type": trip_type,
                "passengers": total_pax,
                "price_per_person_usd": per_person_usd,
                "price_per_person_inr": per_person_inr,
                "total_price_usd": total_usd,
                "total_price_inr": total_inr,
                "return_flight": return_flight_info,
            },
        )
        records.append(record)

    # Sort so top picks come first, then by price
    records.sort(key=lambda r: (not r.is_top_pick, r.price_usd))
    return records


class RecaptchaBlocked(RuntimeError):
    """Raised when Google Flights serves a recaptcha wall instead of results."""


# Only one Google Flights browser may run at a time. Timed-out scrape threads
# keep running in the background (threads cannot be cancelled), so without this
# lock a retry would launch a second Chromium while the first is still running —
# which reliably triggers Google's recaptcha and poisons every later leg.
_SCRAPE_LOCK = threading.Lock()


def _run_scrape_in_thread(**kwargs: Any) -> list[dict[str, Any]]:
    """Run the Playwright scrape in a worker thread with a fresh event loop.

    On Windows, Playwright's ``create_subprocess_exec`` (Chromium launch) only
    works on a ProactorEventLoop. ``asyncio.run()`` in a worker thread always
    gets the process policy loop (Proactor here), regardless of whatever loop
    the caller happens to be on.
    """
    acquired = _SCRAPE_LOCK.acquire(timeout=30.0)
    if not acquired:
        log.warning("Another Google Flights scrape is still shutting down; skipping this attempt")
        return []
    try:
        return asyncio.run(run_playwright_scraper(**kwargs))
    finally:
        _SCRAPE_LOCK.release()


async def run_playwright_scraper(
    origin: str,
    destination: str,
    flight_date: str,
    cabin: str = "economy",
    adults: int = 1,
    children: int = 0,
    infants_seat: int = 0,
    infants_lap: int = 0,
    currency: str = "INR",
    trip_type: str = "one-way",
    max_results: int | None = None,
) -> list[dict[str, Any]]:
    """Attempt live scrape of Google Flights using Playwright with no cutoff."""
    try:
        from scrapers.user_scrapers.google_flights_scraper.app.flights_source import PlaywrightFlightsSource
        from scrapers.user_scrapers.google_flights_scraper.app.models import Leg
    except Exception:
        from app.flights_source import PlaywrightFlightsSource
        from app.models import Leg

    leg = Leg(origin=origin.upper(), destination=destination.upper(), date=flight_date)
    params = {
        "cabin_class": cabin.lower(),
        "adults": adults,
        "children": children,
        "infants_seat": infants_seat,
        "infants_lap": infants_lap,
        "trip_type": trip_type,
        "currency": currency.upper(),
        # Lets the browser stop paginating once it has enough cards instead of
        # exhausting every result (which used to blow the 120s scrape budget and
        # silently fall back to generated data).
        "max_results": max_results,
    }
    source = PlaywrightFlightsSource(headless=True)
    # Hard ceiling so a wedged browser can never hold _SCRAPE_LOCK forever.
    raw_records, meta = await asyncio.wait_for(
        source.search_leg(leg, params), timeout=150.0
    )
    log.info("Playwright scraped %d records (feeds: %s, signals: %s)", len(raw_records), meta.get("feeds"), meta.get("signals"))

    if not raw_records and "recaptcha" in (meta.get("signals") or []):
        raise RecaptchaBlocked(
            f"Google Flights served a recaptcha wall for {origin} -> {destination}"
        )

    # Convert app.models.FlightRecord objects to dicts
    out = []
    for r in raw_records:
        data = r.model_dump()
        out.append(data)
    return out


async def search_flights(
    origin: str,
    destination: str,
    date: str = "",
    return_date: str | None = None,
    cabin: str = "economy",
    adults: int = 1,
    children: int = 0,
    infants_seat: int = 0,
    infants_lap: int = 0,
    currency: str = "INR",
    trip_type: str = "one-way",
    legs: list[dict[str, str]] | None = None,
    live: bool = True,
    max_results: int | None = None,
    allow_fallback: bool = True,
) -> list[FlightRecord]:
    """Unified entrypoint: scrapes Google Flights live without cache, extracts all flights.

    Set ``allow_fallback=False`` to guarantee that generated route-matched
    records are never returned (callers that require live data only).
    """
    records: list[FlightRecord] = []
    use_live = live if live is not None else (os.getenv("USE_PLAYWRIGHT_FLIGHTS", "1").lower() in ("1", "true", "yes"))

    # Handle multi-city trip
    if trip_type == "multi-city" and legs:
        log.info("Multi-city search with %d legs requested", len(legs))
        for leg_idx, leg_info in enumerate(legs):
            leg_orig = (leg_info.get("origin") or "").strip().upper()
            leg_dest = (leg_info.get("destination") or "").strip().upper()
            leg_dt = (leg_info.get("date") or "").strip() or (datetime.now() + timedelta(days=7 + leg_idx * 5)).strftime("%Y-%m-%d")
            if not leg_orig or not leg_dest:
                continue

            # Space out browser launches; hammering Google back-to-back is the
            # main trigger for the recaptcha wall on later legs.
            if leg_idx > 0:
                await asyncio.sleep(2.0)

            try:
                leg_records = await search_flights(
                    origin=leg_orig,
                    destination=leg_dest,
                    date=leg_dt,
                    cabin=cabin,
                    adults=adults,
                    children=children,
                    infants_seat=infants_seat,
                    infants_lap=infants_lap,
                    currency=currency,
                    trip_type="one-way",
                    live=use_live,
                    max_results=max_results,
                    allow_fallback=allow_fallback,
                )
            except Exception as leg_err:
                log.warning("Leg %d (%s -> %s) scrape failed: %s", leg_idx, leg_orig, leg_dest, leg_err)
                leg_records = []

            for r in leg_records:
                r.metadata = r.metadata or {}
                r.metadata["leg_index"] = leg_idx
                r.metadata["leg_route"] = f"{leg_orig} → {leg_dest}"
                records.append(r)
        return records

    origin = origin.strip().upper()
    destination = destination.strip().upper()
    flight_date = date.strip() or (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")

    if use_live:
        log.info("Attempting live Google Flights scrape: %s -> %s on %s (curr=%s)...", origin, destination, flight_date, currency)
        raw_dicts: list[dict[str, Any]] = []
        scrape_err: str | None = None
        leg_started = time.monotonic()
        # Retry budget: scrapes normally finish in 25-45s. Give each attempt
        # enough room to finish so its browser is never left running while the
        # next attempt starts, and allow up to 3 attempts / ~3 min per leg.
        max_attempts = 3
        per_attempt_timeout = 100.0
        max_leg_seconds = 180.0

        for attempt in range(1, max_attempts + 1):
            try:
                if sys.platform == "win32":
                    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
                raw_dicts = await asyncio.wait_for(
                    asyncio.to_thread(
                        _run_scrape_in_thread,
                        origin=origin,
                        destination=destination,
                        flight_date=flight_date,
                        cabin=cabin,
                        adults=adults,
                        children=children,
                        infants_seat=infants_seat,
                        infants_lap=infants_lap,
                        currency=currency,
                        trip_type=trip_type,
                        max_results=max_results,
                    ),
                    timeout=per_attempt_timeout,
                )
                if raw_dicts:
                    break  # got results, no need to retry
                log.warning("Live scrape returned 0 cards for %s -> %s on %s (attempt %d)", origin, destination, flight_date, attempt)
                scrape_err = "empty result set"
            except asyncio.TimeoutError:
                scrape_err = "timeout"
                log.warning("Live scrape attempt %d timed out for %s -> %s on %s", attempt, origin, destination, flight_date)
            except RecaptchaBlocked as exc:
                scrape_err = "recaptcha"
                log.warning("Live scrape attempt %d blocked by recaptcha for %s -> %s: %s", attempt, origin, destination, exc)
            except BaseException as exc:
                scrape_err = str(exc)
                log.warning("Live scrape attempt %d encountered an issue: %s", attempt, exc)

            if attempt >= max_attempts:
                break
            if time.monotonic() - leg_started > max_leg_seconds:
                log.warning("Live scrape budget exhausted for %s -> %s after %ds", origin, destination, int(time.monotonic() - leg_started))
                break
            # Recaptcha needs a longer cool-down than a plain empty/slow load.
            delay = 8.0 * attempt if scrape_err == "recaptcha" else 2.0 * attempt
            log.info("Retrying %s -> %s in %.0fs (attempt %d/%d)", origin, destination, delay, attempt + 1, max_attempts)
            await asyncio.sleep(delay)

        if not raw_dicts:
            log.warning("Live scrape failed after retries for %s -> %s on %s: %s", origin, destination, flight_date, scrape_err or "empty result set")
            records = []
        else:
            seen: set[tuple[Any, ...]] = set()
            for idx, raw in enumerate(raw_dicts):
                raw["flight_date"] = flight_date
                rec = _to_record(raw, fallback_date=flight_date, index=idx)
                if not rec:
                    continue
                # Dedupe: Google sometimes renders the same flight twice (e.g.
                # separate fare cards or pagination overlap), which would show
                # duplicate itineraries in the UI.
                key = (
                    str(rec.airline or ""),
                    str(rec.origin or ""),
                    str(rec.destination or ""),
                    str(rec.departure_time or ""),
                    int(rec.duration_minutes or 0),
                    round(float(rec.price_inr or rec.price_usd or 0), 2),
                )
                if key in seen:
                    continue
                seen.add(key)
                rec.source = "google_flights_live"
                # Default top 4 as top picks if not already set
                if not rec.is_top_pick and idx < 4:
                    rec.is_top_pick = True
                records.append(rec)
            log.info("Live scrape successfully normalized %d flight records.", len(records))

    # If round_trip is requested with return_date, also scrape the return leg.
    # Return legs are paired onto the outbound records as `return_flight`
    # metadata — they must never appear as separate search results.
    if trip_type == "round-trip" and return_date and use_live:
        log.info("Attempting live scrape for return leg: %s -> %s on %s...", destination, origin, return_date)
        try:
            return_raw: list[dict[str, Any]] = []
            return_records: list[FlightRecord] = []
            if sys.platform == "win32":
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            return_raw = await asyncio.wait_for(
                asyncio.to_thread(
                    _run_scrape_in_thread,
                    origin=destination,
                    destination=origin,
                    flight_date=return_date,
                    cabin=cabin,
                    adults=adults,
                    children=children,
                    infants_seat=infants_seat,
                    infants_lap=infants_lap,
                    currency=currency,
                    trip_type="one-way",
                    max_results=max_results,
                ),
                timeout=180.0,
            )

            for idx, raw in enumerate(return_raw):
                raw["flight_date"] = return_date
                rec = _to_record(raw, fallback_date=return_date, index=idx)
                if rec:
                    rec.source = "google_flights_live"
                    return_records.append(rec)

            if records and return_records:
                for idx, rec in enumerate(records):
                    ret = return_records[idx % len(return_records)]
                    rec.metadata = rec.metadata or {}
                    rec.metadata["trip_type"] = "round-trip"
                    rec.metadata["return_flight"] = {
                        "airline": ret.airline,
                        "airline_code": ret.airline_code,
                        "flight_number": ret.flight_number,
                        "origin": ret.origin,
                        "destination": ret.destination,
                        "departure_time": str(ret.departure_time),
                        "arrival_time": str(ret.arrival_time),
                        "duration_minutes": ret.duration_minutes,
                        "stops": ret.stops,
                        "date": return_date,
                    }
            log.info(
                "Return leg live scrape yielded %d records (paired with %d outbound).",
                len(return_records),
                len(records),
            )
        except Exception as ret_err:
            log.warning("Return leg live scrape error: %s", ret_err)

    total_pax = max(1, adults + children)
    if not records and allow_fallback:
        log.info("Generating route-matched fallback flights for %s -> %s (trip_type=%s, adults=%d)...", origin, destination, trip_type, adults)
        records = generate_fallback_flights(
            origin=origin,
            destination=destination,
            flight_date=flight_date,
            cabin=cabin,
            count=max_results or 5,
            trip_type=trip_type,
            return_date=return_date,
            adults=adults,
            children=children,
        )
    elif not records:
        log.warning(
            "No live Google Flights results for %s -> %s on %s; fallback disabled.",
            origin, destination, flight_date,
        )
        return []
    else:
        # Live scrape yielded records; ensure multi-passenger pricing and paired return flights are populated
        for idx, rec in enumerate(records):
            rec.metadata = rec.metadata or {}
            rec.metadata["passengers"] = total_pax
            rec.metadata["trip_type"] = trip_type
            # Google Flights returns the TOTAL price for all passengers (e.g. 300k for 3 pax).
            # Use it directly as total; derive per-person by dividing by total_pax.
            total_usd = float(rec.price_usd or 0.0)
            per_person_usd = round(total_usd / max(1, total_pax), 2)
            total_inr = float(rec.price_inr or round(total_usd * 85.0, 2))
            per_person_inr = round(total_inr / max(1, total_pax), 2)
            rec.metadata["price_per_person_usd"] = per_person_usd
            rec.metadata["price_per_person_inr"] = per_person_inr
            rec.metadata["total_price_usd"] = total_usd
            rec.metadata["total_price_inr"] = total_inr
            rec.price_usd = total_usd
            rec.price_inr = total_inr

            if trip_type == "round-trip" and not rec.metadata.get("return_flight"):
                ret_d = return_date or (datetime.now() + timedelta(days=21)).strftime("%Y-%m-%d")
                try:
                    ret_base = datetime.strptime(ret_d, "%Y-%m-%d")
                except Exception:
                    ret_base = datetime.now() + timedelta(days=21)
                ret_hour = [7, 9, 11, 14, 16, 18, 20, 22][idx % 8]
                ret_dep = ret_base.replace(hour=ret_hour, minute=(idx * 20) % 60, second=0)
                dur = rec.duration_minutes or 210
                ret_arr = ret_dep + timedelta(minutes=dur)
                rec.metadata["return_flight"] = {
                    "airline": rec.airline,
                    "airline_code": rec.airline_code,
                    "flight_number": f"{rec.airline_code} {200 + idx * 19}",
                    "origin": destination,
                    "destination": origin,
                    "departure_time": ret_dep.isoformat(),
                    "arrival_time": ret_arr.isoformat(),
                    "duration_minutes": dur,
                    "stops": rec.stops,
                    "date": ret_d,
                }

    if max_results and max_results > 0:
        return records[:max_results]
    return records


def save_flights_to_db(records: list[FlightRecord], session: Any | None = None) -> int:
    """Save or upsert flight records into SQLite database."""
    try:
        from sqlmodel import Session, select
        from backend.database.db import engine
        from backend.database.models import Flight

        def _do_save(s: Any) -> int:
            saved = 0
            try:
                # Fast chunked pre-fetch of existing flight records
                rec_ids = [rec.id for rec in records if rec.id]
                existing_map = {}
                chunk_size = 400
                for i in range(0, len(rec_ids), chunk_size):
                    chunk = rec_ids[i:i + chunk_size]
                    stmt = select(Flight).where(Flight.id.in_(chunk))
                    for f in s.exec(stmt).all():
                        existing_map[f.id] = f

                for rec in records:
                    existing = existing_map.get(rec.id)
                    meta = rec.metadata.copy() if rec.metadata else {}
                    meta["is_top_pick"] = rec.is_top_pick
                    meta["price_inr"] = rec.price_inr
                    meta["emissions"] = rec.emissions
                    meta["emissions_diff_pct"] = rec.emissions_diff_pct
                    meta["self_transfer"] = rec.self_transfer
                    payload = {
                        "airline": rec.airline,
                        "airline_code": rec.airline_code,
                        "flight_number": rec.flight_number,
                        "origin": rec.origin,
                        "destination": rec.destination,
                        "departure_time": str(rec.departure_time),
                        "arrival_time": str(rec.arrival_time),
                        "duration_minutes": rec.duration_minutes,
                        "stops": rec.stops,
                        "price_usd": rec.price_usd,
                        "cabin": rec.cabin,
                        "baggage": rec.baggage,
                        "booking_url": rec.booking_url,
                        "source": rec.source,
                        "metadata_json": meta,
                    }
                    if existing:
                        for k, v in payload.items():
                            setattr(existing, k, v)
                    else:
                        s.add(Flight(id=rec.id, **payload))
                    saved += 1
                s.commit()
                log.info("Successfully saved/updated %d flights in database.", saved)
                return saved
            except Exception as exc:
                try:
                    s.rollback()
                except Exception:
                    pass
                log.warning("Database write skipped/rolled back: %s", exc)
                return 0

        if session is not None:
            return _do_save(session)
        with Session(engine) as s:
            return _do_save(s)
    except Exception as e:
        log.warning("Could not persist flights to DB: %s", e)
        return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Google Flights Scraper Runner")
    parser.add_argument("--origin", required=True, help="Origin airport IATA code (e.g. SFO)")
    parser.add_argument("--destination", required=True, help="Destination airport IATA code (e.g. JFK)")
    parser.add_argument("--date", default="", help="Departure date YYYY-MM-DD")
    parser.add_argument("--return-date", default="", help="Return date YYYY-MM-DD")
    parser.add_argument("--cabin", default="economy", help="Cabin class (economy, premium, business, first)")
    parser.add_argument("--adults", type=int, default=1, help="Number of adults")
    parser.add_argument("--live", action="store_true", help="Attempt live Playwright browser scraping")
    parser.add_argument("--save", action="store_true", help="Save results to Mindtrip SQLite database")
    parser.add_argument("--out", default="", help="File path to save JSON results")
    args = parser.parse_args()

    outbound = args.date or (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    results = search_flights(
        origin=args.origin,
        destination=args.destination,
        date=outbound,
        return_date=args.return_date,
        cabin=args.cabin,
        adults=args.adults,
        live=args.live,
    )

    print(f"\n--- Found {len(results)} Flights for {args.origin.upper()} -> {args.destination.upper()} on {outbound} ---")
    for fl in results[:10]:
        print(f"• {fl.airline} ({fl.flight_number}): {fl.origin} -> {fl.destination} | ${fl.price_usd} | {fl.duration_minutes}m | {fl.stops} stops | {fl.departure_time}")

    if args.save:
        save_flights_to_db(results)

    if args.out:
        data = [r.model_dump(mode="json") for r in results]
        Path(args.out).write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"Saved results to {args.out}")


if __name__ == "__main__":
    main()
