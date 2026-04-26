#!/usr/bin/env python3
"""
gui/views/home.py — Route input view.

Features:
 - Enter addresses manually (add one at a time)
 - Load from CSV or Excel file
 - Use current location as depot / first stop
 - Drag-to-reorder the stop list before solving
 - Choose backend (OSRM / Google Maps / Haversine) and solver mode
 - Geocode + solve in a background thread to keep UI responsive
"""

from __future__ import annotations
import threading
import os

import customtkinter as ctk
from tkinter import filedialog, messagebox
import tkinter as tk

from core.parser import parse_addresses
from core.geocoder import geocode_addresses, get_current_location
from core.matrix import build_distance_matrix
from core.solver import solve_tsp, solve_open_tsp

TDS_BLUE    = "#0057A8"
TDS_NAVY    = "#002855"
TDS_ORANGE  = "#F26522"
TDS_LIGHT   = "#E8F0F8"
TDS_WHITE   = "#FFFFFF"
TDS_GRAY    = "#6B7280"
TDS_SURFACE = "#1A2535"
TDS_BG      = "#111827"
TDS_GREEN   = "#22C55E"
TDS_RED     = "#EF4444"


class HomeView(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=TDS_BG, corner_radius=0)
        self.app = app
        self._drag_start = None
        self._build()

    def on_show(self):
        pass

    # ── Layout ─────────────────────────────────────────────────────────────

    def _build(self):
        self.grid_columnconfigure(0, weight=1, minsize=320)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)

        # Left panel — address entry
        left = ctk.CTkFrame(self, fg_color=TDS_SURFACE, corner_radius=12)
        left.grid(row=0, column=0, padx=(16, 8), pady=16, sticky="nsew")
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(4, weight=1)

        # Section title
        ctk.CTkLabel(
            left, text="Stop List",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=TDS_WHITE,
        ).grid(row=0, column=0, columnspan=2, padx=16, pady=(14, 4), sticky="w")

        # Manual address entry
        entry_frame = ctk.CTkFrame(left, fg_color="transparent")
        entry_frame.grid(row=1, column=0, columnspan=2, padx=12, pady=4, sticky="ew")
        entry_frame.grid_columnconfigure(0, weight=1)

        self.addr_entry = ctk.CTkEntry(
            entry_frame,
            placeholder_text="Enter address (e.g. 123 Main St Spokane WA)",
            height=38,
            fg_color="#243044",
            border_color=TDS_BLUE,
            text_color=TDS_WHITE,
        )
        self.addr_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.addr_entry.bind("<Return>", lambda e: self._add_address())

        ctk.CTkButton(
            entry_frame, text="Add", width=60, height=38,
            fg_color=TDS_BLUE, hover_color=TDS_NAVY,
            command=self._add_address,
        ).grid(row=0, column=1)

        # Voice button — speak an address instead of typing
        try:
            from gui.components.voice_button import VoiceButton
            self._voice_btn = VoiceButton(
                entry_frame,
                on_result=self._on_voice_address,
                model_size="base",
                width=80,
            )
            self._voice_btn.grid(row=0, column=2, padx=(6, 0))
        except ImportError:
            pass  # voice deps not installed — button simply not shown

        # Action buttons row
        btn_row = ctk.CTkFrame(left, fg_color="transparent")
        btn_row.grid(row=2, column=0, columnspan=2, padx=12, pady=(2, 8), sticky="ew")

        ctk.CTkButton(
            btn_row, text="📂 Load File", width=120, height=32,
            fg_color="#243044", hover_color=TDS_NAVY,
            text_color=TDS_WHITE,
            command=self._load_file,
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            btn_row, text="📍 My Location", width=120, height=32,
            fg_color="#243044", hover_color=TDS_NAVY,
            text_color=TDS_WHITE,
            command=self._use_current_location,
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            btn_row, text="🗑 Clear", width=70, height=32,
            fg_color="#3B1A1A", hover_color="#5C2222",
            text_color=TDS_WHITE,
            command=self._clear_list,
        ).pack(side="left")

        # Stop list (drag-reorderable)
        list_container = ctk.CTkFrame(left, fg_color="#1A2535", corner_radius=8)
        list_container.grid(row=4, column=0, columnspan=2, padx=12, pady=(0, 8), sticky="nsew")
        list_container.grid_rowconfigure(0, weight=1)
        list_container.grid_columnconfigure(0, weight=1)

        self.stop_listbox = tk.Listbox(
            list_container,
            bg="#1A2535",
            fg=TDS_WHITE,
            selectbackground=TDS_BLUE,
            selectforeground=TDS_WHITE,
            activestyle="none",
            relief="flat",
            bd=0,
            font=("Segoe UI", 12),
            highlightthickness=0,
        )
        self.stop_listbox.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        self.stop_listbox.bind("<ButtonPress-1>",   self._on_drag_start)
        self.stop_listbox.bind("<B1-Motion>",        self._on_drag_motion)
        self.stop_listbox.bind("<ButtonRelease-1>",  self._on_drag_release)
        self.stop_listbox.bind("<Delete>",           lambda e: self._remove_selected())
        self.stop_listbox.bind("<BackSpace>",        lambda e: self._remove_selected())

        sb = ctk.CTkScrollbar(list_container, command=self.stop_listbox.yview)
        sb.grid(row=0, column=1, sticky="ns", pady=6)
        self.stop_listbox.configure(yscrollcommand=sb.set)

        self._stop_count_var = tk.StringVar(value="0 stops")
        ctk.CTkLabel(left, textvariable=self._stop_count_var,
                     font=ctk.CTkFont(size=11), text_color=TDS_GRAY).grid(
            row=5, column=0, padx=14, pady=(0, 4), sticky="w")

        # Reorder buttons
        reorder_frame = ctk.CTkFrame(left, fg_color="transparent")
        reorder_frame.grid(row=3, column=0, columnspan=2, padx=12, pady=2, sticky="ew")

        ctk.CTkButton(reorder_frame, text="▲ Up", width=80, height=28,
                      fg_color="#243044", hover_color=TDS_NAVY, text_color=TDS_WHITE,
                      command=self._move_up).pack(side="left", padx=(0, 6))
        ctk.CTkButton(reorder_frame, text="▼ Down", width=80, height=28,
                      fg_color="#243044", hover_color=TDS_NAVY, text_color=TDS_WHITE,
                      command=self._move_down).pack(side="left", padx=(0, 6))
        ctk.CTkButton(reorder_frame, text="✕ Remove", width=90, height=28,
                      fg_color="#3B1A1A", hover_color="#5C2222", text_color=TDS_WHITE,
                      command=self._remove_selected).pack(side="left")

        # Right panel — options + solve
        right = ctk.CTkFrame(self, fg_color=TDS_SURFACE, corner_radius=12)
        right.grid(row=0, column=1, padx=(8, 16), pady=16, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            right, text="Route Options",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=TDS_WHITE,
        ).grid(row=0, column=0, padx=20, pady=(14, 4), sticky="w")

        # ── Route type (simple, always visible) ──────────────────────────────
        simple_opts = ctk.CTkFrame(right, fg_color="transparent")
        simple_opts.grid(row=1, column=0, padx=20, pady=(0, 4), sticky="ew")
        simple_opts.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(simple_opts, text="Route type:",
                     font=ctk.CTkFont(size=13), text_color="#9DB8D6",
                     ).grid(row=0, column=0, sticky="w", padx=(0, 16), pady=6)
        self.route_type_var = ctk.StringVar(value="open (no return)")
        ctk.CTkOptionMenu(
            simple_opts, values=["open (no return)", "round trip"],
            variable=self.route_type_var, width=200, height=34,
            fg_color="#243044", button_color=TDS_BLUE, text_color=TDS_WHITE,
        ).grid(row=0, column=1, sticky="w")

        ctk.CTkLabel(simple_opts, text="Starting stop:",
                     font=ctk.CTkFont(size=13), text_color="#9DB8D6",
                     ).grid(row=1, column=0, sticky="w", padx=(0, 16), pady=6)
        self.depot_var = ctk.StringVar(value="First in list")
        self.depot_menu = ctk.CTkOptionMenu(
            simple_opts, values=["First in list"],
            variable=self.depot_var, width=200, height=34,
            fg_color="#243044", button_color=TDS_BLUE, text_color=TDS_WHITE,
        )
        self.depot_menu.grid(row=1, column=1, sticky="w")

        # ── Advanced toggle ────────────────────────────────────────────────
        self._adv_open = tk.BooleanVar(value=False)
        adv_toggle = ctk.CTkButton(
            right, text="▶ Advanced options",
            height=30, fg_color="transparent",
            hover_color=TDS_SURFACE, text_color=TDS_GRAY,
            font=ctk.CTkFont(size=12), anchor="w",
            command=self._toggle_advanced,
        )
        adv_toggle.grid(row=2, column=0, padx=16, pady=(2, 0), sticky="w")
        self._adv_toggle_btn = adv_toggle

        # Advanced options frame (hidden by default)
        self._adv_frame = ctk.CTkFrame(right, fg_color="#1A2535", corner_radius=8)
        # NOT gridded yet — shown on toggle
        self._adv_frame.grid_columnconfigure(1, weight=1)

        def _adv_label(text, row):
            ctk.CTkLabel(self._adv_frame, text=text, font=ctk.CTkFont(size=12),
                         text_color="#9DB8D6").grid(
                row=row, column=0, sticky="w", pady=5, padx=(12, 14))

        _adv_label("Distance backend:", 0)
        self.backend_var = ctk.StringVar(value="osrm")
        ctk.CTkOptionMenu(
            self._adv_frame, values=["osrm (free)", "google (API key needed)", "haversine"],
            variable=self.backend_var, width=220, height=32,
            fg_color="#243044", button_color=TDS_BLUE, text_color=TDS_WHITE,
        ).grid(row=0, column=1, sticky="w", pady=5, padx=(0, 12))

        _adv_label("Solver time limit:", 1)
        self.time_limit_var = ctk.StringVar(value="30s")
        ctk.CTkOptionMenu(
            self._adv_frame, values=["10s", "30s", "60s", "120s"],
            variable=self.time_limit_var, width=220, height=32,
            fg_color="#243044", button_color=TDS_BLUE, text_color=TDS_WHITE,
        ).grid(row=1, column=1, sticky="w", pady=5, padx=(0, 12))

        # Status / progress
        self._status_var = tk.StringVar(value="Add stops to get started.")
        ctk.CTkLabel(right, textvariable=self._status_var,
                     font=ctk.CTkFont(size=12), text_color=TDS_GRAY,
                     wraplength=440).grid(row=2, column=0, padx=20, pady=(12, 4), sticky="w")

        self.progress = ctk.CTkProgressBar(right, mode="indeterminate",
                                           progress_color=TDS_BLUE)
        self.progress.grid(row=3, column=0, padx=20, pady=4, sticky="ew")
        self.progress.set(0)

        # Solve button
        self.solve_btn = ctk.CTkButton(
            right,
            text="⚡  Optimize Route",
            height=52,
            fg_color=TDS_ORANGE,
            hover_color="#D4541A",
            text_color=TDS_WHITE,
            font=ctk.CTkFont(size=16, weight="bold"),
            corner_radius=10,
            command=self._start_solve,
        )
        self.solve_btn.grid(row=4, column=0, padx=20, pady=(12, 20), sticky="ew")

        # Hint text
        ctk.CTkLabel(
            right,
            text="Tip: Click '📍 My Location' to start from your current position.\n"
                 "Drag stops in the list to manually reorder before solving.\n"
                 "Delete key removes the selected stop.",
            font=ctk.CTkFont(size=11),
            text_color=TDS_GRAY,
            justify="left",
        ).grid(row=5, column=0, padx=20, pady=0, sticky="w")

    # ── Address list management ────────────────────────────────────────────

    def _on_voice_address(self, text: str):
        """Called when voice recognition returns a transcribed address."""
        if text:
            self.addr_entry.delete(0, tk.END)
            self.addr_entry.insert(0, text)
            self._add_address()

    def _add_address(self):
        addr = self.addr_entry.get().strip()
        if not addr:
            return
        self.stop_listbox.insert(tk.END, addr)
        self.addr_entry.delete(0, tk.END)
        self._update_count()
        self._refresh_depot_menu()

    def _load_file(self):
        path = filedialog.askopenfilename(
            title="Select address file",
            filetypes=[("CSV / Excel", "*.csv *.xlsx *.xls"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            addrs = parse_addresses(path)
            for a in addrs:
                self.stop_listbox.insert(tk.END, a)
            self._update_count()
            self._refresh_depot_menu()
            self._status_var.set(f"Loaded {len(addrs)} addresses from {os.path.basename(path)}.")
        except Exception as e:
            messagebox.showerror("Load Error", str(e))

    def _use_current_location(self):
        self._status_var.set("Detecting current location…")
        self.update_idletasks()

        def _fetch():
            loc = get_current_location()
            self.after(0, lambda: self._on_location(loc))

        threading.Thread(target=_fetch, daemon=True).start()

    def _toggle_advanced(self):
        if self._adv_open.get():
            self._adv_frame.grid_forget()
            self._adv_open.set(False)
            self._adv_toggle_btn.configure(text="▶ Advanced options")
        else:
            self._adv_frame.grid(row=3, column=0, padx=20, pady=(2, 4), sticky="ew")
            self._adv_open.set(True)
            self._adv_toggle_btn.configure(text="▼ Advanced options")

    def _on_location(self, loc):
        if loc:
            self.app.current_loc = loc
            label = f"📍 {loc['lat']:.4f}, {loc['lng']:.4f}"
            self.stop_listbox.insert(0, label)
            self._update_count()
            self._refresh_depot_menu()
            self._status_var.set(f"Current location added as first stop.")
        else:
            messagebox.showwarning("Location", "Could not determine current location.")
            self._status_var.set("Location unavailable.")

    def _clear_list(self):
        self.stop_listbox.delete(0, tk.END)
        self._update_count()
        self._refresh_depot_menu()
        self._status_var.set("Stop list cleared.")

    def _remove_selected(self):
        sel = self.stop_listbox.curselection()
        if sel:
            self.stop_listbox.delete(sel[0])
            self._update_count()
            self._refresh_depot_menu()

    def _move_up(self):
        sel = self.stop_listbox.curselection()
        if not sel or sel[0] == 0:
            return
        i = sel[0]
        text = self.stop_listbox.get(i)
        self.stop_listbox.delete(i)
        self.stop_listbox.insert(i - 1, text)
        self.stop_listbox.selection_set(i - 1)
        self._refresh_depot_menu()

    def _move_down(self):
        sel = self.stop_listbox.curselection()
        if not sel or sel[0] == self.stop_listbox.size() - 1:
            return
        i = sel[0]
        text = self.stop_listbox.get(i)
        self.stop_listbox.delete(i)
        self.stop_listbox.insert(i + 1, text)
        self.stop_listbox.selection_set(i + 1)
        self._refresh_depot_menu()

    def _update_count(self):
        n = self.stop_listbox.size()
        self._stop_count_var.set(f"{n} stop{'s' if n != 1 else ''}")

    def _refresh_depot_menu(self):
        items = list(self.stop_listbox.get(0, tk.END))
        opts = ["First in list"] + [f"{i+1}. {a[:40]}" for i, a in enumerate(items)]
        self.depot_menu.configure(values=opts)
        if self.depot_var.get() not in opts:
            self.depot_var.set("First in list")

    # ── Drag reorder ───────────────────────────────────────────────────────

    def _on_drag_start(self, event):
        self._drag_start = self.stop_listbox.nearest(event.y)

    def _on_drag_motion(self, event):
        target = self.stop_listbox.nearest(event.y)
        if self._drag_start is not None and target != self._drag_start:
            text = self.stop_listbox.get(self._drag_start)
            self.stop_listbox.delete(self._drag_start)
            self.stop_listbox.insert(target, text)
            self.stop_listbox.selection_clear(0, tk.END)
            self.stop_listbox.selection_set(target)
            self._drag_start = target

    def _on_drag_release(self, event):
        self._drag_start = None
        self._refresh_depot_menu()

    # ── Solve ──────────────────────────────────────────────────────────────

    def _get_addresses(self) -> list[str]:
        return list(self.stop_listbox.get(0, tk.END))

    def _start_solve(self):
        addrs = self._get_addresses()
        if len(addrs) < 2:
            messagebox.showwarning("Not enough stops", "Add at least 2 stops to optimize a route.")
            return

        self.solve_btn.configure(state="disabled", text="Working…")
        self.progress.configure(mode="indeterminate")
        self.progress.start()
        self._status_var.set("Geocoding addresses…")

        threading.Thread(target=self._solve_worker, args=(addrs,), daemon=True).start()

    def _solve_worker(self, addrs: list[str]):
        try:
            from config.settings import GOOGLE_MAPS_API_KEY, OSRM_BASE_URL

            # Step 1 — geocode
            # backend_var may include a suffix like "osrm (free)" — extract the key word
            backend_raw = self.backend_var.get().split()[0]  # "osrm", "google", "haversine"
            use_google = backend_raw == "google"
            self.after(0, lambda: self._status_var.set("Geocoding addresses…"))
            locations = geocode_addresses(
                addrs,
                use_google=use_google,
                google_api_key=GOOGLE_MAPS_API_KEY or None,
                progress_callback=lambda d, t: self.after(
                    0, lambda: self._status_var.set(f"Geocoding {d}/{t}…")
                ),
            )

            failed = [l["address"] for l in locations if l["lat"] is None]
            if failed:
                warn = "\n".join(failed[:5])
                self.after(0, lambda: messagebox.showwarning(
                    "Geocoding issues",
                    f"Could not geocode {len(failed)} address(es):\n{warn}\n\nThey will be skipped.",
                ))

            good = [l for l in locations if l["lat"] is not None]
            if len(good) < 2:
                raise ValueError("Fewer than 2 addresses could be geocoded. Check addresses and try again.")

            # Step 2 — distance matrix
            self.after(0, lambda: self._status_var.set("Building distance matrix…"))
            backend = self.backend_var.get().split()[0]  # strip any "(free)" suffix
            matrix = build_distance_matrix(
                good,
                backend=backend,
                osrm_url=OSRM_BASE_URL,
                google_api_key=GOOGLE_MAPS_API_KEY or None,
            )

            # Step 3 — solve
            self.after(0, lambda: self._status_var.set("Optimizing route…"))
            depot_sel = self.depot_var.get()
            depot_idx = 0
            if depot_sel != "First in list":
                try:
                    depot_idx = int(depot_sel.split(".")[0]) - 1
                    depot_idx = max(0, min(depot_idx, len(good) - 1))
                except ValueError:
                    depot_idx = 0

            tl = int(self.time_limit_var.get().rstrip("s"))
            open_route = "open" in self.route_type_var.get()

            if open_route:
                result = solve_open_tsp(good, matrix, start_index=depot_idx, time_limit_seconds=tl)
            else:
                result = solve_tsp(good, matrix, depot_index=depot_idx, time_limit_seconds=tl)

            self.after(0, lambda: self._on_solve_done(result, good))

        except Exception as e:
            self.after(0, lambda: self._on_solve_error(str(e)))

    def _on_solve_done(self, result, locations):
        self.app.route_result = result
        self.app.locations    = locations
        self.app.raw_addresses = result.ordered_addresses

        self.progress.stop()
        self.progress.set(1)
        self.solve_btn.configure(state="normal", text="⚡  Optimize Route")

        from core.exporter import format_duration
        dur = format_duration(result.total_duration_seconds)
        n = len(result.ordered_addresses)
        self._status_var.set(f"✓ Route ready: {n} stops · {dur} estimated")

        # Switch to results view
        self.app.navigate_to("results")

    def _on_solve_error(self, msg: str):
        self.progress.stop()
        self.progress.set(0)
        self.solve_btn.configure(state="normal", text="⚡  Optimize Route")
        self._status_var.set(f"Error: {msg}")
        messagebox.showerror("Route Error", msg)
