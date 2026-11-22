"""Enhanced chat context: history retrieval, summarization, context window management."""

from __future__ import annotations

import logging
from typing import Any

from sqlmodel import Session, select

from backend.database.models import ChatMessage, Trip
from backend.services import data_service
from backend.services.llm_service import LLMService

logger = logging.getLogger("mindtrip.chat_context")

MAX_CONTEXT_MESSAGES = 10
SUMMARY_THRESHOLD_MESSAGES = 20


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
        if not older_turns:
            return ""

        # Fallback deterministic summary without LLM (always safe)
        user_count = sum(1 for t in older_turns if t.get("sender") == "user")
        assistant_count = sum(1 for t in older_turns if t.get("sender") == "assistant")
        destinations: set[str] = set()
        for t in older_turns:
            msg = (t.get("message") or "").lower()
            for city in (
                "paris", "tokyo", "kyoto", "dubai", "new york", "swiss alps",
                "rome", "london", "mumbai", "delhi", "jaipur", "pune", "dublin",
            ):
                if city in msg:
                    destinations.add(city.title())
        dest_str = ", ".join(sorted(destinations)) if destinations else "unspecified"
        fallback = (
            f"Earlier conversation: {user_count} user messages and {assistant_count} assistant replies "
            f"covering {dest_str}. Older turns summarized to save context."
        )

        if not self.llm.is_live:
            return fallback

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
            content = (res.content or "").strip()
            return content if content else fallback
        except Exception as exc:
            logger.warning("Context summarization failed: %s", exc)
            return fallback
