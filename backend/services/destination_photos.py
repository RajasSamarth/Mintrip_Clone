"""Destination cover photo resolver with high-resolution imagery for global and Indian destinations."""

from __future__ import annotations

import re
from typing import Any
from sqlmodel import Session, select

# High-resolution, licensed Unsplash photography for major world & Indian destinations
DESTINATION_PHOTOS: dict[str, str] = {
    # India - Major Cities & Regions
    "pune": "https://images.unsplash.com/photo-1576487247234-4366d0ef0a30?auto=format&fit=crop&w=1800&q=80",
    "delhi": "https://images.unsplash.com/photo-1587474260584-136574528ed5?auto=format&fit=crop&w=1800&q=80",
    "new delhi": "https://images.unsplash.com/photo-1587474260584-136574528ed5?auto=format&fit=crop&w=1800&q=80",
    "mumbai": "https://images.unsplash.com/photo-1570168007204-dfb528c6958f?auto=format&fit=crop&w=1800&q=80",
    "bombay": "https://images.unsplash.com/photo-1570168007204-dfb528c6958f?auto=format&fit=crop&w=1800&q=80",
    "bengaluru": "https://images.unsplash.com/photo-1596176530529-78163a4f7af2?auto=format&fit=crop&w=1800&q=80",
    "bangalore": "https://images.unsplash.com/photo-1596176530529-78163a4f7af2?auto=format&fit=crop&w=1800&q=80",
    "jaipur": "https://images.unsplash.com/photo-1603262110263-fb010d6e59d4?auto=format&fit=crop&w=1800&q=80",
    "agra": "https://images.unsplash.com/photo-1564507592333-c60657eea523?auto=format&fit=crop&w=1800&q=80",
    "goa": "https://images.unsplash.com/photo-1512343879784-a960bf40e7f2?auto=format&fit=crop&w=1800&q=80",
    "kerala": "https://images.unsplash.com/photo-1602216056096-3b40cc0c9944?auto=format&fit=crop&w=1800&q=80",
    "kolkata": "https://images.unsplash.com/photo-1558431382-27e303142255?auto=format&fit=crop&w=1800&q=80",
    "chennai": "https://images.unsplash.com/photo-1582510003544-4d00b7f74220?auto=format&fit=crop&w=1800&q=80",
    "hyderabad": "https://images.unsplash.com/photo-1605649487212-47bdab064df8?auto=format&fit=crop&w=1800&q=80",
    "varanasi": "https://images.unsplash.com/photo-1561361513-2d000a50f0dc?auto=format&fit=crop&w=1800&q=80",
    "udaipur": "https://images.unsplash.com/photo-1615836245337-f5b9b2303f10?auto=format&fit=crop&w=1800&q=80",
    "bhopal": "https://images.unsplash.com/photo-1609137144822-0d12753a8069?auto=format&fit=crop&w=1800&q=80",
    "indore": "https://images.unsplash.com/photo-1628155930542-3c7a64e2c833?auto=format&fit=crop&w=1800&q=80",
    "nagpur": "https://images.unsplash.com/photo-1605649487212-47bdab064df8?auto=format&fit=crop&w=1800&q=80",
    "amritsar": "https://images.unsplash.com/photo-1584551246679-0daf3d275d0f?auto=format&fit=crop&w=1800&q=80",
    "shimla": "https://images.unsplash.com/photo-1588668214407-6ea9a6d8c272?auto=format&fit=crop&w=1800&q=80",
    "manali": "https://images.unsplash.com/photo-1605649487212-47bdab064df8?auto=format&fit=crop&w=1800&q=80",
    "rishikesh": "https://images.unsplash.com/photo-1596768341671-55e105e197ca?auto=format&fit=crop&w=1800&q=80",
    "ladakh": "https://images.unsplash.com/photo-1581793745862-99fde7fa73d2?auto=format&fit=crop&w=1800&q=80",
    "kashmir": "https://images.unsplash.com/photo-1595815771614-ade9d652a65d?auto=format&fit=crop&w=1800&q=80",
    "india": "https://images.unsplash.com/photo-1524492412937-b28074a5d7da?auto=format&fit=crop&w=1800&q=80",

    # International Cities & Destinations
    "dublin": "https://images.unsplash.com/photo-1549918864-48ac978761a4?auto=format&fit=crop&w=1800&q=80",
    "ireland": "https://images.unsplash.com/photo-1549918864-48ac978761a4?auto=format&fit=crop&w=1800&q=80",
    "paris": "https://images.unsplash.com/photo-1502602898657-3e91760cbb34?auto=format&fit=crop&w=1800&q=80",
    "france": "https://images.unsplash.com/photo-1502602898657-3e91760cbb34?auto=format&fit=crop&w=1800&q=80",
    "london": "https://images.unsplash.com/photo-1513635269975-59663e0ac1ad?auto=format&fit=crop&w=1800&q=80",
    "united kingdom": "https://images.unsplash.com/photo-1513635269975-59663e0ac1ad?auto=format&fit=crop&w=1800&q=80",
    "tokyo": "https://images.unsplash.com/photo-1540959733332-eab4deabeeaf?auto=format&fit=crop&w=1800&q=80",
    "kyoto": "https://images.unsplash.com/photo-1493976040374-85c8e12f0c0e?auto=format&fit=crop&w=1800&q=80",
    "osaka": "https://images.unsplash.com/photo-1590559899731-a382839e5549?auto=format&fit=crop&w=1800&q=80",
    "japan": "https://images.unsplash.com/photo-1493976040374-85c8e12f0c0e?auto=format&fit=crop&w=1800&q=80",
    "rome": "https://images.unsplash.com/photo-1552832230-c0197dd311b5?auto=format&fit=crop&w=1800&q=80",
    "venice": "https://images.unsplash.com/photo-1514890547357-a9ee288728e0?auto=format&fit=crop&w=1800&q=80",
    "florence": "https://images.unsplash.com/photo-1543429776-2782fc8e1acd?auto=format&fit=crop&w=1800&q=80",
    "italy": "https://images.unsplash.com/photo-1552832230-c0197dd311b5?auto=format&fit=crop&w=1800&q=80",
    "bali": "https://images.unsplash.com/photo-1537996194471-e657df975ab4?auto=format&fit=crop&w=1800&q=80",
    "indonesia": "https://images.unsplash.com/photo-1537996194471-e657df975ab4?auto=format&fit=crop&w=1800&q=80",
    "bangkok": "https://images.unsplash.com/photo-1508009603885-50cf7c579365?auto=format&fit=crop&w=1800&q=80",
    "phuket": "https://images.unsplash.com/photo-1589394815804-964ed0be2eb5?auto=format&fit=crop&w=1800&q=80",
    "thailand": "https://images.unsplash.com/photo-1508009603885-50cf7c579365?auto=format&fit=crop&w=1800&q=80",
    "dubai": "https://images.unsplash.com/photo-1512453979798-5ea266f8880c?auto=format&fit=crop&w=1800&q=80",
    "abu dhabi": "https://images.unsplash.com/photo-1512632570417-a60008dd52f3?auto=format&fit=crop&w=1800&q=80",
    "united arab emirates": "https://images.unsplash.com/photo-1512453979798-5ea266f8880c?auto=format&fit=crop&w=1800&q=80",
    "singapore": "https://images.unsplash.com/photo-1525625293386-3f8f99389edd?auto=format&fit=crop&w=1800&q=80",
    "new york": "https://images.unsplash.com/photo-1496442226666-8d4d0e62e6e9?auto=format&fit=crop&w=1800&q=80",
    "san francisco": "https://images.unsplash.com/photo-1501594907352-04cda38ebc29?auto=format&fit=crop&w=1800&q=80",
    "los angeles": "https://images.unsplash.com/photo-1580655653885-65763b2597d0?auto=format&fit=crop&w=1800&q=80",
    "united states": "https://images.unsplash.com/photo-1496442226666-8d4d0e62e6e9?auto=format&fit=crop&w=1800&q=80",
    "barcelona": "https://images.unsplash.com/photo-1583422409516-2895a77efded?auto=format&fit=crop&w=1800&q=80",
    "madrid": "https://images.unsplash.com/photo-1539037116277-4db20889f2d4?auto=format&fit=crop&w=1800&q=80",
    "spain": "https://images.unsplash.com/photo-1583422409516-2895a77efded?auto=format&fit=crop&w=1800&q=80",
    "amsterdam": "https://images.unsplash.com/photo-1534351590666-13e3e96b5017?auto=format&fit=crop&w=1800&q=80",
    "netherlands": "https://images.unsplash.com/photo-1534351590666-13e3e96b5017?auto=format&fit=crop&w=1800&q=80",
    "swiss alps": "https://images.unsplash.com/photo-1533105079780-92b9be482077?auto=format&fit=crop&w=1800&q=80",
    "switzerland": "https://images.unsplash.com/photo-1530122037265-a5f1f91d3b99?auto=format&fit=crop&w=1800&q=80",
    "sydney": "https://images.unsplash.com/photo-1506973035872-a4ec16b8e8d9?auto=format&fit=crop&w=1800&q=80",
    "melbourne": "https://images.unsplash.com/photo-1514395462725-fb4566210144?auto=format&fit=crop&w=1800&q=80",
    "australia": "https://images.unsplash.com/photo-1506973035872-a4ec16b8e8d9?auto=format&fit=crop&w=1800&q=80",
    "cairo": "https://images.unsplash.com/photo-1572252009286-268acec5ca0a?auto=format&fit=crop&w=1800&q=80",
    "egypt": "https://images.unsplash.com/photo-1572252009286-268acec5ca0a?auto=format&fit=crop&w=1800&q=80",
    "istanbul": "https://images.unsplash.com/photo-1524231757912-21f4fe3a7200?auto=format&fit=crop&w=1800&q=80",
    "turkey": "https://images.unsplash.com/photo-1524231757912-21f4fe3a7200?auto=format&fit=crop&w=1800&q=80",
    "seoul": "https://images.unsplash.com/photo-1538485399081-7191377e8241?auto=format&fit=crop&w=1800&q=80",
    "south korea": "https://images.unsplash.com/photo-1538485399081-7191377e8241?auto=format&fit=crop&w=1800&q=80",
}

DEFAULT_FALLBACK = "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?auto=format&fit=crop&w=1800&q=80"


def clean_dest_key(destination: str) -> str:
    """Normalize destination string to match keys."""
    if not destination:
        return ""
    # Strip country/state suffixes like ", India" or ", Maharashtra"
    first_part = destination.split(",")[0].strip().lower()
    first_part = re.sub(r"[^\w\s-]", "", first_part)
    return first_part.strip()


def resolve_destination_photo(destination: str, session: Session | None = None) -> str:
    """
    Finds a scenic, authentic cover photo for a city or country:
    1. Looks up normalized key in DESTINATION_PHOTOS dictionary.
    2. Partial substring search in DESTINATION_PHOTOS.
    3. Checks if any Hotel or Place in the database for this destination has photos.
    4. Falls back to a clean landscape image.
    """
    if not destination:
        return DEFAULT_FALLBACK

    key = clean_dest_key(destination)
    if key in DESTINATION_PHOTOS:
        return DESTINATION_PHOTOS[key]

    # Check whole string lowercase
    raw_lower = destination.lower().strip()
    for dest_name, photo_url in DESTINATION_PHOTOS.items():
        if dest_name in raw_lower or raw_lower in dest_name:
            return photo_url

    # Check database for existing hotel/place photos in that destination
    if session:
        try:
            from backend.database.models import Destination, Hotel, Place

            dest_row = session.get(Destination, key) or session.get(Destination, raw_lower)
            if dest_row and dest_row.hero_image:
                return dest_row.hero_image

            place = session.exec(
                select(Place).where(Place.destination.ilike(f"%{key}%")).where(Place.photos != None)  # noqa: E711
            ).first()
            if place and place.photos and len(place.photos) > 0 and place.photos[0]:
                return place.photos[0]

            hotel = session.exec(
                select(Hotel).where(Hotel.destination.ilike(f"%{key}%")).where(Hotel.photos != None)  # noqa: E711
            ).first()
            if hotel and hotel.photos and len(hotel.photos) > 0 and hotel.photos[0]:
                return hotel.photos[0]
        except Exception:
            pass

    return DEFAULT_FALLBACK
