"""
test_platform_compat.py — cross-platform build compatibility probes

These tests do NOT actually compile the app. They verify that every
dependency, import path, and runtime assumption is sound on the current
platform, so you can run this matrix on CI:

  Linux x86_64  →  standard pytest run (always passes if env is correct)
  Windows 11    →  same run under windows-latest GitHub Actions runner
  Android       →  buildozer dry-run + p4a recipe existence checks

Tests are split into three marks so you can run a subset:
  pytest -m linux
  pytest -m windows
  pytest -m android

All three marks are applied where a check is genuinely platform-agnostic.
"""

import sys
import platform
import importlib
import pathlib
import subprocess
import shutil

import pytest

# ── Helpers ────────────────────────────────────────────────────────────────

def _importable(name: str) -> bool:
    try:
        importlib.import_module(name)
        return True
    except ImportError:
        return False


def _cmd_exists(cmd: str) -> bool:
    return shutil.which(cmd) is not None


ONTRACK_ROOT = pathlib.Path(__file__).parent.parent


# ══════════════════════════════════════════════════════════════════════════
# 1. PYTHON VERSION — must be ≥3.9 on all targets
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.linux
@pytest.mark.windows
@pytest.mark.android
def test_python_version():
    """Python ≥ 3.9 required for 'list[str]' type hints and match statements."""
    assert sys.version_info >= (3, 9), (
        f"Python 3.9+ required, running {sys.version}"
    )


# ══════════════════════════════════════════════════════════════════════════
# 2. CORE RUNTIME IMPORTS — packages that must exist on all targets
# ══════════════════════════════════════════════════════════════════════════

CORE_DEPS = [
    ("pandas",       "Data parsing (CSV/Excel)"),
    ("openpyxl",     "Excel file support"),
    ("geopy",        "Nominatim geocoding"),
    ("requests",     "HTTP calls to OSRM / Google"),
    ("ortools",      "OR-Tools TSP solver"),
    ("ortools.constraint_solver.pywrapcp", "OR-Tools CP bindings"),
    ("dotenv",       "python-dotenv env loading"),
]


@pytest.mark.linux
@pytest.mark.windows
@pytest.mark.android
@pytest.mark.parametrize("module,purpose", CORE_DEPS, ids=[m for m, _ in CORE_DEPS])
def test_core_import(module, purpose):
    """Every core dependency must be importable."""
    assert _importable(module), (
        f"Cannot import '{module}' — needed for {purpose}. "
        f"Run: pip install -r requirements.txt"
    )


# ══════════════════════════════════════════════════════════════════════════
# 3. LINUX x86_64 SPECIFIC
# ══════════════════════════════════════════════════════════════════════════

class TestLinuxCompat:
    """Checks for PyInstaller one-file build on Linux x86_64."""

    @pytest.mark.linux
    def test_platform_is_linux_or_ci(self):
        """Warn if running on a non-Linux host — results may not apply."""
        if platform.system() != "Linux":
            pytest.skip("Linux-specific check; skipping on non-Linux host")

    @pytest.mark.linux
    def test_customtkinter_importable(self):
        """CustomTkinter is the desktop GUI — required for Linux/Windows builds."""
        assert _importable("customtkinter"), (
            "customtkinter not found. Install: pip install customtkinter"
        )

    @pytest.mark.linux
    def test_pyinstaller_importable(self):
        assert _importable("PyInstaller"), (
            "PyInstaller not found. Install: pip install pyinstaller"
        )

    @pytest.mark.linux
    def test_pyinstaller_cli_available(self):
        assert _cmd_exists("pyinstaller"), (
            "pyinstaller binary not on PATH. "
            "Ensure your venv is activated or pip install pyinstaller."
        )

    @pytest.mark.linux
    def test_ontrack_spec_exists(self):
        """ontrack.spec must exist for PyInstaller to reproduce the build."""
        assert (ONTRACK_ROOT / "ontrack.spec").exists(), (
            "ontrack.spec missing — PyInstaller cannot reproduce the frozen build."
        )

    @pytest.mark.linux
    def test_main_entrypoint_exists(self):
        assert (ONTRACK_ROOT / "main.py").exists()

    @pytest.mark.linux
    def test_tkinter_available(self):
        """Tkinter is a system dep (python3-tk) — must exist for CustomTkinter."""
        assert _importable("tkinter"), (
            "tkinter not available. On Arch: sudo pacman -S tk\n"
            "On Debian/Ubuntu: sudo apt install python3-tk"
        )

    @pytest.mark.linux
    def test_pillow_importable(self):
        """Pillow is used by CustomTkinter for icon/image handling."""
        assert _importable("PIL"), (
            "Pillow not found. Install: pip install Pillow"
        )

    @pytest.mark.linux
    def test_folium_importable(self):
        assert _importable("folium"), (
            "folium not found. Install: pip install folium"
        )

    @pytest.mark.linux
    def test_no_windows_only_imports_in_core(self):
        """Core modules must not import winreg, win32api, or msvcrt."""
        windows_only = {"winreg", "win32api", "win32con", "msvcrt", "winsound"}
        core_dir = ONTRACK_ROOT / "core"
        for pyfile in core_dir.glob("*.py"):
            source = pyfile.read_text()
            for mod in windows_only:
                assert f"import {mod}" not in source, (
                    f"{pyfile.name} imports Windows-only module '{mod}'"
                )


# ══════════════════════════════════════════════════════════════════════════
# 4. WINDOWS 11 SPECIFIC
# ══════════════════════════════════════════════════════════════════════════

class TestWindowsCompat:
    """Checks for PyInstaller one-file build on Windows 11."""

    @pytest.mark.windows
    def test_customtkinter_importable(self):
        assert _importable("customtkinter"), "customtkinter missing"

    @pytest.mark.windows
    def test_pyinstaller_importable(self):
        assert _importable("PyInstaller"), "PyInstaller missing"

    @pytest.mark.windows
    def test_pillow_importable(self):
        assert _importable("PIL"), "Pillow missing"

    @pytest.mark.windows
    def test_no_posix_only_calls_in_core(self):
        """
        Core modules must not call os.fork(), os.getpwnam(), or open
        paths with hard-coded forward slashes as the root (e.g. /etc/).
        Windows CI will catch these at import time if they're top-level.
        """
        posix_only = ["os.fork(", "os.getpwnam(", "os.getpwuid("]
        core_dir = ONTRACK_ROOT / "core"
        for pyfile in core_dir.glob("*.py"):
            source = pyfile.read_text()
            for call in posix_only:
                assert call not in source, (
                    f"{pyfile.name} uses POSIX-only call '{call}'"
                )

    @pytest.mark.windows
    def test_pathlib_used_not_hardcoded_slash(self):
        """
        Verify that file operations use pathlib.Path or os.path rather
        than string concatenation with '/' — catches Windows path bugs.
        """
        danger = [
            "open('/'",
            'open("/',
        ]
        for pyfile in (ONTRACK_ROOT / "core").glob("*.py"):
            src = pyfile.read_text()
            for pat in danger:
                assert pat not in src, (
                    f"{pyfile.name} appears to hard-code a POSIX root path"
                )

    @pytest.mark.windows
    def test_csv_newline_kwarg_in_exporter(self):
        """
        export_csv must pass newline='' to open() to avoid double CR on Windows.
        This is a very common Windows bug for csv.writer.
        """
        src = (ONTRACK_ROOT / "core" / "exporter.py").read_text()
        assert 'newline=""' in src or "newline=''" in src, (
            "exporter.py open() call is missing newline='' — "
            "CSV on Windows will have double carriage returns."
        )


# ══════════════════════════════════════════════════════════════════════════
# 5. ANDROID / BUILDOZER SPECIFIC
# ══════════════════════════════════════════════════════════════════════════

class TestAndroidCompat:
    """
    Checks for buildozer/python-for-android (p4a) packaging on Android.
    These do not require a connected device; they validate build config.
    """

    @pytest.mark.android
    def test_buildozer_spec_exists(self):
        assert (ONTRACK_ROOT / "buildozer.spec").exists(), (
            "buildozer.spec is missing. Run: buildozer init"
        )

    @pytest.mark.android
    def test_buildozer_spec_has_required_fields(self):
        spec = (ONTRACK_ROOT / "buildozer.spec").read_text()
        required = [
            "title =",
            "package.name =",
            "package.domain =",
            "version =",
            "requirements =",
            "android.permissions =",
            "android.api =",
            "android.minapi =",
        ]
        for field in required:
            assert field in spec, f"buildozer.spec missing field: '{field}'"

    @pytest.mark.android
    def test_internet_permission_declared(self):
        spec = (ONTRACK_ROOT / "buildozer.spec").read_text()
        assert "INTERNET" in spec, (
            "INTERNET permission missing from buildozer.spec — "
            "OSRM/Nominatim calls will be blocked on Android."
        )

    @pytest.mark.android
    def test_kivy_in_requirements(self):
        spec = (ONTRACK_ROOT / "buildozer.spec").read_text()
        assert "kivy" in spec.lower(), (
            "kivy must be listed in buildozer.spec requirements."
        )

    @pytest.mark.android
    def test_customtkinter_not_in_requirements(self):
        """CustomTkinter uses Tkinter which is unavailable on Android."""
        spec = (ONTRACK_ROOT / "buildozer.spec").read_text()
        lines = [l for l in spec.splitlines() if l.strip().startswith("requirements")]
        for line in lines:
            assert "customtkinter" not in line.lower(), (
                "customtkinter is listed in buildozer.spec requirements but "
                "Tkinter does NOT exist on Android. Use Kivy/KivyMD instead."
            )

    @pytest.mark.android
    def test_tkinter_not_imported_in_gui(self):
        """
        The gui/ layer must not import tkinter or customtkinter —
        those packages do not exist in python-for-android.
        """
        tk_imports = {"import tkinter", "from tkinter", "import customtkinter", "from customtkinter"}
        gui_dir = ONTRACK_ROOT / "gui"
        offenders = []
        for pyfile in gui_dir.rglob("*.py"):
            src = pyfile.read_text()
            for pattern in tk_imports:
                if pattern in src:
                    offenders.append(f"{pyfile.relative_to(ONTRACK_ROOT)}: '{pattern}'")
        assert not offenders, (
            "GUI files import Tkinter/CustomTkinter — these won't work on Android:\n"
            + "\n".join(offenders)
        )

    @pytest.mark.android
    def test_assets_directory_exists(self):
        assert (ONTRACK_ROOT / "assets").is_dir()

    @pytest.mark.android
    def test_presplash_asset_exists(self):
        """buildozer.spec references ontrack.jpg as presplash."""
        assert (ONTRACK_ROOT / "assets" / "ontrack.jpg").exists(), (
            "assets/ontrack.jpg missing — buildozer presplash will fail."
        )

    @pytest.mark.android
    def test_no_dotenv_in_android_main(self):
        """
        python-dotenv reads .env files from the filesystem, which is
        sandboxed on Android. The main entry point should not call
        load_dotenv() at module level without a try/except.
        """
        main_src = (ONTRACK_ROOT / "main.py").read_text()
        config_src = (ONTRACK_ROOT / "config" / "settings.py").read_text()
        combined = main_src + config_src
        if "load_dotenv" in combined:
            # Acceptable if it's inside a try block
            assert "try" in combined, (
                "load_dotenv() is called at module level without try/except. "
                "On Android, .env files may not exist — wrap in try/except."
            )

    @pytest.mark.android
    def test_ortools_not_in_buildozer_requirements(self):
        """
        OR-Tools has no pre-built p4a recipe and will fail the buildozer
        compile step. It must either be absent from buildozer requirements
        or replaced with a pure-Python fallback for Android.
        """
        spec = (ONTRACK_ROOT / "buildozer.spec").read_text()
        req_lines = [l for l in spec.splitlines() if l.strip().startswith("requirements")]
        for line in req_lines:
            if not line.strip().startswith("#"):
                assert "ortools" not in line.lower(), (
                    "ortools is listed in active buildozer.spec requirements. "
                    "OR-Tools has no python-for-android recipe and will break "
                    "the Android build. Comment it out and use a pure-Python "
                    "fallback (e.g. nearest-neighbor heuristic) for the mobile build."
                )

    @pytest.mark.android
    def test_archs_include_arm64(self):
        spec = (ONTRACK_ROOT / "buildozer.spec").read_text()
        assert "arm64-v8a" in spec, (
            "arm64-v8a missing from android.archs — modern Android phones need it."
        )

    @pytest.mark.android
    def test_min_api_24_or_higher(self):
        """Android API 24 (Android 7) is the p4a minimum for SDL2 bootstrap."""
        spec = (ONTRACK_ROOT / "buildozer.spec").read_text()
        for line in spec.splitlines():
            if line.strip().startswith("android.minapi"):
                val = int(line.split("=")[1].strip())
                assert val >= 24, f"android.minapi must be ≥ 24, got {val}"
                return
        pytest.fail("android.minapi not found in buildozer.spec")


# ══════════════════════════════════════════════════════════════════════════
# 6. DEPENDENCY VERSIONS — python-for-android recipe compatibility
# ══════════════════════════════════════════════════════════════════════════

class TestDependencyVersions:
    @pytest.mark.linux
    @pytest.mark.windows
    def test_pandas_version(self):
        """pandas ≥ 1.3 required for proper CSV/Excel handling."""
        import pandas as pd
        major, minor = map(int, pd.__version__.split(".")[:2])
        assert (major, minor) >= (1, 3), f"pandas {pd.__version__} < 1.3"

    @pytest.mark.linux
    @pytest.mark.windows
    @pytest.mark.android
    def test_requests_version(self):
        """requests ≥ 2.28 for modern SSL + urllib3 v2 compat."""
        import requests
        parts = list(map(int, requests.__version__.split(".")[:2]))
        assert parts >= [2, 28], f"requests {requests.__version__} < 2.28"

    @pytest.mark.linux
    @pytest.mark.windows
    @pytest.mark.android
    def test_geopy_version(self):
        """geopy ≥ 2.0 required (Nominatim API changed in v2)."""
        import geopy
        major = int(geopy.__version__.split(".")[0])
        assert major >= 2, f"geopy {geopy.__version__} < 2.0"
