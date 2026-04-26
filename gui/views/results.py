#!/usr/bin/env python3
"""
gui/views/results.py — Route results, map preview, and map launch.

Features:
  - Ordered stop table (stop #, address, ETA)
  - Add extra stop inline, remove stop, reorder stop
  - Re-solve with modified stop list
  - Location preview panel:
      • Always: free OSM map tile (no API key)
      • With Google key: Street View Static image
  - Launch in Google Maps (all stops as waypoints, no key needed)
  - Launch in ArcGIS FieldMaps (per-stop deep link, no key needed)
  - Copy route as text / export CSV
  - Summary banner (stops, est. duration)
"""

from __future__ import annotations
import threading
import webbrowser
import math
import os
import io

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw, ImageFont
import requests

from core.exporter import (
    build_maps_url,
    build_maps_url_chunked,
    build_streetview_url,
    build_fieldmaps_url,
    build_waze_url,
    export_csv,
    format_duration,
)

TDS_BLUE    = "#0057A8"
TDS_NAVY    = "#002855"
TDS_ORANGE  = "#F26522"
TDS_WHITE   = "#FFFFFF"
TDS_GRAY    = "#6B7280"
TDS_SURFACE = "#1A2535"
TDS_BG      = "#111827"
TDS_GREEN   = "#22C55E"
TDS_RED     = "#EF4444"

OSM_TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
OSM_HEADERS  = {"User-Agent": "OnTrack-TDS/2.0 (field route optimizer)"}


def _latlon_to_tile(lat: float, lng: float, zoom: int) -> tuple[int, int]:
    x = int((lng + 180) / 360 * 2**zoom)
    y = int((1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * 2**zoom)
    return x, y


def _fetch_osm_tile(lat: float, lng: float, zoom: int = 16) -> Image.Image | None:
    """Fetch a single OSM tile and return a PIL Image, or None on failure."""
    try:
        x, y = _latlon_to_tile(lat, lng, zoom)
        url = OSM_TILE_URL.format(z=zoom, x=x, y=y)
        resp = requests.get(url, headers=OSM_HEADERS, timeout=6)
        resp.raise_for_status()
        return Image.open(io.BytesIO(resp.content)).convert("RGB")
    except Exception:
        return None


def _build_map_image(lat: float, lng: float, width: int = 300, height: int = 200) -> Image.Image:
    """
    Build a map preview image centred on lat/lng using OSM tiles (no API key).
    Fetches a 3×3 tile grid around the centre tile and stitches them,
    then crops to the requested pixel size with a red pin in the centre.
    """
    zoom = 16
    cx, cy = _latlon_to_tile(lat, lng, zoom)
    tile_size = 256

    # Fetch 3×3 grid around the centre tile
    canvas = Image.new("RGB", (tile_size * 3, tile_size * 3), (30, 40, 60))
    for dy in range(-1, 2):
        for dx in range(-1, 2):
            tile = _fetch_osm_tile.__wrapped__(lat, lng, zoom) if False else None
            try:
                url = OSM_TILE_URL.format(z=zoom, x=cx + dx, y=cy + dy)
                resp = requests.get(url, headers=OSM_HEADERS, timeout=6)
                resp.raise_for_status()
                tile = Image.open(io.BytesIO(resp.content)).convert("RGB")
            except Exception:
                tile = Image.new("RGB", (tile_size, tile_size), (30, 40, 60))
            canvas.paste(tile, ((dx + 1) * tile_size, (dy + 1) * tile_size))

    # Precise pixel offset of the lat/lng within the centre tile
    n = 2**zoom
    x_frac = (lng + 180) / 360 * n - cx  # 0..1 within tile
    lat_rad = math.radians(lat)
    y_frac = (1 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2 * n - cy

    pin_x = int(tile_size + x_frac * tile_size)
    pin_y = int(tile_size + y_frac * tile_size)

    # Crop around the pin
    left   = max(0, pin_x - width  // 2)
    top    = max(0, pin_y - height // 2)
    right  = left + width
    bottom = top  + height
    cropped = canvas.crop((left, top, right, bottom))

    # Draw a red pin circle
    draw = ImageDraw.Draw(cropped)
    px, py = pin_x - left, pin_y - top
    r = 8
    draw.ellipse([px - r, py - r, px + r, py + r], fill="#EF4444", outline="white", width=2)
    draw.ellipse([px - 3, py - 3, px + 3, py + 3], fill="white")

    return cropped


class ResultsView(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=TDS_BG, corner_radius=0)
        self.app = app
        self._sv_cache: dict[int, ImageTk.PhotoImage] = {}
        self._selected_idx: int | None = None
        self._build()

    def on_show(self):
        if self.app.route_result:
            self._populate()

    # ── Layout ─────────────────────────────────────────────────────────────

    def _build(self):
        self.grid_columnconfigure(0, weight=2, minsize=420)
        self.grid_columnconfigure(1, weight=1, minsize=320)
        self.grid_rowconfigure(1, weight=1)

        # ── Summary banner ──
        banner = ctk.CTkFrame(self, fg_color=TDS_NAVY, corner_radius=0, height=52)
        banner.grid(row=0, column=0, columnspan=2, sticky="ew")
        banner.grid_propagate(False)
        banner.grid_columnconfigure(1, weight=1)

        self._summary_var = tk.StringVar(value="No route loaded — go to New Route to start.")
        ctk.CTkLabel(banner, textvariable=self._summary_var,
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=TDS_WHITE).grid(row=0, column=0, padx=20, pady=0, sticky="w")

        action_bar = ctk.CTkFrame(banner, fg_color="transparent")
        action_bar.grid(row=0, column=2, padx=12, pady=8, sticky="e")

        for (text, color, cmd) in [
            ("🗺 Open in Maps",   TDS_BLUE,   self._open_in_maps),
            ("📐 ArcGIS FieldMaps", "#1A5F3F", self._open_fieldmaps_all),
            ("↩ Waze",            "#2563EB",  self._open_waze_first),
            ("💾 Export CSV",     "#374151",   self._export_csv),
        ]:
            ctk.CTkButton(
                action_bar, text=text, height=34, width=148,
                fg_color=color, hover_color=TDS_NAVY,
                text_color=TDS_WHITE, font=ctk.CTkFont(size=12),
                corner_radius=6, command=cmd,
            ).pack(side="left", padx=4)

        # ── Left: Stop table + inline edit ──
        left = ctk.CTkFrame(self, fg_color=TDS_SURFACE, corner_radius=12)
        left.grid(row=1, column=0, padx=(14, 7), pady=14, sticky="nsew")
        left.grid_rowconfigure(1, weight=1)
        left.grid_columnconfigure(0, weight=1)

        # Inline add stop
        add_row = ctk.CTkFrame(left, fg_color="transparent")
        add_row.grid(row=0, column=0, padx=12, pady=(12, 4), sticky="ew")
        add_row.grid_columnconfigure(0, weight=1)

        self.add_entry = ctk.CTkEntry(
            add_row, placeholder_text="Add a stop to the route…",
            height=36, fg_color="#243044", border_color=TDS_BLUE, text_color=TDS_WHITE)
        self.add_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.add_entry.bind("<Return>", lambda e: self._add_inline_stop())

        ctk.CTkButton(
            add_row, text="+ Add", width=68, height=36,
            fg_color=TDS_BLUE, hover_color=TDS_NAVY,
            command=self._add_inline_stop,
        ).grid(row=0, column=1)

        # Route table (canvas-scrolled)
        self.table_frame = ctk.CTkScrollableFrame(left, fg_color="#1A2535", corner_radius=8)
        self.table_frame.grid(row=1, column=0, padx=12, pady=(0, 8), sticky="nsew")
        self.table_frame.grid_columnconfigure(0, weight=0)   # stop #
        self.table_frame.grid_columnconfigure(1, weight=1)   # address
        self.table_frame.grid_columnconfigure(2, weight=0)   # actions

        # Column headers
        for col, (txt, w) in enumerate([("  #", 40), ("Address", 300), ("Actions", 100)]):
            ctk.CTkLabel(self.table_frame, text=txt,
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color="#9DB8D6", width=w, anchor="w",
                         ).grid(row=0, column=col, padx=(6, 4), pady=(6, 2), sticky="w")

        self._row_widgets: list[dict] = []  # track per-row widgets for refresh

        # ── Right: Street View + per-stop actions ──
        right = ctk.CTkFrame(self, fg_color=TDS_SURFACE, corner_radius=12)
        right.grid(row=1, column=1, padx=(7, 14), pady=14, sticky="nsew")
        right.grid_rowconfigure(2, weight=1)
        right.grid_columnconfigure(0, weight=1)

        # Panel header row
        preview_header = ctk.CTkFrame(right, fg_color="transparent")
        preview_header.grid(row=0, column=0, padx=14, pady=(14, 2), sticky="ew")
        preview_header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(preview_header, text="Location Preview",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=TDS_WHITE,
                     ).grid(row=0, column=0, sticky="w")

        # Small badge showing data source
        self._preview_source_var = tk.StringVar(value="OpenStreetMap")
        ctk.CTkLabel(preview_header, textvariable=self._preview_source_var,
                     font=ctk.CTkFont(size=10), text_color=TDS_GRAY,
                     ).grid(row=0, column=1, sticky="e", padx=(0, 2))

        self._sv_addr_var = tk.StringVar(value="Select a stop to preview")
        ctk.CTkLabel(right, textvariable=self._sv_addr_var,
                     font=ctk.CTkFont(size=11), text_color=TDS_GRAY,
                     wraplength=290,
                     ).grid(row=1, column=0, padx=16, pady=(0, 4), sticky="w")

        # Preview image canvas (OSM map tile by default, Street View if key present)
        self.sv_canvas = tk.Canvas(right, bg="#0D1421", highlightthickness=0,
                                   width=300, height=200)
        self.sv_canvas.grid(row=2, column=0, padx=14, pady=0, sticky="nsew")
        self._sv_msg_id = self.sv_canvas.create_text(
            150, 100, text="Select a stop\nto see its location",
            fill=TDS_GRAY, font=("Segoe UI", 12), justify="center",
        )

        # Per-stop action buttons
        sv_actions = ctk.CTkFrame(right, fg_color="transparent")
        sv_actions.grid(row=3, column=0, padx=14, pady=10, sticky="ew")

        ctk.CTkButton(
            sv_actions, text="🗺 Navigate", width=100, height=32,
            fg_color=TDS_BLUE, hover_color=TDS_NAVY, text_color=TDS_WHITE,
            command=self._open_maps_single,
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            sv_actions, text="📐 FieldMaps", width=100, height=32,
            fg_color="#1A5F3F", hover_color="#0F3D27", text_color=TDS_WHITE,
            command=self._open_fieldmaps_single,
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            sv_actions, text="🌐 Street View", width=110, height=32,
            fg_color="#374151", hover_color="#1F2937", text_color=TDS_WHITE,
            command=self._open_streetview_browser,
        ).pack(side="left")

        # Re-solve button
        ctk.CTkButton(
            right, text="⚡ Re-optimize Route",
            height=40, fg_color=TDS_ORANGE, hover_color="#D4541A",
            text_color=TDS_WHITE, font=ctk.CTkFont(size=13, weight="bold"),
            corner_radius=8, command=self._re_solve,
        ).grid(row=4, column=0, padx=14, pady=(4, 14), sticky="ew")

    # ── Populate table ─────────────────────────────────────────────────────

    def _populate(self):
        result = self.app.route_result
        if not result:
            return

        # Clear old rows
        for rw in self._row_widgets:
            for w in rw.values():
                try:
                    w.destroy()
                except Exception:
                    pass
        self._row_widgets.clear()
        self._sv_cache.clear()

        dur = format_duration(result.total_duration_seconds)
        n = len(result.ordered_addresses)
        self._summary_var.set(
            f"✓  {n} stops  ·  Est. {dur}  ·  Backend: {result.backend_used}"
        )

        for i, addr in enumerate(result.ordered_addresses):
            row = i + 1  # header is row 0
            bg = "#1A2535" if i % 2 == 0 else "#1F2D42"
            widgets = {}

            num_lbl = ctk.CTkLabel(
                self.table_frame, text=f"  {i+1}",
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=TDS_ORANGE, width=40, anchor="w",
            )
            num_lbl.grid(row=row, column=0, padx=(6, 2), pady=3, sticky="w")
            widgets["num"] = num_lbl

            addr_lbl = ctk.CTkLabel(
                self.table_frame, text=addr,
                font=ctk.CTkFont(size=12), text_color=TDS_WHITE,
                anchor="w", wraplength=320,
            )
            addr_lbl.grid(row=row, column=1, padx=(2, 4), pady=3, sticky="w")
            addr_lbl.bind("<Button-1>", lambda e, idx=i: self._select_stop(idx))
            addr_lbl.bind("<Enter>",    lambda e, lbl=addr_lbl: lbl.configure(text_color=TDS_ORANGE))
            addr_lbl.bind("<Leave>",    lambda e, lbl=addr_lbl: lbl.configure(text_color=TDS_WHITE))
            widgets["addr"] = addr_lbl

            act_frame = ctk.CTkFrame(self.table_frame, fg_color="transparent")
            act_frame.grid(row=row, column=2, padx=4, pady=2, sticky="e")

            del_btn = ctk.CTkButton(
                act_frame, text="✕", width=28, height=26,
                fg_color="#3B1A1A", hover_color=TDS_RED, text_color=TDS_WHITE,
                font=ctk.CTkFont(size=11),
                command=lambda idx=i: self._delete_stop(idx),
            )
            del_btn.pack(side="left", padx=2)
            widgets["del"] = del_btn

            up_btn = ctk.CTkButton(
                act_frame, text="▲", width=28, height=26,
                fg_color="#243044", hover_color=TDS_NAVY, text_color=TDS_WHITE,
                font=ctk.CTkFont(size=10),
                command=lambda idx=i: self._move_stop(idx, -1),
            )
            up_btn.pack(side="left", padx=2)

            dn_btn = ctk.CTkButton(
                act_frame, text="▼", width=28, height=26,
                fg_color="#243044", hover_color=TDS_NAVY, text_color=TDS_WHITE,
                font=ctk.CTkFont(size=10),
                command=lambda idx=i: self._move_stop(idx, +1),
            )
            dn_btn.pack(side="left", padx=2)

            widgets["act"] = act_frame
            self._row_widgets.append(widgets)

        # Auto-select first stop for Street View
        if result.ordered_addresses:
            self._select_stop(0)

    # ── Stop selection + Street View ───────────────────────────────────────

    def _select_stop(self, idx: int):
        result = self.app.route_result
        if not result or idx >= len(result.ordered_addresses):
            return
        self._selected_idx = idx
        addr = result.ordered_addresses[idx]
        self._sv_addr_var.set(f"Stop {idx+1}: {addr}")

        # Check location for this stop
        locs = self.app.locations
        lat, lng = None, None
        # Try to find matching geocoded location
        for loc in locs:
            if loc["address"] == addr:
                lat, lng = loc.get("lat"), loc.get("lng")
                break

        if idx in self._sv_cache:
            self._show_sv_image(self._sv_cache[idx])
        else:
            self._load_sv_image(idx, addr, lat, lng)

    def _load_sv_image(self, idx: int, addr: str, lat, lng):
        """
        Load a location preview image.
        Priority:
          1. OSM map tile (free, no key) — always attempted if lat/lng known
          2. Google Street View Static API — only if API key is configured
        Falls back to a plain text message if both fail.
        """
        from config.settings import GOOGLE_MAPS_API_KEY

        self.sv_canvas.itemconfigure(self._sv_msg_id, text="Loading…")
        key = GOOGLE_MAPS_API_KEY or os.getenv("GOOGLE_MAPS_API_KEY", "")

        def _fetch():
            w = max(self.sv_canvas.winfo_width() or 300, 200)
            h = max(self.sv_canvas.winfo_height() or 200, 160)

            img: Image.Image | None = None
            source = "OpenStreetMap"

            # ── 1. Google Street View (if key available) ──────────────────
            if key and lat is not None and lng is not None:
                try:
                    sv_url = build_streetview_url(lat, lng, addr, api_key=key,
                                                  width=w, height=h)
                    resp = requests.get(sv_url, timeout=10)
                    resp.raise_for_status()
                    # Google returns a grey "no imagery" image for missing locations;
                    # check Content-Type — real SV images are image/jpeg
                    if "image/jpeg" in resp.headers.get("Content-Type", ""):
                        img = Image.open(io.BytesIO(resp.content))
                        source = "Google Street View"
                except Exception:
                    pass  # fall through to OSM

            # ── 2. OSM map tile (free fallback, always works) ─────────────
            if img is None and lat is not None and lng is not None:
                try:
                    img = _build_map_image(lat, lng, width=w, height=h)
                    source = "OpenStreetMap"
                except Exception:
                    pass

            if img is not None:
                img = img.resize((w, h), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self._sv_cache[idx] = photo
                self.after(0, lambda p=photo, s=source: self._show_sv_image(p, s))
            else:
                self.after(0, lambda: self.sv_canvas.itemconfigure(
                    self._sv_msg_id, text="Location preview\nnot available"
                ))

        threading.Thread(target=_fetch, daemon=True).start()

    def _show_sv_image(self, photo: ImageTk.PhotoImage, source: str = "OpenStreetMap"):
        self.sv_canvas.delete("img")
        self.sv_canvas.itemconfigure(self._sv_msg_id, text="")
        w = self.sv_canvas.winfo_width() or 300
        h = self.sv_canvas.winfo_height() or 200
        self.sv_canvas.create_image(w // 2, h // 2, image=photo, anchor="center", tags="img")
        self._current_photo = photo  # keep reference
        self._preview_source_var.set(source)

    # ── Inline stop editing ────────────────────────────────────────────────

    def _add_inline_stop(self):
        addr = self.add_entry.get().strip()
        if not addr:
            return
        result = self.app.route_result
        if not result:
            return
        result.ordered_addresses.append(addr)
        self.add_entry.delete(0, tk.END)
        self._populate()

    def _delete_stop(self, idx: int):
        result = self.app.route_result
        if not result:
            return
        result.ordered_addresses.pop(idx)
        if self.app.locations and idx < len(self.app.locations):
            self.app.locations.pop(idx)
        self._populate()

    def _move_stop(self, idx: int, direction: int):
        result = self.app.route_result
        if not result:
            return
        addrs = result.ordered_addresses
        locs  = self.app.locations
        new_idx = idx + direction
        if 0 <= new_idx < len(addrs):
            addrs[idx], addrs[new_idx] = addrs[new_idx], addrs[idx]
            if locs and len(locs) == len(addrs):
                locs[idx], locs[new_idx] = locs[new_idx], locs[idx]
            self._populate()

    # ── Re-solve ───────────────────────────────────────────────────────────

    def _re_solve(self):
        """Push the current (possibly edited) addresses back to home view and re-solve."""
        result = self.app.route_result
        if not result:
            return
        home = self.app.views["home"]
        home.stop_listbox.delete(0, tk.END)
        for addr in result.ordered_addresses:
            home.stop_listbox.insert(tk.END, addr)
        home._update_count()
        home._refresh_depot_menu()
        self.app.navigate_to("home")
        home._start_solve()

    # ── Map launch actions ─────────────────────────────────────────────────

    def _open_in_maps(self):
        result = self.app.route_result
        if not result:
            return
        addrs = result.ordered_addresses
        if len(addrs) <= 10:
            webbrowser.open(build_maps_url(addrs))
        else:
            urls = build_maps_url_chunked(addrs)
            msg = f"Route has {len(addrs)} stops (Google Maps supports 10 per URL).\n\n"
            msg += f"{len(urls)} URLs will open in your browser.\nContinue?"
            if messagebox.askyesno("Long route", msg):
                for u in urls:
                    webbrowser.open(u)

    def _open_maps_single(self):
        if self._selected_idx is None:
            return
        result = self.app.route_result
        if not result:
            return
        addr = result.ordered_addresses[self._selected_idx]
        import urllib.parse
        enc = urllib.parse.quote_plus(addr)
        webbrowser.open(f"https://www.google.com/maps/dir/?api=1&destination={enc}&travelmode=driving")

    def _open_fieldmaps_all(self):
        result = self.app.route_result
        if not result:
            return
        from config.settings import ARCGIS_ITEM_ID
        for i, addr in enumerate(result.ordered_addresses):
            locs = self.app.locations
            lat = lng = None
            for loc in locs:
                if loc["address"] == addr:
                    lat, lng = loc.get("lat"), loc.get("lng")
                    break
            url = build_fieldmaps_url(addr, lat, lng, item_id=ARCGIS_ITEM_ID or None)
            if i == 0:
                webbrowser.open(url)
            # For bulk, just open first — user can navigate from within FieldMaps
        messagebox.showinfo(
            "ArcGIS FieldMaps",
            f"Opened stop 1 in ArcGIS FieldMaps.\n\n"
            f"Select individual stops and click 'FieldMaps' to navigate to each.",
        )

    def _open_fieldmaps_single(self):
        if self._selected_idx is None:
            messagebox.showinfo("FieldMaps", "Select a stop first.")
            return
        result = self.app.route_result
        if not result:
            return
        from config.settings import ARCGIS_ITEM_ID
        addr = result.ordered_addresses[self._selected_idx]
        locs = self.app.locations
        lat = lng = None
        for loc in locs:
            if loc["address"] == addr:
                lat, lng = loc.get("lat"), loc.get("lng")
                break
        url = build_fieldmaps_url(addr, lat, lng, item_id=ARCGIS_ITEM_ID or None)
        webbrowser.open(url)

    def _open_waze_first(self):
        locs = self.app.locations
        if not locs:
            return
        first = locs[0]
        if first.get("lat") and first.get("lng"):
            webbrowser.open(build_waze_url(first["lat"], first["lng"]))

    def _open_streetview_browser(self):
        if self._selected_idx is None:
            return
        locs = self.app.locations
        result = self.app.route_result
        if not result or not locs:
            return
        addr = result.ordered_addresses[self._selected_idx]
        for loc in locs:
            if loc["address"] == addr and loc.get("lat") and loc.get("lng"):
                lat, lng = loc["lat"], loc["lng"]
                url = f"https://www.google.com/maps/@{lat},{lng},3a,90y,0h,90t/data=!3m4!1e1"
                webbrowser.open(url)
                return
        # Fallback: open Maps search
        import urllib.parse
        webbrowser.open(f"https://www.google.com/maps/search/{urllib.parse.quote_plus(addr)}")

    # ── Export ─────────────────────────────────────────────────────────────

    def _export_csv(self):
        result = self.app.route_result
        if not result:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile="ontrack_route.csv",
        )
        if path:
            export_csv(result.ordered_addresses, path)
            messagebox.showinfo("Exported", f"Route saved to:\n{path}")
