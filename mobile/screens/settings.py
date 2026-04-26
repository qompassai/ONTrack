"""
mobile/screens/settings.py — Settings screen for Kivy (Android).
"""

import os
import sys

from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
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
C_GREEN   = get_color_from_hex("#22C55Eff")


def _btn(text, bg=C_BLUE, **kw) -> Button:
    return Button(text=text, background_color=bg, color=C_WHITE,
                  size_hint_y=None, height=dp(42), **kw)


class SettingsScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self._fields: dict[str, TextInput] = {}
        self._build()

    def on_enter(self):
        self._reload()

    def _build(self):
        root = BoxLayout(orientation="vertical", spacing=dp(8),
                         padding=[dp(12), dp(8)])

        header = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        back = _btn("← Back", bg=C_NAVY, size_hint_x=None, width=dp(80))
        back.bind(on_release=lambda *_: App.get_running_app().navigate("home", "right"))
        header.add_widget(back)
        header.add_widget(Label(text="[b]Settings[/b]", markup=True,
                                color=C_WHITE, font_size=dp(16)))
        root.add_widget(header)

        sv = ScrollView(size_hint=(1, 1))
        content = BoxLayout(orientation="vertical", spacing=dp(10),
                            size_hint_y=None, padding=[0, dp(4)])
        content.bind(minimum_height=content.setter("height"))

        settings_defs = [
            ("GOOGLE_MAPS_API_KEY",
             "Google Maps API Key",
             "Required for Street View, geocoding accuracy, and Google distance matrix."),
            ("OSRM_BASE_URL",
             "OSRM Base URL",
             "Custom OSRM server. Default: http://router.project-osrm.org"),
            ("ARCGIS_ITEM_ID",
             "ArcGIS Web Map Item ID",
             "Your ArcGIS Online Web Map ID for FieldMaps deep links."),
        ]

        for env_key, label, hint in settings_defs:
            card = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(130),
                             padding=[dp(10), dp(8)], spacing=dp(4))

            card.add_widget(Label(text=f"[b]{label}[/b]", markup=True,
                                  color=C_WHITE, font_size=dp(13),
                                  size_hint_y=None, height=dp(22), halign="left"))
            card.add_widget(Label(text=hint, color=C_GRAY, font_size=dp(11),
                                  size_hint_y=None, height=dp(28),
                                  text_size=(dp(320), None), halign="left"))

            ti = TextInput(
                multiline=False, size_hint_y=None, height=dp(40),
                background_color=C_CARD, foreground_color=C_WHITE,
                hint_text_color=C_GRAY, cursor_color=C_WHITE,
                font_size=dp(13),
                password=("KEY" in env_key),
            )
            card.add_widget(ti)
            self._fields[env_key] = ti
            content.add_widget(card)

        sv.add_widget(content)
        root.add_widget(sv)

        save_btn = _btn("💾 Save Settings", bg=C_BLUE)
        save_btn.height = dp(50)
        save_btn.bind(on_release=lambda *_: self._save())
        root.add_widget(save_btn)

        self.status_lbl = Label(text="", color=C_GREEN, font_size=dp(13),
                                size_hint_y=None, height=dp(28))
        root.add_widget(self.status_lbl)

        self.add_widget(root)

    def _reload(self):
        from config.settings import GOOGLE_MAPS_API_KEY, OSRM_BASE_URL, ARCGIS_ITEM_ID
        defaults = {
            "GOOGLE_MAPS_API_KEY": GOOGLE_MAPS_API_KEY,
            "OSRM_BASE_URL":       OSRM_BASE_URL,
            "ARCGIS_ITEM_ID":      ARCGIS_ITEM_ID,
        }
        for k, ti in self._fields.items():
            ti.text = defaults.get(k, "")

    def _save(self):
        vals = {k: ti.text.strip() for k, ti in self._fields.items()}
        for k, v in vals.items():
            if v:
                os.environ[k] = v
            elif k in os.environ:
                del os.environ[k]
        # Try to persist to a local file (works on Android in app storage)
        try:
            from android.storage import app_storage_path  # type: ignore
            env_path = os.path.join(app_storage_path(), ".ontrack.env")
        except ImportError:
            env_path = os.path.expanduser("~/.ontrack.env")

        try:
            with open(env_path, "w") as f:
                for k, v in vals.items():
                    f.write(f'{k}="{v}"\n')
        except Exception:
            pass

        import importlib
        import config.settings as cs
        importlib.reload(cs)

        self.status_lbl.text = "✓ Saved"
        Clock.schedule_once(lambda dt: setattr(self.status_lbl, "text", ""), 3)
