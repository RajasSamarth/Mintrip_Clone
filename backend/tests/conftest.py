"""Shared pytest setup: isolated SQLite database and demo LLM."""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import uuid
from pathlib import Path

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

test_run_id = uuid.uuid4().hex[:8]
temp_dir = Path(tempfile.gettempdir())
TEST_DB = temp_dir / f"test_mindtrip_{test_run_id}.db"

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["LLM_PROVIDER"] = "demo"
os.environ["GROQ_API_KEY"] = ""
os.environ["XAI_API_KEY"] = ""
os.environ["OPENAI_API_KEY"] = ""
os.environ["GEMINI_API_KEY"] = ""
os.environ["ENABLE_LIVE_ROUTING"] = "false"
os.environ["ENABLE_LIVE_FLIGHT_ATTACH"] = "0"
os.environ["AUTO_SEED"] = "true"
os.environ["FIXTURES_PATH"] = str(ROOT / "data" / "fixtures" / "sample_trips.json")
os.environ["USER_SCRAPER_DIR"] = str(ROOT / "scrapers" / "user_scrapers")

from backend.config import Settings, get_settings  # noqa: E402

_test_settings = Settings(
    database_url=f"sqlite:///{TEST_DB.as_posix()}",
    llm_provider="demo",
    groq_api_key="",
    xai_api_key="",
    openai_api_key="",
    gemini_api_key="",
    enable_live_routing=False,
    fixtures_path=str(ROOT / "data" / "fixtures" / "sample_trips.json"),
    user_scraper_dir=str(ROOT / "scrapers" / "user_scrapers"),
)

import backend.config  # noqa: E402
backend.config.get_settings = lambda: _test_settings

import backend.services.llm_service  # noqa: E402
backend.services.llm_service.get_settings = lambda: _test_settings

# Also reload database engine with the test URL
from backend.database import db  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
db.engine = create_engine(f"sqlite:///{TEST_DB.as_posix()}", echo=False, connect_args={"check_same_thread": False})
db.init_db()

import backend.main  # noqa: E402
backend.main.engine = db.engine
import backend.routers.chat  # noqa: E402
backend.routers.chat.engine = db.engine

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_db():
    yield
    try:
        db.engine.dispose()
    except Exception:
        pass
    try:
        if TEST_DB.exists():
            TEST_DB.unlink()
    except Exception:
        pass


@pytest.fixture(scope="session")
def client():
    from backend.main import app
    from backend.database.db import get_session
    from sqlmodel import Session as SQLSession

    def override_get_session():
        with SQLSession(db.engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def auth_headers() -> dict[str, str]:
    return {}
