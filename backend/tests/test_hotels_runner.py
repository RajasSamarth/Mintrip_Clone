"""Tests for hotel scraper runner and data normalisation."""

from scrapers.hotel_scraper_runner import (
    generate_fallback_hotels,
    search_hotels,
)


def test_generate_fallback_hotels_kyoto() -> None:
    hotels = generate_fallback_hotels("Kyoto", count=8, currency="INR")
    assert len(hotels) >= 3
    assert all("#" not in h.name for h in hotels)
    assert hotels[0].destination == "Kyoto"
    assert any(h.name == "The Thousand Kyoto" for h in hotels)
    # Check honest price_unavailable handling on Yoshikawa
    yoshikawa = next((h for h in hotels if "Yoshikawa" in h.name), None)
    if yoshikawa:
        assert yoshikawa.price_unavailable is True
        assert yoshikawa.price_per_night is None


def test_search_hotels_offline() -> None:
    hotels = search_hotels("Rome", live=False, currency="USD")
    assert len(hotels) > 0
    assert hotels[0].currency == "USD"
    assert hotels[0].destination == "Rome"
