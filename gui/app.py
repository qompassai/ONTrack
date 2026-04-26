#!/usr/bin/env python3
"""
gui/app.py — OnTrack desktop application root (CustomTkinter).
Manages navigation between views and shared state.
"""

import customtkinter as ctk
from gui.views.home import HomeView
from gui.views.results import ResultsView
from gui.views.settings import SettingsView

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# TDS brand colors
TDS_BLUE    = "#0057A8"
TDS_NAVY    = "#002855"
TDS_ORANGE  = "#F26522"
TDS_LIGHT   = "#E8F0F8"
TDS_WHITE   = "#FFFFFF"
TDS_GRAY    = "#6B7280"
TDS_SURFACE = "#1A2535"
TDS_BG      = "#111827"


class ONTrackApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("OnTrack — TDS Field Route Optimizer")
        self.geometry("1200x780")
        self.minsize(900, 600)
        self.configure(fg_color=TDS_BG)

        # Shared state
        self.route_result    = None   # core.solver.RouteResult
        self.locations       = []     # geocoded list[dict]
        self.raw_addresses   = []     # list[str]
        self.current_loc     = None   # {"lat":, "lng":, "address":}

        self._build_layout()
        self._show_view("home")

    # ── Layout ─────────────────────────────────────────────────────────────

    def _build_layout(self):
        self.grid_rowconfigure(0, weight=0)   # header
        self.grid_rowconfigure(1, weight=1)   # content
        self.grid_columnconfigure(0, weight=1)

        # Header / nav bar
        self.header = ctk.CTkFrame(self, fg_color=TDS_NAVY, height=56, corner_radius=0)
        self.header.grid(row=0, column=0, sticky="ew")
        self.header.grid_propagate(False)
        self.header.grid_columnconfigure(1, weight=1)

        logo_lbl = ctk.CTkLabel(
            self.header,
            text="  🗺  OnTrack",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color=TDS_WHITE,
        )
        logo_lbl.grid(row=0, column=0, padx=20, pady=0, sticky="w")

        tds_lbl = ctk.CTkLabel(
            self.header,
            text="TDS Telecom · Field Route Optimizer",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#9DB8D6",
        )
        tds_lbl.grid(row=0, column=1, padx=0, pady=0, sticky="w")

        nav_frame = ctk.CTkFrame(self.header, fg_color="transparent")
        nav_frame.grid(row=0, column=2, padx=12, pady=6, sticky="e")

        self._nav_buttons = {}
        for name, label in [("home", "New Route"), ("results", "Route"), ("settings", "Settings")]:
            btn = ctk.CTkButton(
                nav_frame,
                text=label,
                width=100,
                height=36,
                fg_color="transparent",
                hover_color=TDS_SURFACE,
                text_color=TDS_WHITE,
                font=ctk.CTkFont(size=13),
                corner_radius=6,
                command=lambda n=name: self._show_view(n),
            )
            btn.pack(side="left", padx=4)
            self._nav_buttons[name] = btn

        # Content area
        self.content = ctk.CTkFrame(self, fg_color=TDS_BG, corner_radius=0)
        self.content.grid(row=1, column=0, sticky="nsew")
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        # Instantiate views
        self.views = {
            "home":     HomeView(self.content, app=self),
            "results":  ResultsView(self.content, app=self),
            "settings": SettingsView(self.content, app=self),
        }
        for view in self.views.values():
            view.grid(row=0, column=0, sticky="nsew")

    # ── Navigation ─────────────────────────────────────────────────────────

    def _show_view(self, name: str):
        self._current_view = name
        for k, btn in self._nav_buttons.items():
            btn.configure(
                fg_color=TDS_BLUE if k == name else "transparent",
                font=ctk.CTkFont(size=13, weight="bold" if k == name else "normal"),
            )
        self.views[name].tkraise()
        self.views[name].on_show()

    def navigate_to(self, name: str):
        self._show_view(name)
