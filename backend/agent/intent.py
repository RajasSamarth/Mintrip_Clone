"""Lightweight, zero-LLM intent classifier.

Routes user messages to fast local handlers so Groq tokens are only spent on
genuine travel planning / modification requests. All matching is regex-based
and runs in microseconds.
"""

from __future__ import annotations

import re
from typing import Literal

Intent = Literal[
    "greeting",
    "goodbye",
    "thanks",
    "help",
    "modify_trip",
    "add_stop",
    "remove_stop",
    "swap_hotel",
    "flight_info",
    "trip_status",
    "off_topic",
    "new_itinerary",
    "unclear",
]

# Patterns ordered from most specific to most general.
_INTENT_PATTERNS: list[tuple[Intent, re.Pattern[str]]] = [
    ("greeting", re.compile(r"\b(hi|hello|hey|good (morning|afternoon|evening)|yo|hiya)\b", re.I)),
    ("goodbye", re.compile(r"\b(bye|goodbye|see ya|see you|chat later|take care)\b", re.I)),
    ("thanks", re.compile(r"\b(thank you|thanks|thx|appreciate it|cheers)\b", re.I)),
    ("help", re.compile(r"\b(help|how do i|what can you do|instructions|guide|tutorial)\b", re.I)),
    # Modification intents (highest priority among travel actions)
    ("swap_hotel", re.compile(r"\b(swap|change|replace|switch|different|another)\b.*\b(hotel|stay|room|accommodation)\b", re.I)),
    ("add_stop", re.compile(r"\b(add|include|put|insert|schedule)\b.*\b(stop|place|spot|activity|restaurant|cafe|dinner|lunch|breakfast)\b", re.I)),
    ("remove_stop", re.compile(r"\b(remove|delete|drop|cancel|take out)\b.*\b(stop|place|spot|activity|restaurant|day)\b", re.I)),
    ("flight_info", re.compile(r"\b(flight|fly|airline|plane|depart|arrive|boarding|ticket)\b", re.I)),
    ("trip_status", re.compile(r"\b(my trip|itinerary|day (\d+)|schedule|plan so far|current trip|booked)\b", re.I)),
    # General travel planning
    ("new_itinerary", re.compile(r"\b(plan|planning|trip|itinerary|travel|vacation|holiday|days?|nights?|weekend|getaway|visit|visiting|explore|flights?|hotels?|staying|tour|city break)\b", re.I)),
]


def classify(text: str) -> Intent:
    """Return the most likely intent for a user message.

    Falls back to ``new_itinerary`` for substantive travel-looking text, and
    ``unclear`` for short/ambiguous input.
    """
    lowered = (text or "").strip().lower()
    if not lowered:
        return "unclear"

    for intent, pattern in _INTENT_PATTERNS:
        if pattern.search(lowered):
            return intent

    # Heuristic: more than a couple of words almost certainly means a travel
    # request rather than a one-word greeting.
    if len(lowered.split()) > 3:
        return "new_itinerary"
    return "unclear"


# Instant, zero-token replies for non-planning intents.
INSTANT_REPLIES: dict[Intent, str] = {
    "greeting": "Hi! I'm your Mindtrip travel concierge. Where would you like to go?",
    "goodbye": "Have a wonderful trip! Come back anytime to plan your next adventure.",
    "thanks": "You're welcome! Anything else I can help you plan?",
    "help": (
        "Ask me to plan a trip (e.g. “Plan a 5-day trip to Kyoto”), swap a hotel, "
        "add a stop to your itinerary, or check your flights. I handle the details "
        "so you don't have to."
    ),
}

__all__ = ["classify", "INSTANT_REPLIES", "Intent"]
