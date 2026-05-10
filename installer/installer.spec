#/qompassai/ONTrack/installer/installer.spec
# -*- mode: python ; coding: utf-8 -*-
#
#
# Build:
#   cd ontrack/installer
#   pyinstaller installer.spec
#
# Output:
#   dist/OnTrackInstaller.exe   (Windows)
#   dist/OnTrackInstaller       (Linux)

import sys
import os
import pathlib

APP_ROOT = str(pathlib.Path(SPECPATH).parent)

block_cipher = None

a = Analysis(
    [os.path.join(SPECPATH, "ontrack_installer.py")],
    pathex=[SPECPATH, APP_ROOT],
    binaries=[],
    datas=[
        (os.path.join(APP_ROOT, ".env.example"),                  "."),
        (os.path.join(APP_ROOT, "assets"),                        "assets"),
        (os.path.join(APP_ROOT, "config"),                        "config"),
        (os.path.join(APP_ROOT, "core"),                          "core"),
        (os.path.join(APP_ROOT, "gui"),                           "gui"),
        (os.path.join(APP_ROOT, "main.py"),                       "."),
        (os.path.join(APP_ROOT, "mobile"),                        "mobile"),
        (os.path.join(APP_ROOT, "requirements-android.txt"),      "."),
        (os.path.join(APP_ROOT, "requirements.txt"),              "."),
        (os.path.join(SPECPATH, "build_info.jsonc"),              "."),
    ],
    hiddenimports=[
        "customtkinter",
        "logging.handlers",
        "PIL",
        "PIL.Image",
        "PIL.ImageDraw",
        "PIL.ImageFont",
        "PIL.ImageTk",
        "pkg_resources.py2_compat",
        "tkinter",
        "tkinter.filedialog",
        "tkinter.messagebox",
        "tkinter.ttk",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "android",
        "jnius",
        "kivy",
        "ortools",
        "plyer",
        "pytest",
        "unittest",
        "matplotlib",
        "scipy",
        "sklearn",
        "tensorflow",
        "torch",
        "xmlrpc",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="OnTrackInstaller",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[
        "vcruntime140.dll",
        "python3*.dll",
        "libpython*.so*",
    ],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=(
        os.path.join(APP_ROOT, "assets", "icon.ico") if sys.platform == "win32"
        else os.path.join(APP_ROOT, "assets", "icon.png") if sys.platform.startswith("linux")
        else None
    ),
    version_file=None,
)
#TODO: MacOS
# app = BUNDLE(
#     exe,
#     name="OnTrackInstaller.app",
#     icon=os.path.join(APP_ROOT, "assets", "icon.icns"),
#     bundle_identifier="com.amorfatilabs.ontrack.installer",
#     info_plist={
#         "NSHighResolutionCapable": True,
#         "LSMinimumSystemVersion": "12.0",
#     },
# )
