#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
solver.py — TSP/VRP route solver for OnTrack.

Primary solver: Google OR-Tools (desktop/Linux/Windows)
Fallback solver: nearest-neighbor heuristic (Android/p4a — no OR-Tools recipe)

The module auto-selects based on availability.
Force a backend with: solve_tsp(..., force_backend="ortools"|"nn")
"""
from __future__ import annotations

from dataclasses import dataclass, field

try:
    from ontrack import solve_greedy as _solve_greedy_rs  # type: ignore[import-not-found]
    _HAS_RUST = True
except ImportError:
    _HAS_RUST = False

try:
    from ortools.constraint_solver import routing_enums_pb2, pywrapcp  # type: ignore[import-not-found]
    ORTOOLS_AVAILABLE = True
except ImportError:
    ORTOOLS_AVAILABLE = False


@dataclass
class RouteResult:
    ordered_addresses: list[str]
    ordered_indices: list[int]
    total_duration_seconds: float
    dropped_nodes: list[int] = field(default_factory=list)
    backend_used: str = "unknown"


def _nn_solve(
    locations: list[dict],
    matrix: list[list[float]],
    start: int = 0,
) -> RouteResult:
    """
    Greedy nearest-neighbour TSP heuristic.
    O(n²) — acceptable for typical field routes (≤ 50 stops).
    Delegates to Rust extension when available for better performance.
    """
    n = len(locations)

    if _HAS_RUST:
        flat = [matrix[i][j] for i in range(n) for j in range(n)]
        order = _solve_greedy_rs(flat, n)
        total = sum(matrix[order[i]][order[i + 1]] for i in range(len(order) - 1))
        return RouteResult(
            ordered_addresses=[locations[i]["address"] for i in order],
            ordered_indices=list(order),
            total_duration_seconds=total,
            dropped_nodes=[i for i in range(n) if i not in order],
            backend_used="nearest-neighbor-rust",
        )

    visited = [False] * n
    order = [start]
    visited[start] = True
    total = 0.0

    for _ in range(n - 1):
        current = order[-1]
        best_cost = float("inf")
        best_next = -1
        for j in range(n):
            if not visited[j] and matrix[current][j] < best_cost:
                best_cost = matrix[current][j]
                best_next = j
        if best_next == -1:
            break
        visited[best_next] = True
        order.append(best_next)
        total += best_cost

    return RouteResult(
        ordered_addresses=[locations[i]["address"] for i in order],
        ordered_indices=order,
        total_duration_seconds=total,
        dropped_nodes=[i for i in range(n) if i not in order],
        backend_used="nearest-neighbor",
    )


def _scale_matrix(matrix: list[list[float]], scale: int = 1) -> list[list[int]]:
    return [[int(matrix[i][j] / scale) for j in range(len(matrix))] for i in range(len(matrix))]


def _ortools_solve(
    locations: list[dict],
    matrix: list[list[float]],
    depot_index: int = 0,
    num_vehicles: int = 1,
    max_duration_seconds: int | None = None,
    time_limit_seconds: int = 30,
    scale: int = 1,
) -> RouteResult:
    n = len(locations)
    int_matrix = _scale_matrix(matrix, scale)
    manager = pywrapcp.RoutingIndexManager(n, num_vehicles, depot_index)
    routing = pywrapcp.RoutingModel(manager)

    def transit_callback(fi, ti):
        return int_matrix[manager.IndexToNode(fi)][manager.IndexToNode(ti)]

    cb_idx = routing.RegisterTransitCallback(transit_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(cb_idx)

    dim_name = "Duration"
    max_route = (
        int(max_duration_seconds / scale)
        if max_duration_seconds
        else int(sum(int_matrix[i][j] for i in range(n) for j in range(n)))
    )
    routing.AddDimension(cb_idx, 0, max_route, True, dim_name)

    penalty = max_route * 10
    for node in range(1, n):
        routing.AddDisjunction([manager.NodeToIndex(node)], penalty)

    sp = pywrapcp.DefaultRoutingSearchParameters()
    sp.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    sp.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    sp.time_limit.seconds = time_limit_seconds
    sp.log_search = False

    solution = routing.SolveWithParameters(sp)
    if not solution:
        raise RuntimeError("OR-Tools could not find a feasible solution.")

    all_indices: list[int] = []
    for v in range(num_vehicles):
        idx = routing.Start(v)
        while not routing.IsEnd(idx):
            all_indices.append(manager.IndexToNode(idx))
            idx = solution.Value(routing.NextVar(idx))

    time_dim = routing.GetDimensionOrDie(dim_name)
    total = solution.Value(time_dim.CumulVar(routing.End(0))) * scale

    dropped = []
    for node in range(routing.Size()):
        if routing.IsStart(node) or routing.IsEnd(node):
            continue
        if solution.Value(routing.NextVar(node)) == node:
            dropped.append(manager.IndexToNode(node))

    return RouteResult(
        ordered_addresses=[locations[i]["address"] for i in all_indices],
        ordered_indices=all_indices,
        total_duration_seconds=float(total),
        dropped_nodes=dropped,
        backend_used="ortools",
    )


def solve_tsp(
    locations: list[dict],
    matrix: list[list[float]],
    depot_index: int = 0,
    num_vehicles: int = 1,
    max_duration_seconds: int | None = None,
    time_limit_seconds: int = 30,
    scale: int = 1,
    force_backend: str | None = None,
) -> RouteResult:
    """
    Solve the TSP for the given locations and distance/duration matrix.

    Args:
        locations:             Geocoded dicts from geocoder.geocode_addresses().
        matrix:                NxN cost matrix from matrix.build_distance_matrix().
        depot_index:           Starting location index (0 = first in list).
        num_vehicles:          1 = TSP, >1 = VRP.
        max_duration_seconds:  Optional hard cap per vehicle.
        time_limit_seconds:    OR-Tools search budget.
        scale:                 Divide matrix by this before handing to OR-Tools.
        force_backend:         "ortools" | "nn" | None (auto).

    Returns:
        RouteResult with ordered stops and total duration.
    """
    n = len(locations)
    if n == 0:
        raise ValueError("No locations provided.")
    if len(matrix) != n or any(len(row) != n for row in matrix):
        raise ValueError(
            f"Matrix shape {len(matrix)}×{len(matrix[0]) if matrix else 0} "
            f"does not match {n} locations."
        )
    if not (0 <= depot_index < n):
        raise ValueError(f"depot_index {depot_index} out of range [0, {n}).")

    use_ortools = ORTOOLS_AVAILABLE and force_backend != "nn"
    if force_backend == "ortools" and not ORTOOLS_AVAILABLE:
        raise RuntimeError("OR-Tools not installed. Cannot force 'ortools' backend.")

    if use_ortools:
        return _ortools_solve(
            locations, matrix, depot_index, num_vehicles,
            max_duration_seconds, time_limit_seconds, scale,
        )
    return _nn_solve(locations, matrix, depot_index)


def solve_open_tsp(
    locations: list[dict],
    matrix: list[list[float]],
    start_index: int = 0,
    **kwargs,
) -> RouteResult:
    """
    Open TSP — driver does not return to origin.
    Uses a zero-cost dummy sink node.
    """
    n = len(locations)
    open_matrix = [row + [0] for row in matrix] + [[0] * (n + 1)]
    dummy = {"address": "__end__", "lat": None, "lng": None}
    result = solve_tsp(locations + [dummy], open_matrix, depot_index=start_index, **kwargs)
    result.ordered_addresses = [a for a in result.ordered_addresses if a != "__end__"]
    result.ordered_indices = [i for i in result.ordered_indices if i != n]
    return result

