# -*- mode: python ; coding: utf-8 -*-
# Build: pyinstaller ontrack.spec

import sys
import os

block_cipher = None

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=[
        ("assets", "assets"),
        ("config", "config"),
    ],
    hiddenimports=[
        "certifi",
        "charset_normalizer",
        "customtkinter",
        "dotenv",
        "geopy.geocoders",
        "geopy.geocoders.nominatim",
        "geopy.geocoders.googlev3",
        "geopy.geocoders.bing",
        "logging.handlers",
        # openpyxl (pandas xlsx engine)
        "openpyxl",
        "openpyxl.cell._writer",
        "ortools",
        "ortools.constraint_solver",
        "ortools.constraint_solver.pywrapcp",
        "ortools.constraint_solver.routing_enums_pb2",
        "ortools.constraint_solver.routing_parameters_pb2",
        "pandas",
        "pandas._libs.tslibs.base",
        "pandas._libs.tslibs.np_datetime",
        "pandas._libs.tslibs.nattype",
        "pandas._libs.tslibs.timedeltas",
        "pandas._libs.tslibs.timestamps",
        "pandas._libs.tslibs.offsets",
        "pandas.io.formats.style",
        "PIL",
        "PIL.Image",
        "PIL.ImageDraw",
        "PIL.ImageFont",
        "PIL.ImageTk",
        "pkg_resources.py2_compat",
        "google.protobuf",
        "google.protobuf.descriptor",
        "google.protobuf.descriptor_pool",
        "google.protobuf.message",
        "google.protobuf.reflection",
        "google.protobuf.runtime_version",
        "google.protobuf.symbol_database",
        "pytz",
        "requests",
        "requests.adapters",
        "requests.packages",
        "urllib3",
        "urllib3.contrib",
        "urllib3.util",
        "tkinter",
        "tkinter.ttk",
        "tkinter.filedialog",
        "tkinter.messagebox",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "android",
        "jnius",
        "kivy",
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
    name="OnTrack",
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
        os.path.join("assets", "icon.ico") if sys.platform == "win32"
        else os.path.join("assets", "icon.png") if sys.platform.startswith("linux")
        else None
    ),
)
#TODO: MacOS
# app = BUNDLE(
#     exe,
#     name="OnTrack.app",
#     icon=os.path.join("assets", "icon.icns"),
#     bundle_identifier="com.amorfatilabs.ontrack",
#     info_plist={
#         "NSHighResolutionCapable": True,
#         "LSMinimumSystemVersion": "12.0",
#     },
# )

