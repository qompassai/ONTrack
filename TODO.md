# OnTrack — Build & Correctness TODO

> Repo: `qompassai/Python` → `ontrack/`
---

### 1. Missing `Cargo.toml` and `src/lib.rs` — maturin build backend has no source

`pyproject.toml` sets `maturin` as the build backend and references `ontrack/Cargo.toml`:

```toml
[build-system]
requires = ["maturin>=1.4,<2.0"]
build-backend = "maturin"

[tool.maturin]
cargo-extra-args = ["--manifest-path", "ontrack/Cargo.toml"]
```

There are **zero Rust files in the entire repo**. Running `pip install .` or `maturin develop` fails immediately.

**Fix — Option A (recommended, no Rust needed):** Replace maturin with setuptools since the project is pure Python:

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.backends.legacy:build"

[tool.setuptools.packages.find]
where = ["."]
include = ["core*", "config*", "gui*", "mobile*"]
```

Remove the entire `[tool.maturin]` section.

**Fix — Option B (keep Rust):** Scaffold a minimal PyO3 extension:
```
Cargo.toml
src/lib.rs
```

---

### 2. `pyproject.toml` — only `fastapi` listed as a dependency (wrong project copy-paste)

`[project].dependencies` reads `["fastapi>=0.115.0"]`. The actual runtime deps live only in `requirements.txt` and are invisible to `pip install .`.

**Fix:** Replace with the correct dependency list:

```toml
dependencies = [
    "pandas>=1.5",
    "openpyxl>=3.0",
    "geopy>=2.3",
    "requests>=2.28",
    "ortools>=9.5",
    "python-dotenv>=1.0",
    "customtkinter>=5.2",
    "Pillow>=9.0",
    "folium>=0.14",
    "faster-whisper>=1.0",
    "sounddevice>=0.4.6",
    "soundfile>=0.12",
]
```

Remove `fastapi`. Add `routingpy` only if it is actually used (see issue #17).

---

### 3. `assets/convert.py` opens `assets/icon.jpg` which does not exist

The converter reads `assets/icon.jpg` but the repo contains `assets/ontrack.jpg`.
Running `python assets/convert.py` raises `FileNotFoundError`.

This is the same script that must be run to generate the missing `ontrack.png` and `ontrack.ico`
required by buildozer and PyInstaller respectively.

**Fix:** Update `assets/convert.py`:
```python
# Change this line:
src = Image.open("assets/icon.jpg").convert("RGBA")
# To:
src = Image.open("assets/ontrack.jpg").convert("RGBA")

# And update output filenames:
src.save("assets/ontrack.png")
src.save("assets/ontrack.ico", format="ICO", sizes=[
    (16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)
])
```

Then run `python assets/convert.py` from the `ontrack/` directory to generate the missing files.

---

### 4. Missing `assets/ontrack.png` — Buildozer icon packaging fails

`buildozer.spec` references:
```
icon.filename = %(source.dir)s/assets/ontrack.png
```

Only `assets/ontrack.jpg` exists. Buildozer will error during APK packaging.

**Fix:** Run the corrected `assets/convert.py` (see issue #3).

---

### 5. Missing `assets/ontrack.ico` — PyInstaller fails on Windows

`ontrack.spec` and `installer/installer.spec` both reference `assets/ontrack.ico`.
The file does not exist. PyInstaller will error on Windows builds.

**Fix:** Run the corrected `assets/convert.py` (see issue #3).

---

### 6. `buildozer.spec` — `android.ndk_path` hardcoded to `/opt/android-ndk`

```ini
android.ndk_path = /opt/android-ndk
```

`flake.nix` installs the NDK at `/opt/android-sdk/ndk/29.0.14206865` and sets both
`ANDROID_NDK_HOME` and `ANDROID_NDK_ROOT` to that path. The spec overrides those
env vars with a path that doesn't exist in the Nix devShell.

**Fix:** Remove `android.ndk_path` from `buildozer.spec` entirely (let Buildozer read
`ANDROID_NDK_HOME` from the environment set by `flake.nix`), or align both:
```ini
android.ndk_path = /opt/android-sdk/ndk/29.0.14206865
```

---

### 7. `gradle.properties` — Python `%(...)s` interpolation syntax is not valid in Gradle

```properties
android.buildCacheDir=%(XDG_CACHE_HOME)s/buildozer/ontrack/gradle-cache
```

Gradle reads this as a literal string. The cache will be written to a directory named
`%(XDG_CACHE_HOME)s/buildozer/...`, which does not exist and may fail on some hosts.

**Fix:**
```properties
android.buildCacheDir=/var/tmp/buildozer/ontrack/gradle-cache
```

---

### 8. `build.sh` — hardcoded `~/.local/bin/buildozer` path, not activated from Nix venv

```bash
~/.local/bin/buildozer android debug 2>&1 | tee ~/buildozer_debug.log
```

The `flake.nix` `shellHook` creates `.venv-buildozer/` and activates it. Inside that
venv, `buildozer` is on `$PATH`. The hardcoded `~/.local/bin/buildozer` bypasses this
and may invoke a different (incompatible) buildozer version, or fail if buildozer is
not user-installed at all.

**Fix:**
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

## 🟠 HIGH — Tests fail or core features broken

### 9. `buildozer.spec` — `RECORD_AUDIO` permission missing

`buildozer.spec` lists `ACCESS_FINE_LOCATION`, `INTERNET`, etc., but is missing
`RECORD_AUDIO`. The voice screen (`mobile/screens/voice.py`) calls
`request_permissions([Permission.RECORD_AUDIO])` at runtime, but Android will deny
the permission request if it is not declared in the manifest.

**Fix:** Add to `buildozer.spec`:
```ini
android.permissions =
    ACCESS_BACKGROUND_LOCATION,
    ACCESS_COARSE_LOCATION,
    ACCESS_FINE_LOCATION,
    ACCESS_NETWORK_STATE,
    INTERNET,
    READ_EXTERNAL_STORAGE,
    RECORD_AUDIO,
    WRITE_EXTERNAL_STORAGE
```

---

### 10. `buildozer.spec` — `faster-whisper` absent from `requirements`

The voice feature requires `faster-whisper` (and its dependency `ctranslate2`) on Android.
Neither is listed in `buildozer.spec`'s `requirements` block. Voice transcription will
be unavailable in the APK even though `VoiceScreen` is built for it.

**Fix:**
```ini
requirements =
    geopy,
    kivy==2.3.0,
    Pillow,
    plyer,
    python3,
    python-dotenv,
    requests,
    faster-whisper,
    ctranslate2
```

Verify an ARM64 wheel exists for `ctranslate2`; if the build fails, pin versions as
noted in `requirements-android.txt`:
```
faster-whisper==0.10.1
ctranslate2==3.24.0
```

---

### 11. `mobile/app.py` — `VoiceScreen` never registered in the `ScreenManager`

`mobile/app.py` adds `HomeScreen`, `ResultsScreen`, and `SettingsScreen` to the
`ScreenManager`. `VoiceScreen` (defined in `mobile/screens/voice.py`) is never added.
Any navigation to `'voice'` raises `ScreenManagerException: No screen with name "voice"`.

Additionally, `VoiceScreen.__init__` accepts an `on_result` callback, but `HomeScreen`
never wires one up — so even after adding the screen, confirmed addresses would not
flow back to the home screen's address entry.

**Fix:**
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

### 12. `assets/themes/ontrack.json` is empty `{}`

CustomTkinter silently falls back to the default blue theme when given an empty JSON.
Any brand styling (TDS_BLUE `#0057A8`, TDS_NAVY `#002855`, TDS_ORANGE `#F26522`) is
hardcoded in Python but not in the theme file, which is the correct place for it.

**Fix:** Either populate the theme file following customtkinter's theme schema:
```json
{
  "CTk": { "fg_color": ["#111827", "#111827"] },
  "CTkFrame": { "fg_color": ["#1A2535", "#1A2535"], "top_fg_color": ["#243044", "#243044"] },
  "CTkButton": {
    "fg_color": ["#0057A8", "#0057A8"],
    "hover_color": ["#002855", "#002855"],
    "text_color": ["#FFFFFF", "#FFFFFF"]
  }
}
```
Or remove the theme file and the dead reference to it in `gui/app.py`
(currently `ctk.set_default_color_theme("blue")` is used anyway — the theme file
is never loaded).

---

### 13. `gui/views/home.py` — row collision on right panel: `adv_frame` and `progress` both target `row=3`

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

**Fix:** Shift progress and solve button down:
```python
self.progress.grid(row=4, ...)
self.solve_btn.grid(row=5, ...)
ctk.CTkLabel(...).grid(row=6, ...)   # hint text
```

---

### 14. `tests/test_exporter.py` — `build_maps_url` tests assert wrong URL format

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

**Fix:** Update the test assertions to match the real `build_maps_url` output format:
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

### 15. `core/voice.py` — `transcribe_file()` imports `scipy` which is not in `requirements.txt`

```python
import scipy.signal as sps   # inside try/except ImportError for soundfile
```

`scipy` is not listed in `requirements.txt`. On a fresh install the soundfile path
will be taken (soundfile is installed), but any environment that strips or replaces
soundfile will silently break. The `# type: ignore` comment suggests this was known.

**Fix — Option A:** Add `scipy` to `requirements.txt`.

**Fix — Option B (no new dependency):** Replace with a pure-numpy resample:
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

### 16. `tests/test_platform_compat.py` — `hardware` mark referenced in `test_voice.py` but not registered

`test_voice.py` documents `@pytest.mark.hardware` and `pytest --hardware` usage in its
docstring. The mark is not registered in `pyproject.toml`'s `[tool.pytest.ini_options]`
`markers` list. Running the test suite produces `PytestUnknownMarkWarning` for every
`hardware`-marked test, and `--strict-markers` (if enabled) will cause CI to fail.

**Fix:** Add to `pyproject.toml`:
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

### 17. `results/map_preview` — `_build_map_image` has a dead code branch causing silent failure

In `gui/views/results.py`:
```python
tile = _fetch_osm_tile.__wrapped__(lat, lng, zoom) if False else None
```

`if False` means this branch is unreachable dead code. `_fetch_osm_tile` also has no
`__wrapped__` attribute — this line would raise `AttributeError` if ever reached.
The code was likely left behind during a refactor.

**Fix:** Remove the dead branch entirely:
```python
# Remove this line:
tile = _fetch_osm_tile.__wrapped__(lat, lng, zoom) if False else None
# The try/except block below it already handles all tile fetching correctly.
```

---

## 🟡 MEDIUM — Quality and correctness issues

### 18. `gui/components/map_preview.py` is a stub (`# Embedded folium or webview`)

`map_preview.py` is never imported by `gui/views/results.py` or any other GUI file.
`results.py` implements OSM tile fetching directly with inline code. The stub file
and `folium` dependency in `requirements.txt` are dead weight.

**Fix — Option A:** Implement `MapPreview` as a `CTkFrame` that wraps the OSM/folium
tile-stitching logic currently inline in `results.py` and import it there.

**Fix — Option B:** Delete `map_preview.py` and remove `folium>=0.14` from
`requirements.txt` if folium is not actually used anywhere (it is not — confirmed by
grep). Update `test_platform_compat.py` to remove `test_folium_importable`.

---

### 19. `gui/components/address_table.py` is a stub (`# Scrollable stop list`)

`address_table.py` is empty. The stop list in `gui/views/home.py` is built inline
using a `tk.Listbox`. This is inconsistent with the stated component architecture.

**Fix:** Either implement `AddressTable` as a proper `CTkFrame` widget and use it
in `home.py`, or delete the stub and remove it from `gui/components/__init__.py`.

---

### 20. `routingpy` in `requirements.txt` — imported nowhere, never used

`grep` across all `.py` files finds `routingpy` only in the stale `scaffold_ontrack.py`.
It is not imported in any production module.

**Fix:** Remove from `requirements.txt` (and from `pyproject.toml` dependencies once
issue #2 is fixed).

---

### 21. `pyshortcuts` in `requirements.txt` — superseded by installer's own shortcut logic

`pyshortcuts` appears only in `scaffold_ontrack.py`. The actual installer
(`installer/ontrack_installer.py`) implements its own `.lnk` / `.desktop` creation
using `powershell` and `pathlib` — it does not import `pyshortcuts`.

**Fix:** Remove `pyshortcuts>=1.9` from `requirements.txt`.

---

### 22. `pyproject.toml` — `[tool.coverage.run]` omits `gui/` and `mobile/`

```toml
[tool.coverage.run]
source = ["core", "config"]
omit = ["tests/*", "gui/*", "assets/*"]
```

`gui/` is explicitly omitted but `mobile/` is not in source either. The `fail_under = 70`
threshold is trivially met by `core/` alone.

**Fix:**
```toml
[tool.coverage.run]
source = ["core", "config", "gui", "mobile"]
omit = ["tests/*", "assets/*", "installer/*"]
```

---

### 23. `pip.conf` in repo root — affects all pip invocations on any machine that runs from this directory

`ontrack/pip.conf` pins `index-url = https://pypi.org/simple/` globally. This is
intentional for build hygiene, but having it in the working directory means it silently
affects any developer who `cd`s into `ontrack/` and runs pip — overriding their own
`~/.config/pip/pip.conf`.

**Fix:** Document this behavior in `README.md` and in the file itself. Alternatively,
move the intent into `pyproject.toml`'s `[tool.pip]` table (PEP 517/518 aware):
```toml
[tool.pip]
index-url = "https://pypi.org/simple/"
no-extra-index-url = true
```

---

### 24. `flake.nix` — `CHANGELOG.md` referenced but does not exist

```nix
changelog = "https://github.com/qompassai/Python/blob/main/ontrack/CHANGELOG.md";
```

**Fix:** Create `ontrack/CHANGELOG.md` (even a stub), or remove the attribute.

---

### 25. `config/settings.py` — `ORG_NAME` hardcoded to `"TDS Telecom"`

**Fix:** Load from environment to support multi-org deployments:
```python
ORG_NAME: str = os.getenv("ORG_NAME", "TDS Telecom")
```

Add `ORG_NAME=""` to `.env.example`.

---

### 26. `core/matrix.py` — `_google_matrix` passes address strings, not lat/lng coords

The Google Distance Matrix API call uses raw address strings as `origins`/`destinations`.
The API re-geocodes them server-side, which may produce different canonical forms than
`geocoder.py` used. Using the already-geocoded coordinates is more reliable and avoids
a second geocoding round-trip.

**Fix:**
```python
origins = '|'.join(
    f"{locations[i+ri]['lat']},{locations[i+ri]['lng']}"
    for ri in range(min(batch, n - i))
)
```

---

### 27. `ontrack.spec` — `datas` list omits `gui/` and `mobile/`

PyInstaller's `Analysis` discovers Python packages via `pathex`, but any non-Python
data files (`.kv` Kivy layouts, templates, etc.) added later to `gui/` or `mobile/`
will be silently dropped from the frozen binary.

**Fix:**
```python
datas=[
    ("assets",  "assets"),
    ("config",  "config"),
    ("gui",     "gui"),
    ("mobile",  "mobile"),
],
```

---

### 28. `renovate.jsonc` — file comment points to wrong repo

```jsonc
// /qompassai/bunker/renovate.json5
```

**Fix:**
```jsonc
// /qompassai/Python/ontrack/renovate.jsonc
```

---

## 🟢 LOW — Housekeeping

### 29. `.gitignore` excludes `*.spec` — this hides `ontrack.spec` from the repo

```
*.spec
```

Both `ontrack.spec` (PyInstaller) and `buildozer.spec` are committed intentionally
and needed for reproducible builds, but `*.spec` would exclude them from tracking
if `.gitignore` were applied retroactively or on a fresh clone.

**Fix:** Add explicit exceptions:
```
*.spec
!ontrack.spec
!buildozer.spec
!installer/installer.spec
```

---

### 30. `tags` file committed to version control

A `tags` (ctags/etags) file is present at `ontrack/tags`. This is a local developer
tooling artifact.

**Fix:** Add to `.gitignore`:
```
tags
.tags
```

---

### 31. `scaffold_ontrack.py` — stale bootstrapper with outdated stub content

The scaffold script creates minimal stubs that are now superceded by the full
implementations. It should not be confused with production code.

**Fix:** Move to `tools/scaffold_ontrack.py` and add a prominent comment:
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

### 33. `tests/` — no `__init__.py`

`tests/` has no `__init__.py`. While `pytest` discovers tests without it, absolute
imports inside tests (e.g. `from core.solver import ...`) require the repo root on
`sys.path`. This works with `pytest` run from the `ontrack/` directory but may fail
when run from the repo root or in certain CI configurations.

**Fix:** Add an empty `tests/__init__.py`, or add `pythonpath = ["."]` to
`pyproject.toml`:
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

---

## Summary Table

| # | Severity | Area | Issue |
|---|----------|------|-------|
| 1 | 🔴 Critical | Build | `Cargo.toml`/`src/lib.rs` absent — maturin build backend has no source |
| 2 | 🔴 Critical | Build | `pyproject.toml` only lists `fastapi` as dependency — wrong project |
| 3 | 🔴 Critical | Assets | `assets/convert.py` opens `icon.jpg` (doesn't exist), not `ontrack.jpg` |
| 4 | 🔴 Critical | Android | `assets/ontrack.png` missing — buildozer icon fails |
| 5 | 🔴 Critical | Windows | `assets/ontrack.ico` missing — PyInstaller fails on Windows |
| 6 | 🔴 Critical | Android | `android.ndk_path` hardcoded, conflicts with `flake.nix` NDK path |
| 7 | 🔴 Critical | Android | `gradle.properties` uses Python `%(...)s` syntax — invalid in Gradle |
| 8 | 🔴 Critical | Android | `build.sh` calls `~/.local/bin/buildozer` bypassing Nix venv |
| 9 | 🟠 High | Android | `RECORD_AUDIO` permission missing from `buildozer.spec` |
| 10 | 🟠 High | Android | `faster-whisper` absent from `buildozer.spec` requirements |
| 11 | 🟠 High | Mobile | `VoiceScreen` not registered in `ScreenManager`; no `on_result` wiring |
| 12 | 🟠 High | Desktop GUI | `assets/themes/ontrack.json` is empty `{}` — theme non-functional |
| 13 | 🟠 High | Desktop GUI | `adv_frame` and `progress` both at `row=3` in right panel — overlap |
| 14 | 🟠 High | Tests | `test_exporter.py` asserts old stub URL format — fails against real code |
| 15 | 🟠 High | Voice | `transcribe_file()` requires `scipy` not in `requirements.txt` |
| 16 | 🟠 High | Tests | `hardware` pytest mark used but not registered — `strict-markers` CI fail |
| 17 | 🟠 High | Desktop GUI | Dead `if False` branch in `_build_map_image` — would raise `AttributeError` |
| 18 | 🟡 Medium | Desktop GUI | `gui/components/map_preview.py` is a stub, never imported, `folium` unused |
| 19 | 🟡 Medium | Desktop GUI | `gui/components/address_table.py` is a stub, never used |
| 20 | 🟡 Medium | Dependencies | `routingpy` in `requirements.txt` — never imported in production code |
| 21 | 🟡 Medium | Dependencies | `pyshortcuts` in `requirements.txt` — superseded by installer logic |
| 22 | 🟡 Medium | Tests | Coverage omits `gui/` and `mobile/` — `fail_under=70` trivially met |
| 23 | 🟡 Medium | Config | `pip.conf` in working directory silently overrides dev pip config |
| 24 | 🟡 Medium | Nix | `flake.nix` references non-existent `CHANGELOG.md` |
| 25 | 🟡 Medium | Config | `ORG_NAME` hardcoded to `"TDS Telecom"` — should be env var |
| 26 | 🟡 Medium | Matrix | `_google_matrix` re-geocodes via address strings instead of lat/lng coords |
| 27 | 🟡 Medium | Packaging | `ontrack.spec` datas omit `gui/` and `mobile/` |
| 28 | 🟡 Medium | Config | `renovate.jsonc` header comment references wrong repo (`bunker`) |
| 29 | 🟢 Low | Repo hygiene | `.gitignore` rule `*.spec` would hide `ontrack.spec` / `buildozer.spec` |
| 30 | 🟢 Low | Repo hygiene | `tags` file committed — add to `.gitignore` |
| 31 | 🟢 Low | Repo hygiene | `scaffold_ontrack.py` is stale bootstrapper — move to `tools/` |
| 32 | 🟢 Low | Docs | `README.md` likely stale — needs full update |
| 33 | 🟢 Low | Tests | `tests/` has no `__init__.py` — may break imports in some CI setups |
