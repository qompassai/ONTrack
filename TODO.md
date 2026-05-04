# OnTrack TODO

### `build.sh` — hardcoded `~/.local/bin/buildozer` path, not activated from Nix venv

```bash
~/.local/bin/buildozer android debug 2>&1 | tee ~/buildozer_debug.log
```

The `flake.nix` `shellHook` creates `.venv-buildozer/` and activates it. Inside that
venv, `buildozer` is on `$PATH`. The hardcoded `~/.local/bin/buildozer` bypasses this
and may invoke a different (incompatible) buildozer version, or fail if buildozer is
not user-installed at all.

**TODO:**
```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

env -u PIP_EXTRA_INDEX_URL \
    -u PIP_INDEX_URL \
    -u PIP_FIND_LINKS \
    buildozer android debug 2>&1 | tee ~/buildozer_debug.log
```

Require the Nix devShell to be active (`nix develop`) before running `build.sh`.

---

### `mobile/app.py` — `VoiceScreen` never registered in the `ScreenManager`

`mobile/app.py` adds `HomeScreen`, `ResultsScreen`, and `SettingsScreen` to the
`ScreenManager`. `VoiceScreen` (defined in `mobile/screens/voice.py`) is never added.
Any navigation to `'voice'` raises `ScreenManagerException: No screen with name "voice"`.

Additionally, `VoiceScreen.__init__` accepts an `on_result` callback, but `HomeScreen`
never wires one up — so even after adding the screen, confirmed addresses would not
flow back to the home screen's address entry.

**TODO:**
```python
# mobile/app.py
from mobile.screens.voice import VoiceScreen

def build(self):
    ...
    self.voice_screen = VoiceScreen(
        name="voice",
        on_result=self._on_voice_result,   # new app-level handler
    )
    sm.add_widget(self.voice_screen)
    ...

def _on_voice_result(self, text: str):
    self.home_screen.addr_input.text = text
    self.navigate("home", "right")
```

Add a mic button to `HomeScreen` that navigates to `'voice'`:
```python
# mobile/screens/home.py — inside _build(), in the entry_row
mic_btn = _btn("🎤", size_hint_x=None, width=dp(44), bg=C_SURFACE)
mic_btn.bind(on_release=lambda *_: App.get_running_app().navigate("voice"))
entry_row.add_widget(mic_btn)
```

---

###  `gui/views/home.py` — row collision on right panel: `adv_frame` and `progress` both target `row=3`

```python
# row 2 — adv_toggle button
adv_toggle.grid(row=2, ...)

# row 3 — adv_frame (advanced options, collapsible)
self._adv_frame.grid(row=3, ...)

# row 3 — progress bar (COLLISION)
self.progress.grid(row=3, ...)

# row 4 — solve_btn
self.solve_btn.grid(row=4, ...)
```

When the advanced frame is hidden, the progress bar sits at row 3 correctly.
When `_adv_frame` is shown, it and `progress` overlap at row 3.

**TODO:** Shift progress and solve button down:
```python
self.progress.grid(row=4, ...)
self.solve_btn.grid(row=5, ...)
ctk.CTkLabel(...).grid(row=6, ...)   # hint text
```

---

### `tests/test_exporter.py` — `build_maps_url` tests assert wrong URL format

`test_exporter.py` asserts:
```python
assert url == MAPS_BASE + "456+Elm+St+Spokane+WA"   # single address
assert url == MAPS_BASE + "A+St/B+Ave"               # two addresses
```

But `build_maps_url()` actually produces:
```
# single address
https://www.google.com/maps/dir/?api=1&destination=456%2BElm%2BSt...&travelmode=driving

# two addresses
https://www.google.com/maps/dir/?api=1&origin=A+St&destination=B+Ave&travelmode=driving
```

The tests test the old `scaffold_ontrack.py` stub implementation, not the real one.
These tests will **fail** even when the actual code is correct.

**TODO:** Update the test assertions to match the real `build_maps_url` output format:
```python
def test_single_address(self):
    url = build_maps_url(["456 Elm St Spokane WA"])
    assert "destination=" in url
    assert "456" in url

def test_two_addresses(self):
    url = build_maps_url(["A St", "B Ave"])
    assert "origin=" in url
    assert "destination=" in url
    assert "travelmode=driving" in url
```

---

### `core/voice.py` — `transcribe_file()` imports `scipy` which is not in `requirements.txt`

```python
import scipy.signal as sps   # inside try/except ImportError for soundfile
```

`scipy` is not listed in `requirements.txt`. On a fresh install the soundfile path
will be taken (soundfile is installed), but any environment that strips or replaces
soundfile will silently break. The `# type: ignore` comment suggests this was known.

**TODO — Option A:** Add `scipy` to `requirements.txt`.

**TODO — Option B (no new dependency):** Replace with a pure-numpy resample:
```python
if sr != SAMPLE_RATE:
    num = int(len(audio) * SAMPLE_RATE / sr)
    audio = np.interp(
        np.linspace(0, len(audio), num),
        np.arange(len(audio)),
        audio.astype(np.float32),
    ).astype(np.int16)
```

---

### `tests/test_platform_compat.py` — `hardware` mark referenced in `test_voice.py` but not registered

`test_voice.py` documents `@pytest.mark.hardware` and `pytest --hardware` usage in its
docstring. The mark is not registered in `pyproject.toml`'s `[tool.pytest.ini_options]`
`markers` list. Running the test suite produces `PytestUnknownMarkWarning` for every
`hardware`-marked test, and `--strict-markers` (if enabled) will cause CI to fail.

**TODO:** Add to `pyproject.toml`:
```toml
[tool.pytest.ini_options]
markers = [
  "linux:    Linux x86_64 build checks",
  "windows:  Windows 11 build checks",
  "android:  Android/Buildozer packaging checks",
  "integration: Requires faster-whisper and sounddevice installed",
  "hardware: Requires a real microphone (never runs in CI)",
]
```

Also add `--hardware` as a custom option to `conftest.py`:
```python
def pytest_addoption(parser):
    parser.addoption("--hardware", action="store_true", default=False)

def pytest_collection_modifyitems(config, items):
    if not config.getoption("--hardware"):
        skip = pytest.mark.skip(reason="Pass --hardware to run")
        for item in items:
            if "hardware" in item.keywords:
                item.add_marker(skip)
```

---

### `results/map_preview` — `_build_map_image` has a dead code branch causing silent failure

In `gui/views/results.py`:
```python
tile = _fetch_osm_tile.__wrapped__(lat, lng, zoom) if False else None
```

`if False` means this branch is unreachable dead code. `_fetch_osm_tile` also has no
`__wrapped__` attribute — this line would raise `AttributeError` if ever reached.
The code was likely left behind during a refactor.

**TODO:** Remove the dead branch entirely:
```python
# Remove this line:
tile = _fetch_osm_tile.__wrapped__(lat, lng, zoom) if False else None
# The try/except block below it already handles all tile fetching correctly.
```

---

## 🟡 MEDIUM — Quality and correctness issues

###  `gui/components/map_preview.py` is a stub (`# Embedded folium or webview`)

`map_preview.py` is never imported by `gui/views/results.py` or any other GUI file.
`results.py` implements OSM tile fetching directly with inline code. The stub file
and `folium` dependency in `requirements.txt` are dead weight.

**TODO — Option A:** Implement `MapPreview` as a `CTkFrame` that wraps the OSM/folium
tile-stitching logic currently inline in `results.py` and import it there.

**TODO — Option B:** Delete `map_preview.py` and remove `folium>=0.14` from
`requirements.txt` if folium is not actually used anywhere (it is not — confirmed by
grep). Update `test_platform_compat.py` to remove `test_folium_importable`.

---

###  `gui/components/address_table.py` is a stub (`# Scrollable stop list`)

`address_table.py` is empty. The stop list in `gui/views/home.py` is built inline
using a `tk.Listbox`. This is inconsistent with the stated component architecture.

**TODO:** Either implement `AddressTable` as a proper `CTkFrame` widget and use it
in `home.py`, or delete the stub and remove it from `gui/components/__init__.py`.

---

###  `routingpy` in `requirements.txt` — imported nowhere, never used

`grep` across all `.py` files finds `routingpy` only in the stale `scaffold_ontrack.py`.
It is not imported in any production module.

**TODO:** Remove from `requirements.txt` (and from `pyproject.toml` dependencies once
issue #2 is fixed).

---

### `pyshortcuts` in `requirements.txt` — superseded by installer's own shortcut logic

`pyshortcuts` appears only in `scaffold_ontrack.py`. The actual installer
(`installer/ontrack_installer.py`) implements its own `.lnk` / `.desktop` creation
using `powershell` and `pathlib` — it does not import `pyshortcuts`.

**TODO:** Remove `pyshortcuts>=1.9` from `requirements.txt`.

---

###  `pyproject.toml` — `[tool.coverage.run]` omits `gui/` and `mobile/`

```toml
[tool.coverage.run]
source = ["core", "config"]
omit = ["tests/*", "gui/*", "assets/*"]
```

`gui/` is explicitly omitted but `mobile/` is not in source either. The `fail_under = 70`
threshold is trivially met by `core/` alone.

**TODO:**
```toml
[tool.coverage.run]
source = ["core", "config", "gui", "mobile"]
omit = ["tests/*", "assets/*", "installer/*"]
```

---

### `pip.conf` in repo root — affects all pip invocations on any machine that runs from this directory

`ontrack/pip.conf` pins `index-url = https://pypi.org/simple/` globally. This is
intentional for build hygiene, but having it in the working directory means it silently
affects any developer who `cd`s into `ontrack/` and runs pip — overriding their own
`~/.config/pip/pip.conf`.

**TODO:** Document this behavior in `README.md` and in the file itself. Alternatively,
move the intent into `pyproject.toml`'s `[tool.pip]` table (PEP 517/518 aware):
```toml
[tool.pip]
index-url = "https://pypi.org/simple/"
no-extra-index-url = true
```

---

###  `flake.nix` — `CHANGELOG.md` referenced but does not exist

```nix
changelog = "https://github.com/qompassai/Python/blob/main/ontrack/CHANGELOG.md";
```

**TODO:** Create `ontrack/CHANGELOG.md` (even a stub), or remove the attribute.

---

### `config/settings.py` — `ORG_NAME` hardcoded to `"TDS Telecom"`

**TODO:** Load from environment to support multi-org deployments:
```python
ORG_NAME: str = os.getenv("ORG_NAME", "TDS Telecom")
```

Add `ORG_NAME=""` to `.env.example`.

---

### `core/matrix.py` — `_google_matrix` passes address strings, not lat/lng coords

The Google Distance Matrix API call uses raw address strings as `origins`/`destinations`.
The API re-geocodes them server-side, which may produce different canonical forms than
`geocoder.py` used. Using the already-geocoded coordinates is more reliable and avoids
a second geocoding round-trip.

**TODO:**
```python
origins = '|'.join(
    f"{locations[i+ri]['lat']},{locations[i+ri]['lng']}"
    for ri in range(min(batch, n - i))
)
```

---

###  `ontrack.spec` — `datas` list omits `gui/` and `mobile/`

PyInstaller's `Analysis` discovers Python packages via `pathex`, but any non-Python
data files (`.kv` Kivy layouts, templates, etc.) added later to `gui/` or `mobile/`
will be silently dropped from the frozen binary.

**TODO:**
```python
datas=[
    ("assets",  "assets"),
    ("config",  "config"),
    ("gui",     "gui"),
    ("mobile",  "mobile"),
],
```

---

###  `renovate.jsonc` — file comment points to wrong repo

```jsonc
// /qompassai/bunker/renovate.json5
```

**TODO:**
```jsonc
// /qompassai/Python/ontrack/renovate.jsonc
```

---


### `.gitignore` excludes `*.spec` — this hides `ontrack.spec` from the repo

```
*.spec
```

Both `ontrack.spec` (PyInstaller) and `buildozer.spec` are committed intentionally
and needed for reproducible builds, but `*.spec` would exclude them from tracking
if `.gitignore` were applied retroactively or on a fresh clone.

**TODO:** Add explicit exceptions:
```
*.spec
!ontrack.spec
!buildozer.spec
!installer/installer.spec
```

---

###  `tags` file committed to version control

A `tags` (ctags/etags) file is present at `ontrack/tags`. This is a local developer
tooling artifact.

**TODO:** Add to `.gitignore`:
```
tags
.tags
```

---

###  `scaffold_ontrack.py` — stale bootstrapper with outdated stub content

The scaffold script creates minimal stubs that are now superceded by the full
implementations. It should not be confused with production code.

**TODO:** Move to `tools/scaffold_ontrack.py` and add a prominent comment:
```python
# NOTE: This is a one-time project bootstrapper. All files it would create
# already exist with full implementations. Do not run this on an existing checkout.
```

---

### 32. `README.md` — likely stale, needs a full update

Verify `README.md` documents:
- Desktop install: `pip install -r requirements.txt && python main.py`
- Android build: `nix develop` → `bash build.sh`
- `.env` setup (copy `.env.example` → `.env`)
- `ONTRACK_WHISPER_MODEL` env var for model selection
- PipeWire echo-cancel setup: reference `pipewire/README.md` and `pipewire/51-ontrack-echo-cancel.conf`
- `python assets/convert.py` must be run before first build

---

###  `tests/` — no `__init__.py`

`tests/` has no `__init__.py`. While `pytest` discovers tests without it, absolute
imports inside tests (e.g. `from core.solver import ...`) require the repo root on
`sys.path`. This works with `pytest` run from the `ontrack/` directory but may fail
when run from the repo root or in certain CI configurations.

**TODO:** Add an empty `tests/__init__.py`, or add `pythonpath = ["."]` to
`pyproject.toml`:
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

---


