"""
mobile/screens/results.py — Route results screen for Kivy (Android).
"""

from __future__ import annotations
import threading
import webbrowser

from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.image import AsyncImage
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput
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
    return Button(text=text, background_color=bg, color=C_WHITE,
                  size_hint_y=None, height=dp(42), **kw)


class ResultsScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self._selected_idx: int | None = None
        self._layout_built = False

    def on_enter(self):
        if not self._layout_built:
            self._build()
            self._layout_built = True
        self._populate()

    def _build(self):
        root = BoxLayout(orientation="vertical", spacing=dp(8),
                         padding=[dp(10), dp(6)])

        # ── Header ──
        header = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        back_btn = _btn("← Back", bg=C_NAVY, size_hint_x=None, width=dp(80))
        back_btn.bind(on_release=lambda *_: App.get_running_app().navigate("home", "right"))
        header.add_widget(back_btn)
        self.summary_lbl = Label(text="Route", color=C_WHITE,
                                 font_size=dp(14), bold=True)
        header.add_widget(self.summary_lbl)
        settings_btn = _btn("⚙", bg=C_NAVY, size_hint_x=None, width=dp(44))
        settings_btn.bind(on_release=lambda *_: App.get_running_app().navigate("settings"))
        header.add_widget(settings_btn)
        root.add_widget(header)

        # ── Map launch buttons ──
        map_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        maps_btn = _btn("🗺 Google Maps", bg=C_BLUE)
        maps_btn.bind(on_release=lambda *_: self._open_maps_all())
        map_row.add_widget(maps_btn)
        fm_btn = _btn("📐 FieldMaps", bg=get_color_from_hex("#1A5F3Fff"))
        fm_btn.bind(on_release=lambda *_: self._open_fieldmaps_first())
        map_row.add_widget(fm_btn)
        root.add_widget(map_row)

        # ── Street View panel ──
        sv_card = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(220),
                            padding=[dp(8), dp(4)], spacing=dp(4))

        sv_header = BoxLayout(size_hint_y=None, height=dp(32), spacing=dp(8))
        sv_header.add_widget(Label(text="[b]Street View[/b]", markup=True,
                                   color=C_WHITE, font_size=dp(14), size_hint_x=1))
        sv_open_btn = _btn("🌐 Open", bg=C_CARD, size_hint_x=None, width=dp(80), height=dp(32))
        sv_open_btn.bind(on_release=lambda *_: self._open_sv_browser())
        sv_header.add_widget(sv_open_btn)
        sv_card.add_widget(sv_header)

        self.sv_addr_lbl = Label(text="Tap a stop to preview",
                                 color=C_GRAY, font_size=dp(11),
                                 size_hint_y=None, height=dp(20))
        sv_card.add_widget(self.sv_addr_lbl)

        # Use free OSM tile URL by default; replaced with Street View URL if API key set
        self.sv_image = AsyncImage(
            source="",
            allow_stretch=True, keep_ratio=True,
            size_hint_y=None, height=dp(160),
            nocache=True,
        )
        sv_card.add_widget(self.sv_image)
        root.add_widget(sv_card)

        # ── Inline add stop ──
        add_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        self.add_input = TextInput(hint_text="Add a stop…", multiline=False,
                                   background_color=C_CARD, foreground_color=C_WHITE,
                                   hint_text_color=C_GRAY, cursor_color=C_WHITE,
                                   font_size=dp(13))
        self.add_input.bind(on_text_validate=lambda *_: self._add_stop())
        add_row.add_widget(self.add_input)
        add_btn = _btn("+ Add", size_hint_x=None, width=dp(70))
        add_btn.bind(on_release=lambda *_: self._add_stop())
        add_row.add_widget(add_btn)
        root.add_widget(add_row)

        # ── Route table ──
        sv = ScrollView(size_hint=(1, 1))
        self.table = GridLayout(cols=1, spacing=dp(4), size_hint_y=None, padding=[0, dp(4)])
        self.table.bind(minimum_height=self.table.setter("height"))
        sv.add_widget(self.table)
        root.add_widget(sv)

        # ── Re-solve ──
        resolve_btn = _btn("⚡ Re-optimize Route", bg=C_ORANGE)
        resolve_btn.font_size = dp(15)
        resolve_btn.height = dp(50)
        resolve_btn.bind(on_release=lambda *_: self._re_solve())
        root.add_widget(resolve_btn)

        self.add_widget(root)

    def _populate(self):
        app = App.get_running_app()
        result = app.route_result
        if not result:
            return

        self.table.clear_widgets()
        from core.exporter import format_duration
        dur = format_duration(result.total_duration_seconds)
        self.summary_lbl.text = f"{len(result.ordered_addresses)} stops  ·  {dur}"

        for i, addr in enumerate(result.ordered_addresses):
            row = BoxLayout(size_hint_y=None, height=dp(48),
                            spacing=dp(6), padding=[dp(4), dp(2)])

            num = Label(text=f"[b]{i+1}[/b]", markup=True, color=C_ORANGE,
                        size_hint_x=None, width=dp(28), font_size=dp(14))
            row.add_widget(num)

            addr_btn = Button(text=addr, color=C_WHITE, halign="left", valign="middle",
                              background_color=C_SURFACE, font_size=dp(12))
            addr_btn.text_size = (None, None)
            addr_btn.bind(on_release=lambda b, idx=i: self._select_stop(idx))
            row.add_widget(addr_btn)

            del_btn = Button(text="✕", background_color=C_RED, color=C_WHITE,
                             size_hint_x=None, width=dp(36))
            del_btn.bind(on_release=lambda b, idx=i: self._delete_stop(idx))
            row.add_widget(del_btn)

            fm_btn = Button(text="📐", background_color=get_color_from_hex("#1A5F3Fff"),
                            color=C_WHITE, size_hint_x=None, width=dp(36))
            fm_btn.bind(on_release=lambda b, idx=i: self._open_fieldmaps_stop(idx))
            row.add_widget(fm_btn)

            self.table.add_widget(row)

    # ── Stop interactions ──────────────────────────────────────────────────

    def _select_stop(self, idx: int):
        self._selected_idx = idx
        app = App.get_running_app()
        result = app.route_result
        if not result:
            return
        addr = result.ordered_addresses[idx]
        self.sv_addr_lbl.text = f"Stop {idx+1}: {addr}"
        self._load_sv(idx, addr, app.locations)

    def _load_sv(self, idx: int, addr: str, locs: list[dict]):
        """
        Load a preview for the selected stop.
        - With Google API key: loads Street View Static image
        - Without key: loads a free OSM static map tile
        Both require no setup from end users.
        """
        from config.settings import GOOGLE_MAPS_API_KEY
        from core.exporter import build_streetview_url
        lat = lng = None
        for loc in locs:
            if loc["address"] == addr:
                lat, lng = loc.get("lat"), loc.get("lng")
                break

        key = GOOGLE_MAPS_API_KEY
        if key and lat is not None and lng is not None:
            try:
                url = build_streetview_url(lat, lng, addr, api_key=key, width=600, height=300)
                self.sv_image.source = url
                self.sv_image.reload()
                return
            except Exception:
                pass  # fall through to OSM

        # Free OSM static map (no key required)
        if lat is not None and lng is not None:
            zoom = 16
            import math
            x = int((lng + 180) / 360 * 2**zoom)
            y = int((1 - math.log(math.tan(math.radians(lat)) + 1/math.cos(math.radians(lat))) / math.pi) / 2 * 2**zoom)
            osm_url = f"https://tile.openstreetmap.org/{zoom}/{x}/{y}.png"
            self.sv_image.source = osm_url
            self.sv_image.reload()
            self.sv_addr_lbl.text = f"Stop {idx+1}: {addr}  ·  OpenStreetMap"
        else:
            self.sv_addr_lbl.text = f"Stop {idx+1}: {addr}  ·  (location unknown)"

    def _add_stop(self):
        addr = self.add_input.text.strip()
        if not addr:
            return
        app = App.get_running_app()
        result = app.route_result
        if result:
            result.ordered_addresses.append(addr)
            self.add_input.text = ""
            self._populate()

    def _delete_stop(self, idx: int):
        app = App.get_running_app()
        result = app.route_result
        if result:
            result.ordered_addresses.pop(idx)
            if app.locations and idx < len(app.locations):
                app.locations.pop(idx)
            self._populate()

    def _re_solve(self):
        app = App.get_running_app()
        result = app.route_result
        if not result:
            return
        home = app.home_screen
        home._stop_list = list(result.ordered_addresses)
        home._refresh_list()
        app.navigate("home", "right")
        Clock.schedule_once(lambda dt: home._start_solve(), 0.3)

    # ── Map launches ───────────────────────────────────────────────────────

    def _open_maps_all(self):
        app = App.get_running_app()
        result = app.route_result
        if not result:
            return
        from core.exporter import build_maps_url, build_maps_url_chunked
        addrs = result.ordered_addresses
        if len(addrs) <= 10:
            webbrowser.open(build_maps_url(addrs))
        else:
            for url in build_maps_url_chunked(addrs):
                webbrowser.open(url)

    def _open_fieldmaps_first(self):
        self._open_fieldmaps_stop(0)

    def _open_fieldmaps_stop(self, idx: int):
        app = App.get_running_app()
        result = app.route_result
        if not result or idx >= len(result.ordered_addresses):
            return
        from config.settings import ARCGIS_ITEM_ID
        from core.exporter import build_fieldmaps_url
        addr = result.ordered_addresses[idx]
        lat = lng = None
        for loc in app.locations:
            if loc["address"] == addr:
                lat, lng = loc.get("lat"), loc.get("lng")
                break
        url = build_fieldmaps_url(addr, lat, lng, item_id=ARCGIS_ITEM_ID or None)
        webbrowser.open(url)

    def _open_sv_browser(self):
        if self._selected_idx is None:
            return
        app = App.get_running_app()
        result = app.route_result
        if not result:
            return
        addr = result.ordered_addresses[self._selected_idx]
        for loc in app.locations:
            if loc["address"] == addr and loc.get("lat"):
                lat, lng = loc["lat"], loc["lng"]
                webbrowser.open(f"https://www.google.com/maps/@{lat},{lng},3a,90y,0h,90t/data=!3m4!1e1")
                return
        import urllib.parse
        webbrowser.open(f"https://www.google.com/maps/search/{urllib.parse.quote_plus(addr)}")
