"""Standard data models used across the application.

 Keeping one canonical record format means the collector, cleaner, exporter and
 API can all exchange the same structure.  Unavailable fields stay as ``None``
 and are written as blank cells in Excel.
"""
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional


@dataclass
class BusinessRecord:
    business_name: Optional[str] = None
    category: Optional[str] = None
    full_address: Optional[str] = None
    area_locality: Optional[str] = None
    city_pincode: Optional[str] = None
    phone_number: Optional[str] = None
    website: Optional[str] = None
    rating: Optional[float] = None
    total_reviews: Optional[int] = None
    opening_hours: Optional[str] = None
    business_status: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    google_maps_link: Optional[str] = None
    place_id: Optional[str] = None
    # The locality label whose feed produced this record, e.g.
    # "Dharampeth, Nagpur". Filled in by the fan-out pipeline so the combined
    # CSV can show which locality each restaurant was found in.
    search_locality: Optional[str] = None
    # True when the detail tab failed and only list-level data survived
    # (phone/website/hours may be missing). False = fully enriched.
    detail_failed: bool = False

    def to_dict(self) -> dict:
        """Return a plain dictionary copy of this record."""
        return asdict(self)


@dataclass
class SearchInfo:
    query: str
    location: str
    radius_km: Optional[float] = None
    timestamp: str = ""
    total_results: int = 0

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat(timespec="seconds")

# ---- API schemas (Pydantic) ----
from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=200, description="Business category to search for.")
    location: str = Field(..., min_length=1, max_length=200, description="Area, city, or landmark.")
    radius_km: float | None = Field(default=None, ge=0.1, le=100, description="Optional reference saved with the search; the search area itself comes from the location text.")
    max_results: int | None = Field(default=25, ge=1, le=10000, description="Maximum number of results (default 25).")
    min_rating: float | None = Field(default=None, ge=0, le=5, description="Minimum rating filter.")
    enrich_details: bool = Field(default=True, description="True (default): open each listing for phone/website/hours. False: fast list-level data only.")
    extra_locations: list[str] = Field(default=[], description="Extra areas swept by the same job (one search per area, merged and deduped).")
    extra_queries: list[str] = Field(default=[], description="Extra query variants swept per area (e.g. family restaurant, dhaba).")
    auto_areas: bool = Field(default=False, description="False (default): direct targeted search in the specified area/city. True: auto-discover localities.")
    max_areas: int | None = Field(default=1, ge=1, description="Cap on auto-discovered areas per job. Default 1 for fast searches.")


class SearchCreatedResponse(BaseModel):
    job_id: str
    status: str
    status_url: str


class SearchStatusResponse(BaseModel):
    job_id: str
    status: str
    total_results: int | None = None
    download_url: str | None = None
    error: str | None = None


class CitySearchRequest(BaseModel):
    """Whole-city sweep: resolve the city's localities, then scrape each one."""

    city: str = Field(..., min_length=1, max_length=100, description="City name, e.g. Nagpur. Its localities are resolved from mapsofindia.com (OpenStreetMap fallback).")
    query: str = Field(default="restaurant", min_length=1, max_length=200, description="Business category searched in localities.")
    radius_km: float | None = Field(default=None, ge=0.1, le=100, description="Optional reference saved with the search.")
    max_results: int | None = Field(default=25, ge=1, le=10000, description="Optional total budget across the city (default 25).")
    min_rating: float | None = Field(default=None, ge=0, le=5, description="Minimum rating filter.")
    enrich_details: bool = Field(default=True, description="True (default): open each listing for phone/website/hours. False: fast list-level data only.")
    extra_queries: list[str] = Field(default=[], description="Extra query variants swept per locality (e.g. cafe, dhaba).")
    max_localities: int | None = Field(default=2, ge=1, le=2000, description="Cap on localities swept per job. Default 2 for fast targeted results.")


class LocalitiesResponse(BaseModel):
    city: str
    source: str
    total: int
    localities: list[str]
