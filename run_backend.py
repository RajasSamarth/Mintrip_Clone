import sys
import os
import time
import traceback
import asyncio
from pathlib import Path

# Set Windows Proactor event loop policy BEFORE any event loop is created,
# so Playwright's create_subprocess_exec works on Windows.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import uvicorn

if __name__ == "__main__":
    while True:
        print("Starting MindTrip FastAPI backend server on http://127.0.0.1:8000 ...", flush=True)
        try:
            uvicorn.run(
                "backend.main:app",
                host="127.0.0.1",
                port=8000,
                log_level="info",
                access_log=True,
            )
        except BaseException as e:
            print(f"Server exited with exception: {e}", file=sys.stderr, flush=True)
            traceback.print_exc()
            time.sleep(2)
