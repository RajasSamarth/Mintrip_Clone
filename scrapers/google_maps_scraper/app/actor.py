"""Apify Actor entry point for Google Maps Business Data Extractor.

This script executes when running as an Apify Actor on the Apify platform or
locally via the Apify CLI / python -m app.actor. It reads input from the Actor
input schema, runs the search/scraper pipeline, pushes listings to the Apify
Dataset, and optionally saves the formatted Excel file to the Key-Value Store.

Listings are pushed to the dataset batch by batch *while* scraping, so a run
that hits the platform timeout still leaves everything collected so far in the
dataset instead of losing the whole run.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
import logging
import os
from pathlib import Path
import time
from typing import Any, Callable, Optional, Tuple

from apify import Actor

from app.schemas import BusinessRecord, SearchInfo
from app.services.csv_exporter import export_to_csv
from app.services.excel_exporter import export_to_excel
from app.services.pipeline import build_plan, run_fanout

logger = logging.getLogger("apify.actor")

#: Optional hard stop (minutes) so a huge sweep ends cleanly instead of being
#: killed at the platform timeout. Default is 720 (12 hours). 0 disables it.
#: Partial data is safe either way because rows are streamed to the dataset.
DEFAULT_MAX_RUNTIME_MINUTES = 720


def _max_runtime_seconds(params: Optional[dict[str, Any]] = None) -> Optional[float]:
    if params and "max_runtime_minutes" in params and params["max_runtime_minutes"] is not None:
        try:
            minutes = float(params["max_runtime_minutes"])
            return minutes * 60 if minutes > 0 else None
        except (TypeError, ValueError):
            pass
    try:
        minutes = float(os.getenv("MAX_RUNTIME_MINUTES", str(DEFAULT_MAX_RUNTIME_MINUTES)) or 0)
    except (TypeError, ValueError):
        minutes = 0
    return minutes * 60 if minutes > 0 else None


def _sync_scrape_pipeline(
    params: dict[str, Any],
    emit: Optional[Callable[[list[BusinessRecord]], None]] = None,
) -> Tuple[list[BusinessRecord], Path | None, Path | None, list[str]]:
    """Synchronous pipeline executed in a worker thread.

    Running in a separate thread ensures Playwright's internal asyncio.run()
    does not conflict with Apify's main event loop.

    ``emit`` receives each new batch of unique records as it is scraped so the
    caller can stream them to the dataset.
    """
    query = (params.get("query") or "dental clinic").strip()
    location = (params.get("location") or "Dharampeth, Nagpur").strip()
    radius_km = params.get("radius_km")
    max_results = params.get("max_results") or 25
    min_rating = params.get("min_rating")
    enrich_details = params.get("enrich_details", True)
    auto_areas = params.get("auto_areas", False)
    max_areas = params.get("max_areas") or 1
    export_excel_flag = params.get("export_excel", True)
    use_playwright = params.get("use_playwright_source", True)

    # The Actor runs a single job, so the per-process worker count is 1. This
    # lets the Playwright adapter use its full parallel-page budget for detail
    # enrichment instead of being clamped to 14 // JOB_WORKERS.
    os.environ.setdefault("JOB_WORKERS", "1")

    # Choose data source
    if use_playwright:
        os.environ["USE_PLAYWRIGHT_SOURCE"] = "1"
        from app.adapters.playwright_source import PlaywrightGoogleMapsSource
        source = PlaywrightGoogleMapsSource(
            headless=True,
            target_cap=max_results,
            enrich=enrich_details,
        )
    else:
        from app.adapters.approved_source import SyntheticDataSource
        source = SyntheticDataSource(total_available=87, page_size=20)

    queries, locations, notes = build_plan(
        query=query,
        location=location,
        extra_queries=params.get("extra_queries") or [],
        extra_locations=params.get("extra_locations") or [],
        auto_areas=auto_areas,
        max_areas=max_areas,
    )
    logger.info(
        "Plan: %d query(s) x %d location(s) = %d feed(s); max_results=%s",
        len(queries),
        len(locations),
        len(queries) * len(locations),
        max_results,
    )

    result = run_fanout(
        source,
        queries,
        locations,
        max_results=max_results,
        min_rating=min_rating,
        radius_km=radius_km,
        on_batch=emit,
        time_budget_sec=_max_runtime_seconds(params),
    )
    notes.extend(result.notes)
    cleaned = result.records

    if result.stopped_reason:
        logger.info("Sweep stopped early: %s", result.stopped_reason)

    csv_file: Path | None = None
    xlsx_file: Path | None = None
    if export_excel_flag:
        from datetime import timezone
        # Report what was actually swept, not every discovered area: an early
        # stop means the file name should not claim 82 untouched areas.
        swept = result.swept_locations or locations
        info = SearchInfo(
            query=", ".join(queries),
            location=", ".join(swept),
            radius_km=radius_km,
            timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            total_results=len(cleaned),
        )
        file_label = f"{swept[0]} + {len(swept) - 1} areas" if len(swept) > 1 else swept[0]
        output_dir = os.getenv("OUTPUT_DIR", "output")
        # Always produce a combined CSV (one file for the whole city sweep)
        # and keep the Excel version as well.
        csv_file = export_to_csv(
            records=cleaned,
            search_info=info,
            output_dir=output_dir,
            filename_location=file_label,
        )
        xlsx_file = export_to_excel(
            records=cleaned,
            search_info=info,
            output_dir=output_dir,
            filename_location=file_label,
        )
        # The combined CSV is the primary downloadable artifact.

    return cleaned, csv_file, xlsx_file, notes


def _dataset_emitter(loop: asyncio.AbstractEventLoop) -> Callable[[list[BusinessRecord]], None]:
    """Build a thread-safe emitter that pushes batches to the dataset.

    Called from the worker thread: the coroutine is scheduled back onto the
    Actor's own event loop, and we block on the result so scraping cannot run
    ahead of the upload (which also keeps memory flat).
    """
    pushed = {"rows": 0}

    def emit(batch: list[BusinessRecord]) -> None:
        payload = [r.to_dict() if hasattr(r, "to_dict") else r for r in batch]
        if not payload:
            return
        last_error: Optional[Exception] = None
        for attempt in range(1, 4):
            try:
                fut = asyncio.run_coroutine_threadsafe(Actor.push_data(payload), loop)
                fut.result(timeout=300)
                pushed["rows"] += len(payload)
                logger.info(
                    "Pushed %d listings to the dataset (total %d)",
                    len(payload),
                    pushed["rows"],
                )
                return
            except Exception as exc:  # noqa: BLE001 - retry, then carry on
                last_error = exc
                logger.warning(
                    "Dataset push attempt %d/3 failed (%d rows): %s",
                    attempt,
                    len(payload),
                    exc,
                )
                time.sleep(2 ** attempt)
        raise RuntimeError(f"could not push {len(payload)} listings: {last_error}")

    return emit


async def main() -> None:
    """Actor execution entry point."""
    async with Actor:
        actor_input = await Actor.get_input() or {}
        Actor.log.info(f"Received Actor input: {actor_input}")

        # Set up proxy if configured
        proxy_input = actor_input.get("proxy_configuration")
        if proxy_input and (proxy_input.get("useApifyProxy") or proxy_input.get("proxyUrls")):
            proxy_config = await Actor.create_proxy_configuration(actor_proxy_input=proxy_input)
            if proxy_config:
                proxy_url = await proxy_config.new_url()
                if proxy_url:
                    os.environ["PLAYWRIGHT_PROXY"] = proxy_url
                    Actor.log.info("Configured proxy for browser requests.")
        else:
            os.environ.pop("PLAYWRIGHT_PROXY", None)
            Actor.log.info("Running with direct connection (no proxy).")

        # Default use_playwright_source to True unless explicitly disabled (or if mock testing)
        if "use_playwright_source" not in actor_input:
            actor_input["use_playwright_source"] = os.getenv("USE_PLAYWRIGHT_SOURCE", "1") == "1"

        Actor.log.info("Starting Google Maps extraction...")

        loop = asyncio.get_running_loop()
        cleaned_records, csv_path, xlsx_path, notes = await asyncio.to_thread(
            _sync_scrape_pipeline, actor_input, _dataset_emitter(loop)
        )

        if notes:
            Actor.log.warning(f"Pipeline notes: {'; '.join(notes)}")

        # Records were streamed to the dataset as they were scraped; only warn
        # when nothing at all was collected (an empty push would be a no-op).
        if cleaned_records:
            Actor.log.info(f"Successfully pushed {len(cleaned_records)} listings to the Apify Dataset.")
        else:
            Actor.log.warning("No listings found matching the specified query and filters.")

        # Push files to Key-Value Store: combined CSV (primary) + Excel.
        if csv_path and Path(csv_path).exists():
            with open(csv_path, "rb") as f:
                csv_bytes = f.read()
            await Actor.set_value(
                key="OUTPUT.csv",
                value=csv_bytes,
                content_type="text/csv",
            )
            Actor.log.info(f"Combined CSV saved to Key-Value Store as 'OUTPUT.csv'.")
        if xlsx_path and Path(xlsx_path).exists():
            with open(xlsx_path, "rb") as f:
                xlsx_bytes = f.read()
            await Actor.set_value(
                key="OUTPUT.xlsx",
                value=xlsx_bytes,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            Actor.log.info(f"Formatted Excel workbook saved to Key-Value Store as 'OUTPUT.xlsx'.")

        await Actor.set_status_message(f"Scraped {len(cleaned_records)} listings successfully.")


if __name__ == "__main__":
    asyncio.run(main())
