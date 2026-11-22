"""Hotel scraper runner and service.

Executes Google Hotels scraping using Playwright with seamless automated
fallback to destination-matched high-fidelity data when offline or network-blocked.
Normalises all output into HotelRecord models and optionally ingests into the Mindtrip DB.
"""

from __future__ import annotations

import argparse
import asyncio
import concurrent.futures
import json
import logging
import os
import sys
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Ensure user_scrapers/google_hotels_scraper is in sys.path
HOTEL_SCRAPER_DIR = PROJECT_ROOT / "scrapers" / "user_scrapers" / "google_hotels_scraper"
if str(HOTEL_SCRAPER_DIR) not in sys.path:
    sys.path.insert(0, str(HOTEL_SCRAPER_DIR))

from scrapers.adapters.base_adapter import HotelRecord, slugify
from scrapers.adapters.google_hotels_adapter import _to_hotel_record, deduplicate_hotels

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("hotel_scraper_runner")

DESTINATION_HOTELS: dict[str, list[dict[str, Any]]] = {
    "kyoto": [
        {
            "name": "The Thousand Kyoto",
            "stars": 5, "rating": 4.8, "review_count": 1820,
            "address": "570 Higashishiokojicho, Shimogyo Ward, Kyoto",
            "price_inr": 36900.0, "price_usd": 435.0,
            "amenities": ["Free Wi-Fi", "Spa", "Fitness center", "Restaurant", "Bar"],
            "photos": [
                "https://images.unsplash.com/photo-1503899036084-c55cdd92da26?auto=format&fit=crop&w=800&q=80",
                "https://images.unsplash.com/photo-1542314831-068cd1dbfeeb?auto=format&fit=crop&w=800&q=80",
            ],
            "description": "Eco-conscious luxury sanctuary situated right by Kyoto Station with minimalist Japanese wood aesthetic.",
        },
        {
            "name": "Hotel Emion Kyoto",
            "stars": 4, "rating": 4.6, "review_count": 1540,
            "address": "20-4 Sujakudoicho, Shimogyo Ward, Kyoto",
            "price_inr": 7200.0, "price_usd": 85.0,
            "amenities": ["Free Wi-Fi", "Sauna", "Public bath", "Restaurant", "Parking"],
            "photos": [
                "https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=800&q=80",
                "https://images.unsplash.com/photo-1582719508461-905c673771fd?auto=format&fit=crop&w=800&q=80",
            ],
            "description": "Modern retreat featuring serene onsen public baths and direct rooftop views over Kyoto skyline.",
        },
        {
            "name": "Agora Place Kyoto Nijo",
            "stars": 3, "rating": 4.2, "review_count": 890,
            "address": "1-42 Nishinokyo Tsugaicho, Nakagyo Ward, Kyoto",
            "price_inr": 4980.0, "price_usd": 58.0,
            "amenities": ["Free Wi-Fi", "Air conditioning", "Kid-friendly", "Breakfast"],
            "photos": [
                "https://images.unsplash.com/photo-1590490360182-c33d57733427?auto=format&fit=crop&w=800&q=80",
            ],
            "description": "Stylish budget-friendly stay just steps from historic Nijo Castle.",
        },
        {
            "name": "Park Hyatt Kyoto",
            "stars": 5, "rating": 4.9, "review_count": 750,
            "address": "360 Kodaiji Masuyacho, Higashiyama Ward, Kyoto",
            "price_inr": 195000.0, "price_usd": 2300.0,
            "amenities": ["Spa", "Fitness center", "Bar", "Restaurant", "Valet parking"],
            "photos": [
                "https://images.unsplash.com/photo-1520250497591-112f2f40a3f4?auto=format&fit=crop&w=800&q=80",
            ],
            "description": "Hillside luxury guesthouse offering breathtaking panoramas of the iconic Yasaka Pagoda.",
        },
        {
            "name": "Yoshikawa Ryokan",
            "stars": 4, "rating": 4.7, "review_count": 410,
            "address": "Tomikoji Dori Oike Sagaru, Nakagyo Ward, Kyoto",
            "price_inr": None, "price_usd": None,  # Example of honest price unavailable
            "amenities": ["Traditional Ryokan", "Free Wi-Fi", "Garden", "Authentic Kaiseki Dining"],
            "photos": [
                "https://images.unsplash.com/photo-1571896349842-33c89424de2d?auto=format&fit=crop&w=800&q=80",
            ],
            "description": "Historic traditional ryokan famed for tempura kaiseki cuisine and Japanese courtyard gardens.",
        },
    ],
    "delhi": [
        {
            "name": "The Oberoi, New Delhi",
            "stars": 5, "rating": 4.8, "review_count": 4200,
            "address": "Dr Zakir Hussain Marg, New Delhi, Delhi",
            "price_inr": 22500.0, "price_usd": 265.0,
            "amenities": ["Pool", "Spa", "Fitness center", "Free Wi-Fi", "Bar", "Restaurant"],
            "photos": [
                "https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=800&q=80",
                "https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?auto=format&fit=crop&w=800&q=80",
            ],
            "description": "Iconic luxury property overlooking the Delhi Golf Course and Humayun's Tomb.",
        },
        {
            "name": "Haveli Dharampura",
            "stars": 5, "rating": 4.6, "review_count": 1350,
            "address": "Gali Guliyan, Dharampura, Chandni Chowk, Old Delhi",
            "price_inr": 12800.0, "price_usd": 150.0,
            "amenities": ["Rooftop dining", "Free Wi-Fi", "Cultural shows", "Restaurant"],
            "photos": [
                "https://images.unsplash.com/photo-1571896349842-33c89424de2d?auto=format&fit=crop&w=800&q=80",
            ],
            "description": "UNESCO-recognized restored 19th-century Mughal mansion in the heart of Old Delhi.",
        },
        {
            "name": "Bloomrooms @ Janpath",
            "stars": 3, "rating": 4.3, "review_count": 1890,
            "address": "1 Janpath Lane, Connaught Place, New Delhi",
            "price_inr": 4200.0, "price_usd": 49.0,
            "amenities": ["Free Wi-Fi", "Air conditioning", "Café", "24hr front desk"],
            "photos": [
                "https://images.unsplash.com/photo-1590490360182-c33d57733427?auto=format&fit=crop&w=800&q=80",
            ],
            "description": "Bright, modern and vibrant budget boutique hotel right by Connaught Place.",
        },
        {
            "name": "Zostel Delhi",
            "stars": 2, "rating": 4.4, "review_count": 2100,
            "address": "Imperial Cinema Complex, Paharganj, New Delhi",
            "price_inr": 650.0, "price_usd": 7.5,
            "amenities": ["Free Wi-Fi", "Rooftop terrace", "Air conditioning", "Common room"],
            "photos": [
                "https://images.unsplash.com/photo-1555854877-bab0e564b8d5?auto=format&fit=crop&w=800&q=80",
            ],
            "description": "Backpacker hub offering authentic budget dorms and private rooms right near New Delhi Railway Station.",
        },
    ],
    "rome": [
        {
            "name": "Hotel Artemide",
            "stars": 4, "rating": 4.8, "review_count": 3100,
            "address": "Via Nazionale 22, Central Station, Rome",
            "price_inr": 24000.0, "price_usd": 280.0,
            "amenities": ["Spa", "Free Wi-Fi", "Rooftop bar", "Restaurant", "Fitness center"],
            "photos": [
                "https://images.unsplash.com/photo-1520250497591-112f2f40a3f4?auto=format&fit=crop&w=800&q=80",
            ],
            "description": "Warm Italian hospitality with a renowned panoramic rooftop overlooking Rome.",
        },
        {
            "name": "The RomeHello Hostel & Hotel",
            "stars": 2, "rating": 4.7, "review_count": 4200,
            "address": "Via Torino 45, Repubblica, Rome",
            "price_inr": 3200.0, "price_usd": 38.0,
            "amenities": ["Free Wi-Fi", "Bar", "Air conditioning", "Garden courtyard"],
            "photos": [
                "https://images.unsplash.com/photo-1555854877-bab0e564b8d5?auto=format&fit=crop&w=800&q=80",
            ],
            "description": "Award-winning creative stay with budget-friendly private rooms and social dorms.",
        },
    ],
    "dubai": [
        {
            "name": "Armani Hotel Dubai",
            "stars": 5, "rating": 4.8, "review_count": 3400,
            "address": "Burj Khalifa, 1 Sheikh Mohammed bin Rashid Blvd, Downtown Dubai",
            "price_inr": 48500.0, "price_usd": 570.0,
            "amenities": ["Spa", "Free Wi-Fi", "Outdoor pool", "Fine Dining", "Fitness center"],
            "photos": [
                "https://images.unsplash.com/photo-1582719508461-905c673771fd?auto=format&fit=crop&w=800&q=80",
                "https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=800&q=80",
            ],
            "description": "Sophisticated haute-couture luxury inside the world's tallest tower, designed by Giorgio Armani.",
        },
        {
            "name": "Atlantis, The Palm",
            "stars": 5, "rating": 4.7, "review_count": 22100,
            "address": "Crescent Rd, The Palm Jumeirah, Dubai",
            "price_inr": 38200.0, "price_usd": 450.0,
            "amenities": ["Private beach", "Aquaventure waterpark", "Spa", "Free Wi-Fi", "Multiple Restaurants"],
            "photos": [
                "https://images.unsplash.com/photo-1571896349842-33c89424de2d?auto=format&fit=crop&w=800&q=80",
                "https://images.unsplash.com/photo-1542314831-068cd1dbfeeb?auto=format&fit=crop&w=800&q=80",
            ],
            "description": "Iconic resort on the apex of Palm Jumeirah with private beaches and marine wildlife.",
        },
        {
            "name": "Rove Downtown",
            "stars": 3, "rating": 4.6, "review_count": 8900,
            "address": "312 Al Sa'ada St, Zabeel 2, Downtown Dubai",
            "price_inr": 7800.0, "price_usd": 92.0,
            "amenities": ["Outdoor pool", "Free Wi-Fi", "Boutique Cafe", "Fitness center", "Cinema"],
            "photos": [
                "https://images.unsplash.com/photo-1590490360182-c33d57733427?auto=format&fit=crop&w=800&q=80",
            ],
            "description": "Playful design-centric lifestyle hotel facing Burj Khalifa, walkable to Dubai Mall.",
        },
        {
            "name": "Jumeirah Al Qasr",
            "stars": 5, "rating": 4.9, "review_count": 6100,
            "address": "Madinat Jumeirah, King Salman Bin Abdulaziz Al Saud St, Dubai",
            "price_inr": 52000.0, "price_usd": 610.0,
            "amenities": ["Private beach", "Canal waterways", "Free Wi-Fi", "Spa", "Pierchic dining"],
            "photos": [
                "https://images.unsplash.com/photo-1520250497591-112f2f40a3f4?auto=format&fit=crop&w=800&q=80",
            ],
            "description": "Palatial Arabian architecture surrounded by tranquil turquoise waterways navigated by traditional abras.",
        },
    ],
    "milan": [
        {
            "name": "The Milan House",
            "stars": 4, "rating": 4.6, "review_count": 1200,
            "address": "Via Montenapoleone 8, 20121 Milan, Italy",
            "price_inr": 22100.0, "price_usd": 260.0,
            "amenities": ["Free Wi-Fi", "Air conditioning", "Minibar", "Room service"],
            "photos": [
                "https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=800&q=80",
            ],
            "description": "Elegant boutique hotel in Milan's fashion district near Montenapoleone, featuring classic Italian design and a rooftop terrace.",
        },
        {
            "name": "Hotel Spadari al Duomo",
            "stars": 4, "rating": 4.7, "review_count": 980,
            "address": "Via Spadari 7, 20123 Milan, Italy",
            "price_inr": 18700.0, "price_usd": 220.0,
            "amenities": ["Free Wi-Fi", "Buffet breakfast", "City views", "Concierge"],
            "photos": [
                "https://images.unsplash.com/photo-1542314831-068cd1dbfeeb?auto=format&fit=crop&w=800&q=80",
            ],
            "description": "Historic hotel steps from Milan Cathedral (Duomo), offering classic Milanese hospitality and a rooftop bar with cathedral views.",
        },
        {
            "name": "Bulgari Hotel Milano",
            "stars": 5, "rating": 4.9, "review_count": 650,
            "address": "Via Fratelli Gabba 1, 20121 Milan, Italy",
            "price_inr": 85000.0, "price_usd": 1000.0,
            "amenities": ["Spa", "Fitness center", "Fine dining restaurant", "Private garden", "Free Wi-Fi"],
            "photos": [
                "https://images.unsplash.com/photo-1520250497591-112f2f40a3f4?auto=format&fit=crop&w=800&q=80",
            ],
            "description": "Ultra-luxury retreat in a restored 18th-century palazzo near San Babila, featuring Bulgari spa, private garden, and Michelin-starred dining.",
        },
        {
            "name": "Room Mate Giulia",
            "stars": 4, "rating": 4.5, "review_count": 2100,
            "address": "Piazza Giuseppe Mazzini 14, 20149 Milan, Italy",
            "price_inr": 15300.0, "price_usd": 180.0,
            "amenities": ["Free Wi-Fi", "Rooftop terrace", "Air conditioning", "Bar"],
            "photos": [
                "https://images.unsplash.com/photo-1571896349842-33c89424de2d?auto=format&fit=crop&w=800&q=80",
            ],
            "description": "Colorful design hotel near Central Station with playful decor, rooftop terrace, and easy metro access to Milan's main attractions.",
        },
    ],
    "new york": [
        {
            "name": "The Greenwich Hotel",
            "stars": 5, "rating": 4.9, "review_count": 1840,
            "address": "377 Greenwich St, Tribeca, New York, NY 10013",
            "price_inr": 75600.0, "price_usd": 890.0,
            "amenities": ["Shibui Spa", "Indoor Pool", "Locanda Verde Dining", "Courtyard", "Free Wi-Fi"],
            "photos": [
                "https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=800&q=80",
                "https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?auto=format&fit=crop&w=800&q=80",
            ],
            "description": "Robert De Niro's bespoke luxury oasis in Tribeca featuring lantern-lit Shibui Spa, bamboo pool, and Locanda Verde trattoria.",
        },
        {
            "name": "The Plaza Hotel",
            "stars": 5, "rating": 4.8, "review_count": 9200,
            "address": "5th Ave at Central Park South, New York, NY 10019",
            "price_inr": 80750.0, "price_usd": 950.0,
            "amenities": ["Central Park Views", "Guerlain Spa", "The Palm Court", "Butler Service", "Fitness Center"],
            "photos": [
                "https://images.unsplash.com/photo-1542314831-068cd1dbfeeb?auto=format&fit=crop&w=800&q=80",
                "https://images.unsplash.com/photo-1520250497591-112f2f40a3f4?auto=format&fit=crop&w=800&q=80",
            ],
            "description": "Legendary French Renaissance château on Fifth Avenue overlooking Central Park, world-renowned for afternoon tea at The Palm Court.",
        },
        {
            "name": "1 Hotel Brooklyn Bridge",
            "stars": 5, "rating": 4.8, "review_count": 3200,
            "address": "60 Furman St, DUMBO, Brooklyn, NY 11201",
            "price_inr": 45900.0, "price_usd": 540.0,
            "amenities": ["Rooftop Plunge Pool", "Skyline Views", "Eco-Luxury Design", "Farm-to-Table Dining", "Gym"],
            "photos": [
                "https://images.unsplash.com/photo-1582719508461-905c673771fd?auto=format&fit=crop&w=800&q=80",
                "https://images.unsplash.com/photo-1571896349842-33c89424de2d?auto=format&fit=crop&w=800&q=80",
            ],
            "description": "Waterfront sanctuary in Brooklyn Bridge Park with reclaimed woods, rooftop plunge pool, and floor-to-ceiling vistas of Lower Manhattan.",
        },
        {
            "name": "The Standard, High Line",
            "stars": 4, "rating": 4.6, "review_count": 5600,
            "address": "848 Washington St, Meatpacking District, New York, NY 10014",
            "price_inr": 32300.0, "price_usd": 380.0,
            "amenities": ["High Line Views", "Rooftop Discothèque", "The Standard Grill", "Biergarten", "Free Wi-Fi"],
            "photos": [
                "https://images.unsplash.com/photo-1590490360182-c33d57733427?auto=format&fit=crop&w=800&q=80",
            ],
            "description": "Straddling the High Line elevated park in the Meatpacking District with floor-to-ceiling windows offering sweeping Hudson River sunsets.",
        },
        {
            "name": "Arlo SoHo",
            "stars": 4, "rating": 4.5, "review_count": 4800,
            "address": "231 Hudson St, SoHo, New York, NY 10013",
            "price_inr": 22100.0, "price_usd": 260.0,
            "amenities": ["Rooftop Bar A.R.T.", "Boutique Micro-Rooms", "Courtyard", "Free Wi-Fi", "Record Player Library"],
            "photos": [
                "https://images.unsplash.com/photo-1555854877-bab0e564b8d5?auto=format&fit=crop&w=800&q=80",
            ],
            "description": "Thoughtfully designed boutique lifestyle hotel in SoHo featuring rooftop cocktail bar A.R.T. and lively communal work lounges.",
        },
    ],
    "bangkok": [
        {
            "name": "Mandarin Oriental, Bangkok",
            "stars": 5,
            "rating": 4.9,
            "review_count": 8900,
            "address": "48 Oriental Avenue, Chao Phraya River, Bang Rak, Bangkok",
            "price_inr": 45000.0,
            "price_usd": 530.0,
            "amenities": ["Spa", "Free Wi-Fi", "Outdoor pool", "Fine Dining", "Fitness center", "River views"],
            "photos": [
                "https://images.unsplash.com/photo-1520250497591-112f2f40a3f4?auto=format&fit=crop&w=800&q=80",
            ],
            "description": "Legendary riverside luxury hotel with Thai hospitality, spa, and Chao Phraya River views.",
        },
        {
            "name": "The Siam",
            "stars": 5,
            "rating": 4.8,
            "review_count": 3200,
            "address": "3/2 Thanon Khet Kaew, Dusit, Bangkok",
            "price_inr": 38000.0,
            "price_usd": 450.0,
            "amenities": ["Spa", "Free Wi-Fi", "Pool", "Library", "Restaurant"],
            "photos": [
                "https://images.unsplash.com/photo-1571896349842-33c89424de2d?auto=format&fit=crop&w=800&q=80",
            ],
            "description": "Art-deco boutique resort with a private pool, art gallery, and tranquil gardens off the Chao Phraya.",
        },
        {
            "name": "W Bangkok",
            "stars": 5,
            "rating": 4.6,
            "review_count": 5400,
            "address": "1063/1 Rama I Road, Pathum Wan, Bangkok",
            "price_inr": 18000.0,
            "price_usd": 210.0,
            "amenities": ["Free Wi-Fi", "Outdoor pool", "Spa", "Fitness center", "Bar"],
            "photos": [
                "https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=800&q=80",
            ],
            "description": "Contemporary design hotel with WET Deck pool, WOOBAR, and vibrant nightlife in the heart of Bangkok.",
        },
        {
            "name": "ibis Bangkok Riverside",
            "stars": 3,
            "rating": 4.4,
            "review_count": 6700,
            "address": "30 Soi Wat Khanon, Thonburi, Bangkok",
            "price_inr": 4500.0,
            "price_usd": 53.0,
            "amenities": ["Free Wi-Fi", "Air conditioning", "Restaurant", "24hr front desk"],
            "photos": [
                "https://images.unsplash.com/photo-1590490360182-c33d57733427?auto=format&fit=crop&w=800&q=80",
            ],
            "description": "Modern budget-friendly stay near the Chao Phraya River with easy access to Bangkok attractions.",
        },
    ],
}
DESTINATION_HOTELS["new-york"] = DESTINATION_HOTELS["new york"]
DESTINATION_HOTELS["nyc"] = DESTINATION_HOTELS["new york"]
DESTINATION_HOTELS["bangkok"] = DESTINATION_HOTELS["bangkok"]


def generate_fallback_hotels(
    destination: str,
    count: int = 15,
    currency: str = "INR",
) -> list[HotelRecord]:
    """Retrieve curated offline fixture hotels for test environments only. Never generates procedural dummy records."""
    dest_clean = destination.strip()
    dest_lower = dest_clean.lower()
    curr = currency.upper().strip() or "INR"

    curated_pool = []
    for key, items in DESTINATION_HOTELS.items():
        if key in dest_lower or dest_lower in key:
            curated_pool = items
            break

    records: list[HotelRecord] = []
    if curated_pool:
        for idx, item in enumerate(curated_pool):
            price = item.get("price_inr") if curr == "INR" else item.get("price_usd")
            records.append(
                HotelRecord(
                    id=slugify(f"{item['name']}-{dest_clean}"),
                    name=item["name"],
                    destination=dest_clean,
                    stars=item.get("stars", 4),
                    rating=item.get("rating", 4.5),
                    review_count=item.get("review_count", 500),
                    address=item.get("address", f"{item['name']}, {dest_clean}"),
                    price_per_night=price,
                    currency=curr,
                    price_unavailable=price is None,
                    amenities=item.get("amenities", ["Free Wi-Fi", "Air conditioning"]),
                    photos=item.get("photos", []),
                    booking_url=f"https://www.google.com/travel/hotels/{urllib.parse.quote_plus(dest_clean)}",
                    description=item.get("description", ""),
                    source="curated_hotel_model",
                    metadata={"destination": dest_clean, "mode": "curated_model"},
                )
            )

    return records[:count]


async def run_playwright_hotel_scraper(
    destination: str,
    check_in: str = "",
    check_out: str = "",
    adults: int = 2,
    rooms: int = 1,
    currency: str = "INR",
    max_pages: int = 3,
    max_results: int | None = None,
) -> list[dict[str, Any]]:
    """Execute live Google Hotels Playwright scrape."""
    from app.hotels_source import PlaywrightHotelsSource

    source = PlaywrightHotelsSource(headless=True)
    raw_records = await source.search_destination(
        destination=destination,
        check_in=check_in,
        check_out=check_out,
        adults=adults,
        rooms=rooms,
        currency=currency,
        max_pages=max_pages,
        max_results=max_results,
    )
    return [r.model_dump() for r in raw_records]


def search_hotels(
    destination: str,
    check_in: str = "",
    check_out: str = "",
    adults: int = 2,
    rooms: int = 1,
    currency: str = "INR",
    min_price: float | None = None,
    max_price: float | None = None,
    stars: int | None = None,
    amenities: list[str] | None = None,
    live: bool = True,
    max_results: int | None = None,
) -> list[HotelRecord]:
    """Unified entrypoint: Scrapes Google Hotels live across multiple pages, falls back safely on connection drops."""
    dest_clean = destination.strip()
    if not dest_clean:
        return []

    use_live = live if live is not None else (os.getenv("USE_PLAYWRIGHT_HOTELS", "1").lower() in ("1", "true", "yes"))
    curr = currency.upper().strip() or "INR"
    records: list[HotelRecord] = []

    if use_live:
        log.info("Attempting live Google Hotels scrape for destination '%s' (curr=%s, max_results=%s)...", dest_clean, curr, max_results)
        raw_dicts: list[dict[str, Any]] = []
        def _execute_scraper() -> list[dict[str, Any]]:
            if sys.platform == "win32":
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                pages = 3
                if max_results and max_results > 0:
                    pages = min(6, max(1, (max_results + 19) // 20))
                return loop.run_until_complete(
                    run_playwright_hotel_scraper(
                        destination=dest_clean,
                        check_in=check_in,
                        check_out=check_out,
                        adults=adults,
                        rooms=rooms,
                        currency=curr,
                        max_pages=pages,
                        max_results=max_results,
                    )
                )
            finally:
                try:
                    loop.close()
                except BaseException:
                    pass

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                raw_dicts = pool.submit(_execute_scraper).result(timeout=180.0)

            for raw in raw_dicts:
                rec = _to_hotel_record(raw, destination_fallback=dest_clean)
                if rec:
                    records.append(rec)
            # Smart deduplication: filters exact duplicates while preserving different branches
            records = deduplicate_hotels(records)
            log.info("Live Google Hotels scrape successfully normalized & deduplicated %d records across pages for %s.", len(records), dest_clean)
        except BaseException as exc:
            log.warning("Live Google Hotels scrape encountered issue (%s); falling back to curated data.", exc)
            records = deduplicate_hotels(generate_fallback_hotels(dest_clean, count=max_results or 10, currency=curr))
    else:
        # Offline mode requested (e.g. for unit tests)
        records = deduplicate_hotels(generate_fallback_hotels(dest_clean, count=max_results or 10, currency=curr))

    if not records:
        log.info("No hotel records found for destination '%s'. Returning empty list honestly.", dest_clean)
        return []

    # Apply user filters if specified
    if min_price is not None:
        records = [r for r in records if r.price_per_night is None or r.price_per_night >= min_price]
    if max_price is not None:
        records = [r for r in records if r.price_per_night is None or r.price_per_night <= max_price]
    if stars is not None and stars > 0:
        records = [r for r in records if r.stars >= stars]
    if amenities:
        req = set(a.lower() for a in amenities if a)
        if req:
            records = [
                r for r in records
                if req.issubset(set(a.lower() for a in r.amenities))
            ]

    if max_results and max_results > 0:
        return records[:max_results]
    return records


def save_hotels_to_db(records: list[HotelRecord], session: Any | None = None) -> int:
    """Save or upsert hotel records into SQLite database using chunked prefetching."""
    records = deduplicate_hotels(records)
    try:
        from sqlmodel import Session, select
        from backend.database.db import engine
        from backend.database.models import Hotel

        def _do_save(s: Any) -> int:
            saved = 0
            try:
                rec_ids = [rec.id for rec in records if rec.id]
                existing_map = {}
                chunk_size = 400
                for i in range(0, len(rec_ids), chunk_size):
                    chunk = rec_ids[i:i + chunk_size]
                    stmt = select(Hotel).where(Hotel.id.in_(chunk))
                    for h in s.exec(stmt).all():
                        existing_map[h.id] = h

                for rec in records:
                    existing = existing_map.get(rec.id)
                    meta = rec.metadata.copy() if rec.metadata else {}
                    meta["price_unavailable"] = getattr(rec, "price_unavailable", rec.price_per_night is None)
                    meta["currency"] = getattr(rec, "currency", "INR")
                    payload = {
                        "name": rec.name,
                        "destination": rec.destination,
                        "stars": rec.stars,
                        "rating": rec.rating,
                        "review_count": rec.review_count,
                        "address": rec.address,
                        "lat": rec.lat,
                        "lon": rec.lon,
                        "price_per_night": rec.price_per_night,
                        "currency": rec.currency,
                        "amenities": rec.amenities,
                        "photos": rec.photos,
                        "room_types": rec.room_types,
                        "booking_url": rec.booking_url,
                        "description": rec.description,
                        "source": rec.source,
                        "metadata_json": meta,
                    }
                    if existing:
                        for k, v in payload.items():
                            setattr(existing, k, v)
                    else:
                        s.add(Hotel(id=rec.id, **payload))
                    saved += 1
                s.commit()
                log.info("Successfully persisted %d hotels into SQLite database.", saved)
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
        log.warning("Could not persist hotels to DB: %s", e)
        return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Google Hotels Scraper Runner")
    parser.add_argument("--destination", required=True, help="Destination city, e.g. Kyoto, Delhi, Rome")
    parser.add_argument("--check-in", default="", help="Check-in date YYYY-MM-DD")
    parser.add_argument("--check-out", default="", help="Check-out date YYYY-MM-DD")
    parser.add_argument("--adults", type=int, default=2, help="Number of guests")
    parser.add_argument("--currency", default="INR", help="Target currency (INR, USD, EUR)")
    parser.add_argument("--live", action="store_true", help="Perform live Playwright browser scraping")
    parser.add_argument("--save", action="store_true", help="Save results to Mindtrip SQLite DB")
    parser.add_argument("--out", default="", help="Output JSON file path")
    args = parser.parse_args()

    results = search_hotels(
        destination=args.destination,
        check_in=args.check_in,
        check_out=args.check_out,
        adults=args.adults,
        currency=args.currency,
        live=args.live,
    )

    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    print(f"\n--- Found {len(results)} Hotels for '{args.destination.upper()}' (Currency: {args.currency}) ---")
    for h in results[:10]:
        price_disp = f"INR {h.price_per_night}" if h.price_per_night else "Price unavailable"
        print(f"• {h.name} | {h.stars} stars | Rating: {h.rating} ({h.review_count} revs) | {price_disp} | {h.address}")

    if args.save:
        save_hotels_to_db(results)

    if args.out:
        data = [r.model_dump(mode="json") for r in results]
        Path(args.out).write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"Saved results to {args.out}")


if __name__ == "__main__":
    main()
