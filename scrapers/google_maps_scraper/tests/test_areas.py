"""Tests for automatic area discovery (no network: parsing + validation only)."""
from app.services.areas import (
    _parse_names,
    coordinate_grid,
    discover_areas,
    extract_city,
    is_coordinate_label,
)


def test_extract_city():
    assert extract_city("Dharampeth, Nagpur") == "Nagpur"
    assert extract_city("Nagpur") == "Nagpur"
    assert extract_city("  Sadar, Nagpur  ") == "Nagpur"
    assert extract_city("") == ""


def test_is_coordinate_label():
    assert is_coordinate_label("21.14580,79.08820")
    assert is_coordinate_label("-33.86880,151.20930")
    assert not is_coordinate_label("Sadar, Nagpur")
    assert not is_coordinate_label("")


def test_coordinate_grid_covers_the_bbox():
    cells = coordinate_grid((21.0, 79.0, 21.3, 79.3), cells=3)

    assert len(cells) == 9
    assert all(is_coordinate_label(c) for c in cells)
    # Cell centres, not the bbox corners.
    assert cells[0] == "21.05000,79.05000"
    assert cells[-1] == "21.25000,79.25000"


def test_parse_names_dedupes():
    payload = {"elements": [
        {"tags": {"name": "Sadar"}},
        {"tags": {"name": "Sadar"}},
        {"tags": {"name": "  Bajaj Nagar  "}},
        {"tags": {}},
        {},
    ]}
    assert _parse_names(payload) == ["Sadar", "Bajaj Nagar"]
    assert _parse_names({}) == []
    assert _parse_names(None) == []


def test_discover_short_circuits_without_network(monkeypatch):
    def _fail(*args, **kwargs):
        raise AssertionError("no network allowed")

    monkeypatch.setattr("urllib.request.urlopen", _fail)
    assert discover_areas("") == []
    assert discover_areas("   ") == []
    assert discover_areas("Nagpur", limit=0) == []


def test_discover_parses_response(monkeypatch):
    calls = {"n": 0}

    class _Resp:
        def __init__(self, body: bytes):
            self._body = body

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return self._body

    def _fake(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:  # Nominatim bbox lookup
            return _Resp(b'[{"boundingbox": ["21.0", "21.2", "79.0", "79.2"]}]')
        # Overpass area lookup
        return _Resp(b'{"elements": [{"tags": {"name": "Sadar"}}, {"tags": {"name": "Itwari"}}]}')

    monkeypatch.setattr("urllib.request.urlopen", _fake)
    assert discover_areas("Nagpur", limit=5, use_mapsofindia=False) == ["Sadar", "Itwari"]
    assert discover_areas("Nagpur", limit=1, use_mapsofindia=False) == ["Sadar"]


def test_discover_failure_returns_empty(monkeypatch):
    from app.services import areas as areas_mod

    def _boom(*args, **kwargs):
        raise OSError("offline")

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    monkeypatch.setitem(areas_mod._CACHE, "offline city", (0.0, ["stale"]))
    assert discover_areas("Offline City") == []


def test_discover_falls_back_to_grid_when_overpass_fails(monkeypatch):
    from app.services import areas as areas_mod

    class _Resp:
        def __init__(self, body: bytes):
            self._body = body

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return self._body

    def _fake(url, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:  # Nominatim bbox lookup
            return _Resp(b'[{"boundingbox": ["21.0", "21.3", "79.0", "79.3"]}]')
        raise OSError("overpass overloaded")

    calls = {"n": 0}
    monkeypatch.setattr("urllib.request.urlopen", _fake)
    monkeypatch.setitem(areas_mod._CACHE, "grid city", (0.0, ["stale"]))
    areas = discover_areas("Grid City", grid_fallback=True, use_mapsofindia=False)

    # OSM is down: a coordinate grid still gives the job city-wide coverage.
    assert len(areas) == 9
    assert all(is_coordinate_label(a) for a in areas)


def test_discover_can_disable_grid_fallback(monkeypatch):
    from app.services import areas as areas_mod

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'[{"boundingbox": ["21.0", "21.3", "79.0", "79.3"]}]'

    def _fake(url, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:  # Nominatim bbox lookup
            return _Resp()
        raise OSError("overpass overloaded")

    calls = {"n": 0}
    monkeypatch.setattr("urllib.request.urlopen", _fake)
    monkeypatch.setitem(areas_mod._CACHE, "no grid city", (0.0, ["stale"]))
    assert discover_areas("No Grid City", grid_fallback=False) == []
