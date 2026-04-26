#!/usr/bin/env python3
"""
geocoder.py — Address geocoding + current-location detection for OnTrack.

Backends:
  - Nominatim (free, default)
  - Google Geocoding API (optional, better rural accuracy)

Current location:
  - Desktop: ip-api.com (no perms needed)
  - Android: via Android GPS if PLATFORM == 'android'
"""

import os
import requests
from geopy.geocoders import Nominatim

geolocator = Nominatim(user_agent="ontrack-tds/1.0")

try:
    from android.permissions import request_permissions, Permission  # type: ignore
    PLATFORM = "android"
except ImportError:
    PLATFORM = "desktop"


# ── Address geocoding ──────────────────────────────────────────────────────

def geocode_address_nominatim(addr: str) -> dict:
    loc = geolocator.geocode(addr)
    if loc:
        return {"address": addr, "lat": loc.latitude, "lng": loc.longitude}
    return {"address": addr, "lat": None, "lng": None}


def geocode_address_google(addr: str, api_key: str) -> dict:
    resp = requests.get(
        "https://maps.googleapis.com/maps/api/geocode/json",
        params={"address": addr, "key": api_key},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    if data["status"] == "OK":
        loc = data["results"][0]["geometry"]["location"]
        return {"address": addr, "lat": loc["lat"], "lng": loc["lng"]}
    return {"address": addr, "lat": None, "lng": None}


def geocode_addresses(
    addresses: list[str],
    use_google: bool = False,
    google_api_key: str | None = None,
    progress_callback=None,
) -> list[dict]:
    """
    Convert a list of address strings to lat/lng dicts.

    Args:
        addresses:         List of address strings.
        use_google:        Use Google Geocoding API instead of Nominatim.
        google_api_key:    Required when use_google=True.
        progress_callback: Optional callable(done, total) for UI progress bars.

    Returns:
        List of {"address": str, "lat": float|None, "lng": float|None}
    """
    results = []
    key = google_api_key or os.getenv("GOOGLE_MAPS_API_KEY", "")
    for i, addr in enumerate(addresses):
        if use_google and key:
            result = geocode_address_google(addr, key)
        else:
            result = geocode_address_nominatim(addr)
        results.append(result)
        if progress_callback:
            progress_callback(i + 1, len(addresses))
    return results


# ── Current location ───────────────────────────────────────────────────────

def get_current_location() -> dict | None:
    """
    Return the device's current location as {"lat": float, "lng": float, "address": "Current Location"}.
    On Android uses GPS; on desktop falls back to IP geolocation.
    Returns None if location cannot be determined.
    """
    if PLATFORM == "android":
        return _android_location()
    return _ip_location()


def _ip_location() -> dict | None:
    """Coarse location via IP (desktop fallback, no API key needed)."""
    try:
        resp = requests.get("http://ip-api.com/json/?fields=lat,lon,status", timeout=5)
        data = resp.json()
        if data.get("status") == "success":
            return {"address": "Current Location", "lat": data["lat"], "lng": data["lon"]}
    except Exception:
        pass
    return None


def _android_location() -> dict | None:
    """GPS location on Android via plyer."""
    try:
        from plyer import gps  # type: ignore
        # plyer GPS is event-driven; for a simple blocking call, use Android directly
        from jnius import autoclass  # type: ignore
        Context = autoclass("android.content.Context")
        LocationManager = autoclass("android.location.LocationManager")
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        activity = PythonActivity.mActivity
        lm = activity.getSystemService(Context.LOCATION_SERVICE)
        loc = lm.getLastKnownLocation(LocationManager.GPS_PROVIDER)
        if loc is None:
            loc = lm.getLastKnownLocation(LocationManager.NETWORK_PROVIDER)
        if loc:
            return {"address": "Current Location", "lat": loc.getLatitude(), "lng": loc.getLongitude()}
    except Exception:
        pass
    # Fall back to IP on Android if GPS unavailable
    return _ip_location()
