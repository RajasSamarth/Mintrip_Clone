# Google Maps Business Extractor

A FastAPI service that searches live Google Maps business listings via
Playwright browser automation and exports the results to an Excel file.
It ships with a built-in web frontend — open http://127.0.0.1:8000/ after
starting the server.

## Requirements

- Python 3.10+
- Windows / PowerShell (commands below)

## Setup (PowerShell)

```powershell
cd "D:\Velocity Projects\Google Scraper\google-maps-business-extractor"
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Copy `.env` and review the values:

```text
API_KEY=change-me-in-development
HOST=127.0.0.1
PORT=8000
FILE_RETENTION_HOURS=24
CACHE_TTL_HOURS=24
RATE_LIMIT_PER_MINUTE=30
MAX_JOBS=10
MAX_JOBS_PER_HOUR=10
```

## Run the API

```powershell
.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc
- Web frontend: http://127.0.0.1:8000/ (search, preview all results, download)

> **All results:** leave `max_results` empty (or omit it) to collect every
> listing Google Maps returns for the query — the scraper scrolls the full
> results feed and enriches each listing. Expect large searches to take a
> few minutes.
>
> **`max_results` is a budget, not a trim.** A `max_results=100` job stops
> scraping as soon as 100 *unique* listings are collected instead of sweeping
> the whole city and throwing the rest away. That is the difference between a
> 2-minute run and a multi-hour one.

## Authentication

All endpoints require the header:

```text
X-API-Key: <value from .env API_KEY>
```

## Endpoints

### 1. Start a search

`POST /api/v1/search`

```json
{
  "query": "dental clinic",
  "location": "Dharampeth, Nagpur",
  "radius_km": 3,
  "max_results": 200,
  "min_rating": 4.0
}
```

Response:

```json
{
  "job_id": "…",
  "status": "queued",
  "status_url": "/api/v1/search/…"
}
```

### 2. Check status

`GET /api/v1/search/{job_id}`

Response (done):

```json
{
  "job_id": "…",
  "status": "done",
  "total_results": 87,
  "download_url": "/api/v1/search/…/download"
}
```

Statuses: `queued`, `running`, `done`, `failed`.

### 3. Preview results

`GET /api/v1/search/{job_id}/results`

Returns the cleaned records as JSON (used by the frontend preview table).

### 4. Download Excel

`GET /api/v1/search/{job_id}/download`

Returns the generated `.xlsx` file.

### 5. List a city's localities

`GET /api/v1/localities?city=Nagpur`

Resolves the city's locality list from
[mapsofindia.com](https://www.mapsofindia.com/nagpur/localities/)
(`https://www.mapsofindia.com/<city>/localities/`), falling back to
OpenStreetMap when the site has no page for that city.

```json
{
  "city": "Nagpur",
  "source": "mapsofindia",
  "total": 51,
  "localities": ["Abhyankar Nagar", "Ajni", "Amravati Road", "..."]
}
```

`source` is `mapsofindia` or `openstreetmap`. Add `&limit=20` to cap the list.

### 6. Whole-city sweep (city → localities → one combined CSV)

`POST /api/v1/city-search`

The end-to-end flow: give it a **city**, it resolves every locality, scrapes
**one Google Maps feed per locality**, merges + dedupes, and writes a single
combined CSV. Each row carries a `Search Locality` column so you can see which
locality a listing came from.

```json
{
  "city": "Nagpur",
  "query": "restaurant",
  "max_results": null,
  "min_rating": 4.0,
  "enrich_details": true,
  "max_localities": null
}
```

Response is the usual job envelope — poll `GET /api/v1/search/{job_id}` and
download `GET /api/v1/search/{job_id}/download`. Filename pattern:
`restaurant_nagpur_2026-10-28.csv`.

Notes:

- `query` defaults to `restaurant`; `extra_queries` adds variants per locality.
- `max_results` is a total budget for the whole city; leave it out for complete
  coverage (a metro can have hundreds of localities, so a full sweep takes a
  while).
- `max_localities` caps how many localities are swept — handy for a quick test.
- If the city has no locality list on either source the call returns `404`; use
  `/api/v1/search` with `auto_areas: true` instead.
- The same locality source is used by `/api/v1/search` `auto_areas` discovery,
  so a normal search now sweeps mapsofindia localities without any typing.

## Excel output

Workbook contains two sheets:

- `Businesses` with columns:
  `Sr. No., Business Name, Category, Full Address, Area / Locality, City / Pincode,
   Phone Number, Website, Rating, Total Reviews, Opening Hours, Business Status,
   Latitude, Longitude, Google Maps Link, Place ID, Search Locality, Detail Status`
  (`Search Locality` = the locality feed a row came from; identical for the
  combined CSV.)
- `Search Info` with `Search query, Location, Search radius, Search timestamp,
   Total result count`.

Filename pattern: `dental_clinic_dharampeth_nagpur_2026-10-14.xlsx`.

## Data source

The project is structured so the collector depends only on the
`BusinessDataSource` interface. Live Google Maps extraction is implemented in
`app/adapters/playwright_source.py` (Playwright/Chromium, enabled with
`USE_PLAYWRIGHT_SOURCE=1` — only use with explicit permission to automate
Google Maps). `SyntheticDataSource` (in `app/adapters/approved_source.py`)
remains available for development and testing with `USE_PLAYWRIGHT_SOURCE=0`.

## City-wide sweeps, timeouts and speed

Google caps a single Maps feed at roughly 120 listings, so full-city coverage
means scraping one feed per locality and merging them. The shared fan-out lives
in `app/services/pipeline.py` and works like this:

1. **Locality discovery** (`app/services/localities.py` + `areas.py`) tries
   [mapsofindia.com](https://www.mapsofindia.com/) first — the curated
   `/<city>/localities/` list this project is built around. If that city has no
   page there, it resolves the bounding box with Nominatim and asks the
   Overpass mirrors **concurrently** for suburb / neighbourhood names. If both
   are unavailable it falls back to a coordinate grid over the bounding box, so
   coverage does not depend on any single site.
2. **Fan-out**: every query x location feed is scraped and deduped on the fly.
   With a `max_results` budget the areas are walked sequentially and the run
   stops the moment the budget is met (with a small slack per area to absorb
   cross-area duplicates). Without a budget the areas are scraped concurrently
   (`LOCATION_CONCURRENCY`).
3. **Streaming**: the Actor pushes each batch of new listings to the Apify
   dataset as it is scraped, so a run killed by the platform timeout still
   leaves everything collected so far in the dataset.

### Tuning environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `AREAS_TIMEOUT` | `40` | Client timeout (s) for area discovery. Must stay above the Overpass server timeout. |
| `AREA_GRID_CELLS` | `3` | `N x N` coordinate grid used when OSM has no area names. |
| `LOCATION_CONCURRENCY` | `2` | Areas scraped in parallel for uncapped ("give me everything") runs. |
| `MAX_STALE_AREAS` | `5` | Stop a budgeted run after this many consecutive areas add no new listings. |
| `PLAYWRIGHT_CONCURRENCY` | `4` | Detail pages opened in parallel per area. |
| `PLAYWRIGHT_SCROLL_STABLE` | `4` | Consecutive non-growing scrolls before a feed is considered finished. |
| `MAX_RUNTIME_MINUTES` | `720` | Optional hard stop (720 min = 12 hours); `0` = no limit (Apify's own timeout applies). |
| `PLAYWRIGHT_PAUSE_SEC` / `PLAYWRIGHT_SCROLL_DELAY` / `PLAYWRIGHT_DETAIL_PAUSE` | `0.6` / `0.6` / `0.4` | Polite pauses between actions. |

`JOB_WORKERS x PLAYWRIGHT_CONCURRENCY` is clamped to 14 parallel pages to keep
RAM and Google's rate limiting in check.

### Why not Scrapy?

Scrapy is an HTTP/HTML crawler. Google Maps is a client-side rendered app: the
search results arrive through XHR/JSON after the page boots, so plain Scrapy
sees an empty shell. `scrapy-playwright` would still drive the same Chromium,
just behind another framework — the render cost (and therefore the runtime) is
unchanged, plus extra overhead. The real speed levers are the ones above:
scrape fewer areas (budget-aware fan-out), parallelise areas, and skip the
per-listing detail pages with `enrich_details=false`.

If you need a fundamentally faster path, it would be a different adapter that
talks to Google's internal `tbm=map` JSON endpoint (plain HTTP, no browser).
That endpoint is undocumented and unstable, so it is not used here.

## Testing

```powershell
.venv\Scripts\Activate.ps1
pytest
```

## Deploying to Apify via GitHub & CI/CD

This project is configured to run as an **Apify Actor** with full GitHub Actions CI/CD automation.

### Apify Actor Features
- **Apify Dataset**: All scraped and cleaned business records are pushed directly into Apify's Default Dataset (downloadable as JSON, CSV, XML, Excel). Rows are pushed **batch by batch while scraping**, so a run that hits the platform timeout still keeps its data.
- **Key-Value Store**: Generates a formatted multi-sheet Excel file (`OUTPUT.xlsx`) plus `OUTPUT.csv` and saves them directly to the run's Key-Value store.
- **Proxy Support**: Supports Apify Residential / Datacenter Proxies and custom proxies via the Apify UI input schema or `PLAYWRIGHT_PROXY` / `HTTP_PROXY`.
- **Apify Console UI**: Fully defined input schema in `.actor/input_schema.json` with user-friendly fields for search queries, locations, radius, ratings, and multi-area sweeps.

### Setup GitHub CI/CD Deployment

Whenever you push to the `main` branch, the workflow [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) runs tests and deploys the Actor to Apify automatically.

#### 1. Retrieve your Apify API Token
1. Log in to [Apify Console](https://console.apify.com/).
2. Navigate to **Settings** -> [**Integrations**](https://console.apify.com/settings/integrations).
3. Copy your personal **API Token**.

#### 2. Configure GitHub Secrets
1. In your GitHub repository, open **Settings** -> **Secrets and variables** -> **Actions**.
2. Click **New repository secret**.
3. Name: `APIFY_TOKEN`
4. Value: `<your-apify-token>`
5. *(Optional)* Name: `APIFY_ACTOR_ID` (e.g. `your-username/google-maps-business-extractor` if you want to deploy to a specific existing Actor). If omitted, Apify CLI uses the name defined in `.actor/actor.json`.

#### 3. Trigger Deployment
- **Automatic:** Push any commit to the `main` branch.
  ```bash
  git add .
  git commit -m "Configure Apify Actor and CI/CD"
  git push origin main
  ```
- **Manual:** Go to **Actions** in your GitHub repository, select **Deploy Actor to Apify**, and click **Run workflow**.

### Alternative: Native Apify GitHub Integration
You can also connect GitHub directly in Apify:
1. In [Apify Console](https://console.apify.com/actors), click **Create new** -> **Web & Git**.
2. Select **GitHub repository** and authorize your repo.
3. Apify will automatically rebuild on every commit to `main`.

### Testing the Actor Locally

You can test the Apify Actor locally using python or the Apify CLI:

```powershell
.venv\Scripts\Activate.ps1

# Run with synthetic test source (no browser launch):
$env:USE_PLAYWRIGHT_SOURCE="0"
python -m app.actor

# Run with live Playwright scraper:
$env:USE_PLAYWRIGHT_SOURCE="1"
python -m app.actor
```

Local results will be saved in `storage/datasets/default` and `storage/key_value_stores/default/OUTPUT.xlsx`.

## Notes / limitations

- Job state and cache in the FastAPI server are in-memory and single-process.
- When running on Apify, state and storage are persisted natively by the Apify platform.