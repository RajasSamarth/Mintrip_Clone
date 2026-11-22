"""Conversation memory with summarization.

Compresses older chat turns into a short summary so the live LLM sees a compact
system prompt instead of a growing transcript. This saves Groq tokens and keeps
responses fast on long conversations.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from backend.services import data_service
from backend.services.llm_service import LLMService

logger = logging.getLogger("mindtrip.memory")

# Keep the last N turns verbatim; everything older gets summarized.
VERBATIM_WINDOW = 6
SUMMARY_MAX_TURNS = 40  # don't summarize more than this many at once


def _escape_for_prompt(text: str) -> str:
    return (text or "").replace("{", "{{").replace("}", "}}")


async def summarize_history(
    llm: LLMService,
    session_id: str,
    session: Any,
    max_turns: int = SUMMARY_MAX_TURNS,
) -> dict[str, Any]:
    """Return ``{"summary": str, "recent_history": list[dict]}``.

    Older turns (beyond the verbatim window) are summarized by the LLM into one
    short paragraph. Recent turns are returned verbatim for the system prompt.
    """
    if not llm.is_live:
        # No LLM available: fall back to raw recent history without summarization.
        rows = data_service.chat_history(session, session_id, limit=VERBATIM_WINDOW)
        recent = [
            {
                "sender": r["sender"],
                "message": r["message"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]
        return {"summary": "", "recent_history": recent}

    all_rows = data_service.chat_history(session, session_id, limit=max_turns)
    if not all_rows or len(all_rows) <= VERBATIM_WINDOW:
        return {
            "summary": "",
            "recent_history": [
                {"sender": r["sender"], "message": r["message"], "created_at": r["created_at"]}
                for r in all_rows
            ],
        }

    split_index = len(all_rows) - VERBATIM_WINDOW
    older_rows = all_rows[:split_index]
    recent_rows = all_rows[split_index:]

    # Build transcript for summarization.
    transcript_lines = []
    for r in older_rows:
        transcript_lines.append(f"{r['sender']}: {r['message'][:200]}")
    transcript = "\n".join(transcript_lines)

    summary_prompt = (
        "Summarize the following travel-conversation transcript into a short "
        "paragraph (2-3 sentences). Capture: destination, dates, travelers, "
        "hotel, flights already discussed, and any open requests or changes the "
        "user is waiting on. Do not invent details.\n\n"
        + transcript
    )

    try:
        res = await llm.complete([{"role": "user", "content": summary_prompt}])
        summary = (res.content or "").strip()
    except Exception as exc:  # noqa: BLE001 - summarization is best-effort
        logger.warning("Conversation summarization failed (%s); skipping summary", exc)
        summary = ""

    recent_history = [
        {"sender": r["sender"], "message": r["message"], "created_at": r["created_at"]}
        for r in recent_rows
    ]
    return {"summary": summary, "recent_history": recent_history}


def build_context_from_history(
    session: Any,
    session_id: str,
    limit: int = VERBATIM_WINDOW,
) -> dict[str, Any]:
    """Synchronous fallback: raw recent history without LLM summarization."""
    rows = data_service.chat_history(session, session_id, limit=limit)
    return {
        "summary": "",
        "recent_history": [
            {"sender": r["sender"], "message": r["message"], "created_at": r["created_at"]}
            for r in rows
        ],
    }
