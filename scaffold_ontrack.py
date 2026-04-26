#!/usr/bin/env python3
import os

structure = {
    "main.py": '''from gui.app import ONTrackApp

if __name__ == "__main__":
    app = ONTrackApp()
    app.mainloop()
''',
    "requirements.txt": '''customtkinter
pandas
openpyxl
geopy
routingpy
ortools
folium
python-dotenv
pyinstaller
pyshortcuts
Pillow
''',
    "README.md": "# ONTrack\n\nField service route optimizer for fiber optic address verification.\n",
    "ontrack.spec": "",
    "gui/__init__.py": "",
    "gui/app.py": '''import customtkinter as ctk

class ONTrackApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("ONTrack")
        self.geometry("900x650")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
''',
    "gui/views/__init__.py": "",
    "gui/views/home.py": "# File picker + start address input view\n",
    "gui/views/results.py": "# Optimized route display/table view\n",
    "gui/views/settings.py": "# API keys, preferences view\n",
    "gui/components/__init__.py": "",
    "gui/components/file_picker.py": "# CSV/Excel drag-drop widget\n",
    "gui/components/address_table.py": "# Scrollable stop list\n",
    "gui/components/map_preview.py": "# Embedded folium or webview\n",
    "core/__init__.py": "",
    "core/parser.py": '''import pandas as pd

def parse_addresses(filepath: str) -> list[str]:
    """Load CSV or Excel and return list of address strings."""
    if filepath.endswith(".csv"):
        df = pd.read_csv(filepath)
    else:
        df = pd.read_excel(filepath)
    return df["address"].dropna().tolist()
''',
    "core/geocoder.py": '''from geopy.geocoders import Nominatim

geolocator = Nominatim(user_agent="ontrack")

def geocode_addresses(addresses: list[str]) -> list[dict]:
    """Convert addresses to lat/lng dicts."""
    results = []
    for addr in addresses:
        loc = geolocator.geocode(addr)
        if loc:
            results.append({"address": addr, "lat": loc.latitude, "lng": loc.longitude})
        else:
            results.append({"address": addr, "lat": None, "lng": None})
    return results
''',
    "core/matrix.py": "# Distance matrix builder (OSRM/Google)\n",
    "core/solver.py": "# OR-Tools TSP logic\n",
    "core/exporter.py": '''import csv

def export_csv(ordered_addresses: list[str], output_path: str):
    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["stop", "address"])
        for i, addr in enumerate(ordered_addresses, 1):
            writer.writerow([i, addr])

def build_maps_url(ordered_addresses: list[str]) -> str:
    base = "https://www.google.com/maps/dir/"
    return base + "/".join(a.replace(" ", "+") for a in ordered_addresses)
''',
    "assets/icon.png": None,
    "assets/icon.ico": None,
    "assets/themes/ontrack.json": "{}\n",
    "config/__init__.py": "",
    "config/settings.py": '''from dotenv import load_dotenv
import os

load_dotenv()

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
OSRM_BASE_URL = os.getenv("OSRM_BASE_URL", "http://router.project-osrm.org")
''',
    "tests/test_parser.py": "# Tests for core/parser.py\n",
    "tests/test_geocoder.py": "# Tests for core/geocoder.py\n",
    "tests/test_solver.py": "# Tests for core/solver.py\n",
    "tests/sample_addresses.csv": "address\n123 Main St Spokane WA\n456 Elm St Spokane WA\n789 Oak Ave Spokane WA\n",
    ".env.example": "GOOGLE_MAPS_API_KEY=\nOSRM_BASE_URL=http://router.project-osrm.org\n",
    ".gitignore": "build/\ndist/\n__pycache__/\n*.pyc\n.env\n*.spec\n",
    "build/.gitkeep": "",
}

def create_structure(base, files):
    for path, content in files.items():
        full_path = os.path.join(base, path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        if content is None:
            continue  # skip binary placeholders
        if not os.path.exists(full_path):
            with open(full_path, "w") as f:
                f.write(content)

if __name__ == "__main__":
    base = os.getcwd()
    create_structure(base, structure)
    print(f"ONTrack structure created in {base}")
