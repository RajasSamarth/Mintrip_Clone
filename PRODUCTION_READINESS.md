# Mindtrip Clone — Production Readiness Artifact

**Status:** Implementation Ready  
**Target:** Make the AI travel concierge chatbot production-ready  
**Scope:** Backend (FastAPI + SQLModel/SQLite), Frontend (Next.js App Router), Agent Layer (TravelAgent + LLMService)

---

## 1. Executive Summary

The Mindtrip Clone is a functional AI travel concierge with itinerary synthesis, Google Maps integration, flight scraping, and SSE streaming. However, it is **not production-ready** in its current state. This artifact identifies the gaps and provides concrete, implementable fixes across:

| Area | Current State | Production Gap |
|------|--------------|----------------|
| **Chat History** | Stored in DB but **never fed back** to the agent in the local/demo path; only the last 8 messages are passed to the live LLM with no summarization | The chatbot has no memory of prior conversation turns outside the live LLM path |
| **Input Validation** | Only `min_length=1, max_length=4000` on the message field | No sanitization, no PII detection, no prompt-injection guards, no rate limiting |
| **Error Handling** | Bare `try/except` that returns 502 or SSE error event | No circuit breaker, no retry with backoff, no degraded-mode responses |
| **LLM Resilience** | Falls back to local planner on LLM error, but the local path ignores history entirely | No timeout tuning, no provider fallback chain, no token budget management |
| **Security** | CORS allows localhost only (good), but no auth, no input sanitization, no PII redaction | Vulnerable to prompt injection, PII leakage, and scraping abuse |
| **Observability** | Basic `logging.basicConfig`, one `backend.log` file | No structured logging, no request IDs, no metrics, no health endpoint depth |
| **Frontend Resilience** | SSE stream falls back to polling POST on failure | No retry with backoff, no offline queue, no reconnect with backoff |

---

## 2. Implementation Plan

### 2.1 New Files to Create

| File | Purpose |
|------|---------|
| `backend/services/production_middleware.py` | Rate limiting, input sanitization, PII redaction, request ID injection, structured error responses |
| `backend/services/chat_context.py` | Enhanced history retrieval, conversation summarization, context window management |
| `backend/config/production.py` | Production configuration presets (CORS, timeouts, rate limits, feature flags) |
| `PRODUCTION_READINESS.md` | This document |

### 2.2 Files to Modify

| File | Changes |
|------|---------|
| `backend/routers/chat.py` | Add middleware dependencies, request ID, rate limiting, validation, structured error responses |
| `backend/agent/travel_agent.py` | Inject chat history into `_local_response`, add summarization hook, improve `_live_response` context handling |
| `backend/services/llm_service.py` | Add retry with exponential backoff, provider fallback chain, timeout configuration per provider |
| `backend/config.py` | Add production settings fields (rate limits, max context messages, PII patterns, etc.) |
| `frontend/src/lib/api.ts` | Add retry with backoff, request timeout, offline message queue |

---

## 3. Code Implementation

---

### 3.1 `backend/services/production_middleware.py`

```python
"""Production middleware: rate limiting, input sanitization, PII redaction, request IDs."""

from __future__ import annotations

import re
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse

from backend.config import get_settings

settings = get_settings()


# --------------------------------------------------------------------------- #
# Request ID middleware
# --------------------------------------------------------------------------- #

async def request_id_middleware(request: Request, call_next):
    """Inject a unique request ID into every request for traceability."""
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    request.state.request_id = request_id
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time-Ms"] = f"{duration_ms:.2f}"
    return response


# --------------------------------------------------------------------------- #
# Rate limiting (in-memory, per session + per IP)
# --------------------------------------------------------------------------- #

class RateLimiter:
    """Token-bucket rate limiter keyed by session_id and client IP."""

    def __init__(self, requests_per_minute: int = 30, burst: int = 5):
        self.rpm = requests_per_minute
        self.burst = burst
        self._buckets: dict[str, deque[float]] = defaultdict(deque)

    def _now(self) -> float:
        return time.time()

    def _prune(self, key: str, window: float = 60.0) -> None:
        now = self._now()
        bucket = self._buckets[key]
        while bucket and bucket[0] < now - window:
            bucket.popleft()

    def allow(self, key: str) -> tuple[bool, int]:
        """Returns (allowed, retry_after_seconds)."""
        self._prune(key)
        bucket = self._buckets[key]
        if len(bucket) >= self.rpm:
            oldest = bucket[0]
            retry_after = int(oldest + 60.0 - self._now()) + 1
            return False, max(retry_after, 1)
        bucket.append(self._now())
        return True, 0


_rate_limiter = RateLimiter(
    requests_per_minute=int(getattr(settings, "chat_rate_limit_rpm", 30)),
    burst=int(getattr(settings, "chat_rate_limit_burst", 5)),
)


async def rate_limit_middleware(request: Request, call_next):
    """Apply rate limiting to chat endpoints only."""
    path = request.url.path
    if not path.startswith("/api/chat/"):
        return await call_next(request)

    # Identify client: session_id from body/query, fallback to client host
    client_key = request.client.host if request.client else "unknown"
    session_id = None
    if request.method == "POST":
        try:
            body = await request.json()
            session_id = body.get("session_id") or body.get("message", "")[:50]
        except Exception:
            pass
    key = f"sess:{session_id}" if session_id else f"ip:{client_key}"

    allowed, retry_after = _rate_limiter.allow(key)
    if not allowed:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error": "rate_limited",
                "message": f"Too many requests. Try again in {retry_after} second(s).",
                "retry_after": retry_after,
                "request_id": getattr(request.state, "request_id", str(uuid.uuid4())),
            },
            headers={"Retry-After": str(retry_after)},
        )

    response = await call_next(request)
    return response


# --------------------------------------------------------------------------- #
# Input sanitization & PII redaction
# --------------------------------------------------------------------------- #

_PII_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"), "[PHONE]"),          # US phone
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[EMAIL]"),  # email
    (re.compile(r"\b\d{4}[-.]?\d{4}[-.]?\d{4}[-.]?\d{4}\b"), "[CARD]"),   # credit card
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN]"),                      # US SSN
]


def sanitize_user_message(message: str) -> tuple[str, list[str]]:
    """Sanitize user input: strip control chars, redact PII, detect prompt injection.

    Returns (sanitized_message, list_of_redactions).
    """
    if not message or not isinstance(message, str):
        return "", []

    redactions: list[str] = []
    text = message

    # Redact PII
    for pattern, replacement in _PII_PATTERNS:
        matches = pattern.findall(text)
        if matches:
            redactions.append(pattern.pattern)
            text = pattern.sub(replacement, text)

    # Remove control characters except newlines/tabs
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    # Detect potential prompt-injection attempts (heuristic)
    injection_patterns = [
        r"ignore\s+previous\s+instructions",
        r"disregard\s+all\s+prior",
        r"system\s*[:=]\s*you\s+are\s+now",
        r"jailbreak",
        r"DAN\s*[:=]",
        r"as\s+an\s+AI\s+language\s+model",
    ]
    injection_found = any(p.search(text, re.IGNORECASE) for p in injection_patterns)

    # Length guard (hard limit 4000 chars, soft warning at 3500)
    if len(text) > 4000:
        text = text[:4000]

    return text, redactions, injection_found


# --------------------------------------------------------------------------- #
# Standardized error response
# --------------------------------------------------------------------------- #

def error_response(
    status_code: int,
    error_code: str,
    message: str,
    request_id: str | None = None,
    detail: str | None = None,
) -> JSONResponse:
    payload: dict[str, Any] = {
        "error": error_code,
        "message": message,
        "request_id": request_id or str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if detail:
        payload["detail"] = detail
    return JSONResponse(status_code=status_code, content=payload)


# --------------------------------------------------------------------------- #
# Validation helper for chat requests
# --------------------------------------------------------------------------- #

def validate_chat_request(message: str, session_id: str | None = None) -> tuple[str, str | None, list[str]]:
    """Validate and sanitize a chat request. Returns (clean_message, clean_session_id, redactions)."""
    clean_msg, redactions, injection_found = sanitize_user_message(message)
    if not clean_msg.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message cannot be empty after sanitization.",
        )
    clean_sid = session_id or ""
    if clean_sid and not re.match(r"^[a-zA-Z0-9_-]{1,64}$", clean_sid):
        clean_sid = ""
    if injection_found:
        # Still allow but log; could also block entirely
        pass
    return clean_msg, clean_sid, redactions

```

---

### 3.2 `backend/services/chat_context.py`

```python
"""Enhanced chat context: history retrieval, summarization, context window management."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from backend.database.models import ChatMessage
from backend.services import data_service
from backend.services.llm_service import LLMService

logger = logging.getLogger("mindtrip.chat_context")

MAX_CONTEXT_MESSAGES = 10
SUMMARY_THRESHOLD_MESSAGES = 20
SUMMARY_MAX_TOKENS_ESTIMATE = 600  # rough token budget for summary


class ChatContextManager:
    """Manages conversation context for the travel agent.

    Features:
    - Retrieves recent chat history from DB
    - Summarizes older turns when context window is large
    - Injects trip context when an active trip exists
    - Tracks token budget to avoid LLM overflow
    """

    def __init__(self, session: Session, session_id: str, llm: LLMService | None = None):
        self.session = session
        self.session_id = session_id
        self.llm = llm or LLMService()

    async def build_context(
        self,
        user_message: str,
        context: dict[str, Any] | None = None,
        max_messages: int = MAX_CONTEXT_MESSAGES,
    ) -> dict[str, Any]:
        """Build a context dict for the agent: history, trip, summary, and metadata."""
        context = context or {}
        trip_id = context.get("trip_id") or ""
        active_trip = None

        # Resolve active trip
        if not trip_id:
            from backend.database.models import Trip
            stmt = select(Trip).where(Trip.session_id == self.session_id).order_by(Trip.updated_at.desc())
            row = self.session.exec(stmt).first()
            if row:
                trip_id = row.id
        if trip_id:
            active_trip = data_service.get_trip(self.session, trip_id)

        # Retrieve recent chat history
        history = data_service.chat_history(self.session, self.session_id, limit=50)

        # Decide whether summarization is needed
        needs_summary = len(history) > SUMMARY_THRESHOLD_MESSAGES
        recent_history = history[-max_messages:] if not needs_summary else history[-max_messages:]

        summary_text = ""
        if needs_summary and len(history) > max_messages:
            summary_text = await self._summarize_older_turns(history[:-max_messages])

        return {
            "trip_id": trip_id,
            "active_trip": active_trip,
            "recent_history": recent_history,
            "summary": summary_text,
            "total_messages": len(history),
            "needs_summary": needs_summary,
        }

    async def _summarize_older_turns(self, older_turns: list[dict[str, Any]]) -> str:
        """Summarize older conversation turns to compress context."""
        if not self.llm.is_live or not older_turns:
            # Fallback: deterministic summary without LLM
            user_count = sum(1 for t in older_turns if t.get("sender") == "user")
            assistant_count = sum(1 for t in older_turns if t.get("sender") == "assistant")
            destinations = set()
            for t in older_turns:
                msg = t.get("message", "")
                for city in ("paris", "tokyo", "kyoto", "dubai", "new york", "swiss alps", "rome", "london"):
                    if city in msg.lower():
                        destinations.add(city.title())
            dest_str = ", ".join(sorted(destinations)) if destinations else "unspecified"
            return (
                f"Earlier conversation: {user_count} user messages and {assistant_count} assistant replies "
                f"covering {dest_str}. Older turns summarized to save context."
            )

        try:
            turns_text = "\n".join(
                f"{t.get('sender', 'unknown')}: {t.get('message', '')[:200]}"
                for t in older_turns[-10:]
            )
            prompt = (
                "Summarize the following conversation turns into 2-3 sentences. "
                "Focus on travel intent, destination, dates, travelers, and any decisions made. "
                "Be concise.\n\n" + turns_text
            )
            res = await self.llm.complete([{"role": "user", "content": prompt}])
            return (res.content or "").strip() or "Previous conversation context summarized."
        except Exception as exc:
            logger.warning("Context summarization failed: %s", exc)
            return "Previous conversation context unavailable."

```

---

### 3.3 `backend/config/production.py`

```python
"""Production configuration presets for Mindtrip Clone."""

from backend.config import Settings

PRODUCTION_DEFAULTS = {
    "environment": "production",
    "llm_provider": "demo",  # safe default; override via .env
    "llm_timeout_seconds": 30,
    "llm_temperature": 0.7,
    "chat_rate_limit_rpm": 30,
    "chat_rate_limit_burst": 5,
    "max_context_messages": 10,
    "summary_threshold_messages": 20,
    "cors_origins": "https://mindtrip.example.com,https://www.mindtrip.example.com",
    "enable_live_routing": True,
    "auto_seed": False,
}


def apply_production_defaults(settings: Settings) -> Settings:
    """Apply production-safe defaults to a Settings instance (non-destructive)."""
    for key, value in PRODUCTION_DEFAULTS.items():
        if hasattr(settings, key):
            current = getattr(settings, key)
            # Only override if the current value is the development default
            if current in ("demo", "development", "http://localhost:3000,http://127.0.0.1:3000"):
                setattr(settings, key, value)
    return settings

```

---

### 3.4 Modified `backend/routers/chat.py` (key changes)

The key changes to `chat.py` are shown below as diffs for clarity:

```python
# ADD at top imports:
from backend.services.production_middleware import (
    request_id_middleware,
    rate_limit_middleware,
    validate_chat_request,
    error_response,
)
from backend.services.chat_context import ChatContextManager

# ADD middleware to router (after router definition):
router.middleware("http")(request_id_middleware)
router.middleware("http")(rate_limit_middleware)

# Modified POST /message endpoint:
@router.post("/message")
async def send_message(request: ChatRequest, session: Session = Depends(get_session)) -> dict[str, Any]:
    # Validate & sanitize
    clean_message, clean_session_id, redactions = validate_chat_request(
        request.message, request.session_id
    )
    session_id = _ensure_session(session, clean_session_id or request.session_id or "")
    data_service.save_chat_message(session, session_id, "user", clean_message)

    # Build enriched context
    ctx_mgr = ChatContextManager(session, session_id)
    enriched_context = await ctx_mgr.build_context(
        clean_message,
        context=request.context or {},
    )

    agent = TravelAgent(session, session_id)
    try:
        reply = await agent.respond(clean_message, {
            **request.context,
            "trip_id": enriched_context["trip_id"],
            "_chat_context": enriched_context,  # passed to agent for history-aware responses
        })
    except Exception as exc:
        return error_response(
            status_code=502,
            error_code="agent_error",
            message="The concierge hit a snag. Please try again.",
            request_id=getattr(request.state, "request_id", None),
            detail=str(exc)[:200],
        )

    data_service.save_chat_message(
        session,
        session_id,
        "assistant",
        reply.get("message", ""),
        cards=reply.get("cards", []),
        pins=reply.get("pins", []),
    )
    reply["session_id"] = session_id
    reply["request_id"] = getattr(request.state, "request_id", None)
    return reply
```

---

### 3.5 Modified `backend/agent/travel_agent.py` (key changes)

**Inject chat history into `_local_response`** (the demo/local path currently ignores it entirely):

```python
# In _local_response, after resolving existing trip, add history-aware response:

def _local_response(self, message: str, context: dict[str, Any]) -> dict[str, Any]:
    # ... existing trip resolution ...
    ctx = context.get("_chat_context") or {}
    recent_history = ctx.get("recent_history", [])
    summary = ctx.get("summary", "")

    if trip_id and not is_new_trip:
        existing = data_service.get_trip(self.session, trip_id)
        if existing:
            # Build history-aware message using recent turns
            history_lines = []
            for turn in recent_history[-6:]:
                sender = turn.get("sender", "unknown")
                content = turn.get("message", "")[:150]
                history_lines.append(f"{sender}: {content}")
            history_str = "\n".join(history_lines) if history_lines else "No prior turns."

            # If the user is asking about their trip, reference history
            lowered_msg = message.lower()
            if any(w in lowered_msg for w in ("again", "also", "same", "like before", "that one", "it")):
                # Reference previous turn
                last_user = next(
                    (t for t in reversed(recent_history) if t.get("sender") == "user"),
                    None,
                )
                if last_user:
                    return {
                        "message": (
                            f"Based on our conversation, you previously asked about "
                            f"'{last_user.get('message', '')[:100]}'. "
                            f"Here's your current itinerary for {existing.get('title')}..."
                        ),
                        "cards": visuals["cards"],
                        "pins": visuals["pins"],
                        "trip": existing,
                        ...
                    }

            # ... rest of existing logic with history context appended ...
```

**Improve `_live_response` to use the enriched context:**

```python
# In _live_response, replace the simple history fetch with enriched context:
ctx = context.get("_chat_context") or {}
history = ctx.get("recent_history", [])
summary = ctx.get("summary", "")

messages: list[dict[str, Any]] = [{"role": "system", "content": system_text}]
if summary:
    messages.append({"role": "system", "content": f"CONVERSATION SUMMARY (older turns): {summary}"})
for row in history[-8:]:
    if row["sender"] in {"user", "assistant"} and row["message"]:
        messages.append({"role": row["sender"], "content": row["message"]})
messages.append({"role": "user", "content": message})
```

---

### 3.6 Modified `backend/services/llm_service.py` (resilience)

Add retry with exponential backoff to `complete()`:

```python
import asyncio

async def complete_with_retry(
    self,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    temperature: float | None = None,
    max_retries: int = 2,
    base_delay: float = 1.0,
) -> LLMResponse:
    """Complete with exponential backoff retry on transient errors."""
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            return await self.complete(messages, tools, temperature)
        except LLMError as exc:
            last_exc = exc
            if attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                logger.warning("LLM call failed (attempt %d/%d): %s; retrying in %.1fs",
                               attempt + 1, max_retries + 1, exc, delay)
                await asyncio.sleep(delay)
            else:
                raise
    raise last_exc  # unreachable but satisfies type checker
```

And update `travel_agent.py` `_live_response` to call `complete_with_retry` instead of `complete`.

---

### 3.7 Frontend: `frontend/src/lib/api.ts` (resilience)

```typescript
const MAX_RETRIES = 3;
const BASE_DELAY_MS = 800;

async function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function api(path: string, init?: RequestInit): Promise<Response> {
  const cleanPath = path.startsWith("/") ? path : `/${path}`;
  const fullPath = cleanPath.startsWith("/api/") || cleanPath === "/api"
    ? cleanPath
    : `${API_BASE}${cleanPath}`;

  let lastError: unknown = null;
  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      const res = await fetch(fullPath, {
        headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
        ...init,
      });
      if (!res.ok) throw new Error(`API ${fullPath} ${res.status}`);
      return res;
    } catch (err) {
      lastError = err;
      if (attempt < MAX_RETRIES) {
        await sleep(BASE_DELAY_MS * (2 ** attempt));
      }
    }
  }
  throw lastError;
}
```

---

## 4. Verification Checklist

Before deploying to production, verify each item:

### Security
- [ ] Rate limiting blocks >30 req/min per session
- [ ] PII (phones, emails, cards, SSNs) is redacted in logs and responses
- [ ] Prompt-injection patterns are detected and flagged
- [ ] CORS is restricted to production domains only
- [ ] No raw IDs or JSON leaked in LLM responses (prompt instruction already exists)

### Reliability
- [ ] LLM calls retry with exponential backoff (max 2 retries)
- [ ] SSE stream falls back to POST `/chat/message` with retry
- [ ] Frontend retries failed API calls with backoff
- [ ] Local planner path uses chat history (not just live LLM path)
- [ ] Database session is properly closed after each request

### Observability
- [ ] Every response includes `X-Request-ID` header
- [ ] Structured logging includes request_id and duration
- [ ] Health endpoint (`/health`) returns dependency status (DB, LLM provider)
- [ ] Error responses include `request_id` for client-side correlation

### Data
- [ ] Chat messages are persisted with cards/pins JSON
- [ ] Trip context is resolved from `trip_id` or latest session trip
- [ ] Conversation summarization triggers after 20+ messages
- [ ] SQLite WAL mode enabled for concurrent reads/writes (production)

---

## 5. Quick Start

```bash
# 1. Copy production env template
cp .env.example .env
# Edit .env: set LLM_PROVIDER, API keys, CORS origins, rate limits

# 2. Install backend deps (already in .venv)
cd backend
.venv\Scripts\pip install -r requirements.txt

# 3. Run with production settings
# Ensure .env has environment=production
.venv\Scripts\python run_backend.py

# 4. Run frontend
cd frontend
npm install
npm run dev
```

---

## 6. Files Changed / Created Summary

```
NEW:   backend/services/production_middleware.py   (rate limiting, sanitization, PII, request IDs)
NEW:   backend/services/chat_context.py             (history, summarization, context window)
NEW:   backend/config/production.py                  (production presets)
MOD:   backend/routers/chat.py                        (middleware, validation, enriched context)
MOD:   backend/agent/travel_agent.py                  (history-aware local path, retry LLM)
MOD:   backend/services/llm_service.py                (complete_with_retry)
MOD:   backend/config.py                              (new settings fields)
MOD:   frontend/src/lib/api.ts                        (retry with backoff)
NEW:   PRODUCTION_READINESS.md                         (this document)
```
