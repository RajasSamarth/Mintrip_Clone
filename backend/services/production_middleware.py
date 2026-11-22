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
    (re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"), "[PHONE]"),
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[EMAIL]"),
    (re.compile(r"\b\d{4}[-.]?\d{4}[-.]?\d{4}[-.]?\d{4}\b"), "[CARD]"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN]"),
]


def sanitize_user_message(message: str) -> tuple[str, list[str], bool]:
    """Sanitize user input: strip control chars, redact PII, detect prompt injection.

    Returns (sanitized_message, list_of_redaction_patterns, injection_detected).
    """
    if not message or not isinstance(message, str):
        return "", [], False

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
        re.compile(r"ignore\s+previous\s+instructions", re.IGNORECASE),
        re.compile(r"disregard\s+all\s+prior", re.IGNORECASE),
        re.compile(r"system\s*[:=]\s*you\s+are\s+now", re.IGNORECASE),
        re.compile(r"jailbreak", re.IGNORECASE),
        re.compile(r"DAN\s*[:=]", re.IGNORECASE),
    ]
    injection_found = any(p.search(text) for p in injection_patterns)

    # Length guard
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

def validate_chat_request(
    message: str,
    session_id: str | None = None,
) -> tuple[str, str | None, list[str]]:
    """Validate and sanitize a chat request.

    Returns (clean_message, clean_session_id, redactions).
    Raises HTTPException(400) if the message is empty after sanitization.
    """
    clean_msg, redactions, _injection_found = sanitize_user_message(message)
    if not clean_msg.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message cannot be empty after sanitization.",
        )
    clean_sid = session_id or ""
    if clean_sid and not re.match(r"^[a-zA-Z0-9_-]{1,64}$", clean_sid):
        clean_sid = ""
    return clean_msg, clean_sid, redactions
