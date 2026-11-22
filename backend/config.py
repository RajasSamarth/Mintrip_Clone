"""Application configuration (environment driven)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=[str(ROOT / ".env"), str(ROOT / "backend" / ".env")],
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Mindtrip Clone API"
    environment: str = "development"
    api_prefix: str = "/api"

    database_url: str = f"sqlite:///{(ROOT / 'data' / 'mindtrip.db').as_posix()}"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # LLM: grok | openai | gemini | openrouter | ollama | demo
    llm_provider: str = "demo"
    llm_model: str = ""
    xai_api_key: str = ""
    openai_api_key: str = ""
    gemini_api_key: str = ""
    openrouter_api_key: str = ""
    groq_api_key: str = ""
    groq_api_keys: str = ""  # comma-separated backup Groq keys for auto-failover on 429
    nvidia_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    llm_temperature: float = 0.7
    llm_timeout_seconds: int = 15

    # Supabase persistence & sync
    supabase_url: str = ""
    supabase_key: str = ""
    supabase_service_role_key: str = ""

    enable_live_routing: bool = False
    user_scraper_dir: str = str(ROOT / "scrapers" / "user_scrapers")
    fixtures_path: str = str(ROOT / "data" / "fixtures" / "sample_trips.json")
    auto_seed: bool = True

    # Production settings
    chat_rate_limit_rpm: int = 30
    chat_rate_limit_burst: int = 5
    max_context_messages: int = 10
    summary_threshold_messages: int = 20

    # Circuit breaker for external APIs
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout: int = 60

    # Free forex API (Frankfurter.app - no key required)
    forex_api_url: str = "https://api.frankfurter.app/latest"

    # Stripe (optional, for booking/payment flow)
    stripe_publishable_key: str = ""
    stripe_secret_key: str = ""

    # Redis URL for distributed rate limiting (optional)
    redis_url: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def groq_key_list(self) -> list[str]:
        """Return all configured Groq API keys (primary first, then backups)."""
        keys: list[str] = []
        if self.groq_api_key.strip():
            keys.append(self.groq_api_key.strip())
        if self.groq_api_keys.strip():
            for k in self.groq_api_keys.split(","):
                k = k.strip()
                if k and k not in keys:
                    keys.append(k)
        return keys


@lru_cache
def get_settings() -> Settings:
    return Settings()


# --------------------------------------------------------------------------- #
# Production presets
# --------------------------------------------------------------------------- #

PRODUCTION_DEFAULTS: dict[str, Any] = {
    "environment": "production",
    "llm_provider": "demo",  # safe default; override via .env with a real key
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
    """Apply production-safe defaults to a Settings instance (non-destructive).

    Only overrides fields that still hold their development defaults, so an
    existing .env with real API keys will not be clobbered.
    """
    dev_defaults = ("demo", "development", "http://localhost:3000,http://127.0.0.1:3000", "")
    for key, value in PRODUCTION_DEFAULTS.items():
        if hasattr(settings, key):
            current = getattr(settings, key)
            if current in dev_defaults:
                setattr(settings, key, value)
    return settings
