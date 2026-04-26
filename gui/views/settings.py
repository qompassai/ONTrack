#!/usr/bin/env python3
"""
gui/views/settings.py — API keys, preferences, and about screen.
"""

from __future__ import annotations
import os

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox

TDS_BLUE    = "#0057A8"
TDS_NAVY    = "#002855"
TDS_ORANGE  = "#F26522"
TDS_WHITE   = "#FFFFFF"
TDS_GRAY    = "#6B7280"
TDS_SURFACE = "#1A2535"
TDS_BG      = "#111827"
TDS_GREEN   = "#22C55E"


class SettingsView(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=TDS_BG, corner_radius=0)
        self.app = app
        self._build()

    def on_show(self):
        self._reload_values()

    # ── Layout ─────────────────────────────────────────────────────────────

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Left column — API keys
        left = ctk.CTkScrollableFrame(self, fg_color=TDS_SURFACE, corner_radius=12)
        left.grid(row=0, column=0, padx=(16, 8), pady=16, sticky="nsew")
        left.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(left, text="API Configuration",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=TDS_WHITE,
                     ).pack(padx=16, pady=(14, 8), anchor="w")

        self._fields: dict[str, ctk.CTkEntry] = {}

        settings_defs = [
            (
                "GOOGLE_MAPS_API_KEY",
                "Google Maps API Key",
                "Required for Google geocoding, distance matrix,\nStreet View Static API, and route accuracy.",
                "https://console.cloud.google.com/google/maps-apis/credentials",
            ),
            (
                "OSRM_BASE_URL",
                "OSRM Base URL",
                "Self-hosted OSRM server URL. Leave default to use\nthe free public router (slower, no SLA).",
                None,
            ),
            (
                "ARCGIS_ITEM_ID",
                "ArcGIS Web Map Item ID",
                "Your ArcGIS Online Web Map item ID for FieldMaps\ndeep links. Found in the map's URL on ArcGIS Online.",
                "https://www.arcgis.com/home/content.html",
            ),
        ]

        for env_key, label, hint, link in settings_defs:
            self._add_field(left, env_key, label, hint, link)

        # Save button
        ctk.CTkButton(
            left, text="💾 Save Settings",
            height=42, fg_color=TDS_BLUE, hover_color=TDS_NAVY,
            text_color=TDS_WHITE, font=ctk.CTkFont(size=14, weight="bold"),
            corner_radius=8, command=self._save,
        ).pack(padx=16, pady=(16, 8), fill="x")

        self._save_status = tk.StringVar(value="")
        ctk.CTkLabel(left, textvariable=self._save_status,
                     font=ctk.CTkFont(size=12), text_color=TDS_GREEN,
                     ).pack(padx=16, pady=(0, 16), anchor="w")

        # Right column — about + tips
        right = ctk.CTkScrollableFrame(self, fg_color=TDS_SURFACE, corner_radius=12)
        right.grid(row=0, column=1, padx=(8, 16), pady=16, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(right, text="About OnTrack",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=TDS_WHITE,
                     ).pack(padx=16, pady=(14, 6), anchor="w")

        about_text = (
            "OnTrack v2.0  ·  TDS Telecom Internal\n"
            "Field Route Optimizer for service technicians.\n\n"
            "Route solver: OR-Tools TSP/VRP (desktop)\n"
            "               Nearest-neighbor (Android)\n\n"
            "Distance backends:\n"
            "  • OSRM (free, no API key)\n"
            "  • Google Distance Matrix (API key required)\n"
            "  • Haversine straight-line fallback\n\n"
            "Geocoding:\n"
            "  • Nominatim / OpenStreetMap (free)\n"
            "  • Google Geocoding (API key required)\n\n"
            "Map integrations:\n"
            "  • Google Maps (web + app launch)\n"
            "  • ArcGIS FieldMaps deep link\n"
            "  • Waze navigation deep link\n"
            "  • Google Street View preview\n"
        )
        ctk.CTkLabel(right, text=about_text,
                     font=ctk.CTkFont(size=12), text_color="#C7D9F0",
                     justify="left",
                     ).pack(padx=16, pady=(0, 12), anchor="w")

        ctk.CTkLabel(right, text="Quick Tips",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=TDS_WHITE,
                     ).pack(padx=16, pady=(4, 4), anchor="w")

        tips = (
            "• Add your Google Maps API Key to enable Street\n"
            "  View images and improved rural geocoding.\n\n"
            "• Set ARCGIS_ITEM_ID to open the correct web map\n"
            "  when launching ArcGIS FieldMaps.\n\n"
            "• Use 'Open route type' for field routes that don't\n"
            "  need to return to the starting point.\n\n"
            "• For large routes (20+ stops) use the '📂 Load File'\n"
            "  option on the New Route screen with a CSV.\n\n"
            "• The solver time limit controls route quality:\n"
            "  longer = better routes, but slower to compute.\n\n"
            "• Settings are saved to a local .env file and loaded\n"
            "  automatically on next launch."
        )
        ctk.CTkLabel(right, text=tips,
                     font=ctk.CTkFont(size=12), text_color="#9DB8D6",
                     justify="left",
                     ).pack(padx=16, pady=(0, 16), anchor="w")

    def _add_field(self, parent, env_key: str, label: str, hint: str, link: str | None):
        frame = ctk.CTkFrame(parent, fg_color="#243044", corner_radius=8)
        frame.pack(padx=16, pady=6, fill="x")
        frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(frame, text=label,
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=TDS_WHITE,
                     ).grid(row=0, column=0, padx=12, pady=(10, 2), sticky="w")

        ctk.CTkLabel(frame, text=hint,
                     font=ctk.CTkFont(size=11), text_color=TDS_GRAY,
                     justify="left",
                     ).grid(row=1, column=0, padx=12, pady=(0, 4), sticky="w")

        entry = ctk.CTkEntry(
            frame, height=36,
            fg_color="#1A2535", border_color=TDS_BLUE, text_color=TDS_WHITE,
            show="•" if "KEY" in env_key or "TOKEN" in env_key else "",
        )
        entry.grid(row=2, column=0, padx=12, pady=(0, 4), sticky="ew")
        self._fields[env_key] = entry

        btn_row = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row.grid(row=3, column=0, padx=12, pady=(0, 10), sticky="w")

        if link:
            ctk.CTkButton(
                btn_row, text="🔗 Get key →", width=100, height=26,
                fg_color="transparent", hover_color="#1A2535",
                text_color=TDS_BLUE, font=ctk.CTkFont(size=11),
                command=lambda u=link: __import__("webbrowser").open(u),
            ).pack(side="left", padx=(0, 8))

        # Toggle show/hide for secret fields
        if "KEY" in env_key or "TOKEN" in env_key:
            def _toggle(e=entry):
                e.configure(show="" if e.cget("show") else "•")
            ctk.CTkButton(
                btn_row, text="👁 Show/Hide", width=100, height=26,
                fg_color="transparent", hover_color="#1A2535",
                text_color=TDS_GRAY, font=ctk.CTkFont(size=11),
                command=_toggle,
            ).pack(side="left")

    def _reload_values(self):
        """Load current .env values into form fields."""
        env_path = _find_env()
        env_vals = _parse_env(env_path) if env_path else {}

        defaults = {
            "GOOGLE_MAPS_API_KEY": "",
            "OSRM_BASE_URL": "http://router.project-osrm.org",
            "ARCGIS_ITEM_ID": "",
        }
        for key, entry in self._fields.items():
            val = env_vals.get(key) or os.getenv(key, defaults.get(key, ""))
            entry.delete(0, tk.END)
            entry.insert(0, val)

    def _save(self):
        env_path = _find_env() or _default_env_path()
        vals = {k: e.get().strip() for k, e in self._fields.items()}
        _write_env(env_path, vals)

        # Reload into os.environ so changes take effect immediately
        for k, v in vals.items():
            if v:
                os.environ[k] = v
            elif k in os.environ:
                del os.environ[k]

        # Re-load settings module
        import importlib
        import config.settings as cs
        importlib.reload(cs)

        self._save_status.set("✓ Settings saved to .env")
        self.after(3000, lambda: self._save_status.set(""))


# ── .env helpers ───────────────────────────────────────────────────────────

def _find_env() -> str | None:
    candidates = [
        os.path.join(os.path.dirname(__file__), "..", "..", ".env"),
        os.path.expanduser("~/.ontrack.env"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return os.path.realpath(p)
    return None


def _default_env_path() -> str:
    base = os.path.join(os.path.dirname(__file__), "..", "..")
    return os.path.realpath(os.path.join(base, ".env"))


def _parse_env(path: str) -> dict:
    result = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                result[k.strip()] = v.strip().strip('"').strip("'")
    return result


def _write_env(path: str, vals: dict):
    existing = _parse_env(path) if os.path.exists(path) else {}
    existing.update(vals)
    with open(path, "w") as f:
        for k, v in existing.items():
            f.write(f'{k}="{v}"\n')
