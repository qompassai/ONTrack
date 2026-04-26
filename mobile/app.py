"""
mobile/app.py — Kivy application root for OnTrack Android.

Screens:
  home     — address entry + file load + current location
  results  — ordered route table + map launch + street view
  settings — API keys + preferences
"""

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, SlideTransition
from kivy.core.window import Window
from kivy.utils import get_color_from_hex

from mobile.screens.home     import HomeScreen
from mobile.screens.results  import ResultsScreen
from mobile.screens.settings import SettingsScreen

# TDS brand colors
C_NAVY   = get_color_from_hex("#002855")
C_BG     = get_color_from_hex("#111827")
C_BLUE   = get_color_from_hex("#0057A8")
C_ORANGE = get_color_from_hex("#F26522")


class OnTrackMobileApp(App):
    title = "OnTrack — TDS Route Optimizer"

    # Shared state (screens read/write via App.get_running_app())
    route_result   = None
    locations      = []
    current_loc    = None

    def build(self):
        Window.clearcolor = C_BG

        sm = ScreenManager(transition=SlideTransition())

        self.home_screen     = HomeScreen(name="home")
        self.results_screen  = ResultsScreen(name="results")
        self.settings_screen = SettingsScreen(name="settings")

        sm.add_widget(self.home_screen)
        sm.add_widget(self.results_screen)
        sm.add_widget(self.settings_screen)

        sm.current = "home"
        return sm

    def navigate(self, screen_name: str, direction: str = "left"):
        self.root.transition.direction = direction
        self.root.current = screen_name
