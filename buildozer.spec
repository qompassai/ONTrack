# /qompassai/ONTrack/buildozer.spec
[app]
title                        = ONTrack
package.name                 = ontrack
package.domain               = com.tds.ontrack
version                      = 2.0.0
source.dir                   = .
source.include_exts          = csv,ico,jpeg,jpg,json,kv,png,py
source.include_patterns      = assets/*,config/*,core/*,mobile/*
source.exclude_dirs = .buildozer,.git,.github,.mypy_cache,__pycache__,bin,build,dist,tests,venv,.venv


requirements =
    geopy,
    kivy==2.3.0,
    Pillow,
    plyer,
    python3,
    python-dotenv,
    faster-whisper
    ctranslate2
    requests

orientation                  = portrait
orientations                 = portrait,landscape
fullscreen                   = 0
icon.filename                = %(source.dir)s/assets/icon.png
presplash.filename           = %(source.dir)s/assets/icon.jpg
presplash.color              = #002855
presplash.keep_on_top        = 1

android.api                  = 35
android.minapi               = 26
android.ndk                  = 29
android.ndk_api              = 26
android.sdk_path             = /opt/android-sdk
android.archs                = arm64-v8a,armeabi-v7a
android.allow_backup         = 0
android.copy_libs            = 1
android.hide_statusbar       = 0
android.manifest.application_name = ONTrack
android.category             = PRODUCTIVITY
android.features             = android.hardware.location,android.hardware.location.gps

android.permissions =
    ACCESS_BACKGROUND_LOCATION,
    ACCESS_COARSE_LOCATION,
    ACCESS_FINE_LOCATION,
    ACCESS_NETWORK_STATE,
    INTERNET,
    READ_EXTERNAL_STORAGE,
    RECORD_AUDIO,
    WRITE_EXTERNAL_STORAGE

p4a.bootstrap                = sdl2
p4a.branch                   = develop

languages                    = en
entrypoint                   = main.py

[buildozer]
android.pip_args             = --index-url https://pypi.org/simple/ --no-extra-index-url
bin_dir                      = /var/tmp/buildozer/ontrack/bin
build_dir                    = /var/tmp/buildozer/ontrack/build
build_workers                = 0
clean_build                  = 0
log_level                    = 2
warn_on_root                 = 1

[python-for-android]
