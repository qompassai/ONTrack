"""
test_geocoder.py — unit tests for core/geocoder.py

All network calls are mocked with pytest-mock so CI never hits Nominatim.

Covers:
  - All addresses resolve → all have lat/lng
  - One address fails (geocoder returns None) → lat/lng are None for that entry
  - All addresses fail → all None
  - Empty input → empty output
  - Output length always matches input length
  - Output dicts carry the original address string
"""

import pytest
from unittest.mock import MagicMock, patch

from core.geocoder import geocode_addresses


def _make_loc(lat, lng):
    """Minimal geopy Location stand-in."""
    loc = MagicMock()
    loc.latitude = lat
    loc.longitude = lng
    return loc


class TestGeocodeAddresses:
    def test_all_resolve(self, three_addresses):
        fake_locs = [
            _make_loc(47.6588, -117.4260),
            _make_loc(47.6601, -117.4200),
            _make_loc(47.6615, -117.4150),
        ]
        with patch("core.geocoder.geolocator.geocode", side_effect=fake_locs):
            result = geocode_addresses(three_addresses)

        assert len(result) == 3
        for item, addr in zip(result, three_addresses):
            assert item["address"] == addr
            assert item["lat"] is not None
            assert item["lng"] is not None

    def test_one_fails(self, three_addresses):
        """Middle address returns None from Nominatim."""
        side_effects = [
            _make_loc(47.6588, -117.4260),
            None,
            _make_loc(47.6615, -117.4150),
        ]
        with patch("core.geocoder.geolocator.geocode", side_effect=side_effects):
            result = geocode_addresses(three_addresses)

        assert len(result) == 3
        assert result[1]["lat"] is None
        assert result[1]["lng"] is None
        assert result[1]["address"] == three_addresses[1]

    def test_all_fail(self, three_addresses):
        with patch("core.geocoder.geolocator.geocode", return_value=None):
            result = geocode_addresses(three_addresses)

        assert all(r["lat"] is None and r["lng"] is None for r in result)

    def test_empty_input(self):
        with patch("core.geocoder.geolocator.geocode") as mock_geocode:
            result = geocode_addresses([])
        assert result == []
        mock_geocode.assert_not_called()

    def test_output_length_matches_input(self, three_addresses):
        with patch("core.geocoder.geolocator.geocode", return_value=None):
            result = geocode_addresses(three_addresses)
        assert len(result) == len(three_addresses)

    def test_lat_lng_types(self, three_addresses):
        fake_locs = [_make_loc(47.658 + i * 0.001, -117.426 + i * 0.001) for i in range(3)]
        with patch("core.geocoder.geolocator.geocode", side_effect=fake_locs):
            result = geocode_addresses(three_addresses)
        for item in result:
            assert isinstance(item["lat"], float)
            assert isinstance(item["lng"], float)

    def test_address_string_preserved(self, three_addresses):
        with patch("core.geocoder.geolocator.geocode", return_value=None):
            result = geocode_addresses(three_addresses)
        for item, addr in zip(result, three_addresses):
            assert item["address"] == addr
