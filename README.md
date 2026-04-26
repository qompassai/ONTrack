# OnTrack — TDS Telecom Field Route Optimizer

Route optimization tool for TDS field service technicians.  
Enter addresses manually or load a CSV/Excel file, optimize the drive order, preview each stop in Street View, and launch turn-by-turn navigation in Google Maps or ArcGIS FieldMaps.

---

## Features

| Feature | Desktop | Android |
|---|---|---|
| Manual address entry | ✓ | ✓ |
| CSV / Excel import | ✓ | – |
| Current location as start | ✓ (IP) | ✓ (GPS) |
| Drag-to-reorder stops | ✓ | ✓ (delete/add) |
| TSP route optimization | OR-Tools | Nearest-neighbor |
| Distance backend: OSRM | ✓ | ✓ |
| Distance backend: Google | ✓ (key) | ✓ (key) |
| Street View preview | ✓ (key) | ✓ (key) |
| Launch Google Maps | ✓ | ✓ |
| Launch ArcGIS FieldMaps | ✓ | ✓ |
| Launch Waze | ✓ | ✓ |
| Add/remove stops after solve | ✓ | ✓ |
| Re-optimize after edits | ✓ | ✓ |
| CSV export | ✓ | – |

---

## Setup

### 1. Copy the example environment file
```bash
cp .env.example .env
```
Edit `.env` and add your Google Maps API key and ArcGIS item ID.  
You can also set these values from the **Settings** screen inside the app.

### 2. Install desktop dependencies
```bash
pip install -r requirements.txt
```

### 3. Run on desktop
```bash
python main.py
```

---

## Build — Desktop

### Windows (one-file EXE)
```powershell
pip install pyinstaller
pyinstaller ontrack.spec
# Output: dist/OnTrack.exe
```

### Linux x86_64 (one-file binary)
```bash
pip install pyinstaller
pyinstaller ontrack.spec
# Output: dist/OnTrack
```

---

## Build — Android APK

**Prerequisites:** Ubuntu/Debian Linux (or WSL2), Java 17, Android SDK/NDK.

```bash
pip install buildozer

buildozer android debug

```

> **Note:** OR-Tools has no python-for-android recipe.  
> The Android build uses a pure-Python nearest-neighbor solver instead.  
> This gives good-quality routes for typical field routes (≤ 30 stops).

### Sign for Play Store
```bash
buildozer android release
```

---

## API Keys

All keys are optional — the app works without them using free fallbacks.

| Key | Used for | Get it |
|---|---|---|
| `GOOGLE_MAPS_API_KEY` | Street View images, Google geocoding, Google distance matrix | [console.cloud.google.com](https://console.cloud.google.com/google/maps-apis/credentials) |
| `ARCGIS_ITEM_ID` | Opens correct web map in ArcGIS FieldMaps | Your ArcGIS Online map URL |

---

## Distance Backends

| Backend | Requires | Quality |
|---|---|---|
| `osrm` (default) | None (uses public router) | Good — real road distances |
| `google` | `GOOGLE_MAPS_API_KEY` | Best — live traffic aware |
| `haversine` | None | Fast — straight-line only |

---

## Address File Format

CSV or Excel with a column named `address`:

```csv
address
123 Main St Spokane WA
456 Elm St Coeur d'Alene ID
789 Oak Ave Post Falls ID
```

---

## Architecture

```
ontrack/
├── main.py                 # Entry point — detects desktop vs Android
├── core/
│   ├── parser.py           # CSV/Excel → address list
│   ├── geocoder.py         # Address → lat/lng (Nominatim or Google)
│   ├── matrix.py           # Distance matrix (OSRM / Google / Haversine)
│   ├── solver.py           # TSP optimizer (OR-Tools or nearest-neighbor)
│   └── exporter.py         # CSV export, Maps URL, FieldMaps URL, Street View URL
├── gui/                    # Desktop UI (CustomTkinter)
│   ├── app.py
│   └── views/
│       ├── home.py         # Address input + solve
│       ├── results.py      # Route table + Street View + map launch
│       └── settings.py     # API keys + preferences
├── mobile/                 # Android UI (Kivy)
│   ├── app.py
│   └── screens/
│       ├── home.py
│       ├── results.py
│       └── settings.py
├── config/
│   └── settings.py         # Env var loader
├── assets/                 # Icons, splash
├── buildozer.spec          # Android build config
├── ontrack.spec            # PyInstaller desktop build config
└── tests/                  # pytest test suite
```

---

## TDS Internal Notes

- The app does not transmit any address data to TDS servers. All routing uses OSRM (free, no account) or the technician's own Google Maps API key.  
- ArcGIS FieldMaps deep links open the technician's configured web map and search for the stop address.  
- For enterprise deployment, set `OSRM_BASE_URL` to a self-hosted OSRM instance on TDS infrastructure for offline-capable routing.
