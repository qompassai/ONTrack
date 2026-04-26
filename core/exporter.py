#!/usr/bin/env python3
"""
exporter.py — Route export and external map integration for OnTrack.

Provides:
  - CSV export
  - Google Maps directions URL (works in browser + launches app on mobile)
  - ArcGIS FieldMaps deep link (opens Field Maps to a searched location)
  - Google Street View Static API URL (embeddable image URL)
  - Waze navigation deep link
"""

from __future__ import annotations
import csv
import urllib.parse


# ── CSV export ─────────────────────────────────────────────────────────────

def export_csv(ordered_addresses: list[str], output_path: str) -> None:
    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["stop", "address"])
        for i, addr in enumerate(ordered_addresses, 1):
            writer.writerow([i, addr])


# ── Google Maps URLs ───────────────────────────────────────────────────────

def build_maps_url(ordered_addresses: list[str]) -> str:
    """
    Build a Google Maps Directions URL with all addresses as waypoints.
    Works universally across browser / Android / iOS — launches the Maps app on mobile.
    Supports up to 9 waypoints (10 total stops) per Google's URL scheme limit.
    """
    if not ordered_addresses:
        return "https://www.google.com/maps/dir/?api=1"
    if len(ordered_addresses) == 1:
        enc = urllib.parse.quote_plus(ordered_addresses[0])
        return f"https://www.google.com/maps/dir/?api=1&destination={enc}&travelmode=driving"

    origin = urllib.parse.quote_plus(ordered_addresses[0])
    destination = urllib.parse.quote_plus(ordered_addresses[-1])
    base = f"https://www.google.com/maps/dir/?api=1&origin={origin}&destination={destination}&travelmode=driving"

    waypoints = ordered_addresses[1:-1]
    if waypoints:
        wp_str = urllib.parse.quote("|".join(waypoints), safe="")
        base += f"&waypoints={wp_str}"

    return base


def build_maps_url_chunked(ordered_addresses: list[str]) -> list[str]:
    """
    For routes with > 10 stops, split into multiple Google Maps URLs (max 10 per URL).
    Returns a list of URLs to open in sequence.
    """
    chunk_size = 10
    chunks = [ordered_addresses[i:i + chunk_size] for i in range(0, len(ordered_addresses), chunk_size)]
    return [build_maps_url(chunk) for chunk in chunks]


# ── Street View Static API ─────────────────────────────────────────────────

def build_streetview_url(
    lat: float | None,
    lng: float | None,
    address: str | None = None,
    api_key: str = "",
    width: int = 640,
    height: int = 400,
    heading: int | None = None,
    pitch: int = 0,
    fov: int = 90,
) -> str:
    """
    Build a Google Street View Static API image URL.

    If lat/lng are provided they take precedence over address string.
    Returns a URL that resolves to a JPEG image.
    Requires a Google Maps API key with Street View Static API enabled.
    """
    params: dict = {
        "size": f"{width}x{height}",
        "pitch": pitch,
        "fov": fov,
        "key": api_key,
    }
    if lat is not None and lng is not None:
        params["location"] = f"{lat},{lng}"
    elif address:
        params["location"] = address
    else:
        raise ValueError("Either lat/lng or address must be provided.")

    if heading is not None:
        params["heading"] = heading

    return "https://maps.googleapis.com/maps/api/streetview?" + urllib.parse.urlencode(params)


def build_streetview_embed_url(lat: float, lng: float) -> str:
    """
    Interactive Street View embed URL (use in <iframe> or webview).
    Does not require an API key for basic usage.
    """
    return f"https://www.google.com/maps/@{lat},{lng},3a,90y,0h,90t/data=!3m4!1e1!3m2!1s!2e0"


# ── ArcGIS FieldMaps deep link ─────────────────────────────────────────────

def build_fieldmaps_url(
    address: str,
    lat: float | None = None,
    lng: float | None = None,
    item_id: str | None = None,
    scale: int = 2000,
) -> str:
    """
    Build an ArcGIS FieldMaps deep link that opens Field Maps
    and centers/searches on the given address or coordinate.

    Args:
        address:  The address string to search for in Field Maps.
        lat:      Optional latitude for center parameter.
        lng:      Optional longitude for center parameter.
        item_id:  Optional ArcGIS Online Web Map item ID to open a specific map.
        scale:    Map scale (default 2000 = street level).

    Returns:
        Deep link URL: https://fieldmaps.arcgis.app?...
    """
    params: dict[str, str] = {
        "search": urllib.parse.quote_plus(address),
    }
    if item_id:
        params["itemID"] = item_id
    if lat is not None and lng is not None:
        params["center"] = f"{lat},{lng}"
        params["scale"] = str(scale)

    return "https://fieldmaps.arcgis.app?" + "&".join(f"{k}={v}" for k, v in params.items())


# ── Waze deep link ─────────────────────────────────────────────────────────

def build_waze_url(lat: float, lng: float) -> str:
    return f"https://waze.com/ul?ll={lat},{lng}&navigate=yes&zoom=17"


# ── Route summary ──────────────────────────────────────────────────────────

def format_duration(seconds: float) -> str:
    """Format seconds into human-readable h m string."""
    mins = int(seconds // 60)
    if mins < 60:
        return f"{mins} min"
    h = mins // 60
    m = mins % 60
    return f"{h}h {m}m" if m else f"{h}h"
