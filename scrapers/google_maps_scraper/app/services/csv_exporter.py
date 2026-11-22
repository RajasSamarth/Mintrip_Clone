"""CSV export helpers for the business extractor.

Produces a single flat CSV with one row per business listing, using the same
canonical columns as the Excel exporter so the two outputs are interchangeable.
"""
import csv
import io
import logging
import re
from datetime import date
from pathlib import Path

from app.schemas import BusinessRecord, SearchInfo

logger = logging.getLogger(__name__)

# Same column order as the Excel exporter so Excel and CSV outputs match.
COLUMNS = [
    "Sr. No.",
    "Business Name",
    "Category",
    "Full Address",
    "Area / Locality",
    "City / Pincode",
    "Phone Number",
    "Website",
    "Rating",
    "Total Reviews",
    "Opening Hours",
    "Business Status",
    "Latitude, Longitude",
    "Google Maps Link",
    "Place ID",
    "Search Locality",
    "Detail Status",
]


def sanitize_filename_part(value: str) -> str:
    """Make a string safe to use as part of a file name."""
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "search"


def build_filename(query: str, location: str, when: date | None = None) -> str:
    q = sanitize_filename_part(query)[:30]
    loc = sanitize_filename_part(location)[:60]
    day = (when or date.today()).isoformat()
    return f"{q}_{loc}_{day}.csv"


def _as_dict(record) -> dict:
    """Accept a BusinessRecord or a plain dict and return a dict."""
    if isinstance(record, BusinessRecord):
        return record.to_dict()
    return dict(record or {})


def _clean(value):
    """Convert empty strings / NaN-like values to None (blank cell)."""
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped != "" else None
    try:
        import math

        if isinstance(value, float) and math.isnan(value):
            return None
    except Exception:
        pass
    return value


def _coords(record_dict: dict) -> str | None:
    lat = _clean(record_dict.get("latitude"))
    lon = _clean(record_dict.get("longitude"))
    if lat is None and lon is None:
        return None
    if lat is None:
        return str(lon)
    if lon is None:
        return str(lat)
    return f"{lat}, {lon}"


def _detail_status(record_dict: dict) -> str:
    return "Skipped" if record_dict.get("detail_failed") else "Complete"


def _row_from_record(index: int, record) -> list:
    d = _as_dict(record)
    return [
        index,
        _clean(d.get("business_name")),
        _clean(d.get("category")),
        _clean(d.get("full_address")),
        _clean(d.get("area_locality")),
        _clean(d.get("city_pincode")),
        _clean(d.get("phone_number")),
        _clean(d.get("website")),
        _clean(d.get("rating")),
        _clean(d.get("total_reviews")),
        _clean(d.get("opening_hours")),
        _clean(d.get("business_status")),
        _coords(d),
        _clean(d.get("google_maps_link")),
        _clean(d.get("place_id")),
        _clean(d.get("search_locality")),
        _detail_status(d),
    ]


def export_to_csv(records, search_info, output_dir="output", filename_location=None) -> Path:
    """Create a ``.csv`` file from records and search metadata.

    Returns the path to the generated file.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if isinstance(search_info, SearchInfo):
        info = search_info
    else:
        from app.schemas import SearchInfo as _SI

        info = _SI(
            query=search_info.get("query", ""),
            location=search_info.get("location", ""),
            radius_km=search_info.get("radius_km"),
            timestamp=search_info.get("timestamp", "") or None,
            total_results=search_info.get("total_results", len(list(records))),
        )

    records_list = list(records or [])
    name_query = info.query
    name_location = filename_location if filename_location else info.location
    filename = build_filename(name_query, name_location)
    file_path = output_path / filename

    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNS)
        for i, rec in enumerate(records_list, start=1):
            writer.writerow(_row_from_record(i, rec))

    logger.info("Wrote %d records to %s", len(records_list), file_path)
    return file_path
