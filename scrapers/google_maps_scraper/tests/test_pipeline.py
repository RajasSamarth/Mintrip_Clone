"""Tests for the shared query x location fan-out pipeline."""
from app.adapters.approved_source import SyntheticDataSource
from app.services import areas as areas_service
from app.services.pipeline import _ask_size, build_plan, run_fanout


class _CountingSource:
    """Wraps a source and records which locations were actually scraped."""

    def __init__(self, source):
        self.source = source
        self.calls: list[str] = []

    def search_page(self, **kwargs):
        self.calls.append(kwargs["location"])
        return self.source.search_page(**kwargs)


def test_ask_size_has_bounded_slack():
    # Uncapped stays uncapped.
    assert _ask_size(None) is None
    # Small budgets get some slack to absorb cross-area duplicates.
    assert _ask_size(5) == 25
    # ...but never more than Google's own feed ceiling.
    assert _ask_size(100) == 120
    assert _ask_size(5000) == 120


def test_fanout_stops_at_max_results():
    source = _CountingSource(SyntheticDataSource(total_available=87, page_size=20))
    result = run_fanout(source, ["restaurants"], ["Area A", "Area B", "Area C"], max_results=5)

    assert len(result.records) == 5
    # The remaining areas are never scraped: max_results is a budget, not a
    # post-processing trim (that is what used to make small jobs take hours).
    assert set(source.calls) == {"Area A"}
    assert result.stopped_reason == "max_results reached"


def test_fanout_tops_up_from_next_area():
    source = SyntheticDataSource(total_available=87, page_size=20)
    result = run_fanout(source, ["q"], ["Area A", "Area B"], max_results=100)

    assert len(result.records) == 100
    assert result.areas_swept == 2


def test_fanout_streams_batches():
    batches: list[list] = []
    result = run_fanout(
        SyntheticDataSource(total_available=87),
        ["q"],
        ["Area A"],
        max_results=None,
        on_batch=batches.append,
        max_workers=1,
    )

    assert len(result.records) == 87
    assert sum(len(b) for b in batches) == 87


def test_fanout_merges_and_dedupes_areas():
    result = run_fanout(
        SyntheticDataSource(total_available=87),
        ["q"],
        ["Area A", "Area B"],
        max_results=None,
        max_workers=1,
    )

    # 87 + 87 raw, 45 shared place_ids collapse.
    assert len(result.records) == 129


def test_fanout_gives_up_after_fruitless_areas(monkeypatch):
    """Areas that only repeat known listings must not keep the job alive."""

    class _SameEverywhere:
        def __init__(self):
            self.calls = 0

        def search_page(self, query, location, radius_km=None, page_size=20, page_token=None):
            self.calls += 1
            if page_token:
                return [], None
            return [{"business_name": "Same Place", "place_id": "p1"}], None

    monkeypatch.setenv("MAX_STALE_AREAS", "2")
    source = _SameEverywhere()
    result = run_fanout(
        source, ["q"], ["A", "B", "C", "D", "E"], max_results=10
    )

    assert len(result.records) == 1
    assert result.areas_swept == 3  # A + two fruitless areas
    assert "no new listings" in (result.stopped_reason or "")


def test_fanout_applies_min_rating():
    result = run_fanout(
        SyntheticDataSource(total_available=20),
        ["q"],
        ["Area A"],
        max_results=None,
        min_rating=4.0,
        max_workers=1,
    )

    assert result.records
    assert all(r.rating is None or r.rating >= 4.0 for r in result.records)


def test_build_plan_keeps_requested_location_first():
    queries, locations, notes = build_plan(
        "restaurants",
        "Dharampeth, Nagpur",
        extra_queries=["cafes", " restaurants "],
        extra_locations=["Sadar, Nagpur"],
        auto_areas=False,
    )

    assert queries == ["restaurants", "cafes"]
    assert locations == ["Dharampeth, Nagpur", "Sadar, Nagpur"]
    assert notes == []


def test_build_plan_labels_discovered_areas(monkeypatch):
    monkeypatch.setattr(
        areas_service, "discover_areas", lambda city, limit=None: ["Sadar", "Nagpur"]
    )
    _queries, locations, _notes = build_plan("gym", "Dharampeth, Nagpur", auto_areas=True)

    assert locations == ["Dharampeth, Nagpur", "Sadar, Nagpur", "Nagpur"]


def test_build_plan_keeps_coordinate_labels_clean(monkeypatch):
    monkeypatch.setattr(
        areas_service, "discover_areas", lambda city, limit=None: ["21.14580,79.08820"]
    )
    _queries, locations, notes = build_plan("gym", "Dharampeth, Nagpur", auto_areas=True)

    # A grid cell is already unambiguous -- no ", Nagpur" suffix.
    assert locations == ["Dharampeth, Nagpur", "21.14580,79.08820"]
    assert any("coordinate grid" in n for n in notes)


def test_build_plan_survives_discovery_crash(monkeypatch):
    def _boom(*args, **kwargs):
        raise RuntimeError("overpass down")

    monkeypatch.setattr(areas_service, "discover_areas", _boom)
    _queries, locations, notes = build_plan("gym", "Dharampeth, Nagpur", auto_areas=True)

    assert locations == ["Dharampeth, Nagpur"]
    assert any("no results" in n for n in notes)
