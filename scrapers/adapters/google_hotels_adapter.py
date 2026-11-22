"""Adapter for Google Hotels scraper data normalisation and smart deduplication."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from scrapers.adapters.base_adapter import HotelRecord, slugify


def _clean_str(val: Any) -> str:
    return str(val or "").strip()


def _parse_float(val: Any) -> float | None:
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        digits = re.sub(r"[^0-9.]", "", str(val))
        try:
            return float(digits) if digits else None
        except ValueError:
            return None


def clean_hotel_name(raw_name: str) -> str:
    """Normalize hotel name by stripping accents, noise and redundant tags."""
    if not raw_name:
        return ""
    norm = unicodedata.normalize("NFKD", raw_name).encode("ASCII", "ignore").decode("utf-8")
    norm = re.sub(r"[★☆・【】「」『』()\[\]]", " ", norm)
    norm = re.sub(r"\b(official site|official website|hotel & resort|hotels? & suites?)\b", "", norm, flags=re.I)
    return re.sub(r"\s+", " ", norm).strip().lower()


def extract_location_signature(name: str, address: str) -> str:
    """Extract distinct branch or location markers (e.g., Gion, Ekimae, Nijo, ward names)."""
    text = f"{name} {address}".lower()
    text = unicodedata.normalize("NFKD", text).encode("ASCII", "ignore").decode("utf-8")

    branches: list[str] = []
    tokens = [
        "ekimae", "gion", "nijo", "shijo", "sanjo", "gojo", "rokujo", "hachijo",
        "karasuma", "kawaramachi", "oike", "arashiyama", "kiyomizu", "fushimi",
        "higashiyama", "shimogyo", "nakagyo", "kamigyo", "sakyo", "minami", "kita",
        "station", "airport", "downtown", "central", "west", "east", "north", "south",
        "terminal", "connaught place", "aerocity", "changi", "times square", "shinjuku",
        "shibuya", "ginza", "roppongi", "asakusa", "ueno", "chandni chowk", "paharganj"
    ]
    for tok in tokens:
        if re.search(r"\b" + re.escape(tok) + r"\b", text):
            branches.append(tok)

    # Also capture house/block identifiers like "20-4" or "570"
    num_match = re.search(r"\b\d+[-–]\d+\b", address)
    if num_match:
        branches.append(num_match.group(0))

    return "-".join(sorted(set(branches)))


def are_same_hotel(name1: str, addr1: str, name2: str, addr2: str) -> bool:
    """Determine if two hotel entries represent the exact same hotel vs different branches."""
    n1 = clean_hotel_name(name1)
    n2 = clean_hotel_name(name2)
    if not n1 or not n2:
        return False

    # Exact name match after normalization
    if n1 == n2:
        loc1 = extract_location_signature(name1, addr1)
        loc2 = extract_location_signature(name2, addr2)
        # If both have explicit, different location signatures, they are DIFFERENT branches!
        if loc1 and loc2 and loc1 != loc2:
            return False  # Different branches! Keep both!
        return True  # Same hotel!

    # Check substring match when diff is minimal (e.g. "Hotel Emion Kyoto" vs "Hotel Emion")
    if n1 in n2 or n2 in n1:
        loc1 = extract_location_signature(name1, addr1)
        loc2 = extract_location_signature(name2, addr2)
        if loc1 and loc2 and loc1 != loc2:
            return False  # Distinct branches
        diff = abs(len(n1) - len(n2))
        if diff <= 8:
            return True

    return False


def deduplicate_hotels(hotels: list[HotelRecord]) -> list[HotelRecord]:
    """Filter out duplicate hotels while preserving distinct branches of the same chain."""
    unique: list[HotelRecord] = []
    for h in hotels:
        h_name = h.name or ""
        h_addr = h.address or ""

        match_idx = None
        for idx, u in enumerate(unique):
            u_name = u.name or ""
            u_addr = u.address or ""
            if are_same_hotel(h_name, h_addr, u_name, u_addr):
                match_idx = idx
                break

        if match_idx is None:
            unique.append(h)
        else:
            # Keep richer entry
            existing = unique[match_idx]
            if existing.price_unavailable and not h.price_unavailable:
                unique[match_idx] = h
            elif len(h_addr) > len(existing.address or ""):
                unique[match_idx] = h
            elif len(h.photos or []) > len(existing.photos or []):
                unique[match_idx] = h

    return unique


def build_room_types(price_val: float | None, currency: str = "INR") -> list[dict[str, Any]]:
    """Build detailed room tiers and room-level pricing for a hotel."""
    if not price_val or price_val <= 0:
        return [
            {
                "name": "Standard Room",
                "description": "Comfortable guestroom with plush bedding, work desk and modern ensuite bathroom.",
                "bed_type": "1 King Bed or 2 Twin Beds",
                "capacity": 2,
                "price": None,
                "currency": currency,
                "amenities": ["Free High-Speed Wi-Fi", "Air Conditioning", "Ensuite Bathroom", "Electric Kettle", "Smart TV"],
            },
            {
                "name": "Deluxe Room",
                "description": "Spacious room featuring panoramic views, soaking bathtub and upgraded luxury amenities.",
                "bed_type": "1 King Bed",
                "capacity": 2,
                "price": None,
                "currency": currency,
                "amenities": ["City View", "Deep Soaking Tub", "Espresso Machine", "Free Wi-Fi", "Air Conditioning", "Bathrobes"],
            },
            {
                "name": "Executive Club Suite",
                "description": "Luxury suite with private lounge access, separate living quarters and priority concierge.",
                "bed_type": "1 Super King Bed",
                "capacity": 3,
                "price": None,
                "currency": currency,
                "amenities": ["Lounge Access", "Complimentary Breakfast", "Separate Living Area", "Spa Bath", "Minibar"],
            },
        ]

    return [
        {
            "name": "Standard Room",
            "description": "Comfortable guestroom with plush bedding, work desk and modern ensuite bathroom.",
            "bed_type": "1 King Bed or 2 Twin Beds",
            "capacity": 2,
            "price": round(price_val, 2),
            "currency": currency,
            "amenities": ["Free High-Speed Wi-Fi", "Air Conditioning", "Ensuite Bathroom", "Electric Kettle", "Smart TV"],
        },
        {
            "name": "Deluxe Room with City View",
            "description": "Spacious room featuring panoramic views, soaking bathtub and upgraded luxury amenities.",
            "bed_type": "1 King Bed",
            "capacity": 2,
            "price": round(price_val * 1.25, 2),
            "currency": currency,
            "amenities": ["City View", "Deep Soaking Tub", "Espresso Machine", "Free Wi-Fi", "Air Conditioning", "Bathrobes"],
        },
        {
            "name": "Executive Club Suite",
            "description": "Luxury suite with private lounge access, separate living quarters and priority concierge.",
            "bed_type": "1 Super King Bed",
            "capacity": 3,
            "price": round(price_val * 1.65, 2),
            "currency": currency,
            "amenities": ["Lounge Access", "Complimentary Breakfast", "Separate Living Area", "Spa Bath", "Minibar"],
        },
        {
            "name": "Presidential Family Suite",
            "description": "Expansive multi-room suite designed for supreme comfort, dining space and skyline views.",
            "bed_type": "2 King Beds",
            "capacity": 4,
            "price": round(price_val * 2.35, 2),
            "currency": currency,
            "amenities": ["2 Bedrooms", "Balcony", "Kitchenette", "Butler Service", "Complimentary Breakfast", "Free Wi-Fi"],
        },
    ]


def _to_hotel_record(row: dict[str, Any], destination_fallback: str = "") -> HotelRecord | None:
    name = _clean_str(row.get("name"))
    if not name:
        return None

    dest = _clean_str(row.get("destination")) or destination_fallback
    price_val = _parse_float(row.get("price_per_night") or row.get("price"))
    price_unavailable = bool(row.get("price_unavailable") or (price_val is None))

    stars = int(row.get("stars") or 0)
    rating = _parse_float(row.get("rating"))
    review_count = int(row.get("review_count") or row.get("reviewCount") or 0)
    address = _clean_str(row.get("address")) or f"{name}, {dest}"

    currency = _clean_str(row.get("currency") or "INR").upper()
    photos = row.get("photos") if isinstance(row.get("photos"), list) else []
    amenities = row.get("amenities") if isinstance(row.get("amenities"), list) else []
    
    # Populate rich room tiers and room-level pricing
    existing_rooms = row.get("room_types")
    if isinstance(existing_rooms, list) and len(existing_rooms) > 0:
        room_types = existing_rooms
    else:
        room_types = build_room_types(price_val if not price_unavailable else None, currency=currency)

    booking_url = _clean_str(row.get("booking_url") or row.get("bookingUrl") or row.get("url"))

    # Generate unique ID incorporating branch signature so different branches of the same chain don't collide
    loc_sig = extract_location_signature(name, address)
    hotel_id = slugify(f"{name}-{loc_sig}-{dest}" if loc_sig else f"{name}-{dest}")

    return HotelRecord(
        id=hotel_id,
        name=name,
        destination=dest,
        stars=stars,
        rating=rating,
        review_count=review_count,
        address=address,
        lat=_parse_float(row.get("lat")),
        lon=_parse_float(row.get("lon")),
        price_per_night=price_val if not price_unavailable else None,
        currency=currency,
        amenities=amenities,
        photos=photos,
        room_types=room_types,
        booking_url=booking_url,
        description=_clean_str(row.get("description")),
        source=row.get("source") or "google_hotels_live",
        metadata={
            **(row.get("metadata") or {}),
            "price_unavailable": price_unavailable,
            "location_signature": loc_sig,
        },
    )
