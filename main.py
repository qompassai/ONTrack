#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main.py — OnTrack entry point.

Detects runtime environment and launches the appropriate UI:
  - Desktop (Windows/Linux): CustomTkinter GUI
  - Android: Kivy GUI
"""

import sys
import importlib.util


_PLATFORM = "android" if importlib.util.find_spec("android") is not None else "desktop"


def _run_desktop():
    from gui.app import ONTrackApp
    app = ONTrackApp()
    app.mainloop()


def _run_mobile():
    from mobile.app import OnTrackMobileApp
    OnTrackMobileApp().run()


if __name__ == "__main__":
    if _PLATFORM == "android" or "--mobile" in sys.argv:
        _run_mobile()
    else:
        _run_desktop()

