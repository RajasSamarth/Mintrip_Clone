"""Shared query x location fan-out used by the Apify Actor and the HTTP API.

Google caps a single Maps feed at ~120 listings, so full-city coverage means
fanning out over many areas and merging the results.  Two rules keep that from
turning into a multi-hour job:

* **Stop when the budget is met.**  ``max_results`` is a budget for *unique*
  listings and is enforced *while scraping*, so a ``max_results=100`` job never
  pays for a 100-area sweep.  Cross-area duplicates are expected, so each area
  is asked for slightly more rows than still needed (``OVERLAP_ALLOWANCE``);
  any shortfall is topped up by the next area.
* **Only parallelise unbounded sweeps.**  With a known budget we walk areas
  sequentially -- the first area usually supplies most of the rows and then we
  top up.  When the job asks for "everything" we can only go wider, so areas
  are scraped concurrently (``LOCATION_CONCURRENCY``).

The fan-out also streams results through ``on_batch`` so a run that is killed
by the platform timeout still leaves the collected listings in the dataset.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
import logging
import os
import time
from typing import Callable, Iterable, Optional, Sequence

from app.services import areas as areas_service
from app.services.cleaner import DedupeTracker, normalize_record
from app.services.collector import collect

logger = logging.getLogger(__name__)

#: Google's own ceiling for one Maps search feed.
MAX_PER_AREA = 120

#: Slack (rows) added to the remaining budget when asking one area. Feeds
#: overlap heavily across a city -- the same chain branch shows up in several
#: areas -- so asking for exactly what is still missing under-fills the job.
#: The request is at most doubled so the extra cost stays bounded.
OVERLAP_ALLOWANCE = 20

BatchCallback = Callable[[list], None]


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _dedupe_values(values: Iterable[str]) -> list[str]:
    out: list[str] = []
    for value in values or []:
        value = (value or "").strip()
        if value and value not in out:
            out.append(value)
    return out


def _area_label(area: str, city: str) -> str:
    """Turn a discovered area name into a Maps search location."""
    area = (area or "").strip()
    if not area:
        return ""
    # A coordinate from the grid fallback - keep city context if available so Google Maps doesn't default to browser IP location
    if areas_service.is_coordinate_label(area):
        return f"{area}, {city}" if city else area
    if not city or city.lower() in area.lower():
        return area
    return f"{area}, {city}"


def build_plan(
    query: str,
    location: str,
    extra_queries: Optional[Sequence[str]] = None,
    extra_locations: Optional[Sequence[str]] = None,
    auto_areas: bool = False,
    max_areas: Optional[int] = None,
) -> tuple[list[str], list[str], list[str]]:
    """Return ``(queries, locations, notes)`` for one search run.

    The requested location always comes first: for a bounded ``max_results``
    run it is what fills most of the budget, so the extra areas are only a
    top-up.
    """
    notes: list[str] = []
    queries = _dedupe_values([query, *(extra_queries or [])])
    locations = _dedupe_values([location, *(extra_locations or [])])

    if not auto_areas:
        return queries, locations, notes

    city = areas_service.extract_city(location)
    try:
        effective_max = max_areas if max_areas is not None else 2
        found = areas_service.discover_areas(city, limit=effective_max)
    except Exception as exc:  # noqa: BLE001 - discovery must never break a job
        logger.warning("Area auto-discovery crashed for %r: %s", city, exc)
        found = []

    added = 0
    for area in found:
        label = _area_label(area, city)
        if label and label not in locations:
            locations.append(label)
            added += 1

    if not added:
        notes.append(
            f"Area auto-discovery for {city!r} returned no results; scraped main location only."
        )
    elif any(areas_service.is_coordinate_label(a) for a in found):
        notes.append(
            f"OpenStreetMap areas were unavailable for {city!r}; swept a coordinate grid instead."
        )
    return queries, locations, notes


@dataclass
class FanoutResult:
    """Outcome of :func:`run_fanout`."""

    records: list = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    queries: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    swept_locations: list[str] = field(default_factory=list)
    areas_swept: int = 0
    areas_empty: int = 0
    stopped_reason: Optional[str] = None

    @property
    def total(self) -> int:
        return len(self.records)


def _ask_size(remaining: Optional[int]) -> Optional[int]:
    """How many rows to request from one area given the remaining budget."""
    if remaining is None:
        return None
    return min(MAX_PER_AREA, remaining + max(OVERLAP_ALLOWANCE, remaining))


def run_fanout(
    source,
    queries: Sequence[str],
    locations: Sequence[str],
    *,
    max_results: Optional[int] = None,
    min_rating: Optional[float] = None,
    radius_km: Optional[float] = None,
    page_size: int = 20,
    on_batch: Optional[BatchCallback] = None,
    time_budget_sec: Optional[float] = None,
    max_workers: Optional[int] = None,
) -> FanoutResult:
    """Scrape every query x location feed, dedupe, and stop at ``max_results``.

    ``on_batch`` is called with each new batch of unique :class:`BusinessRecord`
    objects (in result order), which lets the caller stream rows to the Apify
    dataset instead of holding everything until the end.  Every record is
    tagged with ``search_locality`` — the feed label it came from — so the
    combined CSV shows which locality produced each listing.
    """
    queries = _dedupe_values(queries)
    locations = _dedupe_values(locations)
    target: Optional[int] = 25
    if max_results is not None:
        try:
            target = int(max_results)
        except (TypeError, ValueError):
            target = 25
        if target is not None and target <= 0:
            target = 25

    result = FanoutResult(queries=list(queries), locations=list(locations))
    tracker = DedupeTracker()
    unique: list = result.records
    errors: list[Exception] = []

    deadline: Optional[float] = None
    if time_budget_sec and time_budget_sec > 0:
        deadline = time.monotonic() + time_budget_sec

    def budget_left() -> bool:
        return deadline is None or time.monotonic() < deadline

    def done() -> bool:
        return target is not None and len(unique) >= target

    def accept(raw_records, location) -> int:
        """Normalize + filter + dedupe new rows, streaming them out."""
        if not raw_records:
            return 0
        fresh: list = []
        for raw in raw_records:
            rec = normalize_record(raw)
            # Provenance for the combined CSV: which locality feed found it.
            if not rec.search_locality:
                rec.search_locality = location
            if min_rating is not None and rec.rating is not None and rec.rating < float(min_rating):
                continue
            if not tracker.add(rec):
                continue
            unique.append(rec)
            fresh.append(rec)
            if done():
                break
        if fresh and on_batch is not None:
            try:
                on_batch(fresh)
            except Exception as exc:  # noqa: BLE001 - a failed push must not stop the scrape
                logger.warning("Batch callback failed (%d rows): %s", len(fresh), exc)
                result.notes.append(f"Could not push a batch of {len(fresh)} listings: {exc}")
        return len(fresh)

    def record_attempt(query: str, location: str, page_records, error) -> int:
        result.areas_swept += 1
        if location not in result.swept_locations:
            result.swept_locations.append(location)
        if error is not None:
            errors.append(error)
        got = accept(page_records, location)
        logger.info(
            "[%d/%d areas] %r @ %r: %d scraped, %d new, %d total",
            result.areas_swept,
            len(queries) * len(locations),
            query,
            location,
            len(page_records or []),
            got,
            len(unique),
        )
        return got

    tasks = [(q, loc) for q in queries for loc in locations]

    if target is not None:
        # Bounded run: sequential, stop as soon as the budget is filled.
        # Areas that only repeat listings we already have must not keep the
        # job alive for an hour (small towns often resolve every locality to
        # the same feed), so give up after a few fruitless areas in a row.
        max_stale = max(1, _env_int("MAX_STALE_AREAS", 5))
        stale = 0
        for query, location in tasks:
            if done():
                result.stopped_reason = "max_results reached"
                break
            if not budget_left():
                result.stopped_reason = "time budget reached"
                break
            remaining = max(0, target - len(unique))
            page_records, error, _meta = collect(
                source,
                query,
                location,
                radius_km=radius_km,
                max_results=_ask_size(remaining),
                page_size=page_size,
            )
            got = record_attempt(query, location, page_records, error)
            if not page_records and error is None:
                result.areas_empty += 1
            stale = stale + 1 if got == 0 else 0
            if stale >= max_stale:
                result.stopped_reason = f"no new listings in {stale} consecutive areas"
                break
    else:
        # Unbounded run ("give me everything"): widen across areas.
        workers = max_workers or _env_int("LOCATION_CONCURRENCY", 2)
        workers = max(1, min(workers, max(1, len(tasks))))
        if workers == 1:
            for query, location in tasks:
                if not budget_left():
                    result.stopped_reason = "time budget reached"
                    break
                page_records, error, _meta = collect(
                    source,
                    query,
                    location,
                    radius_km=radius_km,
                    max_results=None,
                    page_size=page_size,
                )
                record_attempt(query, location, page_records, error)
                if not page_records and error is None:
                    result.areas_empty += 1
        else:
            logger.info(
                "Unbounded sweep: %d feeds across %d concurrent areas", len(tasks), workers
            )
            pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="area")
            futures = {
                pool.submit(
                    collect, source, q, loc, radius_km, None, page_size
                ): (q, loc)
                for q, loc in tasks
            }
            try:
                for fut in as_completed(futures, timeout=None):
                    query, location = futures[fut]
                    try:
                        page_records, error, _meta = fut.result()
                    except Exception as exc:  # noqa: BLE001 - keep the other areas
                        page_records, error = [], exc
                    record_attempt(query, location, page_records, error)
                    if not page_records and error is None:
                        result.areas_empty += 1
                    if not budget_left():
                        result.stopped_reason = "time budget reached"
                        break
            except Exception as exc:  # noqa: BLE001 - as_completed itself
                logger.warning("Area sweep interrupted: %s", exc)
                errors.append(exc)
            finally:
                pool.shutdown(wait=False, cancel_futures=True)

    if errors:
        result.errors = sorted({str(e) for e in errors})
        result.notes.append("; ".join(result.errors))
    if target is not None and len(unique) < target and not errors:
        result.notes.append(
            f"Only {len(unique)} of {target} requested listings were available "
            f"across {result.areas_swept} feed(s)."
        )
    return result
