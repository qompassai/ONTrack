"""
mobile/screens/home.py — Route input screen for Kivy (Android).
"""

from __future__ import annotations
import threading

from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.uix.progressbar import ProgressBar
from kivy.uix.spinner import Spinner
from kivy.clock import Clock
from kivy.utils import get_color_from_hex
from kivy.metrics import dp

C_BG      = get_color_from_hex("#111827ff")
C_SURFACE = get_color_from_hex("#1A2535ff")
C_CARD    = get_color_from_hex("#243044ff")
C_BLUE    = get_color_from_hex("#0057A8ff")
C_NAVY    = get_color_from_hex("#002855ff")
C_ORANGE  = get_color_from_hex("#F26522ff")
C_WHITE   = get_color_from_hex("#FFFFFFff")
C_GRAY    = get_color_from_hex("#6B7280ff")
C_RED     = get_color_from_hex("#EF4444ff")
C_GREEN   = get_color_from_hex("#22C55Eff")


def _btn(text, bg=C_BLUE, **kw) -> Button:
    b = Button(text=text, background_color=bg, color=C_WHITE,
               size_hint_y=None, height=dp(44), **kw)
    return b


class HomeScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self._stop_list: list[str] = []
        self._build()

    def _build(self):
        root = BoxLayout(orientation="vertical", spacing=dp(8),
                         padding=[dp(12), dp(8)], size_hint=(1, 1))
        root.canvas.before.clear()  # background set by App clearcolor

        # ── Header ──
        header = BoxLayout(size_hint_y=None, height=dp(50))
        lbl = Label(text="[b]OnTrack[/b]  ·  TDS Field Route Optimizer",
                    markup=True, color=C_WHITE, font_size=dp(16))
        header.add_widget(lbl)
        nav_settings = _btn("⚙", bg=C_NAVY, size_hint_x=None, width=dp(44))
        nav_settings.bind(on_release=lambda *_: App.get_running_app().navigate("settings"))
        header.add_widget(nav_settings)
        root.add_widget(header)

        # ── Address entry ──
        entry_row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        self.addr_input = TextInput(
            hint_text="Enter address (e.g. 123 Main St Spokane WA)",
            multiline=False, size_hint_x=1,
            background_color=C_CARD, foreground_color=C_WHITE,
            hint_text_color=C_GRAY, cursor_color=C_WHITE,
            font_size=dp(14),
        )
        self.addr_input.bind(on_text_validate=lambda *_: self._add_address())
        entry_row.add_widget(self.addr_input)
        add_btn = _btn("Add", size_hint_x=None, width=dp(70))
        add_btn.bind(on_release=lambda *_: self._add_address())
        entry_row.add_widget(add_btn)
        root.add_widget(entry_row)

        # ── Action buttons ──
        actions = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        loc_btn = _btn("📍 My Location", bg=C_SURFACE)
        loc_btn.bind(on_release=lambda *_: self._use_location())
        actions.add_widget(loc_btn)

        clr_btn = _btn("🗑 Clear", bg=C_RED)
        clr_btn.bind(on_release=lambda *_: self._clear())
        actions.add_widget(clr_btn)
        root.add_widget(actions)

        # ── Stop list ──
        sv = ScrollView(size_hint=(1, 1))
        self.list_layout = BoxLayout(orientation="vertical", spacing=dp(4),
                                     size_hint_y=None, padding=[0, dp(4)])
        self.list_layout.bind(minimum_height=self.list_layout.setter("height"))
        sv.add_widget(self.list_layout)
        root.add_widget(sv)

        # ── Options ──
        opts = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        self.backend_spinner = Spinner(
            text="osrm",
            values=("osrm", "google", "haversine"),
            size_hint_x=0.4,
            background_color=C_CARD, color=C_WHITE,
        )
        opts.add_widget(Label(text="Backend:", color=C_GRAY, size_hint_x=0.2, font_size=dp(13)))
        opts.add_widget(self.backend_spinner)

        self.route_spinner = Spinner(
            text="open",
            values=("open", "round trip"),
            size_hint_x=0.4,
            background_color=C_CARD, color=C_WHITE,
        )
        opts.add_widget(Label(text="Type:", color=C_GRAY, size_hint_x=0.15, font_size=dp(13)))
        opts.add_widget(self.route_spinner)
        root.add_widget(opts)

        # ── Status ──
        self.status_lbl = Label(text="Add stops to get started.",
                                color=C_GRAY, font_size=dp(12),
                                size_hint_y=None, height=dp(30))
        root.add_widget(self.status_lbl)

        # ── Progress bar ──
        self.progress = ProgressBar(max=100, value=0,
                                    size_hint_y=None, height=dp(6))
        root.add_widget(self.progress)

        # ── Solve button ──
        self.solve_btn = _btn("⚡  Optimize Route", bg=C_ORANGE)
        self.solve_btn.font_size = dp(16)
        self.solve_btn.bold = True
        self.solve_btn.height = dp(54)
        self.solve_btn.bind(on_release=lambda *_: self._start_solve())
        root.add_widget(self.solve_btn)

        self.add_widget(root)

    # ── Stop management ────────────────────────────────────────────────────

    def _add_address(self):
        addr = self.addr_input.text.strip()
        if not addr:
            return
        self._stop_list.append(addr)
        self.addr_input.text = ""
        self._refresh_list()

    def _use_location(self):
        self.status_lbl.text = "Detecting location…"
        from core.geocoder import get_current_location
        threading.Thread(target=self._fetch_loc, daemon=True).start()

    def _fetch_loc(self):
        from core.geocoder import get_current_location
        loc = get_current_location()
        Clock.schedule_once(lambda dt: self._on_loc(loc))

    def _on_loc(self, loc):
        if loc:
            App.get_running_app().current_loc = loc
            label = f"📍 {loc['lat']:.5f}, {loc['lng']:.5f}"
            self._stop_list.insert(0, label)
            self._refresh_list()
            self.status_lbl.text = "Current location added as first stop."
        else:
            self.status_lbl.text = "Could not get location."

    def _clear(self):
        self._stop_list.clear()
        self._refresh_list()
        self.status_lbl.text = "Cleared."

    def _refresh_list(self):
        self.list_layout.clear_widgets()
        for i, addr in enumerate(self._stop_list):
            row = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(4))
            num = Label(text=f"[b]{i+1}[/b]", markup=True,
                        color=C_ORANGE, size_hint_x=None, width=dp(28), font_size=dp(14))
            row.add_widget(num)
            lbl = Label(text=addr, color=C_WHITE, halign="left",
                        text_size=(None, None), font_size=dp(13))
            row.add_widget(lbl)
            del_btn = Button(text="✕", background_color=C_RED, color=C_WHITE,
                             size_hint_x=None, width=dp(36))
            del_btn.bind(on_release=lambda b, idx=i: self._delete(idx))
            row.add_widget(del_btn)
            self.list_layout.add_widget(row)

        n = len(self._stop_list)
        self.status_lbl.text = f"{n} stop{'s' if n != 1 else ''}"

    def _delete(self, idx: int):
        if 0 <= idx < len(self._stop_list):
            self._stop_list.pop(idx)
            self._refresh_list()

    # ── Solve ──────────────────────────────────────────────────────────────

    def _start_solve(self):
        if len(self._stop_list) < 2:
            self._popup("Need 2+ stops", "Add at least 2 stops to optimize a route.")
            return
        self.solve_btn.disabled = True
        self.solve_btn.text = "Working…"
        self.progress.value = 10
        self.status_lbl.text = "Geocoding…"
        threading.Thread(target=self._solve_worker, args=(list(self._stop_list),), daemon=True).start()

    def _solve_worker(self, addrs: list[str]):
        try:
            from config.settings import GOOGLE_MAPS_API_KEY, OSRM_BASE_URL
            from core.geocoder import geocode_addresses
            from core.matrix import build_distance_matrix
            from core.solver import solve_tsp, solve_open_tsp

            Clock.schedule_once(lambda dt: setattr(self.progress, "value", 25))

            use_google = self.backend_spinner.text == "google"
            locations = geocode_addresses(addrs, use_google=use_google,
                                          google_api_key=GOOGLE_MAPS_API_KEY or None)

            good = [l for l in locations if l["lat"] is not None]
            if len(good) < 2:
                raise ValueError("Too few addresses geocoded. Check addresses.")

            Clock.schedule_once(lambda dt: setattr(self.progress, "value", 50))

            matrix = build_distance_matrix(good, backend=self.backend_spinner.text,
                                           osrm_url=OSRM_BASE_URL,
                                           google_api_key=GOOGLE_MAPS_API_KEY or None)

            Clock.schedule_once(lambda dt: setattr(self.progress, "value", 75))

            open_route = self.route_spinner.text == "open"
            if open_route:
                result = solve_open_tsp(good, matrix, time_limit_seconds=20)
            else:
                result = solve_tsp(good, matrix, time_limit_seconds=20)

            app = App.get_running_app()
            app.route_result = result
            app.locations    = good

            Clock.schedule_once(lambda dt: self._on_done(result))

        except Exception as e:
            Clock.schedule_once(lambda dt: self._on_error(str(e)))

    def _on_done(self, result):
        from core.exporter import format_duration
        dur = format_duration(result.total_duration_seconds)
        self.status_lbl.text = f"✓ {len(result.ordered_addresses)} stops · {dur}"
        self.progress.value = 100
        self.solve_btn.disabled = False
        self.solve_btn.text = "⚡  Optimize Route"
        App.get_running_app().navigate("results")

    def _on_error(self, msg: str):
        self.solve_btn.disabled = False
        self.solve_btn.text = "⚡  Optimize Route"
        self.progress.value = 0
        self.status_lbl.text = f"Error: {msg}"
        self._popup("Route Error", msg)

    def _popup(self, title: str, msg: str):
        content = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
        content.add_widget(Label(text=msg, color=C_WHITE, text_size=(dp(280), None)))
        ok = _btn("OK")
        p = Popup(title=title, content=content, size_hint=(0.85, None), height=dp(220))
        ok.bind(on_release=p.dismiss)
        content.add_widget(ok)
        p.open()
