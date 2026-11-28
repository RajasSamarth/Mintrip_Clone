# Mindtrip.ai Clone

Full-stack clone of [Mindtrip.ai](https://mindtrip.ai) — an editorial-luxury AI travel
assistant and visual itinerary planner.

## Stack

| Layer | Tech |
|-------|------|
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind CSS v4, MapLibre GL |
| Backend | FastAPI, SQLModel, SQLite |
| LLM | xAI Grok / OpenAI / Gemini / OpenRouter / Ollama / local demo planner |
| Data | Nominatim, Overpass, Wikivoyage, OSRM, Unsplash + curated fixtures |
| Scrapers | Python adapters for Google Maps / Google Flights, hotel scraper, Mindtrip asset cloner |

## Quick start

### 1. Backend (FastAPI)

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
cp ../.env.example .env       # edit keys if you have them
python -m uvicorn main:app --reload --port 8000
```

The backend seeds curated fixtures (Kyoto, Rome, Swiss Alps, Tokyo, Paris, Lisbon)
and starts on `http://localhost:8000`. API docs at `/docs`.

### 2. Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

## Architecture

```
scrapers/
  cloner/mindtrip_scraper.py   # Mindtrip.ai asset & design-token cloner
  adapters/
    base_adapter.py            # Pydantic schemas (PlaceRecord, HotelRecord, FlightRecord, TripRecord)
    google_maps_adapter.py     # Normalize your Google Maps scraper output
    google_flights_adapter.py  # Normalize your Google Flights scraper output
  hotel_scraper.py             # Playwright/BS4 hotel scraper
  free_apis.py                 # Nominatim, Wikivoyage, OSRM, Unsplash (free)
  user_scrapers/               # Drop your existing scraper JSON/CSV here

backend/
  main.py                      # FastAPI app + CORS + lifespan seeding
  config.py                    # Pydantic settings (.env driven)
  database/{models,db,seed}.py # SQLModel SQLite schema + seeding
  agent/
    travel_agent.py            # Mindtrip concierge agent (live LLM + local planner)
    tools.py                   # OpenAI-compatible tool definitions + dispatcher
    prompts.py                 # Mindtrip persona system prompt
    planner.py                 # Deterministic itinerary synthesis (zero-key fallback)
  services/
    llm_service.py             # Provider-agnostic LLM client
    routing_service.py         # OSRM routing with offline fallback
    data_service.py            # CRUD for trips, places, hotels, flights, chat
  routers/
    chat.py                    # /api/chat/message (REST) + /api/chat/stream (SSE)
    trips.py, hotels.py, flights.py, places.py

frontend/
  src/app/
    page.tsx                   # Landing hero + prompt omnibox
    chat/page.tsx              # Split-screen concierge + map
    trip/[id]/page.tsx         # Day-by-day visual itinerary
    trips/page.tsx             # Curated & saved journeys hub
    inspiration/page.tsx       # Curated editorial collections & guides
    stays/page.tsx             # Hotel discovery hub
    flights/page.tsx           # Flight search hub
  components/
    chat/{MessageBubble,PlaceCard}.tsx
    map/InteractiveMap.tsx     # MapLibre GL + Carto Positron
    itinerary/DayTimeline.tsx
    navigation/{Header,Logo,Footer}.tsx
```

## Key behaviors

- **Anonymous guest sessions**: `POST /api/chat/session` creates a guest session; no login required to plan.
- **Demo mode**: With no LLM key, the deterministic local planner builds full itineraries from curated place data. Add `XAI_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, or `OPENROUTER_API_KEY` to `.env` for live conversational reasoning.
- **Free infrastructure**: Map tiles from CartoDB Positron, geocoding from Nominatim, routing from OSRM, destination copy from Wikivoyage, images from Unsplash CDN.
- **Scraper ingestion**: Drop your Google Maps / Google Flights JSON or CSV into `scrapers/user_scrapers/`; the adapters normalize them into the standard schema on backend startup.

## Testing

```bash
# Backend
cd backend
pip install pytest pytest-asyncio
pytest ../backend/tests      # 20 tests, all pass

# Frontend
cd frontend
npm run build                # zero TypeScript / bundling errors
```

## Verification

1. Open `http://localhost:3000/chat`.
2. Submit: *"Plan a 3-day foodie and culture trip to Kyoto with boutique hotels"*.
3. Confirm streaming conversational stream and simultaneous map pins.
4. Open `/trip/:id` for the day-by-day timeline with transit durations.
5. Browse `/stays` and `/flights` for discovery cards.
