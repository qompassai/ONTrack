"""
conftest.py — shared fixtures for OnTrack test suite.
"""

import os
import pathlib
import pytest

# ── Paths ──────────────────────────────────────────────────────────────────
TESTS_DIR = pathlib.Path(__file__).parent
SAMPLE_CSV = TESTS_DIR / "sample_addresses.csv"


# ── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture
def sample_csv(tmp_path):
    """Copy sample CSV into a temp dir so tests that write don't corrupt it."""
    import shutil
    dest = tmp_path / "addresses.csv"
    shutil.copy(SAMPLE_CSV, dest)
    return str(dest)


@pytest.fixture
def three_addresses():
    return [
        "123 Main St Spokane WA",
        "456 Elm St Spokane WA",
        "789 Oak Ave Spokane WA",
    ]


@pytest.fixture
def three_locations():
    """Pre-geocoded locations so network is never needed for solver/matrix tests."""
    return [
        {"address": "123 Main St Spokane WA",   "lat": 47.6588, "lng": -117.4260},
        {"address": "456 Elm St Spokane WA",    "lat": 47.6601, "lng": -117.4200},
        {"address": "789 Oak Ave Spokane WA",   "lat": 47.6615, "lng": -117.4150},
    ]


@pytest.fixture
def three_matrix():
    """Synthetic 3×3 duration matrix (seconds) matching three_locations."""
    return [
        [0,   300, 600],
        [300,   0, 350],
        [600, 350,   0],
    ]


@pytest.fixture
def null_location_list():
    """Locations where geocoding failed (lat/lng = None)."""
    return [
        {"address": "Nowhere Land",   "lat": None, "lng": None},
        {"address": "Also Nowhere",   "lat": None, "lng": None},
    ]
