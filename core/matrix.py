#!/usr/bin/env python3
"""
matrix.py — Distance matrix builder for OnTrack route optimization.
Supports OSRM (default, free) and Google Maps Distance Matrix API.
"""

import os
import math
import requests


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Straight-line distance in meters between two lat/lng points."""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


OSRM_PUBLIC = 'http://router.project-osrm.org'


def _osrm_matrix(
    locations: list[dict], base_url: str = OSRM_PUBLIC
) -> list[list[float]]:
    """
    Build an NxN duration matrix (seconds) via OSRM Table service.
    locations: list of {"address": str, "lat": float, "lng": float}
    """
    coords = ';'.join(f'{p["lng"]},{p["lat"]}' for p in locations)
    url = f'{base_url}/table/v1/driving/{coords}'
    params = {'annotations': 'duration,distance'}
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data.get('code') != 'Ok':
        raise RuntimeError(f'OSRM error: {data.get("message", "unknown")}')
    return data['durations']




def _google_matrix(locations: list[dict], api_key: str) -> list[list[float]]:
    """
    Build an NxN duration matrix (seconds) via Google Distance Matrix API.
    Batches in groups of 10 (API row/col limit).
    """
    addrs = [p['address'] for p in locations]
    n = len(addrs)
    matrix = [[0.0] * n for _ in range(n)]
    batch = 10

    for i in range(0, n, batch):
        origins = '|'.join(addrs[i : i + batch])
        for j in range(0, n, batch):
            dests = '|'.join(addrs[j : j + batch])
            resp = requests.get(
                'https://maps.googleapis.com/maps/api/distancematrix/json',
                params={'origins': origins, 'destinations': dests, 'key': api_key},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            if data['status'] != 'OK':
                raise RuntimeError(f'Google API error: {data["status"]}')
            for ri, row in enumerate(data['rows']):
                for ci, elem in enumerate(row['elements']):
                    val = (
                        elem['duration']['value']
                        if elem['status'] == 'OK'
                        else _haversine(
                            locations[i + ri]['lat'],
                            locations[i + ri]['lng'],
                            locations[j + ci]['lat'],
                            locations[j + ci]['lng'],
                        )
                    )
                    matrix[i + ri][j + ci] = val
    return matrix

def _haversine_matrix(locations: list[dict]) -> list[list[float]]:
    n = len(locations)
    return [
        [
            _haversine(
                locations[i]['lat'],
                locations[i]['lng'],
                locations[j]['lat'],
                locations[j]['lng'],
            )
            for j in range(n)
        ]
        for i in range(n)
    ]


def build_distance_matrix(
    locations: list[dict],
    backend: str = 'osrm',
    osrm_url: str = OSRM_PUBLIC,
    google_api_key: str | None = None,
) -> list[list[float]]:
    """
    Build an NxN distance/duration matrix from geocoded locations.

    Args:
        locations:      Output of geocoder.geocode_addresses()
        backend:        "osrm" | "google" | "haversine"
        osrm_url:       OSRM base URL (override for self-hosted instance)
        google_api_key: Required when backend="google"; falls back to
                        GOOGLE_MAPS_API_KEY env var if None

    Returns:
        NxN list[list[float]] — durations in seconds (osrm/google)
        or straight-line meters (haversine)

    Raises:
        ValueError:  Invalid backend or missing API key
        RuntimeError: Upstream API failure
    """
    valid = {'osrm', 'google', 'haversine'}
    if backend not in valid:
        raise ValueError(f'backend must be one of {valid}, got {backend!r}')

    resolved = [loc for loc in locations if loc['lat'] is not None]
    if not resolved:
        raise ValueError('No geocoded locations available to build matrix.')

    if backend == 'osrm':
        return _osrm_matrix(resolved, base_url=osrm_url)

    if backend == 'google':
        key = google_api_key or os.getenv('GOOGLE_MAPS_API_KEY')
        if not key:
            raise ValueError(
                'Google backend requires an API key via google_api_key arg '
                'or GOOGLE_MAPS_API_KEY environment variable.'
            )
        return _google_matrix(resolved, api_key=key)

    return _haversine_matrix(resolved)
