# CARRY FORWARD PROMPT: MINDTRIP.AI CLONE IMPLEMENTATION

You are tasked with executing the implementation of the Mindtrip.ai clone following the approved architecture plan.

### Project Context
- **Workspace**: `D:\Velocity Projects\MindTrip clone`
- **Goal**: Full-stack clone of Mindtrip.ai (Editorial luxury AI travel assistant).
- **Core Features**:
  1. Split-screen Chat Concierge + Interactive Map (Leaflet / MapLibre GL with Carto tiles).
  2. Structured Day-by-Day Visual Itineraries with transit time calculations.
  3. Stays & Flights Hub with filterable cards.
  4. Scraper Pipeline: Adapter for user's Google Maps and Google Flights scrapers, Hotel Web Scraper, Mindtrip Reference Asset Cloner, and Free APIs (Nominatim, Wikivoyage, OSRM, Unsplash).
  5. Flexible LLM Engine (xAI Grok / OpenAI / Gemini / Ollama).
  6. 100% Free APIs & data sources (Zero paid key requirement).

---

### Execution Phases

#### Phase 1: Mindtrip Reference Asset Cloner & Scraper Suite
1. Create `scrapers/cloner/mindtrip_scraper.py`:
   - Fetch mindtrip.ai stylesheets, brand colors, SVG icons, and hero assets into `data/reference/`.
   - Extract sample destination data and itinerary fixtures into `data/fixtures/sample_trips.json`.
2. Create `scrapers/adapters/`:
   - `base_adapter.py`: Standard Pydantic models (`PlaceRecord`, `HotelRecord`, `FlightRecord`, `TripRecord`).
   - `google_maps_adapter.py`: Parser to ingest user's Google Maps scraper output.
   - `google_flights_adapter.py`: Parser to ingest user's Google Flights scraper output.
3. Create `scrapers/hotel_scraper.py`: Playwright/BS4 scraper for hotel cards, prices, and amenities.
4. Create `scrapers/free_apis.py`: Nominatim OSM geocoding, Wikivoyage descriptions, and OSRM transit calculation.

#### Phase 2: Backend API & LLM Agent Engine (FastAPI)
1. Initialize `backend/` with FastAPI, Pydantic, and SQLite database (`backend/database/`).
2. Implement `services/llm_service.py` supporting Grok (`api.x.ai/v1`), OpenAI, Gemini, and local models.
3. Implement `agent/travel_agent.py` with Mindtrip persona and tool calling for:
   - `search_places`, `search_hotels`, `search_flights`, `build_itinerary`, `calculate_route`.
4. Implement REST & SSE streaming endpoints in `routers/chat.py`, `trips.py`, `hotels.py`, `flights.py`.

#### Phase 3: Frontend Setup & Mindtrip Design System (Next.js 14)
1. Initialize Next.js 14 App Router project in `frontend/` with TypeScript and Tailwind CSS.
2. Port Mindtrip's exact design tokens (colors, font pairing: Inter + display font, rounded-2xl cards, carousel containers, blur glassmorphism) into `globals.css` and `tailwind.config.ts`.
3. Create global layout, navigation header, and footer matching Mindtrip.ai.

#### Phase 4: Core Pages & Interactive Components
1. **Landing Page (`/`)**: Hero carousel, prompt omnibox, curated trip collections, features showcase.
2. **Chat & Map Split Screen (`/chat`)**:
   - Dual-pane layout (Chat on left, MapLibre on right).
   - Streaming chat with interactive place cards and hotel quote cards.
   - Synchronized map with colored category pins and popups.
3. **Day-by-Day Itinerary Planner (`/trip/[id]`)**:
   - Chronological morning/afternoon/evening timeline.
   - Transit calculation badges ("20 min walk", "15 min drive via OSRM").
4. **Stays (`/stays`) & Flights (`/flights`) Hubs**:
   - Discovery search filters, card galleries, and details modals.

#### Phase 5: Verification & Integration
1. Plug user's scraper outputs into `scrapers/user_scrapers/`.
2. Run test suites and end-to-end user flows.
3. Provide walkthrough documentation.

Please proceed with Phase 1 upon confirmation.
