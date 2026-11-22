# 🧭 MINDTRIP CLONE — PROJECT HANDOVER PROMPT

> **How to use this document**: When initiating a new session or handing over this project to a new developer or AI assistant, provide this prompt in full. It encapsulates the system architecture, business rules, design invariants, database workflows, live scraper integrations, and testing protocols.

---

## 1. Project Mission & Identity
You are continuing development on **Mindtrip Clone**, a full-stack, editorial luxury AI travel assistant inspired by Mindtrip.ai.
- **Core Mission**: Seamlessly combine conversational AI travel planning with an interactive MapLibre GL split-screen map, personalized day-by-day itineraries, live flight search, curated boutique hotel stays, and real-time place scraping via Playwright.
- **Workspace Root**: `D:\Velocity Projects\MindTrip clone`
- **External Scraper Dependency**: `D:\Velocity Projects\Google Scraper\Google-maps-scrapper`

---

## 2. Technology Stack & Directory Structure

### Stack Overview
- **Frontend**: Next.js 14 (App Router), React 18, TypeScript, Tailwind CSS, Lucide React, MapLibre GL with Carto Voyager vector/raster basemaps.
- **Backend**: FastAPI (Python 3.11+), SQLModel / SQLAlchemy, SQLite (`data/mindtrip.db`), Pydantic v2, SSE streaming.
- **Agent & LLM**: Modular `LLMService` (Groq `openai/gpt-oss-120b`, OpenAI, Gemini, Grok, or local Ollama) with fallback support.
- **Cloud & Dual Storage**: Supabase integration (`scrapers/supabase_client.py`) for dual-writing places and stays.
- **Scraper Bridge**: `scrapers/google_maps_adapter.py` executing the user's Playwright scraper out-of-process.

### Directory Layout
```text
MindTrip clone/
├── backend/
│   ├── .venv/                      # Python virtual environment
│   ├── agent/
│   │   ├── planner.py              # Itinerary synthesis, slotting, deduplication & distance calculation
│   │   ├── prompts.py              # System prompts & concierge guidelines
│   │   └── travel_agent.py         # Conversational dispatcher, intent routing & concierge synthesis
│   ├── database/
│   │   ├── connection.py           # SQLModel engine & session management
│   │   ├── famous_spots.py         # Curated seed spots with verified, unique landmark photography
│   │   ├── models.py               # SQLModel schemas (Trip, Day, Stop, Place, Hotel, Flight, ChatSession)
│   │   └── seed_data.py            # Initial seed loader
│   ├── routers/
│   │   ├── chat.py                 # Chat endpoints & streaming SSE (/api/chat/*)
│   │   ├── flights.py              # Flight search & recommendation routes (/api/flights/*)
│   │   ├── hotels.py               # Hotel booking & detail routes (/api/hotels/*)
│   │   └── trips.py                # Trip retrieval, update & deletion routes (/api/trips/*)
│   ├── services/
│   │   ├── data_service.py         # Database CRUD layer
│   │   ├── flight_service.py       # Live flight inventory generation & filtering
│   │   ├── llm_service.py          # Groq / OpenAI / Gemini provider client
│   │   └── routing_service.py      # OSRM / Haversine transit calculation
│   └── tests/                      # Unit tests
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── chat/page.tsx       # Split-screen Chat Concierge + MapLibre Map
│   │   │   ├── flights/page.tsx    # Flights search and booking cards
│   │   │   ├── inspiration/page.tsx# Editorial destination stories
│   │   │   ├── stays/page.tsx      # Stays & boutique hotels gallery
│   │   │   ├── trip/[id]/page.tsx  # Visual day-by-day itinerary view
│   │   │   ├── trips/page.tsx      # User trip archive
│   │   │   └── page.tsx            # Landing page with hero carousel & intake omnibox
│   │   ├── components/
│   │   │   ├── chat/               # MessageBubble, PlaceCard, HotelCard, FlightCard, TripIntakeCard
│   │   │   ├── itinerary/          # DayTimeline, StopCard, TransitBadge
│   │   │   ├── map/                # InteractiveMap (MapLibre GL, colored pins, popups, route lines)
│   │   │   └── navigation/         # Header, Footer
│   │   └── lib/api.ts              # Fetch client connecting to backend
├── scrapers/
│   ├── google_maps_adapter.py      # Subprocess bridge to Playwright Google Maps Scraper
│   └── supabase_client.py          # Supabase REST client for cloud data backup
├── data/
│   └── mindtrip.db                 # SQLite database file
├── run_backend.py                  # Backend startup script (uvicorn on port 8000)
├── test_all_requirements.py        # E2E test: off-topic guardrail, flights, spot updates
├── test_new_user_requests.py       # E2E test: car rental intent, intake questions without assumptions
├── test_saturday_in_trip_condition.py # E2E test: conditional Saturday detection & schedule protection
├── test_user_reported_issues.py    # E2E test: deduplication, unique photos & concierge reasoning
└── .env                            # Environment variables (Groq key, Supabase keys, etc.)
```

---

## 3. Critical Non-Negotiables & Invariants

1. **EXTERNAL SCRAPER DIRECTORY IMMUTABILITY**:
   - The directory `D:\Velocity Projects\Google Scraper\Google-maps-scrapper` **MUST NEVER BE MODIFIED, MOVED, OR RE-INITIALIZED**. It has its own dedicated `.venv` (`env`).
   - The adapter [`scrapers/google_maps_adapter.py`](file:///d:/Velocity%20Projects/MindTrip%20clone/scrapers/google_maps_adapter.py) calls it strictly via external subprocess or headless execution and parses its output records into MindTrip's `Place` model.
2. **NO ASSUMED DATES OR TRAVELERS (INTAKE MODE)**:
   - When a user submits an underspecified travel request (e.g., *"quiet days in the Swiss Alps"*), the assistant **must not hallucinate** default dates or party sizes. It must trigger intake mode and ask:
     1. Target travel dates / duration
     2. Number of travelers (adults/children)
     3. Departure city
3. **STRICT SCHEDULE & CALENDAR INTEGRITY**:
   - When a user asks conditional date queries (e.g., *"is there any Saturday in my trip? If yes, add X"*), the assistant must check the actual days in the itinerary.
   - If the requested day does not exist in the schedule (e.g. a Mon–Wed trip has no Saturday), the assistant **must decline politely** and ask whether the user wants to add it to an existing day or extend the trip. It **must never mutate the database with hallucinated extra days**.
4. **PER-DAY & TRIP-WIDE STOP DEDUPLICATION**:
   - `_slot_plan` in [`backend/agent/planner.py`](file:///d:/Velocity%20Projects/MindTrip%20clone/backend/agent/planner.py) tracks `day_used` and `trip_used`.
   - The same landmark or venue must never be scheduled more than once on the same day or across the itinerary.
   - The category matcher maps broad categories (`nature`, `heritage`, `culture`, `viewpoint`, `attraction`) into attraction slots so spots are never dropped.
5. **100% UNIQUE LANDMARK PHOTOGRAPHY**:
   - All seed places across Mumbai, Delhi, Jaipur, Kyoto, Paris, Pune, Dublin, Dubai, New York, and Swiss Alps have verified, unique Unsplash photo URLs in [`backend/database/famous_spots.py`](file:///d:/Velocity%20Projects/MindTrip%20clone/backend/database/famous_spots.py).
   - Never assign identical photo URLs to different landmarks in the same destination.
6. **AUTHENTIC CONCIERGE REASONING (NO ROBOTIC TEMPLATES)**:
   - When a user asks about cuisines, nightlife, hotels, or specific amenities, `_compose_concierge_response` in [`backend/agent/travel_agent.py`](file:///d:/Velocity%20Projects/MindTrip%20clone/backend/agent/travel_agent.py) synthesizes warm, tailored travel narrative via the live LLM before returning interactive cards and map pins.
   - If Groq hits API rate limits, it falls back gracefully to a clean, formatted response without crashing.
7. **OFF-TOPIC CONVERSATIONAL GUARDRAIL**:
   - Queries unrelated to travel, geography, hospitality, flights, or itineraries (e.g. *"who won IPL last year"*) must be politely declined and steered back to travel planning.

---

## 4. Setup & Running Instructions

### Backend
```powershell
# In D:\Velocity Projects\MindTrip clone
& "backend\.venv\Scripts\python.exe" run_backend.py
```
- Runs FastAPI on `http://127.0.0.1:8000` with Swagger docs at `http://127.0.0.1:8000/docs`.

### Frontend
```powershell
# In D:\Velocity Projects\MindTrip clone\frontend
npm run dev
```
- Runs Next.js on `http://localhost:3000`.

### Database Sync & Seeding
To sync SQLite with updated seed spots from `famous_spots.py`:
```powershell
& "backend\.venv\Scripts\python.exe" -c "from sqlmodel import Session, create_engine; from backend.agent.planner import _ensure_generic_places; engine = create_engine('sqlite:///data/mindtrip.db'); session = Session(engine); _ensure_generic_places(session, 'mumbai'); print('Synced!')"
```

---

## 5. Automated Regression Test Suites

Always run tests before and after making changes. **All must pass 100%**:

```powershell
# 1. Deduplication, unique landmark photos, and concierge reasoning
& "backend\.venv\Scripts\python.exe" test_user_reported_issues.py

# 2. Off-topic guardrail, flight recommendations, and spot database persistence
& "backend\.venv\Scripts\python.exe" test_all_requirements.py

# 3. Conditional Saturday detection (no hallucinated days)
& "backend\.venv\Scripts\python.exe" test_saturday_in_trip_condition.py

# 4. Car rental intent & intake mode (no assumed dates/travelers)
& "backend\.venv\Scripts\python.exe" test_new_user_requests.py

# 5. Live Google Maps cuisine and amenities search
& "backend\.venv\Scripts\python.exe" test_google_maps_cuisine_amenities.py
```

*(Note for Windows sandbox execution: Local socket tests connecting to `127.0.0.1:8000` should be run with sandbox bypass or within the same session).*

---

## 6. Architecture & Data Flow Reference

```mermaid
flowchart TD
    User([User Web Client / Chat]) <--> NextJS[Next.js 14 Frontend - localhost:3000]
    NextJS <--> API[FastAPI Backend - 127.0.0.1:8000]
    
    subgraph Agent & Dispatcher
        API <--> TravelAgent[backend/agent/travel_agent.py]
        TravelAgent <--> IntentClassifier{Intent Type}
        IntentClassifier -->|Trip Planning| Planner[backend/agent/planner.py]
        IntentClassifier -->|Off-Topic| Guardrail[Concierge Guardrail]
        IntentClassifier -->|Live Scraper / Amenities| GMapsAdapter[scrapers/google_maps_adapter.py]
        IntentClassifier -->|Flights / Stays| ServiceLayer[Flight & Data Services]
    end
    
    subgraph Storage
        Planner <--> SQLite[(data/mindtrip.db)]
        GMapsAdapter -->|Dual Write| SQLite
        GMapsAdapter -->|Dual Write| Supabase[(Supabase Cloud)]
        FamousSpots[backend/database/famous_spots.py] -->|Upsert Sync| SQLite
    end
    
    subgraph External Scraper (Read-Only)
        GMapsAdapter -.->|Subprocess Call| ScraperDir[Google-maps-scrapper / Playwright]
    end
```

---

## 7. Current Project State & Next Steps

### Completed & Stable:
- ✅ Split-screen MapLibre GL map synchronized with chat pins and itinerary stops.
- ✅ Live Playwright Google Maps scraper bridge returning live places, salons, cafes, and car rentals.
- ✅ Supabase dual-storage integration.
- ✅ Conversational AI Concierge reasoning via LLM with rate-limit fallbacks.
- ✅ Strict deduplication and landmark photo distinction across all destinations.
- ✅ Date integrity protections against hallucinating days.
- ✅ Full suite of passing automated regression tests.

### Recommended Next Objectives:
1. **Interactive Day Drag-and-Drop**: Add drag-and-drop stop re-ordering on `/trip/[id]` that recalculates OSRM transit times dynamically.
2. **Export to Calendar / PDF**: Generate downloadable `.ics` calendar events or printable PDF travel guides for trips.
3. **Multi-City Itinerary Support**: Enable chaining multi-destination trips (e.g., Zurich -> Interlaken -> Zermatt).
4. **Enhanced User Authentication**: Integrate Supabase Auth for persistent multi-user trip saving.
