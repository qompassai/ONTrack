"""
test_matrix.py — unit tests for core/matrix.py

All HTTP calls are mocked. Covers:
  - _haversine() geometry correctness (known distances)
  - build_distance_matrix() backend dispatch
  - haversine backend: shape, diagonal zeros, symmetry
  - osrm backend: happy path, OSRM error code, request failure
  - google backend: happy path, missing API key, google API error
  - Invalid backend raises ValueError
  - All-None locations raises ValueError
  - Partially-None locations uses only resolved points
"""

import math
import pytest
import requests
from unittest.mock import MagicMock, patch

from core.matrix import (
    _haversine,
    _haversine_matrix,
    build_distance_matrix,
    OSRM_PUBLIC,
)


# ── _haversine ─────────────────────────────────────────────────────────────

class TestHaversine:
    def test_same_point_is_zero(self):
        assert _haversine(47.0, -117.0, 47.0, -117.0) == 0.0

    def test_known_distance(self):
        # Spokane WA (47.6588, -117.4260) to Coeur d'Alene ID (47.6777, -116.7805)
        # Great-circle ≈ 48 km (straight line, not road distance)
        dist = _haversine(47.6588, -117.4260, 47.6777, -116.7805)
        assert 45_000 < dist < 55_000, f"Expected ~48 km great-circle, got {dist:.0f} m"

    def test_symmetry(self):
        d1 = _haversine(47.6588, -117.4260, 47.6777, -116.7805)
        d2 = _haversine(47.6777, -116.7805, 47.6588, -117.4260)
        assert math.isclose(d1, d2, rel_tol=1e-9)

    def test_positive(self):
        assert _haversine(0, 0, 1, 1) > 0


# ── haversine backend ──────────────────────────────────────────────────────

class TestHaversineBackend:
    def test_shape(self, three_locations):
        m = build_distance_matrix(three_locations, backend="haversine")
        n = len(three_locations)
        assert len(m) == n
        assert all(len(row) == n for row in m)

    def test_diagonal_zero(self, three_locations):
        m = build_distance_matrix(three_locations, backend="haversine")
        for i in range(len(three_locations)):
            assert m[i][i] == 0.0

    def test_symmetry(self, three_locations):
        m = build_distance_matrix(three_locations, backend="haversine")
        n = len(three_locations)
        for i in range(n):
            for j in range(n):
                assert math.isclose(m[i][j], m[j][i], rel_tol=1e-9)

    def test_values_are_positive(self, three_locations):
        m = build_distance_matrix(three_locations, backend="haversine")
        n = len(three_locations)
        for i in range(n):
            for j in range(n):
                if i != j:
                    assert m[i][j] > 0


# ── OSRM backend ───────────────────────────────────────────────────────────

def _osrm_response(n):
    """Minimal successful OSRM Table response."""
    durations = [[float(abs(i - j) * 300) for j in range(n)] for i in range(n)]
    mock = MagicMock()
    mock.raise_for_status = MagicMock()
    mock.json.return_value = {"code": "Ok", "durations": durations}
    return mock


class TestOSRMBackend:
    def test_happy_path(self, three_locations):
        with patch("core.matrix.requests.get", return_value=_osrm_response(3)) as mock_get:
            m = build_distance_matrix(three_locations, backend="osrm")
        mock_get.assert_called_once()
        assert len(m) == 3
        assert all(len(row) == 3 for row in m)

    def test_osrm_error_code_raises(self, three_locations):
        bad = MagicMock()
        bad.raise_for_status = MagicMock()
        bad.json.return_value = {"code": "InvalidQuery", "message": "bad coords"}
        with patch("core.matrix.requests.get", return_value=bad):
            with pytest.raises(RuntimeError, match="OSRM error"):
                build_distance_matrix(three_locations, backend="osrm")

    def test_http_failure_raises(self, three_locations):
        with patch("core.matrix.requests.get", side_effect=requests.RequestException("timeout")):
            with pytest.raises(requests.RequestException):
                build_distance_matrix(three_locations, backend="osrm")

    def test_custom_osrm_url(self, three_locations):
        custom_url = "http://localhost:5000"
        with patch("core.matrix.requests.get", return_value=_osrm_response(3)) as mock_get:
            build_distance_matrix(three_locations, backend="osrm", osrm_url=custom_url)
        call_url = mock_get.call_args[0][0]
        assert call_url.startswith(custom_url)


# ── Google backend ─────────────────────────────────────────────────────────

def _google_response(n, status="OK"):
    rows = [
        {
            "elements": [
                {"status": "OK", "duration": {"value": abs(i - j) * 300}}
                for j in range(n)
            ]
        }
        for i in range(n)
    ]
    mock = MagicMock()
    mock.raise_for_status = MagicMock()
    mock.json.return_value = {"status": status, "rows": rows}
    return mock


class TestGoogleBackend:
    def test_happy_path(self, three_locations):
        with patch("core.matrix.requests.get", return_value=_google_response(3)):
            m = build_distance_matrix(
                three_locations, backend="google", google_api_key="FAKE"
            )
        assert len(m) == 3

    def test_missing_key_raises(self, three_locations, monkeypatch):
        monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
        with pytest.raises(ValueError, match="API key"):
            build_distance_matrix(three_locations, backend="google")

    def test_google_api_error_raises(self, three_locations):
        with patch("core.matrix.requests.get", return_value=_google_response(3, status="REQUEST_DENIED")):
            with pytest.raises(RuntimeError, match="Google API error"):
                build_distance_matrix(
                    three_locations, backend="google", google_api_key="FAKE"
                )

    def test_env_key_used(self, three_locations, monkeypatch):
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "ENV_KEY")
        with patch("core.matrix.requests.get", return_value=_google_response(3)) as mock_get:
            build_distance_matrix(three_locations, backend="google")
        call_kwargs = mock_get.call_args[1]
        assert call_kwargs["params"]["key"] == "ENV_KEY"


# ── Validation ─────────────────────────────────────────────────────────────

class TestBuildDistanceMatrixValidation:
    def test_invalid_backend_raises(self, three_locations):
        with pytest.raises(ValueError, match="backend must be one of"):
            build_distance_matrix(three_locations, backend="magic")

    def test_all_none_locations_raise(self, null_location_list):
        with pytest.raises(ValueError, match="No geocoded locations"):
            build_distance_matrix(null_location_list, backend="haversine")

    def test_partial_none_uses_resolved(self):
        mixed = [
            {"address": "A",   "lat": 47.6588, "lng": -117.426},
            {"address": "Bad", "lat": None,    "lng": None},
            {"address": "C",   "lat": 47.6615, "lng": -117.415},
        ]
        m = build_distance_matrix(mixed, backend="haversine")
        # Only 2 resolved points → 2×2 matrix
        assert len(m) == 2
        assert all(len(row) == 2 for row in m)
