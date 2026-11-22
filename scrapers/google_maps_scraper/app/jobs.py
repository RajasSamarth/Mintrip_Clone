"""In-memory job tracking for search requests.

This is intentionally simple (single-process, memory only).  It is fine for
local development and demos; a production deployment should replace it with a
persistent store plus a real task queue.
"""
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import os
import time

from pathlib import Path

# already imports Path

def _output_dir() -> str:
    return os.getenv("OUTPUT_DIR", "output")


def cleanup_expired_files(output_dir: str | None = None, max_age_hours: int | None = None) -> int:
    """Delete generated Excel files older than max_age_hours. Returns count deleted."""
    if output_dir is None:
        output_dir = _output_dir()
    if max_age_hours is None:
        max_age_hours = int(os.getenv("FILE_RETENTION_HOURS", "24"))
    directory = Path(output_dir)
    if not directory.exists():
        return 0
    cutoff = time.time() - (max_age_hours * 3600)
    deleted = 0
    for pattern in ("*.xlsx", "*.csv"):
        for file_path in directory.glob(pattern):
            try:
                if file_path.stat().st_mtime < cutoff:
                    file_path.unlink()
                    deleted += 1
            except OSError:
                continue
    return deleted


from typing import Any, Optional

from app.adapters.approved_source import SyntheticDataSource
from app.services.csv_exporter import export_to_csv
from app.services.excel_exporter import export_to_excel
from app.services.pipeline import build_plan, run_fanout

# ---- Job store ----
_JOBS: dict[str, "Job"] = {}
_LOCK = threading.Lock()

# Simple in-memory cache of finished jobs keyed by a normalized params hash.
_CACHE: dict[str, str] = {}  # cache_key -> job_id
_CACHE_EXPIRY: dict[str, datetime] = {}

# Guardrails (overridable via env at import if desired).
import logging
import time
from concurrent.futures import ThreadPoolExecutor

# at top? jobs already has imports; add after docstring? We'll just use module global. Need insert logger after imports. But imports typing already. We'll add `logger` after Job class? Simpler replace 'MAX_JOBS = 10' with logger definition.
MAX_JOBS = 10
logger = logging.getLogger(__name__)

# Dedicated pool so long scrapes never block the API event loop / threadpool.
_JOB_WORKERS = max(1, int(os.getenv("JOB_WORKERS", "3") or "3"))
_EXECUTOR = ThreadPoolExecutor(max_workers=_JOB_WORKERS, thread_name_prefix="search-job")

# -----------------------------------------------------------------
# Factory: return the concrete DataSource the job will use.
# -----------------------------------------------------------------
def _data_source(max_results: int | None = None, enrich: bool = True):
    """Pick a source based on environment variables.

    * ``USE_PLAYWRIGHT_SOURCE`` = "1"  → PlaywrightGoogleMapsSource (requires
      explicit organizational permission).
    * anything else → SyntheticDataSource (used for development / demos).
    """
    if __import__("os").getenv("USE_PLAYWRIGHT_SOURCE") == "1":
        # Lazy import so hosts without Playwright installed can still run
        # the synthetic demo source. Playwright is an optional dependency.
        from app.adapters.playwright_source import PlaywrightGoogleMapsSource
        # headless=True keeps the browser invisible; set False for debugging.
        # target_cap ensures a max_results=5 job scrapes ~5 listings, not 500.
        return PlaywrightGoogleMapsSource(headless=True, target_cap=max_results, enrich=enrich)
    return SyntheticDataSource(total_available=87, page_size=20)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Job:
    job_id: str
    params: dict[str, Any]
    status: str = "queued"
    created_at: datetime = field(default_factory=_utcnow)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    records: list = field(default_factory=list)
    total_results: int = 0
    file_path: Optional[str] = None
    error: Optional[str] = None


def _cache_key(params: dict[str, Any]) -> str:
    return repr(sorted((k, v) for k, v in params.items()))


def can_accept_new_job() -> bool:
    active = sum(1 for j in _JOBS.values() if j.status in ("queued", "running"))
    return active < MAX_JOBS


def create_job(params: dict[str, Any]) -> Job:
    """Create a (possibly cached) job and return it."""
    key = _cache_key(params)
    now = _utcnow()

    # Cache hit: reuse the previous finished job if still fresh.
    cached_id = _CACHE.get(key)
    if cached_id and cached_id in _JOBS:
        expiry = _CACHE_EXPIRY.get(key)
        if expiry is None or expiry > now:
            cached_file = _JOBS[cached_id].file_path
            if cached_file and Path(cached_file).exists():
                return _JOBS[cached_id]

    job = Job(job_id=str(uuid.uuid4()), params=params)
    with _LOCK:
        _JOBS[job.job_id] = job
    return job


# Fix attribute access: keep a plain helper.
def get_job(job_id: str) -> Optional[Job]:
    with _LOCK:
        return _JOBS.get(job_id)


def list_job_ids() -> list[str]:
    with _LOCK:
        return list(_JOBS.keys())


def run_job(job_id: str) -> None:
    """Execute a job synchronously. Designed to run in a background task."""
    job = get_job(job_id)
    if job is None:
        return

    job.status = "running"
    job.started_at = _utcnow()
    started_at_monotonic = time.monotonic()
    params = job.params
    logger.info("Job %s running params=%s", job_id, params)
    try:
        radius = params.get("radius_km")
        max_results = params.get("max_results") or 25
        min_rating = params.get("min_rating")

        # Per-area target cap: a max_results=25 job should not scrape 500
        # listings per area just to throw almost all of them away.
        source = _data_source(max_results=max_results,
                              enrich=params.get("enrich_details", True))

        # Fan-out: query variant x location. Direct fast targeted search by default;
        # auto_areas is capped so it never sweeps hundreds of localities.
        queries, locations, plan_notes = build_plan(
            query=params["query"],
            location=params["location"],
            extra_queries=params.get("extra_queries") or [],
            extra_locations=params.get("extra_locations") or [],
            auto_areas=params.get("auto_areas", False),
            max_areas=params.get("max_areas") or 1,
        )
        logger.info(
            "Job %s plan: %d query(s) x %d location(s); max_results=%s",
            job_id, len(queries), len(locations), max_results,
        )
        if params.get("city"):
            plan_notes.append(
                "City sweep of {city}: {n} localities from {src}.".format(
                    city=params["city"],
                    n=params.get("total_localities", len(locations)),
                    src=params.get("localities_source") or "auto-discovery",
                )
            )

        fanout = run_fanout(
            source,
            queries,
            locations,
            max_results=max_results,
            min_rating=min_rating,
            radius_km=radius,
        )
        cleaned = fanout.records
        error = None
        if fanout.errors:
            error = RuntimeError(fanout.errors[-1])
        if fanout.stopped_reason:
            logger.info("Job %s sweep stopped early: %s", job_id, fanout.stopped_reason)

        from app.schemas import SearchInfo

        swept = fanout.swept_locations or locations
        info = SearchInfo(
            query=", ".join(queries),
            location=", ".join(swept),
            radius_km=radius,
            timestamp=_utcnow().isoformat(timespec="seconds"),
            total_results=len(cleaned),
        )

        # Keep records on the job BEFORE exporting, so a failed export
        # (e.g. an over-long file name) still leaves previewable results.
        job.records = cleaned
        job.total_results = len(cleaned)

        if len(swept) > 1:
            file_label = f"{swept[0]} + {len(swept) - 1} areas"
        else:
            file_label = swept[0]
        if params.get("city"):
            # City sweeps get a clean "<city>" file name instead of
            # "Dharampeth, Nagpur + 51 areas".
            file_label = params["city"]
        # Always produce a combined CSV (one file for the whole city sweep)
        # and keep the Excel version as well.
        csv_path = export_to_csv(
            cleaned, info, output_dir=_output_dir(), filename_location=file_label
        )
        export_to_excel(
            cleaned, info, output_dir=_output_dir(), filename_location=file_label
        )
        job.file_path = str(csv_path)  # download serves the combined CSV

        # Cache the finished result for 24 hours.
        key = _cache_key(params)
        _CACHE[key] = job.job_id
        _CACHE_EXPIRY[key] = _utcnow() + timedelta(hours=24)

        if error is not None and not cleaned:
            job.status = "failed"
            job.error = str(error)
        else:
            job.status = "done"
            notes = []
            if error is not None:
                notes.append(f"Partial failure: {error}")
            notes.extend(plan_notes)
            notes.extend(fanout.notes)
            skipped = sum(1 for r in cleaned if getattr(r, "detail_failed", False))
            if skipped:
                notes.append(f"{skipped}/{len(cleaned)} listings partial (detail tab skipped)")
            job.error = "; ".join(dict.fromkeys(notes)) if notes else None
    except Exception as exc:  # noqa: BLE001
        job.status = "failed"
        job.error = str(exc)
    finally:
        job.finished_at = _utcnow()
        duration = time.monotonic() - started_at_monotonic
        logger.info(
            "Job %s finished status=%s total=%d duration=%.2fs error=%s",
            job.job_id, job.status, job.total_results, duration, job.error,
        )


def submit_job(job_id: str) -> None:
    """Queue run_job on the dedicated pool. Returns immediately."""
    _EXECUTOR.submit(run_job, job_id)
