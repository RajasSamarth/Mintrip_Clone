# TODO — Mindtrip Clone

## Guardrails (Implement)

- [ ] Rate limiting on chat endpoints (30 req/min per session)
- [ ] Input sanitization (strip control chars, limit 4000 chars)
- [ ] PII redaction (phones, emails, credit cards, SSNs)
- [ ] Prompt injection detection (ignore previous instructions, DAN, etc.)
- [ ] Off-topic guardrail (sports, politics, coding, non-travel trivia)
- [ ] Underspecified trip inquiry (no assumed dates/travelers → intake mode)
- [ ] Saturday/calendar integrity (don't hallucinate days not in trip)
- [ ] Per-day & trip-wide stop deduplication
- [ ] Request ID tracing (X-Request-ID header on all responses)
- [ ] Standardized JSON error responses

## Notes

- Guardrails live in `backend/services/production_middleware.py`
- Chat context/history management in `backend/services/chat_context.py`
- Agent guardrail logic in `backend/agent/travel_agent.py`
- Frontend API retry logic in `frontend/src/lib/api.ts`
