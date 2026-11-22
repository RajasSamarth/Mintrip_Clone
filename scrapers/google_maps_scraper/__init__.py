"""Google Maps Business Data Extractor & Scraper package."""
import sys
from pathlib import Path

# Ensure the internal modules (app.adapters, app.services, app.schemas, etc.)
# can be imported seamlessly without modifying the scraper source code.
_PACKAGE_ROOT = Path(__file__).resolve().parent
if str(_PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PACKAGE_ROOT))
