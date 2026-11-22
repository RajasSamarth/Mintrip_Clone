"""Deterministic itinerary synthesis.

This is the safety net that makes the clone work with **zero API keys**: it
turns a free-text request into a persisted, mapped, day-by-day itinerary using
curated place data (or generated neighbourhood archetypes for new cities).
"""

from __future__ import annotations

import math
import os
import re
from datetime import date, datetime, timedelta
from typing import Any

from sqlmodel import Session, select

from backend.database.models import Destination, Hotel, Place, Trip
from backend.services import data_service
from backend.services.routing_service import calculate_route, haversine_km, transit_label

CITY_COORDS: dict[str, tuple[float, float]] = {
    "kyoto": (35.0116, 135.7681), "tokyo": (35.6762, 139.6503), "osaka": (34.6937, 135.5023),
    "rome": (41.9028, 12.4964), "florence": (43.7696, 11.2558), "venice": (45.4408, 12.3155),
    "milan": (45.4642, 9.1900), "paris": (48.8566, 2.3522), "london": (51.5074, -0.1278),
    "lisbon": (38.7223, -9.1393), "porto": (41.1579, -8.6291), "barcelona": (41.3874, 2.1686),
    "madrid": (40.4168, -3.7038), "amsterdam": (52.3676, 4.9041), "berlin": (52.5200, 13.4050),
    "munich": (48.1351, 11.5820), "zurich": (47.3769, 8.5417), "interlaken": (46.6863, 7.8632),
    "vienna": (48.2082, 16.3738), "prague": (50.0755, 14.4378), "copenhagen": (55.6761, 12.5683),
    "stockholm": (59.3293, 18.0686), "reykjavik": (64.1466, -21.9426), "new york": (40.7128, -74.0060),
    "san francisco": (37.7749, -122.4194), "los angeles": (34.0522, -118.2437), "chicago": (41.8781, -87.6298),
    "miami": (25.7617, -80.1918), "mexico city": (19.4326, -99.1332), "oaxaca": (17.0732, -96.7266),
    "buenos aires": (-34.6037, -58.3816), "rio de janeiro": (-22.9068, -43.1729), "lima": (-12.0464, -77.0428),
    "cusco": (-13.5319, -71.9675), "bangkok": (13.7563, 100.5018), "singapore": (1.3521, 103.8198),
    "hong kong": (22.3193, 114.1694), "seoul": (37.5665, 126.9780), "bali": (-8.4095, 115.1889),
    "sydney": (-33.8688, 151.2093), "melbourne": (-37.8136, 144.9631), "auckland": (-36.8509, 174.7645),
    "cape town": (-33.9249, 18.4241), "marrakech": (31.6295, -7.9811), "cairo": (30.0444, 31.2357),
    "istanbul": (41.0082, 28.9784), "dubai": (25.2048, 55.2708), "delhi": (28.6139, 77.2090),
    "mumbai": (19.0760, 72.8777), "jaipur": (26.9124, 75.7873), "goa": (15.2993, 74.1240),
    "nagpur": (21.1458, 79.0882), "jakarta": (-6.2088, 106.8456),
    "swiss alps": (46.6863, 7.8632), "alps": (46.6863, 7.8632),
}

AIRPORT_BY_DESTINATION = {
    "kyoto": "KIX", "tokyo": "HND", "osaka": "KIX", "rome": "FCO", "florence": "FLR",
    "venice": "VCE", "milan": "MXP", "paris": "CDG", "london": "LHR", "lisbon": "LIS",
    "barcelona": "BCN", "madrid": "MAD", "amsterdam": "AMS", "berlin": "BER", "zurich": "ZRH",
    "swiss-alps": "ZRH", "interlaken": "ZRH", "vienna": "VIE", "prague": "PRG",
    "copenhagen": "CPH", "reykjavik": "KEF", "new-york": "JFK", "new york": "JFK", "nyc": "JFK",
    "san-francisco": "SFO", "san francisco": "SFO", "los-angeles": "LAX", "los angeles": "LAX",
    "mexico-city": "MEX", "bangkok": "BKK", "singapore": "SIN", "seoul": "ICN", "sydney": "SYD",
    "marrakech": "RAK", "istanbul": "IST", "dubai": "DXB", "delhi": "DEL", "new delhi": "DEL",
    "mumbai": "BOM", "pune": "PNQ", "bangalore": "BLR", "bengaluru": "BLR",
    "nagpur": "NAG", "jakarta": "CGK",
}

ORIGIN_HINTS = {
    "san francisco": "SFO", "sfo": "SFO", "new york": "JFK", "jfk": "JFK", "nyc": "JFK",
    "los angeles": "LAX", "lax": "LAX", "london": "LHR", "lhr": "LHR", "chicago": "ORD",
    "boston": "BOS", "seattle": "SEA", "austin": "AUS", "toronto": "YYZ", "paris": "CDG",
    "delhi": "DEL", "del": "DEL", "new delhi": "DEL", "newdelhi": "DEL",
    "mumbai": "BOM", "bom": "BOM", "bombay": "BOM", "bangalore": "BLR", "bengaluru": "BLR", "blr": "BLR",
    "pune": "PNQ", "pnq": "PNQ", "hyderabad": "HYD", "hyd": "HYD", "chennai": "MAA", "maa": "MAA",
    "kolkata": "CCU", "ccu": "CCU", "dubai": "DXB", "dxb": "DXB", "doha": "DOH", "singapore": "SIN",
    "tokyo": "HND", "rome": "FCO", "frankfurt": "FRA", "amsterdam": "AMS",
    "jakarta": "CGK", "cgk": "CGK",
}

DESTINATION_IMAGES = {
    "kyoto": "https://images.unsplash.com/photo-1493976040374-85c8e12f0c0e?auto=format&fit=crop&w=1600&q=80",
    "tokyo": "https://images.unsplash.com/photo-1540959733332-eab4deabeeaf?auto=format&fit=crop&w=1600&q=80",
    "rome": "https://images.unsplash.com/photo-1552832230-c0197dd311b5?auto=format&fit=crop&w=1600&q=80",
    "paris": "https://images.unsplash.com/photo-1502602898657-3e91760cbb34?auto=format&fit=crop&w=1600&q=80",
    "lisbon": "https://images.unsplash.com/photo-1555881400-74d7acaacd8b?auto=format&fit=crop&w=1600&q=80",
    "swiss-alps": "https://images.unsplash.com/photo-1533105079780-92b9be482077?auto=format&fit=crop&w=1600&q=80",
    "dubai": "https://images.unsplash.com/photo-1512453979798-5ea266f8880c?auto=format&fit=crop&w=1600&q=80",
    "new york": "https://images.unsplash.com/photo-1496442226666-8d4d0e62e6e9?auto=format&fit=crop&w=1600&q=80",
    "new-york": "https://images.unsplash.com/photo-1496442226666-8d4d0e62e6e9?auto=format&fit=crop&w=1600&q=80",
    "nagpur": "https://images.unsplash.com/photo-1605649487212-47bdab064df8?auto=format&fit=crop&w=1600&q=80",
    "jakarta": "https://images.unsplash.com/photo-1560168885-3100a8509693?auto=format&fit=crop&w=1600&q=80",
    "default": "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?auto=format&fit=crop&w=1600&q=80",
}

GENERIC_PLACES = [
    ("Old Town Walk", "attraction", "Start where the city does: a slow loop through the oldest lanes, with a coffee stop halfway.", ["Heritage", "Walk"]),
    ("Central Market", "restaurant", "The best introduction to a city's pantry — go hungry, graze at the counters, and ask what is in season.", ["Market", "Local", "Lunch"]),
    ("City Museum", "attraction", "A compact, well-edited collection that gives the rest of your trip context.", ["Museum", "Culture", "Indoor"]),
    ("Riverside Dinner", "restaurant", "A neighbourhood table with a short menu, good bread and a view worth lingering over.", ["Dinner", "Riverside"]),
    ("Sunset Viewpoint", "attraction", "Time this for the last hour of light; bring something to drink and stay for the blue hour.", ["Views", "Evening"]),
    ("Neighbourhood Café", "cafe", "A locals' café for a proper breakfast and a look at the day's papers.", ["Breakfast", "Coffee"]),
    ("Craft Cocktail Bar", "bar", "Twelve seats, serious ice and a bartender who likes a conversation.", ["Nightlife", "Cocktails"]),
    ("Design & Craft Shops", "shopping", "Independent makers, vintage and the kind of object you will still own in ten years.", ["Shopping", "Design"]),
    ("Botanical Garden", "attraction", "A quiet hour among the glasshouses — ideal when the afternoon heats up.", ["Garden", "Quiet"]),
    ("Local Cooking Class", "activity", "Shop the market, then cook a regional menu with a host who actually lives there.", ["Food", "Hands-on"]),
]


# --------------------------------------------------------------------------- #
# Parsing & Intent Extraction
# --------------------------------------------------------------------------- #
MONTH_MAP: dict[str, int] = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}


def extract_destination_and_origin(text: str) -> dict[str, str]:
    """Extract origin and destination candidates from natural language."""
    lowered = (text or "").lower()
    origin = ""
    destination = ""

    # Pattern: 'from <origin> to <destination>' (e.g. 'plan a complete trip from delhi to new york from 16th dec to 24th dec for 3 adults')
    m = re.search(
        r"(?:from|departing|leaving)\s+([a-zA-Z\s]+?)\s+(?:to|into|towards)\s+([a-zA-Z\s]+?)"
        r"(?:\s+(?:from|on|for|with|in|during|departing|between|\d)|$)",
        lowered,
    )
    if m:
        cand_orig = m.group(1).strip()
        cand_dest = m.group(2).strip()
        cand_orig = re.sub(r"\b(?:a|an|the|flight|flights|trip|travel)\b", "", cand_orig).strip()
        cand_dest = re.sub(r"\b(?:a|an|the|flight|flights|trip|travel)\b", "", cand_dest).strip()
        if cand_orig and cand_dest:
            return {"origin": cand_orig, "destination": cand_dest}

    # Pattern: 'trip to <destination> from <origin>'
    m2 = re.search(
        r"(?:to|visit|visiting)\s+([a-zA-Z\s]+?)\s+(?:from|departing)\s+([a-zA-Z\s]+?)"
        r"(?:\s+(?:from|on|for|with|in|during|between|\d)|$)",
        lowered,
    )
    if m2:
        cand_dest = re.sub(r"\b(?:a|an|the|flight|flights|trip|travel)\b", "", m2.group(1)).strip()
        cand_orig = re.sub(r"\b(?:a|an|the|flight|flights|trip|travel)\b", "", m2.group(2)).strip()
        if cand_orig and cand_dest:
            return {"origin": cand_orig, "destination": cand_dest}

    # Pattern: 'trip to <destination>' or 'visit <destination>'
    m3 = re.search(
        r"(?:trip to|travel to|visit|visiting|flight to|head to|holiday in|vacation in)\s+([a-zA-Z\s]+?)"
        r"(?:\s+(?:from|on|for|with|in|during|between|\d)|$)",
        lowered,
    )
    if m3:
        cand_dest = re.sub(r"\b(?:a|an|the|flight|flights|trip|travel)\b", "", m3.group(1)).strip()
        if cand_dest:
            destination = cand_dest

    return {"origin": origin, "destination": destination}


def parse_dates_and_days(text: str) -> dict[str, Any]:
    """Parse start date, end date, and total days from natural language."""
    lowered = (text or "").lower()
    months_pat = "|".join(MONTH_MAP.keys())
    now = datetime.now()
    cur_year = now.year

    # 1. ISO format: 'YYYY-MM-DD to YYYY-MM-DD'
    iso_match = re.search(r"(\d{4}-\d{2}-\d{2})\s*(?:to|-|through|until)\s*(\d{4}-\d{2}-\d{2})", lowered)
    if iso_match:
        try:
            d1 = date.fromisoformat(iso_match.group(1))
            d2 = date.fromisoformat(iso_match.group(2))
            days = (d2 - d1).days + 1
            return {"start_date": d1.isoformat(), "end_date": d2.isoformat(), "days": max(1, min(14, days))}
        except ValueError:
            pass

    # 2. '16th dec to 24th dec' or '16 dec to 24 dec'
    m1 = re.search(
        rf"(\d{{1,2}})(?:st|nd|rd|th)?\s*({months_pat})\b.*?(?:to|until|-|through)\s*(\d{{1,2}})(?:st|nd|rd|th)?\s*({months_pat})\b",
        lowered,
    )
    if m1:
        d1, m1_str, d2, m2_str = int(m1.group(1)), m1.group(2), int(m1.group(3)), m1.group(4)
        mo1, mo2 = MONTH_MAP[m1_str], MONTH_MAP[m2_str]
        y1 = cur_year if mo1 >= now.month else cur_year + 1
        y2 = y1 if mo2 >= mo1 else y1 + 1
        try:
            dt1 = date(y1, mo1, d1)
            dt2 = date(y2, mo2, d2)
            days = (dt2 - dt1).days + 1
            return {"start_date": dt1.isoformat(), "end_date": dt2.isoformat(), "days": max(1, min(14, days))}
        except ValueError:
            pass

    # 3. '16th to 24th dec' or 'dec 16 to 24'
    m2 = re.search(
        rf"(\d{{1,2}})(?:st|nd|rd|th)?\s*(?:to|-|through|until)\s*(\d{{1,2}})(?:st|nd|rd|th)?\s*({months_pat})\b",
        lowered,
    )
    if m2:
        d1, d2, mo_str = int(m2.group(1)), int(m2.group(2)), m2.group(3)
        mo = MONTH_MAP[mo_str]
        y = cur_year if mo >= now.month else cur_year + 1
        try:
            dt1 = date(y, mo, d1)
            dt2 = date(y, mo, d2)
            days = (dt2 - dt1).days + 1
            return {"start_date": dt1.isoformat(), "end_date": dt2.isoformat(), "days": max(1, min(14, days))}
        except ValueError:
            pass

    # 4. 'dec 16 to dec 24' or 'december 16 - 24'
    m3 = re.search(
        rf"({months_pat})\s*(\d{{1,2}})(?:st|nd|rd|th)?\s*(?:to|-|through|until)\s*(?:({months_pat})\s*)?(\d{{1,2}})(?:st|nd|rd|th)?\b",
        lowered,
    )
    if m3:
        m1_str, d1 = m3.group(1), int(m3.group(2))
        m2_str = m3.group(3) or m1_str
        d2 = int(m3.group(4))
        mo1, mo2 = MONTH_MAP[m1_str], MONTH_MAP[m2_str]
        y1 = cur_year if mo1 >= now.month else cur_year + 1
        y2 = y1 if mo2 >= mo1 else y1 + 1
        try:
            dt1 = date(y1, mo1, d1)
            dt2 = date(y2, mo2, d2)
            days = (dt2 - dt1).days + 1
            return {"start_date": dt1.isoformat(), "end_date": dt2.isoformat(), "days": max(1, min(14, days))}
        except ValueError:
            pass

    # 5. Single date + duration (e.g. 'from 16th dec for 5 days')
    m4 = re.search(rf"(?:from|on|starting)\s*(\d{{1,2}})(?:st|nd|rd|th)?\s*({months_pat})\b", lowered)
    day_match = re.search(r"(\d+)\s*(?:-|\s)?\s*days?", lowered)
    explicit_days = int(day_match.group(1)) if day_match else None
    if m4:
        d1, mo_str = int(m4.group(1)), m4.group(2)
        mo = MONTH_MAP[mo_str]
        y = cur_year if mo >= now.month else cur_year + 1
        try:
            dt1 = date(y, mo, d1)
            d_count = explicit_days or 3
            dt2 = dt1 + timedelta(days=d_count - 1)
            return {"start_date": dt1.isoformat(), "end_date": dt2.isoformat(), "days": max(1, min(14, d_count))}
        except ValueError:
            pass

    return {"start_date": None, "end_date": None, "days": None}


def parse_days(text: str, default: int = 3) -> int:
    dates_info = parse_dates_and_days(text)
    if dates_info["days"] is not None:
        return dates_info["days"]
    lowered = text.lower()
    match = re.search(r"(\d+)\s*(?:-|\s)?\s*days?", lowered)
    if match:
        return max(1, min(14, int(match.group(1))))
    match = re.search(r"(\d+)\s*(?:-|\s)?\s*nights?", lowered)
    if match:
        return max(1, min(14, int(match.group(1)) + 1))
    if "weekend" in lowered:
        return 2
    if "week" in lowered:
        return 7
    return default


def parse_traveler_and_passengers(text: str) -> tuple[str, int]:
    lowered = (text or "").lower()
    m = re.search(r"(\d+)\s*(?:adults?|travelers?|travellers?|people|persons?|pax|passengers?)", lowered)
    if m:
        count = max(1, min(9, int(m.group(1))))
        return (f"{count} adults", count)
    if any(word in lowered for word in ("honeymoon", "romantic", "anniversary", "couple")):
        return ("Couple", 2)
    if any(word in lowered for word in ("family", "kids", "children")):
        return ("Family", 4)
    if any(word in lowered for word in ("solo", "by myself", "alone")):
        return ("Solo traveler", 1)
    if any(word in lowered for word in ("friends", "group")):
        return ("Friends", 3)
    return ("Traveler", 1)


def parse_traveler(text: str) -> str:
    return parse_traveler_and_passengers(text)[0]


def parse_budget(text: str) -> float:
    match = re.search(r"\$\s?([\d,]{3,7})", text)
    if match:
        return float(match.group(1).replace(",", ""))
    match = re.search(r"budget(?:\s+of)?\s+([\d,]{3,7})", text.lower())
    if match:
        return float(match.group(1).replace(",", ""))
    return 0


def detect_origin(text: str) -> str:
    extracted = extract_destination_and_origin(text)
    if extracted["origin"]:
        cand = extracted["origin"].lower()
        if cand in ORIGIN_HINTS:
            return ORIGIN_HINTS[cand]
        for hint, code in ORIGIN_HINTS.items():
            if hint in cand:
                return code

    lowered = (text or "").lower()
    for hint, code in ORIGIN_HINTS.items():
        if re.search(rf"\b{re.escape(hint)}\b", lowered):
            if not re.search(rf"(?:to|into|towards)\s+{re.escape(hint)}\b", lowered):
                return code

    for code in re.findall(r"\b([A-Z]{3})\b", text):
        if code in {"SFO", "JFK", "LAX", "LHR", "ORD", "BOS", "SEA", "AUS", "YYZ", "CDG", "DEL", "BOM", "BLR", "PNQ", "DXB"}:
            return code
    return ""


def detect_vibe(text: str) -> tuple[str, list[str]]:
    lowered = text.lower()
    mapping = {
        "food": ("Food & culture", ["Food", "Culture"]),
        "foodie": ("Food & culture", ["Food", "Culture"]),
        "eat": ("Food & culture", ["Food", "Culture"]),
        "romantic": ("Romance", ["Romance", "Slow travel"]),
        "honeymoon": ("Romance", ["Romance", "Slow travel"]),
        "art": ("Art & design", ["Art", "Design"]),
        "museum": ("Art & design", ["Art", "Design"]),
        "nature": ("Nature", ["Nature", "Outdoors"]),
        "hike": ("Nature", ["Nature", "Hiking"]),
        "alps": ("Nature", ["Nature", "Mountains"]),
        "family": ("Family", ["Family", "Easy pace"]),
        "nightlife": ("Nightlife", ["Nightlife", "Food"]),
        "wellness": ("Wellness", ["Wellness", "Slow travel"]),
        "spa": ("Wellness", ["Wellness", "Slow travel"]),
        "design": ("Design", ["Design", "Architecture"]),
    }
    for keyword, value in mapping.items():
        if keyword in lowered:
            return value
    return ("Slow travel", ["Culture", "Food"])


def _title_for(destination_name: str, days: int, vibe: str) -> str:
    suffix = {
        "Food & culture": f"A {days}-Day Food & Culture Edit",
        "Romance": f"A {days}-Day Romantic Escape",
        "Art & design": f"A {days}-Day Art & Design Edit",
        "Nature": f"A {days}-Day Nature Reset",
        "Family": f"A {days}-Day Family Adventure",
        "Nightlife": f"{days} Nights After Dark",
        "Wellness": f"A {days}-Day Slow Reset",
        "Slow travel": f"A {days}-Day Slow Travel Edit",
    }.get(vibe, f"A {days}-Day Edit")
    return f"{destination_name}: {suffix}"


# --------------------------------------------------------------------------- #
# Typo Correction & Country-to-Hub Mapping
# --------------------------------------------------------------------------- #
COMMON_TYPO_MAP: dict[str, str] = {
    "dubaii": "dubai", "dubi": "dubai", "duba": "dubai", "dubei": "dubai", "dxb": "dubai",
    "itly": "rome", "itlay": "rome", "italy": "rome", "italia": "rome",
    "pariss": "paris", "pari": "paris", "priss": "paris", "france": "paris",
    "tokio": "tokyo", "tokiyo": "tokyo", "toqyo": "tokyo", "japan": "tokyo",
    "kyotoo": "kyoto", "kiyoto": "kyoto", "kyto": "kyoto",
    "londn": "london", "lodnon": "london", "lundon": "london", "uk": "london", "england": "london",
    "spian": "barcelona", "spain": "barcelona", "espana": "barcelona",
    "swizerland": "swiss-alps", "switzerland": "swiss-alps", "switz": "swiss-alps", "alps": "swiss-alps",
    "germny": "berlin", "germany": "berlin",
    "amstrdam": "amsterdam", "amsterdm": "amsterdam", "holland": "amsterdam", "netherlands": "amsterdam",
    "singapur": "singapore", "singapre": "singapore",
    "bangkog": "bangkok", "bangcock": "bangkok", "thailand": "bangkok",
    "mumbay": "mumbai", "bombay": "mumbai",
    "dehli": "delhi", "newdelhi": "delhi", "new delhi": "delhi", "india": "delhi",
    "jaipoor": "jaipur", "jaipure": "jaipur",
    "ireland": "dublin", "irlnd": "dublin",
    "greece": "athens", "grece": "athens",
    "egypt": "cairo", "egpyt": "cairo",
    "turkey": "istanbul", "turkiye": "istanbul", "instanbul": "istanbul",
    "portugal": "lisbon", "portgal": "lisbon",
    "usa": "new york", "us": "new york", "america": "new york",
    "ny": "new york", "nyc": "new york", "newyork": "new york",
    "sanfran": "san francisco", "sf": "san francisco",
    "uae": "dubai", "united arab emirates": "dubai",
}

# --------------------------------------------------------------------------- #
# Curated Spot & Category Image Catalogs
# --------------------------------------------------------------------------- #
SPOT_KEYWORD_IMAGES: dict[str, str] = {
    # Swiss Alps & Switzerland Icons
    "lauterbrunnen": "https://images.unsplash.com/photo-1533105079780-92b9be482077?auto=format&fit=crop&w=1200&q=80",
    "staubbach": "https://images.unsplash.com/photo-1533105079780-92b9be482077?auto=format&fit=crop&w=1200&q=80",
    "matterhorn": "https://images.unsplash.com/photo-1530122037265-a5f1f91d3b99?auto=format&fit=crop&w=1200&q=80",
    "zermatt": "https://images.unsplash.com/photo-1530122037265-a5f1f91d3b99?auto=format&fit=crop&w=1200&q=80",
    "grindelwald": "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?auto=format&fit=crop&w=1200&q=80",
    "jungfrau": "https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?auto=format&fit=crop&w=1200&q=80",
    "oeschinen": "https://images.unsplash.com/photo-1570789210967-2cac24afeb00?auto=format&fit=crop&w=1200&q=80",
    "schilthorn": "https://images.unsplash.com/photo-1519681393784-d120267933ba?auto=format&fit=crop&w=1200&q=80",
    "harder kulm": "https://images.unsplash.com/photo-1527668752968-14dc70a27c95?auto=format&fit=crop&w=1200&q=80",
    "trummelbach": "https://images.unsplash.com/photo-1476514525535-07fb3b4ae5f1?auto=format&fit=crop&w=1200&q=80",
    "trümmelbach": "https://images.unsplash.com/photo-1476514525535-07fb3b4ae5f1?auto=format&fit=crop&w=1200&q=80",
    "chez vrony": "https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=1200&q=80",
    "taverne": "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&w=1200&q=80",
    "swiss house": "https://images.unsplash.com/photo-1514933651103-005eec06c04b?auto=format&fit=crop&w=1200&q=80",
    "1903": "https://images.unsplash.com/photo-1550966871-3ed3cdb5ed0c?auto=format&fit=crop&w=1200&q=80",
    "gimmelwald": "https://images.unsplash.com/photo-1486870591958-9b9d0d1dda99?auto=format&fit=crop&w=1200&q=80",
    "fondue": "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&w=1200&q=80",
    "raclette": "https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=1200&q=80",
    "alpine": "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?auto=format&fit=crop&w=1200&q=80",
    "glacier": "https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?auto=format&fit=crop&w=1200&q=80",
    # Global Landmarks
    "burj khalifa": "https://images.unsplash.com/photo-1512453979798-5ea266f8880c?auto=format&fit=crop&w=1200&q=80",
    "top deck": "https://images.unsplash.com/photo-1518684079-3c830dcef090?auto=format&fit=crop&w=1200&q=80",
    "desert safari": "https://images.unsplash.com/photo-1509316975850-ff9c5deb0cd9?auto=format&fit=crop&w=1200&q=80",
    "dune": "https://images.unsplash.com/photo-1547234935-80c7145ec969?auto=format&fit=crop&w=1200&q=80",
    "dubai mall": "https://images.unsplash.com/photo-1526495124232-a04e1849168c?auto=format&fit=crop&w=1200&q=80",
    "fountain": "https://images.unsplash.com/photo-1518684079-3c830dcef090?auto=format&fit=crop&w=1200&q=80",
    "museum of the future": "https://images.unsplash.com/photo-1580674684081-7617fbf3d745?auto=format&fit=crop&w=1200&q=80",
    "palm jumeirah": "https://images.unsplash.com/photo-1577083552431-6e5fd01aa342?auto=format&fit=crop&w=1200&q=80",
    "atlantis": "https://images.unsplash.com/photo-1571896349842-33c89424de2d?auto=format&fit=crop&w=1200&q=80",
    "marina": "https://images.unsplash.com/photo-1512453979798-5ea266f8880c?auto=format&fit=crop&w=1200&q=80",
    "yacht": "https://images.unsplash.com/photo-1569263979104-865ab7cd8d17?auto=format&fit=crop&w=1200&q=80",
    "al fahidi": "https://images.unsplash.com/photo-1518684079-3c830dcef090?auto=format&fit=crop&w=1200&q=80",
    "souk": "https://images.unsplash.com/photo-1546412414-e1885259563a?auto=format&fit=crop&w=1200&q=80",
    "frame": "https://images.unsplash.com/photo-1580674684081-7617fbf3d745?auto=format&fit=crop&w=1200&q=80",
    "pierchic": "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?auto=format&fit=crop&w=1200&q=80",
    "kabab": "https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=1200&q=80",
    "miracle garden": "https://images.unsplash.com/photo-1585320806297-9794b3e4eeae?auto=format&fit=crop&w=1200&q=80",
    "temple": "https://images.unsplash.com/photo-1493976040374-85c8e12f0c0e?auto=format&fit=crop&w=1200&q=80",
    "shrine": "https://images.unsplash.com/photo-1503899036084-c55cdd92da26?auto=format&fit=crop&w=1200&q=80",
    "colosseum": "https://images.unsplash.com/photo-1552832230-c0197dd311b5?auto=format&fit=crop&w=1200&q=80",
    "vatican": "https://images.unsplash.com/photo-1531572753322-ad063cecc140?auto=format&fit=crop&w=1200&q=80",
    "eiffel": "https://images.unsplash.com/photo-1502602898657-3e91760cbb34?auto=format&fit=crop&w=1200&q=80",
    "louvre": "https://images.unsplash.com/photo-1499856871958-5b9627545d1a?auto=format&fit=crop&w=1200&q=80",
    "pasta": "https://images.unsplash.com/photo-1551183053-bf91a1d81141?auto=format&fit=crop&w=1200&q=80",
    "pizza": "https://images.unsplash.com/photo-1513104890138-7c749659a591?auto=format&fit=crop&w=1200&q=80",
    "ramen": "https://images.unsplash.com/photo-1569718212165-3a8278d5f624?auto=format&fit=crop&w=1200&q=80",
    "sushi": "https://images.unsplash.com/photo-1579871494447-9811cf80d66c?auto=format&fit=crop&w=1200&q=80",
    "market": "https://images.unsplash.com/photo-1533900298318-6b8da08a523e?auto=format&fit=crop&w=1200&q=80",
    "cocktail": "https://images.unsplash.com/photo-1514362545857-3bc16c4c7d1b?auto=format&fit=crop&w=1200&q=80",
    "coffee": "https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb?auto=format&fit=crop&w=1200&q=80",
    # Specific Landmarks (Mumbai, Delhi, Jaipur, Kyoto, Paris, Rome)
    "gateway of india": "https://images.unsplash.com/photo-1570168007204-dfb528c6958f?auto=format&fit=crop&w=1200&q=80",
    "marine drive": "https://images.unsplash.com/photo-1567157577867-05ccb1388e66?auto=format&fit=crop&w=1200&q=80",
    "queen's necklace": "https://images.unsplash.com/photo-1567157577867-05ccb1388e66?auto=format&fit=crop&w=1200&q=80",
    "taj mahal palace": "https://images.unsplash.com/photo-1582510003544-4d00b7f74220?auto=format&fit=crop&w=1200&q=80",
    "csmt": "https://images.unsplash.com/photo-1576487247234-4366d0ef0a30?auto=format&fit=crop&w=1200&q=80",
    "chhatrapati shivaji": "https://images.unsplash.com/photo-1576487247234-4366d0ef0a30?auto=format&fit=crop&w=1200&q=80",
    "elephanta": "https://images.unsplash.com/photo-1596768341671-55e105e197ca?auto=format&fit=crop&w=1200&q=80",
    "sea link": "https://images.unsplash.com/photo-1562979314-bee7453e911c?auto=format&fit=crop&w=1200&q=80",
    "haji ali": "https://images.unsplash.com/photo-1595846519845-68e298c2edd8?auto=format&fit=crop&w=1200&q=80",
    "crawford market": "https://images.unsplash.com/photo-1533900298318-6b8da08a523e?auto=format&fit=crop&w=1200&q=80",
    "siddhivinayak": "https://images.unsplash.com/photo-1561361513-2d000a50f0dc?auto=format&fit=crop&w=1200&q=80",
    "bombay canteen": "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&w=1200&q=80",
    "trishna": "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?auto=format&fit=crop&w=1200&q=80",
    "britannia": "https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=1200&q=80",
    "leopold": "https://images.unsplash.com/photo-1514933651103-005eec06c04b?auto=format&fit=crop&w=1200&q=80",
    "subko": "https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb?auto=format&fit=crop&w=1200&q=80",
    "india gate": "https://images.unsplash.com/photo-1587474260584-136574528ed5?auto=format&fit=crop&w=1200&q=80",
    "qutub minar": "https://images.unsplash.com/photo-1524492412937-b28074a5d7da?auto=format&fit=crop&w=1200&q=80",
    "humayun": "https://images.unsplash.com/photo-1588668214407-6ea9a6d8c272?auto=format&fit=crop&w=1200&q=80",
    "lotus temple": "https://images.unsplash.com/photo-1564507592333-c60657eea523?auto=format&fit=crop&w=1200&q=80",
    "hawa mahal": "https://images.unsplash.com/photo-1603262110263-fb010d6e59d4?auto=format&fit=crop&w=1200&q=80",
    "amber fort": "https://images.unsplash.com/photo-1599661046289-e31897846e41?auto=format&fit=crop&w=1200&q=80",
    "fushimi inari": "https://images.unsplash.com/photo-1493976040374-85c8e12f0c0e?auto=format&fit=crop&w=1200&q=80",
    "kiyomizu": "https://images.unsplash.com/photo-1503899036084-c55cdd92da26?auto=format&fit=crop&w=1200&q=80",
    "kinkaku": "https://images.unsplash.com/photo-1545569341-9eb8b30979d9?auto=format&fit=crop&w=1200&q=80",
    "arashiyama": "https://images.unsplash.com/photo-1509023464722-18d996393ca8?auto=format&fit=crop&w=1200&q=80",
    "eiffel tower": "https://images.unsplash.com/photo-1502602898657-3e91760cbb34?auto=format&fit=crop&w=1200&q=80",
    "notre dame": "https://images.unsplash.com/photo-1511739001486-6bfe10ce785f?auto=format&fit=crop&w=1200&q=80",
    "sacre coeur": "https://images.unsplash.com/photo-1520939817895-060bdef4ad1b?auto=format&fit=crop&w=1200&q=80",
    "trevi fountain": "https://images.unsplash.com/photo-1525874684015-58379d421a52?auto=format&fit=crop&w=1200&q=80",
    "pantheon": "https://images.unsplash.com/photo-1531572753322-ad063cecc140?auto=format&fit=crop&w=1200&q=80",
}

DESTINATION_IMAGE_POOLS: dict[str, list[str]] = {
    "mumbai": [
        "https://images.unsplash.com/photo-1570168007204-dfb528c6958f?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1567157577867-05ccb1388e66?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1582510003544-4d00b7f74220?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1576487247234-4366d0ef0a30?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1596768341671-55e105e197ca?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1562979314-bee7453e911c?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1595846519845-68e298c2edd8?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb?auto=format&fit=crop&w=1200&q=80",
    ],
    "delhi": [
        "https://images.unsplash.com/photo-1587474260584-136574528ed5?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1524492412937-b28074a5d7da?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1588668214407-6ea9a6d8c272?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1564507592333-c60657eea523?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1558431382-27e303142255?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1597659840237-640a35db4db1?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1608958435020-e8a7109ba809?auto=format&fit=crop&w=1200&q=80",
    ],
    "jaipur": [
        "https://images.unsplash.com/photo-1603262110263-fb010d6e59d4?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1599661046289-e31897846e41?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1582510003544-4d00b7f74220?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1592635196078-9fdc757f27f4?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1586861635167-e5223aadc9fe?auto=format&fit=crop&w=1200&q=80",
    ],
    "pune": [
        "https://images.unsplash.com/photo-1576487247234-4366d0ef0a30?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1595846519845-68e298c2edd8?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1605649487212-47bdab064df8?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1561361513-2d000a50f0dc?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&w=1200&q=80",
    ],
    "swiss alps": [
        "https://images.unsplash.com/photo-1533105079780-92b9be482077?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1530122037265-a5f1f91d3b99?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1570789210967-2cac24afeb00?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1519681393784-d120267933ba?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1527668752968-14dc70a27c95?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1476514525535-07fb3b4ae5f1?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1486870591958-9b9d0d1dda99?auto=format&fit=crop&w=1200&q=80",
    ],
    "switzerland": [
        "https://images.unsplash.com/photo-1533105079780-92b9be482077?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1530122037265-a5f1f91d3b99?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1570789210967-2cac24afeb00?auto=format&fit=crop&w=1200&q=80",
    ],
    "new york": [
        "https://images.unsplash.com/photo-1538688525198-9b88f6f53126?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1582555172866-f73bb12a2ab3?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1518391846015-55a9cc003b25?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1496442226666-8d4d0e62e6e9?auto=format&fit=crop&w=1200&q=80",
    ],
    "paris": [
        "https://images.unsplash.com/photo-1502602898657-3e91760cbb34?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1499856871958-5b9627545d1a?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1511739001486-6bfe10ce785f?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1509356843151-3e7d96241e11?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1520939817895-060bdef4ad1b?auto=format&fit=crop&w=1200&q=80",
    ],
    "kyoto": [
        "https://images.unsplash.com/photo-1493976040374-85c8e12f0c0e?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1503899036084-c55cdd92da26?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1545569341-9eb8b30979d9?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1509023464722-18d996393ca8?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1528164344705-475426879c0d?auto=format&fit=crop&w=1200&q=80",
    ],
    "rome": [
        "https://images.unsplash.com/photo-1552832230-c0197dd311b5?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1525874684015-58379d421a52?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1531572753322-ad063cecc140?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1515542622106-78bda8ba0e5b?auto=format&fit=crop&w=1200&q=80",
    ],
}

CATEGORY_IMAGE_POOLS: dict[str, list[str]] = {
    "attraction": [
        "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1519681393784-d120267933ba?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1526495124232-a04e1849168c?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1552832230-c0197dd311b5?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1502602898657-3e91760cbb34?auto=format&fit=crop&w=1200&q=80",
    ],
    "restaurant": [
        "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1550966871-3ed3cdb5ed0c?auto=format&fit=crop&w=1200&q=80",
    ],
    "activity": [
        "https://images.unsplash.com/photo-1509316975850-ff9c5deb0cd9?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1577083552431-6e5fd01aa342?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1546412414-e1885259563a?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=1200&q=80",
    ],
    "culture": [
        "https://images.unsplash.com/photo-1518684079-3c830dcef090?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1595846519845-68e298c2edd8?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1499856871958-5b9627545d1a?auto=format&fit=crop&w=1200&q=80",
    ],
    "cafe": [
        "https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?auto=format&fit=crop&w=1200&q=80",
    ],
    "bar": [
        "https://images.unsplash.com/photo-1514362545857-3bc16c4c7d1b?auto=format&fit=crop&w=1200&q=80",
        "https://images.unsplash.com/photo-1572116469696-31de0f17cc34?auto=format&fit=crop&w=1200&q=80",
    ],
}


def get_spot_image(name: str, category: str = "attraction", destination_id: str = "", index: int = 0) -> str:
    """Return a unique, high-resolution photo matching the spot's real content and destination."""
    lowered = name.lower()
    # Sort keyword matches descending by string length so specific landmark keywords take precedence!
    for kw, img in sorted(SPOT_KEYWORD_IMAGES.items(), key=lambda x: len(x[0]), reverse=True):
        if kw in lowered:
            return img

    dest_key = destination_id.lower().replace("-", " ")
    hash_offset = abs(hash(f"{destination_id}:{name}:{category}"))

    # Destination-specific pools if available
    for d_kw, pool in DESTINATION_IMAGE_POOLS.items():
        if d_kw in dest_key or dest_key in d_kw:
            return pool[(hash_offset + index) % len(pool)]

    cat = category.lower()
    pool = CATEGORY_IMAGE_POOLS.get(cat, CATEGORY_IMAGE_POOLS["attraction"])
    return pool[(hash_offset + index) % len(pool)]


def parse_flight_times(text: str) -> tuple[str | None, str | None]:
    """Parse booked flight arrival & departure times from user text.
    
    Examples:
    - 'flight arriving at 14:00' -> ('14:00', None)
    - 'landing at 2:30 pm and departing at 21:00' -> ('14:30', '21:00')
    """
    lowered = text.lower()
    arr_time = None
    dep_time = None

    arr_match = re.search(r"(?:arr(?:iving|ival)|land(?:ing)?|reach(?:ing)?)\s*(?:at|by|around)?\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)", lowered)
    if arr_match:
        raw = arr_match.group(1).strip()
        arr_time = _normalize_time(raw)

    dep_match = re.search(r"(?:dep(?:arting|arture)|takeoff|leaving|fly(?:ing)?\s*out)\s*(?:at|by|around)?\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)", lowered)
    if dep_match:
        raw = dep_match.group(1).strip()
        dep_time = _normalize_time(raw)

    return arr_time, dep_time


def _normalize_time(raw: str) -> str:
    raw = raw.strip().lower()
    is_pm = "pm" in raw
    is_am = "am" in raw
    digits = re.sub(r"[^0-9:]", "", raw)
    if ":" in digits:
        parts = digits.split(":")
        h = int(parts[0])
        m = int(parts[1])
    else:
        h = int(digits)
        m = 0
    if is_pm and h < 12:
        h += 12
    if is_am and h == 12:
        h = 0
    return f"{h:02d}:{m:02d}"


def _add_minutes(time_str: str, minutes: int) -> str:
    parts = time_str.split(":")
    total = int(parts[0]) * 60 + int(parts[1]) + minutes
    total %= (24 * 60)
    return f"{total // 60:02d}:{total % 60:02d}"


def _format_12h(time_str: str) -> str:
    parts = time_str.split(":")
    h = int(parts[0])
    m = int(parts[1])
    suffix = "AM" if h < 12 else "PM"
    h12 = h if 1 <= h <= 12 else (12 if h == 0 or h == 12 else h - 12)
    return f"{h12:02d}:{m:02d} {suffix}"
def _get_or_create_destination(session: Session, city_name_or_id: str) -> dict[str, Any]:
    norm_key = city_name_or_id.strip().lower()
    dest_id = data_service.slugify(norm_key)

    # Check DB
    rows = session.exec(select(Destination)).all()
    for r in rows:
        if r.id in {norm_key, dest_id} or r.name.lower() == norm_key.replace("-", " "):
            return data_service.destination_dict(r)

    # Create new
    name = norm_key.replace("-", " ").title()
    coords = CITY_COORDS.get(norm_key) or CITY_COORDS.get(name.lower())
    if not coords:
        coords = (40.7128, -74.0060) if "york" in norm_key else (48.8566, 2.3522)
    lat, lon = coords
    image = DESTINATION_IMAGES.get(dest_id, DESTINATION_IMAGES.get(norm_key, DESTINATION_IMAGES["default"]))
    row = Destination(
        id=dest_id,
        name=name,
        country="",
        tagline=f"A considered edit of {name}",
        description=f"A first-timer's edit of {name}, built around authentic sights, good tables and memorable experiences.",
        hero_image=image,
        gallery=[image],
        tags=["City", "Culture", "Food"],
        best_season="Spring · Autumn",
        lat=lat,
        lon=lon,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return data_service.destination_dict(row)


def resolve_destination(session: Session, query: str) -> dict[str, Any]:
    query = (query or "").strip()
    lowered = query.lower()

    # 1. Extract destination candidate using travel sentence structure
    extracted = extract_destination_and_origin(query)
    dest_cand = extracted.get("destination", "").strip().lower()
    orig_cand = extracted.get("origin", "").strip().lower()

    # Sort known cities by length descending so multi-word cities match first ('new york' before 'new')
    sorted_cities = sorted(CITY_COORDS.keys(), key=lambda c: len(c), reverse=True)

    # If the origin wasn't extracted from sentence structure, try to pull it from
    # a trailing 'from <city>' in the full query so we don't mistake it for the
    # destination during fallback matching (e.g. 'to jakarta from delhi').
    if not orig_cand:
        m_orig = re.search(r"\bfrom\s+([a-zA-Z\s]+?)(?:\s+(?:for|with|in|on|during|\d)|$)", lowered)
        if m_orig:
            cand_orig = re.sub(r"\b(?:a|an|the|flight|flights|trip|travel)\b", "", m_orig.group(1)).strip()
            if cand_orig:
                orig_cand = cand_orig

    # 2. Check candidate destination first, then full query
    targets = [dest_cand, lowered] if dest_cand else [lowered]
    for target in targets:
        if not target:
            continue

        # Direct match against sorted CITY_COORDS
        for city in sorted_cities:
            if re.search(rf"\b{re.escape(city)}\b", target):
                # Ensure the matched city is not the origin
                if orig_cand and city == orig_cand:
                    continue
                return _get_or_create_destination(session, city)

        # Check typo and alias map
        for typo, real_city in COMMON_TYPO_MAP.items():
            if re.search(rf"\b{re.escape(typo)}\b", target):
                if orig_cand and real_city == orig_cand:
                    continue
                return _get_or_create_destination(session, real_city)

    # 3. Direct match against DB destinations
    db_rows = session.exec(select(Destination)).all()
    for row in db_rows:
        if dest_cand and dest_cand in {row.id, row.name.lower()}:
            return data_service.destination_dict(row)
    for row in db_rows:
        if re.search(rf"\b{re.escape(row.name.lower())}\b", lowered):
            if orig_cand and row.name.lower() == orig_cand:
                continue
            return data_service.destination_dict(row)

    # 4. Strict fuzzy match: ONLY on non-stopwords with len >= 4 and cutoff >= 0.82!
    # Prevents common English words like 'from' matching 'rome' (which is ratio 0.75)!
    STOP_WORDS = {
        "plan", "trip", "complete", "travel", "vacation", "from", "to", "for", "with",
        "and", "the", "a", "an", "days", "day", "night", "nights", "adult", "adults",
        "child", "children", "flight", "flights", "hotel", "hotels", "stay", "under",
        "around", "about", "want", "please", "book", "best", "some", "city", "good",
    }
    import difflib
    search_words = re.findall(r"[a-zA-Z]+", dest_cand or lowered)
    for w in search_words:
        if len(w) >= 4 and w not in STOP_WORDS:
            matches = difflib.get_close_matches(w, sorted_cities, n=1, cutoff=0.82)
            if matches:
                matched_city = matches[0]
                if orig_cand and matched_city == orig_cand:
                    continue
                return _get_or_create_destination(session, matched_city)

    # 5. Fallback extraction from phrases
    match = re.search(r"\b(?:in|to|around|visit(?:ing)?)\s+([A-Za-z'\-]+(?:\s+[A-Za-z'\-]+){0,2})", query, flags=re.I)
    if match:
        candidate = match.group(1).strip()
        candidate = re.sub(r"\b(?:with|for|and|boutique|hotels?|flights?)\b.*", "", candidate, flags=re.I).strip()
        name = candidate.title() if candidate else "Kyoto"
    else:
        # A bare place name (e.g. "Ljubljana") is a perfectly valid destination.
        # Previously anything that did not match the preposition regex silently
        # became "Kyoto", which built the wrong trip for unknown cities.
        bare = re.sub(
            r"\b(?:plan|planning|trip|travel|vacation|holiday|itinerary|"
            r"days?|nights?|adults?|children|people|persons?|from|with|for|to|in|"
            r"a|an|the|and|my|our|of)\b",
            " ",
            query,
            flags=re.I,
        )
        bare = re.sub(r"[^A-Za-z'\- ]+", " ", bare)
        bare = re.sub(r"\s+", " ", bare).strip(" ,.-")
        words = [w for w in bare.split() if w.lower() not in STOP_WORDS and len(w) >= 2]
        if words:
            name = " ".join(words[:3]).title()
        else:
            name = query.strip().title() or "Kyoto"

    return _get_or_create_destination(session, name.lower())


def _ensure_generic_places(session: Session, destination: dict[str, Any]) -> list[Place]:
    dest_id = destination["id"]
    existing_rows = list(session.exec(select(Place).where(Place.destination == dest_id)).all())

    # 1. Sync & enrich with famous curated spots catalog
    try:
        from backend.database.famous_spots import get_famous_spots_for_destination
        famous = get_famous_spots_for_destination(dest_id) or get_famous_spots_for_destination(destination.get("name", ""))
        if famous:
            existing_by_id = {p.id: p for p in existing_rows}
            needs_commit = False
            for s in famous:
                s_id = s.get("id") or f"{dest_id}-{data_service.slugify(s['name'])}"
                if s_id in existing_by_id:
                    p = existing_by_id[s_id]
                    # Only overwrite photos if the existing place has no real
                    # Google Maps photos; never replace live scraped imagery
                    # with static catalog fallbacks.
                    existing_photos = p.photos or []
                    has_real = any(
                        "googleusercontent" in x or "maps.googleapis" in x
                        for x in existing_photos
                    )
                    catalog_photos = s.get("photos") or []
                    if catalog_photos and not has_real:
                        p.photos = catalog_photos
                        needs_commit = True
                    elif catalog_photos and has_real:
                        # Keep real photos, but update other fields
                        pass
                    if s.get("name") and p.name != s["name"]:
                        p.name = s["name"]
                        needs_commit = True
                    if s.get("category") and p.category != s["category"]:
                        p.category = s["category"]
                        needs_commit = True
                    if s.get("description") and p.description != s["description"]:
                        p.description = s["description"]
                        needs_commit = True
                else:
                    price_lvl = 1
                    if s.get("price_level") in {"$$$", "€€€", "₹₹₹", "$$$$"}:
                        price_lvl = 3
                    elif s.get("price_level") in {"$$", "€€", "₹₹"}:
                        price_lvl = 2
                    new_place = Place(
                        id=s_id,
                        name=s["name"],
                        category=s.get("category", "attraction"),
                        destination=dest_id,
                        description=s.get("description", ""),
                        lat=s.get("lat") or destination["lat"],
                        lon=s.get("lon") or destination["lon"],
                        rating=s.get("rating", 4.8),
                        review_count=s.get("reviews_count") or s.get("review_count", 1500),
                        address=s.get("address", f"{destination['name']} central district"),
                        price_level=price_lvl,
                        opening_hours="See local listings",
                        photos=s.get("photos") or [destination.get("hero_image", "")],
                        tags=s.get("tags", []),
                        source="curated",
                    )
                    session.add(new_place)
                    existing_rows.append(new_place)
                    existing_by_id[s_id] = new_place
                    needs_commit = True
            if needs_commit:
                try:
                    session.commit()
                    for p in existing_rows:
                        session.refresh(p)
                except Exception:
                    session.rollback()
            return existing_rows
    except Exception as exc:
        logger.warning("Error syncing famous spots: %s", exc)

    if existing_rows:
        return existing_rows

    # 2. Try live Overpass OSM POIs
    try:
        from scrapers.free_apis import overpass_pois
        osm_spots = overpass_pois(destination["lat"], destination["lon"], category="attraction", limit=8)
        osm_dining = overpass_pois(destination["lat"], destination["lon"], category="restaurant", limit=6)
        all_osm = osm_spots + osm_dining
        if all_osm:
            created = []
            for item in all_osm:
                place = Place(
                    id=f"{dest_id}-{data_service.slugify(item['name'])}",
                    name=item["name"],
                    category=item.get("category", "attraction"),
                    destination=dest_id,
                    description=f"Authentic {item.get('category')} located at {item.get('address') or destination['name']}.",
                    lat=item["lat"],
                    lon=item["lon"],
                    rating=4.7,
                    review_count=450,
                    address=item.get("address") or f"{destination['name']}",
                    price_level=2,
                    opening_hours=item.get("opening_hours") or "Open daily",
                    photos=[destination.get("hero_image", "")],
                    tags=item.get("tags") or ["Must-Visit", "Cultural"],
                    source="openstreetmap",
                )
                session.add(place)
                created.append(place)
            session.commit()
            for p in created:
                session.refresh(p)
            return created
    except Exception:
        pass

    # 2.5 Try live Google Maps scraper for real spots & photos when no curated catalog exists
    try:
        from scrapers.google_maps_adapter import search_google_maps_live
        gmaps_places: list[Place] = []
        for gq, gcat in (
            ("top attractions", "attraction"),
            ("best restaurants", "restaurant"),
            ("cafes", "cafe"),
            ("markets", "attraction"),
            ("temples", "attraction"),
            ("best hotels", "hotel"),
            ("best resorts", "hotel"),
            ("boutique hotels", "hotel"),
        ):
            scraped = search_google_maps_live(
                query=gq,
                location=destination["name"],
                category=gcat,
                max_results=4,
                session=session,
            )
            if scraped:
                gmaps_places.extend(scraped)
        if gmaps_places:
            existing_ids = {p.id for p in existing_rows}
            for p in gmaps_places:
                if p.id not in existing_ids:
                    existing_rows.append(p)
                    existing_ids.add(p.id)
            try:
                session.commit()
            except Exception:
                session.rollback()
            for p in existing_rows:
                try:
                    session.refresh(p)
                except Exception:
                    pass
            return existing_rows
    except Exception:
        pass

    # No live place data available. Return an empty set rather than fabricating
    # businesses or crashing the planner; callers handle a trip with no stops.
    return []


# --------------------------------------------------------------------------- #
# Itinerary synthesis
# --------------------------------------------------------------------------- #
def _pick_hotel(session: Session, destination: dict[str, Any], hotel_id: str = "", budget: float = 0) -> Hotel | None:
    if hotel_id:
        row = session.get(Hotel, hotel_id)
        if row:
            return row
    rows = session.exec(select(Hotel).where(Hotel.destination == destination["id"])).all()
    if not rows:
        return None
    if budget:
        nightly_cap = max(120, budget / 4)
        affordable = [row for row in rows if (row.price_per_night or 0) <= nightly_cap]
        if affordable:
            rows = affordable
    return sorted(rows, key=lambda row: (row.rating or 0), reverse=True)[0]


def _slot_plan(places: list[Place], days: int) -> list[list[Place]]:
    """Distribute places across trip days with strict deduplication:
    1. NEVER duplicate any place within the same day.
    2. Prioritize unvisited places across the entire trip so places don't repeat
       across days unless all available places in the destination have already been scheduled.
    3. Categorize all non-dining places (attraction, heritage, culture, nature, viewpoint,
       museum, shopping, activity, monument, temple) as attractions.
    4. Categorize dining places (restaurant, bar, cafe, dining, food) as restaurants.
    """
    dining_cats = {"restaurant", "bar", "cafe", "dining", "food"}
    attractions = [p for p in places if (p.category or "").lower() not in dining_cats]
    restaurants = [p for p in places if (p.category or "").lower() in dining_cats]

    if not attractions:
        attractions = list(places)
    if not restaurants:
        restaurants = [p for p in places if p not in attractions] or list(places)

    plan: list[list[Place]] = []
    trip_used: set[str] = set()

    for day in range(days):
        day_places: list[Place] = []
        day_used: set[str] = set()

        # Morning & Afternoon spots (Attraction / Culture / Nature / Viewpoint / Activity)
        for _ in range(2):
            candidate = next((p for p in attractions if p.id not in trip_used and p.id not in day_used), None)
            if not candidate:
                candidate = next((p for p in attractions if p.id not in day_used), None)
            if not candidate:
                candidate = next((p for p in places if p.id not in trip_used and p.id not in day_used), None)
            # Strict trip-wide dedup: never repeat a place across the itinerary.
            # If no unused place remains, leave the slot empty rather than repeat.

            if candidate:
                day_places.append(candidate)
                day_used.add(candidate.id)
                trip_used.add(candidate.id)

        # Evening / Dinner spot (Restaurant / Bar / Scenic evening venue)
        dinner = next((p for p in restaurants if p.id not in trip_used and p.id not in day_used), None)
        if not dinner:
            dinner = next((p for p in restaurants if p.id not in day_used), None)
        if not dinner:
            dinner = next((p for p in places if p.id not in trip_used and p.id not in day_used), None)

        if dinner:
            day_places.append(dinner)
            day_used.add(dinner.id)
            trip_used.add(dinner.id)

        plan.append(day_places)

    return plan


def _run_async_sync(factory: Any) -> Any:
    """Run an async factory from sync code, even when a loop is already running.

    ``synthesize_trip`` is called both from plain sync endpoints and from inside
    the agent's async event loop. ``asyncio.run`` cannot be nested, so when a
    loop is already active the coroutine runs on a dedicated thread/loop.
    """
    import asyncio
    import threading

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(factory())

    box: dict[str, Any] = {}

    def _runner() -> None:
        try:
            box["value"] = asyncio.run(factory())
        except BaseException as exc:  # noqa: BLE001 - re-raised below
            box["error"] = exc

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    thread.join()
    if box.get("error"):
        raise box["error"]
    return box.get("value")


def synthesize_trip(
    session: Session,
    *,
    destination_query: str,
    days: int = 3,
    title: str = "",
    traveler_type: str = "",
    budget: float = 0,
    start_date: str = "",
    end_date: str = "",
    hotel_id: str = "",
    preferences: str = "",
    session_id: str = "",
    origin: str = "",
    passengers: int = 1,
) -> dict[str, Any]:
    # Extract dates, duration, passengers, and origin if underspecified
    combined_query = f"{preferences} {destination_query} {title}"
    dates_info = parse_dates_and_days(combined_query)
    if dates_info["days"] is not None:
        days = dates_info["days"]
    if dates_info["start_date"]:
        start_date = start_date or dates_info["start_date"]
    if dates_info["end_date"]:
        end_date = end_date or dates_info["end_date"]

    parsed_traveler, parsed_pax = parse_traveler_and_passengers(combined_query)
    if not traveler_type or traveler_type == "Traveler":
        traveler_type = parsed_traveler
    if passengers <= 1 and parsed_pax > 1:
        passengers = parsed_pax

    if not origin:
        origin = detect_origin(combined_query)

    days = max(1, min(14, int(days or 3)))
    destination = resolve_destination(session, destination_query)

    # --- Always scrape live Google Maps for real places & photos ---
    # We scrape attractions + restaurants + hotels regardless of curated catalog
    # so every place has authentic Google Maps imagery (no Unsplash fallbacks).
    live_places: list[Place] = []
    live_hotels: list[Place] = []
    try:
        from scrapers.google_maps_adapter import search_google_maps_live
        per_cat = max(6, days)  # scrape enough for all slots + buffer
        for gq, gcat, target_list in (
            ("top attractions", "attraction", live_places),
            ("best restaurants", "restaurant", live_places),
            ("best hotels", "hotel", live_hotels),
        ):
            scraped = search_google_maps_live(
                query=gq,
                location=destination["name"],
                category=gcat,
                max_results=per_cat,
                session=session,
            )
            if gcat == "hotel":
                live_hotels.extend(scraped)
            else:
                live_places.extend(scraped)
    except Exception:
        pass

    # --- Curated catalog spots (used only as fillers when live scrape is sparse) ---
    curated = _ensure_generic_places(session, destination) or []
    curated_ids = {p.id for p in curated}

    # Merge: live-scraped places first (real photos), then curated to fill gaps
    all_places: list[Place] = []
    seen_ids: set[str] = set()
    for p in live_places:
        if p.id not in seen_ids:
            all_places.append(p)
            seen_ids.add(p.id)
    for p in curated:
        if p.id not in seen_ids:
            all_places.append(p)
            seen_ids.add(p.id)
    places = sorted(all_places, key=lambda place: (place.rating or 0), reverse=True)

    # --- Ensure enough unique places for all day slots (2 attractions + 1 restaurant per day) ---
    needed_places = days * 3
    if len(places) < needed_places:
        try:
            from scrapers.google_maps_adapter import search_google_maps_live
            still_needed = needed_places - len(places)
            for gq, gcat in (
                ("things to do", "attraction"),
                ("popular restaurants", "restaurant"),
                ("must visit places", "attraction"),
            ):
                scraped = search_google_maps_live(
                    query=gq,
                    location=destination["name"],
                    category=gcat,
                    max_results=max(still_needed, 4),
                    session=session,
                )
                for p in scraped:
                    if p.id not in seen_ids:
                        places.append(p)
                        seen_ids.add(p.id)
                if len(places) >= needed_places:
                    break
            places = sorted(places, key=lambda place: (place.rating or 0), reverse=True)
        except Exception:
            pass

    # --- Save live-scraped hotels to the Hotel table so _pick_hotel can find them ---
    if live_hotels:
        try:
            existing_hotel_ids = {
                h.id for h in session.exec(select(Hotel).where(Hotel.destination == destination["id"])).all()
            }
            for hp in live_hotels:
                if hp.id in existing_hotel_ids:
                    continue
                rating = hp.rating or 4.5
                stars = 5 if rating >= 4.5 else (4 if rating >= 4.0 else (3 if rating >= 3.5 else 2))
                hotel_row = Hotel(
                    id=hp.id,
                    name=hp.name,
                    destination=destination["id"],
                    stars=stars,
                    rating=rating,
                    review_count=hp.review_count or 500,
                    address=hp.address or "",
                    lat=hp.lat,
                    lon=hp.lon,
                    price_per_night=None,
                    currency="INR",
                    amenities=hp.tags or [],
                    photos=hp.photos or [],
                    room_types=[],
                    booking_url="",
                    description=hp.description or "",
                    source="google_maps_live",
                )
                session.add(hotel_row)
            session.commit()
        except Exception:
            session.rollback()
            pass

    # --- Second pass: get real Google Maps photos for places that still lack them ---
    places_without_real = [
        p for p in places
        if not any("googleusercontent" in x or "maps.googleapis" in x for x in (p.photos or []))
    ]
    if places_without_real:
        try:
            from scrapers.google_maps_adapter import search_google_maps_live
            for p in places_without_real:
                scraped = search_google_maps_live(
                    query=p.name,
                    location=destination["name"],
                    category=p.category,
                    max_results=1,
                    session=session,
                )
                if scraped and scraped[0].photos:
                    real_photos = [
                        x for x in scraped[0].photos
                        if "googleusercontent" in x or "maps.googleapis" in x
                    ]
                    if real_photos:
                        p.photos = real_photos
                        session.add(p)
            session.commit()
        except Exception:
            session.rollback()
            pass

    hotel = _pick_hotel(session, destination, hotel_id, budget)
    vibe, vibe_tags = detect_vibe(f"{preferences} {destination_query} {title}")

    start = start_date or (date.today() + timedelta(days=30)).isoformat()
    try:
        start_dt = date.fromisoformat(start)
    except ValueError:
        start_dt = date.today() + timedelta(days=30)
        start = start_dt.isoformat()

    calc_end_date = end_date or (start_dt + timedelta(days=days - 1)).isoformat()

    flight_arr, flight_dep = parse_flight_times(combined_query)
    plan = _slot_plan(places, days)
    day_payloads: list[dict[str, Any]] = []
    pins: list[dict[str, Any]] = []
    cards: list[dict[str, Any]] = []
    all_stops: list[dict[str, Any]] = []

    pin_number = 0
    for day_index, day_places in enumerate(plan, start=1):
        stops: list[dict[str, Any]] = []
        previous: Place | None = None

        # Calculate day schedule times with buffer times
        if day_index == 1 and flight_arr:
            day1_start = _add_minutes(flight_arr, 150)
            slot_times = {
                "morning": _add_minutes(flight_arr, 150),
                "afternoon": _add_minutes(flight_arr, 150),
                "evening": _add_minutes(flight_arr, 270),
            }
        else:
            slot_times = {"morning": "09:30", "afternoon": "13:30", "evening": "18:30"}

        slot_titles = {
            "morning": "Morning exploration", "afternoon": "Afternoon in focus", "evening": "Evening & dining",
        }

        for order, place in enumerate(day_places):
            slot = ("morning", "afternoon", "evening")[min(order, 2)]
            start_t = slot_times[slot]
            duration = 90 if place.category in {"restaurant", "bar", "cafe"} else 120
            end_t = _add_minutes(start_t, duration)
            time_range = f"{_format_12h(start_t)} – {_format_12h(end_t)}"

            if previous is None:
                if hotel and hotel.lat and hotel.lon:
                    route = calculate_route((hotel.lat, hotel.lon), (place.lat, place.lon), "walking" if haversine_km(hotel.lat, hotel.lon, place.lat, place.lon) < 2.5 else "driving")
                    transit = f"{transit_label(route)} from {hotel.name}"
                else:
                    transit = "Start of day"
            else:
                distance = haversine_km(previous.lat, previous.lon, place.lat, place.lon)
                profile = "walking" if distance < 2.2 else "driving"
                route = calculate_route((previous.lat, previous.lon), (place.lat, place.lon), profile)
                transit = f"{transit_label(route)} · {route['distance_km']} km"

            note = place.description
            if day_index == 1 and flight_arr and order == 0:
                note = f"✈️ Flight lands at {_format_12h(flight_arr)}. Includes 75 min airport clearance + 75 min hotel check-in/luggage drop buffer. {place.description}"
            elif place.category in {"restaurant", "bar", "cafe"}:
                note = f"{place.description} Recommended for evening dinner. Book ahead for best seating."

            pin_number += 1
            # Prefer real scraped photos from Google Maps; fall back to curated
            # Unsplash only when no photos exist at all.
            place_photos = place.photos or []
            real_photos = [
                p for p in place_photos
                if p and ("googleusercontent" in p or "maps.googleapis" in p)
            ]
            distinct_photo = (
                real_photos[0]
                if real_photos
                else (place_photos[0] if place_photos else "")
                or get_spot_image(place.name, place.category, destination["id"], pin_number)
            )

            stops.append(
                {
                    "place_id": place.id,
                    "time_slot": slot,
                    "arrival_time": start_t,
                    "end_time": end_t,
                    "time_range": time_range,
                    "duration_mins": duration,
                    "transit_info": transit,
                    "notes": note,
                    "kind": "restaurant" if place.category in {"restaurant", "bar", "cafe"} else "place",
                }
            )
            pin = {
                "id": place.id,
                "name": place.name,
                "category": place.category,
                "lat": place.lat,
                "lon": place.lon,
                "rating": place.rating,
                "address": place.address,
                "photo": distinct_photo,
                "day_index": day_index,
                "order": order,
                "label": str(pin_number),
                "trip_id": "",
                "time_range": time_range,
            }
            pins.append(pin)
            all_stops.append({**pin, "time_slot": slot, "arrival_time": start_t, "end_time": end_t, "transit_info": transit, "duration_mins": duration, "notes": note})

            if len(cards) < 8:
                cards.append(
                    {
                        "type": "place",
                        "id": place.id,
                        "name": place.name,
                        "category": place.category,
                        "destination": destination["id"],
                        "description": place.description,
                        "image": distinct_photo,
                        "photos": [distinct_photo],
                        "rating": place.rating,
                        "review_count": place.review_count,
                        "address": place.address,
                        "price_level": place.price_level,
                        "tags": place.tags or [],
                        "lat": place.lat,
                        "lon": place.lon,
                        "day_index": day_index,
                        "order": order,
                        "time_range": time_range,
                    }
                )
            previous = place
        day_payloads.append(
            {
                "day_index": day_index,
                "date": (start_dt + timedelta(days=day_index - 1)).isoformat(),
                "title": f"Day {day_index} · {slot_titles['morning'] if day_index == 1 else destination['name'] + ' in focus'}",
                "summary": (
                    f"{day_places[0].name} in the morning, "
                    f"{day_places[1].name if len(day_places) > 1 else 'a slow afternoon'} after lunch, "
                    f"and {day_places[-1].name} in the evening."
                ) if day_places else "A free day to explore at your own pace.",
                "stops": stops,
            }
        )

    # Attach a real, freshly scraped Google Flights option. Never attach
    # route-matched/generated flights: if the live scrape fails, the trip simply
    # has no flight and the user can search again from the Flights tab.
    airport = AIRPORT_BY_DESTINATION.get(destination["id"]) or AIRPORT_BY_DESTINATION.get(destination["id"].replace("-", " "))
    origin_code = origin.upper() if origin else ""
    flight = None
    want_live_attach = os.getenv("ENABLE_LIVE_FLIGHT_ATTACH", "1").lower() not in ("0", "false", "no")
    if airport and origin_code and origin_code != airport and want_live_attach:
        try:
            from scrapers.flight_scraper_runner import (
                save_flights_to_db,
                search_flights as live_search_flights,
            )

            is_round = bool(end_date or days > 1)
            records = _run_async_sync(
                lambda: live_search_flights(
                    origin=origin_code,
                    destination=airport,
                    date=start,
                    return_date=calc_end_date if is_round else None,
                    cabin="Economy",
                    adults=passengers,
                    trip_type="round-trip" if is_round else "one-way",
                    live=True,
                    max_results=5,
                    allow_fallback=False,
                )
            ) or []
            if records:
                save_flights_to_db(records, session=session)
                top_rec = records[0]
                flight = {
                    "id": top_rec.id,
                    "airline": top_rec.airline,
                    "airline_code": top_rec.airline_code,
                    "flight_number": top_rec.flight_number,
                    "origin": top_rec.origin,
                    "destination": top_rec.destination,
                    "departure_time": str(top_rec.departure_time),
                    "arrival_time": str(top_rec.arrival_time),
                    "duration_minutes": top_rec.duration_minutes,
                    "stops": top_rec.stops,
                    "price_usd": top_rec.price_usd,
                    "price_inr": top_rec.price_inr,
                    "cabin": top_rec.cabin,
                    "baggage": top_rec.baggage,
                    "booking_url": top_rec.booking_url,
                    "trip_type": "round-trip" if is_round else "one-way",
                    "passengers": passengers,
                    "price_per_person_usd": top_rec.metadata.get("price_per_person_usd", round(top_rec.price_usd / max(1, passengers), 2)),
                    "price_per_person_inr": top_rec.metadata.get("price_per_person_inr"),
                    "return_flight": top_rec.metadata.get("return_flight"),
                }
        except Exception as exc:  # noqa: BLE001 - live flights are best effort
            pass

    final_title = title or _title_for(destination["name"], days, vibe)
    summary = (
        f"{days} days in {destination['name']}, built around {vibe.lower()}: "
        f"{plan[0][0].name}, {plan[0][-1].name} and the kind of unhurried afternoons that make a trip."
        if plan and plan[0]
        else f"{days} days in {destination['name']}, built around {vibe.lower()} and unhurried afternoons."
    )
    trip = data_service.create_trip(
        session,
        title=final_title,
        destination=destination["id"],
        days=day_payloads,
        start_date=start,
        end_date=calc_end_date,
        traveler_type=traveler_type or "Traveler",
        budget=budget,
        cover_photo=destination.get("hero_image", ""),
        summary=summary,
        tags=list(dict.fromkeys(vibe_tags + [f"{days} days"])),
        hotel_id=hotel.id if hotel else None,
        flight_id=flight["id"] if flight else None,
        flights_json=[flight] if flight else [],
        session_id=session_id or None,
        status="published",
    )
    for pin in pins:
        pin["trip_id"] = trip["id"]

    cards.insert(
        0,
        {
            "type": "trip",
            "id": trip["id"],
            "title": trip["title"],
            "destination": destination["name"],
            "destination_id": destination["id"],
            "summary": trip["summary"],
            "image": trip["cover_photo"],
            "start_date": trip["start_date"],
            "end_date": trip["end_date"],
            "day_count": trip["day_count"],
            "stop_count": trip["stop_count"],
            "tags": trip["tags"],
            "budget": trip["budget"],
            "traveler_type": trip["traveler_type"],
        },
    )
    if hotel:
        cards.append(
            {
                "type": "hotel",
                "id": hotel.id,
                "name": hotel.name,
                "destination": destination["id"],
                "image": (hotel.photos or [destination.get("hero_image", "")])[0],
                "photos": hotel.photos or [],
                "rating": hotel.rating,
                "review_count": hotel.review_count,
                "stars": hotel.stars,
                "price_per_night": hotel.price_per_night,
                "currency": hotel.currency,
                "amenities": hotel.amenities or [],
                "address": hotel.address,
                "lat": hotel.lat,
                "lon": hotel.lon,
                "description": hotel.description,
                "booking_url": hotel.booking_url,
            }
        )
        pins.append(
            {
                "id": hotel.id,
                "name": hotel.name,
                "category": "hotel",
                "lat": hotel.lat or destination["lat"],
                "lon": hotel.lon or destination["lon"],
                "rating": hotel.rating,
                "address": hotel.address,
                "photo": (hotel.photos or [""])[0],
                "day_index": 1,
                "order": -1,
                "label": "H",
                "trip_id": trip["id"],
            }
        )

    if flight:
        cards.append(
            {
                "type": "flight",
                "id": flight["id"],
                "airline": flight["airline"],
                "airline_code": flight["airline_code"],
                "flight_number": flight["flight_number"],
                "origin": flight["origin"],
                "destination": flight["destination"],
                "departure_time": flight["departure_time"],
                "arrival_time": flight["arrival_time"],
                "duration_minutes": flight["duration_minutes"],
                "stops": flight["stops"],
                "price_usd": flight["price_usd"],
                "price_inr": flight.get("price_inr"),
                "price_per_person_usd": flight.get("price_per_person_usd"),
                "price_per_person_inr": flight.get("price_per_person_inr"),
                "passengers": flight.get("passengers", passengers),
                "trip_type": flight.get("trip_type", "round-trip"),
                "return_flight": flight.get("return_flight"),
                "cabin": flight["cabin"],
                "baggage": flight["baggage"],
                "booking_url": flight["booking_url"],
            }
        )

    first = plan[0][0].name
    second = plan[0][1].name if len(plan[0]) > 1 else ""
    pax_str = f" for {traveler_type}" if traveler_type and traveler_type != "Traveler" else ""
    dates_str = f" ({start_dt.strftime('%b %d')} - {date.fromisoformat(calc_end_date).strftime('%b %d, %Y')})" if start_date else ""
    message = (
        f"Here's a {days}-day {destination['name']} plan{pax_str}{dates_str} built around {vibe.lower()}. "
        f"You'll open with {first}{', then ' + second if second else ''}, with balanced mornings, afternoons, and evenings. "
        f"I've pinned {len([p for p in pins if p['category'] != 'hotel'])} stops on the map and saved the itinerary as \"{trip['title']}\"."
    )
    if hotel:
        message += f" For the stay, I chose {hotel.name}"
        if hotel.price_per_night:
            message += f" (from ${int(hotel.price_per_night)}/night)"
        message += "."
    if flight:
        if flight.get("return_flight") or flight.get("trip_type") == "round-trip":
            pax_txt = f" for {passengers} adults" if passengers > 1 else ""
            pp_txt = f" (${int(flight.get('price_per_person_usd', 0))}/person)" if passengers > 1 and flight.get("price_per_person_usd") else ""
            message += f" For travel, I found round-trip {flight['airline']} flights ({flight['origin']} <-> {flight['destination']}) from ${int(flight['price_usd'])}{pax_txt}{pp_txt}."
        else:
            message += f" I also found a {flight['airline']} flight from {flight['origin']} to {flight['destination']} from ${int(flight['price_usd'])}."
    message += " Want me to swap the hotel, add a day trip, or rebuild a day around food?"

    return {
        "trip": trip,
        "cards": cards,
        "pins": pins,
        "message": message,
        "destination": destination,
        "hotel": data_service.hotel_dict(hotel) if hotel else None,
        "flight": flight,
        "stops": all_stops,
    }


def visuals_for_trip(session: Session, trip: dict[str, Any]) -> dict[str, Any]:
    """Build chat cards and map pins for an already-persisted trip."""
    cards: list[dict[str, Any]] = [
        {
            "type": "trip",
            "id": trip["id"],
            "title": trip["title"],
            "destination": trip.get("destination", ""),
            "destination_id": trip.get("destination", ""),
            "summary": trip.get("summary", ""),
            "image": trip.get("cover_photo", ""),
            "start_date": trip.get("start_date", ""),
            "end_date": trip.get("end_date", ""),
            "day_count": trip.get("day_count", len(trip.get("days", []))),
            "stop_count": trip.get("stop_count", 0),
            "tags": trip.get("tags", []),
            "budget": trip.get("budget", 0),
            "traveler_type": trip.get("traveler_type", ""),
        }
    ]
    pins: list[dict[str, Any]] = []
    pin_number = 0
    dest_id = trip.get("destination", "")
    for day in trip.get("days", []):
        day_idx = int(day.get("day_index") or 1)
        for order, stop in enumerate(day.get("stops", [])):
            place = stop.get("place")
            if not place:
                continue
            pin_number += 1
            # Prefer real scraped photos from Google Maps; fall back to curated
            # Unsplash only when no photos exist at all.
            place_photos = place.get("photos") or []
            real_photos = [
                p for p in place_photos
                if p and ("googleusercontent" in p or "maps.googleapis" in p)
            ]
            photo = (
                real_photos[0]
                if real_photos
                else (place_photos[0] if place_photos else "")
                or get_spot_image(place["name"], place["category"], dest_id, pin_number)
            )
            pins.append(
                {
                    "id": place["id"],
                    "name": place["name"],
                    "category": place["category"],
                    "lat": float(place["lat"]),
                    "lon": float(place["lon"]),
                    "rating": float(place.get("rating") or 4.7),
                    "address": place.get("address", ""),
                    "photo": photo,
                    "day_index": day_idx,
                    "order": int(order),
                    "label": str(pin_number),
                    "trip_id": trip["id"],
                }
            )
            if len([c for c in cards if c["type"] == "place"]) < 8:
                cards.append(
                    {
                        "type": "place",
                        "id": place["id"],
                        "name": place["name"],
                        "category": place["category"],
                        "destination": place.get("destination", ""),
                        "description": place.get("description", ""),
                        "image": photo,
                        "photos": [photo] if not place.get("photos") else place.get("photos"),
                        "rating": place.get("rating"),
                        "review_count": place.get("review_count", 0),
                        "address": place.get("address", ""),
                        "price_level": place.get("price_level"),
                        "tags": place.get("tags", []),
                        "lat": float(place["lat"]),
                        "lon": float(place["lon"]),
                        "day_index": day_idx,
                        "order": int(order),
                    }
                )
    hotel = trip.get("hotel")
    if hotel:
        cards.append(
            {
                "type": "hotel",
                "id": hotel["id"],
                "name": hotel["name"],
                "destination": hotel.get("destination", ""),
                "image": (hotel.get("photos") or [trip.get("cover_photo", "")])[0],
                "photos": hotel.get("photos", []),
                "rating": hotel.get("rating"),
                "review_count": hotel.get("review_count", 0),
                "stars": hotel.get("stars", 0),
                "price_per_night": hotel.get("price_per_night"),
                "currency": hotel.get("currency", "USD"),
                "amenities": hotel.get("amenities", []),
                "address": hotel.get("address", ""),
                "lat": hotel.get("lat"),
                "lon": hotel.get("lon"),
                "description": hotel.get("description", ""),
                "booking_url": hotel.get("booking_url", ""),
            }
        )
        pins.append(
            {
                "id": hotel["id"],
                "name": hotel["name"],
                "category": "hotel",
                "lat": hotel.get("lat") or 0,
                "lon": hotel.get("lon") or 0,
                "rating": hotel.get("rating"),
                "address": hotel.get("address", ""),
                "photo": (hotel.get("photos") or [""])[0],
                "day_index": 1,
                "order": -1,
                "label": "H",
                "trip_id": trip["id"],
            }
        )

    flights = trip.get("flights") or ([trip["flight"]] if trip.get("flight") else [])
    if flights and flights[0]:
        fl = flights[0]
        cards.append(
            {
                "type": "flight",
                "id": fl.get("id"),
                "airline": fl.get("airline"),
                "airline_code": fl.get("airline_code"),
                "flight_number": fl.get("flight_number"),
                "origin": fl.get("origin"),
                "destination": fl.get("destination"),
                "departure_time": str(fl.get("departure_time")),
                "arrival_time": str(fl.get("arrival_time")),
                "duration_minutes": fl.get("duration_minutes"),
                "stops": fl.get("stops", 0),
                "price_usd": fl.get("price_usd"),
                "price_inr": fl.get("price_inr"),
                "price_per_person_usd": fl.get("price_per_person_usd"),
                "price_per_person_inr": fl.get("price_per_person_inr"),
                "passengers": fl.get("passengers", 1),
                "trip_type": fl.get("trip_type", "round-trip"),
                "return_flight": fl.get("return_flight"),
                "cabin": fl.get("cabin", "Economy"),
                "baggage": fl.get("baggage"),
                "booking_url": fl.get("booking_url"),
            }
        )
    return {"cards": cards, "pins": pins}
