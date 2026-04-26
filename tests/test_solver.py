"""
test_solver.py — unit tests for core/solver.py (OR-Tools TSP/VRP)

No network calls. Uses synthetic matrices.

Covers:
  - solve_tsp happy path: returns RouteResult, visits all nodes
  - depot always appears first
  - total_duration_seconds is non-negative
  - mismatched matrix raises ValueError
  - empty locations raises ValueError
  - bad depot_index raises ValueError
  - solve_open_tsp: dummy sink stripped from output
  - scale parameter: minute-resolution large matrices
  - _scale_matrix rounding
"""

import pytest
from core.solver import solve_tsp, solve_open_tsp, RouteResult, _scale_matrix


# ── _scale_matrix ──────────────────────────────────────────────────────────

class TestScaleMatrix:
    def test_no_scale(self):
        m = [[0, 300], [300, 0]]
        assert _scale_matrix(m, scale=1) == [[0, 300], [300, 0]]

    def test_minute_scale(self):
        m = [[0, 3600], [3600, 0]]
        assert _scale_matrix(m, scale=60) == [[0, 60], [60, 0]]

    def test_truncation_not_rounding(self):
        # int() truncates toward zero
        m = [[0, 299], [299, 0]]
        assert _scale_matrix(m, scale=60) == [[0, 4], [4, 0]]


# ── solve_tsp ─────────────────────────────────────────────────────────────

class TestSolveTSP:
    def test_happy_path(self, three_locations, three_matrix):
        result = solve_tsp(three_locations, three_matrix, time_limit_seconds=5)
        assert isinstance(result, RouteResult)
        assert len(result.ordered_addresses) > 0

    def test_visits_all_nodes(self, three_locations, three_matrix):
        result = solve_tsp(three_locations, three_matrix, time_limit_seconds=5)
        # All 3 addresses must appear in the route (no drops on a trivial 3-node graph)
        addr_set = set(result.ordered_addresses)
        expected = {loc["address"] for loc in three_locations}
        assert addr_set == expected

    def test_depot_is_first(self, three_locations, three_matrix):
        result = solve_tsp(three_locations, three_matrix, depot_index=0, time_limit_seconds=5)
        assert result.ordered_addresses[0] == three_locations[0]["address"]

    def test_nonzero_depot(self, three_locations, three_matrix):
        result = solve_tsp(three_locations, three_matrix, depot_index=2, time_limit_seconds=5)
        assert result.ordered_addresses[0] == three_locations[2]["address"]

    def test_total_duration_nonnegative(self, three_locations, three_matrix):
        result = solve_tsp(three_locations, three_matrix, time_limit_seconds=5)
        assert result.total_duration_seconds >= 0

    def test_dropped_nodes_is_list(self, three_locations, three_matrix):
        result = solve_tsp(three_locations, three_matrix, time_limit_seconds=5)
        assert isinstance(result.dropped_nodes, list)

    def test_five_node_route(self):
        """Slightly larger graph to exercise GLS heuristic."""
        n = 5
        locations = [
            {"address": f"Stop {i}", "lat": 47.65 + i * 0.01, "lng": -117.42 + i * 0.01}
            for i in range(n)
        ]
        matrix = [
            [0 if i == j else (abs(i - j) * 200) for j in range(n)]
            for i in range(n)
        ]
        result = solve_tsp(locations, matrix, time_limit_seconds=5)
        assert isinstance(result, RouteResult)
        assert len(result.ordered_addresses) >= 1

    def test_minute_scale(self, three_locations, three_matrix):
        """Scaling by 60 should still produce a valid result."""
        result = solve_tsp(three_locations, three_matrix, scale=60, time_limit_seconds=5)
        assert isinstance(result, RouteResult)

    def test_single_location(self):
        locs = [{"address": "Only Stop", "lat": 47.0, "lng": -117.0}]
        m = [[0]]
        result = solve_tsp(locs, m, time_limit_seconds=5)
        assert result.ordered_addresses == ["Only Stop"]


# ── Input validation ───────────────────────────────────────────────────────

class TestSolveTSPValidation:
    def test_empty_locations_raises(self):
        with pytest.raises(ValueError, match="No locations"):
            solve_tsp([], [], time_limit_seconds=5)

    def test_matrix_shape_mismatch_raises(self, three_locations):
        bad_matrix = [[0, 1], [1, 0]]  # 2×2 for 3 locations
        with pytest.raises(ValueError, match="Matrix shape"):
            solve_tsp(three_locations, bad_matrix, time_limit_seconds=5)

    def test_bad_depot_index_raises(self, three_locations, three_matrix):
        with pytest.raises(ValueError, match="depot_index"):
            solve_tsp(three_locations, three_matrix, depot_index=99, time_limit_seconds=5)

    def test_negative_depot_raises(self, three_locations, three_matrix):
        with pytest.raises(ValueError, match="depot_index"):
            solve_tsp(three_locations, three_matrix, depot_index=-1, time_limit_seconds=5)


# ── solve_open_tsp ─────────────────────────────────────────────────────────

class TestSolveOpenTSP:
    def test_returns_route_result(self, three_locations, three_matrix):
        result = solve_open_tsp(three_locations, three_matrix, time_limit_seconds=5)
        assert isinstance(result, RouteResult)

    def test_dummy_sink_stripped(self, three_locations, three_matrix):
        result = solve_open_tsp(three_locations, three_matrix, time_limit_seconds=5)
        assert "__end__" not in result.ordered_addresses

    def test_no_dummy_index(self, three_locations, three_matrix):
        n = len(three_locations)
        result = solve_open_tsp(three_locations, three_matrix, time_limit_seconds=5)
        assert n not in result.ordered_indices  # dummy was index n

    def test_start_index(self, three_locations, three_matrix):
        result = solve_open_tsp(three_locations, three_matrix, start_index=1, time_limit_seconds=5)
        assert isinstance(result, RouteResult)
